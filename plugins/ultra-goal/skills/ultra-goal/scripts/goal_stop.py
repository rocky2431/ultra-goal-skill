#!/usr/bin/env python3
"""Completion gate for an armed, owner-approved goal contract.

Ordinary Stop ends a host turn without measuring completion. A candidate is
consumed once, bounded by the owner's attempt ceiling and the host-specific
continuation budget. The gate checks the frozen contract, protected evaluator
inputs, required current independent review, then executes the anchor once.
It rechecks evaluator/review inputs after execution and records actual evidence.

A green anchor plus required review satisfies the accepted verification contract;
it does not prove the specification captures every aspect of the owner's intent.
Timeouts/unrunnable commands remain unknown. Budget exhaustion, cancellation,
ordinary Stop and host goal completion are never substitutes for verification.
Delegation failures remain audit observations; output evidence determines whether
an authorized fallback has fulfilled the goal's obligations.

Frozen specification changes end/disarm the run with an owner-facing explanation.
Evidence failures refuse a candidate within the existing denial bounds. An allow
carries no model context: the native host supplies further turns, and the model's
final response must not pretend it has observed a future Stop result. Baselines,
receipts and event logs are auditable files, not a security isolation boundary.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from goal_hooks import (  # noqa: E402
    ANCHOR_BUDGET_CEILING,
    DEFAULT_ANCHOR_BUDGET,
    DEFAULT_HOST,
    ActiveGoal,
    append_event,
    completion_attempts,
    event_session,
    frozen_digest,
    host_facts,
    read_events,
    read_spec_baseline,
    run_hook,
    sections,
)
from goal_contract import check_protection, check_review  # noqa: E402


# How long to wait is the owner's call, not a constant in this file: an anchor
# that legitimately takes four minutes was previously unknowable to the gate,
# which is the same mistake as judging success by elapsed time. The artifact
# declares it in `## Anchor` as e.g. `budget: 4 minutes`; the constant is only
# the fallback, and the ceiling is what the host's own hook timeout allows.
UNITS = {"second": 1, "minute": 60, "hour": 3600}
BUDGET = re.compile(
    rf"budget[^\n]*?(\d+)\s*({'|'.join(UNITS)})s?", re.I
)
# Used only when the artifact's stop condition names no ceiling. Deliberately
# generous: guessing low is the failure mode that cuts off real work.
DEFAULT_CEILING = 12
FENCE = re.compile(r"```[a-z]*\n(.+?)\n```", re.S)
INLINE = re.compile(r"`([^`\n]+)`")
# Widened after measuring the original against real phrasings: "six turns",
# "6 iterations" and "6-turn ceiling" all missed, and a miss meant silently
# enforcing DEFAULT_CEILING instead of the owner's number - a moved threshold
# that looks exactly like the owner's own.
WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "fifteen": 15, "twenty": 20,
}
UNIT = r"(?:(?:turn|iteration|round|cycle)s?|pass(?:es)?)"
TURNS = re.compile(rf"(\d+)[\s-]+{UNIT}\b", re.I)
TURNS_WORD = re.compile(
    rf"\b({'|'.join(WORD_NUMBERS)})[\s-]+{UNIT}\b", re.I
)


DECLARED_CEILING = re.compile(r"(?mi)^\s*ceiling:\s*(none|unbounded|\d+)\s*$")


def _ceiling(stop_section: str) -> tuple[int | None, bool]:
    """The owner's turn ceiling, whether it was found, and None for unbounded.

    Three answers, not two, for the same reason the anchor has three outcomes.
    A run the owner declared unbounded is not a run with a ceiling of twelve -
    and that substitution was a live defect: a real long run whose stop
    condition said "no ceiling" would have been stopped by this gate at turn 13
    while reporting "ceiling reached", in the owner's own voice.

    `ceiling: none` and `ceiling: N` are declared forms, checked first, because
    a token the owner wrote beats prose this parser has to guess at.
    """
    declared = DECLARED_CEILING.search(stop_section)
    if declared is not None:
        value = declared.group(1).lower()
        return (None, True) if value in ("none", "unbounded") else (int(value), True)
    digits = TURNS.search(stop_section)
    if digits is not None:
        return int(digits.group(1)), True
    word = TURNS_WORD.search(stop_section)
    if word is not None:
        return WORD_NUMBERS[word.group(1).lower()], True
    return DEFAULT_CEILING, False
# Exit codes for "command not found" are a per-shell detail: POSIX shells use
# 127 (and 126 for found-but-not-executable), cmd.exe uses 9009, and CI proved
# that guessing from the code alone leaves the third outcome missing on some
# platform. They are kept as a fallback, but the primary check happens before
# the command runs, where it can be answered by looking rather than inferring.
UNRUNNABLE_EXITS = {126, 127, 9009}


def _first_command(text: str) -> tuple[str | None, str | None]:
    """The anchor command, or None plus the reason there is not exactly one.

    A fenced block holding several lines used to yield its first line, which
    turned a two-command anchor into a one-command anchor without saying so.
    A real run found it: an anchor written as `run` then `verify` ran only
    `run`, so the half that checked the product never executed and the gate
    reported green on a proposition nothing had tested.

    The two tempting repairs are both worse. Running the whole block hands the
    verdict to the *last* line, so a failing `run` followed by a passing
    `verify` is green. Joining the lines with `&&` silently rewrites what the
    author asked for. So this refuses to choose: several lines means there is
    no single command whose exit code decides, and the gate says so instead of
    running half of it.
    """
    fence = FENCE.search(text)
    if fence is not None:
        lines = [l.strip() for l in fence.group(1).strip().splitlines() if l.strip()]
        if len(lines) > 1:
            return None, (
                f"the anchor's fenced block holds {len(lines)} commands, so no single "
                "exit code decides it. Write it as one line - join them with `&&` if "
                "all must pass - or put them in a script and name the script. This "
                "gate will not pick one for you: running only the first is how an "
                "anchor goes green on work it never checked"
            )
        if lines:
            return lines[0], None
    inline = INLINE.search(text)
    if inline is not None:
        return inline.group(1).strip(), None
    return None, None


def _budget(anchor_section: str) -> tuple[int, bool]:
    """Seconds to allow the anchor, and whether the artifact declared it.

    Clamped to what the host's hook timeout permits. Exceeding the budget is
    still *unknown* and never *failed* - a clock cannot see whether work
    landed, so raising this number changes what the gate can know, never what
    it is allowed to claim.
    """
    match = BUDGET.search(anchor_section or "")
    if match is None:
        return min(DEFAULT_ANCHOR_BUDGET, ANCHOR_BUDGET_CEILING), False
    seconds = int(match.group(1)) * UNITS[match.group(2).lower()]
    return min(max(seconds, 1), ANCHOR_BUDGET_CEILING), True


def _resolvable(command: str, root: Path) -> bool:
    """Can this command's executable actually be found?

    Asked before running, because "command not found" is reported differently
    by every shell and inferring it from an exit code is how the unknown
    outcome went missing on Windows. Looking is cheaper and portable.

    A false negative here costs an unnecessary "unknown", which allows the turn
    to end and says the result is unverified. A false negative in the other
    direction - treating a broken anchor as a failing one - denies the stop on
    no evidence. Erring toward unknown is the safe direction.

    `root` is not optional and not cosmetic. A relative head - and
    `.venv/bin/python` is the commonest anchor there is - used to be resolved
    against whatever directory the host happened to spawn the hook in, while
    twenty lines below the anchor is executed with `cwd=root` explicitly. Those
    two disagreeing is the worst kind of failure this gate can have: every turn
    reports `unknown`, the gate never enforces anything, and nothing anywhere
    says so. Found on a real artifact whose anchor began `.venv/bin/python`.
    """
    try:
        parts = shlex.split(command, posix=(os.name != "nt"))
    except ValueError:
        return True  # unparseable quoting: let the shell have a go at it
    if not parts:
        return False
    head = parts[0].strip('"\'')
    if not head:
        return False
    try:
        candidate = Path(head)
        if (root / candidate).exists() if not candidate.is_absolute() else candidate.exists():
            return True
    except OSError:
        pass
    return shutil.which(head) is not None


def _allow(reason: str) -> dict[str, Any]:
    """End the turn, telling the owner why - and the model nothing.

    An allow used to attach `hookSpecificOutput.additionalContext`, read as
    "end the turn and tell the model what it owes". On Claude Code 2.1.260
    that is not what happens: the probe `clean-claude-allow-context` (clean
    settings, isolated directory) showed a second Stop callback and the model
    acting on the injected text - the turn did not end. So an allow carries
    no model context at all, on any path.

    The obligation did not disappear; it moved to where it always belonged:
    the run's own loop. The skill's standing instructions make important
    results visible through ordinary tool output before the Stop and write
    durable state (carry-over, lessons, commits) before a turn is allowed to
    end. The next injectable event - where one exists at all; Kimi's task and
    system-triggered turns fire no `UserPromptSubmit`, and `SessionStart` is
    not guaranteed either - is best-effort recovery and never carries
    correctness.
    """
    return {"systemMessage": f"[ultra-goal] {reason}"}


def output_for(
    host: str | None, payload: dict[str, Any] | None
) -> dict[str, Any] | None:
    """The one allowlisted Stop-output shape for the host that asked.

    A deny is not portable, and the proof is two live consumers, not taste:
    Codex 0.150.1 blocks on the top-level pair and a mixed payload made the
    block inert, while Kimi 0.40.1's parser reads `message` and
    `hookSpecificOutput` only and blocks solely on
    `hookSpecificOutput.permissionDecision == "deny"` - it ignores the
    top-level pair entirely. One Stop output cannot be shared across
    vendors, so instead of emitting both shapes and hoping, this
    reconstructs exactly one shape per host from the decision and the
    reason and passes nothing else through: the top-level pair for Claude
    Code, Codex and zCode; the nested pair for Kimi, with the reason
    carrying everything the blocked turn must hear - on Kimi it is the only
    field that reaches the model. An allow is silent toward the model on
    every host (`systemMessage` speaks to the owner) and carries nothing to
    translate.
    """
    if payload is None or payload.get("decision") != "block":
        return payload
    reason = str(payload.get("reason") or "")
    if (host or DEFAULT_HOST) == "kimi":
        return {
            "hookSpecificOutput": {
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    return {"decision": "block", "reason": reason}


def _deny(host: str | None, reason: str) -> dict[str, Any]:
    """Refuse to let the turn end, in the host's own output shape.

    Two authoritative sources disagree about how a Stop hook blocks, and
    this gate once answered by emitting both in one payload. Codex 0.150.1
    settled that answer with a paired probe: the mixed payload (top-level
    `decision: block` plus nested `hookSpecificOutput.permissionDecision`)
    made the block inert - one Stop callback, no continuation - while the
    same probe sending only the top-level form blocked correctly. Deleting
    the nested form globally then broke the other consumer: Kimi 0.40.1
    blocks only on the nested pair. The fix is not to pick one shape but to
    stop sharing - `output_for` builds the one shape the asking host reads,
    and the reason carries everything, because a deny has exactly one
    channel on every host.
    """
    return output_for(host, {"decision": "block", "reason": reason})


def _obligation(found: dict[str, str], goal: ActiveGoal) -> str | None:
    """What the run owes before this turn ends. Fixed size, by design.

    This used to carry `### Next`, `### Lessons`, `### State` and every open
    `## Acceptance` line *with their current text*. On the first real artifact
    that was 4,683 characters, every turn, against a 40-turn ceiling - about
    47k tokens of text that barely changed from one turn to the next, re-sent
    to a model that could read the file.

    The rule that replaced it, and it is the one worth remembering:

        **A hook inlines only what it alone possesses. Everything already on
        disk gets a path.**

    What this hook alone possesses is the measurement it just took - it ran the
    anchor, the run did not - plus the obligation, which is the gate's to state
    and not the artifact's. The bodies of the mutable sections are on disk, and
    a run that is about to rewrite them has to read them anyway. Naming them
    without quoting them keeps the owner's rule intact - *what it reminds you
    of is exactly what you may change* - because the rule was about which
    sections, never about their contents.

    The counts stay inline because they are measurements too: how many
    acceptance lines are still open is a fact about the file, and a run that
    miscounts its remaining work is the failure this is here to prevent.
    """
    carry = found.get("carry-over") or ""
    present = [
        name for name in ("next", "lessons", "state") if _subsection(carry, name)
    ]
    acceptance = found.get("acceptance") or ""
    still_open = [
        line for line in acceptance.splitlines() if line.strip().startswith("- [ ]")
    ]
    if not present and not still_open:
        return None

    parts = [
        "Before you try to end this turn again, in `" + goal.goal_path.name + "`:",
    ]
    if present:
        parts.append(
            "- rewrite "
            + ", ".join(f"`### {name.title()}`" for name in present)
            + " under the carry-over section. Read them there - their current text "
            "is deliberately not repeated here. `### Next` takes exactly one "
            "objective, `### Lessons` a cause and a next action, never an event."
        )
    if still_open:
        parts.append(
            f"- the acceptance list has {len(still_open)} line(s) still open. A line "
            "moves to `[x]` only after its accepted anchor or review evidence showed it - not on "
            "reasoning about the code."
        )
    parts.append(
        "The intent, the boundary, the anchor, success/exit conditions, verification, "
        "acceptance requirements and labelled means are frozen. If one is "
        f"wrong, write a row under the challenges heading in "
        f"`{goal.decisions_path.name}` instead of editing it, and say you stopped "
        "for that reason."
    )
    return "\n".join(parts)


def _subsection(text: str, name: str) -> str | None:
    body: list[str] = []
    capturing = False
    for line in text.splitlines():
        if line.startswith("### "):
            if capturing:
                break
            capturing = line[4:].strip().lower() == name
            continue
        if capturing:
            body.append(line)
    joined = "\n".join(body).strip()
    return joined or None


def _signature(outcome: str, exit_code: int | None, digest: str) -> str:
    return f"{outcome}:{exit_code}:{digest}"


def _tree_digest(root: Path) -> str | None:
    """Digest of everything the anchor could see: HEAD, changed paths, content.

    `.goals` is excluded because the gate's own event log lives there and
    grows by one line with every check - counting it would make even a turn
    that did nothing read as progress. None means there is no work-tree fact
    (no Git, or Git failed), and the caller falls back to the anchor's output
    alone.

    Untracked-but-not-ignored files contribute their *content*, not just
    their path: `git status --porcelain` names an untracked file and
    `git diff HEAD` omits it entirely, so a path-only digest was blind to the
    one remaining kind of work - rewriting a file that was never committed.
    `git ls-files --others --exclude-standard` respects `.gitignore`, so
    build directories stay out. Content is hashed up to 1 MiB per file; an
    edit confined to the tail of a larger untracked file is unseen, which is
    a named bound, not an accident.
    """
    parts: list[str] = []
    for args in (
        ("rev-parse", "HEAD"),
        ("status", "--porcelain", "--", ":!.goals"),
        ("diff", "HEAD", "--", ":!.goals"),
        ("ls-files", "--others", "--exclude-standard", "-z", "--", ":!.goals"),
    ):
        try:
            completed = subprocess.run(
                ["git", *args],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0:
            return None
        parts.append(completed.stdout)
    for relative in sorted(p for p in parts.pop().split("\0") if p):
        digest = hashlib.sha256()
        try:
            with (root / relative).open("rb") as handle:
                digest.update(handle.read(1 << 20))
        except OSError:
            continue  # vanished or unreadable mid-digest: the path is still counted
        parts.append(f"{relative}\0{digest.hexdigest()}")
    return hashlib.sha256("\0".join(parts).encode("utf-8", "replace")).hexdigest()[:12]


# Events that end a host turn. Any of them between two denials means the
# denials cannot have been consecutive: the chain broke when the turn did.
# They size the denial streak only - since round 5 they are no longer the
# recovery window's edge for a delegation failure; recovery is a positive
# observation now (see `_unrecovered_failures`).
_TURN_BOUNDARIES = {
    "anchor_unavailable",
    "ceiling_reached",
    "frozen_spec_changed",
    "continuation_budget_spent",
    "stop_ordinary",
}


def _same_role(failure: dict[str, Any], recovery: dict[str, Any]) -> bool:
    return (
        failure.get("role") == recovery.get("role")
        and failure.get("tool") == recovery.get("tool")
    )


def _unrecovered_failures(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Outstanding transport observations for audit, never completion blockers.

    A same-target/tool success clears its prior failures. A fallback can satisfy
    acceptance without clearing these historical observations.
    """
    failures: list[dict[str, Any]] = []
    for entry in events:
        kind = entry.get("event")
        if kind == "role_unavailable":
            failures.append(entry)
        elif kind == "role_recovered":
            failures = [f for f in failures if not _same_role(f, entry)]
    return failures


