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
from goal_hooks import ActiveGoal, read_events, run_hook, sections  # noqa: E402


SOURCES = {"startup", "resume", "clear", "compact"}
# Raised from 6000 once `## Roles` and `## Acceptance` existed: measured, the
# load-bearing sections came to about 5.9k, so the old budget dropped
# `## Carry-over` - the state and lessons this hook exists to restore. A resume
# is rare (startup, resume, clear, compact), so a few hundred extra tokens
# there is far cheaper than resuming without knowing what was already learned.
CONTEXT_LIMIT = 8000
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


def handle(event: dict[str, Any], goal: ActiveGoal) -> dict[str, Any] | None:
    if event.get("source") not in SOURCES:
        return None

    spec = goal.goal_path.read_text(encoding="utf-8")
    found = sections(spec)
    checks = [e for e in read_events(goal) if e.get("event") == "anchor_checked"]
    last = checks[-1] if checks else None

    lines = [
        f"An active goal is running in this project: `{goal.slug}`.",
        "",
        f"Its artifact is `{goal.goal_path.name}` and it is the authority on what to do.",
        "The spec sections are frozen for the duration of the run: if the intent, the",
        "anchor, or the boundary turns out to be wrong, stop and report it rather than",
        "editing them yourself.",
        "",
        "You are the run, not its designer. Do not reopen the design as an interview.",
        "",
    ]
    if last is not None:
        lines += [
            f"Last anchor check: turn {last.get('turn')}, outcome "
            f"{last.get('outcome')}, exit {last.get('exit_code')}.",
            "",
        ]
    if event.get("source") == "compact":
        # A compacted model does not know it lost anything - it reads its own
        # summary as memory. PreCompact already recorded that a compaction
        # happened; this is the first time that fact reaches the model.
        lines += [
            "**This session was just compacted.** Your intermediate reasoning is gone,",
            "and what remains is a summary of it. Do not trust a recollection of having",
            "tried something: if it is not in `### Lessons`, in the event log, or in a",
            "commit, treat it as unknown and check.",
            "",
        ]
    lines += ["Read `## Carry-over` before acting and rewrite it before finishing.", ""]

    head = "\n".join(lines)
    budget = CONTEXT_LIMIT - len(head)
    body: list[str] = []
    dropped: list[str] = []
    for name in INJECT_ORDER:
        section = found.get(name)
        if section is None:
            continue
        block = f"\n## {name.title()}\n{section.rstrip()}\n"
        # Whole sections only. A section cut in half is worse than an absent
        # one: a truncated instruction still reads as an instruction.
        if len(block) > budget:
            dropped.append(name)
            continue
        body.append(block)
        budget -= len(block)

    context = head + "".join(body)
    missing = [name for name in ESSENTIAL if name in dropped]
    if missing:
        context += (
            f"\n**Could not inject {', '.join(missing)} - too large for the "
            f"{CONTEXT_LIMIT}-character budget.** Read `{goal.goal_path.name}` in full "
            "before doing anything; do not act on the sections above alone.\n"
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
