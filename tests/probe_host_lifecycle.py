#!/usr/bin/env python3
"""Opt-in real-host probes in a temporary workspace, never a runtime service.

Uses existing authenticated host configuration in private temporary copies.
Only sanitized receipts leave that directory. Each hook calls shipped code;
the wrapper records transport observations without changing its result.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import queue
import threading


REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "plugins/ultra-goal"
SCRIPTS = PLUGIN / "skills/ultragoal/scripts"
OWNER_HOME = Path.home()
SESSION_ENV = {"CODEX_SESSION_ID", "CLAUDE_SESSION_ID", "KIMI_SESSION_ID", "ZCODE_SESSION_ID"}
HANDLERS = {"Stop": "goal_stop.py", "SessionStart": "goal_session_start.py",
            "PreCompact": "goal_pre_compact.py", "UserPromptSubmit": "goal_prompt_submit.py",
            "TurnStarted": "goal_turn_started.py", "PostToolUse": "goal_tool_success.py",
            "PostToolUseFailure": "goal_tool_failure.py"}

WRAPPER = '''import json,subprocess,sys,os
from pathlib import Path
root=Path(__file__).parent
raw=sys.stdin.read(); event=json.loads(raw)
name=event.get('hook_event_name'); session=event.get('session_id')
if name=='Stop':
    count=root/'native-stop-count'
    count.write_text(str(int(count.read_text())+1 if count.exists() else 1))
if session:
    (root/('session-'+os.environ.get('UG_PROBE_LABEL','A')+'.json')).write_text(json.dumps({'session_id':session}))
script=sys.argv[1]; host=sys.argv[2]
args=[sys.executable,str(root/'pluginroot/skills/ultragoal/scripts'/script)]
if name=='Stop': args += ['--host',host]
result=subprocess.run(args,input=raw,text=True,capture_output=True)
try: payload=json.loads(result.stdout) if result.stdout.strip() else {}
except ValueError: payload={'invalid_json':True}
with (root/'transport.jsonl').open('a') as f:
    f.write(json.dumps({'event':name,'session_id':session,'source':event.get('source'),
                        'label':os.environ.get('UG_PROBE_LABEL','A'),
                        'payload':payload,'exit':result.returncode})+'\\n')
sys.stdout.write(result.stdout);sys.stderr.write(result.stderr);sys.exit(result.returncode)
'''

ANCHOR = '''from pathlib import Path
import time
p=Path(__file__).parent
mode=(p/'mode').read_text().strip()
with (p/'anchor-runs').open('a') as f: f.write(mode+'\\n')
if mode=='timeout': time.sleep(3)
if mode=='error': raise RuntimeError('deliberate probe failure')
raise SystemExit(0 if mode=='green' and (p/'worker-result').is_file() else 1)
'''


def json_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


class Probe:
    def __init__(self, host, root):
        self.host, self.root = host, root
        self.env = {k: v for k, v in os.environ.items() if k not in SESSION_ENV}
        self.env.pop("CLAUDECODE", None)
        self.scripts = root / "pluginroot/skills/ultragoal/scripts"
        shutil.copytree(SCRIPTS, self.scripts)
        (root / "wrapper.py").write_text(WRAPPER)
        (root / "anchor.py").write_text(ANCHOR)
        (root / "mode").write_text("red")
        goals = root / ".goals"
        goals.mkdir()
        template = (PLUGIN / "skills/ultragoal/assets/goal-package.md").read_text()
        start, end = template.index("## Anchor"), template.index("## Means")
        template = template[:start] + f'## Anchor\n\n```\n{shlex.quote(sys.executable)} anchor.py\n```\n\nbudget: 1 second\n\n' + template[end:]
        template = template.replace("ceiling: 6", "ceiling: 12")
        # This probe tests host transport, not the example dependency goal.
        # Give its independent fixture anchor an explicit complete contract.
        start, end = template.index("## Verification"), template.index("## Cadence")
        definition = {"source": "owner-approved", "basis": "Independent host protocol fixture.",
                      "protected": ["anchor.py"], "covers": {"protocol": "anchor"}, "review": None}
        template = template[:start] + "## Verification\n\n```json\n" + json.dumps(definition) + "\n```\n\n## Acceptance\n\n- [ ] protocol: The fixture's worker result and current mode satisfy its check.\n\n" + template[end:]
        (goals / "demo.goal.md").write_text(template)
        (goals / "demo.decisions.md").write_text((PLUGIN / "skills/ultragoal/assets/decisions-record.md").read_text())
        self.args = self.configure()

    def hook(self, event):
        cmd = shlex.join([sys.executable, str(self.root / "wrapper.py"), HANDLERS[event], self.host])
        return {"type": "command", "command": cmd, "timeout": 15}

    def configure(self):
        root = self.root
        if self.host == "codex":
            args = [shutil.which("codex"), "exec", "--skip-git-repo-check", "--ignore-user-config",
                    "--dangerously-bypass-approvals-and-sandbox", "--dangerously-bypass-hook-trust", "--json"]
            for event in ("SessionStart", "Stop", "PreCompact"):
                h = self.hook(event)
                entry = '[{hooks=[{type="command",command=' + json.dumps(h['command']) + ',timeout=15}]}]'
                args += ["-c", f"hooks.{event}={entry}"]
            return args
        if self.host == "claude":
            config = {"hooks": {e: [{"matcher": "*", "hooks": [self.hook(e)]}]
                                for e in ("SessionStart", "Stop", "PreCompact", "PostToolUse", "PostToolUseFailure")}}
            path = root / "claude-settings.json"
            path.write_text(json.dumps(config))
            return [shutil.which("claude"), "-p", "--settings", str(path), "--setting-sources", "",
                    "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                    "--dangerously-skip-permissions", "--output-format", "json"]
        if self.host == "kimi":
            src = OWNER_HOME / ".kimi-code"
            home = root / "kimi-home"
            home.mkdir(mode=0o700)
            for item in ("config.toml", "tui.toml", "device_id", "region"):
                if (src / item).is_file(): shutil.copy2(src / item, home / item)
            for item in ("oauth", "credentials", "workspace-trust"):
                if (src / item).is_dir(): shutil.copytree(src / item, home / item)
            with (home / "config.toml").open("a") as f:
                for event in HANDLERS:
                    f.write(f'\n[[hooks]]\nevent = {json.dumps(event)}\ncommand = {json.dumps(self.hook(event)["command"])}\ntimeout = 15\n')
            self.env["KIMI_CODE_HOME"] = str(home)
            return [str(src / "bin/kimi"), "--output-format", "text"]
        home = root / "zcode-home"
        directory = home / ".zcode/cli"
        directory.mkdir(parents=True, mode=0o700)
        config = json.loads((OWNER_HOME / ".zcode/cli/config.json").read_text())
        config["hooks"] = {"enabled": True, "events": {
            e: [{"matcher": "*", "hooks": [self.hook(e)]}]
            for e in ("SessionStart", "Stop", "PostToolUse", "PostToolUseFailure")}}
        (directory / "config.json").write_text(json.dumps(config))
        self.env["HOME"] = str(home)
        return [str(OWNER_HOME / ".hermes/node/bin/node"),
                "/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs", "--mode", "yolo", "--no-color"]

    def invoke(self, prompt, label="A", resume=None, native=False):
        args = list(self.args)
        if resume:
            args += ["resume", resume] if self.host == "codex" else ["--session" if self.host == "kimi" else "--resume", resume]
        if native:
            if self.host in {'claude', 'kimi', 'zcode'}:
                prompt = '/goal ' + prompt
            else:
                args += ['--enable', 'goals']
                prompt = 'Explicit request: create a native goal with create_goal for this objective, then pursue it. ' + prompt
        if self.host == "kimi": args += ["-p", prompt]
        elif self.host == "zcode": args += ["--prompt", prompt]
        else: args += [prompt]
        result = subprocess.run(args, cwd=self.root, env={**self.env, "UG_PROBE_LABEL": label},
                                capture_output=True, text=True, timeout=480)
        (self.root / f"{label}-stdout.txt").write_text(result.stdout)
        (self.root / f"{label}-stderr.txt").write_text(result.stderr)
        if result.returncode:
            raise RuntimeError(f"{self.host} {label} exited {result.returncode}: {result.stderr[-500:]}")
        return result

    def events(self):
        return json_lines(self.root / ".goals/demo.events.jsonl")

    def transport(self):
        return json_lines(self.root / "transport.jsonl")

    def run(self):
        runner = shlex.quote(str(self.scripts / "goal_run.py"))
        prompt = f'''Authorized isolated hook acceptance probe. Work only in {self.root}. No commits, external writes, installs, login, or config edits.
The fixture is deliberately synthetic; do not perform its example dependency-upgrade task.
Read session-A.json, which was written by this host's SessionStart hook, and use its session_id to run:
{shlex.quote(sys.executable)} {runner} arm demo --session-id <that-id>
Then write .goals/demo.candidate containing 'deliberate red claim for protocol test'. Output exactly PROBE_INITIAL and end your response.
If a Stop hook refuses the claim, do the correction in ordinary tools: start a child Python process that writes worker-result containing WORKER_DONE and wait for it with subprocess.run(check=True); only after the child finishes write green to mode, run python3 anchor.py and verify exit 0, then write .goals/demo.candidate again. Output PROBE_CORRECTED_GATE_PENDING and finish.
The first red claim is the authorized test stimulus, not a real completion claim. Do not delete or change the anchor, baselines, hooks, or active marker. Do not invoke the hook yourself. Do not create a native goal in this probe.'''
        self.invoke(prompt)
        transport = self.transport()
        starts = [r for r in transport if r['event'] == 'SessionStart' and r['label'] == 'A']
        owner = starts[0]['session_id'] if starts else None
        checks = [e for e in self.events() if e['event'] == 'anchor_checked']
        observations = {"initial_hook_received": bool(checks),
                        "red_claim_corrected": bool(checks) and checks[0]['outcome'] == 'red' and (self.root / 'worker-result').is_file(),
                        "initial_outcomes": [e['outcome'] for e in checks],
                        "initial_stop_callbacks": sum(r['event']=='Stop' and r['label']=='A' for r in transport)}
        if not owner: raise RuntimeError("No native SessionStart identity observed")
        # A second real session shares the directory before the owner's next check.
        candidate = self.root / '.goals/demo.candidate'
        candidate.write_text('owner claim: foreign session must not consume')
        before = (self.root / '.goals/active').read_bytes(), list(self.events())
        self.invoke('Authorized isolated foreign-session probe. Reply exactly FOREIGN_SESSION. Do not use tools or change files.', label='B')
        foreign = [r for r in self.transport() if r['event']=='Stop' and r['label']=='B']
        observations['foreign_session_inert'] = bool(foreign) and all(not r['payload'] for r in foreign) and candidate.exists() and before == ((self.root / '.goals/active').read_bytes(), self.events())
        self.invoke('Resume the existing authorized probe. Read .goals/demo.goal.md Carry-over and the last .goals/demo.events.jsonl measurement. The prepared completion candidate is pending; reply exactly RESUMED_GATE_PENDING and end. Do not change any file or manually call a hook.', label='R', resume=owner)
        checks = [e for e in self.events() if e['event']=='anchor_checked']
        observations['resume_checks_pending_candidate'] = bool(checks) and checks[-1]['outcome']=='green' and not candidate.exists()
        observations['green_allow_ends'] = bool(checks) and checks[-1]['outcome']=='green'
        # Same anchor identity, deliberately timed-out current state.
        (self.root / 'mode').write_text('timeout')
        candidate.write_text('deliberate timed-out check')
        self.invoke('Authorized timeout probe. The completion candidate was prepared by the test. Reply exactly UNVERIFIED_TIMEOUT_EXPECTED and end; do not change files or call the anchor yourself.', label='T', resume=owner)
        checks = [e for e in self.events() if e['event']=='anchor_checked']
        observations['timeout_never_green'] = bool(checks) and checks[-1]['outcome']=='unknown'
        self.invoke(f'Owner explicitly cancels this isolated goal. Run python3 {runner} disarm demo, then reply CANCELED. Do not re-arm, create a candidate or claim completion.', label='C', resume=owner)
        observations['cancel_disarms'] = not (self.root / '.goals/active').exists()
        canceled = [r for r in self.transport() if r['event']=='Stop' and r['label']=='C']
        observations['cancel_stop_inert'] = bool(canceled) and all(not r['payload'] for r in canceled)
        observations['worker_result_before_green'] = observations['red_claim_corrected'] and observations['resume_checks_pending_candidate']
        observations['transport'] = [{k:v for k,v in r.items() if k != 'session_id'} for r in self.transport() if r['event'] in {'Stop','SessionStart','PreCompact'}]
        return observations

    def run_native(self):
        runner = shlex.quote(str(self.scripts / 'goal_run.py'))
        prompt = f'''Authorized isolated native goal and Ultra coexistence test; no commits, installs or external writes. Work only in {self.root}. Ignore the example dependency-upgrade task in the synthetic fixture.
Finish when you have read native-stop-count with value at least 2 and printed NATIVE_CONTINUATION_CONFIRMED with that value. This is a test of native continuation across host turn boundaries. Do not write, delete, or wait/poll on native-stop-count: the host's real Stop callback is its only writer.
On your first turn, read session-G.json and arm demo using python3 {runner} arm demo --session-id <the observed session_id>. This arm tests activation only; do not create .goals/demo.candidate. The red Ultra anchor intentionally remains unverified in this coexistence test.
Each turn read native-stop-count once (missing means 0); if below 2, say NATIVE_CONTINUATION_PENDING and end that response with the native goal still active so the native host can start the next turn. Do not mark the goal blocked or complete while below 2. At 2 or above, report NATIVE_CONTINUATION_CONFIRMED and clearly say ULTRA_UNVERIFIED: native goal completion is not Ultra completion. Stop after at most 4 observed host Stops even if the protocol fails.'''
        result = self.invoke(prompt, label='G', native=True)
        log = self.transport()
        stops = [e for e in log if e['event']=='Stop']
        native_visible = 'NATIVE_CONTINUATION_CONFIRMED' in result.stdout
        native_records = []
        if self.host == 'kimi':
            for path in self.root.glob('kimi-home/sessions/**/*.jsonl'):
                for row in json_lines(path):
                    kind = str(row.get('type', ''))
                    if 'goal' in kind.lower():
                        native_records.append(row)
        native_turns = max((r.get('turnsUsed',0) for r in native_records), default=0)
        return {'native_multiple_turns': native_turns>=3 if self.host=='kimi' else len(stops)>=3,
                'native_completion_separate_from_ultra': native_visible and 'ULTRA_UNVERIFIED' in result.stdout and not any(e['event']=='anchor_checked' for e in self.events()),
                'stop_callbacks':len(stops),
                'native_status_not_an_ultra_pass': not any(e.get('outcome')=='green' for e in self.events()),
                'native_goal_records':native_records,
                'output_tail':result.stdout[-6000:]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host', choices=['claude','codex','kimi','zcode'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--native-goal', action='store_true')
    args = parser.parse_args()
    receipt = {'host': args.host, 'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SCRIPTS.glob('*.py')}}
    with tempfile.TemporaryDirectory(prefix=f'ug-lifecycle-{args.host}-') as directory:
        try:
            probe = Probe(args.host, Path(directory))
            receipt['observations'] = probe.run_native() if args.native_goal else probe.run()
            receipt['ok'] = all(v for v in receipt['observations'].values() if isinstance(v,bool))
        except Exception as exc:
            receipt['ok'] = False
            receipt['error'] = str(exc)
            receipt['observations'] = {'events': probe.events(), 'transport': probe.transport()} if 'probe' in locals() else {}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'host':args.host,'ok':receipt['ok'],'error':receipt.get('error'),'output':str(args.output)}))
    return 0 if receipt['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
