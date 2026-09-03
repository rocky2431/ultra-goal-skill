from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = (
    REPO_ROOT
    / "plugins"
    / "goal-engineering"
    / "skills"
    / "goal-engineering"
    / "scripts"
    / "validate_artifact.py"
)

sys.path.insert(0, str(VALIDATOR.parent))
import validate_artifact as va  # noqa: E402


GOOD_WORKFLOW = """// anchor: `pnpm test -- --run`
export const meta = {
  name: 'fix-flaky-tests',
  description: 'Quarantine flaky tests, then verify each quarantine decision',
  phases: [{ title: 'Triage' }, { title: 'Verify' }],
}

const SUITES = ['unit', 'integration']

const triaged = await parallel(SUITES.map(s => () =>
  agent(`Triage flaky tests in ${s}`, { label: `triage:${s}`, phase: 'Triage' })
))

const verdicts = await parallel(triaged.map(t => () =>
  agent(`Re-run and confirm: ${t}`, { label: 'verify', phase: 'Verify' })
))

return { verdicts }
"""

GOOD_DECISIONS = """# Decisions

| Decision | Rejected | Why |
| --- | --- | --- |
| Graph, pure Claude Workflow | Star delegation across vendors | No vendor-specific tool is needed |
| Split by suite | Split by phase (triage/fix/verify) | Phases share context; suites isolate it |
"""

GOOD_GOAL = """# Goal: weekly-dep-upgrade

## Intent

Keep production dependencies free of high-severity advisories without breaking the build.

## Boundary

Only `package.json` and the lockfile. Never touch application source, CI config, or pinned
transitive overrides that carry a comment.

## Stop condition

Stop when `pnpm audit --audit-level=high` reports 0 findings, or after 6 turns.

## Anchor

```
pnpm test -- --run
```

## Means

- `[load-bearing]` move versions through `package.json` and the lockfile only
- `[droppable]` clear every advisory in one pass - drop it when one dependency needs a
  source change to move

## Verification

A reviewer with a fresh context reviews the diff; a critic then audits that review rather
than the code, classifying each point as agreement, evidence-backed disagreement, or
concern-based disagreement. At most 5 inner rounds.

## Cadence

`/loop 1w`

## Carry-over

Read this before acting; rewrite it before finishing. Drop anything no longer true.

### State

- remaining after iteration 6: `packages/api`

### Lessons

- `@types/node` 22 breaks tsconfig because the bundler resolver rejects its new
  conditional exports - pin at 20 and revisit when tsconfig moves to `node20`

### Next

- get `packages/api` to a green anchor with `@types/node` pinned at 20

## Handoff

```
/goal Upgrade dependencies until the audit is clean. You have not met this goal until
`pnpm audit --audit-level=high` reports 0 findings in this session.
```
"""

GOOD_DELEGATION = """# Delegation: settlement-audit

Adversarial review over a frozen artifact. Only the orchestrator edits it, and only after
the review has converged. The reviewer and critic are different vendors on purpose: agents
that share a model share its blind spots.

## Reviewer

- target: codex
- mission: Review the diff for overflow on partial fills, reentrancy, and gas regressions. Cite file:line and the command whose output proves each finding.
- anchor: `forge test --match-path test/Settlement.t.sol`
- inputs: the frozen diff, the acceptance criteria, and the anchor's own output. Not the orchestrator's account of why the change is correct.

## Critic

- target: kimi
- mission: Audit the reviewer's review, not the code. Classify every point as exactly one of agreement, evidence-backed disagreement, or concern-based disagreement.
- anchor: `forge test --match-path test/Settlement.t.sol`
- inputs: the reviewer's review and the same frozen diff. Not the orchestrator's opinion of the review.

## Convergence

The artifact stays frozen for the whole inner loop. The reviewer answers a disagreement with
evidence, never with a rebuttal. At most 5 inner rounds. If round 1 converges with no
findings, accept and stop.
"""


class Harness(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, name: str, text: str) -> Path:
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def codes(self, *paths: Path) -> list[str]:
        report = va.validate_paths([str(p) for p in paths])
        return sorted({f.code for f in report.findings})


