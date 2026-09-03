#!/usr/bin/env python3
"""SessionStart hook: put the active loop back in front of the model.

A new or resumed session has no idea a loop is running. This injects the frozen
spec and the carried state, which is exactly the pair SKILL.state keeps: the
immutable procedural specification plus the current execution state.

It only ever adds context. It cannot block a session from starting.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loop_hooks import ActiveLoop, read_events, run_hook  # noqa: E402


SOURCES = {"startup", "resume", "clear", "compact"}
CONTEXT_LIMIT = 6000


def handle(event: dict[str, Any], loop: ActiveLoop) -> dict[str, Any] | None:
    if event.get("source") not in SOURCES:
        return None

    goal = loop.goal_path.read_text(encoding="utf-8")
    checks = [e for e in read_events(loop) if e.get("event") == "anchor_checked"]
    last = checks[-1] if checks else None

    lines = [
        f"An active loop is running in this project: `{loop.slug}`.",
        "",
        f"Its artifact is `{loop.goal_path.name}` and it is the authority on what to do.",
        "The spec sections are frozen for the duration of the run: if the intent, the",
        "anchor, or the boundary turns out to be wrong, stop and report it rather than",
        "editing them yourself.",
        "",
    ]
    if last is not None:
        lines += [
            f"Last anchor check: turn {last.get('turn')}, outcome "
            f"{last.get('outcome')}, exit {last.get('exit_code')}.",
            "",
        ]
    lines += ["Read `## Carry-over` before acting and rewrite it before finishing.", "", "---", "", goal]

    context = "\n".join(lines)
    if len(context) > CONTEXT_LIMIT:
        context = context[:CONTEXT_LIMIT] + "\n\n[truncated - read the artifact directly]"

    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }


if __name__ == "__main__":
    raise SystemExit(run_hook("SessionStart", handle))
