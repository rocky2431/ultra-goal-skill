#!/usr/bin/env python3
"""Round-5 adversarial probes: the ten round-4 findings, re-run against the fix.

Each control reproduces one finding's proving scenario with the smallest
honest fixture, then asserts the fixed behavior - not the absence of the old
string, but the presence of the property the finding said was missing.

Uses the real shipped scripts (copied, so paths carry no spaces) and the real
arming fence (`goal_run.py`), in isolated throwaway directories.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

# The worktree these ran in is gone; resolve the repository from this
# file so the drivers stay runnable where the record now lives.
REPO = Path(__file__).resolve().parents[5]
SCRIPTS = REPO / "plugins" / "ultra-goal" / "skills" / "ultra-goal" / "scripts"

results: list[dict] = []


def report(name: str, ok: bool, detail: dict) -> None:
    results.append({"probe": name, "ok": ok, **detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    for key, value in detail.items():
        print(f"    {key}: {value}")


GOAL = """# Goal: probe

## Intent

Probe the gate.

## Boundary

**Scope.** Only this directory.

**Confidence.** Never claim without the anchor.

**Inference.** Reproduce everything.

## Stop condition

__STOP__

## Anchor

```
__ANCHOR__
```

## Roles

- **lead**: this session with the owner. fallback: none.
- **carry out**: this session, code and tests together. fallback: none.
- **reviewer**: a subagent with a fresh context. fallback: none.
- **critic**: a second subagent. fallback: none.

## Means

- `[load-bearing]` one probe slice per finding

## Verification

A reviewer with a fresh context reviews the diff; a critic then audits that
review rather than the code. At most 5 inner rounds.

## Acceptance

- [x] probe line

## Cadence

Started by hand.

## Carry-over

Read this before acting; rewrite it before finishing.

### State

- nothing yet

### Lessons

- nothing yet

### Next

- finish the probe

## Handoff

```
/goal Probe the gate.
```
"""

DECISIONS = """# Decisions