class WorkflowTests(Harness):
    def test_valid_workflow_with_decisions_passes(self) -> None:
        self.write("fix-flaky-tests.decisions.md", GOOD_DECISIONS)
        path = self.write("fix-flaky-tests.workflow.js", GOOD_WORKFLOW)
        report = va.validate_paths([str(path)])
        self.assertTrue(report.ok, report.findings)

    def test_missing_decisions_record_is_reported(self) -> None:
        path = self.write("fix-flaky-tests.workflow.js", GOOD_WORKFLOW)
        self.assertIn("PAIRED_DECISIONS_MISSING", self.codes(path))

    def test_meta_must_be_the_first_statement(self) -> None:
        self.write("x.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "x.workflow.js",
            "const DIMENSIONS = ['a']\n" + GOOD_WORKFLOW,
        )
        self.assertIn("META_NOT_FIRST", self.codes(path))

    def test_meta_must_be_a_pure_literal(self) -> None:
        self.write("y.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "y.workflow.js",
            GOOD_WORKFLOW.replace(
                "name: 'fix-flaky-tests',", "name: buildName(),"
            ),
        )
        self.assertIn("META_NOT_LITERAL", self.codes(path))

    def test_meta_requires_name_and_description(self) -> None:
        self.write("z.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "z.workflow.js",
            GOOD_WORKFLOW.replace(
                "  description: 'Quarantine flaky tests, then verify each quarantine decision',\n",
                "",
            ),
        )
        self.assertIn("META_MISSING_FIELD", self.codes(path))

    def test_phase_used_in_code_must_be_declared_in_meta(self) -> None:
        self.write("p.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "p.workflow.js", GOOD_WORKFLOW.replace("phase: 'Verify'", "phase: 'Confirm'")
        )
        self.assertIn("PHASE_TITLE_UNDECLARED", self.codes(path))

    def test_syntax_error_is_reported(self) -> None:
        self.write("s.decisions.md", GOOD_DECISIONS)
        path = self.write("s.workflow.js", GOOD_WORKFLOW + "\nfunction ( {\n")
        self.assertIn("SYNTAX_ERROR", self.codes(path))


class GoalTests(Harness):
    def test_valid_goal_package_passes(self) -> None:
        self.write("weekly-dep-upgrade.decisions.md", GOOD_DECISIONS)
        path = self.write("weekly-dep-upgrade.goal.md", GOOD_GOAL)
        report = va.validate_paths([str(path)])
        self.assertTrue(report.ok, report.findings)

    def test_missing_stop_condition_is_reported(self) -> None:
        self.write("g.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "g.goal.md", GOOD_GOAL.replace("## Stop condition", "## Notes")
        )
        self.assertIn("STOP_CONDITION_MISSING", self.codes(path))

    def test_unquantified_stop_condition_is_reported(self) -> None:
        self.write("h.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "h.goal.md",
            GOOD_GOAL.replace(
                "Stop when `pnpm audit --audit-level=high` reports 0 findings, or after 6 turns.",
                "Stop when the dependencies look healthy enough.",
            ),
        )
        self.assertIn("STOP_CONDITION_NOT_QUANTIFIED", self.codes(path))

    def test_missing_independent_verification_is_reported(self) -> None:
        self.write("i.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "i.goal.md", GOOD_GOAL.replace("## Verification", "## Afterthoughts")
        )
        self.assertIn("VERIFIER_NOT_DECLARED", self.codes(path))

    def test_missing_intent_is_reported(self) -> None:
        self.write("t1.decisions.md", GOOD_DECISIONS)
        path = self.write("t1.goal.md", GOOD_GOAL.replace("## Intent", "## Summary"))
        self.assertIn("INTENT_MISSING", self.codes(path))

    def test_missing_boundary_is_reported(self) -> None:
        self.write("t2.decisions.md", GOOD_DECISIONS)
        path = self.write("t2.goal.md", GOOD_GOAL.replace("## Boundary", "## Scope notes"))
        self.assertIn("BOUNDARY_MISSING", self.codes(path))

    def test_anchor_without_a_command_is_reported(self) -> None:
        self.write("t3.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "t3.goal.md",
            GOOD_GOAL.replace("```\npnpm test -- --run\n```", "The team agrees it feels stable."),
        )
        self.assertIn("ANCHOR_NOT_EXECUTABLE", self.codes(path))

    def test_missing_anchor_is_reported(self) -> None:
        self.write("j.decisions.md", GOOD_DECISIONS)
        path = self.write("j.goal.md", GOOD_GOAL.replace("## Anchor", "## Background"))
        self.assertIn("ANCHOR_MISSING", self.codes(path))


