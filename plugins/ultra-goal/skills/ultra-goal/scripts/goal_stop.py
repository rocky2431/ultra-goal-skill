#!/usr/bin/env python3
"""Stop hook: the anchor gate.

Eight steps, seven of which let the turn end. A mechanical gate's default has
to be "allow" - it only refuses where it is certain.

It refuses while the anchor ran and was red, up to the host's continuation
budget: every host counts consecutive Stop blocks differently (Claude Code
force-ends at 8, zCode at 3, Kimi triggers a blocking Stop once per turn,
Codex documents no cap), so the gate counts its own blocks in the event log
and releases one before the host's cap - the last word is its reason, not the
host's force-end warning. Everything else - frozen spec changed, ceiling
reached, run not progressing, budget spent, anchor unrunnable, anchor green -
lets the turn end and says why.

A changed frozen spec is the least obvious of those and it allows on purpose:
if the intent, the boundary or the anchor moved, the run is no longer pursuing
the goal the owner authorized, and denying the stop would only make it work
harder on a target nobody agreed to. The right response is to end the turn
loudly and put it back in front of the owner.

The third outcome is the one that is easy to leave out and expensive to get
wrong. An anchor that cannot run is not a failed anchor; it is an unknown, and
folding unknown into either verdict is how a mechanical gate starts lying. A
timeout is the same class of mistake: it measures elapsed time and reports it
as success or failure, two things it has no access to.
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
    frozen_digest,
    host_facts,
    read_events,
    run_hook,
    sections,
)


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


def _allow(reason: str, context: str | None = None) -> dict[str, Any]:
    """End the turn, telling the owner why and the model what it may change.

    `additionalContext` is documented for Stop as "Feedback for the model; the
    conversation continues so the model can act on it", and it carries exactly
    the mutable surface - nothing frozen. A reminder about something the run may
    not change has one effect: it invites the change.
    """
    payload: dict[str, Any] = {"systemMessage": f"[ultra-goal] {reason}"}
    if context:
        payload["hookSpecificOutput"] = {
            "hookEventName": "Stop",
            "additionalContext": context,
        }
    return payload


def _deny(reason: str, context: str | None = None) -> dict[str, Any]:
    """Refuse to let the turn end, in every documented form at once.

    Two authoritative sources disagree about how a Stop hook blocks, and both
    were read directly rather than assumed:

    - The official hooks reference lists, for Stop,
      `hookSpecificOutput.permissionDecision: "allow|deny"` alongside
      `additionalContext` and `systemMessage`.
    - The running binary's own validator, when it rejected a malformed payload,
      printed a schema in which Stop's `hookSpecificOutput` carries only
      `hookEventName` and `additionalContext`, with `decision: "approve"|"block"`
      and `reason` at the top level.

    I changed this once on the strength of the second source alone and broke a
    field that the first source documents. So it now emits both, and says why:
    when the sources conflict, satisfying both costs a few bytes, while picking
    one costs the only hard power in the design. The docs also record a third
    route - exit code 2 - which this deliberately does not use, because exiting
    non-zero would discard the JSON that carries the reason.

    Which one the host honours is still a claim until a live run settles it. The
    observable is simple: a denied turn does not end.
    """
    payload: dict[str, Any] = {
        "decision": "block",
        "reason": reason,
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }
    if context:
        payload["hookSpecificOutput"]["additionalContext"] = context
    return payload


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
        "Before this turn ends, in `" + goal.goal_path.name + "`:",
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
            "moves to `[x]` only after the anchor's output showed it - not on "
            "reasoning about the code."
        )
    parts.append(
        "The intent, the boundary and the anchor are frozen. If one of them is "
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
    """
    parts: list[str] = []
    for args in (
        ("rev-parse", "HEAD"),
        ("status", "--porcelain", "--", ":!.goals"),
        ("diff", "HEAD", "--", ":!.goals"),
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
    return hashlib.sha256("\0".join(parts).encode("utf-8", "replace")).hexdigest()[:12]


def _stagnant(
    previous: dict[str, Any] | None, signature: str, tree: str | None
) -> bool:
    """Did nothing measurable move since the last check?

    The anchor's output alone cannot answer this. A suite printing the same
    failing summary is what honest mid-run progress looks like - the output
    stays byte-identical until the work suddenly lands - so an unchanged
    result releases the turn only when the work tree did not move either.
    Where no work-tree fact exists on either side (a pre-counter event, or a
    project without Git), the output is the only measurable left, which is
    the rule this replaces and its fallback.
    """
    if previous is None or previous.get("signature") != signature:
        return False
    previous_tree = previous.get("tree_digest")
    if tree is None or previous_tree is None:
        return True
    return previous_tree == tree


def _block_streak(checks: list[dict[str, Any]]) -> int:
    """How many anchor checks in a row this gate has already blocked.

    A measurement from this gate's own log. Events without a `blocked` field
    predate the counter and read as allows, which is the safe direction: a run
    upgraded mid-flight counts its budget from zero rather than inheriting a
    streak it cannot see.
    """
    streak = 0
    for check in reversed(checks):
        if not check.get("blocked"):
            break
        streak += 1
    return streak


def handle(
    event: dict[str, Any], goal: ActiveGoal, host: str | None = None
) -> dict[str, Any] | None:
    spec = goal.goal_path.read_text(encoding="utf-8")
    found = sections(spec)
    anchor_section = found.get("anchor") or ""
    anchor, ambiguous = _first_command(anchor_section)
    budget, budget_declared = _budget(anchor_section)
    if ambiguous is not None or not anchor:
        # Recorded, not just announced. These two turns used to leave the log
        # empty, so an artifact the gate could never enforce produced a run that
        # looked, in `--audit` and in the event log, exactly like a run that had
        # not started yet. Deliberately *not* an `anchor_checked` event: nothing
        # was checked, so it must not advance the turn count or the ceiling.
        reason = ambiguous or (
            "no runnable anchor in `## Anchor`, so nothing can be gated. Fix the "
            "artifact or the gate is decorative"
        )
        append_event(
            goal,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": "anchor_unavailable",
                "turn": len([e for e in read_events(goal)
                             if e.get("event") == "anchor_checked"]) + 1,
                "reason": reason,
                "spec_digest": frozen_digest(spec),
            },
        )
        return _allow(f"{goal.slug}: {reason}.")

    events = read_events(goal)
    checks = [e for e in events if e.get("event") == "anchor_checked"]
    turn = len(checks) + 1
    digest = frozen_digest(spec)

    # Step 3: did the frozen spec move? Compared against the first turn's
    # record, not the previous one, so a change followed by a change back is
    # still a change. Allows, and says so loudly - see the module docstring.
    first = next((c.get("spec_digest") for c in checks if c.get("spec_digest")), None)
    if first is not None and first != digest:
        append_event(
            goal,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": "frozen_spec_changed",
                "turn": turn,
                "spec_digest_first": first,
                "spec_digest_now": digest,
            },
        )
        return _allow(
            f"{goal.slug}: `## Intent`, `## Boundary` or `## Anchor` has changed since "
            f"turn 1 ({first} -> {digest}). Those are frozen for the duration of the "
            "run, so this is no longer the goal the owner authorized. Stopping. Report "
            "what changed and why, and let the owner reopen the interview - do not "
            "carry on against the edited spec."
        )

    stop_section = found.get("stop condition") or ""
    ceiling, declared = _ceiling(stop_section)

    # Step 4: the ceiling is the owner's, and it wins even when the goal is unmet.
    # `None` means the owner declared no ceiling, so this step does not exist for
    # that run. Substituting a number here is how a long run gets stopped in its
    # owner's voice by a limit they never set.
    if ceiling is not None and turn > ceiling:
        append_event(
            goal,
            {
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
            f"{goal.slug}: ceiling of {ceiling} turns reached without meeting the "
            f"goal. Stopping. Report what is left rather than claiming success.{source}",
            _obligation(found, goal),
        )

    # Step 6: is the anchor even runnable? Answered by looking, not by inference.
    if not _resolvable(anchor, goal.goals_dir.parent):
        append_event(
            goal,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": "anchor_checked",
                "turn": turn,
                "anchor": anchor,
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
        )

    # Step 7+8: run it. Three outcomes, not two. The work tree is digested
    # first, before the anchor can dirty it with its own side effects, so
    # "did anything move" measures the run's work and not the anchor's
    # footprint.
    tree_digest = _tree_digest(goal.goals_dir.parent)
    try:
        completed = subprocess.run(
            anchor,
            shell=True,
            cwd=str(goal.goals_dir.parent),
            capture_output=True,
            text=True,
            timeout=budget,
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

    output_digest = hashlib.sha256(output.encode("utf-8", "replace")).hexdigest()[:12]
    signature = _signature(outcome, exit_code, output_digest)

    def record(blocked: bool) -> None:
        append_event(
            goal,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": "anchor_checked",
                "turn": turn,
                "anchor": anchor,
                "outcome": outcome,
                "exit_code": exit_code,
                "output_digest": output_digest,
                "signature": signature,
                "spec_digest": digest,
                "budget_seconds": budget,
                "budget_source": "declared" if budget_declared else "default",
                "tree_digest": tree_digest,
                "blocked": blocked,
                "tail": output.splitlines()[-1][:200] if output else "",
            },
        )

    if outcome == "unknown":
        if exit_code is None:
            detail = (
                f"ran past its {budget}s budget"
                + ("" if budget_declared else ", which is this gate's default - declare "
                   "one in `## Anchor` as `budget: N minutes` if the anchor needs longer")
            )
        else:
            detail = f"exit {exit_code}"
        record(False)
        return _allow(
            f"{goal.slug}: the anchor could not run ({detail}), so whether the work "
            "landed is unknown - not failed. Stopping. Say it is unverified rather "
            "than guessing either way.",
            _obligation(found, goal),
        )

    if outcome == "green":
        # "Goal met" was this gate claiming something it cannot measure. A green
        # anchor is one command exiting 0; whether the goal is met is
        # `## Stop condition`'s question and `## Acceptance`'s evidence. Saying
        # otherwise put the Skill's own doctrine - a green anchor is not a pass -
        # in the mouth of the one component with hard power.
        still_open = [
            line for line in (found.get("acceptance") or "").splitlines()
            if line.strip().startswith("- [ ]")
        ]
        left = (
            f" {len(still_open)} `## Acceptance` line(s) are still open, so this is not "
            "the goal yet: report the verdict and what is left."
            if still_open else
            " No `## Acceptance` line is still open. Whether that means the run is done "
            "is `## Stop condition`'s question, not this gate's - check it before "
            "claiming completion."
        )
        record(False)
        return _allow(
            f"{goal.slug}: anchor `{anchor}` passed on turn {turn}.{left}",
            _obligation(found, goal),
        )

    # Step 5: red, but is anything changing? The anchor's output alone cannot
    # answer that - a suite printing the same failing summary is what honest
    # mid-run progress looks like, so the turn is released only when neither
    # the output nor the work tree moved. Judged before the budget: a stuck
    # run's truest ending is "not progressing", not "budget spent".
    if _stagnant(checks[-1] if checks else None, signature, tree_digest):
        record(False)
        return _allow(
            f"{goal.slug}: the anchor produced an identical result and the work "
            f"tree did not move since the last check (turn {turn}), so the run is "
            "not progressing. Stopping. Report what is blocking it instead of "
            "retrying.",
            _obligation(found, goal),
        )

    # Red and moving. How much longer may this turn be held? The host's
    # continuation budget is the number of consecutive blocks it will honor;
    # spending it means blocking again would only meet the host's force-end,
    # whose last word would be a warning instead of this gate's reason. A red
    # anchor may end a turn only by saying so, never silently.
    facts = host_facts(host)
    budget = facts.continuation_budget
    if budget is not None and _block_streak(checks) >= budget:
        record(False)
        append_event(
            goal,
            {
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
            f"{goal.slug}: anchor `{anchor}` is still red (exit {exit_code}) on turn "
            f"{turn}, and this host's continuation budget is spent - it honors at most "
            f"{budget} consecutive block(s) ({facts.source}). The turn ends here with "
            "the goal unmet. Write `### Lessons` and `### Next`, commit this turn as "
            f"`goal({goal.slug}) turn {turn}: ... [anchor: red]` - one anchor check is "
            "one turn, so commit under the gate's number - and the next prompt "
            "continues the run. The ceiling still binds: the event log keeps the count."
        )
        if (host or DEFAULT_HOST) == "claude":
            message += (
                " The host's own cap is CLAUDE_CODE_STOP_HOOK_BLOCK_CAP (default 8); "
                "the owner can raise it to continue more per turn."
            )
        return _allow(message, _obligation(found, goal))

    # `of {ceiling}` printed "of None" for a run the owner declared unbounded.
    # It says nothing at all there instead: a run without a ceiling should never
    # read the word, and inventing a number is what `_ceiling` exists to prevent.
    of_ceiling = f" of {ceiling}" if ceiling is not None else ""
    deny_reason = (
        f"{goal.slug}: anchor `{anchor}` is still failing (exit {exit_code}) on turn "
        f"{turn}{of_ceiling}, so the goal is not met. Keep working. Before the next "
        "attempt, write one lesson into `### Lessons` naming the cause and the next "
        "action. The anchor is this turn's check; the reviewer and critic in "
        "`## Verification` run when you propose completion, not on every red turn."
    )
    if budget == 1:
        # A one-block host never invokes this gate again after blocking: when
        # the turn ends there is no second message, so the park instructions
        # travel with the only message the run will get.
        deny_reason += (
            " This host continues a blocked turn at most once: when the turn "
            f"ends, commit it as `goal({goal.slug}) turn {turn}: ... [anchor: red]`, "
            "rewrite `### Lessons` and `### Next`, and continue on the next prompt - "
            "the ceiling still binds on the event log's count."
        )
    record(True)
    return _deny(deny_reason, _obligation(found, goal))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help="which host is running this hook; sets the continuation budget",
    )
    args, _unrecognized = parser.parse_known_args()
    raise SystemExit(run_hook("Stop", handle, host=args.host))
