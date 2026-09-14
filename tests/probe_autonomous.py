#!/usr/bin/env python3
"""Opt-in real-host acceptance: one input, ordinary stops, idle wait and verify.

The fixture never starts native Goal mode or supplies a follow-up prompt. Keep
stdin open for Claude's stream session; one-shot -p teardown cannot prove wakeup.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from probe_host_lifecycle import Probe, WRAPPER
from probe_codex_appserver import Client


class AutonomousClient(Client):
    def __init__(self, probe, home, timeout):
        self.messages, self.observed, self.request_id = queue.Queue(), [], 0
        self.deadline = time.monotonic() + timeout
        self.trace = probe.root / "host-events.jsonl"
        self.proc = subprocess.Popen([shutil.which("codex"), "app-server", "--stdio", "--disable", "goals",
            "-c", "bypass_hook_trust=true"], cwd=probe.root,
            env={**probe.env, "CODEX_HOME": str(home), "UG_PROBE_LABEL": "A"},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=(probe.root / "host-stderr.log").open("w"), text=True, bufsize=1)
        threading.Thread(target=self.read, daemon=True).start()

    def receive(self):
        item = super().receive()
        with self.trace.open("a") as out:
            out.write(json.dumps(dict(observed_at=time.time(), item=item)) + "\n")
        return item


def fixture(host, stages=2):
    root = Path(tempfile.mkdtemp(prefix=f"ultragoal-autonomous-{host}-"))
    probe = Probe(host, root)
    probe.stages = stages
    wrapper = WRAPPER.replace("import json,subprocess,sys,os", "import json,subprocess,sys,os,time")
    wrapper = wrapper.replace("{'event':name", "{'observed_at':time.time(),'event':name")
    (root / "wrapper.py").write_text(wrapper)
    (root / "producer.py").write_text("import time\nfrom pathlib import Path\ntime.sleep(20)\nPath('worker-input').write_text('21\\n')\nprint('INPUT_READY')\n")
    (root / "anchor.py").write_text(f"from pathlib import Path\np=Path('.')\nassert (p/'worker-result').read_text() == '42\\n'\nassert int((p/'native-stop-count').read_text()) >= {stages + 1}\nprint('BUSINESS_ACCEPTED')\n")
    # The fixture's protected anchor is installed before the model arms it.
    return probe


def prompt(probe):
    runner = shlex.join([sys.executable, str(probe.scripts / "goal_run.py")])
    driver = shlex.join([sys.executable, str(probe.scripts / "goal_drive.py")])
    return f"""Authorized isolated UltraGoal autonomous acceptance in {probe.root}.
Only this temporary workspace may be changed. Do not create any native Goal, commit, install,
edit hooks/checkers, invoke hooks manually, or contact external services. The synthetic demo
contract is preconfirmed for this probe; its business check requires doubling the delayed input
into worker-result, yielding exactly 42 plus newline. No other work is required.

Each time you run, read native-stop-count once (absent means 0), and read session-A.json
for the actual session_id observed by the real SessionStart hook. Never change either file.
Follow exactly ONE of these stages per response, and finish that response as directed.
- Count 0: execute {runner} arm demo --session-id <actual-id> --driver {probe.host}.
  Then say STAGE_ONE_PENDING and finish. Do not wait or continue within that response.
- Count 1 through {probe.stages - 1}: write stage-<count>.txt containing the actual count. Then say STAGE_<count>_PENDING and finish.
- Count {probe.stages}: execute {driver} wait demo --session-id <actual-id> --timeout 90 -- {shlex.quote(sys.executable)} producer.py.
  Then say WAITING_FOR_EVENT and finish. Do not poll, sleep, manually wake, or enable native Goal.
- Count >={probe.stages + 1}: the awaited event should supply a result.json path. Read the current driver state,
  result.json, output.log and worker-input. Only after the input exists, double it and write
  worker-result as exactly 42 plus newline. Run {runner} verify demo --session-id <actual-id>
  --claim 'Delayed input was doubled and checked'. Read the actual result and report
  AUTONOMOUS_ACCEPTED only if verification_passed is true. Never resume a terminal driver.

