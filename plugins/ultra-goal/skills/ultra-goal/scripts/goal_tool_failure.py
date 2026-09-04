#!/usr/bin/env python3
"""PostToolUseFailure hook: record that a delegated role could not be reached.

This exists because deleting it was right for the wrong reason. An earlier
version had the run write `role_unavailable` into the event log, which put a
claim inside the evidence file - so it was removed, on the reasoning that only
the run can observe a failed delegation. The hooks reference says otherwise:
`PostToolUseFailure` fires after a tool call fails, which is a host-observed
fact about the invocation. So the fact is available to a hook after all, and
the honest version of declared degradation is back.

What it records is narrow on purpose: **that a call naming a delegation target
failed.** Not that the role was unavailable in some deeper sense, not that the
fallback was adequate - those are judgements, and this writes facts.

It cannot block, and would not want to: a failed delegation is the run's
problem to degrade around, not the gate's to refuse.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from goal_hooks import (  # noqa: E402
    ActiveGoal,
    append_event,
    run_hook,
    sections,
)


# The delegation command this Skill's own templates name, plus whatever targets
# the artifact declares. Matched against the failed invocation as a fact about
# what was called - not as a guess about what the failure meant.
DELEGATION_TOOL = "agent-delegate"
TARGET_FIELD = re.compile(r"(?mi)^\s*[-*]\s*target:\s*`?([\w-]+)`?")


def _invocation(event: dict[str, Any]) -> str:
    """Everything the host said about the call, flattened for one search.

    Deliberately not a guess at which field holds the command: the payload
    shape is the host's and has changed before, so this reads all of it rather
    than betting on `tool_input.command`.
    """
    for key in ("tool_input", "tool_response", "tool_name"):
        if key in event:
            break
    else:
        return ""
    try:
        return json.dumps(
            {k: v for k, v in event.items() if k.startswith("tool")},
            ensure_ascii=False,
        )
    except (TypeError, ValueError):
        return ""


def _declared_targets(goal: ActiveGoal) -> list[str]:
    try:
        spec = goal.goal_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return []
    found = sections(spec)
    body = "\n".join(
        found.get(name, "") for name in ("roles", "verification", "reviewer", "critic")
    )
    return [t.lower() for t in TARGET_FIELD.findall(body)]


def handle(
    event: dict[str, Any], goal: ActiveGoal, host: str | None
) -> dict[str, Any] | None:
    invocation = _invocation(event)
    if not invocation:
        return None
    lowered = invocation.lower()
    named = [t for t in _declared_targets(goal) if t and t in lowered]
    if DELEGATION_TOOL not in lowered and not named:
        return None

    append_event(
        goal,
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "role_unavailable",
            "role": named[0] if named else "unnamed",
            "tool": str(event.get("tool_name") or "unknown"),
            "detail": str(event.get("tool_response") or "")[:200],
        },
    )
    return {
        "systemMessage": (
            f"[ultra-goal] {goal.slug}: a call naming "
            f"{named[0] if named else 'a delegation target'} failed, and it is recorded. "
            "Fall back as `## Roles` declares, and say in your report that the round ran "
            "degraded - a review that could not happen is a missing review, not a pass."
        )
    }


if __name__ == "__main__":
    raise SystemExit(run_hook("PostToolUseFailure", handle))
