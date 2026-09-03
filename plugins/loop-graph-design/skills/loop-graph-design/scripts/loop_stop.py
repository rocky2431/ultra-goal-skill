#!/usr/bin/env python3
"""Stop hook: the anchor gate.

Seven steps, six of which let the turn end. A mechanical gate's default has to
be "allow" - it only refuses in the one case it is certain about.

It refuses exactly once: the anchor ran, and it was red. Everything else -
ceiling reached, loop not progressing, anchor unrunnable, anchor green - lets
the turn end and says why.

The third outcome is the one that is easy to leave out and expensive to get
wrong. An anchor that cannot run is not a failed anchor; it is an unknown, and
folding unknown into either verdict is how a mechanical gate starts lying. A
timeout is the same class of mistake: it measures elapsed time and reports it as
success or failure, two things it has no access to.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loop_hooks import (  # noqa: E402
    ActiveLoop,
    append_event,
    read_events,
    run_hook,
)


ANCHOR_TIMEOUT_SECONDS = 180
# Used only when the artifact's stop condition names no ceiling. Deliberately
# generous: guessing low is the failure mode that cuts off real work.
DEFAULT_CEILING = 12
FENCE = re.compile(r"```[a-z]*\n(.+?)\n```", re.S)
INLINE = re.compile(r"`([^`\n]+)`")
TURNS = re.compile(r"(\d+)\s+turns?\b", re.I)
# Exit codes for "command not found" are a per-shell detail: POSIX shells use
# 127 (and 126 for found-but-not-executable), cmd.exe uses 9009, and CI proved
# that guessing from the code alone leaves the third outcome missing on some
# platform. They are kept as a fallback, but the primary check happens before
# the command runs, where it can be answered by looking rather than inferring.
UNRUNNABLE_EXITS = {126, 127, 9009}


def _section(text: str, heading: str) -> str | None:
    found: dict[str, str] = {}
    current: str | None = None
    body: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                found[current] = "\n".join(body)
            current = line[3:].strip().lower()
            body = []
        elif current is not None:
            body.append(line)
    if current is not None:
        found[current] = "\n".join(body)
    return found.get(heading)


def _first_command(text: str) -> str | None:
    fence = FENCE.search(text)
    if fence is not None:
        body = fence.group(1).strip()
        if body:
            return body.splitlines()[0].strip()
    inline = INLINE.search(text)
    return inline.group(1).strip() if inline is not None else None


def _resolvable(command: str) -> bool:
    """Can this command's executable actually be found?

    Asked before running, because "command not found" is reported differently
    by every shell and inferring it from an exit code is how the unknown
    outcome went missing on Windows. Looking is cheaper and portable.

    A false negative here costs an unnecessary "unknown", which allows the turn
    to end and says the result is unverified. A false negative in the other
    direction - treating a broken anchor as a failing one - denies the stop on
    no evidence. Erring toward unknown is the safe direction.
    """
    try:
        parts = shlex.split(command, posix=(os.name != "nt"))
    except ValueError:
        return True  # unparseable quoting: let the shell have a go at it
    if not parts:
        return False
    head = parts[0].strip('"\'')
    if not head:
        return False
    try:
        if Path(head).exists():
            return True
    except OSError:
        pass
    return shutil.which(head) is not None


def _allow(reason: str) -> dict[str, Any]:
    return {"systemMessage": f"[loop-graph-design] {reason}"}


def _deny(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _signature(outcome: str, exit_code: int | None, digest: str) -> str:
    return f"{outcome}:{exit_code}:{digest}"


def handle(event: dict[str, Any], loop: ActiveLoop) -> dict[str, Any] | None:
    goal = loop.goal_path.read_text(encoding="utf-8")
    anchor_section = _section(goal, "anchor")
    anchor = _first_command(anchor_section or "")
    if not anchor:
        return _allow(
            f"{loop.slug}: no runnable anchor in `## Anchor`, so nothing can be "
            "gated. Fix the artifact or the gate is decorative."
        )

    events = read_events(loop)
    checks = [e for e in events if e.get("event") == "anchor_checked"]
    turn = len(checks) + 1

    stop_section = _section(goal, "stop condition") or ""
    ceiling_match = TURNS.search(stop_section)
    ceiling = int(ceiling_match.group(1)) if ceiling_match else DEFAULT_CEILING

    # Step 3: the ceiling is the owner's, and it wins even when the goal is unmet.
    if turn > ceiling:
        append_event(
            loop,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": "ceiling_reached",
                "turn": turn,
                "ceiling": ceiling,
            },
        )
        return _allow(
            f"{loop.slug}: ceiling of {ceiling} turns reached without meeting the "
            "goal. Stopping. Report what is left rather than claiming success."
        )

    # Step 5: is the anchor even runnable? Answered by looking, not by inference.
    if not _resolvable(anchor):
        append_event(
            loop,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": "anchor_checked",
                "turn": turn,
                "anchor": anchor,
                "outcome": "unknown",
                "exit_code": None,
                "output_digest": "",
                "signature": "unknown:unresolvable:",
                "tail": "executable not found",
            },
        )
        return _allow(
            f"{loop.slug}: the anchor's command was not found on PATH, so whether "
            "the work landed is unknown - not failed. Stopping. Fix the anchor or "
            "say the result is unverified; do not guess either way."
        )

    # Step 6+7: run it. Three outcomes, not two.
    try:
        completed = subprocess.run(
            anchor,
            shell=True,
            cwd=str(loop.loops_dir.parent),
            capture_output=True,
            text=True,
            timeout=ANCHOR_TIMEOUT_SECONDS,
        )
        exit_code: int | None = completed.returncode
        output = (completed.stdout + completed.stderr).strip()
        if exit_code == 0:
            outcome = "green"
        elif exit_code in UNRUNNABLE_EXITS:
            outcome = "unknown"
        else:
            outcome = "red"
    except subprocess.TimeoutExpired:
        exit_code, output, outcome = None, "", "unknown"
    except (OSError, ValueError) as exc:
        exit_code, output, outcome = None, str(exc), "unknown"

    digest = hashlib.sha256(output.encode("utf-8", "replace")).hexdigest()[:12]
    signature = _signature(outcome, exit_code, digest)
    append_event(
        loop,
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "anchor_checked",
            "turn": turn,
            "anchor": anchor,
            "outcome": outcome,
            "exit_code": exit_code,
            "output_digest": digest,
            "signature": signature,
            "tail": output.splitlines()[-1][:200] if output else "",
        },
    )

    if outcome == "unknown":
        detail = "timed out" if exit_code is None else f"exit {exit_code}"
        return _allow(
            f"{loop.slug}: the anchor could not run ({detail}), so whether the work "
            "landed is unknown - not failed. Stopping. Say it is unverified rather "
            "than guessing either way."
        )

    if outcome == "green":
        return _allow(
            f"{loop.slug}: anchor `{anchor}` passed on turn {turn}. Goal met."
        )

    # Step 4: red, but is anything changing? Two identical results in a row mean
    # the loop is spinning, and denying the stop again would only spin it more.
    previous = checks[-1].get("signature") if checks else None
    if previous == signature:
        return _allow(
            f"{loop.slug}: the anchor produced an identical result two turns in a "
            f"row (turn {turn}), so the loop is not progressing. Stopping. Report "
            "what is blocking it instead of retrying."
        )

    return _deny(
        f"{loop.slug}: anchor `{anchor}` is still failing (exit {exit_code}) on turn "
        f"{turn} of {ceiling}, so the goal is not met. Keep working. Before the next "
        "attempt, write one lesson into `### Lessons` naming the cause and the next "
        "action - and run the independent verification named in `## Verification`."
    )


if __name__ == "__main__":
    raise SystemExit(run_hook("Stop", handle))
