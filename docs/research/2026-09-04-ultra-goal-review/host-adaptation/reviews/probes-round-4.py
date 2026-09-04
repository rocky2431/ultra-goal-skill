#!/usr/bin/env python3
"""Round-4 post-fix probes, same class as the plan's evidence.json receipts.

Three probes, each in an isolated throwaway directory:

1. claude-allow-no-context  - our gate ALLOWING must end the turn and carry no
   model context (defect 1.1 post-fix positive).
2. codex-deny-toplevel      - our gate DENYING with the top-level pair only
   must still block (defect 1.5 post-fix positive control).
3. claude-dual-session      - a session that is not the marker's owner is
   invisible to the gate (defect 1.4 post-fix positive).

Each registers the REAL gate script (copies, so paths carry no spaces) behind
a logging wrapper, arms a real goal in the probe directory, and records what
the host actually did.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# The worktree these ran in is gone; resolve the repository from this
# file so the drivers stay runnable where the record now lives.
REPO = Path(__file__).resolve().parents[5]
SCRIPTS = REPO / "plugins" / "ultra-goal" / "skills" / "ultra-goal" / "scripts"
CLAUDE = "/Users/rocky243/.local/share/claude/versions/2.1.260"
CODEX = "/Users/rocky243/.local/bin/codex"

sys.path.insert(0, str(SCRIPTS))
from goal_hooks import frozen_digest  # noqa: E402

WRAPPER = '''#!/usr/bin/env python3
import json, subprocess, sys
from pathlib import Path
here = Path(__file__).parent
raw = sys.stdin.read()
try:
    event = json.loads(raw)
except Exception:
    event = {}
log = here / "hook-events.jsonl"
count = len(log.read_text().splitlines()) if log.exists() else 0
child = subprocess.run(
    [sys.executable, str(here / "goal_stop.py")],
    input=raw, capture_output=True, text=True,
)
with log.open("a") as handle:
    handle.write(json.dumps({
        "index": count + 1,
        "hook_event_name": event.get("hook_event_name"),
        "session_id": event.get("session_id"),
        "stop_hook_active": event.get("stop_hook_active"),
        "gate_stdout": child.stdout,
        "gate_exit": child.returncode,
    }) + "\\n")
sys.stdout.write(child.stdout)
sys.stderr.write(child.stderr)
sys.exit(child.returncode)
'''

GOAL = """# Goal: probe

## Intent

Probe the gate.

## Boundary

**Scope.** Only this directory.

**Confidence.** Never claim without the anchor.

**Inference.** Reproduce everything.

## Stop condition

Stop when the anchor is green, or after 4 turns.

## Anchor

```
{anchor}
```

## Carry-over

### State

- nothing yet

### Lessons

- nothing yet

### Next

