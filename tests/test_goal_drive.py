"""Execution regressions: native Stop routing, actual waits and stale delivery."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import test_goal_run as fixtures
from test_goal_run import SCRIPTS
from goal_hooks import active_goal
import goal_drive as drive


@unittest.skipUnless(os.name == "posix", "Autonomous execution uses POSIX process and file locks")
class DriverTests(unittest.TestCase):
    setUp = fixtures.ArmingIdentityTests.setUp
    run_action = fixtures.ArmingIdentityTests.run_action

    def arm(self, host="claude"):
        result = self.run_action("arm", "--session-id", "owner-A", "--driver", host)
        self.assertEqual(0, result.returncode, result.stderr)
        return active_goal(self.root)

    def stop(self, host="claude", session="owner-A"):
        result = subprocess.run([sys.executable, str(SCRIPTS / "goal_stop.py"), "--host", host],
                                input=json.dumps(dict(cwd=str(self.root), session_id=session,
                                    hook_event_name="Stop", stop_hook_active=False)),
                                text=True, capture_output=True, check=True)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def test_both_hosts_continue_ordinary_stops_but_not_foreign_sessions(self):
        for host in ("claude", "codex"):
            goal = self.arm(host)
            for _ in range(3):
                self.assertEqual("block", self.stop(host)["decision"])
            self.assertEqual({}, self.stop(host, "foreign"))
            self.assertFalse((self.goals / "demo.candidate").exists())
            self.assertEqual(3, drive.read(goal)["continuations"])
            drive.halt(goal, "paused", "Required user input")
            self.assertNotEqual("block", self.stop(host).get("decision"))
            if host == "claude":
                self.run_action("disarm")
                (self.goals / "demo.driver.json").unlink()

    def test_completion_comes_only_from_the_current_gate(self):
        goal = self.arm()
        # A historical green alone must not stop a newly running driver.
        from goal_hooks import append_event
        append_event(goal, {"event": "anchor_checked", "verification_passed": True})
        self.assertEqual("block", self.stop()["decision"])
        before = len(drive.read_events(goal))
        append_event(goal, {"event": "anchor_checked", "verification_passed": True})
        drive.after_gate(goal, {}, "claude", True, {}, before)
        self.assertEqual("completed", drive.read(goal)["phase"])
        self.assertNotEqual("block", self.stop().get("decision"))
        with self.assertRaises(ValueError):
            drive.resume(goal)
        drive.halt(goal, "paused", "SessionEnd")
        self.assertEqual("completed", drive.read(goal)["phase"])

    def test_interrupted_verification_pauses_until_explicit_resume(self):
        goal = self.arm()
        from goal_hooks import append_event
        append_event(goal, {"event": "verification_started", "verification_id": "lost", "turn": 1})
        self.assertNotEqual("block", self.stop().get("decision"))
        self.assertEqual("paused", drive.read(goal)["phase"])
        self.assertNotEqual("block", self.stop().get("decision"))
        drive.resume(goal)
        self.assertEqual("block", self.stop()["decision"])

    def test_native_interrupt_is_durable_while_delivery_holds_the_lock(self):
        goal = self.arm("codex")
        stale_writer = drive.read(goal)
        with drive.driver_lock(goal):
            result = subprocess.run([sys.executable, str(SCRIPTS / "goal_drive.py"), "interrupt"],
                input=json.dumps(dict(cwd=str(self.root), session_id="owner-A", hook_event_name="Interrupt")),
                text=True, capture_output=True, timeout=1, check=True)
            self.assertEqual("", result.stdout)
            self.assertEqual("paused", drive.read(goal)["phase"])
            drive.save(goal, stale_writer)
        self.assertEqual("paused", drive.read(goal)["phase"])
        drive.resume(goal)
        self.assertEqual("running", drive.read(goal)["phase"])

    def test_real_wait_delivers_once_without_ordinary_stop_loop(self):
        goal = self.arm()
        state = drive.wait_command(goal, [sys.executable, "-c", "import time; time.sleep(.4); print('RESULT_OK')"])
        self.addCleanup(drive.halt, goal, "canceled", "test cleanup")
        self.assertEqual("waiting", state["phase"])
        with self.assertRaises(ValueError):
            drive.resume(goal)
        self.assertNotEqual("block", self.stop().get("decision"))
        event = dict(cwd=str(self.root), session_id="owner-A", hook_event_name="Stop")
        message = drive.wake_hook(event)
        self.assertIn(state["wait"]["id"], message)
        self.assertIsNone(drive.wake_hook(event))
        directory = Path(state["wait"]["directory"])
        self.assertIn("RESULT_OK", (directory / "output.log").read_text())
        self.assertEqual(0, json.loads((directory / "result.json").read_text())["exit_code"])
        self.assertEqual("running", drive.read(goal)["phase"])

    def test_cancel_and_rebind_suppress_stale_results(self):
        goal = self.arm()
        state = drive.wait_command(goal, [sys.executable, "-c", "import time; time.sleep(30)"])
        result = self.run_action("disarm")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("canceled", drive.read(goal)["phase"])
        self.assertIsNone(drive.delivery(goal, state["wait"]["id"]))
        self.assertIsNone(drive.wake_hook(dict(cwd=str(self.root), session_id="owner-A")))
        self.arm()
        self.assertEqual("canceled", drive.read(goal)["phase"], "Rearm must not revive cancellation")
        result = self.run_action("rebind", "--session-id", "owner-B")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIsNone(drive.delivery(goal, state["wait"]["id"]))

    def test_failure_and_timeout_are_results_not_success(self):
        goal = self.arm()
        for argv, timeout, expected in ((["/no/such/ultragoal-command"], None, "launch_failed"),
                 ([sys.executable, "-c", "import time; time.sleep(2)"], .1, "timeout")):
            state = drive.wait_command(goal, argv, timeout)
            message = drive.wake_hook(dict(cwd=str(self.root), session_id="owner-A"))
            self.assertIsNotNone(message)
            result = json.loads((Path(state["wait"]["directory"]) / "result.json").read_text())
            self.assertEqual(expected, result["status"])
            self.assertIsNone(result["exit_code"])
            self.assertEqual("running", drive.read(goal)["phase"])

    def test_codex_delivery_is_once_and_failure_is_visible(self):
        from unittest.mock import patch
        goal = self.arm("codex")
        with patch.object(drive.shutil, "which", return_value="/test/codex"), \
             patch.object(drive.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
            state = drive.wait_command(goal, [sys.executable, "-c", "print('ready')"])
        self.addCleanup(drive.halt, goal, "canceled", "test cleanup")
        directory = Path(state["wait"]["directory"])
        with drive.lock(directory / "wait.lock", shared=True):
            pass
        current = drive.read(goal)
        self.assertEqual("paused", current["phase"], "Worker cannot reach the intentionally absent queue executable")
        self.assertEqual("unknown", current["wait"]["status"])
        with patch.object(drive.subprocess, "run") as enqueue:
            self.assertIsNone(drive.delivery(goal, state["wait"]["id"]))
            enqueue.assert_not_called()


if __name__ == "__main__":
    unittest.main()
