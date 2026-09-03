"""The early exit is the only thing between an installed hook and a project
that never asked for one. It is tested from every angle, and every failure
path must lead to exit 0 with no side effects."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    REPO_ROOT
    / "plugins"
    / "loop-graph-design"
    / "skills"
    / "loop-graph-design"
    / "scripts"
)
sys.path.insert(0, str(SCRIPTS))
import loop_hooks as lh  # noqa: E402


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
true
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

## Handoff

```
/goal Keep the suite green.
```
"""


class Harness(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def make_loop(self, slug: str = "demo", goal: str = GOAL) -> Path:
        loops = self.cwd / ".loops"
        loops.mkdir(exist_ok=True)
        (loops / f"{slug}.goal.md").write_text(goal, encoding="utf-8")
        (loops / "active").write_text(f"{slug}\n", encoding="utf-8")
        return loops

    def snapshot(self) -> set[str]:
        return {
            str(p.relative_to(self.cwd))
            for p in self.cwd.rglob("*")
            if p.is_file()
        }


class ActivationTests(Harness):
    def test_no_loops_directory_is_inactive(self) -> None:
        self.assertIsNone(lh.active_loop(self.cwd))

    def test_loops_directory_without_active_marker_is_inactive(self) -> None:
        (self.cwd / ".loops").mkdir()
        (self.cwd / ".loops" / "x.goal.md").write_text(GOAL, encoding="utf-8")
        self.assertIsNone(lh.active_loop(self.cwd))

    def test_active_marker_pointing_at_a_missing_goal_is_inactive(self) -> None:
        loops = self.cwd / ".loops"
        loops.mkdir()
        (loops / "active").write_text("ghost\n", encoding="utf-8")
        self.assertIsNone(lh.active_loop(self.cwd))

    def test_empty_active_marker_is_inactive(self) -> None:
        loops = self.cwd / ".loops"
        loops.mkdir()
        (loops / "active").write_text("   \n", encoding="utf-8")
        self.assertIsNone(lh.active_loop(self.cwd))

    def test_active_marker_that_is_a_directory_is_inactive(self) -> None:
        (self.cwd / ".loops" / "active").mkdir(parents=True)
        self.assertIsNone(lh.active_loop(self.cwd))

    def test_a_slug_with_a_path_separator_is_refused(self) -> None:
        """The marker names a slug, not a path. Traversal is not a loop."""
        loops = self.cwd / ".loops"
        loops.mkdir()
        (loops / "active").write_text("../../etc/passwd\n", encoding="utf-8")
        self.assertIsNone(lh.active_loop(self.cwd))

    def test_a_real_loop_resolves(self) -> None:
        self.make_loop()
        found = lh.active_loop(self.cwd)
        self.assertIsNotNone(found)
        self.assertEqual("demo", found.slug)
        self.assertTrue(found.goal_path.is_file())
        self.assertEqual(".loops/demo.events.jsonl", str(
            found.events_path.relative_to(self.cwd)))

    def test_activation_check_has_no_side_effects(self) -> None:
        self.make_loop()
        before = self.snapshot()
        lh.active_loop(self.cwd)
        lh.active_loop(self.cwd)
        self.assertEqual(before, self.snapshot())

    def test_inactive_check_writes_nothing(self) -> None:
        before = self.snapshot()
        lh.active_loop(self.cwd)
        self.assertEqual(before, self.snapshot())

    def test_unreadable_cwd_is_inactive_not_an_error(self) -> None:
        self.assertIsNone(lh.active_loop(self.cwd / "does-not-exist"))
        self.assertIsNone(lh.active_loop(None))


class FailOpenTests(Harness):
    def test_a_handler_that_raises_still_exits_zero(self) -> None:
        def boom(event, loop):
            raise RuntimeError("handler blew up")

        self.assertEqual(0, lh.run_hook("Stop", boom, stdin_text="{}"))

    def test_garbage_stdin_exits_zero(self) -> None:
        calls = []
        self.assertEqual(
            0, lh.run_hook("Stop", lambda e, l: calls.append(e), stdin_text="not json")
        )
        self.assertEqual([], calls, "the handler must not run on unparseable input")

    def test_wrong_event_name_exits_zero_without_calling_the_handler(self) -> None:
        calls = []
        payload = json.dumps({"hook_event_name": "PostToolUse", "cwd": str(self.cwd)})
        self.assertEqual(
            0, lh.run_hook("Stop", lambda e, l: calls.append(e), stdin_text=payload)
        )
        self.assertEqual([], calls)

    def test_inactive_project_exits_zero_without_calling_the_handler(self) -> None:
        calls = []
        payload = json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)})
        self.assertEqual(
            0, lh.run_hook("Stop", lambda e, l: calls.append(e), stdin_text=payload)
        )
        self.assertEqual([], calls, "no loop here, so the handler is never reached")

    def test_stop_hook_active_is_a_hard_early_exit(self) -> None:
        """Re-entry guard: without this a denied stop can loop forever."""
        self.make_loop()
        calls = []
        payload = json.dumps(
            {"hook_event_name": "Stop", "cwd": str(self.cwd), "stop_hook_active": True}
        )
        self.assertEqual(
            0, lh.run_hook("Stop", lambda e, l: calls.append(e), stdin_text=payload)
        )
        self.assertEqual([], calls)

    def test_disable_env_var_is_honoured(self) -> None:
        self.make_loop()
        calls = []
        payload = json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)})
        self.assertEqual(
            0,
            lh.run_hook(
                "Stop",
                lambda e, l: calls.append(e),
                stdin_text=payload,
                env={"LOOP_GRAPH_HOOKS_DISABLED": "1"},
            ),
        )
        self.assertEqual([], calls)

    def test_an_active_loop_reaches_the_handler(self) -> None:
        self.make_loop()
        seen = {}
        payload = json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)})

        def handler(event, loop):
            seen["slug"] = loop.slug
            return None

        self.assertEqual(0, lh.run_hook("Stop", handler, stdin_text=payload))
        self.assertEqual("demo", seen.get("slug"))


