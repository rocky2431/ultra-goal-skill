"""The early exit is the only thing between an installed hook and a project
that never asked for one. It is tested from every angle, and every failure
path must lead to exit 0 with no side effects."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    REPO_ROOT
    / "plugins"
    / "ultra-goal"
    / "skills"
    / "ultra-goal"
    / "scripts"
)
sys.path.insert(0, str(SCRIPTS))
import goal_hooks as lh  # noqa: E402


# `true` and `test -f` are not commands on cmd.exe, so the fixtures drive the
# gate through the interpreter running the tests - present on every platform.
GREEN = f'"{sys.executable}" -c "raise SystemExit(0)"'
RED = f'"{sys.executable}" -c "raise SystemExit(1)"'

GOAL = """# Goal: demo

## Intent

Keep the suite green.

## Boundary

**Scope.** Only `src/`.

**Confidence.** Never call it passing without the anchor output.

**Inference.** Never conclude from logs alone.

## Stop condition

Stop when `true` succeeds, or after 4 turns.
success: verified
ceiling: 4

## Anchor

```
__ANCHOR__
```

## Verification

A fresh agent re-runs the anchor.

```json
{"source":"external","basis":"Independent test fixture controls the command.","protected":[],"covers":{"result":"anchor"},"review":null}
```

## Acceptance

- [ ] result: The command proves the fixture outcome.

## Cadence

Started by hand.

## Carry-over

Read this before acting; rewrite it before finishing.

### State

- nothing yet

### Lessons

- nothing yet

### Next

- make the anchor pass

## Handoff

```
/goal Keep the suite green.
```
"""


GOAL = GOAL.replace("__ANCHOR__", GREEN)


class Harness(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def make_loop(self, slug: str = "demo", goal: str = GOAL) -> Path:
        goals = self.cwd / ".goals"
        goals.mkdir(exist_ok=True)
        (goals / f"{slug}.goal.md").write_text(goal, encoding="utf-8")
        (goals / "active").write_text(f"{slug}\nsession session-aaa\n", encoding="utf-8")
        # The arming-time spec baseline: since round 5 the gate compares every
        # Stop against this file (what `goal_run.py arm` records) and never
        # against a digest in the event log, and a run without one has its
        # claims refused rather than judged - so a test that wants a judged
        # run arms it the way the fence does.
        (goals / f"{slug}.spec.baseline").write_text(
            lh.frozen_digest(goal) + "\n", encoding="utf-8"
        )
        (goals / f"{slug}.verification.baseline").write_text("{}\n", encoding="utf-8")
        (goals / f"{slug}.verification.lock").touch()
        return goals

    def claim(self, slug: str = "demo") -> None:
        """Write the completion candidate: the run's explicit, self-reported
        claim that the goal is met. It only triggers the gate's check - it
        grants nothing - and the gate consumes it when it rules."""
        (self.cwd / ".goals" / f"{slug}.candidate").write_text(
            "claiming completion\n", encoding="utf-8"
        )

    def snapshot(self) -> set[str]:
        return {
            str(p.relative_to(self.cwd))
            for p in self.cwd.rglob("*")
            if p.is_file()
        }


class ActivationTests(Harness):
    def test_no_goals_directory_is_inactive(self) -> None:
        self.assertIsNone(lh.active_goal(self.cwd))

    def test_goals_directory_without_active_marker_is_inactive(self) -> None:
        (self.cwd / ".goals").mkdir()
        (self.cwd / ".goals" / "x.goal.md").write_text(GOAL, encoding="utf-8")
        self.assertIsNone(lh.active_goal(self.cwd))

    def test_active_marker_pointing_at_a_missing_goal_is_inactive(self) -> None:
        goals = self.cwd / ".goals"
        goals.mkdir()
        (goals / "active").write_text("ghost\n", encoding="utf-8")
        self.assertIsNone(lh.active_goal(self.cwd))

    def test_empty_active_marker_is_inactive(self) -> None:
        goals = self.cwd / ".goals"
        goals.mkdir()
        (goals / "active").write_text("   \n", encoding="utf-8")
        self.assertIsNone(lh.active_goal(self.cwd))

    def test_active_marker_that_is_a_directory_is_inactive(self) -> None:
        (self.cwd / ".goals" / "active").mkdir(parents=True)
        self.assertIsNone(lh.active_goal(self.cwd))

    def test_a_slug_with_a_path_separator_is_refused(self) -> None:
        """The marker names a slug, not a path. Traversal is not a loop."""
        goals = self.cwd / ".goals"
        goals.mkdir()
        (goals / "active").write_text("../../etc/passwd\n", encoding="utf-8")
        self.assertIsNone(lh.active_goal(self.cwd))

    def test_a_real_loop_resolves(self) -> None:
        self.make_loop()
        found = lh.active_goal(self.cwd)
        self.assertIsNotNone(found)
        self.assertEqual("demo", found.slug)
        self.assertTrue(found.goal_path.is_file())
        self.assertEqual(
            ".goals/demo.events.jsonl",
            found.events_path.relative_to(self.cwd).as_posix(),
        )
        self.assertEqual("session-aaa", found.owner_session)


class SessionOwnershipTests(Harness):
    """Defect 1.4: `.goals/active` had no session ownership, so another
    session working in the same cwd had its Stops gated on a goal it never
    ran - and its prompt boundaries resetting the owner's streak.

    Arming records the initiating session before any hook can run. Every
    measured host supplies session_id in its common hook envelope.

    The limit is stated with the fix: a session id is ownership
    information, not an anti-forgery key. Any process that can write files
    can write the marker; what the id buys is that an unrelated session's
    ordinary hooks leave the run alone.
    """

    def stop_with(self, session_id: str | None,
                  script: str = "goal_stop.py") -> subprocess.CompletedProcess:
        payload = {"hook_event_name": "Stop", "cwd": str(self.cwd)}
        if session_id is not None:
            payload["session_id"] = session_id
        return subprocess.run(
            [sys.executable, str(SCRIPTS / script)],
            input=json.dumps(payload),
            capture_output=True, text=True, timeout=60,
        )

    def prompt_with(self, session_id: str | None) -> subprocess.CompletedProcess:
        payload = {"hook_event_name": "UserPromptSubmit", "cwd": str(self.cwd)}
        if session_id is not None:
            payload["session_id"] = session_id
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_prompt_submit.py")],
            input=json.dumps(payload),
            capture_output=True, text=True, timeout=60,
        )

    def events(self) -> list[dict]:
        path = self.cwd / ".goals" / "demo.events.jsonl"
        if not path.is_file():
            return []
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    def marker(self) -> str:
        return (self.cwd / ".goals" / "active").read_text(encoding="utf-8")

    def test_stop_preserves_the_already_bound_session(self) -> None:
        self.make_loop()
        self.stop_with("session-aaa")
        self.assertEqual("demo\nsession session-aaa\n", self.marker())

    def test_a_second_session_is_invisible_to_the_gate(self) -> None:
        """The defect, reproduced then closed: session B works in the same
        cwd, its Stop runs no anchor, writes no event, and says nothing."""
        self.make_loop()
        self.stop_with("session-aaa")
        before = len(self.events())
        result = self.stop_with("session-bbb")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stdout.strip(), "not B's run to gate")
        self.assertEqual(before, len(self.events()))

    def test_a_second_session_prompt_does_not_reset_the_streak(self) -> None:
        """The quieter half of the same defect: B's UserPromptSubmit used to
        write a boundary event into the owner's log, resetting the owner's
        continuation streak from outside the run."""
        self.make_loop()
        self.stop_with("session-aaa")
        before = len(self.events())
        result = self.prompt_with("session-bbb")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stdout.strip())
        self.assertEqual(before, len(self.events()))

    def test_a_sessionless_event_cannot_consume_the_owners_claim(self) -> None:
        self.make_loop()
        self.claim()
        result = self.stop_with(None)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stdout.strip())
        self.assertTrue((self.cwd / ".goals" / "demo.candidate").is_file())
        self.assertEqual([], self.events())

    def test_a_garbage_session_line_is_ignored_not_fatal(self) -> None:
        self.make_loop()
        (self.cwd / ".goals" / "active").write_text(
            "demo\nsession ../../not a session\n", encoding="utf-8")
        result = self.stop_with("session-bbb")
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual({"systemMessage"}, set(payload))
        self.assertIn("invalid session binding", payload["systemMessage"])
        self.assertEqual([], self.events())

    def test_the_owner_session_travels_with_the_measurement(self) -> None:
        self.make_loop()
        self.claim()
        self.stop_with("session-aaa")
        checks = [e for e in self.events() if e.get("event") == "anchor_checked"]
        self.assertEqual("session-aaa", checks[0].get("session_id"))

    def test_ownership_is_enforced_by_every_hook_not_just_the_gate(self) -> None:
        """The injection hooks must not hand session B the owner's frozen
        spec either: `owns_goal` lives in run_hook, below every handler."""
        self.make_loop()
        self.stop_with("session-aaa")
        payload = {"hook_event_name": "SessionStart", "cwd": str(self.cwd),
                   "source": "resume", "session_id": "session-bbb"}
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_session_start.py")],
            input=json.dumps(payload),
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stdout.strip(), "not B's spec to receive")

    def test_foreign_first_stop_cannot_take_over_the_run(self) -> None:
        self.make_loop()
        self.claim()
        result = self.stop_with("session-bbb")
        self.assertEqual("", result.stdout.strip())
        self.assertEqual("demo\nsession session-aaa\n", self.marker())
        self.assertEqual([], self.events())
        self.assertTrue((self.cwd / ".goals" / "demo.candidate").is_file())
        self.stop_with("session-aaa")
        checks = [e for e in self.events() if e.get("event") == "anchor_checked"]
        self.assertEqual(1, len(checks))
        self.assertEqual("session-aaa", checks[0]["session_id"])

    def test_legacy_unbound_marker_warns_without_activating_the_gate(self) -> None:
        for host in ("claude", "codex", "kimi", "zcode"):
            with self.subTest(host=host):
                self.make_loop()
                (self.cwd / ".goals" / "active").write_text("demo\n", encoding="utf-8")
                self.claim()
                before = {p.relative_to(self.cwd): p.read_bytes()
                          for p in self.cwd.rglob("*") if p.is_file()}
                result = subprocess.run(
                    [sys.executable, str(SCRIPTS / "goal_stop.py"), "--host", host],
                    input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd),
                                      "session_id": "session-bbb"}),
                    capture_output=True, text=True, timeout=60,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertTrue(result.stdout.strip(), "An unbound marker needs a diagnostic.")
                payload = json.loads(result.stdout)
                self.assertEqual({"systemMessage"}, set(payload))
                self.assertIn("legacy or invalid session binding", payload["systemMessage"])
                self.assertIn("no verification was performed", payload["systemMessage"])
                self.assertIn("rebind", payload["systemMessage"])
                after = {p.relative_to(self.cwd): p.read_bytes()
                         for p in self.cwd.rglob("*") if p.is_file()}
                self.assertEqual(before, after, "A diagnostic must not arm, consume or record work.")

    def test_activation_check_has_no_side_effects(self) -> None:
        self.make_loop()
        before = self.snapshot()
        lh.active_goal(self.cwd)
        lh.active_goal(self.cwd)
        self.assertEqual(before, self.snapshot())

    def test_inactive_check_writes_nothing(self) -> None:
        before = self.snapshot()
        lh.active_goal(self.cwd)
        self.assertEqual(before, self.snapshot())

    def test_unreadable_cwd_is_inactive_not_an_error(self) -> None:
        self.assertIsNone(lh.active_goal(self.cwd / "does-not-exist"))
        self.assertIsNone(lh.active_goal(None))


class FailOpenTests(Harness):
    def test_a_handler_that_raises_still_exits_zero(self) -> None:
        def boom(event, loop):
            raise RuntimeError("handler blew up")

        self.assertEqual(0, lh.run_hook("Stop", boom, stdin_text="{}"))

    def test_garbage_stdin_exits_zero(self) -> None:
        calls = []
        self.assertEqual(
            0, lh.run_hook("Stop", lambda e, l, h: calls.append(e), stdin_text="not json")
        )
        self.assertEqual([], calls, "the handler must not run on unparseable input")

    def test_wrong_event_name_exits_zero_without_calling_the_handler(self) -> None:
        calls = []
        payload = json.dumps({"session_id": "session-aaa", "hook_event_name": "PostToolUse", "cwd": str(self.cwd)})
        self.assertEqual(
            0, lh.run_hook("Stop", lambda e, l, h: calls.append(e), stdin_text=payload)
        )
        self.assertEqual([], calls)

    def test_inactive_project_exits_zero_without_calling_the_handler(self) -> None:
        calls = []
        payload = json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)})
        self.assertEqual(
            0, lh.run_hook("Stop", lambda e, l, h: calls.append(e), stdin_text=payload)
        )
        self.assertEqual([], calls, "no loop here, so the handler is never reached")

    def test_stop_hook_active_still_reaches_the_handler(self) -> None:
        """`stop_hook_active` marks a continuation, not a reason to go quiet.

        The one-shot guard this replaced read the host's post-mortem advice as
        general guidance: Claude Code prints "return success while
        stop_hook_active is true" only after its consecutive-block cap is
        exceeded, so honouring it eagerly meant the gate blocked exactly once
        per host turn and `ceiling: 40` was unreachable by the gate alone. The
        guard against a gate that denies forever is now the per-host
        continuation budget, counted from the gate's own events.
        """
        self.make_loop()
        calls = []
        payload = json.dumps(
            {"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd), "stop_hook_active": True}
        )
        self.assertEqual(
            0, lh.run_hook("Stop", lambda e, l, h: calls.append(e), stdin_text=payload)
        )
        self.assertEqual(1, len(calls), "a continuation is still gated")

    def test_disable_env_var_is_honoured(self) -> None:
        self.make_loop()
        calls = []
        payload = json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)})
        self.assertEqual(
            0,
            lh.run_hook(
                "Stop",
                lambda e, l, h: calls.append(e),
                stdin_text=payload,
                env={"ULTRA_GOAL_HOOKS_DISABLED": "1"},
            ),
        )
        self.assertEqual([], calls)

    def test_an_active_goal_reaches_the_handler(self) -> None:
        self.make_loop()
        seen = {}
        payload = json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)})

        def handler(event, loop, host):
            seen["slug"] = loop.slug
            return None

        self.assertEqual(0, lh.run_hook("Stop", handler, stdin_text=payload))
        self.assertEqual("demo", seen.get("slug"))


class ScriptSmokeTests(Harness):
    """Each hook script must be invocable and silent in an unrelated project."""

    SCRIPT_EVENTS = {
        "goal_stop.py": "Stop",
        "goal_session_start.py": "SessionStart",
        "goal_pre_compact.py": "PreCompact",
    }

    def run_script(self, name: str, payload: dict) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / name)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_every_script_exits_zero_and_is_silent_without_a_loop(self) -> None:
        for name, event in self.SCRIPT_EVENTS.items():
            with self.subTest(script=name):
                before = self.snapshot()
                result = self.run_script(
                    name, {"session_id": "session-aaa", "hook_event_name": event, "cwd": str(self.cwd)}
                )
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual("", result.stdout.strip())
                self.assertEqual(before, self.snapshot())

    def test_every_script_survives_garbage_stdin(self) -> None:
        for name in self.SCRIPT_EVENTS:
            with self.subTest(script=name):
                result = subprocess.run(
                    [sys.executable, str(SCRIPTS / name)],
                    input="}{ not json",
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(0, result.returncode, result.stderr)


class LauncherContractTests(Harness):
    """The command string the hosts actually execute, not just the script
    behind it. Two confirmed defects (plan section 1.2 and 1.3):

    - `python3 X || python X` re-runs the hook when the first run exits 2,
      with stdin already drained, and the final status is the second run's -
      so the one code every host here reads as a deliberate block was being
      swallowed by the launcher itself. The plan reproduced it with a probe
      script; these tests drive the shipped command strings the same way.
    - A missing script file or an argparse error also exits 2, and all four
      hosts read exit 2 as a deliberate block. Fail-open must therefore
      cover the launch and argument handling, not only the inside of
      `run_hook`.
    """

    STUB = (
        "import sys\n"
        "from pathlib import Path\n"
        "log = Path(__file__).with_name('runs.txt')\n"
        "with log.open('a') as f:\n"
        "    f.write('run\\n')\n"
        "sys.stdin.read()\n"
        "raise SystemExit(2)\n"
    )

    def command_from(self, relative: str, event: str) -> str:
        manifest = json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))
        hooks = manifest["hooks"]
        if isinstance(hooks, dict):
            return hooks[event][0]["hooks"][0]["command"]
        entry = next(h for h in hooks if h.get("event") == event)
        return entry["command"]

    def stub_root(self) -> Path:
        root = self.cwd / "plugin"
        script = root / "skills" / "ultra-goal" / "scripts" / "goal_stop.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(self.STUB, encoding="utf-8")
        return root

    def run_launcher(
        self, command: str, root: Path, payload: str = "{}"
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["/bin/sh", "-c", command],
            input=payload,
            capture_output=True, text=True, timeout=60,
            env={"PATH": os.environ.get("PATH", ""), "PLUGIN_ROOT": str(root)},
            cwd=str(root),
        )

    def runs(self, root: Path) -> int:
        log = root / "skills" / "ultra-goal" / "scripts" / "runs.txt"
        return len(log.read_text().splitlines()) if log.is_file() else 0

    def test_the_shipped_stop_command_preserves_exit_2_and_runs_once(self) -> None:
        root = self.stub_root()
        result = self.run_launcher(
            self.command_from("plugins/ultra-goal/hooks/hooks.json", "Stop"), root
        )
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertEqual(1, self.runs(root),
                         "the hook must execute once: a second run sees drained "
                         "stdin and swallows the deliberate exit 2")

    def test_the_codex_and_kimi_stop_commands_preserve_exit_2(self) -> None:
        for relative in ("plugins/ultra-goal/hooks/codex.json",
                         "plugins/ultra-goal/kimi.plugin.json"):
            with self.subTest(manifest=relative):
                root = self.stub_root()
                before = self.runs(root)
                result = self.run_launcher(
                    self.command_from(relative, "Stop"), root
                )
                self.assertEqual(2, result.returncode, result.stderr)
                self.assertEqual(1, self.runs(root) - before)

    def test_a_missing_script_fails_open_not_block(self) -> None:
        root = self.cwd / "plugin"
        (root / "skills" / "ultra-goal" / "scripts").mkdir(parents=True)
        for relative, event in (
            ("plugins/ultra-goal/hooks/hooks.json", "Stop"),
            ("plugins/ultra-goal/hooks/hooks.json", "SessionStart"),
            ("plugins/ultra-goal/hooks/hooks.json", "PostToolUseFailure"),
            ("plugins/ultra-goal/hooks/claude.json", "PreCompact"),
            ("plugins/ultra-goal/hooks/codex.json", "Stop"),
            ("plugins/ultra-goal/hooks/codex.json", "SessionStart"),
            ("plugins/ultra-goal/kimi.plugin.json", "Stop"),
            ("plugins/ultra-goal/kimi.plugin.json", "UserPromptSubmit"),
            ("plugins/ultra-goal/kimi.plugin.json", "TurnStarted"),
        ):
            with self.subTest(entry=f"{relative}:{event}"):
                result = self.run_launcher(
                    self.command_from(relative, event), root
                )
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual("", result.stdout.strip())

    def test_a_missing_interpreter_falls_back_exactly_once(self) -> None:
        """The fallback the `||` was originally written for: python3 absent,
        python present. It must still run the hook once and keep its status."""
        root = self.stub_root()
        binroot = self.cwd / "bin"
        binroot.mkdir()
        (binroot / "python").symlink_to(sys.executable)
        result = subprocess.run(
            ["/bin/sh", "-c",
             self.command_from("plugins/ultra-goal/hooks/hooks.json", "Stop")],
            input="{}", capture_output=True, text=True, timeout=60,
            env={"PATH": f"{binroot}:/usr/bin:/bin", "PLUGIN_ROOT": str(root)},
            cwd=str(root),
        )
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertEqual(1, self.runs(root))

    def test_an_argparse_error_fails_open_not_block(self) -> None:
        """`--host` without a value makes argparse exit 2 - the same code the
        hosts read as a deliberate block. Reproduced, then guarded: the whole
        launch path is inside the fail-open now."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py"), "--host"],
            input="{}", capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stdout.strip())

    def test_the_shipped_command_still_runs_the_real_hook(self) -> None:
        root = (REPO_ROOT / "plugins" / "ultra-goal").resolve()
        self.make_loop()
        self.claim()
        result = subprocess.run(
            ["/bin/sh", "-c",
             self.command_from("plugins/ultra-goal/hooks/hooks.json", "Stop")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=60,
            env={"PATH": os.environ.get("PATH", ""),
                 "CLAUDE_PLUGIN_ROOT": str(root)},
            cwd=str(self.cwd),
        )
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("passed on attempt", payload["systemMessage"])


if __name__ == "__main__":
    unittest.main()


class ZCodeRootLauncherTests(Harness):
    """Round-4 F2: the shared launcher resolved
    `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}` and used `ZCODE_PLUGIN_ROOT` only
    to append `--host zcode` - so under zCode's own documented root every
    path became `/skills/...`, failed the existence guard, and exited 0 with
    no hook loaded. The root chain must fall through to zCode's variable."""

    def command(self) -> str:
        manifest = json.loads(
            (REPO_ROOT / "plugins" / "ultra-goal" / "hooks" / "hooks.json")
            .read_text(encoding="utf-8")
        )
        return manifest["hooks"]["Stop"][0]["hooks"][0]["command"]

    def test_zcode_s_documented_root_actually_loads_the_gate(self) -> None:
        import os

        self.make_loop(goal=GOAL.replace(f"```\n{GREEN}\n```", f"```\n{RED}\n```"))
        self.claim()
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "ZCODE_PLUGIN_ROOT": str(REPO_ROOT / "plugins" / "ultra-goal"),
        }
        result = subprocess.run(
            ["/bin/sh", "-c", self.command()],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=60, env=env,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            "block",
            json.loads(result.stdout)["decision"],
            "under ZCODE_PLUGIN_ROOT alone the gate must run and tag itself "
            "zcode - an empty output here is a silently dead gate",
        )

    def test_the_windows_launch_paths_guard_and_fail_open(self) -> None:
        """Round-4 F1: `commandWindows` ran `py -3 <script>` with no existence
        guard and no fail-open, so the pre-handler exit-2 path phase 0 had to
        eliminate was still open there. Native Windows behaviour cannot be
        driven on this machine (a named gap in the round-5 report); the
        regression pins the shipped shape: guard the script's existence,
        guard the interpreter's, and any failure before the script runs is
        exit 0 - never the exit 2 every host reads as a deliberate block."""
        for relative in ("plugins/ultra-goal/hooks/hooks.json",
                         "plugins/ultra-goal/hooks/claude.json"):
            manifest = json.loads(
                (REPO_ROOT / relative).read_text(encoding="utf-8")
            )
            for event, groups in manifest["hooks"].items():
                for group in groups:
                    for hook in group["hooks"]:
                        windows = hook.get("commandWindows")
                        if windows is None:
                            continue
                        with self.subTest(entry=f"{relative}:{event}"):
                            self.assertIn("if not exist", windows,
                                          "the script's existence is guarded")
                            self.assertIn("exit 0", windows,
                                          "a missing script fails open")
                            self.assertIn("where py", windows,
                                          "the interpreter is selected, not assumed")
                            self.assertIn("|| exit 0", windows,
                                          "a missing interpreter fails open too")


