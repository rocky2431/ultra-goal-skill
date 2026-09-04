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

## Anchor

```
__ANCHOR__
```

## Verification

A fresh agent re-runs the anchor.

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
        (goals / "active").write_text(f"{slug}\n", encoding="utf-8")
        return goals

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
        payload = json.dumps({"hook_event_name": "PostToolUse", "cwd": str(self.cwd)})
        self.assertEqual(
            0, lh.run_hook("Stop", lambda e, l, h: calls.append(e), stdin_text=payload)
        )
        self.assertEqual([], calls)

    def test_inactive_project_exits_zero_without_calling_the_handler(self) -> None:
        calls = []
        payload = json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)})
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
            {"hook_event_name": "Stop", "cwd": str(self.cwd), "stop_hook_active": True}
        )
        self.assertEqual(
            0, lh.run_hook("Stop", lambda e, l, h: calls.append(e), stdin_text=payload)
        )
        self.assertEqual(1, len(calls), "a continuation is still gated")

    def test_disable_env_var_is_honoured(self) -> None:
        self.make_loop()
        calls = []
        payload = json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)})
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
        payload = json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)})

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
                    name, {"hook_event_name": event, "cwd": str(self.cwd)}
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


if __name__ == "__main__":
    unittest.main()


class AnchorGateTests(Harness):
    """Five outcomes: green, red, unknown, ceiling, not-progressing.
    Exactly one of them refuses to let the turn end."""

    def stop(self, anchor: str, ceiling: str = "4 turns") -> dict:
        goal = GOAL.replace(f"```\n{GREEN}\n```", f"```\n{anchor}\n```").replace(
            "or after 4 turns", f"or after {ceiling}"
        )
        self.make_loop(goal=goal)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def decision(self, payload: dict) -> str | None:
        """Blocked is blocked, whichever documented form the host reads.

        Two authoritative sources disagree: the official hooks reference lists
        `hookSpecificOutput.permissionDecision` for Stop, while the running
        binary's own validator printed a schema with only `additionalContext`
        there and `decision`/`reason` at the top level. The gate emits both, so
        this normalises both to one word rather than betting on either.
        """
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
        self.assertIn("passed on turn", payload["systemMessage"])
        self.assertIn("`## Stop condition`'s question", payload["systemMessage"])
        self.assertNotIn("Goal met", payload["systemMessage"])
        self.assertEqual("green", self.events()[-1]["outcome"])

    def test_red_anchor_denies_the_stop(self) -> None:
        payload = self.stop(RED)
        self.assertEqual("block", self.decision(payload))
        # Both documented forms, because the two sources disagree and picking
        # one costs the only hard power in the design.
        self.assertEqual("block", payload["decision"])
        self.assertEqual(
            "deny", payload["hookSpecificOutput"]["permissionDecision"]
        )
        reason = payload["reason"]
        self.assertEqual(
            reason, payload["hookSpecificOutput"]["permissionDecisionReason"]
        )
        self.assertIn("still failing", reason)
        # The refusal must also say what to do next, since Stop cannot inject context.
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
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)}),
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
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=30,
        )
        payload = json.loads(result.stdout)
        self.assertIsNone(self.decision(payload), "the ceiling must never deny")
        self.assertIn("ceiling of 4 turns", payload["systemMessage"])
        self.assertEqual("ceiling_reached", self.events()[-1]["event"])

    def test_an_identical_result_twice_stops_the_spin(self) -> None:
        """Denying again would only spin it more, so it lets go and reports."""
        first = self.stop(RED)
        self.assertEqual("block", self.decision(first))
        second = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=30,
        )
        payload = json.loads(second.stdout)
        self.assertIsNone(self.decision(payload), "no progress must never deny")
        self.assertIn("not progressing", payload["systemMessage"])

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
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)}),
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
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual("", result.stdout.strip(), "rm .goals/active must disarm it")