| Decision | Rejected | Why | Who |
|---|---|---|---|
| probe | - | probe | owner |
"""


def fixture(name: str, anchor: str = "/usr/bin/false", stop: str = "Stop when the anchor is green, or after 4 turns."):
    root = Path(tempfile.mkdtemp(prefix=f"ultra-goal-r5-{name}-"))
    plugin = root / "pluginroot" / "skills" / "ultra-goal" / "scripts"
    plugin.mkdir(parents=True)
    for script in SCRIPTS.glob("*.py"):
        shutil.copy2(script, plugin / script.name)
    goals = root / ".goals"
    goals.mkdir()
    (goals / "probe.goal.md").write_text(
        GOAL.replace("__ANCHOR__", anchor).replace("__STOP__", stop),
        encoding="utf-8",
    )
    (goals / "probe.decisions.md").write_text(DECISIONS, encoding="utf-8")
    return root


def run(root: Path, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(root / "pluginroot" / "skills" / "ultra-goal" / "scripts" / args[0]), *args[1:]],
        input=stdin, capture_output=True, text=True, timeout=60, cwd=str(root),
    )


def arm(root: Path) -> subprocess.CompletedProcess:
    return run(root, "goal_run.py", "arm", "probe")


def stop(root: Path, host: str = "claude") -> tuple[dict, list[dict]]:
    result = run(
        root, "goal_stop.py", "--host", host,
        stdin=json.dumps({"hook_event_name": "Stop", "cwd": str(root)}),
    )
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return payload, events(root)


def events(root: Path) -> list[dict]:
    log = root / ".goals" / "probe.events.jsonl"
    if not log.is_file():
        return []
    return [json.loads(l) for l in log.read_text().splitlines() if l.strip()]


def claim(root: Path) -> None:
    (root / ".goals" / "probe.candidate").write_text("probe complete\n", "utf-8")


def edit_frozen(root: Path) -> None:
    path = root / ".goals" / "probe.goal.md"
    path.write_text(
        path.read_text(encoding="utf-8")
        .replace("## Intent\n\nProbe the gate.", "## Intent\n\nEDITED GOALPOST")
        .replace("/usr/bin/false", "/usr/bin/true"),
        encoding="utf-8",
    )


def tool_event(root: Path, name: str, response: str) -> dict:
    return json.loads(run(
        root, name,
        stdin=json.dumps({
            "hook_event_name": "PostToolUse" if "success" in name else "PostToolUseFailure",
            "cwd": str(root),
            "tool_name": "agent-delegate",
            "tool_input": {"command": "agent-delegate --target codex review"},
            "tool_response": response,
        }),
    ).stdout or "{}")


def readonly(path: Path) -> None:
    mode = stat.S_IMODE(path.lstat().st_mode)
    os.chmod(path, mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)


def writable(path: Path) -> None:
    os.chmod(path, 0o755)


# --- F3: an edited candidate can no longer author the baseline ---------------
def baseline_launder() -> None:
    root = fixture("launder")
    arm(root)
    edit_frozen(root)
    claim(root)
    payload, log = stop(root)
    kinds = [e.get("event") for e in log]
    report(
        "r5-baseline-launder-refused",
        payload.get("decision") is None
        and "frozen spec" not in json.dumps(payload)
        and "changed since the gate was armed" in payload.get("systemMessage", "")
        and "frozen_spec_changed" in kinds
        and "anchor_checked" not in kinds
        and not (root / ".goals" / "active").exists(),
        {
            "decision": payload.get("decision"),
            "events": kinds,
            "marker_after": (root / ".goals" / "active").exists(),
        },
    )


# --- F3 (trace half): a run-authored trace is not a re-baseline --------------
def trace_rebaseline_launder() -> None:
    root = fixture("trace")
    arm(root)
    # Replace the log with a run-authored trace that "authorizes" the edit.
    digest_now = "25cf46700e55"
    (root / ".goals" / "probe.events.jsonl").write_text(
        json.dumps({"event": "run_authored_trace", "spec_digest": digest_now}) + "\n",
        encoding="utf-8",
    )
    edit_frozen(root)
    claim(root)
    payload, log = stop(root)
    kinds = [e.get("event") for e in log]
    report(
        "r5-trace-rebaseline-refused",
        "changed since the gate was armed" in payload.get("systemMessage", "")
        and "anchor_checked" not in kinds
        and not (root / ".goals" / "active").exists(),
        {
            "events": kinds,
            "marker_after": (root / ".goals" / "active").exists(),
            "message_head": payload.get("systemMessage", "")[:80],
        },
    )


# --- F4: recovery is positive, a boundary is not proof ------------------------
def worker_join() -> None:
    root = fixture("workers", anchor="/usr/bin/false")
    arm(root)
    tool_event(root, "goal_tool_failure.py", "exit 1")
    claim(root)
    first, _ = stop(root)
    # End an ordinary turn with no recovery observation at all.
    stop(root)
    claim(root)
    second, _ = stop(root)
    # Now the positive observation: a successful call naming the same target.
    tool_event(root, "goal_tool_success.py", "ok")
    claim(root)
    third, log = stop(root)
    report(
        "r5-worker-recovery-positive",
        first.get("decision") == "block"
        and second.get("decision") == "block"
        and "recovered" in second.get("reason", "")
        and third.get("decision") == "block"
        and "still failing" in third.get("reason", "")
        and any(e.get("event") == "role_recovered" for e in log),
        {
            "first_decision": first.get("decision"),
            "after_boundary_only": second.get("decision"),
            "after_positive_recovery": third.get("decision"),
            "third_reason_head": third.get("reason", "")[:60],
            "role_recovered_recorded": any(
                e.get("event") == "role_recovered" for e in log
            ),
        },
    )


# --- F5: every candidate consumes the owner ceiling ---------------------------
def ceiling_bypass() -> None:
    root = fixture("ceiling", stop="Stop when the anchor is green.\n\nceiling: 1")
    arm(root)
    tool_event(root, "goal_tool_failure.py", "exit 1")
    turns = []
    decisions = []
    for _ in range(3):
        claim(root)
        payload, log = stop(root)
        spent = [
            e for e in log
            if e.get("event") in ("candidate_refused", "ceiling_reached")
        ]
        turns.append(spent[-1]["turn"] if spent else None)
        decisions.append("allow" if "systemMessage" in payload else "deny")
        stop(root)  # ordinary boundary so the denial streak resets
    kinds = [e.get("event") for e in log]
    report(
        "r5-every-candidate-counts",
        turns == [1, 2, 3]
        and decisions == ["deny", "allow", "allow"]
        and "ceiling_reached" in kinds,
        {
            "candidate_turns": turns,
            "decisions": decisions,
            "events": kinds,
        },
    )


# --- F6: arming a second slug refuses ----------------------------------------
def double_arm() -> None:
    root = fixture("doublearm")
    arm(root)
    for name in ("probe.goal.md", "probe.decisions.md"):
        shutil.copy2(root / ".goals" / name, root / ".goals" / name.replace("probe", "beta"))
    second = arm_beta = subprocess.run(
        [sys.executable, str(root / "pluginroot" / "skills" / "ultra-goal" / "scripts" / "goal_run.py"),
         "arm", "beta"],
        capture_output=True, text=True, timeout=60, cwd=str(root),
    )
    report(
        "r5-double-arm-refused",
        second.returncode == 1
        and (root / ".goals" / "active").read_text().strip() == "probe",
        {
            "second_exit": second.returncode,
            "stderr": second.stderr.strip()[:90],
            "active_after": (root / ".goals" / "active").read_text().strip(),
        },
    )


# --- F6 (session-line half): a claimed marker still disarms -------------------
def disarm_with_session() -> None:
    root = fixture("disarm")
    arm(root)
    (root / ".goals" / "active").write_text("probe\nsession owner-1\n", "utf-8")
    result = subprocess.run(
        [sys.executable, str(root / "pluginroot" / "skills" / "ultra-goal" / "scripts" / "goal_run.py"),
         "disarm", "probe"],
        capture_output=True, text=True, timeout=60, cwd=str(root),
    )
    report(
        "r5-disarm-matches-slug-line",
        result.returncode == 0 and not (root / ".goals" / "active").exists(),
        {"exit": result.returncode, "marker_after": (root / ".goals" / "active").exists()},
    )


# --- F8: the deny reaches every host's consumer -------------------------------
def deny_shapes() -> None:
    shapes = {}
    for host in ("claude", "codex", "zcode", "kimi"):
        root = fixture(f"shape-{host}", anchor="/usr/bin/false")
        arm(root)
        claim(root)
        payload, _ = stop(root, host=host)
        shapes[host] = payload
    ok = (
        all(
            set(shapes[h]) == {"decision", "reason"} and shapes[h]["decision"] == "block"
            for h in ("claude", "codex", "zcode")
        )
        and set(shapes["kimi"]) == {"hookSpecificOutput"}
        and shapes["kimi"]["hookSpecificOutput"]["permissionDecision"] == "deny"
        and "still failing" in shapes["kimi"]["hookSpecificOutput"]["permissionDecisionReason"]
    )
    report(
        "r5-deny-shape-per-host",
        ok,
        {h: sorted(p) for h, p in shapes.items()},
    )


# --- F9: no fourth mechanical outcome; the audit says what happened -----------
def axis_leak() -> None:
    root = fixture("axis")
    arm(root)
    tool_event(root, "goal_tool_failure.py", "exit 1")
    for _ in range(2):
        claim(root)
        payload, log = stop(root, host="kimi")
    budget_events = [e for e in log if e.get("event") == "continuation_budget_spent"]
    anchor_checks = [e for e in log if e.get("event") == "anchor_checked"]
    fourth = [e for e in budget_events if "outcome" in e]
    # The audit must not call a never-run anchor red.
    audit = run(root, "validate_artifact.py", ".goals", "--audit")
    text = audit.stdout + audit.stderr
    refused_reported = "no anchor executed" in text
    report(
        "r9-no-fourth-outcome",
        not fourth and not anchor_checks and refused_reported
        and "anchor still red" not in text,
        {
            "budget_event_keys": sorted(budget_events[0]) if budget_events else [],
            "anchor_checked": len(anchor_checks),
            "audit_names_refusal": refused_reported,
        },
    )


# --- F10: failed transitions are not successes --------------------------------
def checked_transitions() -> None:
    # (a) measurement write failure: green is announced as unrecorded.
    root = fixture("writefail", anchor="/usr/bin/true")
    arm(root)
    log = root / ".goals" / "probe.events.jsonl"
    log.write_text("", "utf-8")
    readonly(log)
    claim(root)
    payload, _ = stop(root)
    message = payload.get("systemMessage", "")
    report(
        "r5-measurement-write-checked",
        "passed on attempt" in message
        and "unrecorded" in message
        and log.stat().st_size == 0,
        {
            "message_tail": message[-140:],
            "event_bytes": log.stat().st_size,
        },
    )
    writable(log)

    # (b) candidate consume failure: refused, never judged twice. The one
    # claim is written while the directory is still writable; it must
    # survive both judgments precisely because it cannot be consumed.
    root = fixture("consumefail", anchor="/usr/bin/true")
    arm(root)
    claim(root)
    readonly(root / ".goals")
    messages = []
    for _ in range(2):
        payload, log_rows = stop(root)
        messages.append(payload.get("reason", payload.get("systemMessage", "")))
    checks = [e for e in log_rows if e.get("event") == "anchor_checked"]
    writable(root / ".goals")
    report(
        "r5-consume-checked",
        all("could not be removed" in m or "not judged" in m for m in messages)
        and not checks
        and (root / ".goals" / "probe.candidate").exists(),
        {
            "messages_head": [m[:70] for m in messages],
            "anchor_checked": len(checks),
            "candidate_survived": (root / ".goals" / "probe.candidate").exists(),
        },
    )

    # (c) disarm failure: not announced as disarmed, and no repeat event.
    root = fixture("disarmfail")
    arm(root)
    edit_frozen(root)
    readonly(root / ".goals")
    payload_a, log_a = stop(root)
    payload_b, log_b = stop(root)
    writable(root / ".goals")
    moved = [e for e in log_b if e.get("event") == "frozen_spec_changed"]
    report(
        "r5-disarm-checked",
        "could not remove" in payload_a.get("systemMessage", "")
        and "could not remove" in payload_b.get("systemMessage", "")
        and (root / ".goals" / "active").exists()
        and len(moved) <= 1,
        {
            "first_says": payload_a.get("systemMessage", "")[130:260],
            "marker_after": (root / ".goals" / "active").exists(),
            "frozen_spec_changed_events": len(moved),
        },
    )


# --- F3 (gate half): a run without an armed baseline is refused, not judged ---
def unverified_run() -> None:
    root = fixture("nobaseline", anchor="/usr/bin/false")
    # Hand-armed the old way: marker, no spec baseline.
    (root / ".goals" / "active").write_text("probe\n", "utf-8")
    claim(root)
    payload, log = stop(root)
    report(
        "r5-unarmed-claims-refused",
        payload.get("decision") == "block"
        and "spec baseline" in payload.get("reason", "")
        and not any(e.get("event") == "anchor_checked" for e in log),
        {
            "decision": payload.get("decision"),
            "reason_head": payload.get("reason", "")[:90],
        },
    )


for probe in (
    baseline_launder,
    trace_rebaseline_launder,
    worker_join,
    ceiling_bypass,
    double_arm,
    disarm_with_session,
    deny_shapes,
    axis_leak,
    checked_transitions,
    unverified_run,
):
    probe()

print()
print(json.dumps({"results": results}, indent=1))
sys.exit(0 if all(r["ok"] for r in results) else 1)
