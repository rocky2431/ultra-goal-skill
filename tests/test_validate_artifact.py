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

## Verification

Delegate review to a fresh agent that never saw the upgrade reasoning.

## Cadence

`/loop 1w`

## Carry-over

Read this before acting; rewrite it before finishing. Drop anything no longer true.

- `@types/node` 22 breaks tsconfig under `moduleResolution: bundler` - do not retry
- remaining after iteration 6: `packages/api`
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
        without_cadence = GOOD_GOAL.split("## Cadence")[0]
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

    def test_an_unpruned_carry_over_is_reported(self) -> None:
        self.write("up.decisions.md", GOOD_DECISIONS)
        bloat = "\n".join(f"- lesson number {n}" for n in range(25))
        path = self.write(
            "up.goal.md",
            GOOD_GOAL.replace("- remaining after iteration 6: `packages/api`", bloat),
        )
        self.assertIn("CARRYOVER_UNPRUNED", self.codes(path))

    def test_status_reports_the_carry_over_size(self) -> None:
        self.write("weekly-dep-upgrade.decisions.md", GOOD_DECISIONS)
        self.write("weekly-dep-upgrade.goal.md", GOOD_GOAL)
        state = va.status_paths([str(self.dir)])
        item = state["artifacts"][0]
        self.assertEqual(2, item["carry_over"])
        self.assertEqual("/loop 1w", item["cadence"])


class HostPortabilityTests(Harness):
    """Unattended means scheduled by anything, not just by a Claude Code command."""

    def _goal_with_cadence(self, name: str, cadence: str, carry_over: bool) -> Path:
        self.write(f"{name}.decisions.md", GOOD_DECISIONS)
        text = GOOD_GOAL.replace("`/loop 1w`", cadence)
        if not carry_over:
            text = text.replace("## Carry-over", "## Notes")
        return self.write(f"{name}.goal.md", text)

    def test_cron_scheduled_loop_needs_carry_over(self) -> None:
        path = self._goal_with_cadence(
            "cron", '`cron: 0 9 * * 1 kimi -p "$(cat prompt.md)"`', carry_over=False
        )
        self.assertIn("CARRYOVER_MISSING", self.codes(path))

    def test_launchd_scheduled_loop_needs_carry_over(self) -> None:
        path = self._goal_with_cadence(
            "launchd", "a `launchd` agent every Monday at 09:00", carry_over=False
        )
        self.assertIn("CARRYOVER_MISSING", self.codes(path))

    def test_ci_scheduled_loop_needs_carry_over(self) -> None:
        path = self._goal_with_cadence(
            "ci", "a GitHub Actions `schedule:` trigger, weekly", carry_over=False
        )
        self.assertIn("CARRYOVER_MISSING", self.codes(path))

    def test_systemd_timer_needs_carry_over(self) -> None:
        path = self._goal_with_cadence(
            "sd", "a `systemd` timer, daily", carry_over=False
        )
        self.assertIn("CARRYOVER_MISSING", self.codes(path))

    def test_hand_run_cadence_does_not_require_carry_over(self) -> None:
        path = self._goal_with_cadence(
            "manual", "I run it by hand when I remember to", carry_over=False
        )
        report = va.validate_paths([str(path)])
        self.assertNotIn(
            "CARRYOVER_MISSING", {f.code for f in report.findings}
        )

    def test_cron_scheduled_loop_with_carry_over_passes(self) -> None:
        path = self._goal_with_cadence(
            "ok", '`cron: 0 9 * * 1 zcode -p "$(cat prompt.md)"`', carry_over=True
        )
        report = va.validate_paths([str(path)])
        self.assertTrue(report.ok, [f.as_dict() for f in report.findings])

    def test_status_reports_a_non_claude_cadence(self) -> None:
        self._goal_with_cadence(
            "k", '`cron: 0 9 * * 1 kimi -p "$(cat prompt.md)"`', carry_over=True
        )
        state = va.status_paths([str(self.dir)])
        self.assertIn("kimi", state["artifacts"][0]["cadence"])
