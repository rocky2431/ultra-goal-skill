"""Recovery after a real verifier crash and after a lost start/settlement write."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

import test_goal_contract as fixture
from test_goal_contract import hooks, run, stop, validator, SCRIPTS
import goal_prompt_submit
import goal_session_start


class VerificationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture.GoalContractTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def attempts(self):
        return hooks.completion_attempts(hooks.read_events(self.case.goal))

    def test_started_and_settled_attempts_share_one_budget_with_legacy_rows(self):
        observations = [
            {"event": "anchor_checked", "turn": 1},
            {"event": "candidate_refused", "turn": 2},
            {"event": "verification_started", "turn": 3, "verification_id": "third"},
            {"event": "anchor_checked", "turn": 3, "verification_id": "third"},
            {"event": "verification_started", "turn": 4, "verification_id": "fourth"},
            {"event": "stop_ordinary"},
        ]
        attempts = hooks.completion_attempts(observations)
        self.assertEqual([1, 2, 3, 4], [entry["turn"] for entry in attempts])
        self.assertEqual("verification_started", attempts[-1]["event"])

    def test_unrecorded_start_preserves_claim_and_never_executes_anchor(self):
        self.case.arm()
        with patch.object(stop, "append_event", return_value=False), patch.object(stop.subprocess, "run") as execute:
            result = run.verify(self.case.root, "demo", "generator-session")
        execute.assert_not_called()
        self.assertFalse(result["verification_passed"])
        self.assertIsNone(result["observation"])
        self.assertFalse(result["fresh_check"])
        self.assertTrue((self.case.goals / "demo.candidate").exists())

    def test_crash_before_consumption_does_not_replay_the_surviving_claim(self):
        self.case.arm()
        candidate = self.case.goals / "demo.candidate"
        unlink = Path.unlink

        def crash(path, *args, **kwargs):
            if path == candidate:
                raise KeyboardInterrupt("process lost before consuming the candidate")
            return unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", crash), self.assertRaises(KeyboardInterrupt):
            run.verify(self.case.root, "demo", "generator-session")
        self.assertTrue(candidate.exists())
        self.assertEqual("unknown", validator.last_verification(self.case.goal.goal_path)["status"])
        with patch.object(stop.subprocess, "run") as execute:
            stop.handle({"session_id": "generator-session"}, self.case.goal, "claude")
        execute.assert_not_called()
        self.assertFalse(candidate.exists())
        self.assertEqual(1, len(self.attempts()))
        self.assertEqual("interrupted", validator.last_verification(self.case.goal.goal_path)["status"])

    def test_interrupted_attempt_still_spends_its_ceiling(self):
        self.case.arm()
        # Isolate the owner-ceiling check; the value is fixed before arming.
        run.disarm(self.case.root, "demo")
        path = self.case.goals / "demo.goal.md"
        spec = path.read_text().replace("ceiling: 6", "ceiling: 1")
        path.write_text(spec)
        self.case.confirm(spec)
        (self.case.goals / "demo.spec.baseline").unlink()
        run.arm(self.case.root, "demo", "generator-session", allow_no_git=True)
        self.case.goal = hooks.active_goal(self.case.root)
        hooks.append_event(self.case.goal, {"event": "verification_started", "turn": 1,
                                           "verification_id": "interrupted", "session_id": "generator-session"})
        with patch.object(stop.subprocess, "run") as execute:
            result = run.verify(self.case.root, "demo", "generator-session")
        execute.assert_not_called()
        self.assertFalse(result["verification_passed"])
        self.assertEqual("ceiling_reached", result["observation"]["event"])
        self.assertEqual(2, len(self.attempts()))

    @unittest.skipIf(os.name == "nt", "POSIX process-group SIGKILL probe")
    def test_real_sigkill_preserves_attempt_and_recovery_supersedes_old_green(self):
        case = self.case
        # Only probe telemetry is written by this otherwise observational anchor.
        case.program.write_text("from pathlib import Path\nimport time\n"
                                "if Path('pause').exists():\n Path('entered').touch()\n time.sleep(30)\n"
                                "assert Path('result.txt').read_text() == 'correct'\n")
        case.arm()
        self.assertTrue(run.verify(case.root, "demo", "generator-session")["verification_passed"])
        (case.root / "result.txt").write_text("wrong")
        (case.root / "pause").touch()
        proc = subprocess.Popen([sys.executable, str(SCRIPTS / "goal_run.py"), "verify", "demo",
                                 "--root", str(case.root), "--session-id", "generator-session"],
                                start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not (case.root / "entered").exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue((case.root / "entered").exists(), "verifier did not enter the anchor")
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate(timeout=5)
            self.assertEqual(-signal.SIGKILL, proc.returncode)
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate(timeout=5)
        self.assertEqual(2, len(self.attempts()))
        status = validator.last_verification(case.goal.goal_path)
        self.assertEqual(("unknown", 2), (status["status"], status["attempt"]))
        context = goal_session_start.handle({"source": "resume"}, case.goal, "claude")["hookSpecificOutput"]["additionalContext"]
        self.assertIn("completion is unverified", context)
        self.assertNotIn("Last completion check: attempt 1", context)
        self.assertIn("goal is unverified", goal_prompt_submit._last_decision(case.goal))
        stop.handle({"session_id": "generator-session"}, case.goal, "claude")
        self.assertEqual((2, "verification_interrupted"), (len(self.attempts()), self.attempts()[-1]["event"]))
        (case.root / "pause").unlink()
        (case.root / "result.txt").write_text("correct")
        resumed = run.verify(case.root, "demo", "generator-session")
        self.assertTrue(resumed["verification_passed"])
        self.assertEqual(3, resumed["observation"]["turn"])
        self.assertEqual(3, len(self.attempts()))

    def test_existing_audit_verifies_retained_review_after_temporary_cleanup(self):
        case = self.case
        case.arm({"path": ".goals/.work/review.json", "verifiers": ["backup"], "inputs": ["result.txt"]})
        case.receipt()
        result = run.verify(case.root, "demo", "generator-session")
        self.assertTrue(result["verification_passed"])
        evidence = result["observation"]["review_evidence"]
        self.assertIn("archive", evidence)
        (case.goals / ".work/review.json").unlink()
        audit, findings = validator.audit_artifact(case.goal.goal_path)
        self.assertEqual("verified", audit["review_archives"][-1]["status"])
        self.assertNotIn("REVIEW_ARCHIVE_UNAVAILABLE", {finding.code for finding in findings})
        (case.root / evidence["archive"]["path"]).write_bytes(b"corrupted archive")
        audit, findings = validator.audit_artifact(case.goal.goal_path)
        self.assertEqual("unavailable", audit["review_archives"][-1]["status"])
        self.assertIn("REVIEW_ARCHIVE_UNAVAILABLE", {finding.code for finding in findings})


if __name__ == "__main__":
    unittest.main()
