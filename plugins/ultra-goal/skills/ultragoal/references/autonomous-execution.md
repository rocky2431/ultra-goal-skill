# Autonomous execution on Codex, Claude Code and Grok Build

The POSIX driver uses the existing goal contract and completion gate. It needs
the installed host hooks, Python 3.10+, and a live host session; it neither calls
a model nor creates a native Goal. Other hosts and Windows retain gate-only use.

## Start and continue

After the accepted goal has passed normal validation and confirmation, use the
current native session ID and the actual host:

```bash
python3 <skill-dir>/scripts/goal_run.py arm <slug> --session-id <native-id> --driver codex
```

Use `--driver claude` on Claude Code or `--driver grok` on Grok Build. Ordinary Stop now requests continued work
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
The driver starts one command and saves its wait ID and paths. On Grok, run this
CLI through `run_terminal_command` with `block_until_ms: 0`: the CLI stays attached
to the native background task until the worker finishes. On other supported hosts
it returns promptly and the host's observer delivers completion.
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
- **Grok Build:** native background-command completion wakes the idle session.
  The attached CLI waits on the same worker lock and returns one result pointer.
  Do not detach it with `&`, poll command output, or substitute a scheduler loop.
  Grok permits eight Stop continuations per turn. Before that limit, the hook
  supplies a `goal_drive.py yield ... --turn-id <current-id>` command to run with
  `block_until_ms: 0`. It blocks on an OS pipe until this session's Stop event,
  then its native completion starts a fresh turn. This is one event-driven
  handoff, with the same goal, ownership and cancellation checks. If that handoff
  is not performed, the guard pauses before the host silently forces a stop.

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
Codex Interrupt, Claude tool interruption/SessionEnd, and Grok
StopCancelled/StopFailure/SessionEnd pause the driver.
Native interruption records a run-bound pause before trying the delivery lock,
so an in-flight queue call cannot consume the short native interruption deadline.
The status command includes this pause even before that delivery settles.

A completion event already queued before cancellation may still be delivered by
the host. Always check the current driver state before acting on it; stale events
must not restart canceled work. Session rebind invalidates the old waiter. After
an authorized rebind, explicitly arm the driver for the new host/session; never
infer transfer from inherited environment variables or a recovered file.

Grok uses camelCase event identities and emits an additional observe-only Stop
at teardown; the native adapter accepts only `reason: end_turn` as a Stop gate.
SessionStart and PostCompact mark recovery pending. Their output is ignored by
Grok, so the bound contract pointer and last decision arrive with the next
PostToolUse result. Read the contract before further work; recovery never resumes
a paused, canceled or completed driver. A transcript without tool use receives
no PostToolUse context. Use the loaded Skill directly when such context is needed.

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

Grok interfaces checked 2026-10-14 against the official
[hook contract](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/10-hooks.md).
Grok 1.0.52 with the real user configuration completed ordinary Stop continuation,
native background wait, idle wakeup and protected-anchor verification in one
275.395s probe, with one initial prompt and no TLS retries. Native cancellation
was checked after its asynchronous StopCancelled hook finished, not merely after
the ACP canceled response. Package/unit checks alone do not establish these events.
An additional single-prompt probe completed a Stop-released turn handoff and
verification. Native session/load and compact_conversation probes delivered the
current recovery context while keeping the interrupted goal paused. These probes
used the candidate native plugin manifests with the existing authentication,
model, MCP and Hindsight configuration; no isolated HOME was substituted.

`tests/test_goal_drive.py` checks selection, ordinary continuation, actual command
waiting, failures/timeouts, one-time delivery and cancellation/rebind suppression.
`tests/probe_autonomous.py` is an opt-in native probe with one initial input and
no native Goal. Its receipts, not unit counts, establish the tested host behavior.
