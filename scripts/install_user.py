#!/usr/bin/env python3
"""Install the portable loop-graph-design Skill at user scope."""

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


VERSION = "0.6.0"
PACKAGE = "loop-graph-design"
MARKER_NAME = ".loop-graph-design-managed.json"
REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_SOURCE = (
    REPO_ROOT
    / "plugins"
    / PACKAGE
    / "skills"
    / PACKAGE
)
SUPPORTED_HOSTS = ("hermes", "claude", "codex", "kimi", "zcode", "opencode")


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
        statuses[host] = {
            "skill": status,
            "version": str(marker.get("version", "unknown")),
        }
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
                        f"{host}: skill={status['skill']} version={status['version']}"
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
