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
    / "loop-graph-design"
    / "skills"
    / "loop-graph-design"
    / "scripts"
    / "validate_artifact.py"
)

sys.path.insert(0, str(VALIDATOR.parent))
import validate_artifact as va  # noqa: E402


GOOD_WORKFLOW = """export const meta = {
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

## Verification

Delegate review to a fresh agent that never saw the upgrade reasoning.
"""

GOOD_DELEGATION = """# Delegation: cross-vendor-audit

## Worker: codex

- target: codex
- mission: Audit the settlement module for integer overflow
- anchor: `forge test --match-path test/Settlement.t.sol`

## Worker: kimi

- target: kimi
- mission: Audit the same module for reentrancy
- anchor: `forge test --match-path test/Reentrancy.t.sol`
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
    def test_valid_delegation_package_passes(self) -> None:
        self.write("cross-vendor-audit.decisions.md", GOOD_DECISIONS)
        path = self.write("cross-vendor-audit.delegation.md", GOOD_DELEGATION)
        report = va.validate_paths([str(path)])
        self.assertTrue(report.ok, report.findings)

    def test_unknown_target_is_reported(self) -> None:
        self.write("k.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "k.delegation.md", GOOD_DELEGATION.replace("- target: kimi", "- target: gpt5")
        )
        self.assertIn("UNKNOWN_TARGET", self.codes(path))

    def test_worker_without_mission_is_reported(self) -> None:
        self.write("l.decisions.md", GOOD_DECISIONS)
        path = self.write(
            "l.delegation.md",
            GOOD_DELEGATION.replace(
                "- mission: Audit the same module for reentrancy\n", ""
            ),
        )
        self.assertIn("WORKER_FIELD_MISSING", self.codes(path))

    def test_single_worker_is_reported_as_not_a_graph(self) -> None:
        self.write("m.decisions.md", GOOD_DECISIONS)
        single = GOOD_DELEGATION.split("## Worker: kimi")[0]
        path = self.write("m.delegation.md", single)
        self.assertIn("SINGLE_WORKER_DELEGATION", self.codes(path))


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


if __name__ == "__main__":
    unittest.main()
