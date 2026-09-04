#!/usr/bin/env python3
"""UserPromptSubmit hook: Kimi's recovery channel.

Kimi's SessionStart output is fire-and-forget - its reference says only
PreToolUse, Stop and UserPromptSubmit have return values that affect the main
flow - so the frozen-spec injection this plugin delivers on SessionStart
everywhere else is not delivered there. The host's documented alternative is
UserPromptSubmit, whose returned text is appended to the context, and this
hook is that alternative, registered only in Kimi's manifest.

The degradation is real and is not hidden: Kimi gets a one-line pointer per
prompt, not the injected spec the other hosts get on a session boundary. A
pointer and not a body is deliberate - a hook inlines only what it alone
possesses, and this hook possesses nothing but the fact that a goal is
active. Everything else is on disk, and the goal text already tells the run
to read it.

It prints plain text rather than JSON, because that is what Kimi documents
for this event, and it never blocks: a prompt is the owner's, not the gate's.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from goal_hooks import ActiveGoal, run_hook  # noqa: E402


LINE = (
    "An active goal is running: `{slug}`. Read `## Carry-over` in "
    "`.goals/{slug}.goal.md` before acting and rewrite it before finishing. "
    "You are the run, not its designer."
)


def handle(
    event: dict[str, Any], goal: ActiveGoal, host: str | None
) -> dict[str, Any] | None:
    try:
        sys.stdout.write(LINE.format(slug=goal.slug))
    except (OSError, ValueError):
        pass
    return None


if __name__ == "__main__":
    raise SystemExit(run_hook("UserPromptSubmit", handle))
