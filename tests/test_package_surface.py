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


# Surface checks protect packaging and instructions. Mechanical behavior is exercised
# in test_goal_contract.py and the hook tests; prose wrapping is not a runtime contract.
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
        skill = " ".join(skill_text().split())
        for required in (
            "## Keep activation scoped", "## Recognize the intent first",
            "## Interview protocol", "One question per turn", "carries your recommended answer",
            "Facts are yours, decisions are theirs", "## Classify first",
            "Can you sketch the whole thing on paper", "## Refuse these shapes",
            "No anchor, no artifact", "A plan or task", "who checks the checker?",
            "## Compile one artifact", "## Inspect what is running", "## Modify an existing loop",
            "## Validate, then offer to start it", "run the status command before the first question",
            "That record is also the interview's progress", "Edit the affected row",
            "A loop whose anchor changed is a different loop", "## Three tiers of frozen",
            "**False consensus**", "Review conclusions merged without evidence",
            "## Make the loop evolve", "read it before acting and rewrite it before finishing",
            "Rewrite, never append", "one project's dead end is another project's correct answer",
            "Preserve the owner's material words and clarifications verbatim", "false acceptance",
            "false rejection", "Start authorization is not a review waiver",
            "Read back the **complete contract**", "before arming",
        ):
            self.assertIn(required, skill, required)
        # Detailed operating contracts have specific, conditional destinations. Keeping
        # their links here protects discovery without loading every reference up front.
        for reference in ("goal-contract.md", "agent-modes.md", "host-hooks.md",
                          "document-system.md", "evolution-and-scope.md"):
            self.assertIn(f"references/{reference}", skill)
        self.assertIn("Do not preload all references", skill)
        run = (PLUGIN_ROOT / "commands" / "goal-run.md").read_text(encoding="utf-8")
        self.assertIn("goal(<slug>) turn <N>:", run)
        # Deliberately no line-count ceiling. Length is a proxy for bloat, and a
        # proxy optimized against stops measuring what it was standing in for: a
        # ceiling is satisfied by moving text into references/ whether or not that
        # makes the Skill better to use. What actually matters - SKILL.md holding
        # operating instructions while rationale lives in references/ - is a
        # judgement, so it stays a judgement. The assertions above still pin every
        # load-bearing rule, and test_every_relative_link_in_the_skill_resolves
        # keeps the references honest.

    def test_skill_does_not_mechanize_topology(self) -> None:
        skill = " ".join(skill_text().split())
        self.assertIn("Do not generate topology from a template engine", skill)
        self.assertIn("never edits the artifact", skill)
        self.assertIn("its silence is not evidence", skill)

    def test_skill_stands_alone_and_status_is_a_projection(self) -> None:
        skill = " ".join(skill_text().split())
        self.assertIn("Assume no other Skill is installed", skill)
        self.assertNotIn("belongs to a harness-design Skill", skill)
        self.assertIn("nothing is stored by the status command", skill)
        self.assertIn("recomputed on every call", skill)
        self.assertIn("use existing authorization", skill)

    def test_skill_keeps_lessons_in_the_project_and_the_shape_small(self) -> None:
        skill = " ".join(skill_text().split())
        self.assertIn("Never automatically promote them to user-level configuration or this Skill", skill)
        self.assertIn("tested promotion/rollback procedure", skill)
        reference = (SKILL_ROOT / "references" / "evolution-and-scope.md").read_text(encoding="utf-8")
        research = (SKILL_ROOT / "references" / "research-basis.md").read_text(encoding="utf-8")
        for paper in ("2608.26263", "2608.27454"):
            self.assertIn(paper, research)
        self.assertIn("100 InterCode CTF instances", reference)
        self.assertIn("48.7% to 63.7%", reference)
        self.assertIn("a skill cannot", reference)
        self.assertIn("## Promote knowledge only through a tested change", reference)
        self.assertIn("Compare on held-out work", reference)
        self.assertIn("Promote or roll back the candidate", reference)
        self.assertIn("no permanent maintainer", reference)
        self.assertIn("does not gain authority to edit the installed skill", reference)

    def test_adversarial_triad_is_an_optional_review_method(self) -> None:
        """Keep the optional triad without requiring it for ordinary goals."""
        skill = " ".join(skill_text().split())
        self.assertIn("who checks the checker?", skill)
        self.assertIn("not mandatory for every goal", skill)
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
        self.assertIn("## Other review methods", ar)
        self.assertIn("reviewers split by **domain**", ar)

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
        self.assertIn("### Optional execution planning", doc)
        self.assertIn("optional execution plan", doc)
        self.assertIn("does not require a new runtime", doc)

    def test_delegation_template_is_a_triad(self) -> None:
        text = (SKILL_ROOT / "assets" / "delegation-package.md").read_text(
            encoding="utf-8"
        )
        for section in ("## Reviewer", "## Critic", "## Convergence"):
            self.assertIn(section, text)
        self.assertNotIn("## Worker:", text)
        self.assertIn("reviewer and critic use different vendors", text)
        self.assertIn("vendor diversity is not evidence", text)
        self.assertIn("evidence-backed disagreement", text)
        self.assertIn("at most 5 inner rounds", " ".join(text.split()))
        # Targets must differ, and both must be registered.
        targets = re.findall(r"(?m)^- target: (\S+)$", text)
        self.assertEqual(2, len(targets))
        self.assertNotEqual(targets[0], targets[1])
        for target in targets:
            self.assertIn(target, va.known_targets()[0])

    def test_boundary_asks_for_three_refusals(self) -> None:
        skill = " ".join(skill_text().split())
        for refusal in ("**Scope**", "**Confidence**", "**Inference**"):
            self.assertIn(refusal, skill)
        self.assertIn("claims needing measured evidence", skill)
        self.assertIn("conclusions that documents alone cannot establish", skill)
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        for refusal in ("**Scope.**", "**Confidence.**", "**Inference.**"):
            self.assertIn(refusal, goal)

    def test_lessons_are_reflections_with_advisory_compactness(self) -> None:
        skill = " ".join(skill_text().split())
        self.assertIn("A lesson is a cause and a next action, not an event", skill)
        self.assertIn("three is a compaction suggestion, not a correctness limit", skill)
        self.assertIn("retain the evidence it cites", skill)
        reference = (SKILL_ROOT / "references" / "evolution-and-scope.md").read_text(encoding="utf-8")
        self.assertIn("A fourth necessary lesson may stay", reference)
        self.assertIn("not validity thresholds", reference)
        primitives = (SKILL_ROOT / "references" / "loop-primitives.md").read_text(encoding="utf-8")
        self.assertIn("## Lessons are reflections, not a log", primitives)
        self.assertIn("credit assignment problem", primitives)
        research = (SKILL_ROOT / "references" / "research-basis.md").read_text(encoding="utf-8")
        for source in ("arxiv.org/abs/2303.11366", "arxiv.org/pdf/2601.04556",
                       "arxiv.org/abs/2305.04091"):
            self.assertIn(source, research)

    def test_unattended_goal_template_wires_the_carry_over(self) -> None:
        goal = " ".join((SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8").split())
        for section in ("## Cadence", "## Carry-over", "### State", "### Lessons", "### Next"):
            self.assertIn(section, goal)
        self.assertIn("Read this before acting; reconcile it with the cited evidence", goal)
        self.assertIn("rewrite it before finishing", goal)
        handoff = goal.split("## Handoff", 1)[1]
        self.assertIn("Read the Carry-over section", handoff)
        self.assertIn("Rewrite the Carry-over section", handoff)
        self.assertIn("goal_run.py verify weekly-dep-upgrade", handoff)
        self.assertIn("goal(weekly-dep-upgrade): <summary>", handoff)
        self.assertIn("goal(weekly-dep-upgrade) turn <N>: <summary> [anchor: green|red|unknown]", handoff)
        self.assertNotIn("Commit once per turn", handoff)
        self.assertIn("Next gets the single objective", handoff)
        self.assertIn("Prune stale summaries, not their only evidence", handoff)

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
            "running_anchors_reuses_existing_authority",
            "changed_anchor_reopens_the_interview",
            "state_is_not_tracked_in_a_file",
            "unattended_loop_needs_carry_over",
            "one_shot_goal_keeps_recovery_without_cadence",
            "carry_over_is_rewritten_not_appended",
            "history_belongs_to_git",
            "requested_raw_trace_keeps_evidence_scope",
            "lesson_stays_in_the_project",
            "skill_learning_requires_tested_promotion",
            "workflow_script_requires_a_workflow_runtime",
            "artifacts_do_not_live_in_a_tool_directory",
            "host_capability_claim_gets_checked_not_assumed",
            "anchor_goes_into_the_goal_text_not_a_wrapper",
            "ceiling_must_be_in_the_goal_text",
            "no_scheduling_machinery_when_the_owner_starts_it_by_hand",
            "carry_over_survives_compaction_not_just_reruns",
            "boundary_is_three_refusals_not_one",
            "a_lesson_must_be_a_cause_and_a_next_action",
            "fourth_necessary_lesson_is_retained",
            "the_turn_number_is_said_out_loud",
            "an_unrunnable_anchor_is_unknown_not_failed",
            "the_target_level_divergence_stops_the_loop",
            "hook_pollution_is_answered_inside_the_hook",
            "an_identical_failure_never_releases_the_claim",
            "worker_evidence_survives_scratch_cleanup",
            "post_tool_use_has_one_narrow_job",
            "domain_split_reviewers_preserve_independent_evidence",
            "false_consensus_is_named_when_two_agents_agree",
            "the_critic_audits_the_review_not_the_code",
            "reviewer_and_critic_need_different_models",
            "a_threshold_change_needs_a_new_authorized_goal",
            "execution_plans_preserve_the_shared_goal",
            "interrupted_attempt_does_not_reuse_historical_green",
            "required_review_evidence_survives_cleanup",
            "unknown_external_effect_is_read_back_before_retry",
            "start_now_does_not_waive_independent_spec_critique",
            "true_quote_does_not_prove_its_conclusion",
            "silent_worker_requires_native_status_evidence",
            "candidate_skill_rule_can_be_rolled_back",
        ):
            self.assertIn(required, names)

    def test_skill_is_host_neutral(self) -> None:
        skill = " ".join(skill_text().split())
        self.assertIn("## Starting a run, on whichever host you are", skill)
        self.assertIn("run works in ordinary host turns", skill)
        self.assertIn("requires a workflow runtime", skill)
        self.assertIn("do **not** emit `<slug>.workflow.js`", skill)
        self.assertNotIn(".claude/workflows", skill)
        self.assertIn(".goals/", skill)
        head, tail = skill.split("## Starting a run, on whichever host you are", 1)
        tail = tail.split("## Validate, then offer to start it", 1)[1]
        leaks = re.findall(r"`/(?:goal|loop|schedule)[` ]", head + tail)
        self.assertEqual([], leaks, f"host commands leaked: {leaks}")
        self.assertIn("/ultra-goal", skill)
        for host in ("Claude Code", "Codex", "Kimi", "zCode", "OpenCode"):
            self.assertIn(host, skill)

    def test_native_continuation_and_completion_gate_have_distinct_jobs(self) -> None:
        skill = " ".join(skill_text().split())
        for host in ("Claude Code", "Codex", "Kimi", "zCode", "OpenCode"):
            self.assertIn(host, skill)
        self.assertEqual(4, skill.count("`/goal <objective>`"))
        self.assertIn("Goal mode supplies the turns; the gate judges the claims", skill)
        self.assertIn("cannot schedule the next turn", skill)
        self.assertIn("**`/ultra-goal:goal-run <slug>`**", skill)
        self.assertIn("this attempt's recorded `verification_passed` result", skill)
        self.assertNotIn("a host's goal mode is no longer needed", skill)
        self.assertIn("not proof of absence", skill)
        self.assertIn("Check your own host rather than trusting this table", skill)

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
        self.assertIn("Stop after 6 completion attempts even if\nunmet", handoff)
        # A1: the turn must be said out loud, or the ceiling is estimated by feel.
        self.assertIn("which `## Acceptance` lines this turn is for", handoff)
        # A3: all three refusals reach the pasted text, not just the document.
        self.assertIn("never application source or CI config", handoff)
        self.assertIn("do not call an upgrade safe without that output", handoff)
        self.assertIn("Do not conclude why something broke", handoff)
        # Recovery retains useful causal findings without a count-based validity gate.
        self.assertIn("Lessons gets the relevant causal findings and source pointers", handoff)
        self.assertIn("Prune stale summaries, not their only evidence", handoff)
        # Goal mode supplies continuation; the plugin command arms the evidence gate.
        # The handoff must also name the portable prompt fallback.
        self.assertIn("`/ultra-goal:goal-run weekly-dep-upgrade`", handoff)
        self.assertIn("arm the gate", handoff)
        self.assertIn("Where the plugin is absent, paste the text below", handoff)
        self.assertIn("goal_run.py arm weekly-dep-upgrade", handoff)
        for gone in ("crontab", "runner.sh"):
            self.assertNotIn(gone, handoff)

        primitives = (SKILL_ROOT / "references" / "loop-primitives.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## Goal mode across hosts", primitives)
        self.assertIn("These four are shapes, not commands.", primitives)
        self.assertIn("The ceiling has to be in the text.", primitives)
        self.assertNotIn("because compaction empties the context", " ".join(primitives.split()))
        recovery = primitives.split("## Goal mode across hosts", 1)[1].split("## Lessons", 1)[0]
        self.assertIn("summary", recovery)

    def test_every_relative_link_in_the_skill_resolves(self) -> None:
        missing = []
        for relative in ("SKILL.md", "references/host-hooks.md"):
            source = SKILL_ROOT / relative
            for target in re.findall(r"\]\((?!https?:)([^)#]+)\)", source.read_text(encoding="utf-8")):
                if not (source.parent / target).exists():
                    missing.append((relative, target))
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
                ("goal-package.md", "review-changed-files.goal.md"),
                ("decisions-record.md", "review-changed-files.decisions.md"),
            ]
        )

    def test_delegation_template_validates(self) -> None:
        self._validate(
            [
                ("delegation-package.md", "settlement-audit.delegation.md"),
                ("goal-package.md", "settlement-audit.goal.md"),
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
        skill = " ".join(skill_text().split())
        for decision in ("4. **Means:**", "8. **Read and write surface:**",
                         "9. **Divergence handling:**"):
            self.assertIn(decision, skill)
        self.assertIn("changing frozen terms stops and reports", skill)
        self.assertIn("A challenge is not permission to change the term", skill)
        self.assertIn("does not prevent resource collisions", skill)
        self.assertIn("shared files, databases, services and resource limits", skill)

    def test_the_graph_nodes_are_named_and_mapped(self) -> None:
        # Ownership and storage belong to the document-system reference, not a second
        # graph diagram in the entry. The executable route still shares one goal.
        skill = " ".join(skill_text().split())
        self.assertIn("references/document-system.md", skill)
        self.assertIn("loop and graph differ in **when routing gets decided**", skill)
        doc = (SKILL_ROOT / "references" / "document-system.md").read_text(encoding="utf-8")
        for node in ("<slug>.goal.md", "<slug>.decisions.md", "<slug>.events.jsonl",
                     "## Carry-over", "## Acceptance", "required review's receipt"):
            self.assertIn(node, doc)
        self.assertIn("Who writes it", doc)
        anti = (SKILL_ROOT / "references" / "anti-patterns.md").read_text(encoding="utf-8")
        for failure in ("Goodhart", "Blindness upward", "Conflict", "Measurement decay", "Circularity"):
            self.assertIn(failure, anti)

    def test_the_gate_section_states_three_outcomes_and_the_escape(self) -> None:
        self.assertIn("references/host-hooks.md", skill_text())
        doc = (SKILL_ROOT / "references" / "host-hooks.md").read_text(encoding="utf-8")
        self.assertIn("**Three outcomes, not two.**", doc)
        self.assertIn("**Nearly every path lets the turn end.**", doc)
        self.assertIn("A changed specification closes the run", doc)
        self.assertIn("`rm .goals/active`", doc)
        self.assertIn("ULTRA_GOAL_HOOKS_DISABLED=1", doc)
        self.assertIn("`PostToolUse`", doc)
        self.assertIn("neither cancels a host-native goal", doc)

    def test_document_system_answers_owner_when_and_relationships(self) -> None:
        doc = " ".join((SKILL_ROOT / "references" / "document-system.md").read_text(encoding="utf-8").split())
        for column in ("Who writes it", "Mutability", "In Git"):
            self.assertIn(column, doc)
        self.assertIn("frozen for the duration of a run", doc)
        self.assertIn("append-only, never edited", doc)
        self.assertIn("A slower, authorized design pass may revise the target", doc)
        self.assertIn("a summary is a derived checkpoint, not a source of truth", doc)
        self.assertIn("### Lessons", doc)
        self.assertIn("resolve revised terms with owner authority", doc)
        self.assertIn(".goals/.work/", doc)
        self.assertIn("gitignored", doc)
        self.assertIn("Give workers the context their mission needs", doc)
        self.assertIn("The orchestrator runs the anchor, not the workers", doc)
        self.assertIn("A required receipt and its supporting inputs must survive the round", doc)
        self.assertIn("separate goal files do not isolate shared product writes", doc.lower())

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
            "phase_split_preserves_context",
            "self_review_is_refused",
            "unquantified_stop_condition_is_sharpened",
            "loop_is_enough_so_no_graph",
            "graph_is_allowed_when_context_isolates",
            "cross_vendor_star_limits_are_stated",
            "single_worker_delegation_keeps_goal_contract",
            "mutual_checking_without_ground_is_refused",
            "requested_design_note_links_executable_contract",
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
        self.assertIn("Rechecked 2026-09-05", text)
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
        # README) - not docs/wip/ or docs/research/, the two record directories
        # whose whole job is citing absolute local paths to evidence. The
        # mission envelope carries two such paths by design, and the research
        # record carries more: probe receipts and three other agents' round
        # transcripts, quoted verbatim because a paraphrased receipt is not one.
        # Red-ing the suite on those guards nothing that installs anywhere.
        records = {("docs", "wip"), ("docs", "research")}
        files = [
            path
            for path in REPO_ROOT.rglob("*")
            if path.is_file()
            and ".git" not in path.relative_to(REPO_ROOT).parts
            and "__pycache__" not in path.relative_to(REPO_ROOT).parts
            and path.relative_to(REPO_ROOT).parts[:2] not in records
        ]
        relative = {path.relative_to(REPO_ROOT).as_posix() for path in files}
        self.assertFalse(any(path.endswith(".mcp.json") for path in relative))

        # Every shipped hook must route through the shared early exit.
        scripts = SKILL_ROOT / "scripts"
        hook_scripts = sorted(p.name for p in scripts.glob("goal_*.py"))
        self.assertEqual(
            ["goal_contract.py", "goal_hooks.py", "goal_pre_compact.py", "goal_prompt_submit.py",
             "goal_run.py", "goal_session_start.py", "goal_stop.py",
             "goal_tool_failure.py", "goal_tool_success.py",
             "goal_turn_started.py"],
            hook_scripts,
        )
        for name in hook_scripts:
            # goal_hooks is the shared plumbing and goal_run is the owner's
            # arming fence, not a host hook: neither routes through run_hook.
            if name in ("goal_contract.py", "goal_hooks.py", "goal_run.py"):
                continue
            source = (scripts / name).read_text(encoding="utf-8")
            self.assertIn("run_hook(", source, name)

        manifest = json.loads(
            (PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8")
        )
        # The shared file is auto-discovered by Claude Code and zCode alike,
        # so it carries only the events both document.
        self.assertEqual(
            ["Stop", "SessionStart", "PostToolUseFailure", "PostToolUse"],
            list(manifest["hooks"]),
        )
        # PostToolUseFailure earns its place: it fires only on a *failed* tool
        # call, so its cost does not scale with tool use the way PostToolUse
        # would - and it is the only host-observed view of a failed delegation.
        self.assertIn("PostToolUseFailure", manifest["description"] or "")
        # PostToolUse is present with ONE narrow job: recording a delegation
        # target's recovery - the positive observation a turn boundary cannot
        # substitute for. Its cost is bounded by running the delegation
        # detection on the invocation text before anything else, so an
        # ordinary tool call stops at one string check and writes nothing.
        self.assertIn("PostToolUse", manifest["hooks"])
        self.assertIn("goal_tool_success.py", json.dumps(manifest))
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
        skill = " ".join(skill_text().split())
        self.assertIn("### Wide latitude, zero trust in self-report", skill)
        self.assertIn("The run's report and mutable state are claims", skill)
        self.assertIn("Gate events are observations", skill)
        self.assertIn("receipts carry checked provenance", skill)
        # Keep the honest limits in the entry, before any unattended offer is used.
        self.assertIn("detection and audit, not isolation or authentication", skill)
        self.assertIn("No digest proves criterion adequacy", skill)

    def test_the_audit_command_is_documented_and_reads_only(self) -> None:
        skill = " ".join(skill_text().split())
        self.assertIn("validate_artifact.py .goals --audit", skill)
        self.assertIn("Audit reads Git history and the event log; it runs nothing", skill)

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
        self.assertIn("isolation that matters is over inputs", ar)
        self.assertIn("rule is stated\nrather than checked", ar)
        delegation = (SKILL_ROOT / "assets" / "delegation-package.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(2, delegation.count("- inputs:"))

    def test_means_and_next_are_nodes_in_the_graph(self) -> None:
        skill = " ".join(skill_text().split())
        self.assertIn("`[load-bearing]` or `[droppable]`", skill)
        self.assertIn("`### Next`: exactly one immediate recovery objective", skill)
        self.assertIn("new goal", skill)
        # The runnable prompt, not a second prompt copy in SKILL.md, carries the clauses.
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        handoff = goal.split("## Handoff", 1)[1]
        for clause in ("not its designer", "## Challenges from the run", "droppable",
                       "load-bearing", "## Acceptance", "Next gets the single"):
            self.assertIn(clause, handoff)

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
        skill = " ".join(skill_text().split())
        self.assertIn("State alone is not the decision", skill)
        self.assertIn("changing its ceiling is Modify", skill)
        self.assertIn("upgrading its next package is Executing", skill)
        self.assertIn("When uncertain, do the requested work rather than reopening an interview", skill)

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
        skill = " ".join(skill_text().split())
        self.assertIn("`## Challenges from the run` in the decisions record", skill)
        self.assertIn("term, observed obstacle and what would settle it", skill)
        self.assertIn("A challenge is not permission", skill)
        self.assertIn("do not invent one when there is no objection", skill)

    def test_divergence_reporting_has_somewhere_to_land(self) -> None:
        skill = " ".join(skill_text().split())
        self.assertIn("changing frozen terms stops and reports", skill)
        self.assertIn("`## Challenges from the run` in the decisions record", skill)

    def test_modify_reads_the_objection_first(self) -> None:
        skill = skill_text()
        self.assertIn(
            "**Read `## Challenges from the run` before anything else in that file.**",
            skill,
        )

    def test_the_goal_text_makes_the_run_the_run(self) -> None:
        skill = " ".join(skill_text().split())
        self.assertIn("you are now the run, not its designer", skill)
        self.assertIn("../../commands/goal-run.md", skill)
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        handoff = goal.split("## Handoff", 1)[1]
        self.assertIn("not its designer", handoff)
        self.assertIn("## Challenges from the run", handoff)

    def test_a_miss_is_paid_for_with_the_sentence(self) -> None:
        self.assertIn("If missing goal terms materially hindered that work, name the missing term once",
                      " ".join(skill_text().split()))

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
        skill = " ".join(skill_text().split())
        self.assertIn("observational command measures the requested result end to end", skill)
        self.assertIn("**An anchor that only tests the code**", skill)
        anti = (SKILL_ROOT / "references" / "anti-patterns.md").read_text(encoding="utf-8")
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

    def test_acceptance_is_required_for_every_goal(self) -> None:
        skill = " ".join(skill_text().split())
        self.assertIn("every goal gets `## Acceptance`", skill)
        self.assertIn("`covers` map", skill)
        self.assertIn("**Unordered, never numbered**", skill)
        contract = (SKILL_ROOT / "references" / "goal-contract.md").read_text(encoding="utf-8")
        self.assertIn("Every acceptance bullet has a stable ID", contract)
        self.assertIn("every acceptance ID maps exactly once", contract)

    def test_execution_planning_does_not_replace_acceptance(self) -> None:
        """The section most easily mistaken for the thing this Skill refuses."""
        doc = (SKILL_ROOT / "references" / "document-system.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## `## Acceptance` is not a task ledger, and here is the line", doc)
        self.assertIn("`ACCEPTANCE_ORDERED`", doc)
        self.assertIn("`plan.md`", doc)
        self.assertIn("`tasks.json`", doc)
        self.assertNotIn("are still refused", doc)
        self.assertIn("the stop condition written out longhand", doc)

    def test_the_anchor_budget_belongs_to_the_artifact(self) -> None:
        skill = " ".join(skill_text().split())
        self.assertIn("Write `budget: N minutes` under `## Anchor`", skill)
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        self.assertIn("budget: 2 minutes", goal)

    def test_worker_outcomes_include_the_two_blocked_states(self) -> None:
        ar = (SKILL_ROOT / "references" / "adversarial-review.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## When a worker cannot proceed", ar)
        for outcome in ("completed", "failed", "input-required", "rejected"):
            self.assertIn(f"**{outcome}**", ar)
        worker_states = ar.split("## When a worker cannot proceed", 1)[1].split("## Cost", 1)[0]
        self.assertNotIn("Silence is `input-required`", worker_states)
        self.assertIn("unconfirmed", worker_states)
        self.assertIn("explicit", worker_states)
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
        """Rewritten for the per-host contract: hosts register what they
        document AND can use. Kimi's reference makes every event but
        PreToolUse, Stop and UserPromptSubmit observation-only, so a Kimi
        SessionStart registration is one that cannot deliver anything by
        design (Claude round-1 F-4) - it is deliberately absent, and the rest
        of the shared core must still reach Kimi so the files cannot drift
        apart silently."""
        hooks = self.load("plugins/ultra-goal/kimi.plugin.json")["hooks"]
        manifest = json.loads(
            (PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8")
        )
        kimi_events = {h["event"] for h in hooks}
        self.assertNotIn(
            "SessionStart", kimi_events,
            "Kimi ignores SessionStart output; registering it reads as context "
            "recovery that cannot happen",
        )
        self.assertLessEqual(
            set(manifest["hooks"]) - {"SessionStart"}, kimi_events,
            "the shared core must reach every host that documents it",
        )


    def test_claude_code_hooks_use_the_variable_claude_code_substitutes(self) -> None:
        """`$PLUGIN_ROOT` is not the name Claude Code expands, so a plugin
        install would have pointed every hook at nothing."""
        text = (PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8")
        # Round-4 F2: under zCode only ZCODE_PLUGIN_ROOT is set, and a chain
        # that never consulted it turned every path into /skills/... and
        # silently loaded nothing - so the chain must name it.
        self.assertIn('R=\\"${CLAUDE_PLUGIN_ROOT}\\"', text)
        self.assertIn('R=\\"${ZCODE_PLUGIN_ROOT}\\"', text)
        self.assertIn('R=\\"${PLUGIN_ROOT}\\"', text)
        self.assertNotIn('"$PLUGIN_ROOT/', text)
        self.assertIn("%CLAUDE_PLUGIN_ROOT%", text)


class PerHostHookRegistrationTests(unittest.TestCase):
    """Every manifest registers only events its host documents.

    Verified 2026-09-04 against each vendor's reference, not against a working
    example:

    - Claude Code (code.claude.com/docs/en/hooks) documents Stop, SessionStart,
      PreCompact and PostToolUseFailure, and its manifest `hooks` field holds
      ADDITIONAL files on top of the auto-discovered hooks/hooks.json ("The
      standard hooks.json is loaded automatically, so manifest.hooks should
      only reference additional hook files" - read from the 2.1.260 binary).
    - zCode (zcode.z.ai/en/docs/hooks) documents exactly seven events:
      SessionStart, UserPromptSubmit, PreToolUse, PermissionRequest,
      PostToolUse, PostToolUseFailure, Stop - no PreCompact - and discovers
      hooks/hooks.json automatically regardless of the manifest.
    - Codex (learn.chatgpt.com/docs/hooks) documents twelve events including
      SessionStart, PreCompact and Stop - but no PostToolUseFailure - and its
      manifest `hooks` field REPLACES the default file location.
    - Kimi (moonshotai.github.io/kimi-code/en/customization/hooks) documents
      all five of our events plus UserPromptSubmit and TurnStarted, and only
      PreToolUse, Stop and UserPromptSubmit can affect the flow - SessionStart
      output is fire-and-forget there, which is why the prompt-submit hook
      exists. TurnStarted is observation-only too, but it is the reference's
      only event that fires for every new turn whatever its origin (user,
      task, system_trigger) and the only one carrying turn_id, which is what
      scoping the budget to the host turn needed.

    So the shared hooks/hooks.json - which Claude Code and zCode both
    auto-discover - may only carry events BOTH document: Stop, SessionStart,
    PostToolUseFailure.
    """

    DOCUMENTED = {
        "claude": {
            "SessionStart", "UserPromptSubmit", "PreToolUse", "PermissionRequest",
            "PostToolUse", "PostToolUseFailure", "Stop", "PreCompact",
        },
        "zcode": {
            "SessionStart", "UserPromptSubmit", "PreToolUse", "PermissionRequest",
            "PostToolUse", "PostToolUseFailure", "Stop",
        },
        "codex": {
            "PreToolUse", "PermissionRequest", "PostToolUse", "PreCompact",
            "PostCompact", "UserPromptSubmit", "SubagentStop", "Stop", "Interrupt",
            "SessionStart", "SubagentStart", "SessionEnd",
        },
        "kimi": {
            "UserPromptSubmit", "PreToolUse", "Stop", "PostToolUse",
            "PostToolUseFailure", "PermissionRequest", "SessionStart", "SessionEnd",
            "SubagentStart", "SubagentStop", "Interrupt", "PreCompact",
            "PostCompact", "Notification", "TurnStarted",
        },
    }

    def load(self, relative: str) -> dict:
        return json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))

    def hook_file(self, relative: str) -> dict:
        return json.loads((PLUGIN_ROOT / relative).read_text(encoding="utf-8"))

    def events_of(self, manifest: dict) -> set[str]:
        if "hooks" in manifest and isinstance(manifest["hooks"], list):
            return {h["event"] for h in manifest["hooks"]}  # Kimi's flat array
        return set(manifest["hooks"])

    def test_the_shared_hook_file_carries_only_events_claude_and_zcode_document(self):
        shared = self.hook_file("hooks/hooks.json")
        events = self.events_of(shared)
        self.assertEqual(
            {"Stop", "SessionStart", "PostToolUseFailure", "PostToolUse"}, events,
            "Claude Code and zCode both auto-discover this file; an event either "
            "does not document is an error or a dead gate. PostToolUse joined in "
            "round 5: it is the positive half of worker recovery, and both hosts "
            "document it",
        )
        for host in ("claude", "zcode"):
            self.assertLessEqual(events, self.DOCUMENTED[host], host)

    def test_precompact_lives_in_claude_and_codex_files_only(self):
        """zCode has no PreCompact event at all, so it cannot be in the shared
        file; Claude Code reaches it through its manifest's ADDITIONAL hook
        files, Codex through its manifest's replaced hook list."""
        claude_extra = self.hook_file("hooks/claude.json")
        self.assertEqual({"PreCompact"}, self.events_of(claude_extra))
        self.assertLessEqual(
            self.events_of(claude_extra), self.DOCUMENTED["claude"]
        )
        codex = self.hook_file("hooks/codex.json")
        self.assertEqual(
            {"Stop", "SessionStart", "PreCompact"}, self.events_of(codex)
        )
        self.assertLessEqual(self.events_of(codex), self.DOCUMENTED["codex"])

    def test_codex_manifest_replaces_discovery_with_its_own_file(self):
        """Codex's manifest hooks field overrides the default location, so it
        must name the file it wants - otherwise it would auto-discover the
        shared file and inherit PostToolUseFailure, which it does not
        document."""
        manifest = json.loads(
            (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text("utf-8")
        )
        self.assertEqual(["./hooks/codex.json"], manifest["hooks"])

    def test_claude_manifest_adds_its_extra_file_to_discovery(self):
        """Claude Code's manifest hooks are ADDITIONAL files, so naming only
        the PreCompact file is correct: the shared file is still
        auto-discovered."""
        manifest = json.loads(
            (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text("utf-8")
        )
        self.assertEqual(["./hooks/claude.json"], manifest["hooks"])

    def test_kimi_registers_six_events_all_documented(self):
        """Claude round-1 F-4 dropped Kimi's undeliverable SessionStart;
        Codex round-2 F2 added TurnStarted; round 5 added PostToolUse so
        worker recovery is a positive observation on Kimi too. What remains
        is exactly what Kimi can use: the shared core minus SessionStart,
        plus PreCompact (recorded evidence), UserPromptSubmit (the documented
        recovery channel) and TurnStarted (the host's own turn boundary with
        turn_id - the reference's only event that fires for every new turn
        whatever its origin). Seven hooks ship; Kimi registers six."""
        hooks = self.load("plugins/ultra-goal/kimi.plugin.json")["hooks"]
        self.assertEqual(
            {"Stop", "PreCompact", "PostToolUseFailure", "PostToolUse",
             "UserPromptSubmit", "TurnStarted"},
            {h["event"] for h in hooks},
        )
        self.assertLessEqual(
            {h["event"] for h in hooks}, self.DOCUMENTED["kimi"]
        )
        # And the dropped registration is named as dropped, with its reason,
        # where a Kimi user will read it.
        manifest_text = (PLUGIN_ROOT / "kimi.plugin.json").read_text("utf-8")
        self.assertIn("SessionStart is not registered", manifest_text)
        # TurnStarted is registered through its own script, observation-only.
        commands = {h["command"] for h in hooks}
        self.assertTrue(
            any("goal_turn_started.py" in c for c in commands),
            commands,
        )

    def test_the_shared_stop_entry_tags_zcode_through_its_documented_env_var(self):
        """One file serves two hosts, so the Stop entry must tell the gate
        which budget to spend. zCode documents ${ZCODE_PLUGIN_ROOT} for its
        hook commands and Claude Code does not set it, so the expansion adds
        `--host zcode` only under zCode; everywhere else the default host
        (claude) applies."""
        text = (PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8")
        # The tag follows the root that actually resolved: under zCode alone
        # the chain falls through to ZCODE_PLUGIN_ROOT and tags the host; the
        # tag must not fire when CLAUDE_PLUGIN_ROOT supplied the root.
        self.assertIn(
            '{ R=\\"${ZCODE_PLUGIN_ROOT}\\"; H=\\"--host zcode\\"; }', text)

    def test_codex_and_kimi_tag_their_own_stop_entries(self):
        codex = (PLUGIN_ROOT / "hooks" / "codex.json").read_text(encoding="utf-8")
        self.assertIn("--host codex", codex)
        kimi = (PLUGIN_ROOT / "kimi.plugin.json").read_text(encoding="utf-8")
        self.assertIn("--host kimi", kimi)

    def test_kimi_stop_timeout_matches_the_gate_it_runs(self):
        """200s would kill a hook whose anchor budget ceiling is 570s: every
        long anchor permanently `unknown`, held by a limit nobody chose - the
        clock-cap defect the shared manifest already fixed for itself."""
        hooks = self.load("plugins/ultra-goal/kimi.plugin.json")["hooks"]
        stop = next(h for h in hooks if h["event"] == "Stop")
        self.assertEqual(600, stop["timeout"])

    def test_the_prompt_submit_hook_is_kimi_only(self):
        """Kimi's SessionStart output is fire-and-forget, so the documented
        injection alternative is UserPromptSubmit. No other host needs it:
        theirs inject from SessionStart."""
        script = PLUGIN_ROOT / "skills" / "ultra-goal" / "scripts" / "goal_prompt_submit.py"
        self.assertTrue(script.is_file())
        for relative in ("hooks/hooks.json", "hooks/claude.json", "hooks/codex.json"):
            text = (PLUGIN_ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("goal_prompt_submit", text, relative)
        kimi = (PLUGIN_ROOT / "kimi.plugin.json").read_text(encoding="utf-8")
        self.assertIn("goal_prompt_submit.py", kimi)

    def test_codex_handlers_carry_the_windows_override_codex_documents(self):
        """Codex's hooks reference documents the field verbatim - "`commandWindows`
        is an optional Windows-only command override" - and `hooks/codex.json`
        carried it on none of its three handlers, so a Windows Codex would have
        been handed a POSIX shell string. Found by walking every manifest for
        the field rather than by reading the one file that had it.

        Every guard is also asserted in both directions, because the round-4
        miss on this exact field was checking the POSIX command and never
        opening `commandWindows`: with the script absent the guard exits before
        any interpreter, with it present the interpreter is reached.
        """
        codex = self.load("plugins/ultra-goal/hooks/codex.json")
        events = []
        for event, matchers in codex["hooks"].items():
            for matcher in matchers:
                for entry in matcher["hooks"]:
                    with self.subTest(event=event):
                        windows = entry.get("commandWindows")
                        self.assertIsNotNone(windows, event)
                        # The guard comes first and leaves on a missing script.
                        self.assertTrue(
                            windows.startswith("if not exist "), windows)
                        self.assertIn("exit 0 &", windows)
                        # And the interpreter is reachable behind it.
                        self.assertIn("py -3 ", windows)
                        self.assertIn(r"%CLAUDE_PLUGIN_ROOT%", windows)
                    events.append(event)
        self.assertEqual(["Stop", "SessionStart", "PreCompact"], events)
        # The host tag travels on the Windows branch too, or a Windows Codex
        # would be gated with another host's continuation budget.
        stop = codex["hooks"]["Stop"][0]["hooks"][0]["commandWindows"]
        self.assertTrue(stop.endswith("--host codex"), stop)

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
        skill = " ".join(skill_text().split())
        self.assertIn("discover actual available targets rather than asking the owner", skill)
        self.assertIn("`agent-delegate list --json`", skill)
        self.assertIn("do not assume the bridge is installed", skill)

    def test_every_stage_is_the_owners_to_assign(self) -> None:
        skill = " ".join(skill_text().split())
        self.assertIn("Follow owner-assigned roles", skill)
        self.assertIn("the main model selects a suitable method", skill)
        doc = self.reference()
        self.assertIn("not mandatory workflow phases", doc)
        self.assertIn("no mandatory test-first rule", doc)
        self.assertNotIn("Test-first is a **Constraint**", skill)

    def test_the_judge_is_recommended_to_judge_blind(self) -> None:
        self.assertIn("references/agent-modes.md", skill_text())
        doc = self.reference()
        self.assertIn("## Judging blind", doc)
        self.assertIn("before reading the worker's explanation", doc)
        self.assertIn("not proof that the verdict is correct", doc)
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        self.assertIn("- **judge**: this session, **blind first**", goal)

    def test_the_stop_hook_reminds_only_what_may_change(self) -> None:
        self.assertIn("references/host-hooks.md", skill_text())
        doc = (SKILL_ROOT / "references" / "host-hooks.md").read_text(encoding="utf-8")
        self.assertIn("It must not invite editing frozen terms", doc)
        self.assertIn('`decision: "block"`', doc)
        self.assertIn("**The anchor runs at exactly one moment: a completion candidate.**", doc)
        self.assertIn("An allow carries no added model context", doc)
        self.assertIn("**Two axes, never conflated", doc)
        for disposition in ("input_required", "blocked_retryable", "budget_exhausted", "unachievable"):
            self.assertIn(disposition, doc)

    def test_an_unbounded_ceiling_is_declarable(self) -> None:
        goal = (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8")
        self.assertIn("ceiling: 6", goal)
        self.assertIn("Write `ceiling: none` instead", goal)
        self.assertIn("explicit field; omission fails validation", goal)

    def test_review_methods_do_not_claim_guaranteed_independence(self) -> None:
        skill, doc = skill_text(), self.reference()
        self.assertIn("neither guarantees independence or correctness", skill)
        self.assertIn("neither eliminates shared errors", doc)
        self.assertIn("One independent reviewer can be sufficient", doc)

    def test_round_cap_applies_to_a_chosen_repeated_exchange(self) -> None:
        self.assertIn("For a repeated exchange, choose a round cap", self.reference())
        self.assertIn("When choosing repeated review, specify a cap", " ".join(skill_text().split()))

    def test_loop_versus_graph_is_kept_off_this_page(self) -> None:
        """Putting it in a list of role options was the clearest symptom."""
        doc = self.reference()
        self.assertIn("## What is *not* on this page", doc)
        self.assertIn("**Loop versus graph is not a role question.**", doc)

    def test_worker_assignment_preserves_authority_and_context(self) -> None:
        doc = self.reference()
        self.assertIn("Follow owner-assigned roles", doc)
        self.assertIn("Within delegated authority", doc)
        self.assertIn("Pass current decisions, failures and evidence", skill_text())
        self.assertIn("no mandatory test-first rule", doc)

    def test_judging_blind_is_an_evidence_based_option(self) -> None:
        doc = self.reference()
        self.assertIn("## Judging blind", doc)
        self.assertIn("before reading the worker's explanation", doc)
        self.assertIn("not proof that the verdict is correct", doc)

    def test_the_two_gate_channels_are_documented(self) -> None:
        doc = (SKILL_ROOT / "references" / "document-system.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## What the gate says, and to whom", doc)
        self.assertIn(
            "what the gate reminds the run of is exactly what it may change", doc)
        # The corrected belief is recorded where it can be read later - both
        # halves of it: the mixed payload was inert on Codex 0.150.1, and
        # deleting the nested form globally broke Kimi 0.40.1 (round-4 F8).
        self.assertIn(
            "One\nStop output cannot be shared across vendors", doc)
        self.assertIn(
            "a claim until something outside the emitter", doc
        )

    def test_degradation_says_which_half_it_actually_has(self) -> None:
        """Rewritten for Codex round-1 F5: this passage used to pin the
        contract as "declared and reported, not measured", which was true
        only while no hook could observe a failed delegation. The hooks
        reference documents PostToolUseFailure, so the failure IS measured on
        the hosts that register it, and the document now states the split in
        one place: order declared, failure measured where the event exists,
        adequacy always a claim."""
        doc = self.reference()
        self.assertIn("## Declared degradation", doc)
        self.assertIn("| who to fall back to | the **owner**, at design time", doc)
        self.assertIn("a **claim**, not evidence", doc)
        # The one contract, both halves, in this document.
        self.assertIn("declared; the failure is measured", doc)
        self.assertIn("no such event", doc)
        # The stale absolutes are gone - they contradicted the hook and the
        # audit finding that does get produced.
        self.assertNotIn("declared and reported**, not measured", doc)
        self.assertNotIn("no code could ever produce", doc)
        # The reason a fake check is worse than no check, stated.
        self.assertIn("because it reads as coverage", doc)
        self.assertIn(
            "a review that cannot happen is a missing review, not a red anchor", doc
        )

    def test_the_degradation_contract_is_the_same_everywhere(self) -> None:
        """Codex round-1 F5: SKILL.md, the README and agent-modes.md all
        carried a verdict on whether role failure is measured, and no two of
        them agreed with the validator. The search that found the
        contradictions must now come back consistent."""
        stale = (
            "UserPromptSubmit is not registered",
            "Nothing could write that event",
            "finding that no code could ever produce",
        )
        for path in (
            REPO_ROOT / "README.md",
            REPO_ROOT / "docs" / "usage.md",
            SKILL_ROOT / "SKILL.md",
            SKILL_ROOT / "references" / "agent-modes.md",
        ):
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                for phrase in stale:
                    self.assertNotIn(phrase, text)
        for path in (
            REPO_ROOT / "docs" / "usage.md",
            SKILL_ROOT / "SKILL.md",
            SKILL_ROOT / "references" / "agent-modes.md",
        ):
            with self.subTest(path=path.name, contract="stated"):
                self.assertIn("role_unavailable", path.read_text(encoding="utf-8"))

    def test_a_succeeded_delegation_with_no_artifact_is_named(self) -> None:
        # The entry routes role detail to one canonical reference and the run manual.
        skill = " ".join(skill_text().split())
        self.assertIn("references/agent-modes.md", skill)
        self.assertIn("Call success is not a join: inspect the expected artifact", skill)
        for path in (REPO_ROOT / "docs" / "usage.md", SKILL_ROOT / "references" / "agent-modes.md"):
            with self.subTest(path=path.name):
                doc = " ".join(path.read_text(encoding="utf-8").split())
                self.assertIn("a call that *succeeds* while writing no file", doc)
                self.assertIn("the round's evidence is the file the role was told to write", doc)
        run = (PLUGIN_ROOT / "commands" / "goal-run.md").read_text(encoding="utf-8")
        self.assertIn("check the file exists before you treat the round as done", run)
        audit = (SKILL_ROOT / "scripts" / "validate_artifact.py").read_text(encoding="utf-8")
        self.assertIn("REVIEW_UNEVIDENCED", audit)

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
        doc = self.reference()
        self.assertIn("forked skill sees", doc)
        self.assertIn("only its own SKILL.md content", doc)

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
        self.assertIn("**This example uses context independence.**", goal)
        self.assertIn("**Review runs at proposed completion**", goal)

    def test_the_plugin_ships_the_command_that_arms_the_gate(self) -> None:
        command = (PLUGIN_ROOT / "commands" / "goal-run.md").read_text(
            encoding="utf-8"
        )
        self.assertIn('arm "$ARGUMENTS"', command)
        self.assertIn("validate_artifact.py", command)
        self.assertIn("You are the run, not its designer.", command)
        self.assertIn("disarm $ARGUMENTS", command)
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
        skill = " ".join(skill_text().split())
        self.assertIn("**The fourth column is `Who`, and it holds `owner` or `agent`.**", skill)
        self.assertIn("| Always | `<slug>.decisions.md` — Decision / Rejected / Why / Who", skill)
        self.assertIn("Mark assumptions honestly; an agent-authored row is not owner confirmation", skill)

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
        skill = " ".join(skill_text().split())
        self.assertIn("**Definitions come from the vendor's reference documentation.**", skill)
        self.assertIn("Examples and local probes show a supported case, not the full host contract", skill)
        self.assertIn("Check the actual session", skill)

    def test_the_documented_fork_mechanism_is_named(self) -> None:
        doc = (SKILL_ROOT / "references" / "agent-modes.md").read_text(encoding="utf-8")
        self.assertIn("## How to actually run a fresh-context role", doc)
        self.assertIn("context: fork", doc)
        self.assertIn("agent: Explore", doc)
        # And why it is better than arranging isolation at the call site.
        self.assertIn("declared property of the file", doc)

    def test_the_gate_records_which_sources_disagreed(self) -> None:
        """A conflict between two authoritative sources is worth keeping -
        including how it was settled. Emitting both forms was retired after
        the Codex paired probe showed the mixed payload makes the block
        inert there, so the docstring must carry the disagreement AND the
        probe that resolved it, not a resolution that no longer holds."""
        gate = (SKILL_ROOT / "scripts" / "goal_stop.py").read_text(encoding="utf-8")
        self.assertIn("Two authoritative sources disagree", gate)
        self.assertIn("paired probe", gate)
        self.assertIn("made the block inert", gate)
        # Round-4 F8: the settlement has two halves - Codex blocks on the
        # top-level pair, Kimi solely on the nested one - so the deny builds
        # the asking host's own shape instead of picking one for everyone.
        self.assertIn("blocks solely on", gate)
        self.assertIn("Kimi 0.40.1", gate)
        self.assertIn("the one shape the asking host reads", gate)

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
    shouldn't invoke directly". Plugin roles are namespaced; bare names require
    standalone user or project entries, such as the optional main-skill shortcut.
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
        """Keep the existing run entry distinct from standalone owner shortcuts."""
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
        skill = " ".join(skill_text().split())
        self.assertIn("otherwise offer to start the run", skill)
        self.assertIn("`/ultra-goal:goal-run <slug>`", skill)
        self.assertIn("artifact, anchor, attempt ceiling, open requirements and exact command", skill)

    def test_the_offer_preserves_start_defer_and_amend(self) -> None:
        # Preserve start/defer/amend behavior without requiring a three-option UI.
        skill = " ".join(skill_text().split())
        self.assertIn("If start authority is missing, ask whether to start now or change the artifact first", skill)
        self.assertIn("If the owner declines starting, hand off the exact command", skill)

    def test_arming_still_needs_the_owner_to_say_so(self) -> None:
        """Chaining removes a keystroke, not the consent."""
        skill = skill_text()
        self.assertIn("Use an existing explicit start", skill)
        self.assertIn("authorization; otherwise offer to start the run", skill)
        self.assertIn("Never read silence or an unrelated reply as consent", skill)

    def test_the_handoff_supersedes_the_interview_manual(self) -> None:
        skill = " ".join(skill_text().split())
        self.assertIn("**When they say start it, this manual stops applying to you.**", skill)
        self.assertIn("the host keeps this Skill's content in the conversation", skill)
        self.assertIn("you are now the run, not its designer", skill)
        self.assertIn("../../commands/goal-run.md", skill)

    def test_the_handoff_does_not_send_the_owner_to_clear(self) -> None:
        skill = " ".join(skill_text().split())
        self.assertIn("**Do not send them to clear the context first.**", skill)
        self.assertIn("carry source decisions forward rather than forcing a reset by default", skill)
        self.assertNotIn("/clear", skill)

    def test_the_handoff_names_what_actually_holds_the_line(self) -> None:
        skill = " ".join(skill_text().split())
        self.assertIn("Frozen-spec checks and `## Challenges from the run` preserve that boundary", skill)
        run = (PLUGIN_ROOT / "commands" / "goal-run.md").read_text(encoding="utf-8")
        self.assertIn("You are the run, not its designer", run)
        self.assertIn("spec.baseline", run)
        self.assertIn("moved goalpost closes the run", run)

    def test_every_shape_hands_off_the_same_armed_contract(self) -> None:
        self.assertIn("runs against the same armed contract", " ".join(skill_text().split()))

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
        field was either ignored or grounds to reject the whole entry.

        `commandWindows` is the one field in this allowlist that neither
        consumer of this shared file documents: Claude Code's hooks reference
        lists `shell: "powershell"` as its Windows knob and no
        `commandWindows`, and zCode's lists ten handler fields and no
        `commandWindows` either. It is here on a measurement rather than a
        reading - both hosts load this file with the field present (zCode
        bisected directly: a config carrying it still loads and still fires the
        hook) - so on these two hosts the field is inert decoration, and it is
        the real Windows mechanism only in `hooks/codex.json`, whose reference
        does document it verbatim. That asymmetry is the whole reason this
        entry is annotated instead of silently allowlisted."""
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

    def test_every_hook_selects_its_interpreter_and_execs_once(self) -> None:
        """`commandWindows` is in neither consumer's hooks reference, so it
        cannot be the only Windows path - and `python3` is usually absent there. The old
        `|| python` fallback was retired: it re-ran the hook on a deliberate
        exit 2 with stdin drained and swallowed the block (plan defect 1.2,
        reproduced). The replacement selects the interpreter first, `exec`s it
        once, and checks the script exists - a missing script is a fail-open
        allow, never an exit-2 block (defect 1.3)."""
        for event, entries in self._hooks().items():
            for entry in entries:
                for hook in entry["hooks"]:
                    with self.subTest(event=event):
                        self.assertIn("command -v python3", hook["command"])
                        self.assertIn("exec python3 ", hook["command"])
                        self.assertIn("exec python ", hook["command"])
                        self.assertIn('|| exit 0', hook["command"])
                        self.assertNotIn("|| python ", hook["command"])

    def test_the_stop_clock_is_the_documented_default(self) -> None:
        """200 was a number I picked, and it capped every anchor in this design
        under three minutes: a five-minute anchor was permanently unknown, held
        there by a limit its owner never chose."""
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        import goal_hooks as gh

        self.assertEqual(600, gh.HOOK_TIMEOUT_SECONDS)
        self.assertEqual(600, self._hooks()["Stop"][0]["hooks"][0]["timeout"])
        self.assertLess(gh.ANCHOR_BUDGET_CEILING, gh.HOOK_TIMEOUT_SECONDS)

    def test_gate_success_is_limited_to_the_accepted_checks(self) -> None:
        """Passing accepted checks must not claim the specification is infallible."""
        gate = (SKILL_ROOT / "scripts" / "goal_stop.py").read_text(encoding="utf-8")
        # The emitted sentence, not the comment that records why it went: the
        # comment has to keep the old wording to be readable.
        self.assertNotIn("Goal met.", gate)
        self.assertIn("not that the specification can never be wrong", gate)

    def test_review_is_not_demanded_on_every_red_turn(self) -> None:
        """The deny text and the template disagreed, and the run obeys the deny
        text: two forks per red turn against a template that says the anchor is
        the intermediate check."""
        gate = (SKILL_ROOT / "scripts" / "goal_stop.py").read_text(encoding="utf-8")
        # The message is wrapped across adjacent literals; join them so the
        # pin checks the sentence the run reads, not the line breaks.
        joined = re.sub(r'"\s*\n\s*f?"', "", gate)
        self.assertIn(
            "their acceptance condition applies; do not repeat them by habit", joined)
        self.assertIn(
            "**Review runs at proposed completion**",
            (SKILL_ROOT / "assets" / "goal-package.md").read_text(encoding="utf-8"),
        )

    def test_an_unenforceable_anchor_is_recorded_not_only_announced(self) -> None:
        """These two turns left the log empty, so an artifact the gate could
        never enforce looked in `--audit` exactly like a run not yet started."""
        gate = (SKILL_ROOT / "scripts" / "goal_stop.py").read_text(encoding="utf-8")
        self.assertIn('"event": "anchor_unavailable"', gate)
        joined = gate.replace('"\n        # advance', "# advance").replace(
            "must not\n        # advance", "must not advance")
        # Round 5: the candidate was still consumed, so the event counts as
        # an attempt - refusing to count it was the round-4 ceiling bypass.
        self.assertIn('"event": "anchor_unavailable"', gate)
        self.assertIn("but the candidate\n        # was consumed, so it counts as an attempt",
                      gate)

    def test_arming_makes_the_gitignore_claim_true(self) -> None:
        """Three documents called `.goals/.work/` gitignored and nothing wrote
        the rule, so `git add -A` committed the reviewer's intermediates."""
        command = (PLUGIN_ROOT / "commands" / "goal-run.md").read_text(encoding="utf-8")
        self.assertIn("`.goals/.gitignore`", command)
        fence_src = (PLUGIN_ROOT / "skills" / "ultra-goal" / "scripts" /
                     "goal_run.py").read_text(encoding="utf-8")
        self.assertIn(
            'IGNORE_ENTRIES = (".work/", "active", "*.candidate", "*.verification.lock")', fence_src,
            "the arming fence writes the rule; a document claiming it alone was "
            "the original defect",
        )

    def test_arming_records_where_the_review_diff_starts(self) -> None:
        """The reviewer used to be handed `git diff HEAD` - uncommitted work
        only - while the run commits once per turn, so at proposed completion
        the reviewer saw almost nothing and could honestly report 'no
        findings', which the run then treated as coverage. Arming records the
        starting revision - and Codex round-1 F4 made it write-once: the line
        is guarded by `-s`, so re-running the arming command on an active run
        cannot move the range to HEAD and shrink a whole change into an
        empty diff."""
        command = (PLUGIN_ROOT / "commands" / "goal-run.md").read_text(encoding="utf-8")
        fence_src = (PLUGIN_ROOT / "skills" / "ultra-goal" / "scripts" /
                     "goal_run.py").read_text(encoding="utf-8")
        self.assertIn("rev-parse", fence_src)
        # Write-once moved into the fence: re-running arming on an active run
        # must not move the range to HEAD and shrink a whole change into an
        # empty diff - and round 5 added the second write-once baseline, the
        # authorized spec digest the gate compares every Stop against.
        self.assertIn('def _write_once', fence_src)
        self.assertIn('GIT_BASELINE_SUFFIX = ".baseline"', fence_src)
        self.assertIn('SPEC_BASELINE_SUFFIX', fence_src)
        self.assertIn("spec.baseline", command)

    def test_the_command_binds_the_slug_through_the_documented_placeholder(self) -> None:
        """Codex round-1 F1: Kimi's command loader expands only `$ARGUMENTS`,
        and Claude Code's reference defines `$1` as the *second* argument
        (0-indexed shorthand), so a `$1` slug bound deterministically on
        zCode alone. `$ARGUMENTS` is the one token documented by Claude Code
        ("All arguments passed when invoking the skill"), zCode ("$ARGUMENTS
        stands for all user-provided arguments") and Kimi ("Whatever you type
        after the command replaces $ARGUMENTS in the body") alike."""
        command = (PLUGIN_ROOT / "commands" / "goal-run.md").read_text(encoding="utf-8")
        self.assertNotIn("$1", command, "no host-neutral meaning; a model guess")
        self.assertIn("$ARGUMENTS", command)
        for role in ("review", "critic", "design-critic"):
            body = (PLUGIN_ROOT / "skills" / role / "SKILL.md").read_text()
            self.assertNotIn("$1", body)
            self.assertIn("$ARGUMENTS", body)

    def test_the_validator_step_refuses_to_arm_when_no_root_reaches_it(self) -> None:
        """Codex round-2 F1: the round-2 `else` branch said "Arming
        continues" when no plugin root reached command execution, which
        converted the hard precondition into a declared downgrade - an
        artifact the validator would refuse could arm the gate, proven by
        driving the real fences. The branch now refuses, and the fence gained
        Kimi's documented managed-install default as a real candidate
        (`$KIMI_CODE_HOME/plugins/managed/<id>/`, `~/.kimi-code` when unset -
        moonshotai.github.io/kimi-code/en/customization/plugins), so the
        refusal fires only where no documented path exists at all."""
        command = (PLUGIN_ROOT / "commands" / "goal-run.md").read_text(encoding="utf-8")
        for root in (
            "CLAUDE_PLUGIN_ROOT", "ZCODE_PLUGIN_ROOT", "KIMI_PLUGIN_ROOT",
            "PLUGIN_ROOT", "${KIMI_CODE_HOME:-$HOME/.kimi-code}/plugins/managed/ultra-goal",
        ):
            self.assertIn(root, command)
        self.assertIn("arming refused", command)
        self.assertNotIn("Arming continues", command)
        self.assertNotIn("not machine-validated", command)
        # The refusal is mechanical, not prose the model may talk itself
        # past: the fence execs the arming program and inherits its exit
        # status, and a validation error inside it stops arming before the
        # marker exists - there is no `||` for a second chance to swallow.
        self.assertIn('exec python3 "$runner" arm "$ARGUMENTS"', command)
        self.assertNotIn("|| exit 1\nprintf", command)

    def test_the_validation_and_arming_are_one_fence(self) -> None:
        """The round-2 defect was structural as well as textual: validation
        and arming were two fences, so anything that ran the second could skip
        the first. One fence cannot arm unvalidated."""
        command = (PLUGIN_ROOT / "commands" / "goal-run.md").read_text(encoding="utf-8")
        fences = re.findall(r"```bash\n(.*?)```", command, re.S)
        # The arming fence is the one that runs `goal_run.py arm`: validation
        # happens inside that call (a function whose exception is the
        # refusal), so the write-once baselines and the marker are written by
        # the same program that validated - there is no second fence.
        arming = [f for f in fences if 'arm "$ARGUMENTS"' in f]
        self.assertEqual(1, len(arming), "exactly one fence may arm")
        self.assertIn("goal_run.py", arming[0])
        self.assertIn("disarm", command,
                      "the checked disarm is documented beside the arm")

    def test_the_reviewer_sees_the_whole_run_not_the_last_commit(self) -> None:
        review = (PLUGIN_ROOT / "skills" / "review" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(".goals/$ARGUMENTS.baseline", review)
        # With no baseline (a run started before this existed, or no Git), the
        # reviewer still gets the old view - but says so instead of mistaking
        # it for the whole change.
        self.assertIn("HEAD", review)
        # Untracked files never appear in a diff; they are listed instead.
        self.assertIn("status --porcelain", review)
        # Uncommitted work that predates arming also lands in the range, so
        # the reviewer still attributes by the boundary.
        self.assertIn("## Boundary", review)

    def test_the_critic_audits_the_same_range_the_reviewer_saw(self) -> None:
        critic = (PLUGIN_ROOT / "skills" / "critic" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(".goals/$ARGUMENTS.baseline", critic)
        self.assertIn("status --porcelain", critic)

    def test_the_gate_table_counts_the_hooks_that_ship(self) -> None:
        """Six hooks ship; which ones register is a per-host fact, because an
        event a host does not document is an error or a dead gate. The union
        of the three hook files plus Kimi's inline list is the full set."""
        self.assertIn("references/host-hooks.md", skill_text())
        skill = (SKILL_ROOT / "references" / "host-hooks.md").read_text(encoding="utf-8")
        events: set[str] = set()
        for relative in ("hooks/hooks.json", "hooks/claude.json", "hooks/codex.json"):
            events |= set(json.loads((PLUGIN_ROOT / relative).read_text("utf-8"))["hooks"])
        events |= {
            h["event"]
            for h in json.loads(
                (PLUGIN_ROOT / "kimi.plugin.json").read_text("utf-8")
            )["hooks"]
        }
        self.assertEqual(
            {"Stop", "SessionStart", "PreCompact", "PostToolUseFailure",
             "PostToolUse", "UserPromptSubmit", "TurnStarted"},
            events,
        )
        self.assertIn("contains seven hooks", skill)
        self.assertIn("| `PostToolUseFailure` |", skill)
        self.assertIn("| `PostToolUse` |", skill)
        self.assertIn("| `UserPromptSubmit` |", skill)
        self.assertIn("| `TurnStarted` |", skill)
        # And the table says which host each extra registration is for.
        self.assertIn("Kimi only", skill)


class ArmingRangeContractTests(unittest.TestCase):
    """Codex round-1 F4, executed rather than pinned: the review baseline is
    write-once, its `none` fallback has an honest branch a reviewer can
    actually run, and a baseline that fell out of history is reported instead
    of diffed against blindly. Each test drives the real fenced commands from
    the shipped files, with the slug substituted exactly the way the hosts
    document it."""

    def command_text(self) -> str:
        return (PLUGIN_ROOT / "commands" / "goal-run.md").read_text(encoding="utf-8")

    def fences(self, text: str) -> list[str]:
        return re.findall(r"```bash\n(.*?)```", text, re.S)

    def arming_fence(self) -> str:
        """The one fence that validates and arms, slug bound the way every
        host documents it."""
        fence = next(
            f for f in self.fences(self.command_text())
            if 'arm "$ARGUMENTS"' in f
        )
        return fence.replace("$ARGUMENTS", "demo").replace("<resolved-native-session-id>", "session-aaa")

    STUB_VALIDATOR = (
        "class _Report:\n"
        "    findings = []\n"
        "def validate_paths(paths):\n"
        "    return _Report()\n"
    )

    def stage_fence(self, scripts_dir: Path, stub_validator: bool = True) -> None:
        """Stage the real arming fence: goal_run.py and its shared plumbing
        are always the shipped files; the validator is real when the test
        wants the validator's own contract, a passing stub otherwise."""
        scripts_dir.mkdir(parents=True, exist_ok=True)
        for name in ("goal_run.py", "goal_hooks.py", "goal_contract.py"):
            shutil.copy2(SKILL_ROOT / "scripts" / name, scripts_dir / name)
        if stub_validator:
            (scripts_dir / "validate_artifact.py").write_text(
                self.STUB_VALIDATOR, encoding="utf-8"
            )
        else:
            shutil.copy2(
                SKILL_ROOT / "scripts" / "validate_artifact.py",
                scripts_dir / "validate_artifact.py",
            )

    def sandbox_env(self, cwd: Path, **extra: str) -> dict[str, str]:
        """A hermetic command-execution environment: no plugin-root variable
        reaches it, and `$HOME` is a directory the test owns, so Kimi's
        managed-install default resolves inside the sandbox rather than
        against whatever this machine happens to have installed."""
        import os

        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(cwd),
               "CODEX_SESSION_ID": "session-aaa"}
        env.update(extra)
        return env

    def run_sh(
        self, script: str, cwd: Path, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["sh", "-c", script], cwd=str(cwd), capture_output=True, text=True,
            timeout=60, env=env,
        )

    def test_the_expanded_prompt_binds_the_slug_end_to_end(self) -> None:
        """The settlement Codex asked for, as far as a no-install mission can
        run it: expand `$ARGUMENTS` the way Kimi, Claude Code and zCode each
        document, and the rendered prompt names the artifact, leaves no `$1`,
        and arms `.goals/active` with exactly the slug - through the real
        validate-then-arm fence, with a validator the sandbox provides."""
        expanded = self.command_text().replace("$ARGUMENTS", "demo").replace("<resolved-native-session-id>", "session-aaa")
        self.assertIn("demo", expanded)
        self.assertNotIn("$1", expanded)
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            (cwd / ".goals").mkdir()
            (cwd / "acceptance.py").write_text("pass\n")
            from test_goal_contract import spec_text
            (cwd / ".goals" / "demo.goal.md").write_text(spec_text(), "utf-8")
            (cwd / ".goals" / "demo.decisions.md").write_text("# Decisions\n", "utf-8")
            root = cwd / "pluginroot" / "skills" / "ultra-goal" / "scripts"
            self.stage_fence(root)
            fence = next(
                f for f in self.fences(expanded) if 'arm "demo"' in f
            )
            result = self.run_sh(
                fence, cwd, env=self.sandbox_env(cwd, PLUGIN_ROOT=str(cwd / "pluginroot"))
            )
            self.assertEqual("", result.stderr, result.stderr)
            self.assertEqual(
                "demo\nsession session-aaa\n", (cwd / ".goals" / "active").read_text(encoding="utf-8")
            )
            self.assertTrue((cwd / ".goals" / "demo.baseline").is_file())
            # Round-4 F3: the authorized spec baseline is written before the
            # marker exists, so no Stop - not even a first candidate - can
            # author its own baseline.
            self.assertRegex(
                (cwd / ".goals" / "demo.spec.baseline").read_text("utf-8"),
                r"^[0-9a-f]{12}\n$",
            )
            self.assertIn(
                "*.candidate",
                (cwd / ".goals" / ".gitignore").read_text("utf-8"),
            )

    def test_an_invalid_artifact_cannot_arm_when_no_root_reaches_the_command(
        self,
    ) -> None:
        """Codex round-2 F1, reproduced as the refusal it must now be: on a
        host whose command execution carries no plugin-root variable (Kimi's
        reference documents none for bodies), the round-2 fence printed
        "Arming continues" and `armed= demo` against an artifact the
        validator refuses. Driven with the same invalid artifact and no
        reachable root, the fence must exit non-zero and leave no marker."""
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            goals = cwd / ".goals"
            goals.mkdir()
            (goals / "demo.goal.md").write_text("invalid\n", "utf-8")
            (goals / "demo.decisions.md").write_text("invalid\n", "utf-8")
            result = self.run_sh(self.arming_fence(), cwd, env=self.sandbox_env(cwd))
            self.assertEqual(1, result.returncode, result.stdout)
            self.assertIn("arming refused", result.stdout)
            self.assertIn("validate_artifact.py", result.stdout)
            self.assertFalse(
                (goals / "active").exists(),
                "a refused validation must not leave an armed gate behind",
            )

    def test_the_documented_kimi_install_default_validates_and_gates_arming(
        self,
    ) -> None:
        """The refusal keeps Kimi's primary path usable by giving it a real
        validation path first: local installs are copied to
        `$KIMI_CODE_HOME/plugins/managed/<id>/` (documented), the plugin's id
        is `ultra-goal`, and `KIMI_CODE_HOME` defaults to `~/.kimi-code`. A
        validator found there decides arming: its error stops the script
        before `.goals/active` is written; its pass arms."""
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            goals = cwd / ".goals"
            goals.mkdir()
            (cwd / "acceptance.py").write_text("pass\n")
            from test_goal_contract import spec_text
            (goals / "demo.goal.md").write_text(spec_text(), "utf-8")
            (goals / "demo.decisions.md").write_text("# Decisions\n", "utf-8")
            scripts = (
                cwd / "home" / ".kimi-code" / "plugins" / "managed" / "ultra-goal"
                / "skills" / "ultra-goal" / "scripts"
            )
            self.stage_fence(scripts)
            # A validator that fails hard decides arming: its SystemExit is
            # not caught by the fence, which is the point.
            (scripts / "validate_artifact.py").write_text(
                "raise SystemExit(1)\n", "utf-8"
            )
            home = cwd / "home"
            refused = self.run_sh(
                self.arming_fence(), cwd, env=self.sandbox_env(home)
            )
            self.assertEqual(1, refused.returncode, refused.stdout)
            self.assertFalse((goals / "active").exists())
            self.stage_fence(scripts)
            armed = self.run_sh(self.arming_fence(), cwd, env=self.sandbox_env(home))
            self.assertEqual(0, armed.returncode, armed.stdout)
            self.assertEqual(
                "demo\nsession session-aaa\n", (goals / "active").read_text(encoding="utf-8")
            )

    def test_the_real_validator_stops_arming_on_errors_only(self) -> None:
        """Through the plugin's own validator, not a stub: an invalid pair of
        artifacts is an error and must refuse to arm; the fence's contract is
        the validator's - errors stop, advisories do not."""
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            goals = cwd / ".goals"
            goals.mkdir()
            (goals / "demo.goal.md").write_text("invalid\n", "utf-8")
            (goals / "demo.decisions.md").write_text("invalid\n", "utf-8")
            result = self.run_sh(
                self.arming_fence(), cwd,
                env=self.sandbox_env(cwd, PLUGIN_ROOT=str(PLUGIN_ROOT)),
            )
            self.assertEqual(1, result.returncode)
            self.assertFalse((goals / "active").exists())

    def test_arming_twice_cannot_move_the_baseline(self) -> None:
        """The empty-diff defect, reproduced and refused: re-running the
        documented arming command used to rewrite the baseline to the current
        HEAD, handing the reviewer an empty range for a 26-file change."""
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            (cwd / ".goals").mkdir()
            (cwd / "acceptance.py").write_text("pass\n")
            from test_goal_contract import spec_text
            (cwd / ".goals" / "demo.goal.md").write_text(spec_text(), "utf-8")
            (cwd / ".goals" / "demo.decisions.md").write_text("# Decisions\n", "utf-8")
            root = cwd / "pluginroot" / "skills" / "ultra-goal" / "scripts"
            self.stage_fence(root)
            env = self.sandbox_env(cwd, PLUGIN_ROOT=str(cwd / "pluginroot"))
            arming = self.arming_fence()
            for args in (
                ("init", "-q", "."), ("config", "user.email", "t@e.st"),
                ("config", "user.name", "t"),
            ):
                subprocess.run(["git", *args], cwd=str(cwd), capture_output=True)
            self.run_sh(arming, cwd, env=env)
            first = (cwd / ".goals" / "demo.baseline").read_text(encoding="utf-8")
            (cwd / "work.txt").write_text("one turn of work\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", "-A"], cwd=str(cwd), capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-qm", "wip"], cwd=str(cwd), capture_output=True
            )
            self.run_sh(arming, cwd, env=env)
            self.assertEqual(
                first,
                (cwd / ".goals" / "demo.baseline").read_text(encoding="utf-8"),
                "a re-arm must not narrow the review range to nothing",
            )

    def review_fence(self) -> str:
        text = (PLUGIN_ROOT / "skills" / "review" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        return next(f for f in self.fences(text) if "baseline" in f).replace(
            "$ARGUMENTS", "demo"
        )

    def test_a_none_baseline_reports_the_review_unavailable(self) -> None:
        """`git diff none` is a fatal error, so the old fallback wording -
        'your diff covers uncommitted work only' - described a command that
        could not run. The branch now says the range cannot be formed and the
        review must be reported unavailable, which is executable and true."""
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            goals = cwd / ".goals"
            goals.mkdir()
            (goals / "demo.baseline").write_text("none\n", encoding="utf-8")
            (goals / "demo.goal.md").write_text("# Goal\n", encoding="utf-8")
            result = self.run_sh(self.review_fence(), cwd)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("no review range can be formed", result.stdout)
            self.assertIn("unavailable", result.stdout)

    def test_a_baseline_outside_history_is_reported(self) -> None:
        """A rebase under an armed run strands the recorded revision; the
        reviewer must say the range is unreliable instead of silently
        diffing against whatever Git makes of it."""
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            goals = cwd / ".goals"
            goals.mkdir()
            (goals / "demo.baseline").write_text("a" * 40 + "\n", encoding="utf-8")
            (goals / "demo.goal.md").write_text("# Goal\n", encoding="utf-8")
            for args in (
                ("init", "-q", "."), ("config", "user.email", "t@e.st"),
                ("config", "user.name", "t"),
            ):
                subprocess.run(["git", *args], cwd=str(cwd), capture_output=True)
            (cwd / "work.txt").write_text("x\n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=str(cwd), capture_output=True)
            subprocess.run(
                ["git", "commit", "-qm", "wip"], cwd=str(cwd), capture_output=True
            )
            result = self.run_sh(self.review_fence(), cwd)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("not an ancestor of HEAD", result.stdout)
