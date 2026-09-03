#!/usr/bin/env python3
"""Check the mechanical surface of a ultra-goal artifact.

This validator observes facts only: file pairing, required sections, declared
phases, known delegation targets, and JavaScript syntax. It never judges whether
a topology is the right one, and it never edits an artifact. Findings are typed
diagnostics for the author to act on.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from goal_hooks import (  # noqa: E402
    ANCHOR_BUDGET_CEILING,
    frozen_digest,
)


KNOWN_TARGETS = ("claude", "codex", "hermes", "kimi", "opencode", "zcode")
PLACEHOLDERS = ("TO" + "DO:", "TB" + "D", "<FILL", "XX" + "X:")
KINDS = (
    (".decisions.md", "decisions"),
    (".workflow.js", "workflow"),
    (".goal.md", "goal"),
    (".delegation.md", "delegation"),
)
GOAL_SECTIONS = (
    ("intent", "INTENT_MISSING", "the artifact has no stated intent"),
    ("boundary", "BOUNDARY_MISSING", "the artifact has no stated boundary"),
    ("stop condition", "STOP_CONDITION_MISSING", "the artifact has no stop condition"),
    ("anchor", "ANCHOR_MISSING", "the artifact has no anchor"),
    ("means", "MEANS_MISSING", "the artifact does not separate its means from its intent, "
     "so dropping one is indistinguishable from scope drift"),
    ("verification", "VERIFIER_NOT_DECLARED", "no independent verifier is declared"),
)
# A means is something believed necessary to reach the intent. The label says
# whether the run may abandon it on evidence, and the owner sets the label - that
# is the whole point of the section, so an unlabelled means is not a means.
MEANS_LABELS = ("load-bearing", "droppable")
# An acceptance line is a requirement plus the state the run claims for it. The
# state is a claim like any other the run writes: the anchor is the evidence.
CHECKBOX = re.compile(r"(?m)^\s*[-*]\s+\[([ xX])\]\s+(\S.*)$")
BULLET_ANY = re.compile(r"(?m)^\s*[-*]\s+(\S.*)$")
ORDERED = re.compile(r"(?m)^\s*\d+[.)]\s+\S")
# A2A's task lifecycle contributes the two states a text protocol still needs:
# a worker that cannot proceed without something, and one that declines. The
# transport it ships with does not transfer; this vocabulary does.
WORKER_OUTCOMES = ("input-required", "rejected")
ANCHOR_BUDGET = re.compile(r"budget[^\n]*?(\d+)\s*(second|minute|hour)s?", re.I)
BUDGET_UNITS = {"second": 1, "minute": 60, "hour": 3600}
BULLET_LINE = re.compile(r"(?m)^\s*[-*]\s+(.*\S)\s*$")
# `## Cadence` and `## Carry-over` are conditional: an unattended run needs both,
# a one-shot goal needs neither.
# `inputs` is what keeps the review independent. Different vendors buy different
# blind spots; only stating what a role is given keeps the main agent's own
# argument for its work out of the reviewer's context.
ROLE_FIELDS = ("target", "mission", "anchor", "inputs")
# The critic's job is to discretize its disagreement, which is what turns it into
# an auditable object instead of a plausible rebuttal. Three classes, named.
DISAGREEMENT_CLASSES = ("agreement", "evidence-backed", "concern-based")
ROUND_CAP = re.compile(r"(\d+)\s+(?:inner\s+)?(?:round|turn)s?\b", re.I)
COMMAND = re.compile(r"`[^`\n]+`|```")
DIGIT = re.compile(r"\d")
FENCE = re.compile(r"```[a-z]*\n(.+?)\n```", re.S)
INLINE = re.compile(r"`([^`\n]+)`")
ANCHOR_COMMENT = re.compile(r"(?m)^\s*//\s*anchor:\s*(.+?)\s*$")
ANCHOR_TIMEOUT_SECONDS = 300
BULLET = re.compile(r"(?m)^\s*[-*]\s+\S")
# Reflexion (arXiv 2303.11366) bounds its reflection memory at 1-3 entries, because
# entries the model must actually reason over compete for the same budget as the work.
# That citation is why exceeding LESSONS_MAX is an error.
LESSONS_MAX = 3
# STATE_MAX has no such basis: it is a number this Skill picked. State entries are
# facts rather than reasoning, so they are cheaper to carry, and how many is too
# many has not been measured. Exceeding it is therefore advisory, not an error.
STATE_MAX = 8
SUBSECTION = re.compile(r"(?m)^###\s+(\w+)\s*$")


@dataclass(frozen=True)
class Finding:
    """One observed fact about an artifact's shape.

    `severity` exists because two different things were being reported as the
    same thing. An artifact missing its anchor is broken. An artifact carrying
    nine state entries against a budget nobody has measured is worth a sentence
    - and failing the build over a number this Skill invented would be the
    Skill enforcing its own guess as if it were a fact.

    The rule for choosing: **error** when the artifact cannot do its job as
    written, **advisory** when the finding is this Skill's judgement about how
    well it will work. Only errors move the exit code.
    """

    path: str
    code: str
    message: str
    severity: str = "error"

    def as_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class Report:
    findings: list[Finding]

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def advisories(self) -> list[Finding]:
        return [f for f in self.findings if f.severity != "error"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "findings": [f.as_dict() for f in self.findings]}


class UsageError(RuntimeError):
    """A path the caller named cannot be validated."""


def classify(path: Path) -> str | None:
    for suffix, kind in KINDS:
        if path.name.endswith(suffix):
            return kind
    return None


def slug_of(path: Path) -> str:
    for suffix, _ in KINDS:
        if path.name.endswith(suffix):
            return path.name[: -len(suffix)]
    return path.stem


def sections(text: str) -> dict[str, str]:
    """Map lowercased '## ' headings to their body text."""
    found: dict[str, str] = {}
    current: str | None = None
    body: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                found[current] = "\n".join(body)
            current = line[3:].strip().lower()
            body = []
        elif current is not None:
            body.append(line)
    if current is not None:
        found[current] = "\n".join(body)
    return found


def meta_block(text: str) -> tuple[str, int] | None:
    """Return the meta object literal and the offset of the export statement."""
    match = re.search(r"export\s+const\s+meta\s*=\s*\{", text)
    if match is None:
        return None
    depth = 0
    for index in range(match.end() - 1, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[match.end() - 1 : index + 1], match.start()
    return None


def carry_over_parts(text: str) -> dict[str, str]:
    """Split a carry-over section into its lowercased `### ` sub-sections."""
    parts: dict[str, str] = {}
    current: str | None = None
    body: list[str] = []
    for line in text.splitlines():
        match = SUBSECTION.match(line)
        if match is not None:
            if current is not None:
                parts[current] = "\n".join(body)
            current = match.group(1).strip().lower()
            body = []
        elif current is not None:
            body.append(line)
    if current is not None:
        parts[current] = "\n".join(body)
    return parts


def check_placeholders(path: Path, text: str, out: list[Finding]) -> None:
    for token in PLACEHOLDERS:
        if token in text:
            out.append(
                Finding(
                    str(path),
                    "PLACEHOLDER_LEFT",
                    f"unfinished placeholder {token!r} is still in the artifact",
                )
            )
            return


CHALLENGE_COLUMNS = {"term challenged", "what the run hit", "what would settle it"}


def decisions_region(text: str) -> str:
    """The decisions table only - everything before the first `## ` heading.

    A challenge row is not a decision: the run wrote it, and the owner has not
    ruled on it yet. Counting the two together would report an unresolved
    objection as a settled decision, which is the one thing this record exists
    to keep apart.
    """
    return text.split("\n## ", 1)[0]


def check_challenges(path: Path, text: str, out: list[Finding]) -> None:
    """The run's objections to its own terms, if it raised any.

    Optional by design: most runs have none, and requiring one would invite an
    invented objection. When the section is there its shape is checked, because
    an objection with no evidence and no exit is just a complaint.
    """
    if "\n## Challenges" not in text:
        return
    body = text.split("\n## Challenges", 1)[1]
    rows = [line.strip() for line in body.splitlines() if line.strip().startswith("|")]
    header = next((r for r in rows if "term challenged" in r.lower()), None)
    if header is None:
        out.append(
            Finding(
                str(path),
                "CHALLENGE_TABLE_MALFORMED",
                "expected a table with Term challenged | What the run hit | What would "
                "settle it columns",
            )
        )
        return
    cells = {c.strip().lower() for c in header.strip("|").split("|")}
    if not CHALLENGE_COLUMNS <= cells:
        out.append(
            Finding(
                str(path),
                "CHALLENGE_TABLE_MALFORMED",
                f"missing column(s): {', '.join(sorted(CHALLENGE_COLUMNS - cells))}",
            )
        )
        return
    for row in rows[rows.index(header) + 1 :]:
        values = [c.strip() for c in row.strip("|").split("|")]
        if set("".join(values)) <= set("- "):
            continue
        if len(values) < 3 or not all(values[:3]):
            out.append(
                Finding(
                    str(path),
                    "CHALLENGE_TABLE_MALFORMED",
                    "a challenge must name the term, what the run hit, and what would "
                    f"settle it - none of the three may be blank: {row}",
                )
            )
            return


def check_decisions(path: Path, text: str, out: list[Finding]) -> None:
    check_challenges(path, text, out)
    text = decisions_region(text)
    rows = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    header = next((row for row in rows if "decision" in row.lower()), None)
    if header is None or not {"rejected", "why"} <= set(
        cell.strip().lower() for cell in header.strip("|").split("|")
    ):
        out.append(
            Finding(
                str(path),
                "DECISIONS_TABLE_MALFORMED",
                "expected a table with Decision | Rejected | Why columns",
            )
        )
        return
    for row in rows[rows.index(header) + 1 :]:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if set("".join(cells)) <= set("- "):
            continue
        if len(cells) < 3 or not all(cells[:3]):
            out.append(
                Finding(
                    str(path),
                    "DECISIONS_TABLE_MALFORMED",
                    f"row has an empty or missing cell: {row}",
                )
            )
            return


def check_pairing(path: Path, out: list[Finding]) -> None:
    record = path.with_name(f"{slug_of(path)}.decisions.md")
    if not record.is_file():
        out.append(
            Finding(
                str(path),
                "PAIRED_DECISIONS_MISSING",
                f"no decisions record at {record.name}",
            )
        )
        return
    text = record.read_text(encoding="utf-8")
    check_placeholders(record, text, out)
    check_decisions(record, text, out)


def check_workflow(path: Path, text: str, out: list[Finding]) -> None:
    block = meta_block(text)
    if block is None:
        out.append(
            Finding(str(path), "META_NOT_FIRST", "no `export const meta = {...}` found")
        )
        return
    literal, offset = block

    prelude = re.sub(r"//[^\n]*|/\*.*?\*/", "", text[:offset], flags=re.S).strip()
    if prelude:
        out.append(
            Finding(
                str(path),
                "META_NOT_FIRST",
                "meta must be the first statement in the script",
            )
        )
    if any(token in literal for token in ("`", "${", "(", "=>")):
        out.append(
            Finding(
                str(path),
                "META_NOT_LITERAL",
                "meta must be a pure literal: no calls, arrows, or interpolation",
            )
        )
    for field in ("name", "description"):
        if not re.search(rf"(?m)^\s*{field}\s*:", literal):
            out.append(
                Finding(str(path), "META_MISSING_FIELD", f"meta is missing {field}")
            )

    declared = set(re.findall(r"""title\s*:\s*['"]([^'"]+)['"]""", literal))
    body = text[:offset] + text[offset + len(literal) :]
    used = set(re.findall(r"""phase\s*[:(]\s*['"]([^'"]+)['"]""", body))
    for title in sorted(used - declared):
        out.append(
            Finding(
                str(path),
                "PHASE_TITLE_UNDECLARED",
                f"phase {title!r} is used but not declared in meta.phases",
            )
        )

    comment = ANCHOR_COMMENT.search(text)
    if comment is None:
        out.append(
            Finding(
                str(path),
                "ANCHOR_MISSING",
                "add a top-line `// anchor: `<command>`` comment naming the runnable check",
            )
        )
    elif not INLINE.search(comment.group(1)):
        out.append(
            Finding(
                str(path),
                "ANCHOR_NOT_EXECUTABLE",
                "the anchor comment must wrap a runnable command in backticks",
            )
        )

    node = shutil.which("node")
    if node is None:
        return
    # The Workflow runtime evaluates a script inside an async function, so its
    # top-level `return` and `await` are legal there but not in a bare module.
    # Reproduce that wrapper before asking node to parse it.
    probe_source = "async function __probe() {\n" + re.sub(
        r"(?m)^export\s+", "", text
    ) + "\n}\n"
    with tempfile.TemporaryDirectory() as work:
        probe = Path(work) / "probe.mjs"
        probe.write_text(probe_source, encoding="utf-8")
        result = subprocess.run(
            [node, "--check", str(probe)], capture_output=True, text=True
        )
    if result.returncode != 0:
        lines = (result.stderr or result.stdout).strip().splitlines()
        detail = next((line for line in lines if "Error" in line), "")
        out.append(
            Finding(
                str(path),
                "SYNTAX_ERROR",
                detail.strip() or "node --check rejected the script",
            )
        )


def check_goal(path: Path, text: str, out: list[Finding]) -> None:
    found = sections(text)
    for name, code, message in GOAL_SECTIONS:
        if name not in found:
            out.append(Finding(str(path), code, f"`## {name.title()}` missing: {message}"))

    stop = found.get("stop condition", "")
    if stop and not (COMMAND.search(stop) or DIGIT.search(stop)):
        out.append(
            Finding(
                str(path),
                "STOP_CONDITION_NOT_QUANTIFIED",
                "stop condition names no command and no number",
            )
        )
    # A reviewer nobody audits is the shape the source study found unreliable:
    # agents optimize for agreement rather than correctness unless something
    # audits the review itself.
    verification = found.get("verification")
    if verification is not None:
        lowered = verification.lower()
        if not ("reviewer" in lowered and "critic" in lowered):
            out.append(
                Finding(
                    str(path),
                    "REVIEW_NOT_ADVERSARIAL",
                    "verification must name both a reviewer (reviews the artifact) and a "
                    "critic (reviews the review); a reviewer nobody audits converges on "
                    "agreement rather than correctness",
                )
            )
        if not ROUND_CAP.search(verification):
            out.append(
                Finding(
                    str(path),
                    "CONVERGENCE_NOT_BOUNDED",
                    "verification must cap the reviewer/critic exchange, e.g. "
                    "`at most 5 inner rounds`",
                )
            )

    means = found.get("means")
    if means is not None:
        unlabelled = [
            line
            for line in BULLET_LINE.findall(means)
            if not any(f"[{label}]" in line.lower() for label in MEANS_LABELS)
        ]
        if unlabelled:
            out.append(
                Finding(
                    str(path),
                    "MEANS_UNLABELLED",
                    f"{len(unlabelled)} means carry no `[load-bearing]` or `[droppable]` "
                    f"label, starting with {unlabelled[0][:60]!r}: without one the run "
                    "cannot tell an authorized abandonment from scope drift",
                )
            )

    anchor = found.get("anchor", "")
    if anchor and not COMMAND.search(anchor):
        out.append(
            Finding(
                str(path),
                "ANCHOR_NOT_EXECUTABLE",
                "anchor must name a runnable command, not an opinion",
            )
        )
    # Caught by a real run: a fenced anchor holding two commands ran only the
    # first, so the half that checked the product never executed and the gate
    # went green on a proposition nothing had tested. Refused here rather than
    # resolved, because both automatic repairs are wrong - the whole block
    # takes its verdict from the last line, and joining with `&&` rewrites
    # what the author asked for.
    fence = FENCE.search(anchor)
    if fence is not None:
        lines = [l.strip() for l in fence.group(1).strip().splitlines() if l.strip()]
        if len(lines) > 1:
            out.append(
                Finding(
                    str(path),
                    "ANCHOR_MULTILINE",
                    f"the anchor's fenced block holds {len(lines)} commands, so no "
                    "single exit code decides it: write one line (join with `&&` if "
                    "all must pass) or name a script. The gate will not pick one, "
                    "and running only the first is how an anchor reports green on "
                    "work it never checked",
                )
            )

    # An unattended run wakes with an empty context every iteration. Without a
    # carry-over section it rebuilds history from scratch and retries paths it has
    # already proven dead.
    # A cadence means this goal gets started more than once, so something has to
    # survive between runs - and inside one long run, across compaction. Its
    # wording is not pattern-matched: the section's presence is the fact.
    cadence = found.get("cadence")
    carry_over = found.get("carry-over")
    if cadence is not None:
        if carry_over is None:
            out.append(
                Finding(
                    str(path),
                    "CARRYOVER_MISSING",
                    "an unattended run needs a `## Carry-over` section: what the next "
                    "iteration must read before acting",
                )
            )
        elif not (
            "read" in carry_over.lower()
            and ("rewrite" in carry_over.lower() or "update" in carry_over.lower())
        ):
            out.append(
                Finding(
                    str(path),
                    "CARRYOVER_NOT_WIRED",
                    "carry-over must tell the run to read it before acting and rewrite "
                    "it before finishing, or it stays empty forever",
                )
            )
    # A goal that spans sessions needs its stop condition enumerable. One
    # sentence plus one anchor answers "is the whole thing done"; it cannot
    # answer "which parts are", which is the granularity at which a long run
    # declares victory early. Anthropic's long-running harness reached for the
    # same thing (a feature list, all failing at first) for the same reason.
    acceptance = found.get("acceptance")
    if cadence is not None and acceptance is None:
        out.append(
            Finding(
                str(path),
                "ACCEPTANCE_MISSING",
                "a goal that gets started more than once needs an `## Acceptance` "
                "section: one line per requirement with the state the run claims for "
                "it, so `passing` can be checked against the anchor rather than "
                "asserted about the whole goal at once",
            )
        )
    if acceptance is not None:
        if ORDERED.search(acceptance):
            out.append(
                Finding(
                    str(path),
                    "ACCEPTANCE_ORDERED",
                    "`## Acceptance` is a numbered list, which makes it a plan: ordered "
                    "steps are an author-time decomposition and belong in a graph. An "
                    "acceptance list is unordered - each line stands alone and the run "
                    "picks which to attempt",
                )
            )
        unstated = [
            line
            for line in BULLET_ANY.findall(acceptance)
            if not line.startswith("[")
        ]
        if unstated:
            out.append(
                Finding(
                    str(path),
                    "ACCEPTANCE_UNSTATED",
                    f"{len(unstated)} acceptance line(s) carry no `[ ]` or `[x]` state, "
                    f"starting with {unstated[0][:60]!r}: a requirement with no state "
                    "cannot tell the next turn what is left",
                )
            )

    # How long the anchor may run is the owner's call, but the host kills the
    # hook first, so a budget above that ceiling is a number with no effect.
    budget_match = ANCHOR_BUDGET.search(anchor)
    if budget_match is not None:
        seconds = int(budget_match.group(1)) * BUDGET_UNITS[
            budget_match.group(2).lower()
        ]
        if seconds > ANCHOR_BUDGET_CEILING:
            out.append(
                Finding(
                    str(path),
                    "ANCHOR_BUDGET_UNREACHABLE",
                    f"the declared budget of {seconds}s is above the {ANCHOR_BUDGET_CEILING}s "
                    "the host's hook timeout allows, so the gate will clamp it. An anchor "
                    "that genuinely needs longer should be split, or run outside the gate "
                    "and its result reported",
                    "advisory",
                )
            )

    # The handoff is the line the owner pastes into their CLI. Without it the
    # artifact describes a run nobody can start.
    handoff = found.get("handoff")
    if handoff is None:
        out.append(
            Finding(
                str(path),
                "HANDOFF_MISSING",
                "a goal package needs a `## Handoff` section holding the exact goal "
                "command to paste into this host",
            )
        )
    elif not FENCE.search(handoff):
        out.append(
            Finding(
                str(path),
                "HANDOFF_NOT_RUNNABLE",
                "the handoff must contain a fenced command block, not a description "
                "of how to run it",
            )
        )

    if carry_over:
        parts = carry_over_parts(carry_over)
        missing = [
            name for name in ("state", "lessons", "next") if name not in parts
        ]
        if missing:
            out.append(
                Finding(
                    str(path),
                    "CARRYOVER_SECTIONS_MISSING",
                    "carry-over needs `### State` (where the work stands), "
                    "`### Lessons` (why something failed and what to do instead) and "
                    "`### Next` (the one objective for the next round); "
                    f"missing: {', '.join(missing)}",
                )
            )
        # One entry, not a list. A list of next objectives is a plan, and a goal
        # that has grown a plan is a graph that should have been authored as one.
        nxt = parts.get("next")
        if nxt is not None:
            entries = len(BULLET.findall(nxt))
            if entries > 1:
                out.append(
                    Finding(
                        str(path),
                        "NEXT_NOT_SINGLE",
                        f"`### Next` holds {entries} entries: it takes exactly one "
                        "objective, derived from this round's verdict and inside the "
                        "frozen intent. A list of them is a plan, and a goal with a "
                        "plan is a graph that should have been authored as one",
                    )
                )
        for name, cap, code, severity in (
            ("state", STATE_MAX, "STATE_UNPRUNED", "advisory"),
            ("lessons", LESSONS_MAX, "LESSONS_UNPRUNED", "error"),
        ):
            body = parts.get(name)
            if body is None:
                continue
            count = len(BULLET.findall(body))
            if count > cap:
                out.append(
                    Finding(
                        str(path),
                        code,
                        f"{count} {name} entries exceeds {cap}: prune what is no longer "
                        "true instead of appending - Git holds the history",
                        severity,
                    )
                )


def check_delegation(path: Path, text: str, out: list[Finding]) -> None:
    """One delegation artifact is one adversarial-review triad.

    A main agent edits the artifact, a reviewer reviews the artifact, and a critic
    reviews the review. The third role is the one that matters: in the source
    study three roles beat a five-agent panel, and removing the critic reproduced
    the false-consensus failure it exists to prevent. So the shape is checked, not
    the head count.
    """
    found = sections(text)
    targets: dict[str, str] = {}
    for role, missing_code in (("reviewer", "REVIEWER_MISSING"), ("critic", "CRITIC_MISSING")):
        body = found.get(role)
        if body is None:
            out.append(
                Finding(
                    str(path),
                    missing_code,
                    f"a delegation package needs a `## {role.title()}` section; without "
                    "the critic, the review is nobody's job to audit",
                )
            )
            continue
        fields = dict(re.findall(r"(?m)^\s*[-*]\s*(\w+)\s*:\s*(.+?)\s*$", body))
        for field in ROLE_FIELDS:
            if not fields.get(field):
                out.append(
                    Finding(
                        str(path),
                        "ROLE_FIELD_MISSING",
                        f"`## {role.title()}` is missing {field}",
                    )
                )
        target = fields.get("target", "").strip("`").lower()
        if target:
            targets[role] = target
            if target not in KNOWN_TARGETS:
                out.append(
                    Finding(
                        str(path),
                        "UNKNOWN_TARGET",
                        f"{target!r} is not a registered target; run "
                        "`agent-delegate list --json`",
                    )
                )

    if len(targets) == 2 and targets["reviewer"] == targets["critic"]:
        out.append(
            Finding(
                str(path),
                "SAME_VENDOR_REVIEW",
                f"reviewer and critic are both {targets['reviewer']!r}: agents that share "
                "a model share its blind spots, so the critic would mostly agree",
            )
        )

    critic = (found.get("critic") or "").lower()
    if critic and not all(name in critic for name in DISAGREEMENT_CLASSES):
        missing = [n for n in DISAGREEMENT_CLASSES if n not in critic]
        out.append(
            Finding(
                str(path),
                "DISAGREEMENT_NOT_CLASSIFIED",
                "the critic must sort every point into agreement, evidence-backed "
                f"disagreement, or concern-based disagreement; missing: {', '.join(missing)}",
            )
        )

    convergence = found.get("convergence")
    if convergence is None:
        out.append(
            Finding(
                str(path),
                "CONVERGENCE_MISSING",
                "a delegation package needs a `## Convergence` section: what keeps the "
                "artifact frozen, and how many inner rounds are allowed",
            )
        )
    elif not ROUND_CAP.search(convergence):
        out.append(
            Finding(
                str(path),
                "CONVERGENCE_NOT_BOUNDED",
                "convergence must cap the inner loop, e.g. `at most 5 inner rounds`",
            )
        )
    if convergence is not None:
        lowered = convergence.lower()
        missing = [name for name in WORKER_OUTCOMES if name not in lowered]
        if missing:
            out.append(
                Finding(
                    str(path),
                    "WORKER_OUTCOMES_UNDECLARED",
                    "convergence must say what a worker does when it cannot proceed. "
                    f"Name these outcomes explicitly: {', '.join(missing)}. Without "
                    "them a blocked worker and a finished one look the same to the "
                    "orchestrator, and silence gets read as agreement",
                )
            )


CHECKS = {
    "workflow": check_workflow,
    "goal": check_goal,
    "delegation": check_delegation,
}


def validate_file(path: Path, kind: str) -> list[Finding]:
    out: list[Finding] = []
    text = path.read_text(encoding="utf-8")
    check_placeholders(path, text, out)
    if kind == "decisions":
        check_decisions(path, text, out)
        return out
    check_pairing(path, out)
    CHECKS[kind](path, text, out)
    return out


def validate_paths(paths: list[str]) -> Report:
    findings: list[Finding] = []
    seen: set[Path] = set()
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            targets = sorted(
                child
                for child in path.rglob("*")
                if child.is_file() and classify(child) is not None
            )
        elif path.is_file():
            kind = classify(path)
            if kind is None:
                findings.append(
                    Finding(
                        str(path),
                        "UNKNOWN_ARTIFACT_KIND",
                        "expected .workflow.js, .goal.md, .delegation.md, or .decisions.md",
                    )
                )
                continue
            targets = [path]
        else:
            raise UsageError(f"no such file or directory: {path}")
        for target in targets:
            resolved = target.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            findings.extend(validate_file(target, classify(target) or ""))
    unique: list[Finding] = []
    for finding in findings:
        if finding not in unique:
            unique.append(finding)
    return Report(unique)


def first_command(text: str) -> str | None:
    """Pull the first runnable command out of a fence or inline backticks."""
    fence = FENCE.search(text)
    if fence is not None:
        body = fence.group(1).strip()
        if body:
            return body.splitlines()[0].strip()
    inline = INLINE.search(text)
    return inline.group(1).strip() if inline is not None else None


def first_bullet(text: str) -> str | None:
    """The first bullet's own line, which for `### Next` is the whole content."""
    match = BULLET_LINE.search(text)
    return match.group(1).strip() if match is not None else None


def first_sentence(text: str) -> str | None:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return None


def challenge_count(record: Path) -> int:
    """How many terms the run has objected to and the owner has not ruled on."""
    if not record.is_file():
        return 0
    text = record.read_text(encoding="utf-8")
    if "\n## Challenges" not in text:
        return 0
    body = text.split("\n## Challenges", 1)[1]
    rows = [line.strip() for line in body.splitlines() if line.strip().startswith("|")]
    header = next((r for r in rows if "term challenged" in r.lower()), None)
    if header is None:
        return 0
    count = 0
    for row in rows[rows.index(header) + 1 :]:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if set("".join(cells)) <= set("- "):
            continue
        count += 1
    return count


def decision_count(record: Path) -> int:
    if not record.is_file():
        return 0
    rows = [
        line.strip()
        for line in decisions_region(record.read_text(encoding="utf-8")).splitlines()
        if line.strip().startswith("|")
    ]
    header = next((row for row in rows if "decision" in row.lower()), None)
    if header is None:
        return 0
    count = 0
    for row in rows[rows.index(header) + 1 :]:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if set("".join(cells)) <= set("- "):
            continue
        count += 1
    return count


SHAPES = {
    "goal": "loop",
    "workflow": "graph-single-vendor",
    "delegation": "graph-star",
}


def read_log(artifact: Path) -> list[dict[str, object]]:
    """Every event the hooks recorded for this artifact, oldest first.

    The log is written by the hooks and never by this validator. That asymmetry
    is the point: the artifact and the commit messages are what the model says
    happened, and this is what the machine measured. A malformed line is skipped
    rather than fatal - a broken log must not make the report unusable.
    """
    log = artifact.with_name(f"{slug_of(artifact)}.events.jsonl")
    entries: list[dict[str, object]] = []
    try:
        if not log.is_file():
            return entries
        for line in log.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, UnicodeError):
                continue
            if isinstance(entry, dict):
                entries.append(entry)
    except (OSError, UnicodeError):
        return entries
    return entries


