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
    / "ultra-goal"
    / "skills"
    / "ultragoal"
    / "scripts"
    / "validate_artifact.py"
)

sys.path.insert(0, str(VALIDATOR.parent))
import validate_artifact as va  # noqa: E402


GOOD_WORKFLOW = """// goal: `fix-flaky-tests.goal.md`
// anchor: `pnpm test -- --run`
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

| Decision | Rejected | Why | Who |
| --- | --- | --- | --- |
| Graph, pure Claude Workflow | Star delegation across vendors | No vendor-specific tool is needed | owner |
| Split by suite | Split by phase (triage/fix/verify) | Phases share context; suites isolate it | owner |
"""

GOOD_GOAL = """# Goal: weekly-dep-upgrade

## Intent

Keep production dependencies free of high-severity advisories without breaking the build.

## Boundary

Only `package.json` and the lockfile. Never touch application source, CI config, or pinned
transitive overrides that carry a comment.

## Stop condition

Stop when `pnpm audit --audit-level=high` reports 0 findings, or after 6 turns.
success: verified
ceiling: 6

## Anchor

```
pnpm test -- --run
```

## Roles

- **lead**: this session with the owner. fallback: none; an interview cannot be delegated.
- **carry out**: this session, code and tests together, test first. fallback: none.
- **reviewer**: a subagent with a fresh context. fallback: this session re-reading cold,
  and say the review was not independent.
- **critic**: a second subagent. fallback: none; a round without a critic is unreviewed.

## Means

- `[load-bearing]` move versions through `package.json` and the lockfile only
- `[droppable]` clear every advisory in one pass - drop it when one dependency needs a
  source change to move

## Verification

A reviewer with a fresh context reviews the diff; a critic then audits that review rather
than the code, classifying each point as agreement, evidence-backed disagreement, or
concern-based disagreement. At most 5 inner rounds.

```json
{"source":"external","basis":"Independent fixture command.","protected":[],"covers":{"core":"anchor","api":"anchor"},"review":null}
```

## Acceptance

- [x] core: `packages/core` current with a green anchor
- [ ] api: `packages/api` current with a green anchor

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

goal: `settlement-audit.goal.md`

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
findings, accept and stop. A report ends in exactly one outcome: completed, failed,
input-required (name what is needed), or rejected (say why). Silence is unknown;
query actual worker state before deciding the next action.
"""