class CheckedTransitionTests(Harness):
    """Round-4 F10: a failed state transition was reported as a success - a
    green allow announced over a zero-byte log, one surviving candidate
    judged twice, a disarm announced while the marker survived. Every
    consume/record/disarm transition is checked now, and the report says
    what actually happened."""

    def events(self) -> list[dict]:
        path = self.cwd / ".goals" / "demo.events.jsonl"
        if not path.is_file():
            return []
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    def stop(self) -> dict:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def test_an_unwritable_log_is_reported_as_unrecorded_not_passed(self) -> None:
        import os
        import stat

        self.make_loop()  # a green anchor
        self.claim()
        log = self.cwd / ".goals" / "demo.events.jsonl"
        log.write_text("", encoding="utf-8")
        mode = stat.S_IMODE(log.lstat().st_mode)
        os.chmod(log, mode & ~stat.S_IWUSR)
        try:
            payload = self.stop()
        finally:
            os.chmod(log, mode)
        self.assertNotIn("passed on attempt", payload["systemMessage"])
        self.assertIn(
            "unrecorded", payload["systemMessage"],
            "a green announced over an unwritten log is a false announcement",
        )
        self.assertEqual(0, log.stat().st_size)
        self.assertTrue((self.cwd / ".goals" / "demo.candidate").exists())

    def test_an_unconsumable_claim_is_refused_not_judged_twice(self) -> None:
        import os
        import stat

        self.make_loop()
        self.claim()
        goals = self.cwd / ".goals"
        # Keep the journal writable while directory permissions forbid unlink:
        # this isolates candidate consumption from the separate start-write gate.
        (goals / "demo.events.jsonl").write_text("")
        mode = stat.S_IMODE(goals.lstat().st_mode)
        os.chmod(goals, mode & ~stat.S_IWUSR)
        messages = []
        try:
            for _ in range(2):
                payload = self.stop()
                messages.append(
                    payload.get("reason", payload.get("systemMessage", ""))
                )
        finally:
            os.chmod(goals, mode)
        self.assertTrue(all("could not be removed" in m for m in messages),
                        messages)
        self.assertFalse(
            any(e.get("event") == "anchor_checked" for e in self.events()),
            "a claim that cannot be consumed must never be judged",
        )
        self.assertTrue(
            (goals / "demo.candidate").exists(),
            "the claim survives precisely because it could not be consumed",
        )

    def test_a_failed_disarm_is_not_announced_as_a_disarm(self) -> None:
        import os
        import stat

        self.make_loop()
        spec = (self.cwd / ".goals" / "demo.goal.md").read_text(encoding="utf-8")
        (self.cwd / ".goals" / "demo.goal.md").write_text(
            spec.replace("## Intent\n\nKeep the suite green.",
                         "## Intent\n\nEDITED GOALPOST"),
            encoding="utf-8",
        )
        goals = self.cwd / ".goals"
        # Keep the log appendable while directory permissions prevent unlink.
        (goals / "demo.events.jsonl").touch()
        mode = stat.S_IMODE(goals.lstat().st_mode)
        os.chmod(goals, mode & ~stat.S_IWUSR)
        try:
            first = self.stop()
            second = self.stop()
        finally:
            os.chmod(goals, mode)
        for payload in (first, second):
            self.assertIn("could not remove", payload["systemMessage"])
            self.assertNotIn("gate is disarmed", payload["systemMessage"])
        self.assertTrue((goals / "active").exists())
        closures = [e for e in self.events() if e.get("event") == "frozen_spec_changed"]
        self.assertEqual(2, len(closures), "each observed closure remains auditable")
        self.assertTrue(all(not e["completion_candidate"] for e in closures))