- finish the probe
"""

GREEN = "/usr/bin/true"
RED = "/usr/bin/false"

results: list[dict] = []


def probe_dir(name: str, anchor: str, candidate: bool,
              marker_extra: str = "") -> Path:
    root = Path(tempfile.mkdtemp(prefix=f"ultra-goal-r4-{name}-"))
    goals = root / ".goals"
    goals.mkdir()
    spec = GOAL.format(anchor=anchor)
    (goals / "probe.goal.md").write_text(spec)
    (goals / "active").write_text("probe" + marker_extra)
    # Round 5: the gate compares against the arming-time spec baseline
    # (`<slug>.spec.baseline`, what goal_run.py arm records) and refuses
    # claims on a run without one - so the probe arms the way the fence does.
    (goals / "probe.spec.baseline").write_text(
        frozen_digest(spec) + "\n", encoding="utf-8"
    )
    if candidate:
        (goals / "probe.candidate").write_text("probe complete\n")
    for script in ("goal_stop.py", "goal_hooks.py"):
        shutil.copy2(SCRIPTS / script, root / script)
    (root / "wrapper.py").write_text(WRAPPER)
    return root


def claude_run(root: Path, prompt: str) -> subprocess.CompletedProcess:
    # Project-scope settings only: user-scope hooks on this machine (hindsight
    # memory injection among them) otherwise reach every --print session and
    # derail the probe model; --setting-sources project skips them while our
    # registration rides the project file.
    project = root / ".claude"
    project.mkdir(exist_ok=True)
    (project / "settings.json").write_text(json.dumps({
        "hooks": {"Stop": [{"matcher": "*", "hooks": [{
            "type": "command",
            "command": f'python3 "{root / "wrapper.py"}"',
            "timeout": 120,
        }]}]},
    }))
    return subprocess.run(
        [CLAUDE, "--print", "--no-session-persistence", "--strict-mcp-config",
         "--mcp-config", '{"mcpServers":{}}', "--tools", "",
         "--setting-sources", "project", prompt],
        capture_output=True, text=True, timeout=180, cwd=str(root),
    )


def codex_run(root: Path, prompt: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [CODEX, "exec", "--ephemeral", "--skip-git-repo-check",
         "--sandbox", "read-only", "--dangerously-bypass-hook-trust",
         "--config",
         f'hooks.Stop=[{{hooks=[{{type="command",command="python3 {root}/wrapper.py"}}]}}]',
         prompt],
        capture_output=True, text=True, timeout=240, cwd=str(root),
    )


def events(root: Path) -> list[dict]:
    log = root / "hook-events.jsonl"
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def report(name: str, ok: bool, detail: dict) -> None:
    results.append({"probe": name, "ok": ok, **detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    for key, value in detail.items():
        print(f"    {key}: {value}")


# --- 1. Claude Code: an allow from the fixed gate ends the turn, silently ---
root = probe_dir("claude-allow", GREEN, candidate=False)
result = claude_run(
    root,
    "This is an authorized isolated hook lifecycle probe. Reply with exactly "
    "PROBE_INITIAL and finish. No tools or other actions are needed.",
)
rows = events(root)
gate_out = rows[0]["gate_stdout"] if rows else ""
allow_payload = json.loads(gate_out) if gate_out.strip() else {}
report(
    "clean-claude-allow-no-context",
    result.returncode == 0
    and len(rows) == 1
    and "systemMessage" in allow_payload
    and "hookSpecificOutput" not in allow_payload
    and "additionalContext" not in gate_out
    and "PROBE_INITIAL" in result.stdout
    and "PROBE_CORRECTED" not in result.stdout,
    {
        "exit": result.returncode,
        "stop_callbacks": len(rows),
        "gate_payload_keys": sorted(allow_payload),
        "visible": [w for w in ("PROBE_INITIAL", "PROBE_CORRECTED")
                    if w in result.stdout],
    },
)

# --- 2. Codex: the top-level-only deny must still block ---------------------
root = probe_dir("codex-deny", RED, candidate=True)
result = codex_run(
    root,
    "This is an authorized isolated hook lifecycle probe. First reply with "
    "exactly PROBE_INITIAL, then finish. If a Stop hook corrects you, reply "
    "with exactly PROBE_CORRECTED and finish. No other actions are needed.",
)
rows = events(root)
first = json.loads(rows[0]["gate_stdout"]) if rows and rows[0]["gate_stdout"].strip() else {}
# codex exec prints only the final agent message to stdout, so the
# observable is the continuation itself: a second Stop callback whose chain
# flag is true, plus the corrected token the model emitted after the deny.
report(
    "clean-codex-deny-toplevel",
    result.returncode == 0
    and len(rows) >= 2
    and rows[1].get("stop_hook_active") is True
    and first.get("decision") == "block"
    and "hookSpecificOutput" not in first
    and "PROBE_CORRECTED" in result.stdout,
    {
        "exit": result.returncode,
        "stop_callbacks": len(rows),
        "chain_flags": [r.get("stop_hook_active") for r in rows],
        "deny_form": sorted(first),
        "visible": [w for w in ("PROBE_INITIAL", "PROBE_CORRECTED")
                    if w in result.stdout],
    },
)

# --- 3. Claude Code: a stranger session is invisible to the gate ------------
root = probe_dir("claude-stranger", RED, candidate=True,
                 marker_extra="\nsession session-owner-not-this-one")
result = claude_run(
    root,
    "This is an authorized isolated hook lifecycle probe. Reply with exactly "
    "PROBE_STRANGER and finish. No tools or other actions are needed.",
)
rows = events(root)
gate_out = rows[0]["gate_stdout"] if rows else ""
report(
    "clean-claude-dual-session",
    result.returncode == 0
    and len(rows) == 1
    and gate_out.strip() == ""
    and not (root / ".goals" / "probe.events.jsonl").exists()
    and "PROBE_STRANGER" in result.stdout,
    {
        "exit": result.returncode,
        "stop_callbacks": len(rows),
        "gate_output": repr(gate_out[:120]),
        "events_file_created": (root / ".goals" / "probe.events.jsonl").exists(),
    },
)

print()
print(json.dumps({"results": results}, indent=1))
sys.exit(0 if all(r["ok"] for r in results) else 1)