class Harness(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, name: str, text: str) -> Path:
        path = self.dir / name
        # Attachment fixtures include the contract they execute. Missing or
        # mismatched shared contracts are tested directly in test_goal_contract.
        for suffix in (".workflow.js", ".delegation.md"):
            if name.endswith(suffix):
                import re
                shared = name[:-len(suffix)] + ".goal.md"
                text = re.sub(r"goal: `[^`]+`", f"goal: `{shared}`", text)
                contract = self.dir / shared
                if not contract.exists():
                    contract.write_text(GOOD_GOAL)
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
            ).replace("success: verified\nceiling: 6", ""),
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
    def test_goal_allows_one_independent_reviewer(self) -> None:
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
        self.assertEqual([], self.codes(path))

    def test_single_check_does_not_need_an_inner_round_cap(self) -> None:
        self.write("v2.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "v2.goal.md",
            GOOD_GOAL.replace("At most 5 inner rounds.", "Run this check once."),
        )
        self.assertEqual([], self.codes(path))


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

    def arm(self, digest: str | None = None) -> None:
        """Write the arming-time spec baseline, exactly as `goal_run.py arm`
        does: since round 5 the audit derives the run's authorized baseline
        from this file and never from the first anchor check - a run can
        write the log, so the first row found there laundered whatever it
        said (round-4 F3)."""
        text = digest if digest is not None else self.digest()
        (self.dir / "demo.spec.baseline").write_text(text + "\n", "utf-8")

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
        self.arm()
        self.log({"event": "anchor_checked", "turn": 1, "outcome": "green",
                  "exit_code": 0, "spec_digest": self.digest()})
        self.claim(1, "green")
        # Nothing about the turns - the one finding left is the review
        # artifact this fixture never wrote (GOOD_GOAL declares
        # `## Verification`), which is the new contract: a begun run that
        # declares a reviewer owes a review file, and its absence is an
        # advisory, not a verdict on the turns.
        self.assertEqual(["REVIEW_UNEVIDENCED"], self.audit_codes())

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
        self.arm()
        self.log({"event": "anchor_checked", "turn": 1, "outcome": "red",
                  "exit_code": 1, "spec_digest": self.digest()})
        self.claim(1, "green")
        self.claim(1, "red")
        # No CLAIM_CONTRADICTED: the amended commit is the claim audited, and
        # REVIEW_UNEVIDENCED is the same fixture artifact as its neighbour.
        self.assertEqual(["REVIEW_UNEVIDENCED"], self.audit_codes())

    def test_claims_with_no_event_log_at_all_are_reported_as_ungated(self) -> None:
        self.claim(1, "green")
        codes = self.audit_codes()
        self.assertIn("GATE_NEVER_RAN", codes)
        self.assertNotIn("CLAIM_UNWITNESSED", codes)

    def test_a_moved_frozen_spec_is_reported(self) -> None:
        """The comparison is armed-digest-file versus artifact-on-disk now -
        never the first digest found in the event log, which the run can
        write (round-4 F3: a laundered first row made the audit bless it)."""
        self.arm()
        self.log({"event": "anchor_checked", "turn": 1, "outcome": "green",
                  "exit_code": 0, "spec_digest": "not-the-current-digest"})
        self.claim(1, "green")
        # The log row's digest is deliberately wrong and must not matter.
        # Move the artifact for real: edit a frozen section after arming.
        self.artifact.write_text(
            self.artifact.read_text(encoding="utf-8").replace(
                "## Intent", "## Intent (edited)"),
            encoding="utf-8",
        )
        self.assertIn("FROZEN_SPEC_CHANGED", self.audit_codes())
        audit = va.audit_artifact(self.artifact)[0]
        self.assertEqual(self.digest_of_good_goal_armed(), audit["spec_digest_armed"])

    def digest_of_good_goal_armed(self) -> str:
        return va.frozen_digest(GOOD_GOAL)

    def test_a_run_with_attempts_and_no_armed_baseline_is_reported(self) -> None:
        """Round-4 F3, audit half: completion attempts with no arming-time
        baseline mean the run was never verifiable against the owner's spec -
        the gate refuses such claims, and the audit names the gap instead of
        quietly deriving a baseline from the log."""
        self.log({"event": "anchor_checked", "turn": 1, "outcome": "green",
                  "exit_code": 0, "spec_digest": self.digest()})
        self.claim(1, "green")
        self.assertIn("SPEC_BASELINE_MISSING", self.audit_codes())

    def test_a_turn_parked_on_the_continuation_budget_is_reported(self) -> None:
        """A budget-spent release is the gate's own measurement of a run that
        keeps ending its host turns with the anchor still red. `--audit`
        surfaces it as an advisory: it is not a verdict on the work, but a run
        whose every turn parks is not advancing even when every turn works."""
        self.log({"event": "anchor_checked", "turn": 1, "outcome": "red",
                  "exit_code": 1, "spec_digest": self.digest(), "blocked": True},
                 {"event": "continuation_budget_spent", "turn": 2, "host": "kimi",
                  "budget": 1, "outcome": "red", "exit_code": 1})
        self.claim(2, "red")
        codes = self.audit_codes()
        self.assertIn("CONTINUATION_BUDGET_SPENT", codes)
        severity = {f.code: f.severity for f in va.audit_artifact(self.artifact)[1]}
        self.assertEqual("advisory", severity["CONTINUATION_BUDGET_SPENT"])

    def test_an_unchanged_frozen_spec_is_not_reported(self) -> None:
        digest = va.frozen_digest(self.artifact.read_text(encoding="utf-8"))
        self.log({"event": "anchor_checked", "turn": 1, "outcome": "green",
                  "exit_code": 0, "spec_digest": digest})
        self.claim(1, "green")
        self.assertNotIn("FROZEN_SPEC_CHANGED", self.audit_codes())

    def test_a_declared_review_with_no_artifact_is_reported(self) -> None:
        """A delegated round can succeed and produce nothing: the round-2
        review of this very mission returned exit 0, status success, and no
        file. No hook can see that - PostToolUseFailure fires on failures
        only, and the one event that fires on success is deliberately not
        registered - so the only real detector is the expected artifact's
        absence, and `--audit` is where the owner must meet it. A run that
        declares a reviewer round owes a review file; missing is unevidenced,
        not clean."""
        self.log({"event": "anchor_checked", "turn": 1, "outcome": "red",
                  "exit_code": 1, "spec_digest": self.digest()})
        self.claim(1, "red")
        codes = self.audit_codes()
        self.assertIn("REVIEW_UNEVIDENCED", codes)
        severity = {f.code: f.severity for f in va.audit_artifact(self.artifact)[1]}
        self.assertEqual("advisory", severity["REVIEW_UNEVIDENCED"])

    def test_a_review_artifact_on_disk_settles_the_finding(self) -> None:
        self.log({"event": "anchor_checked", "turn": 1, "outcome": "red",
                  "exit_code": 1, "spec_digest": self.digest()})
        self.claim(1, "red")
        work = self.dir / ".work"
        work.mkdir(exist_ok=True)
        (work / "demo-review.md").write_text(
            "# Review: demo - round 1\n\n## Findings\n- none\n", encoding="utf-8"
        )
        self.assertNotIn("REVIEW_UNEVIDENCED", self.audit_codes())

    def test_a_run_that_never_started_owes_no_review_yet(self) -> None:
        """The finding names a round that came due and left nothing. Before
        the first check or claim there is no run, and a mid-run audit of a run
        that has not proposed completion has no review to owe - the guard is
        the run having begun, nothing smarter."""
        self.assertNotIn("REVIEW_UNEVIDENCED", self.audit_codes())

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


