#!/usr/bin/env python3
"""Check the mechanical surface of a loop-graph-design artifact.

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


KNOWN_TARGETS = ("claude", "codex", "hermes", "kimi", "opencode", "zcode")
PLACEHOLDERS = ("TO" + "DO:", "TB" + "D", "<FILL", "XX" + "X:")
KINDS = (
    (".decisions.md", "decisions"),
    (".workflow.js", "workflow"),
    (".goal.md", "goal"),
    (".delegation.md", "delegation"),
)
GOAL_SECTIONS = (
    ("intent", "INTENT_MISSING", "the loop has no stated intent"),
    ("boundary", "BOUNDARY_MISSING", "the loop has no stated boundary"),
    ("stop condition", "STOP_CONDITION_MISSING", "the loop has no stop condition"),
    ("anchor", "ANCHOR_MISSING", "the loop has no anchor"),
    ("verification", "VERIFIER_NOT_DECLARED", "no independent verifier is declared"),
)
# `## Cadence` and `## Carry-over` are conditional: an unattended loop needs both,
# a one-shot goal needs neither.
WORKER_FIELDS = ("target", "mission", "anchor")
COMMAND = re.compile(r"`[^`\n]+`|```")
DIGIT = re.compile(r"\d")
FENCE = re.compile(r"```[a-z]*\n(.+?)\n```", re.S)
INLINE = re.compile(r"`([^`\n]+)`")
ANCHOR_COMMENT = re.compile(r"(?m)^\s*//\s*anchor:\s*(.+?)\s*$")
ANCHOR_TIMEOUT_SECONDS = 300
BULLET = re.compile(r"(?m)^\s*[-*]\s+\S")
CARRYOVER_MAX_ITEMS = 20


@dataclass(frozen=True)
class Finding:
    path: str
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "code": self.code, "message": self.message}


@dataclass
class Report:
    findings: list[Finding]

    @property
    def ok(self) -> bool:
        return not self.findings

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


def check_decisions(path: Path, text: str, out: list[Finding]) -> None:
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
    anchor = found.get("anchor", "")
    if anchor and not COMMAND.search(anchor):
        out.append(
            Finding(
                str(path),
                "ANCHOR_NOT_EXECUTABLE",
                "anchor must name a runnable command, not an opinion",
            )
        )

    # An unattended loop wakes with an empty context every iteration. Without a
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
                    "an unattended loop needs a `## Carry-over` section: what the next "
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
                    "carry-over must tell the loop to read it before acting and rewrite "
                    "it before finishing, or it stays empty forever",
                )
            )
    # The handoff is the line the owner pastes into their CLI. Without it the
    # artifact describes a loop nobody can start.
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

    if carry_over and len(BULLET.findall(carry_over)) > CARRYOVER_MAX_ITEMS:
        out.append(
            Finding(
                str(path),
                "CARRYOVER_UNPRUNED",
                f"more than {CARRYOVER_MAX_ITEMS} carry-over items: prune what is no "
                "longer true instead of appending - Git holds the history",
            )
        )


def check_delegation(path: Path, text: str, out: list[Finding]) -> None:
    workers = [
        (name, body)
        for name, body in sections(text).items()
        if name.startswith("worker")
    ]
    if len(workers) < 2:
        out.append(
            Finding(
                str(path),
                "SINGLE_WORKER_DELEGATION",
                "a delegation package needs at least two workers; one worker is a loop",
            )
        )
    for name, body in workers:
        fields = dict(
            re.findall(r"(?m)^\s*[-*]\s*(\w+)\s*:\s*(.+?)\s*$", body)
        )
        for field in WORKER_FIELDS:
            if not fields.get(field):
                out.append(
                    Finding(
                        str(path),
                        "WORKER_FIELD_MISSING",
                        f"`## {name}` is missing {field}",
                    )
                )
        target = fields.get("target", "").strip("`").lower()
        if target and target not in KNOWN_TARGETS:
            out.append(
                Finding(
                    str(path),
                    "UNKNOWN_TARGET",
                    f"{target!r} is not a registered target; run `agent-delegate list --json`",
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


def first_sentence(text: str) -> str | None:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return None


def decision_count(record: Path) -> int:
    if not record.is_file():
        return 0
    rows = [
        line.strip()
        for line in record.read_text(encoding="utf-8").splitlines()
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
        "anchor_result": None,
    }
    item["cadence"] = None
    item["carry_over"] = None
    item["start_command"] = None
    if kind == "goal":
        found = sections(text)
        item["anchor"] = first_command(found.get("anchor", ""))
        item["stop_condition"] = first_sentence(found.get("stop condition", ""))
        cadence = found.get("cadence", "")
        item["cadence"] = first_command(cadence) or first_sentence(cadence)
        carry_over = found.get("carry-over")
        if carry_over is not None:
            item["carry_over"] = len(BULLET.findall(carry_over))
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
        item["workers"] = [
            name.split(":", 1)[1].strip()
            for name in sections(text)
            if name.startswith("worker") and ":" in name
        ]
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


def print_status(state: dict[str, object]) -> None:
    artifacts = state["artifacts"]
    if not artifacts:
        print("no artifacts found")
    for item in artifacts:
        print(f"{item['slug']}  [{item['shape']}]  decisions={item['decisions']}")
        if item["anchor"]:
            print(f"  anchor: {item['anchor']}")
        if item["stop_condition"]:
            print(f"  stop:   {item['stop_condition']}")
        if item["cadence"]:
            print(f"  cadence: {item['cadence']}")
        if item["carry_over"] is not None:
            print(f"  carry-over: {item['carry_over']} item(s)")
        if item["start_command"]:
            print(f"  starts by: {item['start_command']}")
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
        "--run-anchors",
        action="store_true",
        help="With --status, execute each anchor command and report its exit code",
    )
    args = parser.parse_args()
    if args.run_anchors and not args.status:
        print("Error: --run-anchors requires --status", file=sys.stderr)
        return 2
    try:
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
    elif report.ok:
        print("ok")
    else:
        for finding in report.findings:
            print(f"{finding.path}: {finding.code}: {finding.message}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
