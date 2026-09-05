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
from pathlib import Path
import re
import shlex
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from goal_hooks import (  # noqa: E402
    ActiveGoal,
    append_event,
    run_hook,
)


def delegation_target(event: dict[str, Any]) -> str | None:
    """Identify a direct delegation, never a mention in search text or output.

    Opaque scripts, compound shell commands and unknown tools are deliberately
    unobserved. The model must inspect those results; guessing would let a
    successful grep clear a failed worker.
    """
    tool = event.get("tool_name")
    data = event.get("tool_input")
    if not isinstance(data, dict):
        return None
    target = None
    if tool == "agent-delegate":
        target = data.get("to") or data.get("target")
    if target is None:
        if tool not in {"agent-delegate", "Bash", "bash", "Shell", "shell",
                        "exec_command", "run_shell_command", "execute_command"}:
            return None
        command = data.get("command") or data.get("cmd")
        if not isinstance(command, str) or "\n" in command or "\r" in command:
            return None
        try:
            lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>()")
            lexer.whitespace_split = True
            tokens = list(lexer)
        except ValueError:
            return None
        if len(tokens) < 4 or Path(tokens[0]).name != "agent-delegate" or tokens[1] != "run":
            return None
        if any(token and all(c in ";&|<>()" for c in token) for token in tokens):
            return None
        for index, token in enumerate(tokens[2:], 2):
            if token == "--to" and index + 1 < len(tokens):
                target = tokens[index + 1]
                break
            if token.startswith("--to="):
                target = token[5:]
                break
    if isinstance(target, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", target):
        return target.lower()
    return None


def handle(
    event: dict[str, Any], goal: ActiveGoal, host: str | None
) -> dict[str, Any] | None:
    role = delegation_target(event)
    if role is None:
        return None

    append_event(
        goal,
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "role_unavailable",
            "role": role,
            "tool": str(event.get("tool_name") or "unknown"),
            "detail": str(event.get("tool_response") or "")[:200],
        },
    )
    return {
        "systemMessage": (
            f"[ultra-goal] {goal.slug}: a call naming "
            f"{role} failed, and it is recorded. "
            "Fall back as `## Roles` declares, and say in your report that the round ran "
            "degraded - a review that could not happen is a missing review, not a pass."
        )
    }


if __name__ == "__main__":
    raise SystemExit(run_hook("PostToolUseFailure", handle))
