"""Behavioral contract checks through real arm/Stop and current evidence."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins/ultra-goal/skills/ultragoal/scripts"
sys.path.insert(0, str(SCRIPTS))
import goal_contract as contract
import goal_hooks as hooks
import goal_run as run
import goal_stop as stop
import validate_artifact as validator


def spec_text(review=None):
    definition = {"source": "owner-approved", "basis": "Owner-supplied acceptance program.",
                  "protected": ["acceptance.py"], "covers": {"result": "anchor"}, "review": review}
    if review:
        definition["covers"]["result"] = "review"
    return f'''# Goal: demo

## Intent
Deliver the requested result without changing its evaluator.

## Boundary
Only result.txt and working notes may change. No external effects.

## Stop condition
success: verified
ceiling: 6

## Anchor
```
"{sys.executable}" acceptance.py
```
budget: 2 seconds

## Means
- Preserve the requested result
  [load-bearing]
- [droppable] Use the original worker.

## Roles
- implementer: main session; fallback: another authorized worker.

## Verification
```json
{json.dumps(definition)}
```

## Acceptance
- [ ] result: The final output is correct.

## Carry-over
Read before acting; rewrite before finishing.
### State
- Result awaits verification.
### Lessons
- None yet.
### Next
- Verify the accepted result.

## Handoff
```
/goal Deliver demo using the armed contract.
```
'''


class GoalContractTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.goals = self.root / ".goals"
        self.goals.mkdir()
        self.program = self.root / "acceptance.py"
        self.program.write_text("from pathlib import Path\nassert Path('result.txt').read_text() == 'correct'\n")
        (self.root / "result.txt").write_text("correct")
        (self.goals / "demo.decisions.md").write_text(
            "| Decision | Rejected | Why | Who |\n| --- | --- | --- | --- |\n"
            "| Accepted checks | Self-report | Independent evidence | owner |\n")

    def arm(self, review=None):
        self.spec = spec_text(review)
        (self.goals / "demo.goal.md").write_text(self.spec)
        run.arm(self.root, "demo", "generator-session")
        self.goal = hooks.active_goal(self.root)

    def claim(self):
        (self.goals / "demo.candidate").write_text("proposed completion")
        return stop.handle({"session_id": "generator-session", "stop_hook_active": False}, self.goal, "claude")

    def receipt(self, verifier="backup", session="review-session"):
        path = self.root / ".goals/.work/review.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({"verifier": verifier, "session_id": session,
            "input_digest": contract.input_digest(self.root, self.spec), "covers": ["result"],
            "verdict": "pass", "evidence": "Independently read result.txt and exercised the accepted check.",
            "checks": {"result": {"claim": "The result is correct.",
                                   "evidence": [{"path": "result.txt", "quote": "correct"}]}}}))

    def test_a_committed_product_writer_cannot_sign_independent_review(self):
        def git(*args):
            return subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True)

        git("init", "-q")
        git("config", "user.name", "Test")
        git("config", "user.email", "test@example.invalid")
        (self.root / "result.txt").write_text("draft")
        git("add", "acceptance.py", "result.txt")
        git("commit", "-qm", "initial product")
        self.arm({"path": ".goals/.work/review.json", "verifiers": ["backup"], "inputs": ["result.txt"]})
        git("checkout", "-qb", "worker-change")
        (self.root / "result.txt").write_text("correct")
        git("add", "result.txt")
        git("commit", "-qm", "worker implementation")
        git("checkout", "-q", "-")
        git("merge", "--no-ff", "-qm", "goal(demo) step: implement result\n\n"
            "Reason: Satisfy the result requirement.\nCheck: acceptance.py exited 0.\n"
            "Evidence: result.txt\nRemaining: Independent review.\nWriter-Session: worker-session", "worker-change")
        git("commit", "--allow-empty", "-qm", "goal(other) step: unrelated\n\nWriter-Session: independent-session")
        self.receipt(session="worker-session")
        self.assertFalse(run.verify(self.root, "demo", "generator-session")["verification_passed"])
        self.receipt(session="independent-session")
        self.assertTrue(run.verify(self.root, "demo", "generator-session")["verification_passed"])

    def test_verify_returns_this_attempt_before_stop_and_does_not_repeat_it(self):
        self.arm()
        with self.assertRaisesRegex(ValueError, "bound native session"):
            run.verify(self.root, "demo", "stranger")
        self.assertFalse((self.goals / "demo.candidate").exists())
        result = run.verify(self.root, "demo", "generator-session")
        self.assertTrue(result["verification_passed"])
        self.assertEqual("command", result["observation"]["trigger"])
        self.assertFalse((self.goals / "demo.candidate").exists())
        stop.handle({"session_id": "generator-session"}, self.goal, "claude")
        self.assertEqual(1, sum(hooks.completion_attempt(e) for e in hooks.read_events(self.goal)))
        (self.root / "result.txt").write_text("wrong")
        result = run.verify(self.root, "demo", "generator-session")
        self.assertFalse(result["verification_passed"])
        self.assertEqual("red", result["observation"]["outcome"])
        self.assertEqual(2, result["observation"]["turn"])

    def test_review_must_cover_each_requirement_with_real_input_quotes(self):
        self.arm({"path": ".goals/.work/review.json", "verifiers": ["backup"], "inputs": ["result.txt"]})
        self.receipt()
        path = self.goals / ".work/review.json"
        good = json.loads(path.read_text())
        for checks in ({}, {"result": {"claim": "Correct", "evidence": []}},
                       {"result": {"claim": "Correct", "evidence": [{"path": "acceptance.py", "quote": "assert"}]}},
                       {"result": {"claim": "Correct", "evidence": [{"path": "result.txt", "quote": "invented"}]}}):
            path.write_text(json.dumps({**good, "checks": checks}))
            with self.assertRaises(ValueError):
                contract.check_review(self.goal, self.spec)
        path.write_text(json.dumps(good))
        self.assertTrue(run.verify(self.root, "demo", "generator-session")["verification_passed"])

    def test_retained_review_survives_work_cleanup_with_every_declared_input(self):
        source = self.goals / ".work/source"
        source.mkdir(parents=True)
        (source / "original.txt").write_text("The original source supports the correct result.")
        binary = bytes(range(256)) * 5000
        (source / "attachment.bin").write_bytes(binary)
        self.arm({"path": ".goals/.work/review.json", "verifiers": ["backup"],
                  "inputs": ["result.txt", ".goals/.work/source"]})
        self.receipt()
        receipt = (self.goals / ".work/review.json").read_bytes()
        self.assertNotIn("archive", contract.check_review(self.goal, self.spec))
        self.assertFalse((self.goals / "demo.reviews").exists())
        result = run.verify(self.root, "demo", "generator-session")
        self.assertTrue(result["verification_passed"])
        evidence = result["observation"]["review_evidence"]
        shutil.rmtree(self.goals / ".work")
        (self.root / "result.txt").unlink()
        historical = contract.read_review_archive(self.root, evidence)
        self.assertEqual(5, len(historical["manifest"]["files"]))
        audit, findings = validator.audit_artifact(self.goal.goal_path)
        self.assertEqual("verified", audit["review_archives"][0]["status"])
        self.assertNotIn("REVIEW_ARCHIVE_UNAVAILABLE", [finding.code for finding in findings])
        with zipfile.ZipFile(self.root / historical["path"]) as archive:
            self.assertEqual(receipt, archive.read("receipt.json"))
            self.assertEqual(self.spec.encode(), archive.read("goal.md"))
            self.assertEqual(b"correct", archive.read("inputs/result.txt"))
            self.assertEqual(binary, archive.read("inputs/.goals/.work/source/attachment.bin"))
            self.assertIn(b"original source", archive.read("inputs/.goals/.work/source/original.txt"))
        with self.assertRaisesRegex(ValueError, "Required independent review is missing"):
            contract.check_review(self.goal, self.spec, retain=True)

    def test_historical_review_does_not_replace_a_current_receipt_or_current_inputs(self):
        self.arm({"path": ".goals/.work/review.json", "verifiers": ["backup"], "inputs": ["result.txt"]})
        self.receipt()
        evidence = contract.check_review(self.goal, self.spec, retain=True)
        self.assertEqual(evidence, contract.check_review(self.goal, self.spec, retain=True))
        (self.root / "result.txt").write_text("different result")
        with self.assertRaisesRegex(ValueError, "stale"):
            contract.check_review(self.goal, self.spec, retain=True)
        self.assertEqual(evidence["archive"]["path"], contract.read_review_archive(self.root, evidence)["path"])
        (self.root / "result.txt").write_text("correct")
        path = self.goals / ".work/review.json"
        receipt = json.loads(path.read_text())
        path.write_text(json.dumps({**receipt, "verdict": "fail"}))
        with self.assertRaisesRegex(ValueError, "did not pass"):
            contract.check_review(self.goal, self.spec, retain=True)
        path.unlink()
        with self.assertRaisesRegex(ValueError, "Required independent review is missing"):
            contract.check_review(self.goal, self.spec, retain=True)

    def test_recorded_review_archive_tampering_is_visible_and_never_silently_repaired(self):
        self.arm({"path": ".goals/.work/review.json", "verifiers": ["backup"], "inputs": ["result.txt"]})
        self.receipt()
        result = run.verify(self.root, "demo", "generator-session")
        self.assertTrue(result["verification_passed"])
        evidence = result["observation"]["review_evidence"]
        archive_path = self.root / evidence["archive"]["path"]
        original = archive_path.read_bytes()
        archive_path.write_bytes(original + b"unrecorded modification")
        with self.assertRaisesRegex(ValueError, "archive digest mismatch"):
            contract.read_review_archive(self.root, evidence)
        with self.assertRaisesRegex(ValueError, "archive digest mismatch"):
            contract.check_review(self.goal, self.spec, retain=True)
        self.assertEqual(original + b"unrecorded modification", archive_path.read_bytes())
        audit, findings = validator.audit_artifact(self.goal.goal_path)
        self.assertEqual("unavailable", audit["review_archives"][0]["status"])
        self.assertIn("REVIEW_ARCHIVE_UNAVAILABLE", [finding.code for finding in findings])

    def test_retention_failure_cannot_publish_partial_evidence(self):
        self.arm({"path": ".goals/.work/review.json", "verifiers": ["backup"], "inputs": ["result.txt"]})
        self.receipt()
        with patch.object(contract.os, "replace", side_effect=OSError("disk failure")):
            with self.assertRaisesRegex(OSError, "disk failure"):
                contract.check_review(self.goal, self.spec, retain=True)
        self.assertEqual([], list((self.goals / "demo.reviews").iterdir()))

    def test_review_archive_does_not_enter_its_own_input_snapshot(self):
        path = self.root / "review.json"
        self.arm({"path": "review.json", "verifiers": ["backup"], "inputs": ["result.txt", ".goals"]})
        self.receipt()
        shutil.move(self.goals / ".work/review.json", path)
        receipt = json.loads(path.read_text())
        receipt["input_digest"] = contract.input_digest(self.root, self.spec)
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "archive destination overlaps reviewed inputs"):
            contract.check_review(self.goal, self.spec, retain=True)
        self.assertFalse((self.goals / "demo.reviews").exists())

    def test_verify_cannot_reuse_green_when_this_measurement_was_not_recorded(self):
        self.arm()
        self.assertTrue(run.verify(self.root, "demo", "generator-session")["verification_passed"])
        with patch.object(stop, "append_event", return_value=False):
            result = run.verify(self.root, "demo", "generator-session")
        self.assertFalse(result["verification_passed"])
        self.assertIsNone(result["observation"])

    def test_verify_returns_its_own_result_when_another_check_finishes_before_readback(self):
        self.arm()
        (self.root / "result.txt").write_text("wrong")
        paused, release = threading.Event(), threading.Event()
        caller = threading.current_thread()
        read_events = run.read_events

        def delay_first_readback(goal):
            events = read_events(goal)
            if threading.current_thread() is not caller and any(
                event.get("claim") == "first red claim" for event in events
            ):
                paused.set()
                if not release.wait(5):
                    raise TimeoutError("Second verification did not finish")
            return read_events(goal)

        with ThreadPoolExecutor(max_workers=1) as pool:
            with patch.object(run, "read_events", side_effect=delay_first_readback):
                first = pool.submit(run.verify, self.root, "demo", "generator-session", "first red claim")
                try:
                    self.assertTrue(paused.wait(5))
                    self.assertEqual("red", hooks.read_events(self.goal)[-1]["outcome"])
                    (self.root / "result.txt").write_text("correct")
                    second = run.verify(self.root, "demo", "generator-session", "second green claim")
                finally:
                    release.set()
                result = first.result(timeout=5)
        self.assertFalse(result["verification_passed"])
        self.assertEqual("first red claim", result["observation"]["claim"])
        self.assertTrue(second["verification_passed"])
        self.assertNotEqual(result["observation"]["verification_id"], second["observation"]["verification_id"])

    def test_verify_and_stop_share_lock_and_cannot_exceed_attempt_ceiling(self):
        with patch(__name__ + ".spec_text", side_effect=lambda review=None, original=spec_text:
                   original(review).replace("ceiling: 6", "ceiling: 1")):
            self.arm()
        entered, release = threading.Event(), threading.Event()
        handle = stop._handle

        def hold_acquired_lock(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("Concurrent callers did not finish")
            return handle(*args, **kwargs)

        with ThreadPoolExecutor(max_workers=1) as pool:
            with patch.object(stop, "_handle", side_effect=hold_acquired_lock):
                first = pool.submit(run.verify, self.root, "demo", "generator-session")
                try:
                    self.assertTrue(entered.wait(5))
                    second = run.verify(self.root, "demo", "generator-session")
                    self.assertFalse(second["verification_passed"])
                    self.assertIsNone(second["observation"])
                    stop.handle({"session_id": "generator-session"}, self.goal, "claude")
                    self.assertFalse(any(hooks.completion_attempt(e) for e in hooks.read_events(self.goal)))
                finally:
                    release.set()
                self.assertTrue(first.result(timeout=5)["verification_passed"])
        attempts = [e for e in hooks.read_events(self.goal) if hooks.completion_attempt(e)]
        self.assertEqual([1], [e["turn"] for e in attempts])
        self.assertFalse((self.goals / "demo.candidate").exists())
        exhausted = run.verify(self.root, "demo", "generator-session")
        self.assertFalse(exhausted["verification_passed"])
        self.assertEqual("ceiling_reached", exhausted["observation"]["event"])

    def test_review_digest_binds_criteria_but_not_mutable_progress(self):
        self.arm({"path": ".goals/.work/review.json", "verifiers": ["backup"], "inputs": ["result.txt"]})
        digest = contract.input_digest(self.root, self.spec)
        stronger = self.spec.replace("final output is correct", "final output is correct and independently reconciled")
        self.assertNotEqual(digest, contract.input_digest(self.root, stronger))
        self.assertEqual(digest, contract.input_digest(self.root, self.spec.replace("- [ ] result", "- [x] result")))

    def test_full_contract_is_frozen_but_progress_and_method_are_not(self):
        spec = spec_text()
        digest = hooks.frozen_digest(spec)
        for changed in (spec.replace("ceiling: 6", "ceiling: 600"),
                        spec.replace("success: verified", "success: guessed"),
                        spec.replace("[load-bearing]", "[droppable]"),
                        spec.replace("final output is correct", "final output exists"),
                        spec.replace("Owner-supplied acceptance program", "Generator self-approval")):
            self.assertNotEqual(digest, hooks.frozen_digest(changed))
        self.assertEqual(digest, hooks.frozen_digest(spec.replace("- [ ] result", "- [x] result")))
        self.assertEqual(digest, hooks.frozen_digest(spec + "\n## Carry-over\nNew strategy and state.\n"))

    def test_self_verifier_and_missing_coverage_do_not_validate(self):
        for text in (spec_text().replace('"source": "owner-approved"', '"source": "generator"'),
                     spec_text().replace('"covers": {"result": "anchor"}', '"covers": {}'),
                     spec_text().replace('"review": null', '"review": "trust me"')):
            findings = []
            validator.check_goal(Path("demo.goal.md"), text, findings)
            self.assertIn("VERIFICATION_CONTRACT_INVALID", [f.code for f in findings])

    def test_changed_evaluator_cannot_turn_red_into_verified_green(self):
        self.arm()
        (self.root / "result.txt").write_text("wrong")
        self.assertEqual("block", self.claim()["decision"])
        self.program.write_text("raise SystemExit(0)\n")
        result = self.claim()
        self.assertEqual("block", result["decision"])
        self.assertIn("Protected evaluator inputs changed", result["reason"])
        self.assertFalse(any(e.get("verification_passed") for e in hooks.read_events(self.goal)))
        with self.assertRaises(ValueError):
            run.arm(self.root, "demo", "generator-session")

    def test_anchor_cannot_rewrite_its_own_checker(self):
        self.program.write_text("from pathlib import Path\nPath(__file__).write_text('pass')\n")
        self.arm()
        self.assertEqual("block", self.claim()["decision"])
        event = hooks.read_events(self.goal)[-1]
        self.assertEqual("green", event["anchor_outcome"])
        self.assertFalse(event["verification_passed"])

    def test_anchor_cannot_rewrite_the_goal_while_it_is_being_verified(self):
        self.program.write_text(
            "from pathlib import Path\np = Path('.goals/demo.goal.md')\n"
            "p.write_text(p.read_text().replace('ceiling: 6', 'ceiling: 600'))\n")
        self.arm()
        result = self.claim()
        self.assertEqual("block", result["decision"])
        self.assertIn("Frozen goal terms changed during verification", result["reason"])
        event = hooks.read_events(self.goal)[-1]
        self.assertEqual("green", event["anchor_outcome"])
        self.assertFalse(event["verification_passed"])
        stop.handle({"session_id": "generator-session"}, self.goal, "claude")
        self.assertFalse(self.goal.marker_path.exists())
        self.assertEqual("frozen_spec_changed", hooks.read_events(self.goal)[-1]["event"])

    def test_required_review_is_current_independent_and_allows_approved_fallback(self):
        self.arm({"path": ".goals/.work/review.json", "verifiers": ["primary", "backup"], "inputs": ["result.txt"]})
        hooks.append_event(self.goal, {"event": "role_unavailable", "role": "primary", "tool": "Bash"})
        self.assertEqual("block", self.claim()["decision"])
        self.receipt(session="generator-session")
        self.assertEqual("block", self.claim()["decision"])
        self.receipt(verifier="unapproved")
        self.assertEqual("block", self.claim()["decision"])
        self.receipt()
        (self.root / "result.txt").write_text("new result")
        self.assertIn("stale", self.claim()["reason"])
        (self.root / "result.txt").write_text("correct")
        self.receipt()
        result = self.claim()
        self.assertNotIn("decision", result)
        event = hooks.read_events(self.goal)[-1]
        self.assertTrue(event["verification_passed"])
        self.assertEqual("backup", event["review_evidence"]["verifier"])
        self.assertEqual(["primary"], event["unrecovered_targets"])

    def test_original_worker_need_not_recover_if_acceptance_passes(self):
        self.arm()
        hooks.append_event(self.goal, {"event": "role_unavailable", "role": "primary", "tool": "Bash"})
        self.assertNotIn("decision", self.claim())
        self.assertTrue(hooks.read_events(self.goal)[-1]["verification_passed"])

    def test_closed_goal_cannot_be_resurrected_by_restoring_text_and_rearming(self):
        self.arm()
        self.goal.goal_path.write_text(self.spec.replace("ceiling: 6", "ceiling: 600"))
        with self.assertRaisesRegex(ValueError, "Frozen conditions"):
            run.arm(self.root, "demo", "generator-session")
        self.claim()
        self.assertTrue(hooks.completion_attempt(hooks.read_events(self.goal)[-1]))
        self.goal.goal_path.write_text(self.spec)
        with self.assertRaisesRegex(ValueError, "closed"):
            run.arm(self.root, "demo", "generator-session")
        self.assertFalse(self.goal.marker_path.exists())
        # Even if removal fails or an outside actor restores a marker, each
        # observed closure stays visible; an ordinary closure is not a candidate.
        self.goal.marker_path.write_text("demo\nsession generator-session\n")
        self.goal.goal_path.write_text(self.spec.replace("ceiling: 6", "ceiling: 600"))
        stop.handle({"session_id": "generator-session"}, self.goal, "claude")
        closures = [e for e in hooks.read_events(self.goal) if e["event"] == "frozen_spec_changed"]
        self.assertEqual(2, len(closures))
        self.assertFalse(hooks.completion_attempt(closures[-1]))

    def test_previous_generators_cannot_review_after_rebind_or_rearm(self):
        self.arm({"path": ".goals/.work/review.json", "verifiers": ["backup"], "inputs": ["result.txt"]})
        run.rebind(self.root, "demo", "second-generator")
        self.receipt(session="generator-session")
        with self.assertRaisesRegex(ValueError, "distinct verifier"):
            contract.check_review(hooks.active_goal(self.root), self.spec)
        run.disarm(self.root, "demo")
        run.arm(self.root, "demo", "third-generator")
        for session in ("generator-session", "second-generator", "third-generator"):
            self.receipt(session=session)
            with self.assertRaisesRegex(ValueError, "distinct verifier"):
                contract.check_review(hooks.active_goal(self.root), self.spec)
        self.receipt(session="independent-reviewer")
        self.assertEqual("independent-reviewer", contract.check_review(hooks.active_goal(self.root), self.spec)["session_id"])

    def test_every_shape_requires_the_same_contract(self):
        attachment = self.goals / "demo.workflow.js"
        attachment.write_text("// goal: `demo.goal.md`\n// anchor: `true`\n"
                              "export const meta = {\nname: 'demo',\ndescription: 'demo',\n}\nreturn 1\n")
        self.assertIn("GOAL_CONTRACT_MISSING", [f.code for f in validator.validate_file(attachment, "workflow")])
        self.arm()
        self.assertEqual([], validator.validate_file(attachment, "workflow"))
        changed = self.spec.replace('"covers": {"result": "anchor"}', '"covers": {}')
        (self.goals / "demo.goal.md").write_text(changed)
        self.assertIn("VERIFICATION_CONTRACT_INVALID", [f.code for f in validator.validate_file(attachment, "workflow")])

    def test_latest_refusal_and_pending_claim_do_not_reuse_old_green(self):
        self.arm()
        self.claim()
        self.assertEqual("passed", validator.describe(self.goal.goal_path, "goal")["last_verification"]["status"])
        (self.goals / "demo.verification.baseline").unlink()
        self.claim()
        state = validator.describe(self.goal.goal_path, "goal")
        self.assertTrue(state["last_check"]["verification_passed"])
        self.assertEqual("refused", state["last_verification"]["status"])
        (self.goals / "demo.candidate").write_text("new claim")
        self.assertEqual("pending", validator.describe(self.goal.goal_path, "goal")["last_verification"]["status"])


if __name__ == "__main__":
    unittest.main()