def _omission_reminder(found: dict[str, str]) -> str:
    """The one short, deterministic line an ordinary Stop may carry.

    Counts and names only, toward the owner: which carry-over subsections
    are missing and how many acceptance lines are open. It cannot block,
    it cannot release completion, and it quotes nothing - a reminder built
    from file contents would be an oracle wearing a reminder's clothes.
    """
    carry = found.get("carry-over") or ""
    missing = [
        name for name in ("next", "lessons", "state")
        if not _subsection(carry, name)
    ]
    acceptance = found.get("acceptance") or ""
    still_open = [
        line for line in acceptance.splitlines() if line.strip().startswith("- [ ]")
    ]
    parts = []
    if missing:
        parts.append(
            "`## Carry-over` is missing "
            + ", ".join(f"`### {name.title()}`" for name in missing)
            + "."
        )
    if still_open:
        parts.append(f"{len(still_open)} `## Acceptance` line(s) are still open.")
    return " ".join(parts)


def _current_turn_id(events: list[dict[str, Any]]) -> Any | None:
    """The host turn this Stop belongs to, where a host names its turns.

    Kimi's TurnStarted fires for every new turn whatever its origin and
    carries `turn_id`; its Stop input carries no turn identity (0.40.1
    binary: `inputData: {stopHookActive: ...}` and nothing else), so the
    latest `turn_started` row is the strongest identity available. Hosts
    with no turn event (everyone else) get None, and the budget is scoped by
    boundaries instead. Turn ids are per-session ordinals; two concurrent
    sessions in one repository could collide on them - a named bound, not a
    solved one.
    """
    for entry in reversed(events):
        if entry.get("event") == "turn_started":
            return entry.get("turn_id")
    return None


