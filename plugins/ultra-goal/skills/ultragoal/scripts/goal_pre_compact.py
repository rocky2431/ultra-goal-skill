#!/usr/bin/env python3
"""PreCompact hook: record the carried state before the context is emptied.

Compaction empties the working context mid-run just as surely as a week between
runs does. The carry-over section is on disk and survives, but nothing records
*that* a compaction happened - which is the difference between "the run forgot"
and "the run was reset". One event line makes that visible afterwards.

It records; it never blocks a compaction.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from goal_hooks import ActiveGoal, append_event, run_hook  # noqa: E402


BULLET = re.compile(r"(?m)^\s*[-*]\s+\S")
SUBSECTION = re.compile(r"(?m)^###\s+(\w+)\s*$")


def _carry_over(spec: str) -> str:
    body: list[str] = []
    capturing = False
    for line in spec.splitlines():
        if line.startswith("## "):
            capturing = line[3:].strip().lower() == "carry-over"
            continue
        if capturing:
            body.append(line)
    return "\n".join(body)


def handle(
    event: dict[str, Any], goal: ActiveGoal, host: str | None
) -> dict[str, Any] | None:
    spec = goal.goal_path.read_text(encoding="utf-8")
    carry_over = _carry_over(spec)
    parts: dict[str, int] = {}
    current: str | None = None
    chunk: list[str] = []
    for line in carry_over.splitlines():
        match = SUBSECTION.match(line)
        if match is not None:
            if current is not None:
                parts[current] = len(BULLET.findall("\n".join(chunk)))
            current = match.group(1).lower()
            chunk = []
        elif current is not None:
            chunk.append(line)
    if current is not None:
        parts[current] = len(BULLET.findall("\n".join(chunk)))

    append_event(
        goal,
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "pre_compact",
            "trigger": event.get("trigger") or event.get("matcher") or "unknown",
            "carry_over_digest": hashlib.sha256(
                carry_over.encode("utf-8", "replace")
            ).hexdigest()[:12],
            "state_items": parts.get("state", 0),
            "lessons": parts.get("lessons", 0),
        },
    )
    return {
        "systemMessage": (
            f"[ultra-goal] {goal.slug}: carry-over recorded before compaction "
            f"({parts.get('state', 0)} state, {parts.get('lessons', 0)} lesson(s)). "
            f"Re-read `{goal.goal_path.name}` after compaction."
        )
    }


if __name__ == "__main__":
    raise SystemExit(run_hook("PreCompact", handle))
