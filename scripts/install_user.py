#!/usr/bin/env python3
"""Install the portable ultra-goal Skill at user scope."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


VERSION = "2.11.0"
PACKAGE = "ultra-goal"
MARKER_NAME = ".ultra-goal-managed.json"
REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_SOURCE = (
    REPO_ROOT
    / "plugins"
    / PACKAGE
    / "skills"
    / PACKAGE
)
SUPPORTED_HOSTS = ("hermes", "claude", "codex", "kimi", "zcode", "opencode")

# Hook registration is host-specific and only Claude Code carries the event this
# Skill's gate needs. Measured, not assumed: Kimi exposes only SessionStart and
# PostCompact (and in TOML), OpenCode has no declarative hooks at all. The goal
# text works everywhere; the gate does not, and `doctor` says so rather than
# leaving a host quietly ungated.
HOOK_EVENTS = {
    "Stop": "goal_stop.py",
    "SessionStart": "goal_session_start.py",
    "PreCompact": "goal_pre_compact.py",
}
HOOK_MATCHERS = {"SessionStart": "^(startup|resume|clear|compact)$"}
# 600 is the hooks reference's documented default for a command hook; 200 was
# a number picked in isolation and it capped every anchor under four minutes -
# a 540s anchor would be permanently `unknown`, held by a limit nobody chose.
HOOK_TIMEOUTS = {"Stop": 600}
# The Stop registration names its host so the gate spends the right
# continuation budget; this installer only ever writes Claude Code's
# settings.json, so the tag is fixed. Keyed by script name because that is
# what _hook_command looks up - keyed by event name it was dead
# configuration, and the tag silently never landed (Codex round-1 F6).
HOOK_ARGS = {"goal_stop.py": "--host claude"}
HOOK_HOSTS = ("claude",)
# Matched against a normalised command string: a registration written on
# Windows carries backslashes, and comparing them raw made every identity check
# fail there - idempotence, doctor and uninstall all silently.
HOOK_TAG = "ultra-goal/scripts/goal_"


def _tagged(command: object) -> bool:
    return HOOK_TAG in str(command).replace("\\", "/")


class InstallError(RuntimeError):
    """A recoverable, owner-facing installer error."""


def _skill_destination(home: Path, host: str) -> Path:
    roots = {
        "hermes": home / ".hermes" / "skills",
        "claude": home / ".claude" / "skills",
        "codex": home / ".agents" / "skills",
        "kimi": home / ".kimi" / "skills",
        "zcode": home / ".zcode" / "skills",
        "opencode": home / ".config" / "opencode" / "skills",
    }
    return roots[host] / PACKAGE


def _parse_hosts(raw: str) -> list[str]:
    hosts: list[str] = []
    for item in raw.split(","):
        host = item.strip().lower()
        if not host or host in hosts:
            continue
        if host not in SUPPORTED_HOSTS:
            raise InstallError(
                f"Unsupported host {host!r}; choose from {', '.join(SUPPORTED_HOSTS)}."
            )
        hosts.append(host)
    if not hosts:
        raise InstallError("At least one host is required.")
    return hosts


def _default_backup_dir(home: Path, operation: str) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    return (
        home
        / ".local"
        / "state"
        / PACKAGE
        / "backups"
        / f"{stamp}-{operation}"
    )


def _read_marker(destination: Path) -> dict[str, Any]:
    marker = destination / MARKER_NAME
    if not marker.is_file():
        return {}
    try:
        value = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _is_managed(destination: Path) -> bool:
    return _read_marker(destination).get("package") == PACKAGE


def _write_marker(destination: Path) -> None:
    marker = {
        "package": PACKAGE,
        "version": VERSION,
        "installed_at": datetime.now(UTC).isoformat(),
    }
    (destination / MARKER_NAME).write_text(
        json.dumps(marker, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _tree_digest(root: Path) -> str | None:
    if not root.is_dir():
        return None
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or path.name == MARKER_NAME
            or "__pycache__" in path.parts
            or path.suffix == ".pyc"
        ):
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _backup_item(source: Path, destination: Path) -> None:
    if not source.exists() and not source.is_symlink():
        return
    if destination.exists() or destination.is_symlink():
        raise InstallError(f"Recovery destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir() and not source.is_symlink():
        shutil.copytree(source, destination, symlinks=True)
    else:
        shutil.copy2(source, destination, follow_symlinks=False)


def _replace_skill(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(
        tempfile.mkdtemp(prefix=f".{PACKAGE}-", dir=destination.parent)
    )
    staged = staging_root / destination.name
    retired = staging_root / "previous"
    try:
        shutil.copytree(
            SKILL_SOURCE,
            staged,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        _write_marker(staged)
        if destination.exists() or destination.is_symlink():
            destination.rename(retired)
        staged.rename(destination)
    except Exception:
        if not destination.exists() and retired.exists():
            retired.rename(destination)
        raise
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


def _settings_path(home: Path, host: str) -> Path:
    return home / ".claude" / "settings.json"


def _hook_command(home: Path, host: str, script: str) -> str:
    """Build the registered command.

    `sys.executable` rather than a bare `python3`: the latter is absent on most
    Windows installs, and a hook whose interpreter does not exist is a gate that
    fails silently - the exact outcome this Skill refuses elsewhere.

    The script's existence is checked before anything runs, and the interpreter
    is `exec`ed: both are for exit 2, which every host reads as a deliberate
    block. A missing script used to make Python exit 2 - a broken install
    blocking turns - and any non-zero status must be the hook's own decision,
    never the launcher's accident. A missing script is a fail-open allow.
    """
    target = _skill_destination(home, host) / "scripts" / script
    args = HOOK_ARGS.get(script, "")
    suffix = f" {args}" if args else ""
    return (
        f'P="{target}"; [ -f "$P" ] || exit 0; '
        f'exec "{sys.executable}" "$P"{suffix}'
    )


def _load_settings(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InstallError(
            f"{path} is not readable JSON ({exc}); fix or move it before installing hooks."
        ) from exc
    if not isinstance(value, dict):
        raise InstallError(f"{path} does not hold a JSON object.")
    return value


def _write_settings(path: Path, settings: dict[str, Any], backup_dir: Path) -> None:
    """Replace settings.json atomically, keeping a recovery copy of the original.

    Everything not owned by this Skill is preserved: entries are matched by the
    command path, so an unrelated hook on the same event survives untouched.
    """
    if path.exists():
        _backup_item(path, backup_dir / "settings.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(f".{path.name}.ultra-goal.tmp")
    staging.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    staging.replace(path)


def _strip_our_hooks(settings: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Remove only the entries whose command points at this Skill."""
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return settings, 0
    removed = 0
    for event, groups in list(hooks.items()):
        if not isinstance(groups, list):
            continue
        kept_groups = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                kept_groups.append(group)
                continue
            kept = [
                entry
                for entry in group["hooks"]
                if not _tagged(entry.get("command"))
            ]
            removed += len(group["hooks"]) - len(kept)
            if kept:
                kept_groups.append({**group, "hooks": kept})
        if kept_groups:
            hooks[event] = kept_groups
        else:
            hooks.pop(event)
    if not hooks:
        settings.pop("hooks", None)
    return settings, removed