class CompletionContractTests(Harness):
    """The anchor runs at exactly one moment: a completion candidate.

    An ordinary Stop means "I want to end a host turn", not "the goal is
    met" - so it is never blocked, runs nothing, and gets at most one short
    deterministic omission reminder. The candidate is the run's own marker,
    self-reported: it triggers the check and grants nothing. The gate
    consumes it when it rules (one claim, one judgment), checks ownership,
    the authorized spec baseline and the anchor identity first, refuses
    while a delegated role's failure is the log's last word for the turn,
    bounds attempts by the owner's ceiling, and executes the current anchor
    once against the current state - ruling on that result alone. A
    historical green is never a pass input; old rows are audit only.
    """

    def stop(self, anchor: str = GREEN, claim: bool = True,
             host: str | None = None,
             payload_extra: dict | None = None) -> dict:
        goal = GOAL.replace(f"```\n{GREEN}\n```", f"```\n{anchor}\n```")
        self.make_loop(goal=goal)
        if claim:
            self.claim()
        payload = {"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}
        payload.update(payload_extra or {})
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py"),
             *(["--host", host] if host else [])],
            input=json.dumps(payload),
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def events(self) -> list[dict]:
        path = self.cwd / ".goals" / "demo.events.jsonl"
        if not path.is_file():
            return []
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    def decision(self, payload: dict) -> str | None:
        if payload.get("decision") == "block":
            return "block"
        nested = payload.get("hookSpecificOutput", {}).get("permissionDecision")
        return "block" if nested == "deny" else nested

    def test_an_ordinary_stop_runs_nothing_and_never_blocks(self) -> None:
        witness = self.cwd / "anchor-ran"
        anchor = f'"{sys.executable}" -c "open(r\'{witness}\', \'a\').write(\'x\')"'
        payload = self.stop(anchor, claim=False)
        self.assertIsNone(
            self.decision(payload),
            "an ordinary Stop wants to end a host turn; the gate has no "
            "ground to hold it",
        )
        self.assertFalse(witness.exists(), "no claim, no anchor run")
        self.assertEqual("stop_ordinary", self.events()[-1]["event"])

    def test_the_ordinary_stop_reminder_is_short_and_counts(self) -> None:
        goal = GOAL.replace(
            "## Carry-over",
            "## Acceptance\n\n- [ ] one\n- [ ] two\n\n## Carry-over",
        )
        self.make_loop(goal=goal)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=60,
        )
        message = json.loads(result.stdout)["systemMessage"]
        self.assertIn("without a completion claim", message)
        self.assertIn("2 `## Acceptance` line(s) are still open", message)
        self.assertNotIn("one\n", message)
        self.assertNotIn("two left", message)

    def test_a_candidate_runs_the_anchor_once_against_current_state(self) -> None:
        witness = self.cwd / "anchor-ran"
        anchor = f'"{sys.executable}" -c "open(r\'{witness}\', \'a\').write(\'x\')"'
        self.stop(anchor)
        self.assertEqual("x", witness.read_text())
        checks = [e for e in self.events() if e.get("event") == "anchor_checked"]
        self.assertEqual(1, len(checks))
        for field in ("spec_digest", "anchor_digest", "tree_digest",
                      "exit_code", "output_digest", "turn"):
            self.assertIn(field, checks[0], field)

    def test_the_candidate_is_consumed_by_its_judgment(self) -> None:
        """One claim, one judgment: the marker is gone after the gate rules,
        so state changing later cannot resurrect the claim, and a new claim
        needs a new marker."""
        self.stop(RED)
        self.assertFalse(
            (self.cwd / ".goals" / "demo.candidate").exists(),
            "a judged claim must not linger to gate a later turn",
        )
        payload = self.stop(RED, claim=False)
        self.assertIsNone(self.decision(payload))
        self.assertEqual("stop_ordinary", self.events()[-1]["event"])

    def test_a_stale_green_is_never_a_pass_input(self) -> None:
        """The gate never reads a historical green: after a green ruling, new
        work and a new claim mean the anchor executes again - the old row is
        audit, not evidence."""
        witness = self.cwd / "anchor-ran"
        anchor = f'"{sys.executable}" -c "open(r\'{witness}\', \'a\').write(\'x\')"'
        self.stop(anchor)
        self.stop(anchor)
        self.assertEqual("xx", witness.read_text(),
                         "the second claim must re-run the anchor")
        checks = [e for e in self.events() if e.get("event") == "anchor_checked"]
        self.assertEqual(2, len(checks))

    def test_green_proves_only_this_anchor_on_this_state(self) -> None:
        payload = self.stop(GREEN)
        self.assertIn("passed on attempt", payload["systemMessage"])
        self.assertTrue(self.events()[-1]["verification_passed"])
        self.assertNotIn("Goal met", payload["systemMessage"])

    def test_a_wrong_session_candidate_is_never_judged(self) -> None:
        self.make_loop()
        payload = {"hook_event_name": "Stop", "cwd": str(self.cwd),
                   "session_id": "session-aaa"}
        self.claim()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps(payload), capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(0, result.returncode)
        self.assertNotEqual("", result.stdout.strip())
        # Session B's stop over a fresh claim: silent, candidate untouched.
        self.claim()
        payload["session_id"] = "session-bbb"
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps(payload), capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stdout.strip())
        self.assertTrue((self.cwd / ".goals" / "demo.candidate").exists(),
                        "B's stop must not consume the owner's claim")

    def test_transport_failure_does_not_replace_current_acceptance_evidence(self) -> None:
        log = self.cwd / ".goals" / "demo.events.jsonl"
        self.make_loop()
        log.write_text(json.dumps({
            "event": "role_unavailable", "role": "reviewer",
            "tool": "agent-delegate", "detail": "target did not answer",
        }) + "\n", encoding="utf-8")
        self.claim()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=60,
        )
        payload = json.loads(result.stdout)
        self.assertIsNone(self.decision(payload))
        self.assertTrue(self.events()[-1]["verification_passed"])
        self.assertEqual(["reviewer"], self.events()[-1]["unrecovered_targets"])

    def test_a_role_failure_is_not_erased_by_a_turn_boundary(
        self,
    ) -> None:
        """Round-4 F4: a turn boundary proved a turn ended, never that a
        worker joined - the probe ended an ordinary turn with nothing
        recovered and the gate judged the next claim anyway. Recovery is a
        positive observation now: the PostToolUse hook writes
        `role_recovered` when a later call naming the same target and tool
        succeeds, and only that lifts the refusal."""
        self.make_loop()
        # The failure is recorded by the real failure hook, so role and tool
        # are derived exactly as the recovery hook will derive them.
        failed = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_tool_failure.py")],
            input=json.dumps({"session_id": "session-aaa",
                "hook_event_name": "PostToolUseFailure", "cwd": str(self.cwd),
                "tool_name": "agent-delegate",
                "tool_input": {"command": "agent-delegate run --to x --task review"},
                "tool_response": "exit 1",
            }),
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(0, failed.returncode, failed.stderr)
        self.assertEqual("role_unavailable", self.events()[-1]["event"])
        self.claim()
        first = json.loads(subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=60,
        ).stdout)
        # An ordinary turn passes with NO recovery observation at all.
        subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=60,
        )
        self.claim()
        second = json.loads(subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=60,
        ).stdout)
        self.assertIsNone(self.decision(first))
        self.assertIsNone(self.decision(second))
        self.assertEqual(["x"], self.events()[-1]["unrecovered_targets"])
        self.assertFalse(any(e["event"] == "role_recovered" for e in self.events()))
        # The positive observation: a successful call naming the same target.
        recovered = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_tool_success.py")],
            input=json.dumps({"session_id": "session-aaa",
                "hook_event_name": "PostToolUse", "cwd": str(self.cwd),
                "tool_name": "agent-delegate",
                "tool_input": {"command": "agent-delegate run --to x --task review"},
                "tool_response": "ok",
            }),
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(0, recovered.returncode, recovered.stderr)
        self.assertEqual("role_recovered", self.events()[-1]["event"])
        self.claim()
        third = json.loads(subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=60,
        ).stdout)
        self.assertIn("passed on attempt", third["systemMessage"])

    def test_the_ceiling_now_bounds_completion_attempts(self) -> None:
        self.make_loop()
        log = self.cwd / ".goals" / "demo.events.jsonl"
        log.write_text("".join(
            json.dumps({"event": "anchor_checked", "turn": n, "outcome": "red",
                        "signature": f"red:1:sig{n}"}) + "\n"
            for n in range(1, 5)
        ), encoding="utf-8")
        self.claim()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=60,
        )
        payload = json.loads(result.stdout)
        self.assertIsNone(self.decision(payload), "the ceiling must never deny")
        self.assertIn("4 completion attempts", payload["systemMessage"])
        self.assertEqual("ceiling_reached", self.events()[-1]["event"])

    def test_refused_candidates_consume_the_owner_ceiling(self) -> None:
        """Round-4 F5: attempt number counted only `anchor_checked`, so a
        candidate refused for an unrecovered worker cost nothing - three
        explicit candidates under `ceiling: 1` were all called attempt 1.
        Every consumed candidate is an attempt now, whatever refused it."""
        self.make_loop(goal=GOAL.replace(
            "Stop when `true` succeeds, or after 4 turns.",
            "Stop when `true` succeeds.\n\nceiling: 1",
        ))
        # A missing evaluator baseline refuses verification even if the
        # anchor would pass. This is an acceptance failure, not transport.
        (self.cwd / ".goals" / "demo.verification.baseline").unlink()
        # An unrecovered delegation failure: the refusal path that used to
        # cost no attempt at all.
        failed = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_tool_failure.py")],
            input=json.dumps({"session_id": "session-aaa",
                "hook_event_name": "PostToolUseFailure", "cwd": str(self.cwd),
                "tool_name": "agent-delegate",
                "tool_input": {"command": "agent-delegate run --to x --task review"},
                "tool_response": "exit 1",
            }),
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(0, failed.returncode, failed.stderr)
        self.claim()
        first = json.loads(subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({
                "hook_event_name": "Stop", "cwd": str(self.cwd),
                "session_id": "session-aaa",
            }),
            capture_output=True, text=True, timeout=60,
        ).stdout)
        self.assertEqual("block", self.decision(first))
        self.claim()
        second = json.loads(subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({
                "hook_event_name": "Stop", "cwd": str(self.cwd),
                "session_id": "session-aaa",
            }),
            capture_output=True, text=True, timeout=60,
        ).stdout)
        self.assertIsNone(
            self.decision(second), "the owner's ceiling must never deny"
        )
        self.assertIn("ceiling of 1", second["systemMessage"])
        self.assertEqual("ceiling_reached", self.events()[-1]["event"])
        self.assertEqual(2, self.events()[-1]["turn"],
                         "the refused first candidate consumed attempt 1")

    def test_ordinary_turns_do_not_advance_the_ceiling(self) -> None:
        """Only measured attempts count: a run may end any number of host
        turns without claiming, and the owner's ceiling is spent by
        attempts, not by turn-ends."""
        self.make_loop()
        for _ in range(6):
            subprocess.run(
                [sys.executable, str(SCRIPTS / "goal_stop.py")],
                input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
                capture_output=True, text=True, timeout=60,
            )
        self.claim()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=60,
        )
        payload = json.loads(result.stdout)
        self.assertIn("passed on attempt 1", payload["systemMessage"])

    def test_an_identical_signature_is_recorded_not_released(self) -> None:
        """Two identical anchor signatures are not proof of no progress - a
        suite prints the same failing summary until the work lands - so the
        second one is recorded and named in the refusal, and the turn is
        still held."""
        payloads = [self.stop(RED), self.stop(RED)]
        self.assertEqual(["block", "block"], [self.decision(p) for p in payloads])
        self.assertIn("identical", payloads[1]["reason"])
        self.assertNotIn("not progressing", payloads[1]["reason"])

    def test_the_refusal_names_the_attempt_without_authorizing_a_commit(self) -> None:
        payload = self.stop(RED, host="kimi")
        reason = payload["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("at most once", reason)
        self.assertIn("on attempt 1", reason)
        self.assertIn("commit only with existing owner authorization", reason)
        self.assertIn("remains pending", reason)


class AnchorGateTests(Harness):
    """Four outcomes at a completion candidate: green, red, unknown, ceiling.
    Exactly one of them refuses to let the turn end."""

    def stop(self, anchor: str, ceiling: str = "4 turns") -> dict:
        goal = GOAL.replace(f"```\n{GREEN}\n```", f"```\n{anchor}\n```").replace(
            "or after 4 turns", f"or after {ceiling}"
        ).replace("ceiling: 4", f"ceiling: {ceiling.split()[0]}")
        self.make_loop(goal=goal)
        self.claim()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def decision(self, payload: dict) -> str | None:
        """Blocked is blocked, in whichever allowlisted shape the asking host
        reads: the top-level pair on Claude Code, Codex and zCode; the nested
        `permissionDecision: deny` pair on Kimi 0.40.1, whose parser ignores
        the top-level form (round-4 F8). One Stop output is not shared
        across vendors; both shapes mean the same refusal."""
        top = payload.get("decision")
        if top == "block":
            return "block"
        nested = payload.get("hookSpecificOutput", {}).get("permissionDecision")
        return "block" if nested == "deny" else nested

    def events(self) -> list[dict]:
        path = self.cwd / ".goals" / "demo.events.jsonl"
        if not path.is_file():
            return []
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    def test_green_anchor_lets_the_turn_end(self) -> None:
        payload = self.stop(GREEN)
        self.assertIsNone(self.decision(payload))
        # Not "goal met": the gate measured one command exiting 0, and whether
        # that is the goal belongs to `## Stop condition` and `## Acceptance`.
        self.assertIn("passed on attempt", payload["systemMessage"])
        self.assertTrue(self.events()[-1]["verification_passed"])
        self.assertNotIn("Goal met", payload["systemMessage"])
        self.assertEqual("green", self.events()[-1]["outcome"])

    def test_red_anchor_denies_the_stop(self) -> None:
        payload = self.stop(RED)
        self.assertEqual("block", self.decision(payload))
        # The top-level pair only: the nested Stop fields this used to emit
        # made the block inert on Codex 0.150.1 (paired probe,
        # evidence.json), so emitting "both forms" was spending the only
        # hard power in the design to buy nothing.
        self.assertEqual("block", payload["decision"])
        self.assertNotIn("hookSpecificOutput", payload)
        reason = payload["reason"]
        self.assertNotIn("hookSpecificOutput", payload)
        self.assertIn("still failing", reason)
        # The refusal must also say what to do next: the reason is the only
        # channel a deny has, so the obligation rides it.
        self.assertIn("### Lessons", reason)
        self.assertIn("## Verification", reason)
        self.assertEqual("red", self.events()[-1]["outcome"])

    def test_a_missing_command_is_unknown_not_failed(self) -> None:
        """A broken anchor is not a failing one, on any platform.

        Checked by resolving the executable rather than reading an exit code:
        shells disagree about what "not found" returns, and that disagreement
        is how this outcome went missing on Windows.
        """
        payload = self.stop("this-command-does-not-exist-42 --run")
        self.assertIsNone(self.decision(payload), "unknown must never deny")
        self.assertIn("unknown - not failed", payload["systemMessage"])
        self.assertEqual("unknown", self.events()[-1]["outcome"])

    def test_resolvability_is_decided_by_looking(self) -> None:
        import importlib
        gate = importlib.import_module("goal_stop")
        root = Path(self.cwd)
        self.assertTrue(gate._resolvable(f'"{sys.executable}" -c "pass"', root))
        self.assertTrue(gate._resolvable(sys.executable, root))
        self.assertFalse(gate._resolvable("this-command-does-not-exist-42", root))
        self.assertFalse(gate._resolvable("   ", root))
        # Unparseable quoting must not be judged - hand it to the shell.
        self.assertTrue(gate._resolvable('unbalanced "quote', root))

    def test_a_relative_anchor_resolves_against_the_project_not_the_cwd(self) -> None:
        """`.venv/bin/python` is the commonest anchor there is, and it used to be
        looked for wherever the host spawned the hook - while the anchor itself
        runs with `cwd=root`. Those two disagreeing makes every turn `unknown`
        and the gate silently inert. Found on a real artifact.
        """
        import importlib
        gate = importlib.import_module("goal_stop")
        root = Path(self.cwd)
        venv = root / ".venv" / "bin"
        venv.mkdir(parents=True, exist_ok=True)
        exe = venv / "python"
        exe.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        exe.chmod(0o755)

        cwd = os.getcwd()
        os.chdir(tempfile.gettempdir())
        try:
            self.assertTrue(gate._resolvable(".venv/bin/python -m pkg", root))
        finally:
            os.chdir(cwd)

    def test_an_unresolvable_anchor_is_never_executed(self) -> None:
        """Cheaper and safer: nothing runs when the executable is absent."""
        payload = self.stop("this-command-does-not-exist-42 && rm -rf /")
        self.assertIsNone(self.decision(payload))
        self.assertEqual("unknown:unresolvable:", self.events()[-1]["signature"])

    def test_a_goal_with_no_runnable_anchor_lets_the_turn_end(self) -> None:
        goal = GOAL.replace(f"```\n{GREEN}\n```", "it should feel right")
        self.make_loop(goal=goal)
        self.claim()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=30,
        )
        payload = json.loads(result.stdout)
        self.assertIsNone(self.decision(payload))
        self.assertIn("no runnable anchor", payload["systemMessage"])

    def test_the_ceiling_wins_even_when_unmet(self) -> None:
        self.make_loop()
        log = self.cwd / ".goals" / "demo.events.jsonl"
        log.write_text("".join(
            json.dumps({"event": "anchor_checked", "turn": n, "outcome": "red",
                        "signature": f"red:1:sig{n}"}) + "\n"
            for n in range(1, 5)
        ), encoding="utf-8")
        self.claim()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=30,
        )
        payload = json.loads(result.stdout)
        self.assertIsNone(self.decision(payload), "the ceiling must never deny")
        self.assertIn("4 completion attempts", payload["systemMessage"])
        self.assertEqual("ceiling_reached", self.events()[-1]["event"])

    def test_an_identical_result_twice_is_recorded_not_released(self) -> None:
        """The contract changed: two identical signatures used to release
        the turn as "not progressing", but identical failure output does not
        prove no progress - a suite prints the same failing summary until
        the work lands - and releasing on the second one cuts off
        investigation and long fixes. It is recorded and named in the
        refusal instead; the bounds that release are the ceiling and the
        denial budget."""
        first = self.stop(RED)
        self.assertEqual("block", self.decision(first))
        self.claim()
        second = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=30,
        )
        payload = json.loads(second.stdout)
        self.assertEqual("block", self.decision(payload))
        self.assertIn("byte-identical", payload["reason"])

    def test_the_gate_runs_nothing_when_no_loop_is_active(self) -> None:
        witness = self.cwd / "anchor-ran"
        goals = self.cwd / ".goals"
        goals.mkdir()
        (goals / "demo.goal.md").write_text(
            GOAL.replace(
                f"```\n{GREEN}\n```",
                f'```\n"{sys.executable}" -c "open(r\'{witness}\', \'w\').close()"\n```',
            ),
            encoding="utf-8",
        )
        # no `active` marker
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stdout.strip())
        self.assertFalse(witness.exists(), "an inactive project must run no anchor")

    def test_escape_hatch_removing_the_marker_disarms_the_gate(self) -> None:
        self.make_loop(goal=GOAL.replace(f"```\n{GREEN}\n```", f"```\n{RED}\n```"))
        (self.cwd / ".goals" / "active").unlink()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual("", result.stdout.strip(), "rm .goals/active must disarm it")


