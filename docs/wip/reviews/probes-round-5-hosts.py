#!/usr/bin/env python3
"""Round-5 host probes: the three items on Codex's acceptance list that no
script-level control can cover.

1. kimi-deny-nested       - the corrected Kimi-specific deny is consumed BY KIMI:
   a red anchor's nested hookSpecificOutput pair must keep the turn alive and
   put the reason in front of the model. Registered through KIMI_CODE_HOME so
   the owner's own config is never written (config-files reference).
2. zcode-documented-root  - zCode drives the gate from ZCODE_PLUGIN_ROOT, with
   the Stop hook registered in a settings file passed to --settings and
   hooks.enabled true (hooks reference + the shape of the owner's own
   config.json: hooks.events.<Event>).
3. windows-batch-guard    - every commandWindows string's missing-file guard,
   executed by a cmd.exe batch-subset interpreter. THIS IS A SIMULATOR, NOT A
   HOST: it proves the guard's logic, and it does not prove Windows.

Isolated throwaway directories; the real shipped scripts (copied, so paths
carry no spaces); the real arming fence.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path("/Users/rocky243/Context Engineering/ultra-goal-adapt")
SCRIPTS = REPO / "plugins" / "ultra-goal" / "skills" / "ultra-goal" / "scripts"
KIMI = Path("/Users/rocky243/.kimi-code/bin/kimi")
KIMI_HOME = Path("/Users/rocky243/.kimi-code")
ZCODE_CJS = Path("/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs")
ZCODE_NODE = Path("/Users/rocky243/.hermes/node/bin/node")

results: list[dict] = []


def report(name: str, ok: bool, detail: dict) -> None:
    results.append({"probe": name, "ok": ok, **detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    for key, value in detail.items():
        print(f"    {key}: {value}")


# The wrapper records what the gate was handed and what it answered, without
# changing either: the probe's only claim is about the host's behaviour.
WRAPPER = '''#!/usr/bin/env python3
import json, subprocess, sys
from pathlib import Path
here = Path(__file__).parent
raw = sys.stdin.read()
try:
    event = json.loads(raw)
except Exception:
    event = {}
log = here.parent.parent.parent.parent / "hook-events.jsonl"
count = len(log.read_text().splitlines()) if log.exists() else 0
child = subprocess.run(
    [sys.executable, str(here / "goal_stop.py"), *sys.argv[1:]],
    input=raw, capture_output=True, text=True,
)
with log.open("a") as handle:
    handle.write(json.dumps({
        "index": count + 1,
        "event": event.get("hook_event_name") or event.get("hookEventName"),
        "keys_in": sorted(event.keys()),
        "gate_stdout": child.stdout,
        "gate_exit": child.returncode,
        "argv": sys.argv[1:],
        "plugin_root_env": {k: v for k, v in __import__("os").environ.items()
                            if k.endswith("PLUGIN_ROOT")},
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
/usr/bin/false
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

- [ ] probe line

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


def fixture(name: str, candidate: bool = False) -> Path:
    root = Path(tempfile.mkdtemp(prefix=f"ug-host-{name}-"))
    scripts = root / "pluginroot" / "skills" / "ultra-goal" / "scripts"
    scripts.mkdir(parents=True)
    for script in SCRIPTS.glob("*.py"):
        shutil.copy2(script, scripts / script.name)
    (scripts / "wrapper.py").write_text(WRAPPER, encoding="utf-8")
    (scripts / "wrapper.py").chmod(0o755)
    goals = root / ".goals"
    goals.mkdir()
    (goals / "probe.goal.md").write_text(GOAL, encoding="utf-8")
    (goals / "probe.decisions.md").write_text(DECISIONS, encoding="utf-8")
    subprocess.run(
        [sys.executable, str(scripts / "goal_run.py"), "arm", "probe"],
        cwd=str(root), capture_output=True, text=True, check=True,
    )
    if candidate:
        # The gate runs the anchor at a completion claim, not at every Stop
        # (the completion contract), so a probe about the DENY has to make the
        # claim. Written here rather than asked of the model: what is under
        # test is the host's handling of the deny, not the model's compliance.
        (root / ".goals" / "probe.candidate").write_text(
            "the probe claims completion", encoding="utf-8")
    return root


def events(root: Path) -> list[dict]:
    log = root / "hook-events.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------- probe 1: Kimi

def probe_kimi() -> None:
    if not KIMI.exists():
        report("kimi-deny-nested", False, {"why": "kimi binary absent"})
        return
    root = fixture("kimi", candidate=True)
    wrapper = root / "pluginroot" / "skills" / "ultra-goal" / "scripts" / "wrapper.py"

    # KIMI_CODE_HOME redirects the whole config directory (config-files
    # reference), so the owner's ~/.kimi-code is read but never written.
    home = root / "kimi-home"
    home.mkdir()
    for item in ("config.toml", "tui.toml", "device_id", "region"):
        src = KIMI_HOME / item
        if src.exists():
            shutil.copy2(src, home / item)
    for item in ("oauth", "credentials", "workspace-trust"):
        src = KIMI_HOME / item
        if src.is_dir():
            shutil.copytree(src, home / item)
    with (home / "config.toml").open("a") as handle:
        handle.write(
            "\n[[hooks]]\n"
            'event = "Stop"\n'
            f'command = "{sys.executable} {wrapper} --host kimi"\n'
            "timeout = 120\n"
        )

    env = {**os.environ, "KIMI_CODE_HOME": str(home)}
    proc = subprocess.run(
        [str(KIMI), "-p", "Reply with exactly the word DONE and nothing else.",
         "--output-format", "text"],
        cwd=str(root), env=env, capture_output=True, text=True, timeout=600,
    )
    log = events(root)
    payloads = [json.loads(e["gate_stdout"]) for e in log if e["gate_stdout"].strip()]
    nested = [p for p in payloads if "hookSpecificOutput" in p]
    denied = [p for p in nested
              if p["hookSpecificOutput"].get("permissionDecision") == "deny"]
    reason = denied[0]["hookSpecificOutput"].get("permissionDecisionReason", "") if denied else ""
    # Kimi's contract: the nested deny keeps the turn alive and "writes the
    # blocking reason back into the context". Read that off the host's own wire
    # log rather than off the model's prose - a paraphrase in stdout would be
    # inference, and an echo is not what the reference promises. The proof is
    # one context.append_message carrying the reason verbatim, followed by a
    # further llm.request: the reason entered the context and the turn ran on.
    #
    # One Stop callback is CORRECT here, not a miss: this host triggers a
    # blocking Stop at most once per turn, which is the budget the gate
    # declares for it.
    appended = False
    requests_after = 0
    for wire in sorted(home.glob("sessions/*/*/agents/*/wire.jsonl")):
        records = [json.loads(line) for line in
                   wire.read_text(encoding="utf-8").splitlines() if line.strip()]
        for index, record in enumerate(records):
            if record.get("type") != "context.append_message":
                continue
            texts = [part.get("text", "") for part
                     in record.get("message", {}).get("content", [])]
            if reason and any(reason in text for text in texts):
                appended = True
                requests_after = sum(
                    1 for later in records[index + 1:]
                    if later.get("type") == "llm.request")
                break
        if appended:
            break

    alive = appended and requests_after > 0
    report("kimi-deny-nested", bool(denied) and alive, {
        "kimi_exit": proc.returncode,
        "stop_callbacks": len(log),
        "budget_for_this_host": "1 blocking Stop per turn - 1 callback is the max, not a miss",
        "gate_payload_keys": [sorted(p.keys()) for p in payloads],
        "nested_deny": bool(denied),
        "reason_head": reason[:60],
        "reason_appended_to_context_verbatim": appended,
        "llm_requests_after_the_deny": requests_after,
        "turn_stayed_alive": alive,
        "stdout_tail": proc.stdout[-300:].replace("\n", " | "),
    })


# --------------------------------------------------------------- probe 2: zCode

def probe_zcode() -> None:
    if not ZCODE_CJS.exists() or not ZCODE_NODE.exists():
        report("zcode-documented-root", False, {"why": "zcode bundle or node absent"})
        return
    root = fixture("zcode", candidate=True)
    plugin_root = root / "pluginroot"

    # zCode 0.16.5 lists `--settings <path>` in its own --help and its parser
    # rejects it as an unknown option at every position tried (bare, and after
    # `tui` and `app-server`); `--max-turns` behaves the same way. Its docs
    # name no config-directory environment variable either. So the only way in
    # is the documented user-level file, `~/.zcode/cli/config.json` with
    # hooks.enabled true - and reaching it without writing the owner's own
    # config means relocating HOME. The events shape under it is read off the
    # owner's live config: hooks.events.<Event>.
    home = root / "zcode-home"
    (home / ".zcode" / "cli").mkdir(parents=True)
    owner_config = Path("/Users/rocky243/.zcode/cli/config.json")
    config = json.loads(owner_config.read_text(encoding="utf-8"))
    launcher = (
        'P="${ZCODE_PLUGIN_ROOT}/skills/ultra-goal/scripts/wrapper.py"; '
        '[ -f "$P" ] || exit 0; '
        'if command -v python3 >/dev/null 2>&1; then exec python3 "$P" --host zcode; '
        'else exec python "$P" --host zcode; fi'
    )
    # Our Stop hook only: the owner's own registrations point at another
    # plugin's paths, and this probe is about this gate.
    config["hooks"] = {
        "enabled": True,
        "events": {
            "Stop": [{
                # "*", the value this plugin ships. NOT "" - zCode 0.16.5's own
                # hooks documentation uses "matcher": "" in its Stop example,
                # and that value makes the host reject the WHOLE config file
                # while reporting "Model config is missing", naming a section
                # that is intact. Bisected here against the owner's own working
                # config: "" fails, ".*" and "*" both load.
                "matcher": "*",
                "hooks": [{
                    "type": "command",
                    "command": launcher,
                    "timeout": 120,
                    "statusMessage": "Checking the loop's anchor",
                }],
            }],
        },
        "maxOutputBytes": 32768,
    }
    (home / ".zcode" / "cli" / "config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8")

    env = {**os.environ,
           "HOME": str(home),
           "ZCODE_PLUGIN_ROOT": str(plugin_root)}
    proc = subprocess.run(
        [str(ZCODE_NODE), str(ZCODE_CJS),
         "--prompt", "Reply with exactly the word DONE and nothing else.",
         "--mode", "yolo", "--no-color"],
        cwd=str(root), env=env, capture_output=True, text=True, timeout=900,
    )
    log = events(root)
    payloads = [json.loads(e["gate_stdout"]) for e in log if e["gate_stdout"].strip()]
    top_level = [p for p in payloads if p.get("decision") == "block"]
    roots_seen = [e.get("plugin_root_env", {}) for e in log]
    resolved = all(e.get("plugin_root_env", {}).get("ZCODE_PLUGIN_ROOT") == str(plugin_root)
                   for e in log) and bool(log)
    report("zcode-documented-root", bool(log) and bool(top_level) and resolved, {
        "zcode_exit": proc.returncode,
        "stop_callbacks": len(log),
        "gate_ran": bool(log),
        "host_tag": [e.get("argv") for e in log],
        "path_and_tag_from_ZCODE_PLUGIN_ROOT": resolved,
        "resolved_from": roots_seen,
        "deny_form": [sorted(p.keys()) for p in top_level],
        "reference_gap": "--settings and --max-turns are listed in zcode 0.16.5 "
                         "--help and rejected by its parser; no config-dir env "
                         "var is documented, so HOME is the isolation",
        "stdout_tail": proc.stdout[-400:].replace("\n", " | "),
        "stderr_tail": proc.stderr[-400:].replace("\n", " | "),
    })


# ------------------------------------------------- probe 3: the Windows guards

CMD_IF_NOT_EXIST = re.compile(
    r'^if\s+not\s+exist\s+"(?P<path>[^"]+)"\s+(?P<then>.*)$', re.IGNORECASE)


def expand(text: str, env: dict[str, str]) -> str:
    """%VAR% expansion, cmd.exe's rule: an unset variable is left verbatim."""
    return re.sub(r"%([A-Za-z_][A-Za-z0-9_]*)%",
                  lambda m: env.get(m.group(1), m.group(0)), text)


