from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "loop-graph-design"
SKILL_ROOT = PLUGIN_ROOT / "skills" / "loop-graph-design"

sys.path.insert(0, str(SKILL_ROOT / "scripts"))
import validate_artifact as va  # noqa: E402


# Contract assertions below match literal sentences in SKILL.md and the templates.
# They are deliberately newline-sensitive: a load-bearing sentence that wraps mid-phrase
# is harder to read and harder to grep, so the fix for a failure here is to reflow the
# document, not to loosen the assertion.
def skill_text() -> str:
    return (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")


def plugin_manifest() -> dict:
    return json.loads(
        (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )


class IdentityTests(unittest.TestCase):
    def test_plugin_marketplace_and_skill_identity_match(self) -> None:
        plugin = plugin_manifest()
        marketplace = json.loads(
            (REPO_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )
        entry = marketplace["plugins"][0]

        self.assertEqual("loop-graph-design", plugin["name"])
        self.assertEqual(plugin["name"], entry["name"])
        self.assertEqual("./skills/", plugin["skills"])
        self.assertEqual("./plugins/loop-graph-design", entry["source"]["path"])
        self.assertIn("name: loop-graph-design", skill_text())
        self.assertEqual(["Skills"], plugin["interface"]["capabilities"])
        self.assertLessEqual(len(plugin["interface"]["defaultPrompt"]), 128)

        openai = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        prompt = re.search(r'(?m)^  default_prompt: "([^"]+)"$', openai)
        short = re.search(r'(?m)^  short_description: "([^"]+)"$', openai)
        self.assertIsNotNone(prompt)
        self.assertIsNotNone(short)
        self.assertEqual(plugin["interface"]["defaultPrompt"], prompt.group(1))
        self.assertEqual(plugin["interface"]["shortDescription"], short.group(1))

    def test_version_is_consistent(self) -> None:
        version = plugin_manifest()["version"]
        self.assertIn(
            f'metadata:\n  author: rocky2431\n  version: "{version}"', skill_text()
        )
        self.assertIn(
            f'VERSION = "{version}"',
            (REPO_ROOT / "scripts" / "install_user.py").read_text(encoding="utf-8"),
        )


class SkillContractTests(unittest.TestCase):
    def test_description_states_the_artifact_boundary(self) -> None:
        description = re.search(r'(?m)^description: "(.+)"$', skill_text())
        self.assertIsNotNone(description)
        text = description.group(1)
        self.assertLessEqual(len(text), 380)
        self.assertIn("not a design note", text)
        for shape in ("goal prompt", "workflow script", "delegation package"):
            self.assertIn(shape, text)
        # The artifact shapes are portable; the primitives that start them are not.
        # Only one host has a built-in loop command, so naming one here would bind
        # the Skill to that host in the very field used to route to it.
        for host_specific in ("/goal", "/loop", "/schedule", ".claude/"):
            self.assertNotIn(host_specific, text)

    def test_skill_encodes_the_interview_and_the_refusals(self) -> None:
        skill = skill_text()
        for required in (
            "## Keep activation scoped",
            "## Interview protocol",
            "One question per turn",
            "carries your recommended answer",
            "Facts are yours, decisions are theirs",
            "## Classify first",
            "Can you sketch the whole thing on paper",
            "## Refuse these shapes",
            "No anchor, no artifact",
            "never workflow phases",
            "An agent grading its own output praises it",
            "## Compile one artifact",
            "## Inspect what is running",
            "## Modify an existing loop",
            "## Validate, then hand off",
            "## Recognize the intent first",
            "run the status command before the first question",
            "That record is also the interview's progress",
            "Edit the affected row",
            "A loop whose anchor changed is a different loop",
            "## Make the loop evolve",
            "read it before acting and rewrite it before finishing",
            "**Rewrite, never append.**",
            "the diffs *are* the evolution",
            "one project's dead end is another project's correct answer",
            "no second",
        ):
            self.assertIn(required, skill, required)
        # Deliberately no line-count ceiling. Length is a proxy for bloat, and a
        # proxy optimized against stops measuring what it was standing in for: a
        # ceiling is satisfied by moving text into references/ whether or not that
        # makes the Skill better to use. What actually matters - SKILL.md holding
        # operating instructions while rationale lives in references/ - is a
        # judgement, so it stays a judgement. The assertions above still pin every
        # load-bearing rule, and test_every_relative_link_in_the_skill_resolves
        # keeps the references honest.

    def test_skill_does_not_mechanize_topology(self) -> None:
        skill = skill_text()
        self.assertIn("Do not generate topology from a template engine", skill)
        self.assertIn("never edits the artifact", skill)
        self.assertIn("its silence is not evidence", skill)

    def test_skill_stands_alone_and_stores_no_state(self) -> None:
        skill = skill_text()
        self.assertIn("Assume no other Skill is installed", skill)
        self.assertNotIn("belongs to a harness-design Skill", skill)
        self.assertIn("**Nothing is stored.**", skill)
        self.assertIn("recomputed on every call", skill)
        self.assertIn("Ask the owner first", skill)

    def test_skill_keeps_lessons_in_the_project_and_the_shape_small(self) -> None:
        skill = skill_text()
        self.assertIn("**Never** promote it to user-level configuration", skill)
        self.assertIn("no directory tree, no index, no ledger, no state machine", skill)
        reference = (SKILL_ROOT / "references" / "evolution-and-scope.md").read_text(
            encoding="utf-8"
        )
        # The two papers this section rests on, cited so the claim is checkable.
        self.assertIn("arXiv 2608.26263", reference)
        self.assertIn("arXiv 2608.27454", reference)
        self.assertIn("tested_hypotheses", reference)
        self.assertIn("48.7% to 63.7%", reference)
        # And what we deliberately did not take from them.
        self.assertIn("deliberately do **not** take", reference)

    def test_unattended_goal_template_wires_the_carry_over(self) -> None:
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        self.assertIn("## Cadence", goal)
        self.assertIn("## Carry-over", goal)
        self.assertIn("Read this before acting; rewrite it before finishing", goal)
        # The prompt the owner actually runs must carry the same instruction, or the
        # section never gets written.
        handoff = goal.split("## Handoff", 1)[1]
        self.assertIn("Read the Carry-over section", handoff)
        self.assertIn("Rewrite the Carry-over section", handoff)
        self.assertIn("Commit once", handoff)

    def test_behaviour_evals_cover_the_whole_lifecycle(self) -> None:
        data = json.loads(
            (SKILL_ROOT / "evals" / "evals.json").read_text(encoding="utf-8")
        )
        self.assertIn("standalone_assumption", data)
        names = {case["name"] for case in data["evals"]}
        for required in (
            "existing_artifact_makes_it_a_modify",
            "modify_surfaces_a_rejected_decision",
            "inspect_changes_nothing",
            "running_anchors_needs_consent",
            "changed_anchor_reopens_the_interview",
            "state_is_not_tracked_in_a_file",
            "unattended_loop_needs_carry_over",
            "one_shot_goal_needs_no_carry_over",
            "carry_over_is_rewritten_not_appended",
            "history_belongs_to_git",
            "raw_trace_stays_out_of_the_repository",
            "lesson_stays_in_the_project",
            "skill_does_not_accumulate_project_lessons",
            "workflow_script_requires_a_workflow_runtime",
            "external_schedule_when_the_host_has_none",
            "cadence_does_not_name_a_command_the_host_lacks",
            "artifacts_do_not_live_in_a_tool_directory",
            "external_schedule_still_needs_carry_over",
            "use_the_hosts_goal_mode_do_not_reinvent_it",
            "interactive_goal_command_cannot_be_scheduled",
            "host_capability_claim_gets_checked_not_assumed",
        ):
            self.assertIn(required, names)

    def test_skill_is_host_neutral(self) -> None:
        skill = skill_text()
        self.assertIn("## Know your host, and use its goal mode", skill)
        self.assertIn("You are the host.", skill)
        self.assertIn("On most hosts, scheduling is external.", skill)
        self.assertIn("requires a workflow runtime", skill)
        self.assertIn("do **not** emit `<slug>.workflow.js`", skill)
        # Artifacts are project assets, not one tool's private configuration.
        self.assertNotIn(".claude/workflows", skill)
        self.assertIn(".loops/", skill)
        # Activation scope must not name one host's commands either.
        # No host slash-command may appear outside the measured matrix and the
        # runner's own worked examples - that is where this Skill kept re-binding
        # itself. Matched inside backticks so filenames like goal-runner.sh and
        # <slug>.goal.md do not count.
        head, rest = skill.split("## Know your host", 1)
        tail = rest.split("### What this changes about the artifact", 1)[1]
        leaks = re.findall(r"`/(?:goal|loop|schedule)[` ]", head + tail)
        self.assertEqual([], leaks, f"host commands leaked: {leaks}")
        # Every measured host, Codex included - it was missed on the first pass.
        for host in ("Claude Code", "Codex", "Kimi", "zCode", "OpenCode"):
            self.assertIn(host, skill)

    def test_matrix_says_most_hosts_do_have_goal_mode(self) -> None:
        """The first version of this table claimed the opposite. It was wrong."""
        skill = skill_text()
        self.assertIn("most hosts *do* have goal mode", skill)
        self.assertIn("Goal mode is two layers, and they are complements", skill)
        self.assertIn("use the host's own goal mode", skill)
        self.assertIn("asks the anchor", skill)
        # A negative result must read as absence of evidence, not proof.
        self.assertIn("not found", skill)
        self.assertIn(
            "check your\nown host rather than trusting this table", skill
        )

    def test_templates_and_references_are_host_neutral(self) -> None:
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        self.assertNotIn(".claude/workflows", goal)
        handoff = goal.split("## Handoff", 1)[1]
        # One mechanism, portable: the runner, scheduled from outside the agent.
        self.assertIn("runner.sh", handoff)
        self.assertIn("crontab", handoff)
        self.assertIn("byte-identical on every host", handoff)
        # And no host-specific command as the way to start it.
        for host_specific in ("/loop ", "/schedule "):
            self.assertNotIn(host_specific, handoff)

        primitives = (SKILL_ROOT / "references" / "loop-primitives.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## When the host has no scheduler", primitives)
        self.assertIn("These four are shapes, not commands.", primitives)
        self.assertIn("Carry-over matters more, not less.", primitives)

    def test_every_relative_link_in_the_skill_resolves(self) -> None:
        missing = [
            target
            for target in re.findall(r"\]\((?!https?:)([^)#]+)\)", skill_text())
            if not (SKILL_ROOT / target).exists()
        ]
        self.assertEqual([], missing)


class TemplateTests(unittest.TestCase):
    """The shipped templates must satisfy the shipped validator."""

    def _validate(self, pairs: list[tuple[str, str]]) -> None:
        with tempfile.TemporaryDirectory() as work:
            for source, name in pairs:
                shutil.copy(SKILL_ROOT / "assets" / source, Path(work) / name)
            report = va.validate_paths([work])
            self.assertTrue(report.ok, [f.as_dict() for f in report.findings])

    def test_goal_template_validates(self) -> None:
        self._validate(
            [
                ("goal-package.md", "weekly-dep-upgrade.goal.md"),
                ("decisions-record.md", "weekly-dep-upgrade.decisions.md"),
            ]
        )

    def test_workflow_template_validates(self) -> None:
        self._validate(
            [
                ("workflow-script.js", "review-changed-files.workflow.js"),
                ("decisions-record.md", "review-changed-files.decisions.md"),
            ]
        )

    def test_delegation_template_validates(self) -> None:
        self._validate(
            [
                ("delegation-package.md", "settlement-audit.delegation.md"),
                ("decisions-record.md", "settlement-audit.decisions.md"),
            ]
        )

    def test_every_template_declares_an_anchor(self) -> None:
        workflow = (SKILL_ROOT / "assets" / "workflow-script.js").read_text(
            encoding="utf-8"
        )
        self.assertRegex(workflow, r"(?m)^// anchor: `[^`]+`$")
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        self.assertIn("## Anchor", goal)
        delegation = (SKILL_ROOT / "assets" / "delegation-package.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(2, delegation.count("- anchor:"))

    def test_delegation_template_only_names_known_targets(self) -> None:
        text = (SKILL_ROOT / "assets" / "delegation-package.md").read_text(
            encoding="utf-8"
        )
        for target in re.findall(r"(?m)^- target: (\S+)$", text):
            self.assertIn(target, va.KNOWN_TARGETS)


class GoalRunnerTests(unittest.TestCase):
    """The portable goal mechanism has to be real: valid shell, and host-agnostic."""

    RUNNER = SKILL_ROOT / "assets" / "goal-runner.sh"

    def test_runner_is_valid_shell(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(self.RUNNER)], capture_output=True, text=True
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_runner_is_executable(self) -> None:
        import os

        self.assertTrue(os.access(self.RUNNER, os.X_OK))

    def test_runner_has_the_four_fill_ins_and_every_host(self) -> None:
        text = self.RUNNER.read_text(encoding="utf-8")
        for fill_in in ("SLUG=", "MAX_TURNS=", "ANCHOR=(", "run_host()"):
            self.assertIn(fill_in, text)
        # Every host's one-shot entry, and Codex, which was missed entirely at first.
        for host in (
            "claude -p",
            "codex exec",
            "zcode --target",
            "kimi -p",
            "opencode run",
        ):
            self.assertIn(host, text)
        # And the instruction not to trust the list without checking.
        self.assertIn("check yours rather than trusting this list", text)

    def test_runner_lets_the_anchor_decide_not_the_model(self) -> None:
        text = self.RUNNER.read_text(encoding="utf-8")
        self.assertIn("the ANCHOR command's exit code decides", text)
        self.assertIn("A nonzero host exit is not a verdict", text)
        # No -e: an anchor that fails is the normal case and must not abort the loop.
        self.assertIn("set -uo pipefail", text)
        self.assertNotIn("set -euo", text)

    def test_skill_and_template_point_at_the_runner(self) -> None:
        skill = skill_text()
        self.assertIn("### Goal mode is two layers", skill)
        self.assertIn("the anchor gives the verdict", skill)
        self.assertIn("the ceiling is the for-loop", skill)
        self.assertIn("a nonzero host exit is\nnot a verdict", skill)
        self.assertIn("assets/goal-runner.sh", skill)
        # The Skill must not present the runner as a replacement for the host's own
        # goal mode - four of five hosts have one, and theirs is better integrated.
        self.assertIn("rather than replacing it", skill)
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        self.assertIn("runner.sh", goal.split("## Handoff", 1)[1])


class EvalTests(unittest.TestCase):
    def test_behavior_evals_cover_the_refusals(self) -> None:
        data = json.loads((SKILL_ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
        names = {case["name"] for case in data["evals"]}
        self.assertEqual(
            ["no_skill", "agent-harness-design", "loop-graph-design"],
            data["comparison_arms"],
        )
        self.assertGreaterEqual(len(data["evals"]), 12)
        self.assertEqual(len(data["evals"]), len(names))
        for required in (
            "no_anchor_blocks_the_artifact",
            "phase_split_is_refused",
            "self_review_is_refused",
            "unquantified_stop_condition_is_sharpened",
            "loop_is_enough_so_no_graph",
            "graph_is_allowed_when_context_isolates",
            "cross_vendor_star_limits_are_stated",
            "single_worker_delegation_is_a_loop",
            "mutual_checking_without_ground_is_refused",
            "decisions_record_is_not_architecture",
            "artifact_ends_with_a_start_command",
            "one_shot_task_does_not_activate",
        ):
            self.assertIn(required, names)

    def test_trigger_evals_separate_this_skill_from_its_neighbours(self) -> None:
        data = json.loads(
            (SKILL_ROOT / "evals" / "trigger-evals.json").read_text(encoding="utf-8")
        )
        cases = data["evals"]
        self.assertEqual(len(cases), len({case["name"] for case in cases}))
        self.assertTrue(
            {"positive", "negative", "ambiguous", "coexistence"}
            <= {case["kind"] for case in cases}
        )
        self.assertIn("agent-harness-design", data["adjacent_skills"])
        self.assertIn("agent-delegation", data["adjacent_skills"])

        negatives = [case for case in cases if case["kind"] == "negative"]
        self.assertGreaterEqual(len(negatives), 5)
        self.assertIn("standalone_assumption", data)
        for case in negatives:
            self.assertEqual(
                [],
                case["expected_skills"],
                f"{case['name']}: a negative must not depend on a neighbouring Skill "
                "being installed",
            )
        optional = {
            skill for case in cases for skill in case.get("optional_skills", [])
        }
        self.assertTrue(
            {"agent-harness-design", "agent-delegation"} <= optional,
            "record where a neighbour would take over, without requiring it",
        )
        for case in cases:
            # Coexistence must stay correct whether or not the neighbour is
            # installed, so it needs both resolutions. An ambiguous case may have
            # exactly one legitimate answer - its ambiguity can be about intent
            # (create vs modify) rather than about which Skill applies.
            if case["kind"] == "coexistence":
                self.assertGreaterEqual(len(case["accepted_skill_sets"]), 2, case["name"])
            elif case["kind"] == "ambiguous":
                self.assertGreaterEqual(len(case["accepted_skill_sets"]), 1, case["name"])
                self.assertIn("note", case, case["name"])


class ResearchTests(unittest.TestCase):
    def test_research_basis_cites_primary_sources(self) -> None:
        text = (SKILL_ROOT / "references" / "research-basis.md").read_text(
            encoding="utf-8"
        )
        self.assertGreaterEqual(text.count("https://"), 10)
        for source in (
            "claude.com/blog/getting-started-with-loops",
            "anthropic.com/engineering/multi-agent-research-system",
            "anthropic.com/research/multiagent-systems",
            "langchain.com/blog/3-years-of-graph-engineering-with-langgraph",
            "arxiv.org/abs/2503.13657",
        ):
            self.assertIn(source, text)
        self.assertIn("Current as of 2026-09-03", text)
        self.assertIn("community", text)


class HygieneTests(unittest.TestCase):
    def test_package_has_no_hooks_mcp_or_machine_specific_paths(self) -> None:
        files = [
            path
            for path in REPO_ROOT.rglob("*")
            if path.is_file()
            and ".git" not in path.relative_to(REPO_ROOT).parts
            and "__pycache__" not in path.relative_to(REPO_ROOT).parts
        ]
        relative = {path.relative_to(REPO_ROOT).as_posix() for path in files}
        self.assertFalse(any("hooks/" in path for path in relative))
        self.assertFalse(any(path.endswith(".mcp.json") for path in relative))

        machine_path = "/Users/" + "rocky243"
        unfinished = "TO" + "DO:"
        offenders: list[str] = []
        for path in files:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if machine_path in text or unfinished in text:
                offenders.append(path.relative_to(REPO_ROOT).as_posix())
        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