def _denial_streak(
    events: list[dict[str, Any]], fresh_chain: bool = False
) -> int:
    """How many completion attempts in a row this gate has already denied -
    within the host turn that is still running.

    What it counts changed when the anchor moved to completion candidates:
    a denial is a refused claim (a red `anchor_checked`, or a
    `candidate_refused` for an unrecovered role failure), and an ordinary
    Stop denies nothing. The count is still bounded by turn boundaries this
    gate or its sibling hooks *observed*, never by the bare tail of a
    persistent log. The observable boundaries are:

    - a `turn_started` event - the host's own TurnStarted hook ran, which is
      the host saying a new turn began, whatever began it (Kimi's channel:
      the reference names user, task and system_trigger origins, so this is
      the one boundary that covers turns no user prompt opened, and it
      carries the host's `turn_id`);
    - a `prompt_submitted` event - the registered UserPromptSubmit hook ran.
      A user prompt is one origin of a turn, not the boundary itself, but
      the row is still an observation and still breaks the tail on hosts
      where no turn event exists;
    - any recorded decision that ends a turn - an allow, an ordinary stop,
      a ceiling, a closed run;
    - the host's own chain flag, passed in as `fresh_chain` - read only where
      the host's reference documents the field and its meaning.

    Where a `turn_started` row carries a `turn_id`, the count is additionally
    keyed by it: denials from a different host turn do not count, however
    the log is ordered. Events without a `turn_id` predate the counter and
    read as a boundary, which is the safe direction: a run upgraded
    mid-flight counts its budget from zero rather than inheriting a streak
    it cannot see.
    """
    if fresh_chain:
        return 0
    turn_id = _current_turn_id(events)
    streak = 0
    for entry in reversed(events):
        kind = entry.get("event")
        if kind == "anchor_checked":
            if not entry.get("blocked"):
                break
            if turn_id is not None and entry.get("turn_id") != turn_id:
                break
            streak += 1
        elif kind == "candidate_refused":
            if turn_id is not None and entry.get("turn_id") != turn_id:
                break
            streak += 1
        elif (
            kind == "turn_started"
            or kind == "prompt_submitted"
            or kind in _TURN_BOUNDARIES
        ):
            break
    return streak