def cmd_subset(command: str, env: dict[str, str], fs: set[str]) -> tuple[int, list[str]]:
    """Execute the batch subset these launchers use, and report what ran.

    Supported, because it is all they use: %VAR% expansion, `if not exist
    "<path>" <then>`, `exit /b <n>`, `&` sequencing, `||` on a failed `where`,
    and `where <exe>` resolved against a declared PATH set. Anything else is
    reported as reached rather than silently treated as a success.
    """
    ran: list[str] = []
    for step in [s.strip() for s in expand(command, env).split("&") if s.strip()]:
        match = CMD_IF_NOT_EXIST.match(step)
        if match:
            missing = match.group("path").replace("\\", "/") not in fs
            ran.append(f"if-not-exist({match.group('path')})->{'taken' if missing else 'skipped'}")
            if not missing:
                continue
            step = match.group("then").strip()
            if step.startswith("(") and step.endswith(")"):
                step = step[1:-1].strip()
        if re.match(r"^exit\s+/b(\s+\d+)?$", step, re.IGNORECASE):
            code = re.findall(r"\d+", step)
            ran.append(f"exit /b {code[0] if code else 0}")
            return int(code[0]) if code else 0, ran
        if re.match(r"^exit(\s+\d+)?$", step, re.IGNORECASE):
            code = re.findall(r"\d+", step)
            ran.append(f"exit {code[0] if code else 0}")
            return int(code[0]) if code else 0, ran
        ran.append(step)
    return 0, ran