class ChallengeTests(Harness):
    """A challenge is the run's objection, not the owner's decision."""

    RECORD = GOOD_DECISIONS + """

## Challenges from the run

| Term challenged | What the run hit | What would settle it |
| --- | --- | --- |
| Only the lockfile | `node-fetch` 3 needs two import sites changed, so the stated scope makes the advisory unfixable rather than deferred | Widen the scope to those two files, or drop `node-fetch` from this goal |
"""

    def test_a_well_formed_challenge_passes(self) -> None:
        path = self.write("c.decisions.md", self.RECORD)
        report = va.validate_paths([str(path)])
        self.assertTrue(report.ok, report.findings)

    def test_challenges_are_not_counted_as_decisions(self) -> None:
        record = self.write("c.decisions.md", self.RECORD)
        self.write("c.goal.md", GOOD_GOAL)
        state = va.status_paths([str(self.dir)])
        item = next(i for i in state["artifacts"] if i["slug"] == "c")
        self.assertEqual(va.decision_count(record), item["decisions"])
        self.assertEqual(1, item["challenges"])
        # The whole point: an unresolved objection must not read as settled.
        self.assertEqual(2, item["decisions"])

    def test_a_blank_cell_makes_it_a_complaint_not_an_objection(self) -> None:
        path = self.write(
            "c.decisions.md",
            self.RECORD.replace(
                "| Widen the scope to those two files, or drop `node-fetch` from this goal |",
                "|  |",
            ),
        )
        self.assertIn("CHALLENGE_TABLE_MALFORMED", self.codes(path))

    def test_a_missing_column_is_reported(self) -> None:
        path = self.write(
            "c.decisions.md",
            self.RECORD.replace("| What would settle it |", "|"),
        )
        self.assertIn("CHALLENGE_TABLE_MALFORMED", self.codes(path))

    def test_no_challenges_section_is_normal(self) -> None:
        path = self.write("c.decisions.md", GOOD_DECISIONS)
        report = va.validate_paths([str(path)])
        self.assertTrue(report.ok, report.findings)
        self.assertEqual(0, va.challenge_count(path))


