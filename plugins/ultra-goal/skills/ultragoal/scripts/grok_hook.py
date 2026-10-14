#!/usr/bin/env python3
"""Route native Grok hook events to the existing owned-goal handlers."""
import json
from pathlib import Path
import shlex
import sys

import goal_drive
import goal_pre_compact
import goal_stop
import goal_tool_failure
import goal_tool_success
import goal_turn_started
from goal_hooks import append_event, host_facts, read_events, run_hook
from goal_prompt_submit import _last_decision


def handle(event, goal, host):
    name = event["hook_event_name"]
    if name in {"StopCancelled", "StopFailure", "SessionEnd"}:
        goal_drive.interrupt(goal)
        return None
    if name == "UserPromptSubmit":
        return goal_turn_started.handle(event, goal, host)
    if name == "PreCompact":
        goal_pre_compact.handle(event, goal, host)
        return None
    if name in {"SessionStart", "PostCompact"}:
        append_event(goal, {"event": "grok_recovery_pending", "session_id": goal.owner_session})
        return None
    if name == "Stop":
        # Grok also emits an observe-only Stop during teardown; it is not a completion attempt.
        if event.get("reason") != "end_turn":
            return None
        payload = goal_stop.handle(event, goal, host)
        goal_drive.yield_at_stop(goal, event.get("turn_id"))
        if payload and payload.get("decision") == "block":
            blocks = sum(row.get("event") == "grok_stop_blocked"
                         and row.get("turn_id") == event.get("turn_id")
                         and row.get("session_id") == goal.owner_session for row in read_events(goal))
            if blocks >= host_facts("grok").continuation_budget:
                reason = "Grok's per-turn continuation budget is spent; inspect Carry-over and explicitly resume."
                goal_drive.halt(goal, "paused", reason)
                append_event(goal, {"event": "grok_continuation_budget_spent", "reason": reason})
                return {"continue": False, "stopReason": reason}
            append_event(goal, {"event": "grok_stop_blocked", "turn_id": event.get("turn_id"),
                                "session_id": goal.owner_session})
            if blocks >= host_facts("grok").continuation_budget - 2:
                command = shlex.join([sys.executable, str(Path(__file__).with_name("goal_drive.py")),
                    "yield", goal.slug, "--root", str(goal.goals_dir.parent),
                    "--session-id", goal.owner_session, "--turn-id", event.get("turn_id", "")])
                payload["reason"] += (
                    " Before Grok's native continuation ceiling, hand off to a fresh turn: run "
                    + command + " through run_terminal_command with block_until_ms=0, then finish this turn. "
                    "The Stop event releases that background command and its completion wakes this same goal. "
                    "Do not poll, add a timer, or create a second goal. Recheck the driver on wake."
                )
        return payload
    if name not in {"PostToolUse", "PostToolUseFailure"}:
        return None

    result = event.get("tool_response")
    failed = name == "PostToolUseFailure" or (
        isinstance(result, dict) and result.get("type") == "Bash"
        and (result.get("exit_code") not in {None, 0} or result.get("timed_out") is True)
    )
    handler = goal_tool_failure.handle if failed else goal_tool_success.handle
    payload = handler(event, goal, host)
    context = [payload["systemMessage"]] if payload and payload.get("systemMessage") else []
    last = next((row for row in reversed(read_events(goal))
                 if row.get("event") in {"grok_recovery_pending", "grok_recovery_delivered"}
                 and row.get("session_id") == goal.owner_session), None)
    if last is None or last["event"] == "grok_recovery_pending":
        context.append(
            f"UltraGoal {goal.slug} is bound to this session. Read the complete frozen contract at "
            f"{goal.goal_path} and its Carry-over before further work; do not redesign or re-arm it. "
            "A paused, canceled or completed driver must not restart automatically. "
            "On Grok, run goal_drive.py wait through the native background terminal and end the turn; "
            "the command's completion wakes this session. Do not poll."
        )
        decision = _last_decision(goal)
        if decision:
            context.append(decision)
        append_event(goal, {"event": "grok_recovery_delivered", "session_id": goal.owner_session})
    if context:
        return {"hookSpecificOutput": {"hookEventName": name, "additionalContext": "\n".join(context)}}
    return None


def main():
    try:
        event = json.load(sys.stdin)
    except (ValueError, UnicodeError):
        return 0
    if not isinstance(event, dict) or event.get("subagentType"):
        return 0
    # These are Grok's documented fields; a missing native identity never inherits a parent's.
    event.update(session_id=event.get("sessionId"), turn_id=event.get("promptId"),
                 tool_name=event.get("toolName"), tool_input=event.get("toolInput"),
                 tool_response=event.get("toolResult"), stop_hook_active=event.get("stopHookActive"))
    return run_hook(event.get("hook_event_name"), handle, stdin_text=json.dumps(event), host="grok")


if __name__ == "__main__":
    raise SystemExit(main())