class RecoveryHookTests(Harness):
    def test_session_start_injects_spec_and_carried_state(self) -> None:
        self.make_loop()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_session_start.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "SessionStart", "cwd": str(self.cwd),
                              "source": "resume"}),
            capture_output=True, text=True, timeout=30,
        )
        payload = json.loads(result.stdout)
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("An active goal is running", context)
        self.assertIn("frozen for the duration of the run", context)
        self.assertIn("## Carry-over", context)

    def test_session_start_ignores_unrelated_sources(self) -> None:
        self.make_loop()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_session_start.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "SessionStart", "cwd": str(self.cwd),
                              "source": "something-else"}),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual("", result.stdout.strip())

    def test_pre_compact_records_the_carried_state(self) -> None:
        self.make_loop()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_pre_compact.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "PreCompact", "cwd": str(self.cwd),
                              "trigger": "auto"}),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        log = self.cwd / ".goals" / "demo.events.jsonl"
        entry = json.loads(log.read_text().splitlines()[-1])
        self.assertEqual("pre_compact", entry["event"])
        self.assertEqual("auto", entry["trigger"])
        self.assertEqual(1, entry["state_items"])
        self.assertEqual(1, entry["lessons"])
        self.assertIn("carry_over_digest", entry)


class FrozenSpecTests(Harness):
    """The gate remembers which goal it was pointed at.

    This is the one zero-trust control that is genuinely mechanical: the
    quantity measured (a digest of three sections) is the quantity judged (did
    the goal move). It allows rather than denies, because a run against an
    edited spec should end and go back to the owner, not try harder.
    """

    def stop(self, claim: bool = True) -> dict:
        if claim:
            self.claim()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def events(self) -> list[dict]:
        path = self.cwd / ".goals" / "demo.events.jsonl"
        if not path.is_file():
            return []
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    def edit(self, old: str, new: str) -> None:
        path = self.cwd / ".goals" / "demo.goal.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def test_the_first_turn_records_the_frozen_digest(self) -> None:
        self.make_loop()
        self.stop()
        self.assertTrue(self.events()[-1]["spec_digest"])

    def test_a_fluid_edit_is_not_a_moved_goalpost(self) -> None:
        self.make_loop()
        self.stop()
        self.edit("- nothing yet", "- one shard left")
        payload = self.stop()
        # Not "goal met": the gate measured one command exiting 0, and whether
        # that is the goal belongs to `## Stop condition` and `## Acceptance`.
        self.assertIn("passed on attempt", payload["systemMessage"])
        self.assertTrue(self.events()[-1]["verification_passed"])
        self.assertNotIn("Goal met", payload["systemMessage"])
        self.assertEqual("anchor_checked", self.events()[-1]["event"])

    def test_editing_the_intent_ends_the_turn_with_an_alarm(self) -> None:
        self.make_loop()
        self.stop()
        self.edit("Keep the suite green.", "Keep the suite roughly green when easy.")
        payload = self.stop()
        self.assertIsNone(
            payload.get("hookSpecificOutput", {}).get("permissionDecision"),
            "a moved goalpost must end the turn, not force more work against it",
        )
        self.assertIn("no longer the goal the owner authorized", payload["systemMessage"])
        entry = self.events()[-1]
        self.assertEqual("frozen_spec_changed", entry["event"])
        self.assertNotEqual(entry["spec_digest_armed"], entry["spec_digest_now"])

    def test_editing_the_anchor_is_also_a_moved_goalpost(self) -> None:
        self.make_loop()
        self.stop()
        self.edit("Stop when `true` succeeds", "Stop when `true` basically succeeds")
        self.assertEqual("anchor_checked", self.events()[-1]["event"],
                         "the stop condition is Firm, not Frozen")
        self.edit(f"```\n{GREEN}\n```", '```\ntrue # relaxed\n```')
        self.stop()
        self.assertEqual("frozen_spec_changed", self.events()[-1]["event"])

    def test_a_moved_goalpost_closes_the_run(self) -> None:
        """Re-baseline semantics, chosen and stated: a legitimate goal change
        ends the old run - the gate disarms itself, because a gate that can
        no longer speak for the goal it was armed for has exactly one honest
        state left. There is no mid-run re-baseline: the owner reopens the
        interview, and a new run starts against a new spec with a fresh
        event log and baseline (goal-run's documented fresh start). An
        unauthorized edit gets the same ending - visibility, not
        impossibility, is the property this design claims."""
        self.make_loop()
        self.stop()
        self.edit("Keep the suite green.", "Keep it vaguely green.")
        payload = self.stop()
        self.assertIn("no longer the goal the owner authorized", payload["systemMessage"])
        self.assertFalse(
            (self.cwd / ".goals" / "active").exists(),
            "the run is closed: the marker must not outlive the goal it named",
        )
        third = self.stop(claim=False)
        self.assertEqual({}, third, "a closed run gates nothing further")

    def test_a_stale_candidate_dies_with_the_run(self) -> None:
        """A candidate written before the spec moved must not survive into a
        re-armed run to be judged against a spec it was never claimed
        under."""
        self.make_loop()
        self.stop()
        self.claim()
        self.edit("Keep the suite green.", "Keep it vaguely green.")
        self.stop(claim=False)
        self.assertFalse((self.cwd / ".goals" / "demo.candidate").exists())

    def test_the_old_observations_survive_the_closing(self) -> None:
        """Closing the run is not deleting its history: the event log stays
        for --audit and git, which is what makes an unauthorized spec change
        visible after the fact."""
        self.make_loop()
        self.stop()
        self.edit("Keep the suite green.", "Keep it vaguely green.")
        self.stop(claim=False)
        kinds = [e["event"] for e in self.events()]
        self.assertIn("anchor_checked", kinds)
        self.assertIn("frozen_spec_changed", kinds)

    def test_the_anchor_does_not_run_once_the_spec_has_moved(self) -> None:
        witness = self.cwd / "anchor-ran"
        command = f'"{sys.executable}" -c "open(r\'{witness}\', \'a\').close()"'
        self.make_loop(goal=GOAL.replace(f"```\n{GREEN}\n```", f"```\n{command}\n```"))
        self.stop()
        self.assertTrue(witness.exists())
        witness.unlink()
        self.edit("Keep the suite green.", "Keep it vaguely green.")
        self.stop()
        self.assertFalse(
            witness.exists(),
            "running the anchor after the spec moved would prove the wrong thing",
        )