def last_anchor_check(artifact: Path) -> dict[str, object] | None:
    """The newest anchor result from the goal's event log, if any."""
    checks = [e for e in read_log(artifact) if e.get("event") == "anchor_checked"]
    if not checks:
        return None
    newest = checks[-1]
    return {
        "turn": newest.get("turn"),
        "outcome": newest.get("outcome"),
        "exit_code": newest.get("exit_code"),
        "at": newest.get("ts"),
    }


def describe(path: Path, kind: str) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    item: dict[str, object] = {
        "slug": slug_of(path),
        "kind": kind,
        "shape": SHAPES[kind],
        "path": str(path),
        "anchor": None,
        "stop_condition": None,
        "phases": [],
        "workers": [],
        "decisions": decision_count(path.with_name(f"{slug_of(path)}.decisions.md")),
        "challenges": challenge_count(path.with_name(f"{slug_of(path)}.decisions.md")),
        "anchor_result": None,
    }
    item["cadence"] = None
    item["carry_over"] = None
    item["next"] = None
    item["start_command"] = None
    item["last_check"] = last_anchor_check(path)
    if kind == "goal":
        found = sections(text)
        item["anchor"] = first_command(found.get("anchor", ""))
        item["stop_condition"] = first_sentence(found.get("stop condition", ""))
        cadence = found.get("cadence", "")
        item["cadence"] = first_command(cadence) or first_sentence(cadence)
        carry_over = found.get("carry-over")
        if carry_over is not None:
            parts = carry_over_parts(carry_over)
            item["carry_over"] = {
                name: len(BULLET.findall(parts.get(name, "")))
                for name in ("state", "lessons")
            }
            # What the run is aiming at next is the single most useful line
            # about a goal already in flight, so it is shown, not counted.
            item["next"] = first_bullet(parts.get("next", ""))
        handoff = found.get("handoff", "")
        start = FENCE.search(handoff)
        item["start_command"] = (
            start.group(1).strip().splitlines()[0].strip() if start else None
        )
    elif kind == "workflow":
        comment = ANCHOR_COMMENT.search(text)
        if comment is not None:
            item["anchor"] = first_command(comment.group(1)) or comment.group(1)
        block = meta_block(text)
        if block is not None:
            item["phases"] = re.findall(
                r"""title\s*:\s*['\"]([^'\"]+)['\"]""", block[0]
            )
    else:
        found = sections(text)
        roles = []
        for role in ("reviewer", "critic"):
            body = found.get(role) or ""
            match = re.search(r"(?m)^\s*[-*]\s*target\s*:\s*(.+?)\s*$", body)
            if match:
                roles.append(match.group(1).strip("`").lower())
        item["workers"] = roles
    return item