class AcceptanceTests(Harness):
    """The stop condition, enumerated - required only where it earns its keep.

    One sentence plus one anchor answers "is the whole thing done" and cannot
    answer "which parts are". The second granularity is where a long run
    declares victory on the strength of the part it finished.
    """

    def test_a_goal_with_a_cadence_needs_it(self) -> None:
        self.write("a.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "a.goal.md", GOOD_GOAL.replace("## Acceptance", "## Notes")
        )
        self.assertIn("ACCEPTANCE_MISSING", self.codes(path))

    def test_a_one_shot_goal_still_needs_recovery(self) -> None:
        """A single start can still lose context or be interrupted."""
        self.write("a.decisions.md", GOOD_DECISIONS)
        one_shot = GOOD_GOAL
        for section in ("## Acceptance", "## Cadence", "## Carry-over"):
            one_shot = one_shot.replace(section, "## Notes", 1)
        path = self.write("a.goal.md", one_shot)
        codes = self.codes(path)
        self.assertNotIn("ACCEPTANCE_MISSING", codes)
        self.assertIn("CARRYOVER_MISSING", codes)

    def test_a_numbered_acceptance_list_is_a_plan(self) -> None:
        self.write("a.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "a.goal.md",
            GOOD_GOAL.replace(
                "- [x] core: `packages/core` current with a green anchor",
                "1. `packages/core` current with a green anchor",
            ),
        )
        self.assertIn("ACCEPTANCE_ORDERED", self.codes(path))

    def test_a_line_with_no_state_is_reported(self) -> None:
        self.write("a.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "a.goal.md",
            GOOD_GOAL.replace(
                "- [ ] api: `packages/api` current with a green anchor",
                "- `packages/api` current with a green anchor",
            ),
        )
        self.assertIn("ACCEPTANCE_UNSTATED", self.codes(path))

    def test_both_states_are_accepted(self) -> None:
        self.write("a.decisions.md", GOOD_DECISIONS)
        path = self.write("a.goal.md", GOOD_GOAL)
        self.assertNotIn("ACCEPTANCE_UNSTATED", self.codes(path))


class SeverityTests(Harness):
    """Two different things were being reported as the same thing.

    A missing anchor means the artifact cannot do its job. Nine state entries
    against a budget this Skill invented is a sentence worth saying - and
    failing over it would be the Skill enforcing its own guess as a fact.
    """

    def test_an_invented_budget_is_advisory_and_does_not_fail(self) -> None:
        self.write("s.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "s.goal.md",
            GOOD_GOAL.replace(
                "- remaining after iteration 6: `packages/api`",
                "\n".join(f"- fact {i}" for i in range(10)),
            ),
        )
        report = va.validate_paths([str(path)])
        self.assertIn("STATE_UNPRUNED", {f.code for f in report.findings})
        self.assertTrue(report.ok, "an advisory must not fail the artifact")
        self.assertEqual([], report.errors)
        self.assertEqual(1, len(report.advisories))

    def test_necessary_lessons_above_the_compact_default_remain_valid(self) -> None:
        """A research hyperparameter must not reject necessary recovery facts."""
        self.write("s.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "s.goal.md",
            GOOD_GOAL.replace(
                "- `@types/node` 22 breaks tsconfig because the bundler resolver rejects its new\n  conditional exports - pin at 20 and revisit when tsconfig moves to `node20`",
                "\n".join(f"- cause {i} therefore action {i}" for i in range(5)),
            ),
        )
        report = va.validate_paths([str(path)])
        self.assertIn("LESSONS_UNPRUNED", {f.code for f in report.advisories})
        self.assertTrue(report.ok)
        self.assertEqual([], report.errors)

    def test_the_cli_labels_advisories_and_still_exits_zero(self) -> None:
        self.write("s.decisions.md", GOOD_DECISIONS)
        self.write(
            "s.goal.md",
            GOOD_GOAL.replace(
                "- remaining after iteration 6: `packages/api`",
                "\n".join(f"- fact {i}" for i in range(10)),
            ),
        )
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(self.dir)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("[advisory]", result.stdout)
        self.assertIn("ok (advisories above)", result.stdout)


class AnchorBudgetTests(Harness):
    """How long to wait is the owner's call, not a constant in the gate."""

    def test_a_budget_above_the_hook_timeout_is_flagged_as_useless(self) -> None:
        self.write("b.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "b.goal.md",
            GOOD_GOAL.replace("pnpm test -- --run\n```", "pnpm test -- --run\n```\n\nbudget: 30 minutes"),
        )
        report = va.validate_paths([str(path)])
        codes = {f.code for f in report.findings}
        self.assertIn("ANCHOR_BUDGET_UNREACHABLE", codes)
        # Advisory: the artifact is not broken, the number just has no effect.
        self.assertTrue(report.ok)

    def test_a_budget_inside_the_ceiling_is_silent(self) -> None:
        self.write("b.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "b.goal.md",
            GOOD_GOAL.replace("pnpm test -- --run\n```", "pnpm test -- --run\n```\n\nbudget: 2 minutes"),
        )
        self.assertNotIn("ANCHOR_BUDGET_UNREACHABLE", self.codes(path))