class CeilingParsingTests(Harness):
    """An unparsed ceiling is unknown, not twelve.

    The original regex accepted only `<digits> turn(s)`, so "six turns",
    "6 iterations" and "6-turn ceiling" all missed - and a miss silently
    enforced DEFAULT_CEILING instead of the owner's number, which is a moved
    threshold wearing the owner's own handwriting.
    """

    def gate(self):
        import importlib
        return importlib.import_module("goal_stop")

    def test_the_phrasings_an_owner_actually_writes(self) -> None:
        ceiling = self.gate()._ceiling
        for text, expected in (
            ("Stop when the audit is clean, or after 6 turns.", 6),
            ("Stop when the audit is clean, or after six turns.", 6),
            ("stop after 6 iterations", 6),
            ("a 6-turn ceiling", 6),
            ("at most twelve passes", 12),
            ("three cycles", 3),
        ):
            with self.subTest(text=text):
                turns, declared = ceiling(text)
                self.assertEqual(expected, turns)
                self.assertTrue(declared, "this is the owner's number, not a default")

    def test_plural_pass_is_reachable(self) -> None:
        """`pass` pluralises to `passes`, which `s?` cannot match.

        This near-miss hid during development because the fallback happened to
        equal the right answer, so the count looked correct while the flag was
        wrong. The flag is what the assertion has to check.
        """
        turns, declared = self.gate()._ceiling("at most twelve passes")
        self.assertEqual(12, turns)
        self.assertTrue(declared)

    def test_an_unreadable_ceiling_is_flagged_not_assumed(self) -> None:
        for text in ("when it feels done", "", "stop when you are happy"):
            with self.subTest(text=text):
                turns, declared = self.gate()._ceiling(text)
                self.assertEqual(self.gate().DEFAULT_CEILING, turns)
                self.assertFalse(declared)

    def test_the_gate_says_when_the_ceiling_is_its_own(self) -> None:
        goal = GOAL.replace("or after 4 turns", "when it feels done").replace("ceiling: 4", "")
        self.make_loop(goal=goal.replace(f"```\n{GREEN}\n```", f"```\n{RED}\n```"))
        log = self.cwd / ".goals" / "demo.events.jsonl"
        log.write_text("".join(
            json.dumps({"event": "anchor_checked", "turn": n, "outcome": "red",
                        "signature": f"red:1:sig{n}"}) + "\n"
            for n in range(1, 13)
        ), encoding="utf-8")
        self.claim()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=30,
        )
        payload = json.loads(result.stdout)
        self.assertIn("this gate's default, not yours", payload["systemMessage"])
        entry = json.loads(log.read_text().splitlines()[-1])
        self.assertEqual("default", entry["ceiling_source"])


class InjectionBudgetTests(Harness):
    """A section cut in half is worse than an absent one.

    Measured, not imagined: injecting the whole artifact truncated the shipped
    template mid-clause at the default limit, on the first run.
    """

    def context(self, goal: str = GOAL) -> str:
        self.make_loop(goal=goal)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_session_start.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "SessionStart", "cwd": str(self.cwd),
                              "source": "resume"}),
            capture_output=True, text=True, timeout=30,
        )
        return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_recovery_gets_the_frozen_terms_and_the_carried_state(self) -> None:
        context = self.context()
        for probe in ("## Intent", "## Boundary", "## Anchor", "## Carry-over"):
            self.assertIn(probe, context)

    def test_handoff_is_not_injected(self) -> None:
        """It holds the command that starts the run, and the run has started."""
        self.assertNotIn("## Handoff", self.context())

    def test_a_section_is_dropped_whole_and_named(self) -> None:
        import goal_session_start as ss
        padded = GOAL.replace(
            "A fresh agent re-runs the anchor.",
            "A fresh agent re-runs the anchor. " + ("padding " * 1800),
        )
        context = self.context(padded)
        self.assertIn("Not injected for space:", context)
        self.assertIn("verification", context)
        # Whole sections only: no half-instruction may survive.
        self.assertNotIn("padding padding", context)
        self.assertLessEqual(len(context), ss.CONTEXT_LIMIT)

    def test_the_frozen_terms_outrank_everything_else(self) -> None:
        padded = GOAL.replace("Started by hand.", "Started by hand. " + ("x " * 3000))
        context = self.context(padded)
        self.assertIn("Keep the suite green.", context)
        self.assertIn("## Boundary", context)

    def test_the_injection_tells_the_run_it_is_the_run(self) -> None:
        self.assertIn("You are the run, not its designer", self.context())

    def test_every_goal_section_is_either_injected_or_deliberately_skipped(self) -> None:
        """Adding a section must not silently bypass recovery.

        `## Acceptance` was added to the template and left out of INJECT_ORDER,
        so a resuming session could not see what was left - the one thing that
        section exists to answer. This test is the reason that cannot recur:
        every `##` heading the shipped template carries has to be named in
        INJECT_ORDER or in SKIP, on purpose, one or the other.
        """
        import goal_session_start as ss

        template = (
            SCRIPTS.parent / "assets" / "goal-package.md"
        ).read_text(encoding="utf-8")
        headings = [
            line[3:].strip().lower()
            for line in template.splitlines()
            if line.startswith("## ")
        ]
        accounted = set(ss.INJECT_ORDER) | set(ss.SKIP)
        unaccounted = [h for h in headings if h not in accounted]
        self.assertEqual(
            [], unaccounted,
            "name these in INJECT_ORDER or SKIP: a section in neither is invisible "
            "to a resuming session",
        )

    def test_the_essential_sections_are_ordered_ahead_of_the_rest(self) -> None:
        """Order is not cosmetic: a section that does not fit is dropped whole.

        Adding `## Roles` (2.1k) pushed `## Carry-over` off the end of the old
        order, so a resuming session was handed `## Verification` instead of
        the state and lessons this hook exists to restore.
        """
        import goal_session_start as ss

        for name in ss.ESSENTIAL:
            self.assertIn(name, ss.INJECT_ORDER, name)
        essential_positions = [ss.INJECT_ORDER.index(n) for n in ss.ESSENTIAL]
        optional = [
            ss.INJECT_ORDER.index(n)
            for n in ("verification", "cadence")
        ]
        self.assertLess(
            max(essential_positions), min(optional),
            "an essential section must never queue behind an optional one",
        )

    def test_the_shipped_artifact_delivers_everything_a_resume_needs(self) -> None:
        """The contract is not "nothing drops" - it is "nothing needed drops".

        An earlier version of this test asserted the shipped template never
        needed truncating, and the artifact outgrew it twice. That was the test
        encoding a nice property as a requirement. What actually matters: the
        essentials arrive whole, anything dropped is named, and the first thing
        to go is the section a resuming run needs least.
        """
        import goal_session_start as ss

        spec = (SCRIPTS.parent / "assets" / "goal-package.md").read_text(
            encoding="utf-8"
        )
        context = self.context(spec)
        self.assertLessEqual(len(context), ss.CONTEXT_LIMIT)
        # No essential section may be lost, silently or otherwise.
        self.assertNotIn("Could not inject", context)
        for probe in ("### Lessons", "### Next", "fallback:", "- [ ]"):
            self.assertIn(probe, context, probe)
        # A drop is allowed, provided it is named and it is the cheapest one:
        # `## Cadence` says how often the goal gets started, and the run
        # reading this has already started.
        dropped = [l for l in context.splitlines() if "Not injected for space" in l]
        if dropped:
            self.assertEqual(1, len(dropped))
            for essential in ss.ESSENTIAL:
                self.assertNotIn(essential, dropped[0], essential)

    def test_an_essential_section_is_never_dropped_for_space(self) -> None:
        """The contract changed after the first real artifact. `## Carry-over`
        was refused for being 300 characters too large and `## Acceptance`, which
        is not essential, then fit into the space it had vacated. So the frozen
        terms are no longer budgeted at all: they are injected, the overrun is
        announced, and only optional sections compete.
        """
        bloated = GOAL.replace(
            "- nothing yet\n\n### Lessons",
            "- nothing yet\n" + "\n".join(f"- filler {i}" for i in range(1200))
            + "\n\n### Lessons",
        )
        context = self.context(bloated)
        for essential in ("## Intent", "## Boundary", "## Anchor", "## Carry-Over"):
            with self.subTest(section=essential):
                self.assertIn(essential, context)
        self.assertIn("filler 699", context)
        self.assertIn("The frozen terms alone are", context)
        self.assertIn("Nothing optional was injected at all", context)

    def test_a_non_essential_cannot_take_an_essential_section_place(self) -> None:
        """The exact shape of the live failure: something small and optional
        sitting late in the order must not fit where an essential could not."""
        import goal_session_start as ss

        bloated = GOAL.replace(
            "## Boundary", "## Boundary\n\n" + ("padding. " * 1400), 1
        )
        context = self.context(bloated)
        self.assertIn("## Carry-Over", context)
        essential_end = context.index("## Carry-Over")
        for optional in ("## Acceptance", "## Verification", "## Cadence"):
            if optional in context:
                self.assertGreater(context.index(optional), essential_end)

    def test_acceptance_reaches_a_resuming_session(self) -> None:
        goal = GOAL.replace(
            "## Carry-over",
            "## Acceptance\n\n- [x] one done\n- [ ] two left\n\n## Carry-over",
        )
        context = self.context(goal)
        self.assertIn("## Acceptance", context)
        self.assertIn("- [ ] two left", context)


class AmbiguousAnchorTests(Harness):
    """Found by a real run, not by reasoning about it.

    An anchor written as `run` then `verify` on two lines ran only `run`, so
    the assertion that checked the product never executed and the gate went
    green on a proposition nothing had tested. Worse case reproduced while
    fixing it: a ```bash block starting with `set -e` ran `set -e`, exit 0,
    green, nothing tested at all.

    Both automatic repairs are worse than refusing. Running the whole block
    hands the verdict to the last line, so a failing `run` followed by a
    passing `verify` is green. Joining with `&&` rewrites the author's
    intent silently.
    """

    def gate(self):
        import importlib
        return importlib.import_module("goal_stop")

    def test_one_command_per_fence_is_accepted(self) -> None:
        first = self.gate()._first_command
        for body, expected in (
            ("```\npython -m x run\n```", "python -m x run"),
            ("```\na && b\n```", "a && b"),
            ("```bash\npytest -q\n```", "pytest -q"),
            ("the anchor is `pytest -q`", "pytest -q"),
        ):
            with self.subTest(body=body):
                command, ambiguous = first(body)
                self.assertEqual(expected, command)
                self.assertIsNone(ambiguous)

    def test_several_commands_are_refused_not_guessed(self) -> None:
        first = self.gate()._first_command
        for body in (
            "```\npython -m x run\npython -m x verify\n```",
            "```bash\nset -e\npytest -q\npython -m x verify\n```",
        ):
            with self.subTest(body=body):
                command, ambiguous = first(body)
                self.assertIsNone(command, "picking one is the defect")
                self.assertIn("no single exit code decides it", ambiguous)

    def test_an_ambiguous_anchor_ends_the_turn_and_runs_nothing(self) -> None:
        witness = self.cwd / "anchor-ran"
        command = f'"{sys.executable}" -c "open(r\'{witness}\', \'a\').close()"'
        goal = GOAL.replace(f"```\n{GREEN}\n```", f"```\n{command}\n{command}\n```")
        self.make_loop(goal=goal)
        self.claim()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=30,
        )
        payload = json.loads(result.stdout)
        self.assertIsNone(
            payload.get("hookSpecificOutput", {}).get("permissionDecision"),
            "an unusable anchor is unknown, so the turn ends rather than being denied",
        )
        self.assertIn("holds 2 commands", payload["systemMessage"])
        self.assertFalse(
            witness.exists(), "running half of an ambiguous anchor proves the wrong thing"
        )