def _register_hooks(home: Path, host: str, backup_dir: Path) -> list[str]:
    path = _settings_path(home, host)
    settings = _load_settings(path)
    settings, _ = _strip_our_hooks(settings)  # idempotent: never register twice
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise InstallError(f"{path} has a non-object 'hooks' key; fix it first.")
    added: list[str] = []
    for event, script in HOOK_EVENTS.items():
        entry: dict[str, Any] = {
            "type": "command",
            "command": _hook_command(home, host, script),
        }
        if event in HOOK_TIMEOUTS:
            entry["timeout"] = HOOK_TIMEOUTS[event]
        group = {"matcher": HOOK_MATCHERS.get(event, "*"), "hooks": [entry]}
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise InstallError(f"{path} has a non-list '{event}' hook list; fix it first.")
        groups.append(group)
        added.append(f"{event} -> {script}")
    _write_settings(path, settings, backup_dir)
    return added


def _unregister_hooks(home: Path, host: str, backup_dir: Path) -> int:
    path = _settings_path(home, host)
    if not path.is_file():
        return 0
    settings, removed = _strip_our_hooks(_load_settings(path))
    if removed:
        _write_settings(path, settings, backup_dir)
    return removed


def _hook_status(home: Path, host: str) -> dict[str, str]:
    """Report registration per event, so a wiped settings.json is visible.

    This exists because a settings.json rewritten by another tool can silently
    drop a registration and nobody notices for weeks.
    """
    if host not in HOOK_HOSTS:
        return {"hooks": "unsupported-host"}
    path = _settings_path(home, host)
    if not path.is_file():
        return {"hooks": "no-settings-file"}
    try:
        settings = _load_settings(path)
    except InstallError:
        return {"hooks": "settings-unreadable"}
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return {"hooks": "missing"}
    found = set()
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            for entry in group.get("hooks", []) or []:
                if _tagged(entry.get("command")):
                    found.add(event)
    missing = sorted(set(HOOK_EVENTS) - found)
    if not missing:
        if not Path(sys.executable).exists():
            return {"hooks": "interpreter-missing"}
        return {"hooks": "ok"}
    if not found:
        return {"hooks": "missing"}
    return {"hooks": "partial:" + ",".join(missing)}