class ScriptSmokeTests(Harness):
    """Each hook script must be invocable and silent in an unrelated project."""

    SCRIPT_EVENTS = {
        "loop_stop.py": "Stop",
        "loop_session_start.py": "SessionStart",
        "loop_pre_compact.py": "PreCompact",
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
        goal = GOAL.replace("```\ntrue\n```", f"```\n{anchor}\n```").replace(
            "or after 4 turns", f"or after {ceiling}"
        )
        self.make_loop(goal=goal)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "loop_stop.py")],
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def decision(self, payload: dict) -> str | None:
        return payload.get("hookSpecificOutput", {}).get("permissionDecision")

    def events(self) -> list[dict]:
        path = self.cwd / ".loops" / "demo.events.jsonl"
        if not path.is_file():
            return []
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    def test_green_anchor_lets_the_turn_end(self) -> None:
        payload = self.stop("true")
        self.assertIsNone(self.decision(payload))
        self.assertIn("Goal met", payload["systemMessage"])
        self.assertEqual("green", self.events()[-1]["outcome"])

    def test_red_anchor_denies_the_stop(self) -> None:
        payload = self.stop("false")
        self.assertEqual("deny", self.decision(payload))
        reason = payload["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("still failing", reason)
        # The refusal must also say what to do next, since Stop cannot inject context.
        self.assertIn("### Lessons", reason)
        self.assertIn("## Verification", reason)
        self.assertEqual("red", self.events()[-1]["outcome"])

    def test_a_missing_command_is_unknown_not_failed(self) -> None:
        """127 means the anchor is broken, not that the work failed."""
        payload = self.stop("this-command-does-not-exist-42")
        self.assertIsNone(self.decision(payload), "unknown must never deny")
        self.assertIn("unknown - not failed", payload["systemMessage"])
        self.assertEqual("unknown", self.events()[-1]["outcome"])

    def test_a_goal_with_no_runnable_anchor_lets_the_turn_end(self) -> None:
        goal = GOAL.replace("```\ntrue\n```", "it should feel right")
        self.make_loop(goal=goal)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "loop_stop.py")],
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=30,
        )
        payload = json.loads(result.stdout)
        self.assertIsNone(self.decision(payload))
        self.assertIn("no runnable anchor", payload["systemMessage"])

    def test_the_ceiling_wins_even_when_unmet(self) -> None:
        self.make_loop()
        log = self.cwd / ".loops" / "demo.events.jsonl"
        log.write_text("".join(
            json.dumps({"event": "anchor_checked", "turn": n, "outcome": "red",
                        "signature": f"red:1:sig{n}"}) + "\n"
            for n in range(1, 5)
        ), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "loop_stop.py")],
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=30,
        )
        payload = json.loads(result.stdout)
        self.assertIsNone(self.decision(payload), "the ceiling must never deny")
        self.assertIn("ceiling of 4 turns", payload["systemMessage"])
        self.assertEqual("ceiling_reached", self.events()[-1]["event"])

    def test_an_identical_result_twice_stops_the_spin(self) -> None:
        """Denying again would only spin it more, so it lets go and reports."""
        first = self.stop("false")
        self.assertEqual("deny", self.decision(first))
        second = subprocess.run(
            [sys.executable, str(SCRIPTS / "loop_stop.py")],
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=30,
        )
        payload = json.loads(second.stdout)
        self.assertIsNone(self.decision(payload), "no progress must never deny")
        self.assertIn("not progressing", payload["systemMessage"])

    def test_the_gate_runs_nothing_when_no_loop_is_active(self) -> None:
        witness = self.cwd / "anchor-ran"
        loops = self.cwd / ".loops"
        loops.mkdir()
        (loops / "demo.goal.md").write_text(
            GOAL.replace("```\ntrue\n```", f"```\ntouch {witness}\n```"),
            encoding="utf-8",
        )
        # no `active` marker
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "loop_stop.py")],
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stdout.strip())
        self.assertFalse(witness.exists(), "an inactive project must run no anchor")

    def test_escape_hatch_removing_the_marker_disarms_the_gate(self) -> None:
        self.make_loop(goal=GOAL.replace("```\ntrue\n```", "```\nfalse\n```"))
        (self.cwd / ".loops" / "active").unlink()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "loop_stop.py")],
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.cwd)}),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual("", result.stdout.strip(), "rm .loops/active must disarm it")


