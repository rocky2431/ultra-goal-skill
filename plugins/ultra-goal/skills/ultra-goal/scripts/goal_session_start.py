#!/usr/bin/env python3
"""SessionStart hook: put the active goal back in front of the model.

A new or resumed session has no idea a goal is running. This injects the frozen
spec and the carried state, which is exactly the pair SKILL.state keeps: the
immutable procedural specification plus the current execution state.

It only ever adds context. It cannot block a session from starting.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from goal_hooks import ActiveGoal, completion_attempts, read_events, run_hook, sections  # noqa: E402


# Every source the hooks reference documents. `fork` was missing, so a forked
# session - which starts with the parent's context and then diverges - received
# no injection at all. Read from the docs rather than inferred from the four we
# happened to have seen.
SOURCES = {"startup", "resume", "clear", "compact", "fork"}
# Raised from 6000 once `## Roles` and `## Acceptance` existed: measured, the
# load-bearing sections came to about 5.9k, so the old budget dropped
# `## Carry-over` - the state and lessons this hook exists to restore. A resume
# is rare (startup, resume, clear, compact), so a few hundred extra tokens
# there is far cheaper than resuming without knowing what was already learned.
# What one session boundary may cost. 8000 was fitted to the shipped template,
# whose frozen terms are ~5.9k; the first real artifact's are 8.1k, so nothing
# optional reached a resuming run at all.
#
# The number is now derived rather than picked: a resumed run needs the four
# frozen terms, plus the two sections that answer "when do I stop" and "what is
# left" - `## Stop condition` and `## Acceptance`. On that artifact those are
# 8073 + 1465 + 2124 = 11662. Everything past them (means, roles, verification,
# cadence) is genuinely re-readable on demand.
#
# Paying more here got cheap on the same day the Stop hook stopped re-sending
# the mutable sections' text every turn: that was 4,683 characters per turn
# against a 40-turn ceiling, and this is paid once per restart or compaction.
CONTEXT_LIMIT = 12000
# What a resuming session needs, most important first. `## Handoff` is absent on
# purpose: it holds the command that starts the run, and the run is already
# started - injecting it wastes the budget that `## Carry-over` needs.
# Measured before choosing this: injecting the whole artifact truncated the
# shipped template mid-clause at the default limit, on day one.
# Recovery priority, most important first, because a section that does not fit
# is dropped whole. Order is not cosmetic here: adding `## Roles` (2.1k) pushed
# `## Carry-over` off the end, so a resuming session was handed `## Verification`
# instead of the state and lessons it needed. Two sections have gone missing from
# this list or its ordering already, which is what the two tests below are for.
INJECT_ORDER = (
    # The frozen terms: what is pursued, what may not be touched, what proves it.
    "intent",
    "boundary",
    "anchor",
    # Then what the run already knows. `### Lessons` is the only thing that makes
    # turn 7 better than turn 1; `### Next` is the objective it was aimed at.
    "carry-over",
    # Then what is left, and why.
    "acceptance",
    "stop condition",
    "means",
    "roles",
    # Then what can be re-read on demand without being stuck.
    "verification",
    "cadence",
)
# Never dropped quietly. If one of these will not fit, say so loudly instead of
# resuming a run that cannot see its own terms.
ESSENTIAL = ("intent", "boundary", "anchor", "carry-over")
# `## Handoff` holds the command that starts the run, and the run has started.
SKIP = ("handoff",)


def handle(
    event: dict[str, Any], goal: ActiveGoal, host: str | None
) -> dict[str, Any] | None:
    if event.get("source") not in SOURCES:
        return None

    spec = goal.goal_path.read_text(encoding="utf-8")
    found = sections(spec)
    attempts = completion_attempts(read_events(goal))
    unfinished = [e for e in attempts if e.get("event") == "verification_started"]
    last = unfinished[-1] if unfinished else attempts[-1] if attempts else None
    # The anchor runs at completion candidates now, so the count this names
    # is attempts, not host turns - a run may end many turns between them.

    lines = [
        f"An active goal is running in this project: `{goal.slug}`.",
        "",
        f"Its artifact is `{goal.goal_path.name}` and it is the authority on what to do.",
        "The spec sections are frozen for the duration of the run: if the intent, the",
        "anchor, boundary, acceptance, verification or success/exit conditions are wrong,",
        "stop and report rather than changing them. Read the complete contract before acting.",
        "",
        "You are the run, not its designer. Do not reopen the design as an interview.",
        "",
    ]
    if last is not None and last.get("event") in {"verification_started", "verification_interrupted"}:
        lines += [
            f"Latest verification: attempt {last.get('turn')} has no recorded result "
            "or was interrupted; completion is unverified. Earlier green is historical.",
            "Read the event log and actual state before retrying. Do not repeat an "
            "external action whose effect is unknown without first checking its result.",
            "",
        ]
    elif last is not None and last.get("event") == "anchor_checked":
        lines += [
            f"Last completion check: attempt {last.get('turn')}, outcome "
            f"{last.get('outcome')}, exit {last.get('exit_code')}.",
            "",
        ]
    elif last is not None:
        lines += [f"Latest completion attempt {last.get('turn')}: {last.get('event')}; "
                  "read its reason in the event log before acting.", ""]
    if event.get("source") == "compact":
        # A compacted model does not know it lost anything - it reads its own
        # summary as memory. PreCompact already recorded that a compaction
        # happened; this is the first time that fact reaches the model.
        lines += [
            "**This session was just compacted.** Some context may have been summarized",
            "or dropped. Do not trust a recollection of having",
            "tried something: if it is not in `### Lessons`, in the event log, or in a",
            "commit, treat it as unknown and check.",
            "",
        ]
    lines += ["Read `## Carry-over` before acting and rewrite it before finishing.", ""]

    def block(name: str) -> str:
        # Whole sections only. A section cut in half is worse than an absent
        # one: a truncated instruction still reads as an instruction.
        return f"\n## {name.title()}\n{found[name].rstrip()}\n"

    head = "\n".join(lines)

    # The frozen terms are not discretionary, so they are not budgeted. They
    # used to compete for space in one greedy pass, and on the first real
    # artifact that produced the worst possible outcome: `## Carry-over` was
    # refused for being 300 characters too large, and then `## Acceptance` -
    # which is not essential - fit into the space it had just vacated. An
    # essential displaced by a non-essential is not a budget working, it is a
    # budget deciding what the run is allowed to know.
    required = "".join(block(name) for name in ESSENTIAL if name in found)

    # A section this list has never heard of used to be skipped in silence:
    # neither injected nor named among the dropped, so an artifact that grew a
    # heading of its own lost it without a word. Unknown sections go last -
    # nothing known should be displaced by them.
    extra = [n for n in found if n not in INJECT_ORDER and n not in SKIP]
    budget = CONTEXT_LIMIT - len(head) - len(required)
    # Recorded before the loop, which zeroes `budget` when it stops early: a
    # dropped optional section would otherwise erase the fact that the frozen
    # terms had already overrun, and the overrun is the part worth saying.
    overrun = budget < 0
    body: list[str] = []
    dropped: list[str] = []
    for name in (*INJECT_ORDER, *extra):
        if name in ESSENTIAL or name not in found:
            continue
        candidate = block(name)
        if len(candidate) > budget:
            # A strict prefix, not a greedy fill. Greedy let a later, smaller
            # section take the place of an earlier, larger one - `## Stop
            # condition` was dropped and `## Verification` injected in the space
            # it left. INJECT_ORDER is a priority order, and size silently
            # reordering it is the same defect that let a non-essential displace
            # an essential. Once one section will not fit, nothing after it does.
            dropped.append(name)
            budget = 0
            continue
        body.append(candidate)
        budget -= len(candidate)

    context = head + required + "".join(body)
    if overrun:
        context += (
            f"\n**The frozen terms alone are {len(required)} characters, past the "
            f"{CONTEXT_LIMIT}-character target.** They are injected anyway: a run that "
            "cannot see its own intent, boundary, anchor and carry-over is worse than a "
            "long injection. Nothing optional was injected at all.\n"
        )
    if dropped:
        context += (
            f"\nNot injected for space: {', '.join(dropped)}. Read "
            f"`{goal.goal_path.name}` directly for those.\n"
        )

    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }


if __name__ == "__main__":
    raise SystemExit(run_hook("SessionStart", handle))
