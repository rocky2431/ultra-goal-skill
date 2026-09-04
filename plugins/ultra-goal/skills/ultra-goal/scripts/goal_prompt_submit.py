#!/usr/bin/env python3
"""UserPromptSubmit hook: Kimi's recovery channel, and the turn boundary.

Kimi's reference makes every event but PreToolUse, Stop and UserPromptSubmit
observation-only, so two things this plugin needs have no other path there:

- the frozen-spec injection other hosts deliver on SessionStart cannot be
  delivered at all;
- a Stop that *allows* has no output channel either, so green, unknown,
  ceiling, frozen-spec-changed and not-progressing would all end a Kimi turn
  in silence.

UserPromptSubmit is the documented alternative for both: its returned text is
appended to the context, and it fires for every user prompt - which is also
what makes it the observable fact a new host turn began (Kimi resets its own
one-block Stop guard exactly then). So this hook does two jobs, each one
observation, neither one inference:

1. it records a `prompt_submitted` event, which is where the Stop gate scopes
   the continuation budget to the host turn (see `goal_stop._block_streak`);
2. it prints the artifact pointer plus, when the event log holds one, the
   gate's last decision - the verdict a silent Kimi turn ended on, delivered
   on the next prompt because that is the only channel left.

The pointer and the verdict are one fixed-size pair of lines whatever the
artifact holds - a hook inlines only what it alone possesses, and those are
the two facts this hook alone possesses: that a goal is active, and what the
gate last measured. It prints plain text rather than JSON, because that is
what Kimi documents for this event, and it never blocks: a prompt is the
owner's, not the gate's.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from goal_hooks import ActiveGoal, append_event, read_events, run_hook  # noqa: E402


LINE = (
    "An active goal is running: `{slug}`. Read `## Carry-over` in "
    "`.goals/{slug}.goal.md` before acting and rewrite it before finishing. "
    "You are the run, not its designer."
)

# How each recorded decision reads as one line. Bounded by construction: the
# only variable-width facts are the check number and the exit code.
_ENDINGS = {
    "continuation_budget_spent": (
        "still red and this host's continuation budget was spent - the run "
        "parked; continue from `## Carry-over`"
    ),
    "ceiling_reached": "the ceiling was reached - the run is over",
    "frozen_spec_changed": (
        "the frozen spec changed - the run stopped and needs the owner"
    ),
    "anchor_unavailable": (
        "no runnable anchor - the gate cannot enforce this run"
    ),
}


def _last_decision(goal: ActiveGoal) -> str | None:
    """The verdict the previous turn ended on, read from the event log.

    The prompt marker this hook just wrote is skipped by construction: the
    walk looks for decisions, and `prompt_submitted` is not one.
    """
    for entry in reversed(read_events(goal)):
        kind = entry.get("event")
        if kind == "anchor_checked":
            if entry.get("blocked"):
                state = "refused to let the turn end"
            elif entry.get("outcome") == "red":
                state = "released the turn as not progressing"
            elif entry.get("outcome") == "green":
                state = "anchor green, turn ended"
            else:
                state = "anchor unknown, turn ended"
            return (
                f"Last gate decision: turn {entry.get('turn')}, "
                f"anchor {entry.get('outcome')} "
                f"(exit {entry.get('exit_code')}), {state}."
            )
        ending = _ENDINGS.get(str(kind))
        if ending is not None:
            return f"Last gate decision: turn {entry.get('turn')}, {ending}."
    return None


def handle(
    event: dict[str, Any], goal: ActiveGoal, host: str | None
) -> dict[str, Any] | None:
    append_event(
        goal,
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "prompt_submitted",
        },
    )
    try:
        sys.stdout.write(LINE.format(slug=goal.slug))
        decision = _last_decision(goal)
        if decision is not None:
            sys.stdout.write("\n" + decision)
    except (OSError, ValueError):
        pass
    return None


if __name__ == "__main__":
    raise SystemExit(run_hook("UserPromptSubmit", handle))
