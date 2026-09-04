#!/usr/bin/env python3
"""PostToolUse hook: record that a delegation target answered this time.

The failure twin (`goal_tool_failure.py`) writes `role_unavailable` when a
call naming a delegation target fails. Until this hook existed, nothing
recorded the opposite fact, so the Stop gate had to *infer* recovery - and
the only inference available was "a turn boundary passed", which proves a
turn ended and nothing about a worker. Round 4's probe recorded a role
failure, ended an ordinary turn with nothing recovered, claimed again, and
the anchor ran. Recovery is a positive observation now: this hook fires on
the success side, uses the *same* detection as the failure hook (a call
whose text names `agent-delegate` or a target the artifact declares), and
writes `role_recovered` only when an unrecovered failure for that same
role and tool exists. The Stop gate matches the pair.

The cost story is why this was once "deliberately not registered": success
events fire once per tool call. The detection runs on the invocation text
before anything else, so an ordinary Edit or Bash call stops here - no
event log is read, nothing is written. Only a call that itself names a
delegation target pays for the log read, and it pays once.

It cannot block and would not want to: a recovered worker is a fact, not a
verdict. Whether the recovery was adequate is `## Roles`'s fallback rules
and the run's report.
"""

from __future__ import annotations

from datetime import datetime, timezone
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from goal_hooks import (  # noqa: E402
    ActiveGoal,
    append_event,
    read_events,
    run_hook,
)
from goal_tool_failure import (  # noqa: E402
    DELEGATION_TOOL,
    _declared_targets,
    _invocation,
)


def handle(
    event: dict[str, Any], goal: ActiveGoal, host: str | None
) -> dict[str, Any] | None:
    invocation = _invocation(event)
    if not invocation:
        return None
    lowered = invocation.lower()
    named = [t for t in _declared_targets(goal) if t and t in lowered]
    if DELEGATION_TOOL not in lowered and not named:
        # An ordinary successful call: not a delegation, so not this
        # hook's fact to record. This early return is the whole cost
        # story - it is where almost every tool call stops.
        return None
    role = named[0] if named else "unnamed"
    tool = str(event.get("tool_name") or "unknown")

    # The pair (role, tool) is what the Stop gate matches a failure against,
    # so it is what cancels one here: one observed success for the pair
    # recovers every failure of that pair.
    events = read_events(goal)
    failed = any(
        e.get("event") == "role_unavailable"
        and e.get("role") == role
        and e.get("tool") == tool
        for e in events
    )
    already = any(
        e.get("event") == "role_recovered"
        and e.get("role") == role
        and e.get("tool") == tool
        for e in events
    )
    if not failed or already:
        return None

    append_event(
        goal,
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "role_recovered",
            "role": role,
            "tool": tool,
        },
    )
    return {
        "systemMessage": (
            f"[ultra-goal] {goal.slug}: a call naming {role} succeeded, so its "
            "earlier failure is no longer grounds to refuse a completion claim."
        )
    }


if __name__ == "__main__":
    raise SystemExit(run_hook("PostToolUse", handle))