def run_anchor(item: dict[str, object]) -> dict[str, object] | None:
    """Execute an artifact's anchor. Only ever called with explicit consent."""
    command = item.get("anchor")
    if not command:
        return None
    try:
        completed = subprocess.run(
            str(command),
            shell=True,
            cwd=Path(str(item["path"])).parent,
            capture_output=True,
            text=True,
            timeout=ANCHOR_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "exit_code": None,
            "timed_out": True,
            "tail": f"no result within {ANCHOR_TIMEOUT_SECONDS}s",
        }
    tail = (completed.stdout + completed.stderr).strip().splitlines()
    return {
        "command": command,
        "exit_code": completed.returncode,
        "timed_out": False,
        "tail": tail[-1] if tail else "",
    }


def status_paths(paths: list[str], run_anchors: bool = False) -> dict[str, object]:
    """Derive the current state of every artifact under `paths`.

    Nothing is stored: the artifacts on disk are the only record, and this is a
    projection of them. Anchors stay unexecuted unless `run_anchors` is set.
    """
    report = validate_paths(paths)
    items: list[dict[str, object]] = []
    seen: set[Path] = set()
    for raw in paths:
        path = Path(raw).expanduser()
        candidates = (
            sorted(child for child in path.rglob("*") if child.is_file())
            if path.is_dir()
            else [path]
        )
        for candidate in candidates:
            kind = classify(candidate)
            if kind is None or kind == "decisions":
                continue
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            item = describe(candidate, kind)
            if run_anchors:
                item["anchor_result"] = run_anchor(item)
            items.append(item)
    return {
        "ok": report.ok,
        "artifacts": items,
        "findings": [f.as_dict() for f in report.findings],
    }