def _preflight_install(home: Path, hosts: list[str], replace_existing: bool) -> None:
    if not (SKILL_SOURCE / "SKILL.md").is_file():
        raise InstallError(f"Bundled Skill is missing from {SKILL_SOURCE}.")
    for host in hosts:
        destination = _skill_destination(home, host)
        if (
            destination.exists() or destination.is_symlink()
        ) and not _is_managed(destination) and not replace_existing:
            raise InstallError(
                f"Refusing to replace unmanaged Skill {destination}; "
                "review it and pass --replace-existing if intended."
            )


def _install(
    home: Path,
    hosts: list[str],
    backup_dir: Path,
    replace_existing: bool,
) -> None:
    _preflight_install(home, hosts, replace_existing)
    for host in hosts:
        _backup_item(
            _skill_destination(home, host),
            backup_dir / host / "skill",
        )
    for host in hosts:
        _replace_skill(_skill_destination(home, host))
    for host in hosts:
        if host in HOOK_HOSTS:
            for line in _register_hooks(home, host, backup_dir / host):
                print(f"  {host}: registered {line}")
        else:
            print(
                f"  {host}: no hooks registered - this host does not expose the "
                "events the anchor gate needs; the goal text still works"
            )


def _preflight_uninstall(home: Path, hosts: list[str]) -> None:
    for host in hosts:
        destination = _skill_destination(home, host)
        if (
            destination.exists() or destination.is_symlink()
        ) and not _is_managed(destination):
            raise InstallError(f"Refusing to remove unmanaged Skill {destination}.")


def _uninstall(home: Path, hosts: list[str], backup_dir: Path) -> None:
    _preflight_uninstall(home, hosts)
    for host in hosts:
        destination = _skill_destination(home, host)
        _backup_item(destination, backup_dir / host / "skill")
    for host in hosts:
        if host in HOOK_HOSTS:
            removed = _unregister_hooks(home, host, backup_dir / host)
            if removed:
                print(f"  {host}: removed {removed} hook registration(s)")
    for host in hosts:
        destination = _skill_destination(home, host)
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        elif destination.is_dir():
            shutil.rmtree(destination)


def _doctor(home: Path, hosts: list[str]) -> dict[str, object]:
    source_digest = _tree_digest(SKILL_SOURCE)
    healthy = source_digest is not None
    statuses: dict[str, dict[str, str]] = {}
    for host in hosts:
        destination = _skill_destination(home, host)
        marker = _read_marker(destination)
        if not _is_managed(destination):
            status = "missing-or-unmanaged"
        elif _tree_digest(destination) != source_digest:
            status = "drifted"
        else:
            status = "ok"
        if status != "ok":
            healthy = False
        entry = {
            "skill": status,
            "version": str(marker.get("version", "unknown")),
        }
        entry.update(_hook_status(home, host))
        if entry["hooks"].startswith(
            ("missing", "partial", "settings-unreadable", "interpreter")
        ):
            healthy = False
        statuses[host] = entry
    return {"ok": healthy, "hosts": statuses}


def _add_common(parser: argparse.ArgumentParser, *, backup: bool) -> None:
    parser.add_argument(
        "--home",
        type=Path,
        default=Path.home(),
        help="User home containing host Skill directories (default: current user home)",
    )
    parser.add_argument(
        "--hosts",
        default=",".join(SUPPORTED_HOSTS),
        help="Comma-separated hosts: hermes,claude,codex,kimi,zcode,opencode",
    )
    if backup:
        parser.add_argument(
            "--backup-dir",
            type=Path,
            help="Exact recovery-copy directory (default: user state directory)",
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    install = commands.add_parser("install", help="Install or update selected hosts")
    _add_common(install, backup=True)
    install.add_argument(
        "--replace-existing",
        action="store_true",
        help="Back up and replace an unmanaged destination after review",
    )

    uninstall = commands.add_parser(
        "uninstall", help="Remove only managed copies of this Skill"
    )
    _add_common(uninstall, backup=True)

    doctor = commands.add_parser("doctor", help="Verify selected installed copies")
    _add_common(doctor, backup=False)
    doctor.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    home = args.home.expanduser().resolve()
    try:
        hosts = _parse_hosts(args.hosts)
        if args.command == "doctor":
            report = _doctor(home, hosts)
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                for host, status in report["hosts"].items():
                    print(
                        f"{host}: skill={status['skill']} "
                        f"hooks={status['hooks']} version={status['version']}"
                    )
            return 0 if report["ok"] else 1

        backup_dir = (
            args.backup_dir.expanduser().resolve()
            if args.backup_dir
            else _default_backup_dir(home, args.command)
        )
        if args.command == "install":
            _install(home, hosts, backup_dir, args.replace_existing)
            print(f"Installed for: {', '.join(hosts)}")
        else:
            _uninstall(home, hosts, backup_dir)
            print(f"Uninstalled for: {', '.join(hosts)}")
        print(f"Recovery copies: {backup_dir}")
        return 0
    except (InstallError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
