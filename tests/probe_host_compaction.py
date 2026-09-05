#!/usr/bin/env python3
"""Opt-in native /compact probe; a test client, never a product driver.

Reuses the lifecycle fixture and existing authentication in temporary copies.
Native command rejection and absence of a compaction event remain visible.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pty
import select
import shlex
import sqlite3
import subprocess
import struct
import sys
import tempfile
import termios
import time

from probe_host_lifecycle import Probe, SCRIPTS, json_lines


def invoke(probe, prompt, label, session=None):
    args = list(probe.args)
    if session:
        args += ["--session" if probe.host == "kimi" else "--resume", session]
    if probe.host == "kimi":
        args += ["-p", prompt]
    elif probe.host == "zcode":
        args += ["--prompt", prompt]
    else:
        args += [prompt]
    try:
        result = subprocess.run(args, cwd=probe.root,
                                env={**probe.env, "UG_PROBE_LABEL": label},
                                capture_output=True, text=True, timeout=180)
        return {"exit": result.returncode, "stdout": result.stdout[-10000:],
                "stderr": result.stderr[-2000:]}
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or b""
        return {"exit": None, "timeout_seconds": 180,
                "stdout": (output.decode(errors="replace") if isinstance(output, bytes) else output)[-10000:]}


def compact_records(root):
    """Retain event identities, not private config or whole host transcripts."""
    found = []
    for path in root.rglob("*.jsonl"):
        if "session" not in str(path.relative_to(root)).lower():
            continue
        try:
            rows = json_lines(path)
        except (OSError, ValueError):
            continue
        for row in rows:
            kind = row.get("type") or row.get("event") or ""
            subtype = row.get("subtype", "")
            if "compact" in (str(kind) + str(subtype)).lower():
                found.append({"file": str(path.relative_to(root)), "type": kind,
                              "subtype": subtype, "keys": sorted(row)})
    database = root / "zcode-home/.zcode/cli/db/db.sqlite"
    if database.exists():
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
            for data, in connection.execute("select data from part"):
                row = json.loads(data)
                if row.get("type") == "compaction" or row.get("timelineType") == "context_compaction":
                    found.append({"native_storage": "SQLite part table", **{
                        key: value for key, value in row.items()
                        if key in {"type", "timelineType", "status", "trigger", "auto"}}})
    return found


def stop_tui(process):
    """Reap only this test's child; preserve cleanup errors in the receipt."""
    notes = []
    for action in ("terminate", "kill"):
        if process.poll() is not None:
            break
        try:
            getattr(process, action)()
            process.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError) as exc:
            notes.append(f"{action}: {exc}")
    return {"reaped": process.poll() is not None, "exit": process.returncode, "notes": notes}


def invoke_kimi_compact_tui(probe, session):
    """Send the documented native TUI command; do not emulate compaction."""
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
    # Isolate HOME as well so the native onboarding cannot offer to migrate
    # unrelated legacy sessions from the owner's real home.
    home = probe.root / "kimi-tui-home"
    home.mkdir(mode=0o700)
    process = subprocess.Popen([probe.args[0], "--session", session, "--auto"],
                               cwd=probe.root, env={**probe.env, "HOME": str(home), "TERM": "xterm-256color", "UG_PROBE_LABEL": "K"},
                               stdin=slave, stdout=slave, stderr=slave)
    os.close(slave)
    output = bytearray()
    start, sent, compacted_at, trusted, ready_at = time.monotonic(), False, None, False, None
    observation_error = None
    try:
        while process.poll() is None and time.monotonic() - start < 130:
            if select.select([master], [], [], 0.2)[0]:
                try:
                    chunk = os.read(master, 65536)
                    output.extend(chunk)
                    if b"\x1b[6n" in chunk:
                        os.write(master, b"\x1b[1;1R")
                except OSError:
                    break
            if not trusted and b"Trust this folder?" in output:
                # This fixture contains only the authorized probe; the native
                # choice is recorded in the temporary KIMI_CODE_HOME only.
                os.write(master, b"\r")
                trusted = True
            ready = any(row["event"] == "SessionStart" and row["label"] == "K" for row in probe.transport())
            if ready:
                ready_at = ready_at or time.monotonic()
            if not sent and ready_at and time.monotonic() - ready_at > 2:
                os.write(master, b"/compact")
                time.sleep(0.1)
                os.write(master, b"\r")
                sent = True
            (probe.root / "kimi-tui-output.txt").write_bytes(output[-10000:])
            records = compact_records(probe.root)
            if any(any(word in str(row.get("type", "")).lower() for word in ("end", "finish", "complete")) for row in records):
                compacted_at = compacted_at or time.monotonic()
            if compacted_at and time.monotonic() - compacted_at > 3:
                break
    except Exception as exc:
        observation_error = str(exc)
    finally:
        cleanup = stop_tui(process)
        os.close(master)
    return {"exit": process.returncode, "surface": "native TUI /compact", "command_sent": sent,
            "temporary_fixture_trust_selected": trusted,
            "observation_error": observation_error, "cleanup": cleanup,
            "stdout": output.decode(errors="replace")[-10000:]}


