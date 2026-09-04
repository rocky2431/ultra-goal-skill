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
PLUGIN_ROOT = REPO_ROOT / "plugins" / "ultra-goal"
SKILL_ROOT = PLUGIN_ROOT / "skills" / "ultra-goal"

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

        self.assertEqual("ultra-goal", plugin["name"])
        self.assertEqual(plugin["name"], entry["name"])
        self.assertEqual("./skills/", plugin["skills"])
        self.assertEqual("./plugins/ultra-goal", entry["source"]["path"])
        self.assertIn("name: ultra-goal", skill_text())
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
        """The real cap is the reference's, not one this project invented.

        `description` and `when_to_use` are truncated together at 1,536
        characters in the skill listing. A self-imposed 380 was a guess made
        before the reference was read; the deliberate budget below is well
        under the real limit and says which is which.
        """
        skill = skill_text()
        description = re.search(r'(?m)^description: "(.+)"$', skill)
        when = re.search(r'(?m)^when_to_use: "(.+)"$', skill)
        self.assertIsNotNone(description)
        self.assertIsNotNone(when, "trigger phrases belong in `when_to_use`")
        text = description.group(1)
        combined = len(text) + len(when.group(1))
        self.assertLessEqual(combined, 1536, "the documented listing cap")
        self.assertLessEqual(combined, 900, "and a deliberate budget under it")
        self.assertIn("not a design note", text)
        # The three shapes, named as they now are: a goal package is started by
        # this plugin's own command rather than pasted into a host's goal mode.
        for shape in ("goal package to start with /ultra-goal", "workflow script",
                      "cross-vendor delegation triad"):
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
            "who checks the checker?",
            "## Compile one artifact",
            "## Inspect what is running",
            "## Modify an existing loop",
            "## Validate, then offer to start it",
            "## Recognize the intent first",
            "run the status command before the first question",
            "That record is also the interview's progress",
            "Edit the affected row",
            "A loop whose anchor changed is a different loop",
            "## Three tiers of frozen",
            "**False consensus**",
            "Reviewers split by domain",
            "goal(<slug>) turn <N>:",
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

    def test_verification_asks_for_reviewer_and_critic(self) -> None:
        """Three roles beat a five-agent panel; the third role is why."""
        skill = skill_text()
        self.assertIn("who checks the checker?", skill)
        self.assertIn("audits the *review* rather than the code", skill)
        self.assertIn("references/adversarial-review.md", skill)
        ar = (SKILL_ROOT / "references" / "adversarial-review.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("arXiv 2608.18167", ar)
        self.assertIn("FROZEN for the whole inner loop", ar)
        self.assertIn("false consensus", ar)
        for cls in ("**agreement**", "**evidence-backed disagreement**",
                    "**concern-based disagreement**"):
            self.assertIn(cls, ar)
        self.assertIn("not with a plausible\nrebuttal", ar)
        self.assertIn("First pass", ar)
        self.assertIn("give them different underlying models", ar)
        # And the shape it replaced, named so it is not reintroduced.
        self.assertIn("## What this replaces", ar)
        self.assertIn("split delegation by **domain**", ar)

    def test_freeze_tiers_name_the_middle_one(self) -> None:
        skill = skill_text()
        for tier in ("**Frozen**", "**Firm**", "**Fluid**"):
            self.assertIn(tier, skill)
        self.assertIn("write the row in `decisions.md`", skill)
        # Which tier is enforced by what is the load-bearing distinction here:
        # one is measured, the other is asked for.
        self.assertIn("**Frozen is mechanically observed**", skill)
        self.assertIn("**Firm is enforced socially**", skill)

    def test_document_system_maps_a_spec_driven_harness(self) -> None:
        doc = (SKILL_ROOT / "references" / "document-system.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("If you also run a spec-driven development harness", doc)
        self.assertIn("### Why there is no task ledger", doc)
        self.assertIn("deliberately absent", doc)
        self.assertIn("The two compose in one direction", doc)

    def test_delegation_template_is_a_triad(self) -> None:
        text = (SKILL_ROOT / "assets" / "delegation-package.md").read_text(
            encoding="utf-8"
        )
        for section in ("## Reviewer", "## Critic", "## Convergence"):
            self.assertIn(section, text)
        self.assertNotIn("## Worker:", text)
        self.assertIn("different vendors on", text)
        self.assertIn("evidence-backed disagreement", text)
        self.assertIn("At most 5 inner rounds", text)
        # Targets must differ, and both must be registered.
        targets = re.findall(r"(?m)^- target: (\S+)$", text)
        self.assertEqual(2, len(targets))
        self.assertNotEqual(targets[0], targets[1])
        for target in targets:
            self.assertIn(target, va.known_targets()[0])

    def test_boundary_asks_for_three_refusals(self) -> None:
        """4D-ARE names three failures a specification must prevent; the interview
        asks about each rather than folding them into one 'boundary' question."""
        skill = skill_text()
        self.assertIn("three refusals, not one", skill)
        for refusal in ("**Scope**", "**Confidence**", "**Inference**"):
            self.assertIn(refusal, skill)
        self.assertIn("until it is reproduced", skill)
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        for refusal in ("**Scope.**", "**Confidence.**", "**Inference.**"):
            self.assertIn(refusal, goal)

    def test_lessons_are_reflections_with_a_cited_budget(self) -> None:
        skill = skill_text()
        self.assertIn("A lesson is a cause and a next action, not an event.", skill)
        self.assertIn("arXiv 2303.11366", skill)
        self.assertIn("At most 3", skill)
        self.assertIn("Twenty lessons is a log nobody reads", skill)
        primitives = (SKILL_ROOT / "references" / "loop-primitives.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## Lessons are reflections, not a log", primitives)
        self.assertIn("credit assignment problem", primitives)
        research = (SKILL_ROOT / "references" / "research-basis.md").read_text(
            encoding="utf-8"
        )
        for source in ("arxiv.org/abs/2303.11366", "arxiv.org/pdf/2601.04556",
                       "arxiv.org/abs/2305.04091"):
            self.assertIn(source, research)

    def test_unattended_goal_template_wires_the_carry_over(self) -> None:
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        self.assertIn("## Cadence", goal)
        self.assertIn("## Carry-over", goal)
        self.assertIn("### State", goal)
        self.assertIn("### Lessons", goal)
        self.assertIn("Read this before acting; rewrite it before finishing", goal)
        # The prompt the owner actually runs must carry the same instruction, or the
        # section never gets written.
        handoff = goal.split("## Handoff", 1)[1]
        self.assertIn("Read the Carry-over section", handoff)
        self.assertIn("Rewrite the Carry-over section", handoff)
        self.assertIn("### Next", goal)
        self.assertIn("Commit once per turn as `goal(weekly-dep-upgrade) turn", handoff)
        self.assertIn("Next gets the single objective", handoff)

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
            "artifacts_do_not_live_in_a_tool_directory",
            "host_capability_claim_gets_checked_not_assumed",
            "anchor_goes_into_the_goal_text_not_a_wrapper",
            "ceiling_must_be_in_the_goal_text",
            "no_scheduling_machinery_when_the_owner_starts_it_by_hand",
            "carry_over_survives_compaction_not_just_reruns",
            "boundary_is_three_refusals_not_one",
            "a_lesson_must_be_a_cause_and_a_next_action",
            "lessons_are_capped_at_three",
            "the_turn_number_is_said_out_loud",
            "an_unrunnable_anchor_is_unknown_not_failed",
            "the_target_level_divergence_stops_the_loop",
            "hook_pollution_is_answered_inside_the_hook",
            "the_gate_never_denies_twice_on_an_identical_result",
            "worker_transcripts_are_not_the_record",
            "post_tool_use_is_not_registered_yet",
            "domain_split_reviewers_become_a_triad",
            "false_consensus_is_named_when_two_agents_agree",
            "the_critic_audits_the_review_not_the_code",
            "reviewer_and_critic_need_different_models",
            "a_firm_threshold_change_gets_a_decisions_row",
            "a_loop_that_wants_a_task_ledger_should_have_been_a_plan",
        ):
            self.assertIn(required, names)

    def test_skill_is_host_neutral(self) -> None:
        skill = skill_text()
        self.assertIn("## Starting a run, on whichever host you are", skill)
        self.assertIn("You are the host.", skill)
        self.assertIn("requires a workflow runtime", skill)
        self.assertIn("do **not** emit `<slug>.workflow.js`", skill)
        # Artifacts are project assets, not one tool's private configuration.
        self.assertNotIn(".claude/workflows", skill)
        self.assertIn(".goals/", skill)
        # Activation scope must not name one host's commands either.
        # Host slash-commands belong in the goal-mode section and nowhere else.
        # Matched inside backticks so filenames like <slug>.goal.md do not count.
        head, tail = skill.split("## Starting a run, on whichever host you are", 1)
        tail = tail.split("## Compile one artifact", 1)[1]
        leaks = re.findall(r"`/(?:goal|loop|schedule)[` ]", head + tail)
        self.assertEqual([], leaks, f"host commands leaked: {leaks}")
        # This plugin's own command is not a host command and may appear anywhere.
        self.assertIn("/ultra-goal", skill)
        # Every measured host, Codex included - it was missed on the first pass.
        for host in ("Claude Code", "Codex", "Kimi", "zCode", "OpenCode"):
            self.assertIn(host, skill)

    def test_goal_mode_is_the_mechanism_and_the_anchor_is_the_evidence(self) -> None:
        """An earlier version claimed most hosts lacked goal mode. They have it."""
        skill = skill_text()
        self.assertIn("## Starting a run, on whichever host you are", skill)
        # Four hosts, each with its goal command named.
        for host in ("Claude Code", "Codex", "Kimi", "zCode", "OpenCode"):
            self.assertIn(host, skill)
        self.assertEqual(4, skill.count("`/goal <objective>`"))
        # Goal mode is a convenience now, not the mechanism: the gate is.
        self.assertIn("**That something is this\nSkill's own Stop hook**", skill)
        self.assertIn(
            "### The gate is the loop, so a host's goal mode is no longer needed", skill
        )
        self.assertIn("**`/ultra-goal:goal-run <slug>`**", skill)
        self.assertIn("cannot do the one that\nmatters", skill)
        self.assertIn("the only accepted evidence", skill)
        # A negative result must read as absence of evidence, not proof.
        self.assertIn("not proof of\nabsence", skill)
        self.assertIn("check your own host rather than trusting this table", skill)

    def test_skill_carries_no_external_scheduling_machinery(self) -> None:
        """Dropped in 0.6.0: the use case is a goal started by hand, not cron."""
        skill = skill_text()
        for gone in ("runner.sh", "crontab", "launchd", "systemd"):
            self.assertNotIn(gone, skill, gone)
        self.assertFalse(
            (SKILL_ROOT / "assets" / "goal-runner.sh").exists(),
            "the runner was removed as unrequested machinery",
        )

    def test_templates_and_references_are_host_neutral(self) -> None:
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        self.assertNotIn(".claude/workflows", goal)
        handoff = goal.split("## Handoff", 1)[1]
        # The pasteable goal line, with all three clauses that make it hold.
        self.assertIn("/goal ", handoff)
        self.assertIn("You have not met this goal until you have actually", handoff)
        self.assertIn("do not claim completion from reasoning about the code", handoff)
        self.assertIn("Stop after 6 turns even if unmet", handoff)
        # A1: the turn must be said out loud, or the ceiling is estimated by feel.
        self.assertIn("which `## Acceptance` lines this turn is for", handoff)
        # A3: all three refusals reach the pasted text, not just the document.
        self.assertIn("never application source or CI config", handoff)
        self.assertIn("do not call an upgrade safe without that output", handoff)
        self.assertIn("Do not conclude why something broke", handoff)
        # A4: carry-over is rewritten in two parts, lessons bounded.
        self.assertIn("Lessons gets at most 3 causal findings", handoff)
        # No longer routed through any host's goal mode: the gate is the loop, so
        # the artifact names this plugin's command and the paste fallback.
        self.assertIn("`/ultra-goal:goal-run weekly-dep-upgrade`", handoff)
        self.assertIn("arm the gate", handoff)
        self.assertIn("Where the plugin is absent, paste the text below", handoff)
        self.assertIn("> .goals/active", handoff)
        for gone in ("crontab", "runner.sh"):
            self.assertNotIn(gone, handoff)

        primitives = (SKILL_ROOT / "references" / "loop-primitives.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## Goal mode across hosts", primitives)
        self.assertIn("These four are shapes, not commands.", primitives)
        self.assertIn("The ceiling has to be in the text.", primitives)
        self.assertIn("compaction empties the context", primitives)

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
            self.assertIn(target, va.known_targets()[0])


class GateAndDocumentSystemTests(unittest.TestCase):
    def test_interview_asks_about_surface_and_divergence(self) -> None:
        skill = skill_text()
        self.assertIn("4. **Means**", skill)
        self.assertIn("8. **Read and write surface**", skill)
        self.assertIn("9. **Divergence handling**", skill)
        # The recommended default for divergence is the one rule no mechanism
        # can enforce, so it has to be stated plainly.
        self.assertIn(
            "the intent, the anchor, and the boundary always stop and report", skill
        )

    def test_the_graph_nodes_are_named_and_mapped(self) -> None:
        skill = skill_text()
        self.assertIn("## This is a graph, and here is where its nodes live", skill)
        for node in ("North Star", "Mechanical gate", "Adversarial review",
                     "Reflection", "Carried state"):
            self.assertIn(node, skill)
        for failure in ("Goodhart", "Blindness upward", "Conflict",
                        "Measurement decay", "Circularity"):
            self.assertIn(failure, skill)

    def test_the_gate_section_states_three_outcomes_and_the_escape(self) -> None:
        skill = skill_text()
        self.assertIn("## The gate: what the hooks do, and what they cost", skill)
        self.assertIn("**Three outcomes, not two.**", skill)
        self.assertIn("**Seven of the eight steps allow.**", skill)
        self.assertIn("**A moved goalpost allows on purpose.**", skill)
        self.assertIn("`rm .goals/active`", skill)
        self.assertIn("ULTRA_GOAL_HOOKS_DISABLED=1", skill)
        # PostToolUse's absence is a decision with a stated trigger to revisit.
        self.assertIn("`PostToolUse` is deliberately **not** registered", skill)

    def test_document_system_answers_owner_when_and_relationships(self) -> None:
        doc = (SKILL_ROOT / "references" / "document-system.md").read_text(
            encoding="utf-8"
        )
        # who writes it, when, and how mutable - the three questions it exists for
        for column in ("Who writes it", "Mutability", "In Git"):
            self.assertIn(column, doc)
        self.assertIn("frozen for the duration of a run", doc)
        self.assertIn("append-only, never edited", doc)
        self.assertIn("a slower loop owns the faster loop's target", doc)
        self.assertIn("a summary is a derived checkpoint, not a source of truth", doc)
        # the three-layer split for divergence
        self.assertIn("### Lessons", doc)
        self.assertIn("stop and report", doc)
        # multi-worker storage, and what is thrown away
        self.assertIn(".goals/.work/", doc)
        self.assertIn("gitignored", doc)
        self.assertIn("Workers never share a transcript", doc)
        self.assertIn("The orchestrator runs the anchor, not the workers", doc)

    def test_every_relative_link_still_resolves(self) -> None:
        missing = [
            target
            for target in re.findall(r"\]\((?!https?:)([^)#]+)\)", skill_text())
            if not (SKILL_ROOT / target).exists()
        ]
        self.assertEqual([], missing)


class EvalTests(unittest.TestCase):
    def test_behavior_evals_cover_the_refusals(self) -> None:
        data = json.loads((SKILL_ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
        names = {case["name"] for case in data["evals"]}
        self.assertEqual(
            ["no_skill", "agent-harness-design", "ultra-goal"],
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
    def test_package_ships_hooks_but_no_mcp_or_machine_specific_paths(self) -> None:
        """Reversal recorded in 0.8.0: the package now ships hooks.

        Through 0.7.0 this asserted the package had none, on the reasoning that
        a hook is a global effect an installed Skill should not impose. What
        changed the decision is that gating the anchor mechanically is the whole
        point, and an opt-in flag would have meant a Skill that emits "the
        anchor is the only accepted evidence" while nothing executes it - a
        silent downgrade of evidence coverage, which is worse than the pollution
        it avoids. The pollution is instead handled inside the hooks: no
        `.goals/active`, no work. That early exit is pinned by
        tests/test_goal_hooks.py, which is now the load-bearing test.
        """
        # The scan covers what ships (the plugin tree, the installer, tests,
        # README) - not docs/wip/, the working-notes directory whose whole job
        # is citing absolute local paths to evidence. The mission envelope
        # itself carries two such paths by design, and red-ing the suite on
        # the owner's own notes guards nothing that installs anywhere.
        files = [
            path
            for path in REPO_ROOT.rglob("*")
            if path.is_file()
            and ".git" not in path.relative_to(REPO_ROOT).parts
            and "__pycache__" not in path.relative_to(REPO_ROOT).parts
            and path.relative_to(REPO_ROOT).parts[:2] != ("docs", "wip")
        ]
        relative = {path.relative_to(REPO_ROOT).as_posix() for path in files}
        self.assertFalse(any(path.endswith(".mcp.json") for path in relative))

        # Every shipped hook must route through the shared early exit.
        scripts = SKILL_ROOT / "scripts"
        hook_scripts = sorted(p.name for p in scripts.glob("goal_*.py"))
        self.assertEqual(
            ["goal_hooks.py", "goal_pre_compact.py", "goal_session_start.py",
             "goal_stop.py", "goal_tool_failure.py"],
            hook_scripts,
        )
        for name in hook_scripts:
            if name == "goal_hooks.py":
                continue
            source = (scripts / name).read_text(encoding="utf-8")
            self.assertIn("run_hook(", source, name)

        manifest = json.loads(
            (PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            ["Stop", "SessionStart", "PreCompact", "PostToolUseFailure"],
            list(manifest["hooks"]),
        )
        # PostToolUseFailure earns its place: it fires only on a *failed* tool
        # call, so its cost does not scale with tool use the way PostToolUse
        # would - and it is the only host-observed view of a failed delegation.
        self.assertIn("PostToolUseFailure", manifest["description"] or "")
        # PostToolUse is deliberately absent: it fires once per tool call, so its
        # cost is a Python start per call, and its value duplicates SessionStart
        # injection plus the goal text's own instruction to read carry-over.
        self.assertNotIn("PostToolUse", manifest["hooks"])
        self.assertNotIn("UserPromptSubmit", manifest["hooks"])
        for groups in manifest["hooks"].values():
            for group in groups:
                for entry in group["hooks"]:
                    self.assertIn("commandWindows", entry)

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


class ZeroTrustTests(unittest.TestCase):
    """Wide latitude and zero trust in self-report are one decision.

    These pin the parts that are easy to quietly overstate: which side of the
    claim/measurement line each file sits on, and what the controls do not
    prove.
    """

    def test_skill_separates_claims_from_measurements(self) -> None:
        skill = skill_text()
        self.assertIn("### Wide latitude, zero trust in self-report", skill)
        self.assertIn("| the run | the artifact", skill)
        self.assertIn("| the hooks | `<slug>.events.jsonl`", skill)
        # The honest limit has to be in SKILL.md, not only in the reference.
        self.assertIn("Making a moved goalpost **visible** is the achievable property", skill)

    def test_the_audit_command_is_documented_and_reads_only(self) -> None:
        skill = skill_text()
        self.assertIn("validate_artifact.py .goals --audit", skill)
        self.assertIn("It reads Git history and the event log; it runs nothing.", skill)

    def test_zero_trust_reference_states_the_criterion_and_the_limits(self) -> None:
        doc = (SKILL_ROOT / "references" / "zero-trust.md").read_text(encoding="utf-8")
        self.assertIn(
            "**Mechanize a check only when the quantity measured is the quantity "
            "judged.**",
            doc,
        )
        # The rows that answer "no" are the whole point of having a criterion.
        for observation in ("a timeout", "a similarity score", "a line-count ceiling"):
            self.assertIn(observation, doc)
        self.assertIn("**Visible, not impossible**", doc)
        self.assertIn("## Deliberately not mechanized", doc)
        # Input isolation is a different control from vendor choice, and the
        # reference has to say why or the two get conflated.
        self.assertIn("Different vendors buy **different blind spots**", doc)

    def test_new_refusals_name_the_contagion_and_the_missing_receipt(self) -> None:
        skill = skill_text()
        self.assertIn("**A verdict with no receipt**", skill)
        self.assertIn("**The reviewer gets the author's argument**", skill)

    def test_role_inputs_are_specified_where_they_can_be_checked(self) -> None:
        ar = (SKILL_ROOT / "references" / "adversarial-review.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## What each role is given", ar)
        self.assertIn("M's explanation, M's confidence", ar)
        # And it admits where the check is not mechanical.
        self.assertIn("the rule is stated\nrather than checked", ar)
        delegation = (SKILL_ROOT / "assets" / "delegation-package.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(2, delegation.count("- inputs:"))

    def test_means_and_next_are_nodes_in_the_graph(self) -> None:
        skill = skill_text()
        self.assertIn("| What may be given up, and what may not | `## Means` |", skill)
        self.assertIn("| Re-aim | `### Next` |", skill)
        self.assertIn("Nine clauses, each closing one hole:", skill)

    def test_document_system_names_who_authors_which_side(self) -> None:
        doc = (SKILL_ROOT / "references" / "document-system.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## The one distinction that decides who writes what", doc)
        self.assertIn("**claims**", doc)
        self.assertIn("**measurements**", doc)
        self.assertIn("Nothing here auto-resolves a divergence.", doc)

    def test_research_basis_cites_the_review_protocol_and_the_framework(self) -> None:
        text = (SKILL_ROOT / "references" / "research-basis.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("arxiv.org/html/2608.18167", text)
        self.assertIn(
            "antigravity.google/blog/teamwork-when-ai-becomes-a-research-partner", text
        )
        self.assertIn(
            "A pattern is a specification rather than an executable program.", text
        )


class ActivationScopeTests(unittest.TestCase):
    """The intent most likely to pull this Skill in wrongly is a goal being run.

    A pasted goal line is dense with the Skill's own vocabulary because the Skill
    wrote it, so the exclusion has to be in the description - which is what the
    host matches on - and not only in the body, which is read after the Skill has
    already loaded.
    """

    def test_when_to_use_carries_the_triggers_and_the_exclusion(self) -> None:
        """The reference calls `when_to_use` the home for trigger phrases."""
        front = skill_text().split("---")[1]
        for trigger in ("make an agent keep doing this", "keep going until"):
            self.assertIn(trigger, front, trigger)
        self.assertIn("Not when a goal is already running", front)

    def test_the_intent_table_has_the_executing_row(self) -> None:
        skill = skill_text()
        self.assertIn("| **Executing** |", skill)
        self.assertIn("**Do not activate.** Do the work the goal asks for", skill)

    def test_the_ambiguous_case_is_resolved_on_the_request_not_the_state(self) -> None:
        skill = skill_text()
        self.assertIn("### The one intent that is not a request for this Skill", skill)
        # Same project state, opposite answers - so the tie-break has to be stated.
        self.assertIn('"Make it stop after three turns" while a goal is active is', skill)
        self.assertIn("**Executing** — the run", skill)
        # And the asymmetry that decides which way to err.
        self.assertIn("A missed activation costs one", skill)

    def test_trigger_evals_cover_the_execution_collision_both_ways(self) -> None:
        evals = json.loads(
            (SKILL_ROOT / "evals" / "trigger-evals.json").read_text(encoding="utf-8")
        )["evals"]
        by_name = {case["name"]: case for case in evals}
        pasted = by_name["negative_pasted_goal_line_is_execution_not_design"]
        self.assertEqual([], pasted["expected_skills"])
        self.assertIn("/goal ", pasted["prompt"])
        self.assertEqual(
            [], by_name["negative_in_run_work_request_with_a_goal_active"][
                "expected_skills"
            ]
        )
        # The mirror case must stay positive, or the guard would silence Modify too.
        self.assertEqual(
            ["ultra-goal"],
            by_name["positive_modify_while_a_goal_is_active"]["expected_skills"],
        )


class ChallengeChannelTests(unittest.TestCase):
    """The only channel through which execution reaches the goal itself.

    `### Lessons` carries method forward and `### Next` re-aims within the
    terms; neither can say the terms are wrong. Before this existed, "the goal
    is wrong" was the one outcome that wrote nothing down.
    """

    def test_the_skill_names_the_missing_edge(self) -> None:
        skill = skill_text()
        self.assertIn("## The one thing the goal can learn from", skill)
        self.assertIn(
            "| **Written by** | the run, and only the run", skill
        )
        # Optional on purpose: a mandatory objection is an invented one.
        self.assertIn("**Optional on purpose.**", skill)
        self.assertIn(
            "| The run's objection to its own terms | `## Challenges from the run`", skill
        )

    def test_divergence_reporting_has_somewhere_to_land(self) -> None:
        skill = skill_text()
        self.assertIn('**And "report" needs somewhere to land.**', skill)

    def test_modify_reads_the_objection_first(self) -> None:
        skill = skill_text()
        self.assertIn(
            "**Read `## Challenges from the run` before anything else in that file.**",
            skill,
        )

    def test_the_goal_text_makes_the_run_the_run(self) -> None:
        skill = skill_text()
        self.assertIn("You are the run for <slug>, not its", skill)
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        handoff = goal.split("## Handoff", 1)[1]
        self.assertIn("not its designer", handoff)
        self.assertIn("## Challenges from the run", handoff)

    def test_a_miss_is_paid_for_with_the_sentence(self) -> None:
        self.assertIn("actually spend the\nsentence.**", skill_text())

    def test_the_template_ships_a_worked_challenge(self) -> None:
        record = (SKILL_ROOT / "assets" / "decisions-record.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## Challenges from the run", record)
        for column in (
            "Term challenged", "What the run hit", "What would settle it"
        ):
            self.assertIn(column, record)
        self.assertIn("an empty section should be deleted, not filled.", record)


class SweepFindingsTests(unittest.TestCase):
    """The five changes the theory sweep argued for, pinned.

    Each is here because an external source said the design was missing it, so
    each assertion doubles as the record of why the text says what it says.
    """

    def test_the_anchor_must_cross_the_whole_path(self) -> None:
        skill = skill_text()
        self.assertIn("**And it has to cross the whole path.**", skill)
        self.assertIn("| **An anchor that only tests the code** |", skill)
        anti = (SKILL_ROOT / "references" / "anti-patterns.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## An anchor that only tests the code", anti)
        self.assertIn("drives the running thing", anti)

    def test_context_anxiety_is_named_not_merely_survived(self) -> None:
        skill = skill_text()
        self.assertIn("**Wrapping up because the context feels full**", skill)
        self.assertIn("Named *context anxiety*", skill)
        anti = (SKILL_ROOT / "references" / "anti-patterns.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## Context anxiety", anti)
        # The honest half: if the model no longer does this, delete the defence.
        self.assertIn("exactly the kind of mechanism to delete rather than keep", anti)

    def test_acceptance_is_required_only_where_it_earns_its_keep(self) -> None:
        skill = skill_text()
        self.assertIn("**If it will be started more than once, enumerate it.**", skill)
        self.assertIn("**Unordered, never numbered**", skill)
        self.assertIn(
            "| The stop condition, enumerated | `## Acceptance` |", skill
        )

    def test_the_ledger_boundary_is_written_hard(self) -> None:
        """The section most easily mistaken for the thing this Skill refuses."""
        doc = (SKILL_ROOT / "references" / "document-system.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## `## Acceptance` is not a task ledger, and here is the line", doc)
        self.assertIn(
            "**`plan.md` and a dependency-ordered\n`tasks.json` are still refused.**", doc
        )
        self.assertIn("the stop condition written out longhand", doc)

    def test_the_anchor_budget_belongs_to_the_artifact(self) -> None:
        skill = skill_text()
        self.assertIn("write `budget: N minutes` under `## Anchor`", skill)
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        self.assertIn("budget: 2 minutes", goal)

    def test_worker_outcomes_include_the_two_blocked_states(self) -> None:
        ar = (SKILL_ROOT / "references" / "adversarial-review.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## When a worker cannot proceed", ar)
        for outcome in ("completed", "failed", "input-required", "rejected"):
            self.assertIn(f"**{outcome}**", ar)
        self.assertIn(
            "**Silence is `input-required`, never `completed`.**", ar
        )
        delegation = (SKILL_ROOT / "assets" / "delegation-package.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Silence is none of these.", delegation)

    def test_the_hook_timeout_coupling_is_stated_once(self) -> None:
        """Two numbers with no stated relationship is how a gate acquires a
        ceiling nobody chose: the manifest's timeout bounds every budget in the
        gate, so the constant is pinned against the manifest here."""
        import json as _json
        manifest = _json.loads(
            (PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8")
        )
        declared = manifest["hooks"]["Stop"][0]["hooks"][0]["timeout"]
        hooks = (SKILL_ROOT / "scripts" / "goal_hooks.py").read_text(encoding="utf-8")
        self.assertIn(f"HOOK_TIMEOUT_SECONDS = {declared}", hooks)
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        import goal_hooks
        self.assertLess(
            goal_hooks.ANCHOR_BUDGET_CEILING,
            goal_hooks.HOOK_TIMEOUT_SECONDS,
            "the anchor must finish before the host kills the hook",
        )


class HostManifestTests(unittest.TestCase):
    """One plugin, four hosts, and every format measured rather than guessed.

    Ground truth on the machine this was written on: six installed Claude Code
    marketplaces all use `.claude-plugin/marketplace.json`; zcode-cua ships
    `.zcode-plugin/plugin.json` with a string `skills` field; Ultra Builder Pro's
    Kimi manifest is `kimi.plugin.json` with a flat hook array; and the Codex
    binary carries the literal fallback chain
    `.codex-plugin/plugin.json` -> `.claude-plugin/plugin.json` ->
    `.cursor-plugin/plugin.json`, which is why one Claude-format manifest covers
    three of the four.
    """

    VERSIONED = (
        (".claude-plugin/marketplace.json", ("metadata", "version")),
        (".agents/plugins/marketplace.json", ("metadata", "version")),
        ("plugins/ultra-goal/.claude-plugin/plugin.json", ("version",)),
        ("plugins/ultra-goal/.codex-plugin/plugin.json", ("version",)),
        ("plugins/ultra-goal/.zcode-plugin/plugin.json", ("version",)),
        ("plugins/ultra-goal/kimi.plugin.json", ("version",)),
    )

    def load(self, relative: str) -> dict:
        return json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))

    def test_claude_code_marketplace_is_where_claude_code_looks(self) -> None:
        market = self.load(".claude-plugin/marketplace.json")
        self.assertEqual("ultra-goal", market["name"])
        entry = market["plugins"][0]
        self.assertEqual("ultra-goal", entry["name"])
        self.assertEqual("./plugins/ultra-goal", entry["source"])
        self.assertTrue((REPO_ROOT / entry["source"]).is_dir())

    def test_every_host_manifest_exists_and_names_the_same_plugin(self) -> None:
        """A marketplace carries its own name, so the plugin is under
        `plugins[0]`; a plugin manifest names itself at the top level."""
        for relative, _ in self.VERSIONED:
            with self.subTest(manifest=relative):
                node = self.load(relative)
                name = node["plugins"][0]["name"] if "plugins" in node else node["name"]
                self.assertEqual("ultra-goal", name)

    def test_every_manifest_declares_the_same_version_as_the_skill(self) -> None:
        version = re.search(
            r'(?m)^\s*version: "([\d.]+)"$', skill_text()
        ).group(1)
        for relative, keys in self.VERSIONED:
            with self.subTest(manifest=relative):
                node = self.load(relative)
                for key in keys:
                    node = node[key]
                self.assertEqual(version, node)
        installer = (REPO_ROOT / "scripts" / "install_user.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(f'VERSION = "{version}"', installer)

    def test_zcode_and_kimi_declare_skills_in_their_own_shapes(self) -> None:
        """A string for zCode, an array for Kimi. Measured, not guessed."""
        self.assertEqual("skills", self.load(
            "plugins/ultra-goal/.zcode-plugin/plugin.json")["skills"])
        self.assertEqual(["./skills"], self.load(
            "plugins/ultra-goal/kimi.plugin.json")["skills"])

    def test_kimi_hooks_name_the_same_events_as_the_claude_manifest(self) -> None:
        hooks = self.load("plugins/ultra-goal/kimi.plugin.json")["hooks"]
        self.assertEqual(
            ["Stop", "SessionStart", "PreCompact", "PostToolUseFailure"],
            [h["event"] for h in hooks],
        )
        manifest = json.loads(
            (PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8")
        )
        self.assertEqual(list(manifest["hooks"]), [h["event"] for h in hooks])

    def test_claude_code_hooks_use_the_variable_claude_code_substitutes(self) -> None:
        """`$PLUGIN_ROOT` is not the name Claude Code expands, so a plugin
        install would have pointed every hook at nothing."""
        text = (PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8")
        self.assertIn("${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}", text)
        self.assertNotIn('"$PLUGIN_ROOT/', text)
        self.assertIn("%CLAUDE_PLUGIN_ROOT%", text)


class RolesByStageTests(unittest.TestCase):
    """Roles are settled per stage, and most stages are not a choice.

    An earlier version offered four "modes" side by side - same-model
    subagents, cross-vendor, parallel triads, a graph - which flattened three
    orthogonal axes into one column. The owner caught it. These pin the repair
    so the menu cannot come back.
    """

    def reference(self) -> str:
        return (SKILL_ROOT / "references" / "agent-modes.md").read_text(encoding="utf-8")

    def test_the_interview_discovers_before_it_asks(self) -> None:
        skill = skill_text()
        self.assertIn("run `agent-delegate list --json` yourself", skill)
        self.assertIn("which agents exist is a fact", skill)

    def test_every_stage_is_the_owners_to_assign(self) -> None:
        """Who does the work is a material trade-off, so it is theirs.

        An earlier version wrote "No" against three rows, which turned a strong
        recommendation into a rule the Skill had no standing to make.
        """
        skill = skill_text()
        self.assertIn("**Every stage is the owner's to assign**", skill)
        self.assertIn("| Stage | Recommend | Why, and what would change it |", skill)
        # Only two rows are constraints, and each says which kind it is.
        self.assertEqual(3, skill.count("**Constraint"))
        self.assertIn("**But scale flips it**", skill)
        # And the shape that flipped it is described rather than hinted at.
        self.assertIn("two cross-vendor executors alternating build and review", skill)

    def test_the_judge_is_recommended_to_judge_blind(self) -> None:
        skill = skill_text()
        self.assertIn("**Then who judges, and whether they judge blind.**", skill)
        self.assertIn("been persuaded before it decided", skill)
        self.assertIn("`<slug>.judge-review.md`", skill)
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        self.assertIn("- **judge**: this session, **blind first**", goal)

    def test_the_stop_hook_reminds_only_what_may_change(self) -> None:
        skill = skill_text()
        self.assertIn(
            "**What it reminds you of is exactly what you may change.**", skill
        )
        self.assertIn('`decision: "block"`', skill)
        self.assertIn("a frozen section it does mention is an invitation to edit", skill)

    def test_an_unbounded_ceiling_is_declarable(self) -> None:
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        self.assertIn("ceiling: 6", goal)
        self.assertIn("Write `ceiling: none` instead", goal)
        self.assertIn("a number you did not choose", goal)

    def test_the_two_review_axes_are_separated(self) -> None:
        skill, doc = skill_text(), self.reference()
        self.assertIn(
            "**The only genuine choice in review is model independence**", skill
        )
        self.assertIn("| Axis | The disease | The control | Cost |", doc)
        self.assertIn("Contagion of the author's argument.", doc)
        self.assertIn("Shared blind spots.", doc)
        self.assertIn(
            "Context isolation is **not optional**. Model independence is the choice.", doc
        )

    def test_parameters_are_not_presented_as_peer_choices(self) -> None:
        self.assertIn("## Parameters, not peer choices", self.reference())
        self.assertIn("are parameters of that choice, not peers of", skill_text())

    def test_loop_versus_graph_is_kept_off_this_page(self) -> None:
        """Putting it in a list of role options was the clearest symptom."""
        doc = self.reference()
        self.assertIn("## What is *not* on this page", doc)
        self.assertIn("**Loop versus graph is not a role question.**", doc)

    def test_who_writes_the_code_is_a_recommendation_with_both_sides(self) -> None:
        """It is the owner's call, so the page argues rather than rules.

        And it carries the counterexample: a production run on this machine
        does the opposite - lead holds the loop, writes no code, two
        cross-vendor executors alternate build and review rounds - and works.
        """
        doc = self.reference()
        self.assertIn("## Who writes the code: a recommendation, and the scale", doc)
        self.assertIn("**This is the owner's call.**", doc)
        self.assertIn("no standing to take", doc)
        self.assertIn("**The main agent writes code, edits", doc)
        self.assertIn("**At scale it flips, and there is a working counterexample.**", doc)
        self.assertIn("role rotation rather than", doc)
        self.assertIn("**Test-first is not a choice either.**", doc)

    def test_judging_blind_closes_the_referee_hole(self) -> None:
        doc = self.reference()
        self.assertIn("## Judging blind", doc)
        self.assertIn("records its verdict before reading", doc)
        # And why "the anchor decides" was not already enough.
        self.assertIn("persuaded before it decided", doc)
        self.assertIn("the exit code does not settle which findings mattered", doc)

    def test_the_two_gate_channels_are_documented(self) -> None:
        doc = (SKILL_ROOT / "references" / "document-system.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## What the gate says, and to whom", doc)
        self.assertIn("**what the gate reminds you of should\nbe exactly what you may change.**", doc)
        # The corrected belief is recorded where it can be read later.
        self.assertIn("which is the **PreToolUse** shape", doc)
        self.assertIn(
            "a claim until something outside the emitter agrees with it", doc
        )

    def test_degradation_says_which_half_it_actually_has(self) -> None:
        """An earlier draft promised a mechanical check that cannot exist.

        It said a degraded round would appear in the event log and be surfaced
        by `--audit`. Nothing could write that event: the only thing able to
        observe a failed delegation is the run that attempted it, and a run's
        statements are claims - `events.jsonl` is hook-written precisely so it
        is not. The finding and the constant are gone; the honest weaker
        version is documented in their place.
        """
        doc = self.reference()
        self.assertIn("## Declared degradation", doc)
        self.assertIn("| who to fall back to | the **owner**, at design time", doc)
        self.assertIn("a **claim**, not evidence", doc)
        self.assertIn("declared and reported**, not measured", doc)
        # The reason a fake check is worse than no check, stated.
        self.assertIn("because it reads as coverage", doc)
        self.assertIn(
            "a review that cannot happen is a missing review, not a red anchor", doc
        )

    def test_degradation_is_written_by_a_hook_and_read_by_the_audit(self) -> None:
        """Deleted once for the right reason and the wrong fact.

        The old implementation had the run write `role_unavailable`, putting a
        claim inside the evidence file, so it went. The reasoning attached to
        the deletion - that only the run can observe a failed delegation - was
        wrong: the hooks reference documents `PostToolUseFailure`, which is a
        host-observed fact about the invocation. So the finding is back, and
        this pins that the writer is a hook and never the run.
        """
        writer = (SKILL_ROOT / "scripts" / "goal_tool_failure.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"event": "role_unavailable"', writer)
        self.assertIn("PostToolUseFailure", writer)
        # And it writes a fact, not a judgement about what the failure meant.
        self.assertIn("those are judgements, and this writes facts", writer)
        audit = (SKILL_ROOT / "scripts" / "validate_artifact.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("ROUND_DEGRADED", audit)
        self.assertIn("host-observed evidence rather than the", audit)

    def test_the_three_roles_ship_as_forked_skills(self) -> None:
        """Isolation as a property of the file, not of the call site."""
        for name, writes in (("design-critic", False), ("review", True),
                             ("critic", True)):
            with self.subTest(skill=name):
                text = (PLUGIN_ROOT / "skills" / name / "SKILL.md").read_text(
                    encoding="utf-8"
                )
                self.assertIn("context: fork", text)
                self.assertIn("background: false", text)
                self.assertIn("must not seek", text) if name != "design-critic" \
                    else self.assertIn("never saw the interview", text)
                self.assertEqual(writes, "Write" in text.split("---")[1])
        skill = skill_text()
        for command in ("/ultra-goal:design-critic <slug>", "/ultra-goal:review <slug>",
                        "/ultra-goal:critic <slug>"):
            self.assertIn(command, skill)
        self.assertIn("**the fork never sees\n   this conversation**", skill)

    def test_the_run_is_asked_to_say_it_out_loud(self) -> None:
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        self.assertIn("could not be reached, say so in the report", goal)
        # And research finally has a per-turn slot rather than only a role row.
        self.assertIn("what you need to find out before touching", goal)

    def test_the_shipped_goal_declares_roles_and_fallbacks(self) -> None:
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        self.assertIn("## Roles", goal)
        for role in ("**lead**", "**research**", "**design critic**", "**carry out**",
                     "**anchor**", "**reviewer**", "**critic**"):
            self.assertIn(role, goal)
        self.assertIn("**Model independence is deliberately not bought here.**", goal)
        self.assertIn("**Review runs at proposed completion**", goal)

    def test_the_plugin_ships_the_command_that_arms_the_gate(self) -> None:
        command = (PLUGIN_ROOT / "commands" / "goal-run.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("> .goals/active", command)
        self.assertIn("validate_artifact.py", command)
        self.assertIn("You are the run, not its designer.", command)
        self.assertIn("rm .goals/active", command)
        for manifest in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json",
                         "kimi.plugin.json"):
            with self.subTest(manifest=manifest):
                declared = json.loads(
                    (PLUGIN_ROOT / manifest).read_text(encoding="utf-8")
                )["commands"]
                self.assertEqual(["./commands/goal-run.md"], declared)


class DecisionAuthorContractTests(unittest.TestCase):
    """`Who` exists because a run wrote parentheses instead."""

    def test_the_skill_explains_the_fourth_column(self) -> None:
        skill = skill_text()
        self.assertIn(
            "**The fourth column is `Who`, and it holds `owner` or `agent`.**", skill
        )
        self.assertIn("| Always | `<slug>.decisions.md` — Decision / Rejected / Why / Who", skill)
        # An agent-authored row is legitimate; leaving it unmarked is not.
        self.assertIn("What is not\nlegitimate is leaving it unmarked.", skill)

    def test_the_template_ships_both_kinds_of_row(self) -> None:
        record = (SKILL_ROOT / "assets" / "decisions-record.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("| Decision | Rejected | Why | Who |", record)
        self.assertIn("| owner |", record)
        self.assertIn("| agent |", record)


if __name__ == "__main__":
    unittest.main()


class ReferenceFirstTests(unittest.TestCase):
    """Definitions come from the vendor's reference, not from examples.

    Three wrong answers in this project came from the three cheaper sources:
    an engineering blog read as a verdict on hook events the reference defines
    differently, an abbreviated schema printed by a validator read as the whole
    contract, and skill frontmatter reconstructed from installed plugins while
    the reference documented fields none of them used.
    """

    def test_the_interview_protocol_carries_the_rule(self) -> None:
        skill = skill_text()
        self.assertIn(
            "**Definitions come from the vendor's reference documentation.**", skill
        )
        self.assertIn(
            "**An example shows one thing\n  that works; a reference says what is "
            "allowed.**",
            skill,
        )

    def test_the_documented_fork_mechanism_is_named(self) -> None:
        doc = (SKILL_ROOT / "references" / "agent-modes.md").read_text(encoding="utf-8")
        self.assertIn("## How to actually run a fresh-context role", doc)
        self.assertIn("context: fork", doc)
        self.assertIn("agent: Explore", doc)
        # And why it is better than arranging isolation at the call site.
        self.assertIn("declared property of the file", doc)

    def test_the_gate_records_which_sources_disagreed(self) -> None:
        """A conflict between two authoritative sources is worth keeping."""
        gate = (SKILL_ROOT / "scripts" / "goal_stop.py").read_text(encoding="utf-8")
        self.assertIn("Two authoritative sources disagree", gate)
        self.assertIn("official hooks reference lists", gate)
        self.assertIn("running binary's own validator", gate)
        self.assertIn("satisfying both costs a few bytes", gate)

    def test_session_start_covers_every_documented_source(self) -> None:
        """`fork` was missing, so a forked session got no injection at all."""
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        import goal_session_start as ss

        self.assertEqual(
            {"startup", "resume", "clear", "compact", "fork"}, set(ss.SOURCES)
        )


class ApertureTests(unittest.TestCase):
    """What a user sees in the `/` menu, and what only the run may call.

    The three roles are internal to the graph: a user invoking `/critic` by hand
    gets a fork with no frozen diff to audit. The reference documents
    `user-invocable: false` for exactly this - "background knowledge users
    shouldn't invoke directly" - and hiding them also drops the bare aliases
    (`/review`, `/critic`), which a user-scope install would otherwise squat in
    every project on the machine.
    """

    INTERNAL_ROLES = ("review", "critic", "design-critic")

    def test_every_role_is_hidden_from_the_menu(self) -> None:
        for role in self.INTERNAL_ROLES:
            with self.subTest(role=role):
                front = (PLUGIN_ROOT / "skills" / role / "SKILL.md").read_text(
                    encoding="utf-8"
                )
                self.assertIn("user-invocable: false", front)

    def test_the_owner_facing_skill_stays_invocable(self) -> None:
        """Hiding this one would leave no way in at all."""
        self.assertNotIn("user-invocable:", skill_text())

    def test_no_two_components_claim_one_command_name(self) -> None:
        """A command file and a skill wanting `/ultra-goal:ultra-goal` means one
        of them silently shadows the other, and which one is not ours to decide.
        """
        claimed: dict[str, str] = {}
        for skill in sorted((PLUGIN_ROOT / "skills").iterdir()):
            if not (skill / "SKILL.md").is_file():
                continue
            text = (skill / "SKILL.md").read_text(encoding="utf-8")
            match = re.search(r"(?m)^name:\s*(\S+)\s*$", text)
            name = match.group(1) if match else skill.name
            claimed.setdefault(name, f"skills/{skill.name}/SKILL.md")
        for command in sorted((PLUGIN_ROOT / "commands").glob("*.md")):
            # `name` is ignored in a command file: the basename is the command.
            self.assertNotIn(
                command.stem,
                claimed,
                f"commands/{command.name} collides with {claimed.get(command.stem)}",
            )
            claimed[command.stem] = f"commands/{command.name}"

    def test_the_arming_command_is_brand_prefixed(self) -> None:
        """The bare alias lands in the user's global menu, so it cannot be a
        generic word like `run`."""
        commands = sorted(p.stem for p in (PLUGIN_ROOT / "commands").glob("*.md"))
        self.assertEqual(["goal-run"], commands)


class ChainedHandoffTests(unittest.TestCase):
    """Two skills, one door: the goal skill offers, then invokes the run.

    Keeping the run's manual in its own file is what stops a running turn from
    reading the interview as still open. Making the owner type the second
    command is a different thing, and it buys nothing - so the skill asks and
    invokes it, the continuation pattern the owner's earlier harness used.
    """

    def test_the_offer_names_the_command_it_would_invoke(self) -> None:
        skill = skill_text()
        self.assertIn("**Start the run now?**", skill)
        self.assertIn("`/ultra-goal:goal-run <slug>`", skill)

    def test_the_offer_has_three_answers(self) -> None:
        """Yes-or-no folds a changed mind into not-now."""
        skill = skill_text()
        for answer in ("**start it**", "**not yet**", "**change something first**"):
            with self.subTest(answer=answer):
                self.assertIn(answer, skill)

    def test_arming_still_needs_the_owner_to_say_so(self) -> None:
        """Chaining removes a keystroke, not the consent."""
        skill = skill_text()
        self.assertIn("never arm\nwithout asking", skill)
        self.assertIn("never read silence or an unrelated reply as consent", skill)

    def test_the_handoff_supersedes_the_interview_manual(self) -> None:
        """The host keeps this Skill in context after the handoff, so the pull to
        reopen frozen terms outlives the moment of handing off."""
        skill = skill_text()
        self.assertIn(
            "**When they say start it, this manual stops applying to you.**", skill
        )
        self.assertIn("The host keeps this Skill's content in the conversation", skill)

    def test_the_handoff_does_not_send_the_owner_to_clear(self) -> None:
        """A context reset at the handoff is the anti-pattern this project's own
        reference names: it discards the interview - the richest context turn 1
        will ever have - to chase a clean window that a fresh session does not
        have either.
        """
        skill = skill_text()
        self.assertIn("**Do not send them to clear the context first.**", skill)
        self.assertIn("a clean context is not reachable anyway", skill)
        self.assertNotIn("/clear", skill)

    def test_the_handoff_names_what_actually_holds_the_line(self) -> None:
        """Replacing a mechanism with a plea would be the weaker fix, so the
        paragraph names the three defences that already exist instead."""
        skill = skill_text()
        self.assertIn("not a\ncleaner window but three things", skill)
        self.assertIn("`frozen_digest()` is written and\ncompared by machine", skill)
        self.assertIn("`## Challenges from the run`", skill)

    def test_the_shapes_with_nothing_to_arm_are_offered_too(self) -> None:
        self.assertIn("The other two shapes have nothing to arm", skill_text())

class ContextResetTests(unittest.TestCase):
    """The reset this project recommended, and then removed.

    Worth a test because the reasoning is the reusable part: a window is worth
    dropping when what is in it is wrong, not when it is large.
    """

    def test_the_reversal_is_recorded_where_the_rule_lives(self) -> None:
        doc = (
            SKILL_ROOT / "references" / "anti-patterns.md"
        ).read_text(encoding="utf-8")
        self.assertIn("**And then this Skill recommended a reset anyway.**", doc)
        self.assertIn("A clean context is not reachable.", doc)
        self.assertIn(
            "what is in this window that is **wrong**, not what is in it\nthat is "
            "**large**",
            doc,
        )

class AuditFixTests(unittest.TestCase):
    """The findings from the 2026-09-04 audit against the vendor references.

    Each test names the way the thing failed, because a fixed defect with no
    record of its shape is one that comes back under a different name.
    """

    def _hooks(self) -> dict:
        return json.loads(
            (PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8")
        )["hooks"]

    def test_session_start_registers_every_source_the_script_accepts(self) -> None:
        """The script gained `fork`; the manifest's matcher did not, so a forked
        session got no injection at all - a half-landed fix with no test across
        the two files that had to agree."""
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        import goal_session_start as ss

        matcher = self._hooks()["SessionStart"][0]["matcher"]
        for source in ss.SOURCES:
            with self.subTest(source=source):
                self.assertIn(source, matcher)

    def test_no_undocumented_hook_fields(self) -> None:
        """`additionalContextLimit` is not in the hooks reference. The script's
        CONTEXT_LIMIT is what actually bounds the injection, so the manifest
        field was either ignored or grounds to reject the whole entry."""
        documented = {
            "type", "command", "commandWindows", "timeout", "statusMessage",
            "shell", "url", "headers", "prompt", "agent", "once",
        }
        for event, entries in self._hooks().items():
            for entry in entries:
                for hook in entry["hooks"]:
                    with self.subTest(event=event):
                        self.assertEqual(set(), set(hook) - documented)
                        self.assertNotIn("additionalContextLimit", hook)

    def test_every_hook_runs_without_python3_on_path(self) -> None:
        """`commandWindows` is not in the hooks reference, so it cannot be the
        only Windows path - and `python3` is usually absent there. `|| python`
        fires only when the first name is not found, because these hooks exit 0
        whenever they actually run."""
        for event, entries in self._hooks().items():
            for entry in entries:
                for hook in entry["hooks"]:
                    with self.subTest(event=event):
                        self.assertIn("|| python ", hook["command"])

    def test_the_stop_clock_is_the_documented_default(self) -> None:
        """200 was a number I picked, and it capped every anchor in this design
        under three minutes: a five-minute anchor was permanently unknown, held
        there by a limit its owner never chose."""
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        import goal_hooks as gh

        self.assertEqual(600, gh.HOOK_TIMEOUT_SECONDS)
        self.assertEqual(600, self._hooks()["Stop"][0]["hooks"][0]["timeout"])
        self.assertLess(gh.ANCHOR_BUDGET_CEILING, gh.HOOK_TIMEOUT_SECONDS)

    def test_the_gate_does_not_claim_the_goal_is_met(self) -> None:
        """A green anchor is one command exiting 0. Whether that is the goal
        belongs to `## Stop condition` - and the gate is the one component with
        hard power, so it is the last place that should overreach."""
        gate = (SKILL_ROOT / "scripts" / "goal_stop.py").read_text(encoding="utf-8")
        # The emitted sentence, not the comment that records why it went: the
        # comment has to keep the old wording to be readable.
        self.assertNotIn("Goal met.", gate)
        self.assertIn("`## Stop condition`'s question, not this gate's", gate)

    def test_review_is_not_demanded_on_every_red_turn(self) -> None:
        """The deny text and the template disagreed, and the run obeys the deny
        text: two forks per red turn against a template that says the anchor is
        the intermediate check."""
        gate = (SKILL_ROOT / "scripts" / "goal_stop.py").read_text(encoding="utf-8")
        self.assertIn("run when you propose completion, not on every red turn", gate)
        self.assertIn(
            "**Review runs at proposed completion**",
            (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8"),
        )

    def test_an_unenforceable_anchor_is_recorded_not_only_announced(self) -> None:
        """These two turns left the log empty, so an artifact the gate could
        never enforce looked in `--audit` exactly like a run not yet started."""
        gate = (SKILL_ROOT / "scripts" / "goal_stop.py").read_text(encoding="utf-8")
        self.assertIn('"event": "anchor_unavailable"', gate)
        self.assertIn("must not advance the turn count or the ceiling", gate)

    def test_arming_makes_the_gitignore_claim_true(self) -> None:
        """Three documents called `.goals/.work/` gitignored and nothing wrote
        the rule, so `git add -A` committed the reviewer's intermediates."""
        command = (PLUGIN_ROOT / "commands" / "goal-run.md").read_text(encoding="utf-8")
        self.assertIn(".goals/.gitignore", command)
        self.assertIn("'.work/' 'active'", command)

    def test_the_gate_table_counts_the_hooks_that_ship(self) -> None:
        skill = skill_text()
        shipped = len(self._hooks())
        self.assertEqual(4, shipped)
        self.assertIn("four hooks ship with this Skill", skill)
        self.assertIn("| `PostToolUseFailure` |", skill)