class DelegationTests(Harness):
    """One delegation artifact is one adversarial-review triad: a main agent that
    edits, a reviewer that reviews the artifact, and a critic that reviews the
    review. Three roles beat five independent reviewers in the source study, and
    the reason is the third role, not the count."""

    def test_valid_triad_passes(self) -> None:
        self.write("cross-vendor-audit.decisions.md", GOOD_DECISIONS)
        path = self.write("cross-vendor-audit.delegation.md", GOOD_DELEGATION)
        report = va.validate_paths([str(path)])
        self.assertTrue(report.ok, [f.as_dict() for f in report.findings])

    def test_a_missing_reviewer_is_reported(self) -> None:
        self.write("r.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "r.delegation.md", GOOD_DELEGATION.replace("## Reviewer", "## Notes")
        )
        self.assertIn("REVIEWER_MISSING", self.codes(path))

    def test_a_missing_critic_is_reported(self) -> None:
        """A reviewer nobody audits is the shape the study found unreliable."""
        self.write("c.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "c.delegation.md", GOOD_DELEGATION.replace("## Critic", "## Notes")
        )
        self.assertIn("CRITIC_MISSING", self.codes(path))

    def test_reviewer_and_critic_on_the_same_vendor_is_reported(self) -> None:
        """Same model, same blind spots - the critic would mostly agree."""
        self.write("sv.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "sv.delegation.md", GOOD_DELEGATION.replace("- target: kimi", "- target: codex")
        )
        self.assertIn("SAME_VENDOR_REVIEW", self.codes(path))

    def test_a_critic_without_the_three_classes_is_reported(self) -> None:
        self.write("dc.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "dc.delegation.md",
            GOOD_DELEGATION.replace(
                "Classify every point as exactly one of agreement, evidence-backed "
                "disagreement, or concern-based disagreement.",
                "Say whether you agree with the reviewer.",
            ),
        )
        self.assertIn("DISAGREEMENT_NOT_CLASSIFIED", self.codes(path))

    def test_a_missing_convergence_rule_is_reported(self) -> None:
        self.write("cv.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "cv.delegation.md", GOOD_DELEGATION.replace("## Convergence", "## Notes")
        )
        self.assertIn("CONVERGENCE_MISSING", self.codes(path))

    def test_an_unbounded_inner_loop_is_reported(self) -> None:
        self.write("ub.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "ub.delegation.md",
            GOOD_DELEGATION.replace("At most 5 inner rounds.", "Iterate until they agree."),
        )
        self.assertIn("CONVERGENCE_NOT_BOUNDED", self.codes(path))

    def test_unknown_target_is_reported(self) -> None:
        self.write("k.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "k.delegation.md", GOOD_DELEGATION.replace("- target: kimi", "- target: gpt5")
        )
        self.assertIn("UNKNOWN_TARGET", self.codes(path))

    def test_a_role_without_a_mission_is_reported(self) -> None:
        self.write("m.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "m.delegation.md",
            GOOD_DELEGATION.replace(
                "- mission: Audit the reviewer's review, not the code. Classify every point "
                "as exactly one of agreement, evidence-backed disagreement, or "
                "concern-based disagreement.\n",
                "",
            ),
        )
        self.assertIn("ROLE_FIELD_MISSING", self.codes(path))

    def test_status_reports_the_two_roles(self) -> None:
        self.write("t.decisions.md", GOOD_DECISIONS)
        self.write("t.delegation.md", GOOD_DELEGATION)
        item = va.status_paths([str(self.dir)])["artifacts"][0]
        self.assertEqual(["codex", "kimi"], item["workers"])


class GoalVerificationTests(Harness):
    def test_verification_naming_only_one_role_is_reported(self) -> None:
        self.write("v1.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "v1.goal.md",
            GOOD_GOAL.replace(
                "a critic then audits that review rather\nthan the code, classifying each "
                "point as agreement, evidence-backed disagreement, or\nconcern-based "
                "disagreement. At most 5 inner rounds.",
                "That is the whole check.",
            ),
        )
        self.assertIn("REVIEW_NOT_ADVERSARIAL", self.codes(path))

    def test_verification_without_a_round_cap_is_reported(self) -> None:
        self.write("v2.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "v2.goal.md",
            GOOD_GOAL.replace("At most 5 inner rounds.", "Repeat until they agree."),
        )
        self.assertIn("CONVERGENCE_NOT_BOUNDED", self.codes(path))


class DecisionsTests(Harness):
    def test_malformed_decisions_table_is_reported(self) -> None:
        self.write("n.decisions.md", "# Decisions\n\nWe chose a graph.\n")
        path = self.write("n.workflow.js", GOOD_WORKFLOW)
        self.assertIn("DECISIONS_TABLE_MALFORMED", self.codes(path))

    def test_empty_why_cell_is_reported(self) -> None:
        self.write(
            "o.decisions.md",
            "# Decisions\n\n| Decision | Rejected | Why |\n| --- | --- | --- |\n"
            "| Graph | Loop |  |\n",
        )
        path = self.write("o.workflow.js", GOOD_WORKFLOW)
        self.assertIn("DECISIONS_TABLE_MALFORMED", self.codes(path))