The fixture controller will send no further input. Ordinary Stop continuation and event wakeup
must be supplied by UltraGoal itself. If the input is not yet ready, do not poll or invent it;
report the missing delivery and pause with a reason.
This disposable fixture explicitly accepts reduced Git audit coverage: add --allow-no-git
to the arm command. A failed arm is a failed stage; report it instead of claiming the stage ran.
"""


def cancel_wait(probe):
    state = json.loads((probe.root / ".goals/demo.driver.json").read_text())
    if state["phase"] != "waiting":
        raise RuntimeError("Cancellation probe did not reach an actual pending wait")
    subprocess.run([sys.executable, str(probe.scripts / "goal_run.py"), "disarm", "demo",
                    "--root", str(probe.root)], check=True, capture_output=True, text=True)
    return time.time()


def observe_codex_stopped(client, stopped_at):
    client.deadline = time.monotonic() + 25
    try:
        while True:
            item = client.receive()
            if item.get("method") == "turn/started":
                raise RuntimeError("A canceled or interrupted wait started another model turn")
    except TimeoutError:
        return {"canceled_at": stopped_at, "cancellation_observed_seconds": 25, "post_cancel_model_turns": 0}


def run_codex(probe, timeout, scenario):
    home = probe.root / "codex-home"
    home.mkdir(mode=0o700)
    shutil.copy2(Path.home() / ".codex/auth.json", home / "auth.json")
    (home / "auth.json").chmod(0o600)
    client = AutonomousClient(probe, home, timeout)
    try:
        client.request("initialize", {"clientInfo": {"name": "ultragoal-autonomous-probe", "version": "1"},
                                      "capabilities": {"experimentalApi": True}})
        client.send({"method": "initialized", "params": {}})
        hooks = {event: [{"hooks": [probe.hook(event)]}] for event in ("SessionStart", "Stop", "PreCompact")}
        hooks["Interrupt"] = [{"hooks": [{"type": "command", "command": shlex.join([
            sys.executable, str(probe.scripts / "goal_drive.py"), "interrupt"]), "timeout": 3}]}]
        thread = client.request("thread/start", {"cwd": str(probe.root), "approvalPolicy": "never",
            "sandbox": "danger-full-access", "config": {"hooks": hooks, "bypass_hook_trust": True},
            "developerInstructions": "Execute only the authorized temporary fixture. No native Goal service or additional user input is available."})
        turn = client.request("turn/start", {"threadId": thread["thread"]["id"], "input": [{"type": "text", "text": prompt(probe)}]})
        while True:
            message = client.receive()
            state = probe.root / ".goals/demo.driver.json"
            if scenario == "interrupt" and message.get("method") == "item/completed" and state.exists():
                if json.loads(state.read_text())["phase"] == "waiting":
                    client.request("turn/interrupt", {"threadId": thread["thread"]["id"], "turnId": turn["turn"]["id"]})
                    client.until(lambda rows: any(r.get("method") == "turn/completed" for r in rows))
                    if json.loads(state.read_text())["phase"] != "paused":
                        raise RuntimeError("The actual native Interrupt did not pause the driver")
                    return {"native_interrupt": True, **observe_codex_stopped(client, time.time())}
            if message.get("method") == "turn/completed":
                if not state.exists():
                    raise RuntimeError("The first native turn ended without arming the driver")
                if scenario == "cancel" and json.loads(state.read_text())["phase"] == "waiting":
                    canceled_at = cancel_wait(probe)
                    return {"model": thread.get("model"), **observe_codex_stopped(client, canceled_at)}
                if state.exists() and json.loads(state.read_text())["phase"] == "completed":
                    return {"model": thread.get("model"), "session_id": thread["thread"]["id"]}
    finally:
        client.close()
        (home / "auth.json").unlink(missing_ok=True)


def run_claude(probe, timeout, scenario):
    settings = json.loads((probe.root / "claude-settings.json").read_text())
    wake = shlex.join([sys.executable, str(probe.scripts / "goal_drive.py"), "wake-hook"])
    settings["hooks"]["Stop"].append({"hooks": [{"type": "command", "command": wake, "asyncRewake": True, "timeout": 120}]})
    settings["hooks"]["SessionEnd"] = [{"hooks": [{"type": "command", "command": shlex.join([
        sys.executable, str(probe.scripts / "goal_drive.py"), "interrupt"]), "timeout": 1}]}]
    (probe.root / "claude-settings.json").write_text(json.dumps(settings))
    args = probe.args[:-2] + ["--output-format", "stream-json", "--input-format", "stream-json",
                            "--verbose", "--include-partial-messages"]
    messages = queue.Queue()
    process = subprocess.Popen(args, cwd=probe.root, env=probe.env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=(probe.root / "host-stderr.log").open("w"),
                               text=True, bufsize=1)
    def consume():
        for line in process.stdout:
            with (probe.root / "host-events.jsonl").open("a") as out:
                out.write(json.dumps(dict(observed_at=time.time(), item=json.loads(line))) + "\n")
            messages.put(json.loads(line))
        messages.put({"closed": True})
    threading.Thread(target=consume, daemon=True).start()
    process.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": prompt(probe)}}) + "\n")
    process.stdin.flush()
    deadline = time.monotonic() + timeout
    try:
        while True:
            message = messages.get(timeout=max(.01, deadline - time.monotonic()))
            if message.get("closed"):
                raise RuntimeError("Claude closed before autonomous acceptance")
            if message.get("type") == "result":
                state = probe.root / ".goals/demo.driver.json"
                if not state.exists():
                    raise RuntimeError("The first native response ended without arming the driver")
                if scenario == "cancel" and json.loads(state.read_text())["phase"] == "waiting":
                    canceled_at = cancel_wait(probe)
                    cancel_deadline = time.monotonic() + 25
                    try:
                        while True:
                            item = messages.get(timeout=max(.01, cancel_deadline - time.monotonic()))
                            if item.get("type") == "assistant" or item.get("event", {}).get("type") == "message_start":
                                raise RuntimeError("A canceled wait started another model request")
                    except queue.Empty:
                        return {"canceled_at": canceled_at, "cancellation_observed_seconds": 25,
                                "post_cancel_model_turns": 0}
                if state.exists() and json.loads(state.read_text())["phase"] == "completed":
                    return {"session_id": message.get("session_id"), "usage": message.get("usage")}
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("codex", "claude"), required=True)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--scenario", choices=("complete", "cancel", "interrupt"), default="complete")
    parser.add_argument("--stages", type=int, default=2, help="Ordinary continuations before the event wait")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.scenario == "interrupt" and args.host != "codex":
        parser.error("The native turn/interrupt probe currently targets Codex")
    if args.stages < 2:
        parser.error("--stages must be at least 2")
    probe = fixture(args.host, args.stages)
    print(f"Probe workspace: {probe.root}", flush=True)
    result = dict(host=args.host, scenario=args.scenario, stages=args.stages, workspace=str(probe.root), native_goal_enabled=False,
                  initial_user_inputs=1, source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in probe.scripts.glob("*.py")})
    try:
        result.update((run_codex if args.host == "codex" else run_claude)(probe, args.timeout, args.scenario))
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    driver = probe.root / ".goals/demo.driver.json"
    result["driver"] = json.loads(driver.read_text()) if driver.exists() else None
    result["hook_events"] = probe.transport()
    result["pass"] = bool(not result.get("error") and result["driver"]
                          and result["driver"]["phase"] == {"complete": "completed", "cancel": "canceled", "interrupt": "paused"}[args.scenario])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in {"source_sha256", "driver", "hook_events"}}))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
