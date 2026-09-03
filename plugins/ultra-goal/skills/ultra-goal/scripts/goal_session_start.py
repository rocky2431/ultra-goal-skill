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
CONTEXT_LIMIT = 6000
# What a resuming session needs, most important first. `## Handoff` is absent on
# purpose: it holds the command that starts the run, and the run is already
# started - injecting it wastes the budget that `## Carry-over` needs.
# Measured before choosing this: injecting the whole artifact truncated the
# shipped template mid-clause at the default limit, on day one.
INJECT_ORDER = (
    "intent",
    "boundary",
    "anchor",
    "stop condition",
    "means",
    "carry-over",
    "verification",
    "cadence",
)
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