class PlaceholderTests(Harness):
    def test_leftover_placeholder_is_reported(self) -> None:
        self.write("q.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "q.goal.md", GOOD_GOAL.replace("6 turns", "TB" + "D turns")
        )
        self.assertIn("PLACEHOLDER_LEFT", self.codes(path))


class DirectoryAndCliTests(Harness):
    def test_directory_scan_finds_every_artifact(self) -> None:
        self.write("a.decisions.md", GOOD_DECISIONS)
        self.write("a.workflow.js", GOOD_WORKFLOW)
        self.write("b.goal.md", GOOD_GOAL)  # decisions record missing on purpose
        report = va.validate_paths([str(self.dir)])
        self.assertFalse(report.ok)
        self.assertEqual(
            ["PAIRED_DECISIONS_MISSING"], sorted({f.code for f in report.findings})
        )

    def test_unknown_suffix_is_reported(self) -> None:
        path = self.write("notes.md", "hello")
        self.assertIn("UNKNOWN_ARTIFACT_KIND", self.codes(path))

    def test_cli_exits_zero_on_clean_artifact(self) -> None:
        self.write("c.decisions.md", GOOD_DECISIONS)
        self.write("c.workflow.js", GOOD_WORKFLOW)
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(self.dir), "--json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('"ok": true', result.stdout)

    def test_cli_exits_one_and_prints_typed_findings(self) -> None:
        self.write("d.workflow.js", GOOD_WORKFLOW)
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(self.dir), "--json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("PAIRED_DECISIONS_MISSING", result.stdout)

    def test_cli_exits_two_on_missing_path(self) -> None:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(self.dir / "nope.workflow.js")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(2, result.returncode)

    def test_validator_never_edits_the_artifact(self) -> None:
        self.write("e.decisions.md", "# Decisions\n\nbroken\n")
        path = self.write("e.workflow.js", GOOD_WORKFLOW)
        before = path.read_bytes()
        va.validate_paths([str(path)])
        self.assertEqual(before, path.read_bytes())


class MeansTests(Harness):
    """The section that decides how much latitude a run actually has.

    Without labels, abandoning a feature is indistinguishable from scope drift,
    so the run has to either stop on every surprise or drop things quietly.
    """

    def test_valid_means_section_passes(self) -> None:
        self.write("m.decisions.md", GOOD_DECISIONS)
        path = self.write("m.goal.md", GOOD_GOAL)
        report = va.validate_paths([str(path)])
        self.assertTrue(report.ok, report.findings)

    def test_missing_means_is_reported(self) -> None:
        self.write("m.decisions.md", GOOD_DECISIONS)
        path = self.write("m.goal.md", GOOD_GOAL.replace("## Means", "## Notes"))
        self.assertIn("MEANS_MISSING", self.codes(path))

    def test_unlabelled_means_is_reported(self) -> None:
        self.write("m.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "m.goal.md", GOOD_GOAL.replace("`[load-bearing]` ", "").replace(
                "`[droppable]` ", ""
            )
        )
        self.assertIn("MEANS_UNLABELLED", self.codes(path))

    def test_either_label_satisfies_it(self) -> None:
        self.write("m.decisions.md", GOOD_DECISIONS)
        for label in ("[load-bearing]", "[droppable]"):
            path = self.write(
                "m.goal.md",
                GOOD_GOAL.replace("`[load-bearing]`", f"`{label}`").replace(
                    "`[droppable]`", f"`{label}`"
                ),
            )
            self.assertNotIn("MEANS_UNLABELLED", self.codes(path), label)


class NextTests(Harness):
    """`### Next` is the edge that closes the loop, and it takes exactly one entry."""

    def test_missing_next_is_reported_with_the_other_subsections(self) -> None:
        self.write("n.decisions.md", GOOD_DECISIONS)
        path = self.write("n.goal.md", GOOD_GOAL.replace("### Next", "### Plans"))
        report = va.validate_paths([str(path)])
        codes = {f.code for f in report.findings}
        self.assertIn("CARRYOVER_SECTIONS_MISSING", codes)
        message = next(
            f.message for f in report.findings if f.code == "CARRYOVER_SECTIONS_MISSING"
        )
        self.assertIn("next", message)

    def test_more_than_one_next_entry_is_a_plan(self) -> None:
        self.write("n.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "n.goal.md",
            GOOD_GOAL.replace(
                "- get `packages/api` to a green anchor with `@types/node` pinned at 20",
                "- get `packages/api` green\n- then `packages/web`\n- then release",
            ),
        )
        self.assertIn("NEXT_NOT_SINGLE", self.codes(path))