class WorkerOutcomeTests(Harness):
    """A blocked worker and a finished one must not look alike."""

    def test_undeclared_outcomes_are_reported(self) -> None:
        self.write("w.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "w.delegation.md",
            GOOD_DELEGATION.replace(
                "A report ends in exactly one outcome: completed, failed,\ninput-required (name what is needed), or rejected (say why). Silence is unknown;\nquery actual worker state before deciding the next action.",
                "",
            ),
        )
        report = va.validate_paths([str(path)])
        self.assertIn("WORKER_OUTCOMES_UNDECLARED", {f.code for f in report.findings})
        message = next(
            f.message for f in report.findings
            if f.code == "WORKER_OUTCOMES_UNDECLARED"
        )
        for name in ("input-required", "rejected"):
            self.assertIn(name, message)

    def test_the_shipped_vocabulary_satisfies_it(self) -> None:
        self.write("w.decisions.md", GOOD_DECISIONS)
        path = self.write("w.delegation.md", GOOD_DELEGATION)
        report = va.validate_paths([str(path)])
        self.assertTrue(report.ok, report.findings)


class MultilineAnchorTests(Harness):
    """The validator refuses what the gate will not guess at."""

    def test_two_commands_in_the_fence_is_an_error(self) -> None:
        self.write("m.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "m.goal.md",
            GOOD_GOAL.replace(
                "```\npnpm test -- --run\n```",
                "```\npnpm test -- --run\npnpm verify\n```",
            ),
        )
        report = va.validate_paths([str(path)])
        self.assertIn("ANCHOR_MULTILINE", {f.code for f in report.errors})

    def test_joining_with_and_is_accepted(self) -> None:
        self.write("m.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "m.goal.md",
            GOOD_GOAL.replace(
                "pnpm test -- --run\n```", "pnpm test -- --run && pnpm verify\n```"
            ),
        )
        self.assertNotIn("ANCHOR_MULTILINE", self.codes(path))


class DecisionAuthorTests(Harness):
    """Told apart because a real run could not tell them apart.

    Its first artifact carried "(my inline assumption, the owner did not
    object)" and "(I set this outright, not offered as an option)" inside Why
    cells, because the record had nowhere to put the difference. Both were the
    right call; neither was a decision the owner made.
    """

    ASSUMED = GOOD_DECISIONS + (
        "| Offline-reproducible anchor | Live data as the anchor's input | "
        "A network-dependent anchor keeps returning unknown | agent |\n"
    )

    def test_a_three_column_record_is_no_longer_enough(self) -> None:
        path = self.write(
            "d.decisions.md",
            GOOD_DECISIONS.replace(
                "| Decision | Rejected | Why | Who |", "| Decision | Rejected | Why |"
            ),
        )
        self.assertIn("DECISIONS_TABLE_MALFORMED", self.codes(path))

    def test_who_must_be_owner_or_agent(self) -> None:
        path = self.write("d.decisions.md", GOOD_DECISIONS.replace("| owner |", "| me |"))
        self.assertIn("DECISION_AUTHOR_UNCLEAR", self.codes(path))

    def test_an_agent_row_is_legitimate(self) -> None:
        """The interview cannot ask everything, and a hard prohibition on
        irreversible effects should be set rather than offered."""
        path = self.write("d.decisions.md", self.ASSUMED)
        report = va.validate_paths([str(path)])
        self.assertTrue(report.ok, report.findings)
        self.assertEqual(1, va.assumed_count(path))

    def test_assumptions_are_counted_apart_from_decisions(self) -> None:
        record = self.write("d.decisions.md", self.ASSUMED)
        self.write("d.goal.md", GOOD_GOAL)
        state = va.status_paths([str(self.dir)])
        item = next(i for i in state["artifacts"] if i["slug"] == "d")
        self.assertEqual(3, item["decisions"])
        self.assertEqual(1, item["assumed"])
        self.assertEqual(va.assumed_count(record), item["assumed"])


