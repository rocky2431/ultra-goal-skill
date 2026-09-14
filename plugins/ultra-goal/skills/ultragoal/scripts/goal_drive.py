#!/usr/bin/env python3
"""Continue an explicitly selected goal and deliver one awaited command result.

No model calls, polling scheduler, or native Goal service. The host still owns
model execution, permissions, interrupts and resource limits. Wait commands are
started by ordinary authorized tool calls, never by a hook.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import uuid

from goal_hooks import active_goal, append_event, frozen_digest, owns_goal, read_events, read_spec_baseline


def stamp():
    return datetime.now(timezone.utc).isoformat()


def state_path(goal):
    return goal.goals_dir / f"{goal.slug}.driver.json"


def interruption_path(goal):
    return goal.goals_dir / f"{goal.slug}.driver.interrupt"


def apply_interruption(goal, state):
    path = interruption_path(goal)
    if state and state["phase"] not in {"completed", "canceled"} and path.exists():
        if path.read_text().strip() == state["run_id"]:
            state.update(phase="paused", reason="Host interrupted this run; explicit resume required")
    return state


def read(goal):
    path = state_path(goal)
    return apply_interruption(goal, json.loads(path.read_text())) if path.exists() else None


def save(goal, state):
    apply_interruption(goal, state)
    state["updated_at"] = stamp()
    path = state_path(goal)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n")
    temporary.replace(path)


@contextmanager
def lock(path, *, shared=False, blocking=True):
    if os.name != "posix":
        raise ValueError("Autonomous execution currently requires a POSIX host; gate-only use is unchanged.")
    import fcntl
    with path.open("a+b") as handle:
        mode = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
        fcntl.flock(handle, mode | (0 if blocking else fcntl.LOCK_NB))
        yield


def driver_lock(goal, *, blocking=True):
    return lock(goal.goals_dir / f"{goal.slug}.driver.lock", blocking=blocking)


def bound(root, slug, session):
    goal = active_goal(root)
    if goal is None or goal.slug != slug or not session or goal.owner_session != session:
        raise ValueError("Driver control requires this goal's bound native session.")
    if read_spec_baseline(goal) != frozen_digest(goal.goal_path.read_text()):
        raise ValueError("Frozen goal terms changed; the driver cannot continue.")
    return goal


def selected(goal, state):
    current = active_goal(goal.goals_dir.parent)
    return bool(state and current and current.slug == goal.slug
                and current.owner_session == state["session_id"]
                and state["spec_digest"] == read_spec_baseline(current)
                == frozen_digest(current.goal_path.read_text()))


def start(goal, host):
    if host not in {"codex", "claude"}:
        raise ValueError("Autonomous execution is supported only for codex and claude.")
    with driver_lock(goal):
        state = read(goal)
        if state and state["phase"] in {"completed", "canceled"}:
            return state
        if state and state["session_id"] == goal.owner_session:
            if state["host"] != host:
                raise ValueError("The armed driver belongs to another host.")
            return state  # Re-arming never resumes a canceled/paused run.
        state = dict(run_id=uuid.uuid4().hex, host=host, session_id=goal.owner_session,
                     spec_digest=read_spec_baseline(goal), phase="running", continuations=0,
                     wait=None, reason="Explicit autonomous start")
        save(goal, state)
        append_event(goal, {"event": "driver_started", **state})
        return state


def halt(goal, phase, reason, *, blocking=True):
    if goal is None or not state_path(goal).exists():
        return None
    with driver_lock(goal, blocking=blocking):
        state = read(goal)
        if state["phase"] in {"completed", "canceled"}:
            return state
        pending = state.get("wait")
        state.update(phase=phase, reason=reason)
        if pending and pending.get("status") in {"starting", "waiting"}:
            pending["status"] = "canceled"
        save(goal, state)  # Invalidate delivery before terminating the waiter.
        append_event(goal, {"event": "driver_" + phase, "run_id": state["run_id"], "reason": reason})
    if pending and pending.get("pid") and pending.get("status") == "canceled":
        try:
            with lock(Path(pending["directory"]) / "wait.lock", blocking=False):
                pass  # The recorded worker exited; its PID may have been reused.
        except BlockingIOError:
            try:
                os.killpg(pending["pid"], signal.SIGTERM)
            except ProcessLookupError:
                pass
    return state


def interrupt(goal):
    state = read(goal)
    if not state or state["phase"] in {"completed", "canceled"}:
        return
    # Native interrupt hooks have a short deadline. Record intent before trying
    # the lock: a queue call already in flight must not make cancellation disappear.
    interruption_path(goal).write_text(state["run_id"] + "\n")
    try:
        halt(goal, "paused", "Host interrupted this run; explicit resume required", blocking=False)
    except BlockingIOError:
        pass  # The in-flight writer reads this run's interruption before saving.


def resume(goal):
    with driver_lock(goal):
        state = read(goal)
        if not selected(goal, state):
            raise ValueError("No matching autonomous run to resume.")
        if state["phase"] in {"completed", "canceled"}:
            raise ValueError("A terminal run cannot be resumed; start a newly authorized goal.")
        if state["phase"] != "paused":
            raise ValueError("Resume requires a paused run; do not replace an active wait.")
        interruption_path(goal).unlink(missing_ok=True)
        state.update(phase="running", wait=None, reason="Explicit authorized resume")
        save(goal, state)
        return state


def after_gate(goal, event, host, command, payload, previous_count):
    """Keep acceptance decisions and driver decisions separate, in one Stop path."""
    state = read(goal)
    if not state or state["host"] != (host or "claude") and not command:
        return payload
    observations = read_events(goal)[previous_count:]
    if any(row.get("verification_passed") is True for row in observations):
        halt(goal, "completed", "The current verification contract passed")
        return payload
    if any(row.get("event") in {"frozen_spec_changed", "ceiling_reached", "continuation_budget_spent",
                                "verification_interrupted"} for row in observations):
        halt(goal, "paused", "Execution or verification reached a stop condition; inspect the event log")
        return payload
    if command or not any(row.get("event") == "stop_ordinary" for row in observations):
        return payload
    with driver_lock(goal):
        state = read(goal)
        if not selected(goal, state) or state["phase"] != "running":
            return payload
        state["continuations"] += 1
        save(goal, state)
        if state["phase"] != "running":
            return payload
        append_event(goal, {"event": "driver_continued", "run_id": state["run_id"],
                            "continuation": state["continuations"], "session_id": goal.owner_session})
    return {"decision": "block", "reason": (
        f"UltraGoal {goal.slug} remains active. Read {goal.goal_path} and its Carry-over, then do the next "
        "useful authorized action. Do not create a native Goal. If ready, run goal_run.py verify and read "
        "its result. For an external dependency use goal_drive.py wait; for required user input or a real "
        "blocker use goal_drive.py pause with the reason. Honor cancellation and host resource limits. "
        "Do not end an ordinary turn merely to wait for another user prompt.")}


def wait_command(goal, argv, timeout=None):
    if not argv or any(not isinstance(arg, str) or "\0" in arg for arg in argv):
        raise ValueError("Supply an executable argument list after --; no shell is implied.")
    if timeout is not None and timeout <= 0:
        raise ValueError("Wait timeout must be positive.")
    with driver_lock(goal):
        state = read(goal)
        if not selected(goal, state) or state["phase"] != "running":
            raise ValueError("Wait requires the matching running autonomous goal.")
        executable = None
        if state["host"] == "codex":
            executable = shutil.which("codex")
            if not executable:
                raise ValueError("Codex queue is unavailable; no wait command was launched.")
            check = subprocess.run([executable, "queue", "--help"], capture_output=True, timeout=10)
            if check.returncode:
                raise ValueError("Codex queue is unsupported; no wait command was launched.")
        wait_id = uuid.uuid4().hex
        directory = goal.goals_dir / ".work" / f"{goal.slug}-wait-{wait_id}"
        directory.mkdir(parents=True)
        state.update(phase="waiting", wait=dict(id=wait_id, status="starting", directory=str(directory),
                     argv=argv, timeout=timeout, codex=executable, run_id=state["run_id"]))
        save(goal, state)
        log = (directory / "observer.log").open("ab")
        try:
            worker = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "_worker", goal.slug,
                         "--root", str(goal.goals_dir.parent), "--session-id", goal.owner_session,
                         "--wait-id", wait_id], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=log, start_new_session=True)
            # The worker owns wait.lock before acknowledgment; a fast Stop cannot
            # mistake a not-yet-started worker for a finished one.
            import select
            ready, _, _ = select.select([worker.stdout], [], [], 10)
            if not ready or worker.stdout.readline() != b"READY\n":
                worker.terminate()
                state.update(phase="paused", reason="Waiter failed before starting the command")
                save(goal, state)
                raise ValueError(state["reason"])
            worker.stdout.close()
            threading.Thread(target=worker.wait, daemon=True).start()
            state["wait"].update(pid=worker.pid, status="waiting")
            save(goal, state)
            append_event(goal, {"event": "driver_waiting", "run_id": state["run_id"],
                                "wait_id": wait_id, "result": str(directory / "result.json")})
        finally:
            log.close()
    return state


def pending_matches(goal, state, wait_id):
    return bool(selected(goal, state) and state["phase"] in {"waiting", "running"}
                and state.get("wait") and state["wait"]["id"] == wait_id
                and state["wait"]["run_id"] == state["run_id"])


def delivery(goal, wait_id):
    """Claim once while serialized with cancellation; never retry unknown delivery."""
    with driver_lock(goal):
        state = read(goal)
        if not pending_matches(goal, state, wait_id) or state["wait"]["status"] != "ready":
            return None
        waiting = state["wait"]
        message = (f"UltraGoal event {wait_id}: awaited command finished. Read "
                   f"{waiting['directory']}/result.json and output.log. Run goal_drive.py status with this "
                   "goal and native session ID to recheck the current driver state "
                   "and goal before acting; a canceled, paused, completed or rebound goal must not restart. "
                   "Command completion is not goal acceptance. Continue and verify the actual result.")
        waiting["status"] = "sending"
        save(goal, state)
        if state["phase"] != "running":
            return None
        if state["host"] == "codex":
            try:
                result = subprocess.run([waiting["codex"], "queue", "--thread", state["session_id"],
                                         "--message", message], capture_output=True, text=True, timeout=30)
                waiting.update(status="queued" if result.returncode == 0 else "failed",
                               delivery_exit=result.returncode)
            except (OSError, subprocess.TimeoutExpired) as exc:
                waiting.update(status="unknown", delivery_error=str(exc))
            if waiting["status"] != "queued":
                state.update(phase="paused", reason="Wake delivery failed or is unknown; inspect before retrying")
        else:
            waiting["status"] = "delivered"
        save(goal, state)
        append_event(goal, {"event": "driver_delivery", "run_id": state["run_id"],
                            "wait_id": wait_id, "delivery_status": waiting["status"]})
        return message if state["host"] == "claude" and state["phase"] == "running" else None


def worker(goal, wait_id):
    initial = read(goal)
    if not initial or initial.get("wait", {}).get("id") != wait_id:
        return
    directory = Path(initial["wait"]["directory"])
    with lock(directory / "wait.lock"):
        print("READY", flush=True)
        with driver_lock(goal):
            state = read(goal)
            if not pending_matches(goal, state, wait_id):
                return
            waiting = state["wait"]
        outcome = dict(wait_id=wait_id, started_at=stamp(), argv=waiting["argv"])
        with (directory / "output.log").open("wb") as output:
            try:
                result = subprocess.run(waiting["argv"], cwd=goal.goals_dir.parent, stdin=subprocess.DEVNULL,
                                        stdout=output, stderr=subprocess.STDOUT, timeout=waiting["timeout"])
                outcome.update(status="finished", exit_code=result.returncode)
            except subprocess.TimeoutExpired:
                outcome.update(status="timeout", exit_code=None)
            except OSError as exc:
                outcome.update(status="launch_failed", exit_code=None, error=str(exc))
        outcome["finished_at"] = stamp()
        (directory / "result.json").write_text(json.dumps(outcome, indent=2) + "\n")
        with driver_lock(goal):
            state = read(goal)
            if not pending_matches(goal, state, wait_id):
                return
            state["wait"]["status"] = "ready"
            state["phase"] = "running"
            save(goal, state)
        if state["host"] == "codex":
            delivery(goal, wait_id)


def wake_hook(event):
    goal = active_goal(event.get("cwd"))
    if not goal or not owns_goal(goal, event) or os.environ.get("ULTRA_GOAL_HOOKS_DISABLED") == "1":
        return None
    state = read(goal)
    if not selected(goal, state) or state["host"] != "claude" or not state.get("wait"):
        return None
    waiting = state["wait"]
    if waiting["status"] not in {"waiting", "ready"} or state["phase"] not in {"waiting", "running"}:
        return None
    directory = Path(waiting["directory"])
    try:
        with lock(directory / "delivery.lock", blocking=False):
            with lock(directory / "wait.lock", shared=True):
                pass  # OS wait: no model calls or repeated status reads.
            current = read(goal)
            if pending_matches(goal, current, waiting["id"]) and current["wait"]["status"] == "waiting":
                halt(goal, "paused", "Waiter exited without a result; execution is unknown")
                return None
            return delivery(goal, waiting["id"])
    except BlockingIOError:
        return None  # Another hook already owns this event's delivery.


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("start", "pause", "resume", "status", "wait", "_worker", "wake-hook", "interrupt"))
    parser.add_argument("slug", nargs="?")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--session-id")
    parser.add_argument("--host", choices=("codex", "claude"))
    parser.add_argument("--reason")
    parser.add_argument("--wait-id")
    parser.add_argument("--timeout", type=float)
    # Keep command options separate from driver options.
    raw = sys.argv[1:]
    separator = raw.index("--") if "--" in raw else len(raw)
    args = parser.parse_args(raw[:separator])
    try:
        if args.action in {"wake-hook", "interrupt"}:
            if os.environ.get("ULTRA_GOAL_HOOKS_DISABLED") == "1":
                return 0
            event = json.load(sys.stdin)
            if args.action == "wake-hook":
                if event.get("hook_event_name") != "Stop":
                    return 0
                message = wake_hook(event)
                if message:
                    print(message, file=sys.stderr)
                    return 2
            else:
                if event.get("hook_event_name") not in {"Interrupt", "SessionEnd"}:
                    return 0
                goal = active_goal(event.get("cwd"))
                if goal and owns_goal(goal, event):
                    interrupt(goal)
            return 0
        goal = bound(args.root.resolve(), args.slug, args.session_id)
        if args.action == "_worker":
            worker(goal, args.wait_id)
            return 0
        if args.action == "start":
            result = start(goal, args.host)
        elif args.action == "pause":
            if not args.reason:
                raise ValueError("Pause requires a concrete --reason.")
            result = halt(goal, "paused", args.reason)
        elif args.action == "resume":
            result = resume(goal)
        elif args.action == "wait":
            result = wait_command(goal, raw[separator + 1:], args.timeout)
        else:
            result = read(goal)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(f"ultra-goal driver: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