class StopContractTests(Harness):
    """What the host actually reads, pinned against what it prints.

    The gate emitted `hookSpecificOutput.permissionDecision` for its whole life.
    That is the PreToolUse shape; for Stop, Claude Code accepts only
    `hookEventName` and `additionalContext` inside hookSpecificOutput, and
    blocks on the **top-level** `decision`/`reason` pair. So the one hard power
    in this design was wired to a field the host does not read, and 254 tests
    all checked what the script emitted rather than what the host honours.
    """

    def stop(self, anchor: str, goal: str | None = None) -> dict:
        self.make_loop(goal=(goal or GOAL).replace(f"```\n{GREEN}\n```", f"```\n{anchor}\n```"))
        self.claim()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def test_blocking_is_the_top_level_pair_only(self) -> None:
        """The contract changed after the Codex paired probe: emitting both
        forms in one payload made the block inert there, so "satisfying both"
        was spending the only hard power in the design to buy nothing. The
        deny is now exactly `{"decision": "block", "reason"}`."""
        payload = self.stop(RED)
        self.assertEqual("block", payload["decision"])
        self.assertIn("still failing", payload["reason"])
        self.assertNotIn("hookSpecificOutput", payload)

    def test_a_blocked_turn_is_also_told_what_it_owes(self) -> None:
        """The turn most in need of the mutable surface is the one being
        held, and the reason is the only channel a deny has."""
        reason = self.stop(RED)["reason"]
        for probe in ("### Next", "### Lessons"):
            self.assertIn(probe, reason, probe)

    def test_an_ending_turn_gets_no_model_context_at_all(self) -> None:
        """The contract changed: an allow that attaches `additionalContext`
        does not end the turn on Claude Code 2.1.260 (probe
        clean-claude-allow-context), so the reminder toward the model moved
        into the skill's standing instructions and the allow is
        owner-facing only."""
        payload = self.stop(GREEN)
        self.assertEqual({"systemMessage"}, set(payload))
        self.assertIn("passed on attempt", payload["systemMessage"])

    def test_checkboxes_are_claims_and_are_not_quoted_in_completion(self) -> None:
        goal = GOAL.replace("The command proves the fixture outcome.", "Secret acceptance explanation.")
        message = self.stop(GREEN, goal)["systemMessage"]
        self.assertIn("verification contract passed", message)
        self.assertNotIn("Secret acceptance explanation", message)

    def test_the_owner_line_is_the_same_size_whatever_the_artifact(self) -> None:
        small = GOAL
        big = GOAL.replace("The command proves the fixture outcome.", "Long requirement. " * 800)
        a = self.stop(GREEN, small)["systemMessage"]
        b = self.stop(GREEN, big)["systemMessage"]
        self.assertEqual(len(a), len(b))


class StopPayloadContractTests(Harness):
    """What an allow and a deny may carry, pinned to probe evidence.

    Two confirmed defects, both reproduced live (evidence.json,
    2026-09-04-ultra-goal-review):

    - **Allow + `additionalContext` continues the turn** (probe
      `clean-claude-allow-context`, Claude Code 2.1.260, clean settings): a
      Stop that allows while attaching `hookSpecificOutput.additionalContext`
      produced a second Stop callback and the model acting on the injected
      text. So an allow must carry no model context at all - the obligation
      moved into the run's own loop, the skill's standing instructions, where
      important results are made visible by ordinary tool output before the
      Stop and written to durable state before an allow.
    - **The mixed `_deny` payload kills the block on Codex** (paired probe,
      codex-cli 0.150.1): top-level `decision: block` plus nested
      `hookSpecificOutput.permissionDecision` made the block inert, while the
      top-level-only control blocked fine. Codex's reference documents
      top-level `{"decision":"block","reason"}` and exit 2 + stderr for Stop;
      it does not list `permissionDecision` there. The error belongs to the
      event-specific schema, not to the field name - the same field is
      legitimate on other events.
    """

    def stop(self, anchor: str, host: str | None = None) -> dict:
        # A fresh events log per call: subTests share one temp dir, and an
        # anchor that differs across calls would read as a moved goalpost.
        log = self.cwd / ".goals" / "demo.events.jsonl"
        if log.is_file():
            log.unlink()
        self.make_loop(goal=GOAL.replace(f"```\n{GREEN}\n```", f"```\n{anchor}\n```"))
        self.claim()
        argv = [sys.executable, str(SCRIPTS / "goal_stop.py")]
        if host is not None:
            argv += ["--host", host]
        result = subprocess.run(
            argv,
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def kimi_turns(self, count: int) -> list[dict]:
        payloads = []
        for _ in range(count):
            self.claim()
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "goal_stop.py"), "--host", "kimi"],
                input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payloads.append(json.loads(result.stdout))
        return payloads

    def test_every_allow_path_is_silent_toward_the_model(self) -> None:
        for anchor, needle in (
            (GREEN, "passed on attempt"),
            ("this-command-does-not-exist-42 --run", "unknown - not failed"),
            (f"{GREEN}\n{GREEN}", "holds 2 commands"),
        ):
            with self.subTest(path=needle):
                payload = self.stop(anchor)
                self.assertNotIn(
                    "hookSpecificOutput", payload,
                    "an allow that injects context does not end the turn on "
                    "Claude Code 2.1.260 - it says stop while not letting stop",
                )
                self.assertNotIn("additionalContext", json.dumps(payload))
                self.assertIn(needle, payload["systemMessage"])

    def test_the_ceiling_allow_carries_no_model_context(self) -> None:
        self.make_loop()
        log = self.cwd / ".goals" / "demo.events.jsonl"
        log.write_text("".join(
            json.dumps({"event": "anchor_checked", "turn": n, "outcome": "red",
                        "signature": f"red:1:sig{n}"}) + "\n"
            for n in range(1, 5)
        ), encoding="utf-8")
        payload = self.kimi_turns(1)[0]
        self.assertIn("4 completion attempts", payload["systemMessage"])
        self.assertNotIn("hookSpecificOutput", payload)

    def test_the_budget_spent_allow_carries_no_model_context(self) -> None:
        self.make_loop(goal=GOAL.replace(f"```\n{GREEN}\n```", f"```\n{RED}\n```"))
        # Work committed before each stop, so the second release is the
        # spent budget rather than the not-progressing rule.
        subprocess.run(["git", "init", "-q", "."], cwd=str(self.cwd), check=True,
                       capture_output=True)
        for args in (("config", "user.email", "t@e.st"),
                     ("config", "user.name", "t")):
            subprocess.run(["git", *args], cwd=str(self.cwd), check=True,
                           capture_output=True)
        # First Kimi stop: the one block the host allows, in Kimi's own
        # nested shape - the only form its parser blocks on (round-4 F8).
        with open(self.cwd / "src.txt", "a", encoding="utf-8") as handle:
            handle.write("work\n")
        subprocess.run(["git", "add", "-A"], cwd=str(self.cwd), check=True,
                       capture_output=True)
        subprocess.run(["git", "commit", "-qm", "wip"], cwd=str(self.cwd),
                       check=True, capture_output=True)
        denied = self.kimi_turns(1)[0]
        self.assertEqual(
            "deny",
            denied["hookSpecificOutput"]["permissionDecision"],
        )
        # Second stop in a fresh chain: the budget is spent, and the release
        # is an allow - which must carry no model context on any host.
        with open(self.cwd / "src.txt", "a", encoding="utf-8") as handle:
            handle.write("more work\n")
        subprocess.run(["git", "add", "-A"], cwd=str(self.cwd), check=True,
                       capture_output=True)
        subprocess.run(["git", "commit", "-qm", "wip"], cwd=str(self.cwd),
                       check=True, capture_output=True)
        payload = self.kimi_turns(1)[0]
        self.assertNotIn("hookSpecificOutput", payload)
        self.assertIn("denied attempt(s)", payload["systemMessage"])

    def test_a_deny_is_exactly_the_top_level_form(self) -> None:
        payload = self.stop(RED)
        self.assertEqual(
            {"decision", "reason"}, set(payload),
            "the nested Stop fields make the block inert on Codex 0.150.1; "
            "the top-level form is the one the default host reads",
        )
        self.assertEqual("block", payload["decision"])
        self.assertIn("still failing", payload["reason"])

    def test_the_deny_shape_follows_the_asking_host(self) -> None:
        """Round-4 F8: deleting the nested form globally fixed Codex and
        broke Kimi, whose parser (0.40.1 binary) reads only
        `hookSpecificOutput.permissionDecision` and blocks solely on "deny".
        One Stop output cannot be shared across vendors: exactly one
        allowlisted shape per asking host, the reason carrying everything."""
        for host, keys in (
            ("claude", {"decision", "reason"}),
            ("codex", {"decision", "reason"}),
            ("zcode", {"decision", "reason"}),
        ):
            with self.subTest(host=host):
                payload = self.stop(RED, host=host)
                self.assertEqual(keys, set(payload), host)
                self.assertEqual("block", payload["decision"])
                self.assertIn("still failing", payload["reason"])
        kimi = self.stop(RED, host="kimi")
        self.assertEqual({"hookSpecificOutput"}, set(kimi))
        nested = kimi["hookSpecificOutput"]
        self.assertEqual("deny", nested["permissionDecision"])
        self.assertIn("still failing", nested["permissionDecisionReason"])
        self.assertNotIn("decision", kimi, "the top-level pair is inert on Kimi")

    def test_the_obligation_rides_the_deny_reason(self) -> None:
        """The blocked turn is the one that needs the obligation, and a deny
        has exactly one channel - the reason. It names the mutable surface
        and the challenge route without quoting any frozen body."""
        reason = self.stop(RED)["reason"]
        for probe in ("### Lessons", "### Next", "frozen"):
            self.assertIn(probe, reason, probe)
        for frozen in ("## Intent", "## Boundary", "## Anchor"):
            self.assertNotIn(frozen, reason, frozen)


class UnboundedCeilingTests(Harness):
    """A run the owner declared unbounded has no ceiling, not a ceiling of 12.

    Live defect: a real long run whose stop condition said "no ceiling" would
    have been stopped by this gate at turn 13 while reporting "ceiling
    reached" - in the owner's own voice.
    """

    def gate(self):
        import importlib
        return importlib.import_module("goal_stop")

    def test_declared_forms_win_over_prose(self) -> None:
        ceiling = self.gate()._ceiling
        for text, expected in (
            ("ceiling: none", None),
            ("ceiling: unbounded", None),
            ("ceiling: 20", 20),
            ("ceiling: 20\nor after 6 turns", 20),
        ):
            with self.subTest(text=text):
                turns, declared = ceiling(text)
                self.assertEqual(expected, turns)
                self.assertTrue(declared)

    def test_an_unbounded_run_is_never_stopped_for_the_ceiling(self) -> None:
        goal = GOAL.replace("Stop when `true` succeeds, or after 4 turns.",
                            "Stop when the anchor is green.\n\nceiling: none")
        self.make_loop(goal=goal.replace(f"```\n{GREEN}\n```", f"```\n{RED}\n```"))
        log = self.cwd / ".goals" / "demo.events.jsonl"
        log.write_text("".join(
            json.dumps({"event": "anchor_checked", "turn": n, "outcome": "red",
                        "signature": f"red:1:sig{n}"}) + "\n"
            for n in range(1, 40)
        ), encoding="utf-8")
        self.claim()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=30,
        )
        payload = json.loads(result.stdout)
        self.assertNotIn("ceiling", json.dumps(payload).lower())
        # Turn 40 of an unbounded run still gets judged on its anchor.
        self.assertEqual("block", payload.get("decision"))