def handle(
    event: dict[str, Any], goal: ActiveGoal, host: str | None = None, *,
    command: bool = False, claim: str = "Proposed completion"
) -> dict[str, Any] | None:
    # Both entry points share one native file lock. Closing/crashing releases it;
    # never unlink the inode, which could let another caller lock a different one.
    with (goal.goals_dir / f"{goal.slug}.verification.lock").open("a+b") as lock:
        try:
            if os.name == "nt":
                import msvcrt
                if lock.seek(0, 2) == 0:
                    lock.write(b"\0"); lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return _allow(f"{goal.slug}: verification is already in progress or its lock is unavailable; no new attempt was judged.")
        interrupted = [entry for entry in completion_attempts(read_events(goal))
                       if entry.get("event") == "verification_started"]
        if interrupted:
            # The former gate no longer holds this lock. Its anchor/remote effects
            # may still have occurred; never replay a surviving candidate blindly.
            try:
                (goal.goals_dir / f"{goal.slug}.candidate").unlink(missing_ok=True)
            except OSError:
                return _allow(f"{goal.slug}: interrupted verification remains unverified; its stale candidate could not be removed. Check actual state before a new explicit verify.")
            for previous in interrupted:
                if not append_event(goal, {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "event": "verification_interrupted",
                    "verification_id": previous.get("verification_id"),
                    "turn": previous.get("turn"),
                    "session_id": previous.get("session_id"),
                    "verification_passed": False,
                    "reason": "Verification started but did not record its outcome. Reconcile actual state before a new attempt; no automatic replay.",
                }):
                    return _allow(f"{goal.slug}: interrupted verification is unrecorded and unverified; fix the event log before retrying.")
            if not command:
                return _allow(f"{goal.slug}: previous verification was interrupted; its result is unknown. No anchor was replayed. Check actual state, then make a new explicit completion claim.")
        if command:
            candidate = goal.goals_dir / f"{goal.slug}.candidate"
            if not candidate.exists():
                candidate.write_text(claim.strip().splitlines()[0][:200] + "\n", encoding="utf-8")
        return _handle(event, goal, host, command=command)