class RoleInputTests(Harness):
    """Different vendors buy different blind spots; only `inputs` buys independence."""

    def test_reviewer_without_inputs_is_reported(self) -> None:
        self.write("d.decisions.md", GOOD_DECISIONS)
        stripped = GOOD_DELEGATION.replace(
            "- inputs: the frozen diff, the acceptance criteria, and the anchor's own "
            "output. Not the orchestrator's account of why the change is correct.\n",
            "",
        )
        path = self.write("d.delegation.md", stripped)
        report = va.validate_paths([str(path)])
        self.assertIn("ROLE_FIELD_MISSING", {f.code for f in report.findings})
        self.assertTrue(
            any("inputs" in f.message for f in report.findings), report.findings
        )


class AuditTests(Harness):
    """Claims versus measurements, which is the whole reverse-tracing story.

    These use a real Git repository because the claim side of the comparison is
    the commit subject, and parsing it wrong is exactly the bug this class was
    written after: filtering `git log` by the artifact's path hid every turn
    that changed only source, which is most of them.
    """

    def setUp(self) -> None:
        super().setUp()
        self.run_git("init", "-q", ".")
        self.run_git("config", "user.email", "t@e.st")
        self.run_git("config", "user.name", "t")
        self.write("demo.decisions.md", GOOD_DECISIONS)
        self.artifact = self.write("demo.goal.md", GOOD_GOAL)
        self.run_git("add", "-A")
        self.run_git("commit", "-qm", "chore: add the artifact")

    def run_git(self, *args: str) -> None:
        subprocess.run(
            ["git", *args], cwd=str(self.dir), check=True, capture_output=True
        )

    def digest(self) -> str:
        """The artifact's real frozen digest, so only the tests that mean to
        move the goalposts move them."""
        return va.frozen_digest(self.artifact.read_text(encoding="utf-8"))

    def log(self, *entries: dict) -> None:
        import json as _json

        (self.dir / "demo.events.jsonl").write_text(
            "\n".join(_json.dumps(e) for e in entries) + "\n", encoding="utf-8"
        )

    def claim(self, turn: int, verdict: str, touch_artifact: bool = False) -> None:
        if touch_artifact:
            self.artifact.write_text(
                self.artifact.read_text(encoding="utf-8") + "\n", encoding="utf-8"
            )
            self.run_git("add", "-A")
            self.run_git(
                "commit", "-qm", f"goal(demo) turn {turn}: work [anchor: {verdict}]"
            )
            return
        self.run_git(
            "commit",
            "--allow-empty",
            "-qm",
            f"goal(demo) turn {turn}: work [anchor: {verdict}]",
        )

    def audit_codes(self) -> list[str]:
        _, findings = va.audit_artifact(self.artifact)
        return sorted({f.code for f in findings})

    def test_agreeing_claim_and_measurement_report_nothing(self) -> None:
        self.log({"event": "anchor_checked", "turn": 1, "outcome": "green",
                  "exit_code": 0, "spec_digest": self.digest()})
        self.claim(1, "green")
        self.assertEqual([], self.audit_codes())

    def test_a_claim_the_gate_contradicts_is_reported(self) -> None:
        self.log({"event": "anchor_checked", "turn": 1, "outcome": "red",
                  "exit_code": 1, "spec_digest": self.digest()})
        self.claim(1, "green")
        self.assertIn("CLAIM_CONTRADICTED", self.audit_codes())

    def test_a_claim_with_no_check_for_that_turn_is_reported(self) -> None:
        self.log({"event": "anchor_checked", "turn": 1, "outcome": "green",
                  "exit_code": 0, "spec_digest": self.digest()})
        self.claim(1, "green")
        self.claim(2, "green")
        self.assertIn("CLAIM_UNWITNESSED", self.audit_codes())

    def test_claims_are_found_when_the_turn_never_touched_the_artifact(self) -> None:
        """Regression: a pathspec filter dropped 2 of 3 claims in a scratch run.

        Most turns change source and leave the artifact alone, so selecting
        commits by the slug in the subject is the only correct filter.
        """
        self.log({"event": "anchor_checked", "turn": 1, "outcome": "green",
                  "exit_code": 0, "spec_digest": self.digest()})
        self.claim(1, "green")  # empty commit: touches nothing at all
        audit, _ = va.audit_artifact(self.artifact)
        rows = {row["turn"]: row for row in audit["rows"]}
        self.assertEqual("green", rows[1]["claimed"])
        self.assertEqual("green", rows[1]["measured"])

    def test_a_later_commit_for_the_same_turn_wins(self) -> None:
        self.log({"event": "anchor_checked", "turn": 1, "outcome": "red",
                  "exit_code": 1, "spec_digest": self.digest()})
        self.claim(1, "green")
        self.claim(1, "red")
        self.assertEqual([], self.audit_codes())

    def test_claims_with_no_event_log_at_all_are_reported_as_ungated(self) -> None:
        self.claim(1, "green")
        codes = self.audit_codes()
        self.assertIn("GATE_NEVER_RAN", codes)
        self.assertNotIn("CLAIM_UNWITNESSED", codes)

    def test_a_moved_frozen_spec_is_reported(self) -> None:
        self.log({"event": "anchor_checked", "turn": 1, "outcome": "green",
                  "exit_code": 0, "spec_digest": "not-the-current-digest"})
        self.claim(1, "green")
        self.assertIn("FROZEN_SPEC_CHANGED", self.audit_codes())

    def test_an_unchanged_frozen_spec_is_not_reported(self) -> None:
        digest = va.frozen_digest(self.artifact.read_text(encoding="utf-8"))
        self.log({"event": "anchor_checked", "turn": 1, "outcome": "green",
                  "exit_code": 0, "spec_digest": digest})
        self.claim(1, "green")
        self.assertNotIn("FROZEN_SPEC_CHANGED", self.audit_codes())

    def test_no_history_is_itself_the_finding(self) -> None:
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: None)
        (outside / "demo.goal.md").write_text(GOOD_GOAL, encoding="utf-8")
        (outside / "demo.decisions.md").write_text(GOOD_DECISIONS, encoding="utf-8")
        _, findings = va.audit_artifact(outside / "demo.goal.md")
        self.assertIn("HISTORY_UNAVAILABLE", {f.code for f in findings})

    def test_audit_and_status_are_separate_reports(self) -> None:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(self.dir), "--audit", "--status"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("separate reports", result.stderr)


