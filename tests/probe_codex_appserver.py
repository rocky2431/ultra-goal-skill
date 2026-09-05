#!/usr/bin/env python3
"""Opt-in, bounded real app-server goal/compaction acceptance client.

No follow-up turn is submitted during the native goal phase. Auth and native
session state exist only in a private temporary CODEX_HOME, removed on exit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import queue
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from probe_host_lifecycle import Probe


class Client:
    def __init__(self, probe, home):
        self.messages = queue.Queue()
        self.observed = []
        self.request_id = 0
        self.deadline = time.monotonic() + 540
        self.proc = subprocess.Popen(
            [shutil.which('codex'), 'app-server', '--stdio', '--enable', 'goals',
             '-c', 'bypass_hook_trust=true'], cwd=probe.root,
            env={**probe.env, 'CODEX_HOME': str(home), 'UG_PROBE_LABEL': 'G'},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1)
        threading.Thread(target=self.read, daemon=True).start()

    def read(self):
        for line in self.proc.stdout:
            try:
                self.messages.put(json.loads(line))
            except ValueError:
                self.messages.put({'invalid_json': True})
        self.messages.put({'closed': True})

    def send(self, message):
        self.proc.stdin.write(json.dumps(message) + '\n')
        self.proc.stdin.flush()

    def receive(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('App-server acceptance exceeded 540 seconds')
        try:
            message = self.messages.get(timeout=remaining)
        except queue.Empty:
            raise TimeoutError('App-server acceptance exceeded 540 seconds') from None
        if message.get('closed') or message.get('invalid_json'):
            raise RuntimeError('App-server closed or emitted invalid JSON')
        if 'id' in message and 'method' in message:
            raise RuntimeError('Unexpected server request: ' + message['method'])
        method = message.get('method', '')
        if method in {'turn/started', 'turn/completed', 'thread/goal/updated',
                      'thread/goal/cleared', 'thread/compacted', 'error'}:
            self.observed.append(message)
        if method == 'item/completed':
            item = message.get('params', {}).get('item', {})
            if item.get('type') in {'agentMessage', 'contextCompaction'}:
                self.observed.append(message)
        return message

    def request(self, method, params):
        self.request_id += 1
        request_id = self.request_id
        self.send({'id': request_id, 'method': method, 'params': params})
        while True:
            message = self.receive()
            if message.get('id') == request_id:
                if 'error' in message:
                    raise RuntimeError(f'{method}: {message["error"]}')
                return message.get('result', {})

    def until(self, predicate):
        while not predicate(self.observed):
            self.receive()

    def close(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()


def final_messages(records):
    return [row['params']['item'].get('text', '') for row in records
            if row.get('method') == 'item/completed'
            and row['params']['item'].get('type') == 'agentMessage']


def run(probe, client, result):
    client.request('initialize', {'clientInfo': {'name': 'ultra-goal-probe', 'version': '1.0'},
                                 'capabilities': {'experimentalApi': True}})
    client.send({'method': 'initialized', 'params': {}})
    hooks = {event: [{'hooks': [probe.hook(event)]}]
             for event in ('SessionStart', 'Stop', 'PreCompact')}
    thread = client.request('thread/start', {
        'cwd': str(probe.root), 'approvalPolicy': 'never', 'sandbox': 'danger-full-access',
        'config': {'hooks': hooks, 'bypass_hook_trust': True, 'model_reasoning_effort': 'low'},
        'developerInstructions': 'This is an authorized isolated acceptance probe. '
        'Use tools only in the current temporary workspace. Do not commit, install, '
        'modify authentication/configuration, or contact external services yourself. '
        'When asked for a native goal, use the native goal tools to update its status. '
        'Follow the concrete probe objective rather than the synthetic goal template example.'})
    thread_id = thread['thread']['id']
    result['model'] = thread.get('model')
    runner = shlex.quote(str(probe.scripts / 'goal_run.py'))
    objective = f'''Authorized native continuation probe in {probe.root}.
Read native-stop-count exactly once per turn (missing means 0). Do not modify this file,
poll, wait, or manually invoke a hook; only real native Stop callbacks write it.
On the first turn, read session-G.json and arm demo with
{shlex.quote(sys.executable)} {runner} arm demo --session-id <its session_id>.
Leave the red anchor and .goals/demo.candidate absent; this tests coexistence, not Ultra success.
If count is below 2, report NATIVE_CONTINUATION_PENDING and finish the turn while keeping
the native goal active. The native service must start subsequent turns without another user prompt.
When count is at least 2, report NATIVE_CONTINUATION_CONFIRMED and ULTRA_UNVERIFIED,
then call update_goal complete. Native goal completion is not an Ultra anchor pass.
Stop after 4 observed Stop callbacks if this protocol cannot be completed.'''
    native = client.request('thread/goal/set', {'threadId': thread_id,
                                               'objective': objective, 'status': 'active'})
    result['native_goal_created'] = native.get('goal', {}).get('status') == 'active'
    # GoalService.apply_external_goal_set calls continue_if_idle itself.
    client.until(lambda rows: any(row['method'] == 'thread/goal/updated'
                 and row['params'].get('goal', {}).get('status') in
                 {'complete', 'blocked', 'paused', 'budgetLimited', 'usageLimited'} for row in rows))
    client.until(lambda rows: sum(row['method'] == 'turn/completed' for row in rows)
                 >= sum(row['method'] == 'turn/started' for row in rows))
    current = client.request('thread/goal/get', {'threadId': thread_id})
    native_records = list(client.observed)
    native_text = '\n'.join(final_messages(native_records))
    result.update({
        'native_status': current.get('goal', {}).get('status'),
        'native_turns_completed': sum(row['method'] == 'turn/completed' for row in native_records),
        'native_turns_started': sum(row['method'] == 'turn/started' for row in native_records),
        'native_driver_followup_prompts': 0,
        'native_multiple_turns': sum(row['method'] == 'turn/completed' for row in native_records) >= 3,
        'native_completion_separate_from_ultra': 'NATIVE_CONTINUATION_CONFIRMED' in native_text
            and 'ULTRA_UNVERIFIED' in native_text
            and not any(row['event'] == 'anchor_checked' for row in probe.events()),
        'native_output': native_text[-4000:],
    })
    if result['native_status'] != 'complete':
        return
    # Seed the mutable carry-over with a fresh disk-only fact, then compact through
    # the real RPC. The recovery prompt does not disclose this token.
    marker = 'RECOVERY_' + hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:16]
    path = probe.root / '.goals/demo.goal.md'
    spec = path.read_text().replace('### State\n', '### State\n\n- Probe recovery token: ' + marker + '\n', 1)
    path.write_text(spec)
    before = len(client.observed)
    client.request('thread/compact/start', {'threadId': thread_id})
    client.until(lambda rows: any(row.get('method') == 'item/completed'
                 and row.get('params', {}).get('item', {}).get('type') == 'contextCompaction'
                 for row in rows[before:]))
    result['native_compaction_completed'] = True
    result['precompact_hook_recorded'] = any(row['event'] == 'pre_compact' for row in probe.events())
    before = len(client.observed)
    recovery_turn = client.request('turn/start', {'threadId': thread_id, 'input': [{'type': 'text', 'text':
        'Continue this isolated recovery test after compaction. Read .goals/demo.goal.md '
        'Carry-over from disk and report its exact probe recovery token. Say '
        'ULTRA_UNVERIFIED because there is no anchor pass. Do not modify files.'}]})
    recovery_turn_id = recovery_turn['turn']['id']
    client.until(lambda rows: any(row['method'] == 'turn/completed'
                 and row.get('params', {}).get('turn', {}).get('id') == recovery_turn_id
                 for row in rows[before:]))
    recovery = '\n'.join(final_messages(client.observed[before:]))
    result['compaction_recovers_fresh_disk_state'] = marker in recovery
    result['compaction_output'] = recovery[-2000:]
    result['compact_sessionstart_injection'] = any(row['event'] == 'SessionStart'
        and row.get('source') == 'compact' and bool(row['payload']) for row in probe.transport())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {'host': 'codex-app-server', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'cli_version': subprocess.check_output(['codex', '--version'], text=True).strip()}
    with tempfile.TemporaryDirectory(prefix='ultra-goal-appserver-') as directory:
        root = Path(directory)
        home = root / 'codex-home'
        home.mkdir(mode=0o700)
        shutil.copy2(Path.home() / '.codex/auth.json', home / 'auth.json')
        (home / 'auth.json').chmod(0o600)
        probe = Probe('codex', root)
        result['source_sha256'] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                   for path in sorted(probe.scripts.glob('*.py'))}
        client = Client(probe, home)
        try:
            run(probe, client, result)
        except Exception as error:
            result['error'] = f'{type(error).__name__}: {error}'
        finally:
            client.close()
            result['observed_method_counts'] = {method: sum(row['method'] == method for row in client.observed)
                                                for method in sorted({row['method'] for row in client.observed})}
            result['agent_output_tail'] = '\n'.join(final_messages(client.observed))[-4000:]
            result['hook_events'] = [{key: value for key, value in row.items() if key != 'session_id'}
                                     for row in probe.transport()]
            result['ultra_events'] = [{key: value for key, value in row.items() if key != 'session_id'}
                                      for row in probe.events()]
            result['pass'] = all(result.get(key) for key in (
                'native_goal_created', 'native_multiple_turns', 'native_completion_separate_from_ultra',
                'native_compaction_completed', 'precompact_hook_recorded', 'compaction_recovers_fresh_disk_state',
                'compact_sessionstart_injection'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key not in {
        'hook_events', 'source_sha256', 'agent_output_tail', 'ultra_events', 'native_output', 'compaction_output'}}))
    return 0 if result['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
