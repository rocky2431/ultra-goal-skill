#!/usr/bin/env python3
"""UserPromptSubmit hook: Kimi's recovery channel, and a user-origin boundary.

Kimi's reference makes every event but PreToolUse, Stop and UserPromptSubmit
observation-only, so two things this plugin needs have no other path there:

- the frozen-spec injection other hosts deliver on SessionStart cannot be
  delivered at all;
- a Stop that *allows* has no output channel either, so green, unknown,
  ceiling, frozen-spec-changed and not-progressing would all end a Kimi turn
  in silence.

UserPromptSubmit is the documented alternative for both: its returned text is
appended to the context, and it fires for every user prompt. So this hook
does two jobs, each one an observation, neither one inference:

1. it records a `prompt_submitted` event. Round 2 called this the turn
   boundary; Codex round 2 corrected that: a user prompt is one ORIGIN of a
   host turn, not the boundary itself - task- and system-triggered turns
   submit no prompt, and they inherit the log's tail with their budget
   already spent. The turn boundary is now the host's own TurnStarted
   (`goal_turn_started.py`, registered on Kimi); this row remains a boundary
   for user-origin turns and a defense where no turn event exists, because
   the invocation itself is still an observed fact.
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
from goal_hooks import ActiveGoal, append_event, completion_attempts, read_events, run_hook  # noqa: E402


LINE = (
    "An active goal is running: `{slug}`. Read `## Carry-over` in "
    "`.goals/{slug}.goal.md` before acting and rewrite it before finishing. "
    "You are the run, not its designer."
)

# How each recorded decision reads as one line. Bounded by construction: the
# only variable-width facts are the check number and the exit code.
_ENDINGS = {
    "stop_ordinary": (
        "the turn ended with no completion claim - the goal is not yet "
        "claimed met"
    ),
    "candidate_refused": (
        "a completion claim was refused; read the latest refusal reason in the event log"
    ),
    "continuation_budget_spent": (
        "the gate's own bound of consecutive denied attempts was spent - the "
        "run parked; continue from `## Carry-over`"
    ),
    "ceiling_reached": (
        "the ceiling of completion attempts was reached - the run is over"
    ),
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
    events = read_events(goal)
    attempts = completion_attempts(events)
    unfinished = [e for e in attempts if e.get("event") == "verification_started"]
    latest = unfinished[-1] if unfinished else attempts[-1] if attempts else None
    if latest and latest.get("event") in {"verification_started", "verification_interrupted"}:
        return (f"Last verification: attempt {latest.get('turn')} has no recorded outcome "
                "or was interrupted; the goal is unverified. Reconcile actual state before "
                "a new attempt. Earlier green is historical, not this attempt's result.")
    for entry in reversed(events):
        kind = entry.get("event")
        if kind == "anchor_checked":
            if entry.get("blocked"):
                state = "refused to let the turn end"
            elif entry.get("outcome") == "green":
                state = ("accepted verification contract passed, turn ended"
                         if entry.get("verification_passed") else
                         "anchor green; full verification not established, turn ended")
            else:
                state = "anchor unknown, turn ended"
            return (
                f"Last gate decision: attempt {entry.get('turn')}, "
                f"anchor {entry.get('outcome')} "
                f"(exit {entry.get('exit_code')}), {state}."
            )
        ending = _ENDINGS.get(str(kind))
        if ending is not None:
            if kind == "candidate_refused":
                ending += ": " + str(entry.get("reason") or "reason not recorded")[:200]
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
