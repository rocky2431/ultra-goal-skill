"""Registration touches the owner's settings.json, which has been silently
wiped by other tools before. So: idempotent, non-destructive, backed up, and
detectably absent afterwards."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "scripts" / "install_user.py"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import install_user as iu  # noqa: E402


class Harness(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def settings(self) -> dict:
        path = self.home / ".claude" / "settings.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def run_installer(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(INSTALLER), *args, "--home", str(self.home)],
            capture_output=True, text=True, timeout=120,
        )

    def our_entries(self) -> list[str]:
        found = []
        for event, groups in (self.settings().get("hooks") or {}).items():
            for group in groups:
                for entry in group.get("hooks", []):
                    if iu._tagged(entry.get("command")):
                        found.append(event)
        return sorted(found)


class RegistrationTests(Harness):
    def test_install_registers_all_three_events_for_claude(self) -> None:
        result = self.run_installer("install", "--hosts", "claude")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["PreCompact", "SessionStart", "Stop"], self.our_entries())

    def test_registration_is_idempotent(self) -> None:
        self.run_installer("install", "--hosts", "claude")
        first = self.settings()
        self.run_installer("install", "--hosts", "claude")
        self.run_installer("install", "--hosts", "claude")
        self.assertEqual(["PreCompact", "SessionStart", "Stop"], self.our_entries())
        self.assertEqual(first, self.settings(), "re-installing must not accumulate")

    def test_unrelated_settings_and_hooks_survive(self) -> None:
        path = self.home / ".claude" / "settings.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({
            "model": "opus",
            "env": {"FOO": "bar"},
            "hooks": {
                "Stop": [{"matcher": "*", "hooks": [
                    {"type": "command", "command": "python3 /somebody/else/check.py"}
                ]}],
                "PostToolUse": [{"matcher": "Edit", "hooks": [
                    {"type": "command", "command": "python3 /somebody/else/guard.py"}
                ]}],
            },
        }, indent=2), encoding="utf-8")

        self.run_installer("install", "--hosts", "claude")
        after = self.settings()
        self.assertEqual("opus", after["model"])
        self.assertEqual({"FOO": "bar"}, after["env"])
        commands = [
            e["command"]
            for groups in after["hooks"].values()
            for g in groups
            for e in g["hooks"]
        ]
        self.assertIn("python3 /somebody/else/check.py", commands)
        self.assertIn("python3 /somebody/else/guard.py", commands)
        self.assertEqual(["PreCompact", "SessionStart", "Stop"], self.our_entries())

    def test_install_backs_up_the_original_settings(self) -> None:
        path = self.home / ".claude" / "settings.json"
        path.parent.mkdir(parents=True)
        path.write_text('{"model": "sonnet"}', encoding="utf-8")
        backup = self.home / "recovery"
        self.run_installer("install", "--hosts", "claude", "--backup-dir", str(backup))
        copies = list(backup.rglob("settings.json"))
        self.assertTrue(copies, "the original settings.json must be recoverable")
        self.assertIn("sonnet", copies[0].read_text(encoding="utf-8"))

    def test_uninstall_removes_only_our_entries(self) -> None:
        path = self.home / ".claude" / "settings.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"hooks": {"Stop": [{"matcher": "*", "hooks": [
            {"type": "command", "command": "python3 /somebody/else/check.py"}
        ]}]}}), encoding="utf-8")
        self.run_installer("install", "--hosts", "claude")
        self.run_installer("uninstall", "--hosts", "claude")
        self.assertEqual([], self.our_entries())
        remaining = [
            e["command"]
            for groups in (self.settings().get("hooks") or {}).values()
            for g in groups for e in g["hooks"]
        ]
        self.assertEqual(["python3 /somebody/else/check.py"], remaining)

    def test_a_host_without_the_events_registers_nothing_and_says_so(self) -> None:
        result = self.run_installer("install", "--hosts", "kimi")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("no hooks registered", result.stdout)
        self.assertIn("the goal text still works", result.stdout)
        self.assertFalse((self.home / ".claude" / "settings.json").exists())

    def test_unreadable_settings_refuses_rather_than_clobbering(self) -> None:
        path = self.home / ".claude" / "settings.json"
        path.parent.mkdir(parents=True)
        path.write_text("{ this is not json", encoding="utf-8")
        result = self.run_installer("install", "--hosts", "claude")
        self.assertEqual(2, result.returncode)
        self.assertIn("not readable JSON", result.stderr)
        self.assertEqual("{ this is not json", path.read_text(encoding="utf-8"))

    def test_the_registered_stop_command_names_its_host(self) -> None:
        """Codex round-1 F6: HOOK_ARGS was keyed by event name (`Stop`) while
        _hook_command looked it up by script name (`goal_stop.py`), so the
        generated registration silently carried no `--host claude` and ran as
        Claude only because Claude is the default - dead configuration one
        rename away from selecting the wrong budget."""
        self.run_installer("install", "--hosts", "claude")
        hooks = self.settings()["hooks"]
        stops = [
            entry["command"]
            for group in hooks["Stop"]
            for entry in group["hooks"]
            if iu._tagged(entry["command"])
        ]
        self.assertEqual(1, len(stops))
        self.assertIn("--host claude", stops[0])
        # Only the gate is host-sensitive; the recovery hooks carry no tag.
        for event in ("SessionStart", "PreCompact"):
            for group in hooks[event]:
                for entry in group["hooks"]:
                    if iu._tagged(entry["command"]):
                        self.assertNotIn("--host", entry["command"])


class DoctorTests(Harness):
    def doctor(self, host: str = "claude") -> dict:
        result = self.run_installer("doctor", "--hosts", host, "--json")
        return json.loads(result.stdout)

    def test_doctor_reports_ok_after_install(self) -> None:
        self.run_installer("install", "--hosts", "claude")
        report = self.doctor()
        self.assertTrue(report["ok"])
        self.assertEqual("ok", report["hosts"]["claude"]["hooks"])

    def test_doctor_notices_a_wiped_registration(self) -> None:
        """The real failure this exists for: another tool rewrites settings.json
        and the registration disappears without anyone noticing."""
        self.run_installer("install", "--hosts", "claude")
        path = self.home / ".claude" / "settings.json"
        path.write_text('{"model": "opus"}', encoding="utf-8")
        report = self.doctor()
        self.assertFalse(report["ok"])
        self.assertEqual("missing", report["hosts"]["claude"]["hooks"])

    def test_doctor_notices_a_partial_registration(self) -> None:
        self.run_installer("install", "--hosts", "claude")
        path = self.home / ".claude" / "settings.json"
        settings = json.loads(path.read_text(encoding="utf-8"))
        settings["hooks"].pop("Stop")
        path.write_text(json.dumps(settings), encoding="utf-8")
        report = self.doctor()
        self.assertFalse(report["ok"])
        self.assertEqual("partial:Stop", report["hosts"]["claude"]["hooks"])

    def test_doctor_says_unsupported_for_a_host_without_the_events(self) -> None:
        self.run_installer("install", "--hosts", "kimi")
        report = self.doctor("kimi")
        self.assertEqual("unsupported-host", report["hosts"]["kimi"]["hooks"])
        self.assertTrue(report["ok"], "an unsupported host is not a broken install")


if __name__ == "__main__":
    unittest.main()


class PlatformIdentityTests(Harness):
    """A registration written on Windows carries backslashes. Comparing the
    command string raw made every identity check fail there, so the path
    separator is normalised - and that is testable from any platform."""

    def windows_style_settings(self) -> Path:
        path = self.home / ".claude" / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"hooks": {"Stop": [{"matcher": "*", "hooks": [{
            "type": "command",
            "command": ('"C:\\Python312\\python.exe" "C:\\Users\\me\\.claude'
                        '\\skills\\ultra-goal\\scripts\\goal_stop.py"'),
        }]}]}}, indent=2), encoding="utf-8")
        return path

    def test_a_backslash_registration_is_recognised(self) -> None:
        self.assertTrue(iu._tagged(
            'py -3 "C:\\x\\ultra-goal\\scripts\\goal_stop.py"'))
        self.assertTrue(iu._tagged(
            'python3 "/home/me/ultra-goal/scripts/goal_stop.py"'))
        self.assertFalse(iu._tagged('python3 "/somebody/else/check.py"'))
        self.assertFalse(iu._tagged(None))

    def test_reinstall_over_a_backslash_registration_does_not_duplicate(self) -> None:
        self.windows_style_settings()
        self.run_installer("install", "--hosts", "claude")
        self.assertEqual(["PreCompact", "SessionStart", "Stop"], self.our_entries())
        stops = [
            e for groups in self.settings()["hooks"]["Stop"]
            for e in groups["hooks"] if iu._tagged(e["command"])
        ]
        self.assertEqual(1, len(stops), "the old backslash entry must be replaced")

    def test_uninstall_removes_a_backslash_registration(self) -> None:
        self.windows_style_settings()
        self.run_installer("uninstall", "--hosts", "claude")
        self.assertEqual([], self.our_entries())

    def test_the_registered_interpreter_exists(self) -> None:
        """A hook whose interpreter is absent is a gate that fails silently.
        The command now selects and `exec`s the interpreter once, so the
        interpreter is the token inside `exec "..."` - and the script's
        existence check keeps a deleted script a fail-open allow rather than
        an exit-2 block."""
        self.run_installer("install", "--hosts", "claude")
        for groups in self.settings()["hooks"].values():
            for group in groups:
                for entry in group["hooks"]:
                    if not iu._tagged(entry["command"]):
                        continue
                    command = entry["command"]
                    self.assertIn('exec "', command)
                    self.assertIn('[ -f "$P" ] || exit 0', command)
                    interpreter = command.split('exec "', 1)[1].split('"', 1)[0]
                    self.assertTrue(
                        Path(interpreter).exists(),
                        f"registered interpreter must exist: {interpreter}",
                    )
