"""Grok's native hook envelope, gate ownership and background result delivery."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import test_goal_run as fixtures
from test_goal_run import SCRIPTS
from goal_hooks import active_goal, read_events
import goal_drive as drive


@unittest.skipUnless(os.name == "posix", "Native background waits use POSIX locks")
class GrokHooks(unittest.TestCase):
    setUp = fixtures.ArmingIdentityTests.setUp
    run_action = fixtures.ArmingIdentityTests.run_action

    def arm(self):
        result = self.run_action("arm", "--session-id", "owner-A", "--driver", "grok")
        self.assertEqual(result.returncode, 0, result.stderr)
        return active_goal(self.root)

    def hook(self, name, session="owner-A", **fields):
        result = subprocess.run([sys.executable, str(SCRIPTS / "grok_hook.py")],
            input=json.dumps(dict(hook_event_name=name, sessionId=session, cwd=str(self.root),
                                  promptId="prompt-A", **fields)), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout else {}

    def test_native_gate_ignores_foreign_and_teardown_and_honors_cancel(self):
        goal = self.arm()
        before = read_events(goal)
        self.assertEqual({}, self.hook("Stop", "foreign", reason="end_turn"))
        self.assertEqual({}, self.hook("Stop", reason="shutdown"))
        self.assertEqual(before, read_events(goal))
        self.assertEqual("block", self.hook("Stop", reason="end_turn", stopHookActive=False)["decision"])
        self.hook("StopCancelled", reason="user_interrupt")
        self.assertEqual("paused", drive.read(goal)["phase"])
        self.assertNotEqual("block", self.hook("Stop", reason="end_turn").get("decision"))

    def test_recovery_uses_a_supported_output_channel_after_compaction(self):
        goal = self.arm()
        self.assertEqual({}, self.hook("SessionStart", source="resume"))
        self.assertEqual({}, self.hook("PostToolUse", "foreign"))
        first = self.hook("PostToolUse", toolName="read_file", toolInput={})["hookSpecificOutput"]
        self.assertEqual("PostToolUse", first["hookEventName"])
        self.assertIn("demo.goal.md", first["additionalContext"])
        self.assertEqual({}, self.hook("PostToolUse", toolName="read_file", toolInput={}))
        self.hook("PreCompact", trigger="manual")
        self.hook("PostCompact", trigger="manual")
        self.assertIn("demo.goal.md", self.hook("PostToolUse")["hookSpecificOutput"]["additionalContext"])
        self.assertIn("pre_compact", [e["event"] for e in read_events(goal)])

    def test_native_background_observer_delivers_once_and_does_not_revive_cancel(self):
        goal = self.arm()
        command = [sys.executable, str(SCRIPTS / "goal_drive.py"), "wait", "demo", "--root", str(self.root),
                   "--session-id", "owner-A", "--", sys.executable, "-c", "print('GROK_WAIT_OK')"]
        result = subprocess.run(command, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("awaited command finished", result.stdout)
        self.assertEqual("delivered", drive.read(goal)["wait"]["status"])
        self.assertIsNone(drive.wake_hook(dict(cwd=str(self.root), session_id="owner-A"), host="grok"))
        state = drive.wait_command(goal, [sys.executable, "-c", "import time; time.sleep(30)"])
        drive.halt(goal, "canceled", "Owner canceled")
        self.assertIsNone(drive.wake_hook(dict(cwd=str(self.root), session_id="owner-A"), host="grok"))
        self.assertEqual("canceled", drive.read(goal)["phase"])
        self.assertEqual("canceled", drive.read(goal)["wait"]["status"])

    def test_gate_parks_before_the_native_eight_continuation_ceiling(self):
        goal = self.arm()
        for _ in range(7):
            self.assertEqual("block", self.hook("Stop", reason="end_turn")["decision"])
        self.assertNotEqual("block", self.hook("Stop", reason="end_turn").get("decision"))
        self.assertEqual("paused", drive.read(goal)["phase"])
        self.assertIn("Grok", drive.read(goal)["reason"])

    def test_turn_handoff_waits_for_matching_stop_and_delivers_once(self):
        goal = self.arm()
        state = drive.wait_command(goal, [], yield_turn="prompt-A")
        directory = Path(state["wait"]["directory"])
        self.assertEqual({}, self.hook("Stop", "foreign", reason="end_turn"))
        self.assertFalse((directory / "result.json").exists())
        self.hook("Stop", reason="end_turn")
        message = drive.wake_hook(dict(cwd=str(self.root), session_id="owner-A"), host="grok")
        self.assertIn("awaited command finished", message)
        self.assertEqual(0, json.loads((directory / "result.json").read_text())["exit_code"])
        self.assertEqual("running", drive.read(goal)["phase"])
        self.assertEqual("delivered", drive.read(goal)["wait"]["status"])
        self.assertIsNone(drive.wake_hook(dict(cwd=str(self.root), session_id="owner-A"), host="grok"))
        self.assertFalse((directory / "turn-end.fifo").exists())


if __name__ == "__main__":
    unittest.main()
