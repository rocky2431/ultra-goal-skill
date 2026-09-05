# Host hooks and lifecycle limits

Read this when checking the current host or diagnosing a hook/lifecycle result.
The [goal contract](goal-contract.md) owns what establishes completion;
[goal-run](../../../commands/goal-run.md) owns the execution procedure. A hook
registering successfully does not prove that a real host called it or honored its
output. Use the host's current reference and a permitted lifecycle probe.

A legacy marker without a valid session binding remains inactive. On Stop, the
shared entry emits an allowing `systemMessage` diagnostic with explicit recovery
guidance; it does not invoke a handler, consume a candidate or change files. Other
events remain inert. A host UI may hide allowing messages; inspect raw hook output
when needed. Bound foreign sessions remain silent. See the README troubleshooting
section for `rebind` versus disarm/arm recovery; never erase history to hide drift.

## Events and their scope

The union of the installed manifests contains seven hooks. Each host registers
only the events whose input/output contract it supports.

| Hook | Observes or delivers | Can block? |
|---|---|---|
| `Stop` | Judges an explicit completion candidate; ordinary stops only get a bounded omission notice | A refusable claim, within the gate's denial bound |
| `SessionStart` | Restores the active specification and carried state on supported session boundaries | No; not registered on Kimi, where the event cannot inject context |
| `PreCompact` | Records carried state and the observed context transition | No; not registered on zCode, whose compact recovery uses `SessionStart` |
| `PostToolUseFailure` | Records `role_unavailable` for a recognized failed delegation call | No; Codex documents no such event |
| `PostToolUse` | Records `role_recovered` for a later successful call to the same target | No; not registered on Codex, which records no matching failure |
| `UserPromptSubmit` | Kimi only: supplies a fixed-size goal pointer and last recorded gate decision | No; a prompt is not every possible host turn |
| `TurnStarted` | Kimi only: records `turn_id` and `origin_kind` for each host turn, whatever its origin | No; it establishes a turn boundary, not recovery or goal success |

Delegation detection recognizes a direct `agent-delegate run --to <target>` or a
structured call to that exact tool. Search strings, output text, opaque scripts
and compound shell commands are not transport evidence. Even a recognized success
does not prove the worker finished or produced its required result. Read
[agent-modes.md](agent-modes.md) before relying on a fallback or join.

## A completion check is not a continuation service

**The anchor runs at exactly one moment: a completion candidate.** `verify`
requests that check through an ordinary tool call so the model can read its actual
recorded result before final delivery. The candidate-file Stop path is the
fallback. Ordinary Stop means the host turn ended: it does not run the anchor or
consume an attempt, and it never proves the goal is complete.

**Three outcomes, not two.** The anchor can be `green`, `red` or `unknown`.
Missing commands, execution errors and timeouts are unknown observations, not
proof of an incorrect product. Contract verification also requires the current
frozen specification, protected evaluator inputs and any required review.
A historical green is never a pass input.

**Nearly every path lets the turn end.** A red anchor or unmet verification
contract may deny a refusable claim. Ordinary stops, unavailable observations,
spent bounds and frozen-spec closure end with their limits stated. Letting a turn
end is not a successful verification. A changed specification closes the run;
the agent cannot rebaseline it by writing a decisions row.

The owner's completion-attempt ceiling and the gate's consecutive-denial budget
are distinct. Neither is a token budget or a native turn limit. On the measured
Claude Code 2.1.260 surface the host's cap counted consecutive blocks since tool
progress, not blocks per turn. The plugin's bounds therefore do not claim that
the four hosts count alike. zCode exposes neither a readable chain flag nor a turn
identity; a chain without an observed reset can carry its tail into a later turn.
Treat that as a declared limitation rather than inventing a proxy turn boundary.

**Two axes, never conflated:**

| Axis | Values | Source |
|---|---|---|
| Anchor observation | `green`, `red`, `unknown` | The measured command and state |
| Run disposition | `in_progress`, `input_required`, `blocked_retryable`, `budget_exhausted`, `unachievable`, `completed`, `canceled` | The run's evidence-backed report |

For example, an anchor exit 1 alone cannot establish that a goal is unachievable.
That needs independent evidence of permanent impossibility under the frozen
terms. An unavailable service is normally retryable; a spent budget is exhausted.
The disposition vocabulary does not add another mechanical completion oracle.

## Output is host-specific

An allow carries no added model context. On the measured Claude Code 2.1.260
surface, `additionalContext` on an allowing Stop re-entered the model instead of
ending the turn. Make results visible with ordinary tools and save durable state
before ending. A future injectable event is best-effort recovery, not something
the preceding final response can claim to have read.

The denial channel is also specific to the requesting host:

| Host | Denial shape |
|---|---|
| Claude Code, Codex, zCode | Top-level `decision: "block"` and `reason` |
| Kimi | `hookSpecificOutput.permissionDecision` and its reason |

In the paired Codex 0.150.1 probe, a mixed payload that also included nested
`permissionDecision` was inert; Kimi 0.40.1 ignored the top-level pair. Keep one
allowlisted shape per host. The reason must carry the facts the denied turn needs.
These versions identify observations; consult the current reference before
porting the protocol to a new host surface.

The deny reason points to mutable State, Lessons and Next and reports open
acceptance claims. It must not invite editing frozen terms. A hook inlines only
what it alone possesses; already available file bodies get paths. See
[document-system.md](document-system.md) for context and evidence ownership.

## Ownership and escape

Arming binds `.goals/active` to the slug and current native `session <id>` before
any hook can run. `--session-id` is required for arm and rebind; inherited
environment variables may belong to a parent, and the first Stop cannot claim an
unowned run. Resolve the host's actual identity using the run procedure.

Foreign, identity-less and legacy unbound hooks are inert. At an explicit start
or resume, compare the marker to this session and report a mismatch. Use
`goal_run.py rebind <slug> --session-id <new-id>` only for an authorized recovery.
It transfers ownership, preserves frozen baselines and discards the old pending
claim; it does not renew authority, budgets or canceled work.

**A session id is identity, not an anti-forgery key.** Shared writable files can
be forged. Binding prevents accidental first-Stop ownership, not hostile access.
[zero-trust.md](zero-trust.md) names the boundary stronger tasks require.

Without an active goal, hooks take their early-exit path. An unsupported event
provides no coverage. If a hook cannot decide, it lets the host continue without
claiming success. `rm .goals/active` or `ULTRA_GOAL_HOOKS_DISABLED=1` disables this
gate; neither cancels a host-native goal. Use the native cancellation control as
well when the owner cancels execution.

## Scope of the available evidence

Version 2.12.0 has macOS real-host probes for candidate correction, green release,
foreign-session isolation, resume, timeout and cancellation on the four target
hosts. Native continuation was measured separately: Codex app-server and
CC/Kimi/zCode native goal commands. Do not infer the same goal service exists in
`codex exec`, or that these observations prove every later release.

Isolated hook probes do not establish native plugin discovery. A child-process
join probe does not certify arbitrary LLM worker teams. Native goal completion is
not an Ultra pass; a corrected Kimi candidate can wait for a later real Stop.
Windows is unverified: `commandWindows` checks are structural, not a Windows
lifecycle. Finite probes do not establish a statistical 95% reliability claim.