def run(host, root, tui=False):
    probe = Probe(host, root)
    runner = shlex.join([sys.executable, str(probe.scripts / "goal_run.py")])
    marker = "ULTRA_COMPACT_RECOVERY_7e942d"
    goal_path = root / ".goals/demo.goal.md"
    spec = goal_path.read_text()
    spec = spec.replace("## Carry-over\n", f"## Carry-over\n\nRecovery marker: {marker}\n", 1)
    goal_path.write_text(spec)
    initial = invoke(probe, f"""Authorized isolated native compaction acceptance probe. Work only in {root}.
No commits, installs, external writes, login, config edits, or native goal creation.
Ignore the dependency-upgrade example in the synthetic fixture.
Read session-A.json written by the native SessionStart hook, then run:
{runner} arm demo --session-id <that exact session_id>
Read .goals/demo.goal.md Carry-over. Report its recovery marker and state that the goal is unfinished.
Do not write a completion candidate or manually call any hook. Finish your response.""", "A")
    starts = [row for row in probe.transport() if row["event"] == "SessionStart"]
    if not starts:
        return {"ok": False, "stage": "initial", "initial": initial,
                "error": "No real SessionStart identity observed"}
    owner = starts[0]["session_id"]
    active = root / ".goals/active"
    initial_marker = active.read_text() if active.exists() else None
    bound = initial_marker == f"demo\nsession {owner}\n"
    before = hashlib.sha256(goal_path.read_bytes()).hexdigest()
    compact = invoke_kimi_compact_tui(probe, owner) if tui else invoke(probe, "/compact", "K", owner)
    after_compact = probe.transport()
    resume = invoke(probe, """Continue the authorized isolated probe. Read .goals/demo.goal.md Carry-over from disk now.
Report RECOVERY_FROM_DISK followed by its exact recovery marker, and ULTRA_UNFINISHED.
Do not change any file, run the anchor, create a candidate, or manually call a hook.""", "R", owner)
    transport = [{k: v for k, v in row.items() if k != "session_id"}
                 for row in probe.transport() if row["event"] in {"PreCompact", "SessionStart", "Stop"}]
    native_precompact = any(row["event"] == "PreCompact" and row["label"] == "K"
                            for row in after_compact)
    records = compact_records(root)
    observations = {
        "initial_session_bound": bound,
        "native_precompact_observed": native_precompact,
        "native_compact_session_start_observed": any(row["event"] == "SessionStart" and row.get("source") == "compact" for row in after_compact),
        "native_compact_records_observed": bool(records),
        "recovered_marker_from_disk": marker in resume["stdout"] and "RECOVERY_FROM_DISK" in resume["stdout"],
        "unfinished_not_reported_complete": "ULTRA_UNFINISHED" in resume["stdout"] and not any(row.get("outcome") == "green" for row in probe.events()),
        "carry_over_unchanged": hashlib.sha256(goal_path.read_bytes()).hexdigest() == before,
        "session_binding_preserved": bound and active.exists() and active.read_text() == initial_marker,
    }
    native_confirmed = observations["native_compact_session_start_observed"] or any(
        row.get("status") == "completed" or row.get("type") == "full_compaction.complete" or any(
            word in str(row.get("type", "")).lower() for word in ("compact.end", "compact_end", "compactend", "compacted", "compact.complete"))
        for row in records)
    observations["native_compaction_completed"] = native_confirmed
    return {"ok": native_confirmed and observations["recovered_marker_from_disk"] and observations["session_binding_preserved"],
            "surface": ("native TUI" if tui else "native CLI prompt mode") + " /compact plus same-session resume",
            "observations": observations, "initial": initial, "compact": compact,
            "resume": resume, "native_compact_records": records, "transport": transport,
            "limit": "A successful model response alone does not prove native compaction. zCode does not register a PreCompact hook in this profile."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", choices=("claude", "kimi", "zcode"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kimi-tui", action="store_true")
    args = parser.parse_args()
    receipt = {"host": args.host, "started_at_unix": time.time(),
               "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SCRIPTS.glob("*.py")}}
    with tempfile.TemporaryDirectory(prefix=f"ug-compact-{args.host}-") as directory:
        try:
            receipt.update(run(args.host, Path(directory), args.kimi_tui))
        except Exception as exc:
            receipt.update(ok=False, error=str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"host": args.host, "ok": receipt["ok"], "output": str(args.output), "error": receipt.get("error")}))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
