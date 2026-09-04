#!/usr/bin/env python3
"""TurnStarted hook: the host's own turn boundary, with its identity.

Kimi's reference separates two things round 2 conflated: `UserPromptSubmit`
means a user sent a message, while `TurnStarted` fires when a new turn
begins, whatever began it - the reference names `user`, `task` and
`system_trigger` origins, and its payload carries `turn_id` and
`origin_kind`. The 0.40.1 binary dispatches it from `startTurn` for every
new turn, and the Stop-hook continuation is not one: a block appends its
reason inside the running `runStepLoop` call (whose local
`stopHookContinuationUsed` guard is exactly the one-block-per-turn budget),
so no continuation of a blocked turn fires this event.

That is the distinction Codex round-2 F2 turned on: a prompt is one origin
of a turn, not the turn boundary, so a `prompt_submitted` row could never
scope the budget for a task- or system-triggered turn - it arrived
inheriting the log's tail with its budget already spent. This hook records
what the host itself observes: one `turn_started` event per host turn,
carrying the host's `turn_id` and `origin_kind`. The Stop gate scopes the
continuation budget through it (see `goal_stop._block_streak`), and the
`turn_id` it records lets `--audit` tell two checks inside one host turn
from one check in each of two.

TurnStarted is observation-only on Kimi - it cannot affect the flow - and
this hook returns nothing and never blocks. A field the payload did not
carry is recorded as absent rather than guessed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from goal_hooks import ActiveGoal, append_event, run_hook  # noqa: E402


def handle(
    event: dict[str, Any], goal: ActiveGoal, host: str | None
) -> dict[str, Any] | None:
    entry: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": "turn_started",
    }
    # Recorded as the host reported them; an absent field stays absent.
    for field in ("turn_id", "origin_kind"):
        if field in event:
            entry[field] = event[field]
    append_event(goal, entry)
    return None


if __name__ == "__main__":
    raise SystemExit(run_hook("TurnStarted", handle))
