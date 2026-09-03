#!/usr/bin/env python3
"""Shared activation and fail-open plumbing for the loop hooks.

Every hook's first act is to decide whether a loop is active in this project.
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


LOOPS_DIR = ".loops"
ACTIVE_MARKER = "active"
DISABLE_ENV = "LOOP_GRAPH_HOOKS_DISABLED"
# A slug names one artifact in `.loops/`. It is never a path.
SLUG_MAX = 100


@dataclass(frozen=True)
class ActiveLoop:
    """The loop this project is currently running."""

    slug: str
    loops_dir: Path
    goal_path: Path
    events_path: Path
    decisions_path: Path


def _valid_slug(raw: str) -> str | None:
    slug = raw.strip()
    if not slug or len(slug) > SLUG_MAX:
        return None
    # The marker holds a slug, not a path. Traversal is not a loop.
    if slug != Path(slug).name or slug in {".", ".."}:
        return None
    if any(ch in slug for ch in ("/", "\\", "\0")):
        return None
    return slug


def active_loop(cwd: Any) -> ActiveLoop | None:
    """Return the active loop for `cwd`, or None. Never raises."""
    try:
        if not isinstance(cwd, (str, Path)) or not str(cwd):
            return None
        loops = Path(cwd) / LOOPS_DIR
        marker = loops / ACTIVE_MARKER
        if not marker.is_file():
            return None
        slug = _valid_slug(marker.read_text(encoding="utf-8"))
        if slug is None:
            return None
        goal = loops / f"{slug}.goal.md"
        if not goal.is_file():
            return None
        return ActiveLoop(
            slug=slug,
            loops_dir=loops,
            goal_path=goal,
            events_path=loops / f"{slug}.events.jsonl",
            decisions_path=loops / f"{slug}.decisions.md",
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
    handler: Callable[[dict[str, Any], ActiveLoop], dict[str, Any] | None],
    stdin_text: str | None = None,
    env: dict[str, str] | None = None,
) -> int:
    """Run `handler` only when this really is `event_name` on an active loop.

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

        loop = active_loop(event.get("cwd"))
        if loop is None:
            return 0

        payload = handler(event, loop)
        if payload:
            emit(payload)
        return 0
    except BaseException:  # noqa: BLE001 - a hook must never take the host down
        return 0


def append_event(loop: ActiveLoop, entry: dict[str, Any]) -> None:
    """Append one line to the loop's event log. Silent on failure."""
    try:
        loop.loops_dir.mkdir(parents=True, exist_ok=True)
        with loop.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    except (OSError, UnicodeError, TypeError, ValueError):
        pass


def read_events(loop: ActiveLoop) -> list[dict[str, Any]]:
    """Read the loop's event log. A malformed line is skipped, not fatal."""
    events: list[dict[str, Any]] = []
    try:
        if not loop.events_path.is_file():
            return events
        for line in loop.events_path.read_text(encoding="utf-8").splitlines():
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