class ContinuationBudgetTests(Harness):
    """The loop must loop, within each host's own continuation budget.

    Confirmed live: a real run left exactly one `anchor_checked` event and the
    turn ended, because `run_hook` returned 0 the moment `stop_hook_active` was
    true - so the gate gave the run one nudge and `ceiling: 40` was unreachable
    by the gate alone. Every host counts Stop continuations differently, so the
    budget is a per-host fact with a citation, never a constant copied from
    Claude Code:

    - claude: cap 8 consecutive blocks, `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`
      default, read from the running Claude Code 2.1.260 binary.
    - zcode: cap 3 - "After 3 consecutive continuations the run is force-ended"
      (zCode hooks reference, zcode.z.ai/en/docs/hooks).
    - kimi: one per turn - the host triggers a blocking Stop only while
      `!stopHookContinuationUsed` (Kimi 0.40.1 binary, `runStepLoop`), reset in
      `notifyTurnEnded`; its reference documents no cap.
    - codex: no cap documented (learn.chatgpt.com/docs/hooks) and none visible
      in the 0.150.1 binary - `None` means the gate's own ceiling binds.

    The bound is the gate's own - how many attempts in a row it will deny
    within one host turn it can observe - and it is NOT defined as "the
    host's cap minus one": the one cap read precisely (Claude Code 2.1.260)
    counts consecutive no-progress blocks, not blocks per turn, so the host
    facts size the number as a backstop and nothing more. The count is
    scoped by observed boundaries (a turn marker, an allow, or the host's
    documented chain flag), never by the persistent tail of the run log.
    """

    # Each turn appends one line of "work" and commits it, the way a real run
    # does: the anchor's output stays byte-identical every turn (the common
    # case - a suite printing the same failing summary), so these tests prove
    # the loop lives even when only the work tree moves.
    def turn(self, host: str | None = None, anchor: str = RED,
             ceiling: str = "40 turns", work: bool = True,
             stop_hook_active: bool | None = None) -> dict:
        goal = GOAL.replace(f"```\n{GREEN}\n```", f"```\n{anchor}\n```").replace(
            "or after 4 turns", f"or after {ceiling}"
        ).replace("ceiling: 4", f"ceiling: {ceiling.split()[0]}")
        self.make_loop(goal=goal)
        self.claim()
        if not hasattr(self, "_repo"):
            self.run_git("init", "-q", ".")
            self.run_git("config", "user.email", "t@e.st")
            self.run_git("config", "user.name", "t")
            self._repo = True
        if work:
            with open(self.cwd / "src.txt", "a", encoding="utf-8") as handle:
                handle.write("more work\n")
            self.run_git("add", "-A")
            self.run_git("commit", "-qm", "wip")
        payload = {"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}
        if stop_hook_active is not None:
            payload["stop_hook_active"] = stop_hook_active
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py"),
             *(["--host", host] if host else [])],
            input=json.dumps(payload),
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def prompt(self) -> str:
        """One user prompt, the way a user-origin host turn begins.

        On Kimi the UserPromptSubmit hook fires for it. That invocation is an
        observed fact, but round 2 over-claimed it: a user prompt is one origin
        of a host turn, not the turn boundary itself - Kimi also begins turns
        from tasks and system triggers, which submit no prompt at all.
        """
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_prompt_submit.py")],
            input=json.dumps(
                {"session_id": "session-aaa", "hook_event_name": "UserPromptSubmit", "cwd": str(self.cwd)}
            ),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return result.stdout

    def turn_started(self, turn_id: str = "t1",
                     origin_kind: str = "user") -> str:
        """One TurnStarted invocation, the way EVERY Kimi host turn begins.

        Kimi's reference separates "the user sent a message" (UserPromptSubmit)
        from "a new turn began" (TurnStarted, payload turn_id + origin_kind,
        origins user/task/system_trigger), and the 0.40.1 binary fires it from
        startTurn for every new turn - including task- and system-triggered
        ones that no user prompt opens. The stop-hook continuation is not one:
        the block appends its reason inside the running runStepLoop call, whose
        local guard is exactly the one-block-per-turn budget.
        """
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_turn_started.py")],
            input=json.dumps({"session_id": "session-aaa",
                "hook_event_name": "TurnStarted", "cwd": str(self.cwd),
                "turn_id": turn_id, "origin_kind": origin_kind,
            }),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return result.stdout

    def run_git(self, *args: str) -> None:
        subprocess.run(
            ["git", *args], cwd=str(self.cwd), check=True, capture_output=True
        )

    def decision(self, payload: dict) -> str | None:
        top = payload.get("decision")
        if top == "block":
            return "block"
        nested = payload.get("hookSpecificOutput", {}).get("permissionDecision")
        return "block" if nested == "deny" else nested

    def events(self) -> list[dict]:
        path = self.cwd / ".goals" / "demo.events.jsonl"
        if not path.is_file():
            return []
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    def test_the_defect_a_continuation_still_blocks(self) -> None:
        """The repro from the mission: block, then block again.

        Under the old guard the second Stop - the continuation the first block
        bought - exited before the handler ran, so one host turn held at most
        one anchor check and the loop did not loop. The anchor's output is
        byte-identical on both checks, which is the common case; the work tree
        moving is what keeps the turn alive.
        """
        first = self.turn()
        self.assertEqual("block", self.decision(first))
        second = self.turn()
        self.assertEqual(
            "block", self.decision(second),
            "a continuation must be gated, not skipped",
        )
        checks = [e for e in self.events() if e["event"] == "anchor_checked"]
        self.assertEqual(2, len(checks))
        self.assertTrue(checks[0]["blocked"])

    def test_every_host_budget_carries_a_citation(self) -> None:
        facts = lh.HOSTS
        self.assertEqual(7, facts["claude"].continuation_budget)
        self.assertEqual(2, facts["zcode"].continuation_budget)
        self.assertEqual(1, facts["kimi"].continuation_budget)
        self.assertIsNone(facts["codex"].continuation_budget)
        for name, fact in facts.items():
            with self.subTest(host=name):
                self.assertTrue(fact.source.strip(), "a budget without a source is a guess")
        # The chain flag is read only where the host's reference documents
        # the field AND its meaning; a name alone is not semantics, and
        # Kimi's constant camelCase value carries none.
        self.assertEqual(
            {
                "claude": "stop_hook_active",
                "codex": "stop_hook_active",
                "zcode": None,
                "kimi": None,
            },
            {name: fact.chain_flag for name, fact in facts.items()},
        )

    def test_an_unknown_host_gets_the_most_conservative_budget(self) -> None:
        """A host the table has never heard of must not inherit Claude's 8."""
        first = self.turn(host="nowhere")
        self.assertEqual("block", self.decision(first))
        second = self.turn(host="nowhere")
        self.assertIsNone(self.decision(second))
        self.assertIn("denied attempt(s)", second["systemMessage"])

    def test_claude_blocks_seven_of_the_hosts_eight(self) -> None:
        payloads = [self.turn(host="claude") for _ in range(8)]
        self.assertEqual(["block"] * 7, [self.decision(p) for p in payloads[:7]])
        self.assertIsNone(self.decision(payloads[7]))
        spent = [e for e in self.events() if e["event"] == "continuation_budget_spent"]
        self.assertEqual(1, len(spent))
        self.assertEqual(("claude", 7), (spent[0]["host"], spent[0]["budget"]))

    def test_zcode_releases_before_the_hosts_three(self) -> None:
        payloads = [self.turn(host="zcode") for _ in range(3)]
        self.assertEqual(["block", "block"], [self.decision(p) for p in payloads[:2]])
        self.assertIsNone(self.decision(payloads[2]))

    def test_kimi_blocks_at_most_once(self) -> None:
        payloads = [self.turn(host="kimi") for _ in range(2)]
        self.assertEqual("block", self.decision(payloads[0]))
        self.assertIsNone(self.decision(payloads[1]))

    def test_two_fresh_kimi_turns_each_get_their_one_block(self) -> None:
        """Codex round-1 F2: the host resets its Stop guard when a turn ends
        (0.40.1 binary: the guard is a local of runStepLoop, one call per
        turn), so a budget counted from the persistent tail of the run log
        alternates block/allow across fresh turns - every second turn
        inheriting a spent budget it never spent. The scoping fact must be one
        the hook observes: on Kimi every host turn begins with a user prompt,
        and this plugin's registered UserPromptSubmit hook fires for it, so a
        `prompt_submitted` event is a direct observation of a new turn, not an
        inference."""
        self.prompt()
        first = self.turn(host="kimi")
        self.assertEqual("block", self.decision(first))
        self.prompt()
        second = self.turn(host="kimi")
        self.assertEqual(
            "block", self.decision(second),
            "a fresh host turn arrives with a fresh budget",
        )
        self.assertEqual(
            [],
            [e for e in self.events() if e["event"] == "continuation_budget_spent"],
            "neither turn parked: neither spent more than its one block",
        )

    def test_a_non_user_origin_turn_gets_its_own_budget(self) -> None:
        """Codex round-2 F2, the part prompt_submitted could never cover: a
        task- or system-triggered turn submits no prompt, so no
        `prompt_submitted` row exists to reset the streak, and the turn
        inherits the log's tail with its one-block budget already spent. The
        boundary must be the host's own turn event: Kimi's TurnStarted fires
        for every new turn whatever its origin and carries turn_id, so a
        `turn_started` row is the host saying a fresh turn exists."""
        self.make_loop()
        self.turn_started("t1", origin_kind="user")
        first = self.turn(host="kimi")
        self.assertEqual("block", self.decision(first))
        self.turn_started("t2", origin_kind="system_trigger")
        second = self.turn(host="kimi")
        self.assertEqual(
            "block", self.decision(second),
            "a turn no user prompt began still arrives with a fresh budget",
        )
        self.assertEqual(
            [],
            [e for e in self.events() if e["event"] == "continuation_budget_spent"],
            "neither turn parked: each spent exactly its one block",
        )

    def test_turn_identity_scopes_the_streak_within_a_turn(self) -> None:
        """The host's turn_id is not decoration: checks are grouped by the
        turn they belong to, so a second check in the SAME turn still parks
        (Kimi honors one block per turn) while the next turn - of any origin -
        starts from zero. Two fresh task-origin turns each blocking once, and
        only the same-turn continuation parking, is the whole contract."""
        self.make_loop()
        self.turn_started("t1", origin_kind="task")
        self.assertEqual("block", self.decision(self.turn(host="kimi")))
        self.turn_started("t2", origin_kind="task")
        self.assertEqual("block", self.decision(self.turn(host="kimi")))
        parked = self.turn(host="kimi")
        self.assertIsNone(
            self.decision(parked),
            "the continuation inside turn t2 parks on the spent budget",
        )
        checks = [e for e in self.events() if e["event"] == "anchor_checked"]
        self.assertEqual(
            ["t1", "t2", "t2"], [c.get("turn_id") for c in checks],
            "each check carries the host turn it happened in",
        )

    def test_the_gate_records_the_host_turn_identity_on_each_check(self) -> None:
        """Codex round-2 F2's closure asked for the host-provided turn
        identity, not just a better reset: the event log must carry which host
        turn each anchor check belongs to, or `--audit` cannot tell a run that
        parked twice in one host turn from one that blocked once in each of
        two."""
        self.make_loop()
        self.turn_started("t9", origin_kind="user")
        self.turn(host="kimi")
        checks = [e for e in self.events() if e["event"] == "anchor_checked"]
        self.assertEqual(1, len(checks))
        self.assertEqual("t9", checks[0].get("turn_id"))
        rows = [e for e in self.events() if e["event"] == "turn_started"]
        self.assertEqual(
            ("t9", "user"), (rows[0].get("turn_id"), rows[0].get("origin_kind"))
        )

    def test_a_stop_reporting_a_fresh_chain_resets_the_streak(self) -> None:
        """Claude Code's and Codex's references document stop_hook_active as
        "whether this turn was already continued by Stop" - an explicit false
        is the host itself saying this Stop begins a fresh chain, so the count
        must not inherit the tail of an interrupted one. Kimi passes the same
        fact as a constant camelCase stopHookActive inside its once-per-turn
        guard, which carries no information, and zCode names the field without
        documenting its semantics - neither is read as a reset."""
        payloads = [self.turn(stop_hook_active=False) for _ in range(8)]
        self.assertEqual(
            ["block"] * 8,
            [self.decision(p) for p in payloads],
            "eight stops that each report a fresh chain each get a fresh budget",
        )

    def test_a_continuation_reported_by_the_host_extends_the_streak(self) -> None:
        """The same field read the other way: true means this Stop is the
        continuation a previous block bought, so the count keeps running -
        which is the mission's own repro, now stated through the host's fact
        instead of an unbroken log tail."""
        payloads = [
            self.turn(stop_hook_active=(i > 0)) for i in range(8)
        ]
        self.assertEqual(["block"] * 7, [self.decision(p) for p in payloads[:7]])
        self.assertIsNone(self.decision(payloads[7]))

    def test_codex_has_no_documented_budget_to_spend(self) -> None:
        payloads = [self.turn(host="codex") for _ in range(6)]
        self.assertEqual(["block"] * 6, [self.decision(p) for p in payloads])
        self.assertEqual(
            [], [e for e in self.events() if e["event"] == "continuation_budget_spent"]
        )

    def test_a_check_that_allowed_resets_the_streak(self) -> None:
        self.turn(anchor=RED)
        self.turn(anchor=GREEN)
        again = self.turn(anchor=RED)
        self.assertEqual("block", self.decision(again))

    def test_budget_spent_reports_unmet_and_required_continuation(self) -> None:
        """Exhaustion is an unmet goal, with an explicit continuation boundary."""
        self.turn(host="kimi")
        payload = self.turn(host="kimi")
        message = payload["systemMessage"]
        self.assertIn("still red", message)
        self.assertIn("on attempt 2", message)
        self.assertIn("goal unmet", message)
        self.assertIn("owner already authorized", message)
        self.assertIn("native continuation driver", message)

    def test_a_budget_spent_turn_is_not_progressing_toward_green(self) -> None:
        """The event is a measurement, and `--audit` surfaces it: a run that
        keeps parking on the host's budget is not advancing even when every
        turn works."""
        self.turn(host="kimi")
        self.turn(host="kimi")
        spent = [e for e in self.events() if e["event"] == "continuation_budget_spent"]
        self.assertEqual("red", spent[0]["outcome"])
        self.assertEqual(2, spent[0]["turn"], "turn 1 blocked; turn 2 is the release")

    def test_a_one_block_host_carries_the_park_instructions_on_the_block(self) -> None:
        """Kimi never invokes the Stop hook again after one block, so the turn
        ends with no second gate message: the park instructions have to travel
        with the only message the run will get."""
        payload = self.turn(host="kimi")
        self.assertEqual("block", self.decision(payload))
        reason = payload["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("at most once", reason)
        self.assertIn("on attempt 1", reason)
        self.assertIn("commit only with existing owner authorization", reason)
        self.assertIn("remains pending", reason)

    def test_identical_output_with_committed_work_keeps_the_turn_alive(self) -> None:
        """The not-progressing rule cannot be allowed to strangle the loop.

        A deterministic anchor prints the same failing summary until it
        suddenly passes, so under the output-only rule the second check
        released the turn and `ceiling: 40` was unreachable again - the 4.1
        defect in a new costume. Progress is now judged on what the anchor can
        see: the anchor's output AND the work tree, both unchanged twice in a
        row is stagnation; either one moving is work.
        """
        verdicts = [self.decision(self.turn()) for _ in range(4)]
        self.assertEqual(["block"] * 4, verdicts)
        checks = [e for e in self.events() if e["event"] == "anchor_checked"]
        self.assertEqual(checks[0]["signature"], checks[3]["signature"])
        self.assertNotEqual(checks[0]["tree_digest"], checks[1]["tree_digest"])

    def test_no_work_moved_releases_only_through_the_bound(self) -> None:
        """The contract changed: an unmoving work tree used to release the
        turn as "not progressing", which punished investigation and long
        fixes whose intermediate states look identical. Now nothing but the
        ceiling and the denial budget releases a red claim, and the repeated
        signature is recorded and named instead."""
        first = self.turn(host="kimi", work=False)
        self.assertEqual("block", self.decision(first))
        payload = self.turn(host="kimi", work=False)
        self.assertIsNone(self.decision(payload))
        self.assertIn("denied attempt(s)", payload["systemMessage"])
        self.assertNotIn("not progressing", payload["systemMessage"])
        checks = [e for e in self.events() if e["event"] == "anchor_checked"]
        self.assertFalse(checks[-1]["blocked"])

    def test_a_mutating_anchor_changes_no_outcome_only_the_record(self) -> None:
        """Codex round-1 F3's residue, under the new contract: the work tree
        no longer gates anything (the not-progressing release is retired), so
        an anchor whose own writes used to masquerade as progress cannot buy
        extra denials either - the tree digest is a recorded measurement of
        the state the attempt ran against, nothing more."""
        mutating_red = (
            f'"{sys.executable}" -c '
            '"open(\'src.txt\',\'a\').write(\'x\'); raise SystemExit(1)"'
        )
        first = self.turn(anchor=mutating_red, work=True)
        second = self.turn(anchor=mutating_red, work=False)
        self.assertEqual(["block", "block"],
                         [self.decision(p) for p in (first, second)])
        checks = [e for e in self.events() if e["event"] == "anchor_checked"]
        self.assertEqual(2, len(checks))
        self.assertTrue(all(c.get("tree_digest") for c in checks))

    def test_edits_inside_an_existing_untracked_file_are_progress(self) -> None:
        """Codex round-1 F3, other direction: `git status --porcelain`
        contributes an untracked path and `git diff HEAD` omits its content,
        so rewriting an already-untracked file was invisible - real work read
        as stagnation. The digest now hashes untracked content (ignored files
        excluded, `.goals` excluded) rather than listing names only."""
        self.turn()
        notes = self.cwd / "notes.md"
        notes.write_text("one", encoding="utf-8")
        second = self.turn(work=False)
        self.assertEqual("block", self.decision(second))
        notes.write_text("two", encoding="utf-8")
        third = self.turn(work=False)
        self.assertEqual(
            "block", self.decision(third),
            "a content edit inside an existing untracked file is work",
        )


class CompactNoticeTests(Harness):
    """A compacted model reads its own summary as memory."""

    def context(self, source: str) -> str:
        self.make_loop()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_session_start.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "SessionStart", "cwd": str(self.cwd),
                              "source": source}),
            capture_output=True, text=True, timeout=30,
        )
        return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_a_compact_resume_is_told_it_lost_its_reasoning(self) -> None:
        context = self.context("compact")
        self.assertIn("**This session was just compacted.**", context)
        self.assertIn("Do not trust a recollection of having", context)

    def test_an_ordinary_resume_is_not(self) -> None:
        self.assertNotIn("just compacted", self.context("resume"))