class RecoveryHookTests(Harness):
    def test_session_start_injects_spec_and_carried_state(self) -> None:
        self.make_loop()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "loop_session_start.py")],
            input=json.dumps({"hook_event_name": "SessionStart", "cwd": str(self.cwd),
                              "source": "resume"}),
            capture_output=True, text=True, timeout=30,
        )
        payload = json.loads(result.stdout)
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("An active loop is running", context)
        self.assertIn("frozen for the duration of the run", context)
        self.assertIn("## Carry-over", context)

    def test_session_start_ignores_unrelated_sources(self) -> None:
        self.make_loop()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "loop_session_start.py")],
            input=json.dumps({"hook_event_name": "SessionStart", "cwd": str(self.cwd),
                              "source": "something-else"}),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual("", result.stdout.strip())

    def test_pre_compact_records_the_carried_state(self) -> None:
        self.make_loop()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "loop_pre_compact.py")],
            input=json.dumps({"hook_event_name": "PreCompact", "cwd": str(self.cwd),
                              "trigger": "auto"}),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        log = self.cwd / ".loops" / "demo.events.jsonl"
        entry = json.loads(log.read_text().splitlines()[-1])
        self.assertEqual("pre_compact", entry["event"])
        self.assertEqual("auto", entry["trigger"])
        self.assertEqual(1, entry["state_items"])
        self.assertEqual(1, entry["lessons"])
        self.assertIn("carry_over_digest", entry)