# The per-turn commit convention. The verdict in the subject line is the model's
# claim about the turn; the event log is the machine's measurement of it.
CLAIM = re.compile(
    r"^goal\((?P<slug>[^)]+)\)\s+turn\s+(?P<turn>\d+)\s*:\s*"
    r"(?P<summary>.*?)\s*\[anchor:\s*(?P<verdict>green|red|unknown)\s*\]\s*$",
    re.I,
)


def git_claims(artifact: Path) -> dict[int, dict[str, str]] | None:
    """Claims parsed from the commits that touched this artifact, by turn.

    Selected by the slug in the subject line, not by which files the commit
    touched: most turns change source and never touch the artifact, so a
    pathspec filter would drop exactly the turns worth auditing. Measured -
    filtering by path hid two of three claims in a scratch run.

    None means the history could not be read at all - no Git, or not a work
    tree - which is itself the finding: without history there is nothing to
    audit the log against. A later commit for the same turn wins, so an amended
    turn is audited as amended.
    """
    slug = slug_of(artifact)
    try:
        completed = subprocess.run(
            [
                "git", "log", "--reverse", "--format=%h%x1f%s",
                "-F", f"--grep=goal({slug}) turn",
            ],
            cwd=str(artifact.parent),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    claims: dict[int, dict[str, str]] = {}
    for line in completed.stdout.splitlines():
        sha, _, subject = line.partition("\x1f")
        match = CLAIM.match(subject.strip())
        if match is None or match.group("slug") != slug:
            continue
        claims[int(match.group("turn"))] = {
            "commit": sha.strip(),
            "verdict": match.group("verdict").lower(),
            "summary": match.group("summary"),
        }
    return claims


def audit_artifact(path: Path) -> tuple[dict[str, object], list[Finding]]:
    """Put what the run claimed beside what the gate measured.

    Neither side is trusted over the other: a divergence is reported, not
    resolved. The value is that a human can see exactly which turn stopped
    matching its evidence, which is the question "where did it go wrong"
    reduces to.
    """
    out: list[Finding] = []
    events = read_log(path)
    checks = [e for e in events if e.get("event") == "anchor_checked"]
    measured = {e.get("turn"): e for e in checks}
    claims = git_claims(path)

    if claims is None:
        out.append(
            Finding(
                str(path),
                "HISTORY_UNAVAILABLE",
                "no readable Git history for this artifact, so the run's claims cannot "
                "be checked against the gate's measurements - the trace is the only "
                "thing that makes a finished run reviewable",
            )
        )
        claims = {}

    if claims and not checks:
        out.append(
            Finding(
                str(path),
                "GATE_NEVER_RAN",
                f"{len(claims)} turn(s) were committed but the event log holds no anchor "
                "check: every verdict in the history is self-reported. Install the hooks "
                "on this host, or say plainly that the run was ungated",
            )
        )

    rows: list[dict[str, object]] = []
    for turn in sorted(set(claims) | {t for t in measured if isinstance(t, int)}):
        claim = claims.get(turn)
        check = measured.get(turn)
        row = {
            "turn": turn,
            "claimed": claim["verdict"] if claim else None,
            "measured": check.get("outcome") if check else None,
            "exit_code": check.get("exit_code") if check else None,
            "commit": claim["commit"] if claim else None,
            "at": check.get("ts") if check else None,
        }
        rows.append(row)
        if claim and check is None and checks:
            out.append(
                Finding(
                    str(path),
                    "CLAIM_UNWITNESSED",
                    f"turn {turn} claims `[anchor: {claim['verdict']}]` in {claim['commit']} "
                    "but the gate recorded no check for that turn: the verdict came from "
                    "the run's own account of itself",
                )
            )
        elif claim and check and claim["verdict"] != check.get("outcome"):
            out.append(
                Finding(
                    str(path),
                    "CLAIM_CONTRADICTED",
                    f"turn {turn} claims `[anchor: {claim['verdict']}]` in {claim['commit']} "
                    f"but the gate measured {check.get('outcome')} (exit "
                    f"{check.get('exit_code')}). The measurement is the evidence; the "
                    "commit message is the claim",
                )
            )

    # Did the goalposts move? Two ways to find out, both from machine-written
    # facts: the gate said so on some turn, or the file on disk no longer
    # matches the digest recorded on turn 1.
    baseline = next(
        (c.get("spec_digest") for c in checks if c.get("spec_digest")), None
    )
    now = None
    if path.suffix == ".md" and classify(path) == "goal":
        try:
            now = frozen_digest(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError):
            now = None
    moved = [e for e in events if e.get("event") == "frozen_spec_changed"]
    if moved or (baseline and now and baseline != now):
        turns = ", ".join(str(e.get("turn")) for e in moved) or "after the last turn"
        out.append(
            Finding(
                str(path),
                "FROZEN_SPEC_CHANGED",
                f"`## Intent`, `## Boundary` or `## Anchor` changed during the run "
                f"({turns}): {baseline} at turn 1 versus {now or 'unknown'} now. Whatever "
                "the anchor proved, it did not prove the goal the owner authorized",
            )
        )
    return {
        "slug": slug_of(path),
        "path": str(path),
        "rows": rows,
        "spec_digest_first": baseline,
        "spec_digest_now": now,
    }, out


def audit_paths(paths: list[str]) -> dict[str, object]:
    """Audit every artifact under `paths`, plus the ordinary validation."""
    report = validate_paths(paths)
    findings = list(report.findings)
    audits: list[dict[str, object]] = []
    seen: set[Path] = set()
    for raw in paths:
        path = Path(raw).expanduser()
        candidates = (
            sorted(child for child in path.rglob("*") if child.is_file())
            if path.is_dir()
            else [path]
        )
        for candidate in candidates:
            kind = classify(candidate)
            if kind is None or kind == "decisions":
                continue
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            audit, found = audit_artifact(candidate)
            audits.append(audit)
            findings.extend(found)
    return {
        "ok": not findings,
        "audits": audits,
        "findings": [f.as_dict() for f in findings],
    }


def print_audit(state: dict[str, object]) -> None:
    for audit in state["audits"]:
        print(f"{audit['slug']}")
        rows = audit["rows"]
        if not rows:
            print("  no turns recorded and none claimed")
        else:
            print("  turn  claimed   measured  exit  commit")
            for row in rows:
                print(
                    f"  {str(row['turn']):<5} {str(row['claimed'] or '-'):<9} "
                    f"{str(row['measured'] or '-'):<9} "
                    f"{str(row['exit_code'] if row['exit_code'] is not None else '-'):<5} "
                    f"{row['commit'] or '-'}"
                )
        if audit["spec_digest_first"]:
            same = audit["spec_digest_first"] == audit["spec_digest_now"]
            print(
                f"  frozen spec: {audit['spec_digest_first']} at turn 1, "
                f"{audit['spec_digest_now'] or 'unknown'} now"
                f" ({'unchanged' if same else 'CHANGED'})"
            )
    for finding in state["findings"]:
        print(f"{finding['path']}: {finding['code']}: {finding['message']}")


def print_status(state: dict[str, object]) -> None:
    artifacts = state["artifacts"]
    if not artifacts:
        print("no artifacts found")
    for item in artifacts:
        line = f"{item['slug']}  [{item['shape']}]  decisions={item['decisions']}"
        if item.get("challenges"):
            # An unresolved objection to the terms is the most decision-shaped
            # thing an inspect can surface, so it is never merely counted away.
            line += f"  **challenges={item['challenges']}**"
        print(line)
        if item["anchor"]:
            print(f"  anchor: {item['anchor']}")
        if item["stop_condition"]:
            print(f"  stop:   {item['stop_condition']}")
        if item["cadence"]:
            print(f"  cadence: {item['cadence']}")
        if item["carry_over"] is not None:
            counts = item["carry_over"]
            print(
                f"  carry-over: {counts['state']} state, {counts['lessons']} lesson(s)"
            )
        if item["next"]:
            print(f"  next:   {item['next']}")
        if item["start_command"]:
            print(f"  starts by: {item['start_command']}")
        check = item.get("last_check")
        if check:
            print(
                f"  last check: turn {check['turn']}, {check['outcome']}"
                f" (exit {check['exit_code']})"
            )
        if item["phases"]:
            print(f"  phases: {', '.join(item['phases'])}")
        if item["workers"]:
            print(f"  workers: {', '.join(item['workers'])}")
        result = item["anchor_result"]
        if result:
            verdict = "timed out" if result["timed_out"] else f"exit {result['exit_code']}"
            print(f"  ran:    {verdict}  {result['tail']}")
    for finding in state["findings"]:
        print(f"{finding['path']}: {finding['code']}: {finding['message']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Artifact files or a directory holding them")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument(
        "--status",
        action="store_true",
        help="Report the current shape, anchor, and stop condition of each artifact",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Put each turn's committed claim beside the gate's measurement of it",
    )
    parser.add_argument(
        "--run-anchors",
        action="store_true",
        help="With --status, execute each anchor command and report its exit code",
    )
    args = parser.parse_args()
    if args.run_anchors and not args.status:
        print("Error: --run-anchors requires --status", file=sys.stderr)
        return 2
    if args.audit and args.status:
        print("Error: --audit and --status are separate reports", file=sys.stderr)
        return 2
    try:
        if args.audit:
            state = audit_paths(args.paths)
            if args.json:
                print(json.dumps(state, ensure_ascii=False, indent=2))
            else:
                print_audit(state)
            return 0 if state["ok"] else 1
        if args.status:
            state = status_paths(args.paths, run_anchors=args.run_anchors)
            if args.json:
                print(json.dumps(state, ensure_ascii=False, indent=2))
            else:
                print_status(state)
            return 0 if state["ok"] else 1
        report = validate_paths(args.paths)
    except (UsageError, OSError, UnicodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    else:
        for finding in report.findings:
            label = "" if finding.severity == "error" else " [advisory]"
            print(f"{finding.path}: {finding.code}{label}: {finding.message}")
        if report.ok:
            print("ok" if not report.advisories else "ok (advisories above)")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