def _handle(
    event: dict[str, Any], goal: ActiveGoal, host: str | None = None, *, command: bool = False
) -> dict[str, Any] | None:
    # `run_hook` checked the session bound during arming. Stop never claims
    # ownership: a foreign session may be the first one to finish here.
    session = event_session(event)
    # Commands supply a correlation ID; native Stop attempts need one as well.
    import uuid
    attempt_id = event["verification_id"] if command else uuid.uuid4().hex

    def write_event(entry: dict[str, Any]) -> bool:
        entry = {**entry, "verification_id": attempt_id}
        if command:
            entry["trigger"] = "command"
        return append_event(goal, entry)

    spec = goal.goal_path.read_text(encoding="utf-8")
    found = sections(spec)
    anchor_section = found.get("anchor") or ""
    anchor, ambiguous = _first_command(anchor_section)
    digest = frozen_digest(spec)

    events = read_events(goal)
    candidates = completion_attempts(events)
    turn = len(candidates) + 1
    candidate_path = goal.goals_dir / f"{goal.slug}.candidate"

    # The authorized baseline is the digest the arming command recorded in
    # `.goals/<slug>.spec.baseline` before any Stop could run. It is
    # compared on any Stop, candidate or not, because the check is a digest
    # comparison and never needs the anchor to run - so a moved goalpost
    # cannot hide behind "no claim was made". A digest inside the event log
    # is deliberately never consulted: the run can write the log, and a
    # completion candidate arriving first must not author its own baseline.
    # Allows, loudly: see the module docstring.
    armed = read_spec_baseline(goal)
    if armed is not None and armed != digest:
        write_event({
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": "frozen_spec_changed",
                "turn": turn,
                "completion_candidate": candidate_path.is_file(),
                "spec_digest_armed": armed,
                "spec_digest_now": digest,
            },
        )
        # The run is closed, not merely scolded. There is no mid-run
        # re-baseline: the armed digest was written by the owner's arming
        # command, so a changed spec can only mean the run's terms ended.
        # The disarm is checked - an unlink that failed is not a disarm,
        # and announcing one while the marker survives was the round-4
        # false-terminal probe. The observations stay for `--audit` and
        # Git, and the owner reopens the interview.
        def _drop(path: Path) -> bool:
            try:
                path.unlink()
                return True
            except OSError:
                return False

        marker_gone = _drop(goal.marker_path)
        _drop(candidate_path)
        if marker_gone:
            tail = (
                "The run is closed and the gate is disarmed; report what changed and "
                "why. To pursue the changed goal, the owner reopens the interview and "
                "a new run starts against a new spec - a fresh start clears the event "
                "log and baselines by hand. Do not carry on against the edited spec."
            )
        else:
            tail = (
                f"The run is closed, but the gate could not remove its own marker "
                f"({goal.marker_path.name} would not delete), so hooks will keep "
                f"seeing this run until it is removed by hand: `rm {goal.marker_path}`. "
                "Report what changed and why; the owner reopens the interview for a "
                "new spec."
            )
        return _allow(
            f"{goal.slug}: Intent, Boundary, Anchor, Stop condition, Verification, "
            "Acceptance requirements or a labelled Means declaration has changed since "
            f"the gate was armed ({armed} -> {digest}). Those are frozen for the "
            f"duration of the run, so this is no longer the goal the owner "
            f"authorized. {tail}"
        )

    if not candidate_path.is_file():
        # An ordinary Stop: the run wants to end a host turn, and that is
        # all it means. No anchor runs, nothing is judged, and the one line
        # it may carry is the deterministic omission reminder - counts and
        # names toward the owner, never an oracle.
        reminder = _omission_reminder(found)
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "stop_ordinary",
            "spec_digest": digest,
            "attempts": len(candidates),
        }
        turn_id = _current_turn_id(events)
        if turn_id is not None:
            entry["turn_id"] = turn_id
        if session is not None:
            entry["session_id"] = session
        write_event(entry)
        message = f"{goal.slug}: turn ended without a completion claim."
        if reminder:
            message += " " + reminder
        if armed is None:
            message += (
                " (No arming-time spec baseline is recorded for this run, so its "
                "completion claims will be refused rather than judged - re-arm "
                "through the arming command to fix that.)"
            )
        return _allow(message)

    # Record the start before consuming or judging: one claim, one
    # judgment, and state that changes after the check cannot resurrect a
    # claim the gate already ruled on - a new claim needs a new marker.
    # The read and the unlink are separate because they can fail
    # separately, and an unlink that failed is not a consumption: judging
    # anyway would let one surviving marker be judged on every following
    # Stop - the round-4 probe got two "passed attempt" announcements out
    # of one candidate that way. A claim that cannot be consumed is
    # refused, never judged.
    try:
        claim_text = candidate_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        claim_text = ""
    if not write_event({
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": "verification_started",
        "turn": turn,
        "session_id": session,
        "trigger": "command" if command else "stop",
        "spec_digest": digest,
        "claim": claim_text.strip().splitlines()[0][:200] if claim_text.strip() else "",
    }):
        return _allow(f"{goal.slug}: verification start is unrecorded; the claim remains pending and no anchor ran. Fix the event log before retrying; the result is unverified.")
    consumed = False
    try:
        candidate_path.unlink()
        consumed = True
    except OSError:
        consumed = False

    facts = host_facts(host)
    # An ordinary tool call returns directly; it does not deny a host Stop.
    budget = None if command else facts.continuation_budget
    fresh_chain = (
        facts.chain_flag is not None and event.get(facts.chain_flag) is False
    )
    turn_id = _current_turn_id(events)

    def refuse(reason: str, **extra: Any) -> dict[str, Any]:
        """Record and return one refused candidate, budget-bounded."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "candidate_refused",
            "trigger": "command" if command else "stop",
            "turn": turn,
            "reason": reason,
            **extra,
        }
        if turn_id is not None:
            entry["turn_id"] = turn_id
        if session is not None:
            entry["session_id"] = session
        write_event(entry)
        if budget is not None and _denial_streak(events, fresh_chain) >= budget:
            write_event({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "event": "continuation_budget_spent",
                    "turn": turn,
                    "host": host or DEFAULT_HOST,
                    "budget": budget,
                    "refusal": reason,
                    **extra,
                },
            )
            return _allow(
                f"{goal.slug}: this completion claim was refused ({reason}), and "
                f"this gate's own bound of {budget} consecutive denied attempt(s) "
                f"for one host turn is spent ({facts.source}). The turn ends here "
                "with the goal unmet. Retry the role or its declared fallback, then "
                "claim completion again."
            )
        return _deny(host, f"{goal.slug}: completion claim refused ({reason}).")

    if not consumed:
        return refuse(
            "the claim's marker could not be removed, so it was not judged - a "
            "claim the gate cannot consume must not be judged twice. Make "
            f"`{goal.goals_dir.name}` writable and claim again",
        )

    stop_section = found.get("stop condition") or ""
    ceiling, declared = _ceiling(stop_section)

    # The ceiling is the owner's, it bounds completion attempts, and every
    # candidate is one attempt - refused ones included, which is why the
    # count above includes `candidate_refused`. It wins even when the goal
    # is unmet, and it is checked before the refusals so an owner-declared
    # bound can end a run that would otherwise deny forever. `None` means
    # the owner declared no ceiling, so this step does not exist for that
    # run. Substituting a number here is how a long run gets stopped in its
    # owner's voice by a limit they never set.
    if ceiling is not None and turn > ceiling:
        write_event({
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": "ceiling_reached",
                "turn": turn,
                "ceiling": ceiling,
                "ceiling_source": "declared" if declared else "default",
            },
        )
        source = (
            "" if declared else
            f" This ceiling is this gate's default, not yours: no turn count could be "
            f"read from `## Stop condition`, so state one there in the form "
            f"`or after N turns`."
        )
        return _allow(
            f"{goal.slug}: ceiling of {ceiling} completion attempts reached without "
            f"meeting the goal. Stopping. Report what is left rather than claiming "
            f"success.{source}"
        )

    # No authorized baseline, no judgment. The arming command records the
    # frozen digest before any Stop can run; a run whose baseline is absent
    # was never armed through the fence, and its claims are refused rather
    # than "verified" against a spec nobody armed - the alternative was the
    # round-4 laundering hole, where the first event to arrive authored the
    # baseline.
    if armed is None:
        return refuse(
            "no arming-time spec baseline is recorded for this run, so there is "
            "no authorized spec to complete against. Disarm and re-arm through the "
            "arming command (`goal_run.py disarm`/`arm`), then claim again"
        )

    if ambiguous is not None or not anchor:
        # Recorded, not just announced. Deliberately *not* an
        # `anchor_checked` event: nothing was checked - but the candidate
        # was consumed, so it counts as an attempt and is recorded as one.
        reason = ambiguous or (
            "no runnable anchor in `## Anchor`, so nothing can be gated. Fix the "
            "artifact or the gate is decorative"
        )
        write_event({
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": "anchor_unavailable",
                "turn": turn,
                "reason": reason,
                "spec_digest": digest,
            },
        )
        return _allow(f"{goal.slug}: {reason}.")

    # A transport failure is an observation, not an acceptance requirement.
    # Required outputs are checked by the anchor/review contract. A successful
    # authorized fallback may satisfy it while the original target stays down.
    unrecovered = _unrecovered_failures(events)
    try:
        check_protection(goal, spec)
        review_evidence = check_review(goal, spec)
    except (ValueError, OSError) as exc:
        return refuse(str(exc), verification_passed=False)

    # Is the anchor even runnable? Answered by looking, not by inference.
    if not _resolvable(anchor, goal.goals_dir.parent):
        recorded = write_event({
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": "anchor_checked",
                "turn": turn,
                "anchor": anchor,
                "anchor_digest": hashlib.sha256(
                    anchor.encode("utf-8", "replace")
                ).hexdigest()[:12],
                "outcome": "unknown",
                "exit_code": None,
                "output_digest": "",
                "signature": "unknown:unresolvable:",
                "spec_digest": digest,
                "blocked": False,
                "tail": "executable not found",
            },
        )
        return _allow(
            f"{goal.slug}: the anchor's command was not found on PATH, so whether "
            "the work landed is unknown - not failed. Stopping. Fix the anchor or "
            "say the result is unverified; do not guess either way."
            + ("" if recorded else
               " The event log could not be written, so this attempt is unrecorded.")
        )

    # The gate itself executes the current anchor once against the current
    # state and rules on that result alone. The work tree is digested after
    # the run as the post-anchor state identity: a conservative
    # approximation of "the state this measurement is about", recorded with
    # that limit stated.
    seconds, budget_declared = _budget(anchor_section)
    try:
        completed = subprocess.run(
            anchor,
            shell=True,
            cwd=str(goal.goals_dir.parent),
            capture_output=True,
            text=True,
            timeout=seconds,
        )
        exit_code: int | None = completed.returncode
        output = (completed.stdout + completed.stderr).strip()
        if exit_code == 0:
            outcome = "green"
        elif exit_code in UNRUNNABLE_EXITS:
            outcome = "unknown"
        else:
            outcome = "red"
    except subprocess.TimeoutExpired:
        exit_code, output, outcome = None, "", "unknown"
    except (OSError, ValueError) as exc:
        exit_code, output, outcome = None, str(exc), "unknown"

    tree_after = _tree_digest(goal.goals_dir.parent)

    output_digest = hashlib.sha256(output.encode("utf-8", "replace")).hexdigest()[:12]
    # Anchor commands must be observational. Recheck after execution so a
    # command cannot rewrite its own evaluator or invalidate an earlier review.
    try:
        if frozen_digest(goal.goal_path.read_text(encoding="utf-8")) != digest:
            raise ValueError("Frozen goal terms changed during verification; stop and report instead of continuing.")
        check_protection(goal, spec)
        review_evidence = check_review(goal, spec, retain=True)
    except (ValueError, OSError) as exc:
        return refuse(str(exc), verification_passed=False, anchor_outcome=outcome,
                      anchor_exit_code=exit_code, output_digest=output_digest)
    signature = _signature(outcome, exit_code, output_digest)
    checks = [e for e in events if e.get("event") == "anchor_checked"]

    def record(blocked: bool) -> bool:
        """Write the measurement, and say whether it landed.

        The write is checked because announcing "passed on attempt N" over
        an unwritten log was a false announcement: round 4's probe got a
        green allow out of a gate whose event log stayed zero bytes. A
        failed write is reported to the owner as unrecorded - never as a
        filed measurement.
        """
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "anchor_checked",
            "turn": turn,
            "trigger": "command" if command else "stop",
            "anchor": anchor,
            "anchor_digest": hashlib.sha256(
                anchor.encode("utf-8", "replace")
            ).hexdigest()[:12],
            "claim": claim_text.strip().splitlines()[0][:200]
            if claim_text.strip() else "",
            "outcome": outcome,
            "verification_passed": outcome == "green",
            "review_evidence": review_evidence,
            "unrecovered_targets": sorted({str(e.get("role")) for e in unrecovered}),
            "exit_code": exit_code,
            "output_digest": output_digest,
            "signature": signature,
            "spec_digest": digest,
            "budget_seconds": seconds,
            "budget_source": "declared" if budget_declared else "default",
            "tree_digest": tree_after,
            "blocked": blocked,
            "tail": output.splitlines()[-1][:200] if output else "",
        }
        if turn_id is not None:
            entry["turn_id"] = turn_id
        if session is not None:
            entry["session_id"] = session
        return write_event(entry)

    if outcome == "unknown":
        if exit_code is None:
            detail = (
                f"ran past its {seconds}s budget"
                + ("" if budget_declared else ", which is this gate's default - declare "
                   "one in `## Anchor` as `budget: N minutes` if the anchor needs longer")
            )
        else:
            detail = f"exit {exit_code}"
        recorded = record(False)
        return _allow(
            f"{goal.slug}: the anchor could not run ({detail}) on attempt {turn}, so "
            "whether the work landed is unknown - not failed. Stopping. Say it is "
            "unverified rather than guessing either way."
            + ("" if recorded else
               " The event log could not be written, so this attempt is unrecorded - "
               "report it as unverified and unwitnessed.")
        )

    if outcome == "green":
        recorded = record(False)
        return _allow(
            f"{goal.slug}: anchor `{anchor}` passed on attempt {turn}. "
            "The current accepted verification contract passed, including required review. "
            "Checkboxes are progress claims, not additional evidence. This establishes the "
            "agreed checks, not that the specification can never be wrong."
            + (f" Original delegation failures remain recorded for {len(unrecovered)} call(s); "
               "current acceptance evidence satisfied the obligations." if unrecovered else "")
            + ("" if recorded else
               " The event log could not be written, so this attempt is unrecorded - "
               "report the verdict as unwitnessed and fix the log before the next "
               "claim.")
        )

    # Red: the claim is refused and the turn is held. Two identical
    # signatures are recorded and named, never released on - identical
    # failure output does not prove no progress, and releasing on the second
    # one cuts off investigation and long fixes.
    previous = checks[-1] if checks else None
    repeated = previous is not None and previous.get("signature") == signature
    note = (
        " This attempt's output is byte-identical to the previous attempt's - "
        "recorded, not a release: identical failure output does not prove no "
        "progress."
        if repeated else ""
    )

    # How much longer may this turn be held? The bound is the gate's own -
    # how many attempts in a row it will deny within one host turn it can
    # observe - sized by the host's force-end where one is known, as a
    # backstop and never as a claim about how the host counts.
    if budget is not None and _denial_streak(events, fresh_chain) >= budget:
        recorded = record(False)
        write_event({
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": "continuation_budget_spent",
                "turn": turn,
                "host": host or DEFAULT_HOST,
                "budget": budget,
                "outcome": "red",
                "exit_code": exit_code,
            },
        )
        message = (
            f"{goal.slug}: anchor `{anchor}` is still red (exit {exit_code}) on "
            f"attempt {turn}, and this gate's own bound of {budget} consecutive "
            f"denied attempt(s) for one host turn is spent ({facts.source}). The turn "
            "ends here with the goal unmet. Write `### Lessons` and `### Next`, "
            "preserve this measured attempt in the event log, and commit only if "
            "the owner already authorized it. A native continuation driver or an "
            "explicit next prompt is needed to resume. The ceiling still binds: the event log keeps the "
            "count."
        )
        if (host or DEFAULT_HOST) == "claude":
            message += (
                " The host's own force-end is CLAUDE_CODE_STOP_HOOK_BLOCK_CAP "
                "(default 8) consecutive blocks with no tool progress in between - "
                "the backstop this bound stays under, not the bound itself."
            )
        if not recorded:
            message += (
                " The event log could not be written, so this attempt is unrecorded."
            )
        return _allow(message)

    # `of {ceiling}` printed "of None" for a run the owner declared unbounded.
    # It says nothing at all there instead: a run without a ceiling should never
    # read the word, and inventing a number is what `_ceiling` exists to prevent.
    of_ceiling = f" of {ceiling}" if ceiling is not None else ""
    deny_reason = (
        f"{goal.slug}: completion claim refused - anchor `{anchor}` is still failing "
        f"(exit {exit_code}) on attempt {turn}{of_ceiling}, so the goal is not met. "
        "Keep working, and run the applicable verification yourself with ordinary "
        "tools after your next relevant change rather than waiting for this gate. "
        "Before the next claim, write one lesson into `### Lessons` naming the cause "
        "and the next action. Perform the agreed checks in `## Verification` when "
        f"their acceptance condition applies; do not repeat them by habit.{note}"
    )
    if budget == 1:
        # A one-block host never invokes this gate again after blocking: when
        # the turn ends there is no second message, so the park instructions
        # travel with the only message the run will get.
        deny_reason += (
            " This host continues a blocked turn at most once: when the turn "
            "ends, rewrite `### Lessons` and `### Next`; commit only with existing "
            "owner authorization. A corrected candidate remains pending until "
            "an actual later hook checks it. Continue on the next native turn or prompt - "
            "the ceiling still binds on the attempt count."
        )
    obligation = _obligation(found, goal)
    if obligation:
        deny_reason += "\n" + obligation
    recorded = record(True)
    if not recorded:
        deny_reason += (
            "\nThe event log could not be written: this attempt is unrecorded - "
            "say so in your report rather than citing a measurement nobody can read."
        )
    return _deny(host, deny_reason)


if __name__ == "__main__":
    # Exit 2 is the one code every host here reads as a deliberate block, and
    # it is also what Python itself returns for an unreadable script and what
    # argparse returns for a bad argument - so the fail-open has to cover the
    # launch and the argument handling, not only the inside of `run_hook`.
    # SystemExit is a BaseException: argparse's error exit is caught here and
    # downgraded to the one code a broken hook is allowed to return.
    try:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument(
            "--host",
            default=DEFAULT_HOST,
            help="which host is running this hook; sets the continuation budget",
        )
        args, _unrecognized = parser.parse_known_args()
        code = run_hook("Stop", handle, host=args.host)
    except BaseException:  # noqa: BLE001 - launch and argparse fail open too
        code = 0
    raise SystemExit(code)