class TargetDiscoveryTests(unittest.TestCase):
    """Which agents a machine has is a fact, so it is asked rather than frozen.

    Hardcoding the list was one of this Skill's own audited bets: a seventh
    vendor would have failed UNKNOWN_TARGET for the crime of existing.
    """

    def test_targets_come_from_the_tool_when_it_answers(self) -> None:
        names, from_tool = va.known_targets()
        self.assertTrue(names)
        if from_tool:
            self.assertIn("claude", names)
        else:
            self.assertEqual(va.FALLBACK_TARGETS, names)

    def test_the_fallback_is_used_and_downgraded_when_the_tool_is_absent(self) -> None:
        import subprocess as sp
        original = sp.run

        def missing(*args, **kwargs):
            raise OSError("agent-delegate not installed")

        va.subprocess.run = missing
        try:
            names, from_tool = va.known_targets()
            self.assertEqual(va.FALLBACK_TARGETS, names)
            self.assertFalse(from_tool)
        finally:
            va.subprocess.run = original


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

        graph = next(item for item in state["artifacts"] if item["kind"] == "workflow")
        self.assertEqual("graph-single-vendor", graph["shape"])
        self.assertEqual(["Triage", "Verify"], graph["phases"])
        self.assertIn("pnpm test", graph["anchor"])

        star = next(item for item in state["artifacts"] if item["kind"] == "delegation")
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

    def test_status_reports_inactive_binding_without_changing_run_files(self) -> None:
        self.dir = self.dir / ".goals"
        self.dir.mkdir()
        goal = self.write("c.goal.md", GOOD_GOAL)
        self.write("c.decisions.md", GOOD_DECISIONS)
        self.write("another-goal.goal.md", GOOD_GOAL)
        self.write("another-goal.decisions.md", GOOD_DECISIONS)
        self.write("c.candidate", "keep this claim\n")
        self.write("c.events.jsonl", '{"event": "sentinel"}\n')
        self.write("c.spec.baseline", "keep this baseline\n")
        marker = self.dir / "active"
        for contents, expected in (
            ("c\n", True),
            ("c\nsession ../invalid\n", True),
            ("c\nsession native-session-1\n", False),
            ("another-goal\n", False),
            (None, False),
        ):
            with self.subTest(marker=contents):
                if contents is None:
                    marker.unlink()
                else:
                    marker.write_text(contents)
                before = {p.name: p.read_bytes() for p in self.dir.iterdir()}
                state = va.status_paths([str(goal)])
                findings = [
                    f for f in state["findings"]
                    if f["code"] == "SESSION_BINDING_INVALID"
                ]
                self.assertEqual(int(expected), len(findings))
                self.assertTrue(state["ok"])
                self.assertIsNone(state["artifacts"][0]["anchor_result"])
                if expected:
                    self.assertEqual("advisory", findings[0]["severity"])
                    self.assertEqual(str(marker), findings[0]["path"])
                    self.assertIn("hooks are inactive", findings[0]["message"])
                    self.assertIn("goal_run.py rebind c", findings[0]["message"])
                self.assertEqual(
                    before, {p.name: p.read_bytes() for p in self.dir.iterdir()}
                )

    def test_status_checks_attachment_binding_without_duplicate_findings(self) -> None:
        self.dir = self.dir / ".goals"
        self.dir.mkdir()
        workflow = self.write("c.workflow.js", GOOD_WORKFLOW)
        delegation = self.write("c.delegation.md", GOOD_DELEGATION)
        self.write("c.decisions.md", GOOD_DECISIONS)
        self.write("active", "c\n")
        for paths in ([workflow], [delegation], [self.dir]):
            with self.subTest(paths=paths):
                state = va.status_paths([str(p) for p in paths])
                self.assertEqual(
                    1,
                    sum(f["code"] == "SESSION_BINDING_INVALID" for f in state["findings"]),
                )

    def test_cli_status_binding_advisory_is_visible_in_text_and_json(self) -> None:
        self.dir = self.dir / ".goals"
        self.dir.mkdir()
        self.write("c.goal.md", GOOD_GOAL)
        self.write("c.decisions.md", GOOD_DECISIONS)
        self.write("active", "c\n")
        for extra in ([], ["--json"]):
            with self.subTest(extra=extra):
                result = subprocess.run(
                    [sys.executable, str(VALIDATOR), str(self.dir), "--status", *extra],
                    capture_output=True, text=True,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("SESSION_BINDING_INVALID", result.stdout)
                self.assertIn("goal_run.py rebind c", result.stdout)


class CarryOverTests(Harness):
    def test_unattended_loop_needs_a_carry_over_section(self) -> None:
        self.write("co.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "co.goal.md", GOOD_GOAL.replace("## Carry-over", "## Random notes")
        )
        self.assertIn("CARRYOVER_MISSING", self.codes(path))

    def test_one_shot_goal_needs_carry_over(self) -> None:
        self.write("os.decisions.md", GOOD_DECISIONS)
        without_cadence = GOOD_GOAL.split("## Cadence")[0] + """## Handoff

```
/goal Fix the failing test until `pytest -q` exits 0.
```
"""
        path = self.write("os.goal.md", without_cadence)
        report = va.validate_paths([str(path)])
        self.assertIn("CARRYOVER_MISSING", [f.code for f in report.findings])

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
    """Recovery is required independently of cadence or scheduler keywords."""

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

    def test_no_cadence_still_requires_carry_over(self) -> None:
        self.write("c2.decisions.md", GOOD_DECISIONS)
        one_shot = GOOD_GOAL.split("## Cadence")[0] + """## Handoff

```
/goal Fix the failing test until `pytest -q` exits 0.
```
"""
        path = self.write("c2.goal.md", one_shot)
        report = va.validate_paths([str(path)])
        self.assertIn("CARRYOVER_MISSING", [f.code for f in report.findings])


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


class RolesSectionTests(Harness):
    """Every role names what happens when it cannot run."""

    def test_a_missing_roles_section_is_reported(self) -> None:
        self.write("r.decisions.md", GOOD_DECISIONS)
        path = self.write("r.goal.md", GOOD_GOAL.replace("## Roles", "## Team"))
        self.assertIn("ROLES_MISSING", self.codes(path))

    def test_a_role_without_a_fallback_is_reported(self) -> None:
        self.write("r.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "r.goal.md",
            GOOD_GOAL.replace(
                "- **critic**: a second subagent. fallback: none; a round without a critic is unreviewed.",
                "- **critic**: a second subagent.",
            ),
        )
        self.assertIn("ROLE_FALLBACK_MISSING", self.codes(path))

    def test_fallback_none_is_a_legitimate_answer(self) -> None:
        self.write("r.decisions.md", GOOD_DECISIONS)
        path = self.write("r.goal.md", GOOD_GOAL)
        self.assertNotIn("ROLE_FALLBACK_MISSING", self.codes(path))

    def test_a_wrapped_fallback_still_counts(self) -> None:
        """The checker reads whole bullets: four correctly-written roles were
        reported as missing their fallback because the word had wrapped."""
        blocks = va.bullet_blocks(
            "- **reviewer**: a subagent with a fresh context.\n"
            "  fallback: this session re-reading cold, and say it was not independent.\n"
        )
        self.assertEqual(1, len(blocks))
        self.assertIn("fallback:", blocks[0])


class FrozenSectionBudgetTests(unittest.TestCase):
    """An advisory, not an error: the injection happens either way.

    Measured on the first real artifact, whose `## Anchor` was 7,752 characters
    because the check contracts lived inside it - 97% of the target, so every
    restart lost everything else.
    """

    def _report(self, goal: str) -> va.Report:
        with tempfile.TemporaryDirectory() as tmp:
            goals = Path(tmp) / ".goals"
            goals.mkdir()
            (goals / "demo.goal.md").write_text(goal, encoding="utf-8")
            (goals / "demo.decisions.md").write_text(
                "| Decision | Rejected | Why | Who |\n|---|---|---|---|\n"
                "| a | b | c | owner |\n",
                encoding="utf-8",
            )
            return va.validate_paths([str(goals)])

    def test_an_oversized_frozen_section_is_advisory_not_error(self) -> None:
        goal = GOOD_GOAL.replace("## Anchor", "## Anchor\n\n" + ("pad. " * 3000), 1)
        report = self._report(goal)
        codes = {f.code: f for f in report.findings}
        self.assertIn("FROZEN_SECTIONS_OVER_BUDGET", codes)
        self.assertEqual("advisory", codes["FROZEN_SECTIONS_OVER_BUDGET"].severity)
        self.assertIn("`## Anchor`", codes["FROZEN_SECTIONS_OVER_BUDGET"].message)
        # Advisories must not fail the artifact: it still runs.
        self.assertTrue(report.ok)

    def test_a_normal_artifact_raises_nothing(self) -> None:
        report = self._report(GOOD_GOAL)
        self.assertNotIn(
            "FROZEN_SECTIONS_OVER_BUDGET", {f.code for f in report.findings}
        )