class PromptSubmitTests(Harness):
    """Kimi's recovery channel: a pointer, not a body.

    Kimi's SessionStart output is fire-and-forget (its reference: only
    PreToolUse, Stop and UserPromptSubmit affect the main flow), so the
    spec injection other hosts get on a session boundary cannot be delivered
    there. The documented alternative is UserPromptSubmit, whose returned
    text is appended to the context - one fixed-size line per prompt.
    """

    def run_script(self, payload: dict) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_prompt_submit.py")],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_an_active_goal_gets_one_plain_line(self) -> None:
        self.make_loop()
        result = self.run_script(
            {"session_id": "session-aaa", "hook_event_name": "UserPromptSubmit", "cwd": str(self.cwd)}
        )
        self.assertEqual(0, result.returncode, result.stderr)
        # Plain text, not JSON: that is what Kimi documents for this event.
        self.assertIn("An active goal is running", result.stdout)
        self.assertIn("demo.goal.md", result.stdout)
        self.assertIn("You are the run, not its designer", result.stdout)
        self.assertEqual(1, len(result.stdout.strip().splitlines()))

    def test_without_a_loop_it_is_silent(self) -> None:
        result = self.run_script(
            {"session_id": "session-aaa", "hook_event_name": "UserPromptSubmit", "cwd": str(self.cwd)}
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stdout.strip())

    def test_the_line_is_the_same_size_whatever_the_artifact(self) -> None:
        """The rule a hook inlines by: only what it alone possesses. This
        hook possesses one fact - that a goal is active - so the payload
        cannot grow with the artifact."""
        self.make_loop()
        first = self.run_script(
            {"session_id": "session-aaa", "hook_event_name": "UserPromptSubmit", "cwd": str(self.cwd)}
        )
        big = GOAL.replace("## Carry-over", "## Acceptance\n\n"
                           + "\n".join(f"- [ ] line {i}" for i in range(80))
                           + "\n\n## Carry-over")
        self.make_loop(goal=big)
        second = self.run_script(
            {"session_id": "session-aaa", "hook_event_name": "UserPromptSubmit", "cwd": str(self.cwd)}
        )
        self.assertEqual(len(first.stdout), len(second.stdout))

    def test_garbage_stdin_exits_zero(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_prompt_submit.py")],
            input="}{ not json",
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_the_prompt_records_the_turn_boundary(self) -> None:
        """The prompt hook writes the fact the continuation budget is scoped
        to: a `prompt_submitted` event is a direct observation that a new host
        turn began (this hook only runs because the host submitted a prompt),
        which is what lets a fresh Kimi turn arrive with a fresh budget
        without inferring that some previous turn ended."""
        self.make_loop()
        self.run_script(
            {"session_id": "session-aaa", "hook_event_name": "UserPromptSubmit", "cwd": str(self.cwd)}
        )
        log = self.cwd / ".goals" / "demo.events.jsonl"
        self.assertTrue(log.is_file(), "the boundary must be recorded, not implied")
        events = [json.loads(l) for l in log.read_text().splitlines() if l.strip()]
        self.assertEqual("prompt_submitted", events[0]["event"])

    def test_the_prompt_carries_the_new_gate_decisions(self) -> None:
        """The recovery line follows the gate's vocabulary: an ordinary stop
        and a refused claim are decisions the next Kimi turn must hear,
        because a Kimi turn that allows has no other channel."""
        self.make_loop()
        # An ordinary stop, then the pointer carries it.
        subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=60,
        )
        result = self.run_script(
            {"session_id": "session-aaa", "hook_event_name": "UserPromptSubmit", "cwd": str(self.cwd)}
        )
        self.assertIn("no completion claim", result.stdout)

        # A refused claim, then the pointer carries that too.
        log = self.cwd / ".goals" / "demo.events.jsonl"
        log.write_text(json.dumps({
            "event": "role_unavailable", "role": "reviewer",
        }) + "\n", encoding="utf-8")
        (self.cwd / ".goals" / "demo.verification.baseline").unlink()
        self.claim()
        subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=60,
        )
        result = self.run_script(
            {"session_id": "session-aaa", "hook_event_name": "UserPromptSubmit", "cwd": str(self.cwd)}
        )
        self.assertIn("refused", result.stdout)
        self.assertIn("baseline", result.stdout)

    def test_a_resume_names_the_last_completion_check_by_attempt(self) -> None:
        self.make_loop()
        self.claim()
        subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=60,
        )
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_session_start.py")],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "SessionStart", "cwd": str(self.cwd),
                              "source": "resume"}),
            capture_output=True, text=True, timeout=60,
        )
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Last completion check: attempt 1", context)

    def test_the_prompt_carries_the_gate_s_last_decision(self) -> None:
        """Claude round-1 F-1: Kimi's Stop has no allow-channel in its
        documented protocol, so green, unknown, ceiling, frozen-spec-changed
        and not-progressing all end a Kimi turn in silence. The two documented
        channels are the block and the next UserPromptSubmit - so this hook
        reads the gate's last decision out of the event log and delivers it
        with the pointer, bounded and fixed-size whatever the artifact."""
        self.make_loop(goal=GOAL.replace(f"```\n{GREEN}\n```", f"```\n{RED}\n```"))
        self.claim()
        stop = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py"), "--host", "kimi"],
            input=json.dumps({"session_id": "session-aaa", "hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(0, stop.returncode, stop.stderr)
        # Kimi's deny is the nested pair - the one shape its parser blocks on.
        self.assertEqual(
            "deny",
            json.loads(stop.stdout)
            .get("hookSpecificOutput", {})
            .get("permissionDecision"),
        )
        result = self.run_script(
            {"session_id": "session-aaa", "hook_event_name": "UserPromptSubmit", "cwd": str(self.cwd)}
        )
        lines = result.stdout.strip().splitlines()
        self.assertEqual(2, len(lines), "pointer plus verdict, nothing else")
        self.assertIn("attempt 1", lines[1])
        self.assertIn("red", lines[1])
        self.assertIn("refused", lines[1])


class UnknownSectionTests(Harness):
    """An artifact may grow a heading INJECT_ORDER has never heard of.

    Found by recommending exactly that: splitting an over-large `## Anchor`
    into `## Anchor` plus `## Check contracts` would have made the new section
    invisible - not injected, and not named among the drops either.
    """

    def start(self, goal: str) -> str:
        self.make_loop(goal=goal)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_session_start.py")],
            input=json.dumps(
                {"session_id": "session-aaa", "hook_event_name": "SessionStart", "source": "resume",
                 "cwd": str(self.cwd)}
            ),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
        return payload.get("hookSpecificOutput", {}).get("additionalContext", "")

    def test_an_unknown_section_is_injected_when_it_fits(self) -> None:
        goal = GOAL + "\n## Check contracts\n\nthe contract nobody planned for\n"
        context = self.start(goal)
        self.assertIn("## Check Contracts", context)
        self.assertIn("the contract nobody planned for", context)

    def test_an_unknown_section_too_large_is_named_not_vanished(self) -> None:
        goal = GOAL + "\n## Check contracts\n\n" + ("x" * 13000) + "\n"
        context = self.start(goal)
        self.assertNotIn("x" * 100, context)
        self.assertIn("Not injected for space", context)
        self.assertIn("check contracts", context)

    def test_the_frozen_terms_still_win_the_budget(self) -> None:
        """Unknown sections go last, so one cannot push out an essential."""
        goal = GOAL + "\n## Check contracts\n\n" + ("x" * 13000) + "\n"
        context = self.start(goal)
        for essential in ("## Intent", "## Anchor", "## Carry-Over"):
            with self.subTest(section=essential):
                self.assertIn(essential, context)