if __name__ == "__main__":
    unittest.main()


class WorkflowAnchorTests(Harness):
    def test_workflow_without_an_anchor_comment_is_reported(self) -> None:
        self.write("wa.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "wa.workflow.js", GOOD_WORKFLOW.replace("// anchor: `pnpm test -- --run`\n", "")
        )
        self.assertIn("ANCHOR_MISSING", self.codes(path))

    def test_workflow_anchor_must_name_a_command(self) -> None:
        self.write("wb.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "wb.workflow.js",
            GOOD_WORKFLOW.replace("// anchor: `pnpm test -- --run`", "// anchor: it feels right"),
        )
        self.assertIn("ANCHOR_NOT_EXECUTABLE", self.codes(path))


class StatusTests(Harness):
    def test_status_reports_shape_anchor_and_stop_condition(self) -> None:
        self.write("weekly-dep-upgrade.decisions.md", GOOD_DECISIONS)
        self.write("weekly-dep-upgrade.goal.md", GOOD_GOAL)
        self.write("fix-flaky-tests.decisions.md", GOOD_DECISIONS)
        self.write("fix-flaky-tests.workflow.js", GOOD_WORKFLOW)
        self.write("cross-vendor-audit.decisions.md", GOOD_DECISIONS)
        self.write("cross-vendor-audit.delegation.md", GOOD_DELEGATION)

        state = va.status_paths([str(self.dir)])
        by_slug = {item["slug"]: item for item in state["artifacts"]}
        self.assertEqual(
            {"weekly-dep-upgrade", "fix-flaky-tests", "cross-vendor-audit"},
            set(by_slug),
        )

        loop = by_slug["weekly-dep-upgrade"]
        self.assertEqual("loop", loop["shape"])
        self.assertIn("pnpm test", loop["anchor"])
        self.assertIn("pnpm audit", loop["stop_condition"])
        self.assertEqual(2, loop["decisions"])
        # What it is aiming at next is the most useful single line about a goal
        # already in flight, so status shows it rather than counting it.
        self.assertEqual(
            "get `packages/api` to a green anchor with `@types/node` pinned at 20",
            loop["next"],
        )

        graph = by_slug["fix-flaky-tests"]
        self.assertEqual("graph-single-vendor", graph["shape"])
        self.assertEqual(["Triage", "Verify"], graph["phases"])
        self.assertIn("pnpm test", graph["anchor"])

        star = by_slug["cross-vendor-audit"]
        self.assertEqual("graph-star", star["shape"])
        self.assertEqual(["codex", "kimi"], star["workers"])

    def test_status_carries_validation_findings(self) -> None:
        self.write("lonely.goal.md", GOOD_GOAL)
        state = va.status_paths([str(self.dir)])
        self.assertFalse(state["ok"])
        self.assertIn(
            "PAIRED_DECISIONS_MISSING",
            {f["code"] for f in state["findings"]},
        )

    def test_status_does_not_run_anchors_by_default(self) -> None:
        witness = self.dir / "anchor-ran"
        self.write("side.decisions.md", GOOD_DECISIONS)
        self.write(
            "side.goal.md",
            GOOD_GOAL.replace(
                "```\npnpm test -- --run\n```", f"```\ntouch {witness}\n```"
            ),
        )
        state = va.status_paths([str(self.dir)])
        self.assertFalse(witness.exists(), "the validator must not execute an anchor unasked")
        self.assertIsNone(state["artifacts"][0]["anchor_result"])

    def test_status_runs_anchors_only_when_asked(self) -> None:
        self.write("run.decisions.md", GOOD_DECISIONS)
        self.write(
            "run.goal.md",
            GOOD_GOAL.replace("```\npnpm test -- --run\n```", "```\nexit 3\n```"),
        )
        state = va.status_paths([str(self.dir)], run_anchors=True)
        result = state["artifacts"][0]["anchor_result"]
        self.assertIsNotNone(result)
        self.assertEqual(3, result["exit_code"])
        self.assertEqual("exit 3", result["command"])

    def test_cli_status_prints_json_and_exits_zero_when_clean(self) -> None:
        self.write("c.decisions.md", GOOD_DECISIONS)
        self.write("c.workflow.js", GOOD_WORKFLOW)
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(self.dir), "--status", "--json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('"shape": "graph-single-vendor"', result.stdout)

    def test_cli_status_is_readable_without_json(self) -> None:
        self.write("c.decisions.md", GOOD_DECISIONS)
        self.write("c.goal.md", GOOD_GOAL)
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(self.dir), "--status"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("loop", result.stdout)
        self.assertIn("c", result.stdout)