def probe_windows() -> None:
    manifests = [
        REPO / "plugins" / "ultra-goal" / "hooks" / "hooks.json",
        REPO / "plugins" / "ultra-goal" / "hooks" / "claude.json",
        REPO / "plugins" / "ultra-goal" / "hooks" / "codex.json",
    ]
    found: list[tuple[str, str, str]] = []
    for manifest in manifests:
        if not manifest.exists():
            continue
        blob = json.loads(manifest.read_text())
        for event, matchers in blob.get("hooks", {}).items():
            for matcher in matchers:
                for entry in matcher.get("hooks", []):
                    win = entry.get("commandWindows")
                    if win:
                        found.append((manifest.name, event, win))

    env = {"CLAUDE_PLUGIN_ROOT": r"C:\plugins\ultra-goal"}
    failures: list[str] = []
    for name, event, command in found:
        # The script is absent: the guard must exit 0 and reach no interpreter.
        code, ran = cmd_subset(command, env, fs=set())
        if code != 0 or any(step.startswith(("py ", "python")) for step in ran):
            failures.append(f"{name}:{event} missing-file: exit={code} ran={ran}")
        # The script is present: the interpreter must be reached.
        target = re.findall(r'"([^"]*\.py)"', expand(command, env))
        present = {t.replace("\\", "/") for t in target}
        code2, ran2 = cmd_subset(command, env, fs=present)
        if not any(step.startswith(("py ", "python", "where ")) for step in ran2):
            failures.append(f"{name}:{event} present: ran={ran2}")

    report("windows-batch-guard", bool(found) and not failures, {
        "SIMULATOR": "cmd.exe batch subset, not a Windows host - proves the "
                     "guard's logic, does not prove Windows",
        "commandWindows_found": len(found),
        "events": [f"{n}:{e}" for n, e, _ in found],
        "failures": failures or "none",
    })


if __name__ == "__main__":
    probe_windows()
    probe_kimi()
    probe_zcode()
    out = REPO / "docs" / "wip" / "reviews" / "probe-receipts-round-5-hosts.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nreceipts: {out}")
    sys.exit(0 if all(r["ok"] for r in results) else 1)
