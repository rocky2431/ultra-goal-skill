# Autonomous execution on Codex and Claude Code

The POSIX driver uses the existing goal contract and completion gate. It needs
the installed host hooks, Python 3.10+, and a live host session; it neither calls
a model nor creates a native Goal. Other hosts and Windows retain gate-only use.

## Start and continue

After the accepted goal has passed normal validation and confirmation, use the
current native session ID and the actual host:

```bash
python3 <skill-dir>/scripts/goal_run.py arm <slug> --session-id <native-id> --driver codex
```

Use `--driver claude` on Claude Code. Ordinary Stop now requests continued work
while this bound driver is running. A `verify` pass closes it; an explicit pause,
cancellation, changed frozen terms or a verification ceiling stops continuation.
Do not use native Goal at the same time. Host permissions, interruptions, quotas
and continuation limits remain in force; no driver may bypass them.

## Wait for an actual dependency

Use a command that blocks until the needed result exists: a test/build process,
a service's event wait, or an optional delegation tool's terminal-result wait.
Run this through an ordinary authorized shell tool call, not a hook:

```bash
python3 <skill-dir>/scripts/goal_drive.py wait <slug> --session-id <native-id> \
  --timeout 600 -- python3 build_report.py
```

Arguments after `--` are an executable argument list, with no implicit shell.
For a pipeline supply an explicit shell only when that exact command is authorized.
The driver starts one command, saves its wait ID and paths, and returns promptly.
Save Carry-over, report the pending dependency once, then end the turn. Do not
poll status, repeatedly call wait, or enable native Goal to keep checking.

The worker blocks in an OS wait. No model is called during idle waiting. Its
`result.json` records exit status, timeout or launch failure; `output.log` retains
full output. These are observations, not acceptance or instructions. Read them,
integrate the result, continue authorized work, and call the existing `verify`.

- **Codex:** the independent worker calls `codex queue` once for the original
  bound session. This requires a host that consumes its queue while idle.
  CLI queue acceptance alone does not prove wakeup on another host surface.
- **Claude Code:** the packaged `asyncRewake` Stop hook blocks on the worker's
  file lock, checks current ownership/state, and exits 2 once with the result
  pointer. The session must remain open. One-shot `claude -p` teardown kills
  pending async hooks; use an interactive or persistent streaming session.
  The shipped wake-hook timeout is 24 hours; a wait must finish within that
  session/hook lifetime. Configure a longer hook timeout before a longer wait.

The delivery lock prevents duplicate hook firings from waking for the same event.
Failed or interrupted Codex delivery is recorded as failed/unknown and pauses the
driver. Inspect the original queue and actual execution before any retry; never
blindly repeat a possibly executed command. If a host cannot deliver an event,
report pending delivery explicitly rather than promising autonomous completion.

## Pause, resume, cancel and recover

```bash
python3 <skill-dir>/scripts/goal_drive.py status <slug> --session-id <native-id>
python3 <skill-dir>/scripts/goal_drive.py pause <slug> --session-id <native-id> --reason "Need the owner's choice"
python3 <skill-dir>/scripts/goal_drive.py resume <slug> --session-id <native-id>
python3 <skill-dir>/scripts/goal_run.py disarm <slug>
```

Pause requires a concrete reason; use it for required user input, an observed
blocker, or an explicit owner pause. Resume uses existing owner authorization,
preserves the goal/baselines, and does not replay an interrupted command.
Cancellation invalidates pending delivery before terminating the active wait
process group. Re-arming cannot revive a canceled or completed driver. Native
Codex Interrupt, Claude tool interruption and Claude SessionEnd pause the driver.
Native interruption records a run-bound pause before trying the delivery lock,
so an in-flight queue call cannot consume the short native interruption deadline.
The status command includes this pause even before that delivery settles.

A completion event already queued before cancellation may still be delivered by
the host. Always check the current driver state before acting on it; stale events
must not restart canceled work. Session rebind invalidates the old waiter. After
an authorized rebind, explicitly arm the driver for the new host/session; never
infer transfer from inherited environment variables or a recovered file.

The driver JSON holds only execution phase and transport state. Business progress
remains in the existing goal Carry-over or its selected task record. The event log
and wait result files preserve evidence. Keep them when reporting incomplete work.

## Source basis and verification

Interfaces checked 2026-09-13:
[Codex Stop/Interrupt](https://learn.chatgpt.com/docs/hooks),
[Codex turn/result interface](https://learn.chatgpt.com/docs/app-server#start-a-turn),
[Claude command hooks and asyncRewake](https://code.claude.com/docs/en/hooks).
Local versions: Codex CLI 0.153.4; Claude Code 2.1.270.
Both hosts completed real continuation/wait/wake/verification and cancellation
probes. Claude also completed ten ordinary continuations with actual tool work
before its wait; this does not claim that no-progress loops bypass the host cap.

`tests/test_goal_drive.py` checks selection, ordinary continuation, actual command
waiting, failures/timeouts, one-time delivery and cancellation/rebind suppression.
`tests/probe_autonomous.py` is an opt-in native probe with one initial input and
no native Goal. Its receipts, not unit counts, establish the tested host behavior.