class CarryOverTests(Harness):
    def test_unattended_loop_needs_a_carry_over_section(self) -> None:
        self.write("co.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "co.goal.md", GOOD_GOAL.replace("## Carry-over", "## Random notes")
        )
        self.assertIn("CARRYOVER_MISSING", self.codes(path))

    def test_one_shot_goal_needs_no_carry_over(self) -> None:
        self.write("os.decisions.md", GOOD_DECISIONS)
        without_cadence = GOOD_GOAL.split("## Cadence")[0] + """## Handoff

```
/goal Fix the failing test until `pytest -q` exits 0.
```
"""
        path = self.write("os.goal.md", without_cadence)
        report = va.validate_paths([str(path)])
        self.assertTrue(report.ok, [f.as_dict() for f in report.findings])

    def test_scheduled_loop_also_needs_carry_over(self) -> None:
        self.write("sc.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "sc.goal.md",
            GOOD_GOAL.replace("`/loop 1w`", "`/schedule` every Monday").replace(
                "## Carry-over", "## Random notes"
            ),
        )
        self.assertIn("CARRYOVER_MISSING", self.codes(path))

    def test_carry_over_must_say_it_is_read_and_rewritten(self) -> None:
        self.write("cr.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "cr.goal.md",
            GOOD_GOAL.replace(
                "Read this before acting; rewrite it before finishing. "
                "Drop anything no longer true.\n",
                "",
            ),
        )
        self.assertIn("CARRYOVER_NOT_WIRED", self.codes(path))

    def test_carry_over_needs_both_sub_sections(self) -> None:
        self.write("cs.decisions.md", GOOD_DECISIONS)
        path = self.write("cs.goal.md", GOOD_GOAL.replace("### Lessons", "### Notes"))
        self.assertIn("CARRYOVER_SECTIONS_MISSING", self.codes(path))

    def test_more_than_three_lessons_is_reported(self) -> None:
        """Reflexion bounds its reflection memory at 1-3 entries; so do we."""
        self.write("le.decisions.md", GOOD_DECISIONS)
        bloat = "\n".join(f"- lesson {n} because reason {n} - do X" for n in range(4))
        path = self.write(
            "le.goal.md",
            GOOD_GOAL.replace(
                "- `@types/node` 22 breaks tsconfig because the bundler resolver rejects its new\n"
                "  conditional exports - pin at 20 and revisit when tsconfig moves to `node20`",
                bloat,
            ),
        )
        self.assertIn("LESSONS_UNPRUNED", self.codes(path))

    def test_three_lessons_is_allowed(self) -> None:
        self.write("l3.decisions.md", GOOD_DECISIONS)
        three = "\n".join(f"- lesson {n} because reason {n} - do X" for n in range(3))
        path = self.write(
            "l3.goal.md",
            GOOD_GOAL.replace(
                "- `@types/node` 22 breaks tsconfig because the bundler resolver rejects its new\n"
                "  conditional exports - pin at 20 and revisit when tsconfig moves to `node20`",
                three,
            ),
        )
        self.assertNotIn("LESSONS_UNPRUNED", self.codes(path))

    def test_an_unpruned_state_list_is_reported(self) -> None:
        self.write("st.decisions.md", GOOD_DECISIONS)
        bloat = "\n".join(f"- state item {n}" for n in range(12))
        path = self.write(
            "st.goal.md",
            GOOD_GOAL.replace("- remaining after iteration 6: `packages/api`", bloat),
        )
        self.assertIn("STATE_UNPRUNED", self.codes(path))

    def test_status_reports_state_and_lessons_separately(self) -> None:
        self.write("sp.decisions.md", GOOD_DECISIONS)
        self.write("sp.goal.md", GOOD_GOAL)
        item = va.status_paths([str(self.dir)])["artifacts"][0]
        self.assertEqual(1, item["carry_over"]["state"])
        self.assertEqual(1, item["carry_over"]["lessons"])

    def test_status_reports_the_cadence(self) -> None:
        self.write("weekly-dep-upgrade.decisions.md", GOOD_DECISIONS)
        self.write("weekly-dep-upgrade.goal.md", GOOD_GOAL)
        item = va.status_paths([str(self.dir)])["artifacts"][0]
        self.assertEqual("/loop 1w", item["cadence"])


