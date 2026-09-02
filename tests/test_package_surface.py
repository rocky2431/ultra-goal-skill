from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "loop-graph-design"
SKILL_ROOT = PLUGIN_ROOT / "skills" / "loop-graph-design"

sys.path.insert(0, str(SKILL_ROOT / "scripts"))
import validate_artifact as va  # noqa: E402


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
        for primitive in ("/goal", "/loop", "Workflow script", "delegation package"):
            self.assertIn(primitive, text)

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
            "## Validate, then hand off",
        ):
            self.assertIn(required, skill, required)
        self.assertLess(len(skill.splitlines()), 220)

    def test_skill_does_not_mechanize_topology(self) -> None:
        skill = skill_text()
        self.assertIn("Do not generate topology from a template engine", skill)
        self.assertIn("never edits the artifact", skill)
        self.assertIn("its silence is not evidence", skill)

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

    def test_delegation_template_only_names_known_targets(self) -> None:
        text = (SKILL_ROOT / "assets" / "delegation-package.md").read_text(
            encoding="utf-8"
        )
        for target in re.findall(r"(?m)^- target: (\S+)$", text):
            self.assertIn(target, va.KNOWN_TARGETS)


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
        routed = {skill for case in negatives for skill in case["expected_skills"]}
        self.assertIn(
            "agent-harness-design",
            routed,
            "a negative must route authority-design work to the adjacent skill",
        )
        for case in cases:
            if case["kind"] in ("ambiguous", "coexistence"):
                self.assertGreaterEqual(len(case["accepted_skill_sets"]), 2)


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
