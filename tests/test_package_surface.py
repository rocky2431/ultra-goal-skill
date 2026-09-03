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
PLUGIN_ROOT = REPO_ROOT / "plugins" / "goal-engineering"
SKILL_ROOT = PLUGIN_ROOT / "skills" / "goal-engineering"

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

        self.assertEqual("goal-engineering", plugin["name"])
        self.assertEqual(plugin["name"], entry["name"])
        self.assertEqual("./skills/", plugin["skills"])
        self.assertEqual("./plugins/goal-engineering", entry["source"]["path"])
        self.assertIn("name: goal-engineering", skill_text())
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
        for shape in ("goal line to paste", "workflow script", "delegation package"):
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
            "## Validate, then hand off",
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
            self.assertIn(target, va.KNOWN_TARGETS)

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
        self.assertIn("## Goal mode, on whichever host you are", skill)
        self.assertIn("You are the host.", skill)
        self.assertIn("requires a workflow runtime", skill)
        self.assertIn("do **not** emit `<slug>.workflow.js`", skill)
        # Artifacts are project assets, not one tool's private configuration.
        self.assertNotIn(".claude/workflows", skill)
        self.assertIn(".goals/", skill)
        # Activation scope must not name one host's commands either.
        # Host slash-commands belong in the goal-mode section and nowhere else.
        # Matched inside backticks so filenames like <slug>.goal.md do not count.
        head, tail = skill.split("## Goal mode, on whichever host you are", 1)
        tail = tail.split("## Compile one artifact", 1)[1]
        leaks = re.findall(r"`/(?:goal|loop|schedule)[` ]", head + tail)
        self.assertEqual([], leaks, f"host commands leaked: {leaks}")
        # Every measured host, Codex included - it was missed on the first pass.
        for host in ("Claude Code", "Codex", "Kimi", "zCode", "OpenCode"):
            self.assertIn(host, skill)

    def test_goal_mode_is_the_mechanism_and_the_anchor_is_the_evidence(self) -> None:
        """An earlier version claimed most hosts lacked goal mode. They have it."""
        skill = skill_text()
        self.assertIn("## Goal mode, on whichever host you are", skill)
        # Four hosts, each with its goal command named.
        for host in ("Claude Code", "Codex", "Kimi", "zCode", "OpenCode"):
            self.assertIn(host, skill)
        self.assertEqual(4, skill.count("`/goal <objective>`"))
        self.assertIn("Use the host's own goal mode", skill)
        # The gap goal mode leaves, and where it gets closed.
        self.assertIn("it asks **the model** whether the objective\nis met", skill)
        self.assertIn("closes it in the goal text itself", skill)
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
        self.assertIn("State which turn you are on at the start of each turn", handoff)
        # A3: all three refusals reach the pasted text, not just the document.
        self.assertIn("never application source or CI config", handoff)
        self.assertIn("do not call an upgrade safe without that output", handoff)
        self.assertIn("Do not conclude why something broke", handoff)
        # A4: carry-over is rewritten in two parts, lessons bounded.
        self.assertIn("Lessons gets at most 3 causal findings", handoff)
        # And it names the hosts it can be pasted into.
        for host in ("Claude Code", "Codex", "Kimi", "zCode"):
            self.assertIn(host, handoff)
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
            self.assertIn(target, va.KNOWN_TARGETS)


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
        self.assertIn("GOAL_ENGINEERING_HOOKS_DISABLED=1", skill)
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
            ["no_skill", "agent-harness-design", "goal-engineering"],
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
        files = [
            path
            for path in REPO_ROOT.rglob("*")
            if path.is_file()
            and ".git" not in path.relative_to(REPO_ROOT).parts
            and "__pycache__" not in path.relative_to(REPO_ROOT).parts
        ]
        relative = {path.relative_to(REPO_ROOT).as_posix() for path in files}
        self.assertFalse(any(path.endswith(".mcp.json") for path in relative))

        # Every shipped hook must route through the shared early exit.
        scripts = SKILL_ROOT / "scripts"
        hook_scripts = sorted(p.name for p in scripts.glob("goal_*.py"))
        self.assertEqual(
            ["goal_hooks.py", "goal_pre_compact.py", "goal_session_start.py",
             "goal_stop.py"],
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
            ["Stop", "SessionStart", "PreCompact"], list(manifest["hooks"])
        )
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
        self.assertIn("Eight clauses, each closing one hole:", skill)

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


if __name__ == "__main__":
    unittest.main()