class CadenceTests(Harness):
    """Carry-over is required by the presence of a cadence, not by guessing at
    scheduler keywords. A goal that repeats needs carried state; a one-shot does not."""

    def test_any_cadence_requires_carry_over(self) -> None:
        self.write("c1.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "c1.goal.md",
            GOOD_GOAL.replace("`/loop 1w`", "Started by hand, roughly weekly.").replace(
                "## Carry-over", "## Notes"
            ),
        )
        self.assertIn("CARRYOVER_MISSING", self.codes(path))

    def test_cadence_wording_is_not_pattern_matched(self) -> None:
        """No keyword list: a cadence described in any words still requires it."""
        for i, wording in enumerate(
            (
                "Whenever I get around to it.",
                "Each sprint, when I remember.",
                "`cron: 0 9 * * 1`",
                "Twice a release.",
            )
        ):
            with self.subTest(wording=wording):
                self.write(f"w{i}.decisions.md", GOOD_DECISIONS)
                path = self.write(
                    f"w{i}.goal.md",
                    GOOD_GOAL.replace("`/loop 1w`", wording).replace(
                        "## Carry-over", "## Notes"
                    ),
                )
                self.assertIn("CARRYOVER_MISSING", self.codes(path))

    def test_no_cadence_means_no_carry_over_required(self) -> None:
        self.write("c2.decisions.md", GOOD_DECISIONS)
        one_shot = GOOD_GOAL.split("## Cadence")[0] + """## Handoff

```
/goal Fix the failing test until `pytest -q` exits 0.
```
"""
        path = self.write("c2.goal.md", one_shot)
        report = va.validate_paths([str(path)])
        self.assertTrue(report.ok, [f.as_dict() for f in report.findings])


class RunnableHandoffTests(Harness):
    def test_handoff_without_a_runnable_block_is_reported(self) -> None:
        self.write("nh.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "nh.goal.md",
            GOOD_GOAL.replace(
                "```\n/goal Upgrade dependencies until the audit is clean. You have not "
                "met this goal until\n`pnpm audit --audit-level=high` reports 0 findings "
                "in this session.\n```",
                "Just run it the usual way each week.",
            ),
        )
        self.assertIn("HANDOFF_NOT_RUNNABLE", self.codes(path))

    def test_status_reports_the_start_command(self) -> None:
        self.write("sc2.decisions.md", GOOD_DECISIONS)
        self.write("sc2.goal.md", GOOD_GOAL)
        state = va.status_paths([str(self.dir)])
        self.assertTrue(
            state["artifacts"][0]["start_command"].startswith("/goal "),
            state["artifacts"][0]["start_command"],
        )

    def test_a_one_shot_goal_still_needs_a_handoff(self) -> None:
        """The handoff is the line the owner pastes into the CLI. Always required."""
        self.write("oneshot.decisions.md", GOOD_DECISIONS)
        path = self.write("oneshot.goal.md", GOOD_GOAL.split("## Cadence")[0])
        self.assertIn("HANDOFF_MISSING", self.codes(path))

    def test_goal_artifact_must_have_a_handoff(self) -> None:
        self.write("noh.decisions.md", GOOD_DECISIONS)
        path = self.write("noh.goal.md", GOOD_GOAL.replace("## Handoff", "## Notes"))
        self.assertIn("HANDOFF_MISSING", self.codes(path))