class RecoveryHookTests(Harness):
    def test_session_start_injects_spec_and_carried_state(self) -> None:
        self.make_loop()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_session_start.py")],
            input=json.dumps({"hook_event_name": "SessionStart", "cwd": str(self.cwd),
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
            input=json.dumps({"hook_event_name": "SessionStart", "cwd": str(self.cwd),
                              "source": "something-else"}),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual("", result.stdout.strip())

    def test_pre_compact_records_the_carried_state(self) -> None:
        self.make_loop()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_pre_compact.py")],
            input=json.dumps({"hook_event_name": "PreCompact", "cwd": str(self.cwd),
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

    def stop(self) -> dict:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)}),
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
        self.assertIn("passed on turn", payload["systemMessage"])
        self.assertIn("`## Stop condition`'s question", payload["systemMessage"])
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
        self.assertNotEqual(entry["spec_digest_first"], entry["spec_digest_now"])

    def test_editing_the_anchor_is_also_a_moved_goalpost(self) -> None:
        self.make_loop()
        self.stop()
        self.edit("Stop when `true` succeeds", "Stop when `true` basically succeeds")
        self.assertEqual("anchor_checked", self.events()[-1]["event"],
                         "the stop condition is Firm, not Frozen")
        self.edit(f"```\n{GREEN}\n```", '```\ntrue # relaxed\n```')
        self.stop()
        self.assertEqual("frozen_spec_changed", self.events()[-1]["event"])

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
        goal = GOAL.replace("or after 4 turns", "when it feels done")
        self.make_loop(goal=goal.replace(f"```\n{GREEN}\n```", f"```\n{RED}\n```"))
        log = self.cwd / ".goals" / "demo.events.jsonl"
        log.write_text("".join(
            json.dumps({"event": "anchor_checked", "turn": n, "outcome": "red",
                        "signature": f"red:1:sig{n}"}) + "\n"
            for n in range(1, 13)
        ), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)}),
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
            input=json.dumps({"hook_event_name": "SessionStart", "cwd": str(self.cwd),
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
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)}),
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
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def test_blocking_satisfies_both_documented_forms(self) -> None:
        """Emitting both is the answer to two sources disagreeing.

        I changed this once on the strength of one source and broke a field the
        other documents. The cost of satisfying both is a few bytes; the cost of
        picking wrong is the only hard power in the design.
        """
        payload = self.stop(RED)
        self.assertEqual("block", payload["decision"])
        self.assertIn("still failing", payload["reason"])
        nested = payload["hookSpecificOutput"]
        self.assertEqual("Stop", nested["hookEventName"])
        self.assertEqual("deny", nested["permissionDecision"])

    def test_a_blocked_turn_is_also_told_what_it_owes(self) -> None:
        """The turn most in need of the mutable surface is the one being held."""
        context = self.stop(RED)["hookSpecificOutput"]["additionalContext"]
        for probe in ("### Next", "### Lessons"):
            self.assertIn(probe, context, probe)

    def test_an_ending_turn_is_reminded_of_what_it_may_change(self) -> None:
        payload = self.stop(GREEN)
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertEqual("Stop", payload["hookSpecificOutput"]["hookEventName"])
        for probe in ("### Next", "### Lessons", "### State"):
            self.assertIn(probe, context, probe)

    def test_the_reminder_never_carries_a_frozen_section(self) -> None:
        """The owner's rule cuts both ways: a frozen section named in a
        reminder is an invitation to edit it."""
        context = self.stop(GREEN)["hookSpecificOutput"]["additionalContext"]
        for frozen in ("## Intent", "## Boundary", "## Anchor", "## Means"):
            self.assertNotIn(frozen, context, frozen)
        self.assertIn("are frozen", context)

    def test_the_reminder_counts_open_acceptance_lines_without_quoting_them(
        self,
    ) -> None:
        """A hook inlines only what it alone possesses. How many lines are open
        is a measurement; their text is on disk, and the run has to open the
        file to change them anyway. Quoting them cost 4,683 characters a turn on
        the first real artifact.
        """
        goal = GOAL.replace(
            "## Carry-over",
            "## Acceptance\n\n- [x] already true\n- [ ] not yet true\n\n## Carry-over",
        )
        context = self.stop(GREEN, goal)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("1 line(s) still open", context)
        self.assertNotIn("not yet true", context)
        self.assertNotIn("already true", context)
        # And it says where they are.
        self.assertIn("demo.goal.md", context)

    def test_the_reminder_is_the_same_size_whatever_the_artifact(self) -> None:
        """The reason for the rule: an 80-node graph must not make the per-turn
        payload 80 lines long."""
        small = GOAL.replace(
            "## Carry-over", "## Acceptance\n\n- [ ] one\n\n## Carry-over"
        )
        big = GOAL.replace(
            "## Carry-over",
            "## Acceptance\n\n"
            + "\n".join(f"- [ ] line {i}" for i in range(80))
            + "\n\n## Carry-over",
        )
        a = self.stop(GREEN, small)["hookSpecificOutput"]["additionalContext"]
        b = self.stop(GREEN, big)["hookSpecificOutput"]["additionalContext"]
        self.assertLess(abs(len(a) - len(b)), 40)
        self.assertIn("80 line(s) still open", b)


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
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)}),
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

    The gate releases one block BEFORE the cap so the last word is its own
    reason rather than the host's force-end warning. And the count is scoped
    to the host turn, not to the persistent tail of the run log: the host's
    own counter resets when a turn ends, so the boundary has to be observed
    (a prompt marker, an allow, or the host's documented chain flag), never
    inferred.
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
        )
        self.make_loop(goal=goal)
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
        payload = {"hook_event_name": "Stop", "cwd": str(self.cwd)}
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
                {"hook_event_name": "UserPromptSubmit", "cwd": str(self.cwd)}
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
            input=json.dumps({
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
        self.assertIn("continuation budget", second["systemMessage"])

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

    def test_budget_spent_ends_loudly_with_the_commit_turn(self) -> None:
        """A red anchor may end a turn only by saying so, and by naming the
        gate's turn number for the commit subject - one anchor check is one
        turn, so a host turn that held several checks commits under the last
        one the gate reports."""
        self.turn(host="kimi")
        payload = self.turn(host="kimi")
        message = payload["systemMessage"]
        self.assertIn("still red", message)
        self.assertIn("goal(demo) turn 2", message)
        self.assertIn("[anchor: red]", message)

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
        reason = payload["reason"]
        self.assertIn("at most once", reason)
        self.assertIn("goal(demo) turn 1", reason)
        self.assertIn("[anchor: red]", reason)

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

    def test_no_work_moved_releases_as_not_progressing(self) -> None:
        self.turn()
        payload = self.turn(work=False)
        self.assertIsNone(self.decision(payload))
        self.assertIn("not progressing", payload["systemMessage"])
        checks = [e for e in self.events() if e["event"] == "anchor_checked"]
        self.assertFalse(checks[-1]["blocked"])

    def test_a_mutating_anchor_cannot_pose_as_progress(self) -> None:
        """Codex round-1 F3: the comparison base used to be captured before
        the previous anchor ran, so that anchor's own writes landed inside the
        measured window and a red anchor appending to a tracked file kept the
        turn alive forever with no model work at all. The base is now the
        state the previous check *left behind* (captured after its anchor
        ran), so the anchor's footprint is on both sides of the comparison."""
        mutating_red = (
            f'"{sys.executable}" -c '
            '"open(\'src.txt\',\'a\').write(\'x\'); raise SystemExit(1)"'
        )
        first = self.turn(anchor=mutating_red)
        self.assertEqual("block", self.decision(first))
        second = self.turn(anchor=mutating_red, work=False)
        self.assertIsNone(self.decision(second))
        self.assertIn("not progressing", second["systemMessage"])

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
            input=json.dumps({"hook_event_name": "SessionStart", "cwd": str(self.cwd),
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
            {"hook_event_name": "UserPromptSubmit", "cwd": str(self.cwd)}
        )
        self.assertEqual(0, result.returncode, result.stderr)
        # Plain text, not JSON: that is what Kimi documents for this event.
        self.assertIn("An active goal is running", result.stdout)
        self.assertIn("demo.goal.md", result.stdout)
        self.assertIn("You are the run, not its designer", result.stdout)
        self.assertEqual(1, len(result.stdout.strip().splitlines()))

    def test_without_a_loop_it_is_silent(self) -> None:
        result = self.run_script(
            {"hook_event_name": "UserPromptSubmit", "cwd": str(self.cwd)}
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stdout.strip())

    def test_the_line_is_the_same_size_whatever_the_artifact(self) -> None:
        """The rule a hook inlines by: only what it alone possesses. This
        hook possesses one fact - that a goal is active - so the payload
        cannot grow with the artifact."""
        self.make_loop()
        first = self.run_script(
            {"hook_event_name": "UserPromptSubmit", "cwd": str(self.cwd)}
        )
        big = GOAL.replace("## Carry-over", "## Acceptance\n\n"
                           + "\n".join(f"- [ ] line {i}" for i in range(80))
                           + "\n\n## Carry-over")
        self.make_loop(goal=big)
        second = self.run_script(
            {"hook_event_name": "UserPromptSubmit", "cwd": str(self.cwd)}
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
            {"hook_event_name": "UserPromptSubmit", "cwd": str(self.cwd)}
        )
        log = self.cwd / ".goals" / "demo.events.jsonl"
        self.assertTrue(log.is_file(), "the boundary must be recorded, not implied")
        events = [json.loads(l) for l in log.read_text().splitlines() if l.strip()]
        self.assertEqual("prompt_submitted", events[0]["event"])

    def test_the_prompt_carries_the_gate_s_last_decision(self) -> None:
        """Claude round-1 F-1: Kimi's Stop has no allow-channel in its
        documented protocol, so green, unknown, ceiling, frozen-spec-changed
        and not-progressing all end a Kimi turn in silence. The two documented
        channels are the block and the next UserPromptSubmit - so this hook
        reads the gate's last decision out of the event log and delivers it
        with the pointer, bounded and fixed-size whatever the artifact."""
        self.make_loop(goal=GOAL.replace(f"```\n{GREEN}\n```", f"```\n{RED}\n```"))
        stop = subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_stop.py"), "--host", "kimi"],
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(0, stop.returncode, stop.stderr)
        self.assertEqual("block", json.loads(stop.stdout).get("decision"))
        result = self.run_script(
            {"hook_event_name": "UserPromptSubmit", "cwd": str(self.cwd)}
        )
        lines = result.stdout.strip().splitlines()
        self.assertEqual(2, len(lines), "pointer plus verdict, nothing else")
        self.assertIn("turn 1", lines[1])
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
                {"hook_event_name": "SessionStart", "source": "resume",
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
