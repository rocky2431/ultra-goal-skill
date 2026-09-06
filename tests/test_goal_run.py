"""Drive the arming fence and real hooks across session ownership changes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/ultra-goal/skills/ultragoal"
SCRIPTS = SKILL / "scripts"
SESSION_KEYS = ("CODEX_SESSION_ID", "CLAUDE_SESSION_ID", "KIMI_SESSION_ID", "ZCODE_SESSION_ID")
sys.path.insert(0, str(SCRIPTS))
from goal_hooks import frozen_digest  # noqa: E402


class ArmingIdentityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.goals = self.root / ".goals"
        self.goals.mkdir()
        (self.root / "tests").mkdir()
        (self.root / "tests" / "accepted.txt").write_text("Owner-controlled test fixture")
        for template, output in (("goal-package.md", "demo.goal.md"),
                                 ("decisions-record.md", "demo.decisions.md")):
            text = (SKILL / "assets" / template).read_text()
            if output.endswith(".decisions.md"):
                digest = frozen_digest((self.goals / "demo.goal.md").read_text())
                text = text.replace(
                    "| --- | --- | --- | --- |",
                    "| --- | --- | --- | --- |\n"
                    "| Confirm package checkpoint | Arm without final readback | "
                    f"Confirmed complete fixture; frozen:{digest} | owner |",
                    1,
                )
            (self.goals / output).write_text(text)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Test"], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "config", "user.email", "test@example.invalid"],
            check=True,
        )
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "-c", "commit.gpgsign=false", "-c",
             "core.hooksPath=", "commit", "-qm", "fixture baseline"],
            check=True,
        )
        self.env = {k: v for k, v in os.environ.items() if k not in SESSION_KEYS}

    def run_action(self, action="arm", *args, env=None):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "goal_run.py"), action, "demo", *args],
            cwd=self.root, env=self.env if env is None else env,
            capture_output=True, text=True, timeout=30,
        )

    def test_missing_or_ambiguous_identity_cannot_arm(self):
        for env in (self.env, {**self.env, "CLAUDE_SESSION_ID": "inherited-parent"},
                    {**self.env, "CODEX_SESSION_ID": "A", "KIMI_SESSION_ID": "B"}):
            result = self.run_action(env=env)
            self.assertEqual(1, result.returncode, result.stdout)
            self.assertFalse((self.goals / "active").exists())

    def test_git_is_default_and_no_git_requires_an_explicit_flag(self):
        no_git = {**self.env, "PATH": ""}
        refused = self.run_action("arm", "--session-id", "owner-A", env=no_git)
        self.assertEqual(1, refused.returncode)
        self.assertIn("usable Git HEAD by default", refused.stderr)
        self.assertFalse((self.goals / "active").exists())

        allowed = self.run_action(
            "arm", "--session-id", "owner-A", "--allow-no-git", env=no_git
        )
        self.assertEqual(0, allowed.returncode, allowed.stderr)
        self.assertEqual("none\n", (self.goals / "demo.baseline").read_text())
        self.assertIn("No-Git mode was explicitly selected", allowed.stdout)

    def test_package_confirmation_tracks_current_frozen_terms(self):
        goal = self.goals / "demo.goal.md"
        goal.write_text(goal.read_text().replace("ceiling: 6", "ceiling: 7"))
        result = self.run_action("arm", "--session-id", "owner-A")
        self.assertEqual(1, result.returncode)
        self.assertIn("OWNER_CONFIRMATION_STALE", result.stderr)
        self.assertFalse((self.goals / "active").exists())

    def test_spec_digest_reports_current_frozen_terms(self):
        result = self.run_action("spec-digest")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            frozen_digest((self.goals / "demo.goal.md").read_text()),
            result.stdout.strip(),
        )

    def test_rearm_reports_the_write_once_no_git_baseline(self):
        first = self.run_action(
            "arm", "--session-id", "owner-A", "--allow-no-git",
            env={**self.env, "PATH": ""},
        )
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(0, self.run_action("disarm").returncode)
        second = self.run_action("arm", "--session-id", "owner-B")
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertIn("review baseline none", second.stdout)
        self.assertIn("No-Git mode was explicitly selected", second.stdout)

    def test_active_legacy_goal_rearms_without_backfilled_confirmation(self):
        first = self.run_action("arm", "--session-id", "owner-A")
        self.assertEqual(0, first.returncode, first.stderr)
        record = self.goals / "demo.decisions.md"
        record.write_text("\n".join(
            line for line in record.read_text().splitlines()
            if "Confirm package checkpoint" not in line
        ) + "\n")
        resumed = self.run_action("arm", "--session-id", "owner-A")
        self.assertEqual(0, resumed.returncode, resumed.stderr)
        self.assertIn("already armed", resumed.stdout)

    def test_identity_is_bound_before_any_stop(self):
        result = self.run_action("arm", "--session-id", "owner-A")
        self.assertEqual(0, result.returncode, result.stderr)
        marker = self.goals / "active"
        self.assertEqual("demo\nsession owner-A\n", marker.read_text())
        candidate = self.goals / "demo.candidate"
        candidate.write_text("A's proposed completion")
        binding_log = (self.goals / "demo.events.jsonl").read_text()
        self.assertEqual(["owner-A"], json.loads(binding_log)["sessions"])
        for session in ("stranger-B", None):
            event = {"hook_event_name": "Stop", "cwd": str(self.root), "session_id": session}
            stop = subprocess.run(
                [sys.executable, str(SCRIPTS / "goal_stop.py")],
                input=json.dumps(event), capture_output=True, text=True, timeout=30,
            )
            self.assertEqual("", stop.stdout)
            self.assertEqual("demo\nsession owner-A\n", marker.read_text())
            self.assertTrue(candidate.exists())
            self.assertEqual(binding_log, (self.goals / "demo.events.jsonl").read_text())

    def test_environment_identity_and_explicit_nested_identity(self):
        env = {**self.env, "CODEX_SESSION_ID": "parent", "KIMI_SESSION_ID": "child"}
        result = self.run_action("arm", "--session-id", "child", env=env)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("session child", (self.goals / "active").read_text())
        self.assertEqual(1, self.run_action("arm", "--session-id", "parent").returncode)

    def test_explicit_rebind_preserves_baselines_and_discards_old_claim(self):
        self.assertEqual(0, self.run_action("arm", "--session-id", "A").returncode)
        baseline = (self.goals / "demo.spec.baseline").read_bytes()
        (self.goals / "demo.candidate").write_text("old session claim")
        result = self.run_action("rebind", "--session-id", "B")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("demo\nsession B\n", (self.goals / "active").read_text())
        self.assertFalse((self.goals / "demo.candidate").exists())
        self.assertEqual(baseline, (self.goals / "demo.spec.baseline").read_bytes())
        goal = self.goals / "demo.goal.md"
        goal.write_text(goal.read_text().replace("## Intent\n", "## Intent\nChanged intent.\n"))
        self.assertEqual(1, self.run_action("rebind", "--session-id", "C").returncode)
        self.assertIn("session B", (self.goals / "active").read_text())

    def test_each_new_failure_can_be_recovered(self):
        sys.path.insert(0, str(SCRIPTS))
        import goal_hooks
        import goal_stop
        import goal_tool_failure
        import goal_tool_success
        self.assertEqual(0, self.run_action("arm", "--session-id", "A").returncode)
        goal = goal_hooks.active_goal(self.root)
        invocation = {"tool_name": "Bash", "tool_input": {"command": "agent-delegate run --to worker --task review"}}
        for _ in range(2):
            goal_tool_failure.handle(invocation, goal, "claude")
            self.assertTrue(goal_stop._unrecovered_failures(goal_hooks.read_events(goal)))
            goal_tool_success.handle(invocation, goal, "claude")
            self.assertEqual([], goal_stop._unrecovered_failures(goal_hooks.read_events(goal)))
        events = goal_hooks.read_events(goal)
        goal_tool_success.handle(invocation, goal, "claude")
        self.assertEqual(events, goal_hooks.read_events(goal))

    def test_search_text_cannot_create_or_clear_worker_failure(self):
        sys.path.insert(0, str(SCRIPTS))
        import goal_hooks, goal_tool_failure, goal_tool_success
        self.assertEqual(0, self.run_action("arm", "--session-id", "A").returncode)
        goal = goal_hooks.active_goal(self.root)
        mention = {"tool_name": "Bash", "tool_input": {"command": "rg agent-delegate README.md"},
                   "tool_response": "agent-delegate run --to kimi --task review"}
        before = goal_hooks.read_events(goal)
        goal_tool_failure.handle(mention, goal, "claude")
        self.assertEqual(before, goal_hooks.read_events(goal))
        invocation = {"tool_name": "Bash", "tool_input": {
            "command": "agent-delegate run --to kimi --task review"}}
        goal_tool_failure.handle(invocation, goal, "claude")
        failed = goal_hooks.read_events(goal)
        goal_tool_success.handle(mention, goal, "claude")
        self.assertEqual(failed, goal_hooks.read_events(goal))
        goal_tool_success.handle(invocation, goal, "claude")
        self.assertEqual("role_recovered", goal_hooks.read_events(goal)[-1]["event"])
        self.assertEqual("kimi", goal_hooks.read_events(goal)[-1]["role"])

    def test_means_relabelling_closes_run_and_rearm_reports_retained_count(self):
        self.assertEqual(0, self.run_action("arm", "--session-id", "A").returncode)
        log = self.goals / "demo.events.jsonl"
        log.write_text(json.dumps({"event": "candidate_refused", "turn": 1}) + "\n")
        self.assertEqual(0, self.run_action("disarm").returncode)
        self.assertIn("1 earlier completion attempt(s)",
                      self.run_action("arm", "--session-id", "A").stdout)
        goal = self.goals / "demo.goal.md"
        goal.write_text(goal.read_text().replace("- `[load-bearing]`", "- `[droppable]`", 1))
        result = subprocess.run([sys.executable, str(SCRIPTS / "goal_stop.py")],
            input=json.dumps({"hook_event_name": "Stop", "cwd": str(self.root), "session_id": "A"}),
            capture_output=True, text=True, timeout=30)
        self.assertIn("no longer the goal the owner authorized", result.stdout)
        self.assertIn("Means declaration", result.stdout)
        self.assertFalse((self.goals / "active").exists())
        self.assertEqual("frozen_spec_changed", json.loads(log.read_text().splitlines()[-1])["event"])


if __name__ == "__main__":
    unittest.main()
