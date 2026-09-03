#!/usr/bin/env python3
"""Shared activation and fail-open plumbing for the goal hooks.

Every hook's first act is to decide whether a goal is active in this project.
Where none is, that decision is the entire run: nothing is read beyond one
marker file, nothing is written, no command is executed, and the exit code is 0.

That early exit is the only thing standing between an installed hook and a
project that never asked for one, so it is deliberately dumb: one file, one
line, no parsing that can fail in an interesting way. Every failure path in
this module ends in "not active" rather than in an exception.

The same applies to the handlers this module runs. A hook that raises must not
be able to stop the host from working - the historical failure here is a Stop
hook that blocked forever because its own check was broken.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable


GOALS_DIR = ".goals"
ACTIVE_MARKER = "active"
DISABLE_ENV = "GOAL_ENGINEERING_HOOKS_DISABLED"
# A slug names one artifact in `.goals/`. It is never a path.
SLUG_MAX = 100


@dataclass(frozen=True)
class ActiveGoal:
    """The goal this project is currently running."""

    slug: str
    goals_dir: Path
    goal_path: Path
    events_path: Path
    decisions_path: Path


def _valid_slug(raw: str) -> str | None:
    slug = raw.strip()
    if not slug or len(slug) > SLUG_MAX:
        return None
    # The marker holds a slug, not a path. Traversal is not a goal.
    if slug != Path(slug).name or slug in {".", ".."}:
        return None
    if any(ch in slug for ch in ("/", "\\", "\0")):
        return None
    return slug


def active_goal(cwd: Any) -> ActiveGoal | None:
    """Return the active goal for `cwd`, or None. Never raises."""
    try:
        if not isinstance(cwd, (str, Path)) or not str(cwd):
            return None
        goals = Path(cwd) / GOALS_DIR
        marker = goals / ACTIVE_MARKER
        if not marker.is_file():
            return None
        slug = _valid_slug(marker.read_text(encoding="utf-8"))
        if slug is None:
            return None
        goal = goals / f"{slug}.goal.md"
        if not goal.is_file():
            return None
        return ActiveGoal(
            slug=slug,
            goals_dir=goals,
            goal_path=goal,
            events_path=goals / f"{slug}.events.jsonl",
            decisions_path=goals / f"{slug}.decisions.md",
        )
    except (OSError, UnicodeError, ValueError):
        return None


def emit(payload: dict[str, Any]) -> None:
    """Write one JSON object to stdout. Silent on failure."""
    try:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    except (TypeError, ValueError, OSError):
        pass


def run_hook(
    event_name: str,
    handler: Callable[[dict[str, Any], ActiveGoal], dict[str, Any] | None],
    stdin_text: str | None = None,
    env: dict[str, str] | None = None,
) -> int:
    """Run `handler` only when this really is `event_name` on an active goal.

    Returns an exit code. It is always 0: a hook that cannot decide must let the
    host continue. Blocking, where a hook is entitled to it, travels through the
    emitted JSON rather than through the exit code, so a crash can never be
    mistaken for a deliberate block.
    """
    try:
        environ = os.environ if env is None else env
        if environ.get(DISABLE_ENV) == "1":
            return 0

        raw = sys.stdin.read() if stdin_text is None else stdin_text
        try:
            event = json.loads(raw)
        except (json.JSONDecodeError, UnicodeError, TypeError):
            return 0
        if not isinstance(event, dict):
            return 0
        if event.get("hook_event_name") != event_name:
            return 0

        # Re-entry guard. Without it, a denied stop can be denied forever.
        if event.get("stop_hook_active"):
            return 0

        goal = active_goal(event.get("cwd"))
        if goal is None:
            return 0

        payload = handler(event, goal)
        if payload:
            emit(payload)
        return 0
    except BaseException:  # noqa: BLE001 - a hook must never take the host down
        return 0


def append_event(goal: ActiveGoal, entry: dict[str, Any]) -> None:
    """Append one line to the goal's event log. Silent on failure."""
    try:
        goal.goals_dir.mkdir(parents=True, exist_ok=True)
        with goal.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    except (OSError, UnicodeError, TypeError, ValueError):
        pass


def read_events(goal: ActiveGoal) -> list[dict[str, Any]]:
    """Read the goal's event log. A malformed line is skipped, not fatal."""
    events: list[dict[str, Any]] = []
    try:
        if not goal.events_path.is_file():
            return events
        for line in goal.events_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, UnicodeError):
                continue
            if isinstance(entry, dict):
                events.append(entry)
    except (OSError, UnicodeError):
        return events
    return events
