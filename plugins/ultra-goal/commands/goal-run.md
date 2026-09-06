---
description: Arm the gate and start a run against a goal artifact in .goals/
argument-hint: <slug>
allowed-tools: Bash, Read
---

Start the run for `$ARGUMENTS`.

The main model owns the work loop. This command validates and arms the completion
gate; a Stop hook can ask for a bounded correction, but cannot schedule another
turn or restart a stopped process. Use an available, authorized native goal mode
when the run needs unattended continuation across host turns. Without such a
driver, work within the current turn and report any unfinished run as awaiting
another prompt. Never promise unattended completion from arming alone.

Honor cancellation across both layers. If the owner cancels, stop or clear this
run's native goal using its available native control, then disarm this gate and
preserve the canceled state. Disarming only disables hooks; it does not cancel
a native goal. If the host interrupted execution before these steps could run,
reconcile the owner's cancellation at the next authorized opportunity and never
automatically re-arm or restart it. A pause preserves state and is not completion.

`$ARGUMENTS` is the one argument placeholder every host documents for command bodies:
Claude Code defines it as "all arguments passed when invoking the skill" (its numbered
shorthands count from zero, so a first argument is not what they mean), zCode as
"$ARGUMENTS stands for all user-provided arguments", Kimi as "whatever you type after the
command replaces $ARGUMENTS in the body". The slug below is therefore bound by the host
before you see this text — never guessed.

## 1. Find the artifact

```bash
ls .goals/$ARGUMENTS.goal.md .goals/$ARGUMENTS.decisions.md
```

If either is missing, stop and say so. Do not author one here — that is the interview's
job, and starting a run against an artifact nobody agreed to is the failure this whole
design exists to prevent.

## 2. Validate, then arm - one fence, because they are one step

For an unattended run, check that the independent specification critique actually
happened. If missing, invoke it against the approved terms before arming. Do not
reinterpret "start now" or "do not ask again" as a waiver: this is an independent
check, not another owner interview. A clean critique needs no new confirmation;
a material objection must be resolved. Disclose an explicitly waived or unavailable
critique instead of treating it as a pass.

Before executing the fence, replace `<resolved-native-session-id>` with the current
host's actual native ID from its own command substitution or tool environment. Never
select the first available ID across hosts: even a single variable can belong to a
parent agent. If the identity cannot be established, report the gate inactive.

The fence is a script, not prose in this file: it validates through the
real validator (a function call whose exception is the refusal - nothing to
talk past, no fail-open branch to reach), refuses while another goal is
armed, and records the run's authorized baselines before the marker exists.

```bash
root="${CLAUDE_PLUGIN_ROOT}"
[ -n "$root" ] || root="${ZCODE_PLUGIN_ROOT:-${KIMI_PLUGIN_ROOT:-${PLUGIN_ROOT}}}"
[ -n "$root" ] || root="${KIMI_CODE_HOME:-$HOME/.kimi-code}/plugins/managed/ultra-goal"
runner="$root/skills/ultragoal/scripts/goal_run.py"
if [ ! -f "$runner" ]; then
  printf '%s\n' "ultra-goal: arming refused - no documented plugin root reaches this command, so the artifact cannot be machine-validated, and an unvalidated artifact is one the gate cannot honestly enforce. This is a refusal, not a downgrade. Validate it by hand from the plugin's install root (Kimi manages installs at ${KIMI_CODE_HOME:-$HOME/.kimi-code}/plugins/managed/ultra-goal; Codex at ~/.codex/plugins/cache/<marketplace>/ultra-goal/<version>): python3 <plugin-root>/skills/ultragoal/scripts/validate_artifact.py .goals/$ARGUMENTS.goal.md. Fix what it reports, then either export PLUGIN_ROOT=<plugin-root> for this session's shell and run this command again, or - once it is clean - arm from the install root: cd here and run python3 <plugin-root>/skills/ultragoal/scripts/goal_run.py arm $ARGUMENTS --session-id <current-native-session-id>"
  exit 1
fi
session_id='<resolved-native-session-id>'
if command -v python3 >/dev/null 2>&1; then exec python3 "$runner" arm "$ARGUMENTS" --session-id "$session_id"; else exec python "$runner" arm "$ARGUMENTS" --session-id "$session_id"; fi
```

The script validates before creating any active marker, then records three things: the
frozen spec digest in `.goals/$ARGUMENTS.spec.baseline`, the declared evaluator files'
hashes in `.goals/$ARGUMENTS.verification.baseline`, and the review start revision in
`.goals/$ARGUMENTS.baseline`. Re-arming preserves all of them; another active goal, another
owning session, or an evaluator file that has already moved refuses. A baseline written by
an earlier version of this plugin may also refuse — do not silently rewrite it. Finish the
old run under its original version, or start an explicitly authorized fresh goal. These are
local records, not permission to commit. `.goals/.gitignore` excludes `.work/`, `active`,
and `*.candidate`.

**Bind the initiating session before any hook.** `--session-id` is required for arm
and rebind. The script never guesses from inherited environment variables.
The native command/skill substitutions, where this host expands them, are:

- Claude Code: `${CLAUDE_SESSION_ID}`
- Kimi: `${KIMI_SESSION_ID}`
- zCode: `${ZCODE_SESSION_ID}`
- Codex: read `CODEX_SESSION_ID` from the current tool environment.

Literal, unexpanded placeholders are not identities. Do not choose an ID from a
directory scan or another task. If the current identity cannot be obtained,
arming refuses; the model may continue authorized ordinary work, but must say the
gate is inactive. The marker contains the slug and `session <id>` at creation.
Foreign, identity-less, and legacy unbound hook events are inert. Session IDs
identify ownership; they are not authorization credentials or anti-forgery keys.

After an owner-authorized resume into a *different* native session, explicitly
run `goal_run.py rebind <slug> --session-id <new-id>`. This preserves the frozen
baseline and discards the old session's pending completion claim. Binding history preserves prior executing
sessions so they cannot become independent reviewers merely by transferring the run.
Never rebind a
concurrent unrelated task or automatically reopen an owner-canceled run.

At any explicit start or resume, read `.goals/active` and compare its owner with
the current native identity. If they differ, report that this session is not gated
and use rebind only when recovery into it was authorized. Foreign hooks stay silent
so unrelated tasks are never prompted to take over.

### Continuation driver

When the owner requested unattended work, use the host's existing goal tool or
command if it is available in this session. Preserve its budget and user stop
controls. Point its objective at the artifact and require ordinary tools to read
Carry-over and the last gate measurement before continuing. Host goal completion
is a separate claim: it never replaces Ultra's evidence. If the host only exposes
a user command, give the owner the exact `/goal` handoff; do not invent a model
tool or launch a second agent process as a hidden driver. An accepted manual run
needs no extra goal activation. If a driver ends, report the unmet condition and
leave resumable state instead of calling the goal completed.

## 3. Read the spec, then work

Read `.goals/$ARGUMENTS.goal.md` in full. Frozen: `## Intent`, `## Boundary`,
`## Anchor`, `## Stop condition`, `## Verification`, the wording of every `## Acceptance`
requirement, and each labelled `## Means` bullet. If one of them turns out to be wrong, stop
and write a row under `## Challenges from the run` in the decisions record rather than
editing it. You may raise a challenge; you may not edit the term or treat your own challenge
as an owner's ruling — a moved goalpost closes the run and disarms the gate, and only the
owner reopens. Checkbox state is yours to move; the requirement's sentence is not.

Inside those terms you choose the method, the ordering, the tools and the workers, and you
may drop a `[droppable]` means or use a `fallback:` that `## Roles` already authorizes —
each costs one row in the decisions record naming the evidence. **A row records what you
did; it never authorizes less.** Never write one that lowers a threshold, raises a budget,
retires an acceptance requirement or makes a required review optional.

Then follow `## Roles` for who does what this turn, `## Acceptance` for what is still not
true, and `### Next` for the one objective this round is aimed at.

When choosing a worker, fallback or feedback channel, read
[agent-modes.md](../skills/ultragoal/references/agent-modes.md). Another installed Skill
is not required; choose a callable path that preserves the accepted verification terms.

**The evaluator is pinned.** Arming recorded the files `## Verification` names under
`protected` into `.goals/$ARGUMENTS.verification.baseline`. Do not edit them: the gate
compares before and after the anchor runs, and a changed checker refuses the claim instead
of passing it. If one of them genuinely has to change, that is a challenge, not an edit.

**Results are made visible before the Stop, not after.** An allow from the gate carries
no model context — on Claude Code an injected "one more thing" would keep the turn
alive instead of ending it, so the gate stopped carrying one — and the next injectable
event is best-effort recovery that some turns never fire. That makes two habits
load-bearing, and they are yours, not the hook's:

- After a relevant change, when you need feedback or are preparing completion, run the
  applicable verification with ordinary tools — the tests this change touches, the real
  path this change claims to fix. Not the full suite every iteration: the applicable
  check for the change at hand.
- Before you end any turn: make this turn's important results visible in the ordinary
  tool output above, and write the durable state — `## Carry-over` rewritten, `### Next`
  re-aimed, the current evidence saved. Commit only when existing owner authorization covers
  it. What is only in your context when the turn ends is gone.

When you invoke a reviewer or critic, **the round's evidence is the file the role was
told to write** — never the call's
exit status. A delegation can return success and produce nothing; it happened to a review
round on this project, and no hook can see it, because the failure event fires on
failures only. So check the file exists before you treat the round as done: if it is
absent, the round did not happen — fall back as `## Roles` declares and say the round ran
degraded in your report. A review that returned success and left nothing is a missing
review, not a pass. **Wait for every writer you invoked to finish before you request the
required review or claim completion**, and request a fresh review after you change its
inputs — a receipt bound to inputs you have since edited is stale, and the gate reads it
as such. A turn ending proves nothing about a worker.

**A failed delegation is an observation, not a blocker.** It stays in the audit, and on the
hosts that fire `PostToolUseFailure` a hook records it. It does not hold your claim open
until that particular target recovers: what settles the claim is the current required
output and the current review evidence, which an authorized fallback may produce. Report
the failure, name the fallback you used, and never let the absence of a block read as a
round that went fine.

**Where `## Verification` names a required review**, the receipt is written by the
independent verifier at the declared path — not by you, and not from your account of the
work. It carries the verifier's approved identity, that verifier's own native session ID
(distinct from this run's), the input digest it obtained itself with
`goal_run.py review-inputs $ARGUMENTS --root <project>`, the acceptance IDs it covers, its
verdict and its evidence. Prior bound execution sessions are also excluded. A detailed markdown report alongside it is welcome; it is not the
receipt. Never manufacture a passing receipt for a review that did not happen — the gate
checks the declared identity, session, digest, coverage and verdict. A receipt naming
the generating session refuses; these writable fields do not authenticate the writer.

**You are the run, not its designer.** The terms were agreed before you started; do not
reopen them as an interview.

At the start of each turn, state which turn you are on, which `## Acceptance` lines this
turn is for, and what output would prove them — before changing anything.

## Claiming completion

You have not met this goal until the anchor says so on the current state — and the
anchor's verdict at completion belongs to the gate, not to you. So when you believe the
goal is met:

1. Finish the deliverables and Carry-over, join all writers, and obtain any required
   independent review of the final inputs. Its receipt needs `checks` for each
   acceptance ID assigned to review, with concrete claims and actual input quotes.
2. Call `goal_run.py verify $ARGUMENTS --root <project> --session-id <current-native-session-id>
   --claim "<acceptance IDs and evidence>"` using the resolved installed script path.
   It consumes a completion candidate through the same gate and returns JSON before
   your final response. Exit 0 requires a newly recorded `verification_passed: true`.
3. Read that observation. On success, reconcile the native goal with its actual tool
   and deliver the result paths, measured attempt and limits. On failure, use the
   evidence to continue within the remaining budget or report a precise unmet exit.
   Do not edit reviewed outputs after the check; edits require review and verification again.

The gate consumes the claim, checks the verification contract — the pinned evaluator files
and any required review receipt — executes the anchor once against the current state,
re-checks that contract afterwards, and rules on that measurement alone. A pass means the
accepted checks held on this state: the anchor exited 0 and every required review passed on
the current inputs. It does not mean the specification was right, so report the attempt
number, the exit code, and what those checks do not cover. Red refuses the claim and the
turn continues; so does a changed evaluator file or a missing, stale, declaring the generating session, or failing
required review. A historical green is never a pass input: new work and a new claim are
re-measured, always.

`verify` is an ordinary tool call, not a fabricated Stop and not a scheduler. The
following ordinary Stop does not run the consumed candidate again. If only the
Stop path is available, write `.goals/$ARGUMENTS.candidate` with the claim and end
the turn; in that fallback a gate decision arrives after the response. An allow gives
no new model turn. Do not promise to read or commit that future measurement in
the response you are ending: report the ordinary-tool evidence and say the gate
check is pending. At the next actual model opportunity, read the event log and
reconcile the result. On a host that permits only one blocking Stop, a corrected
candidate may remain unchecked until another native turn: keep it pending and
never infer success from the host ending.

For a long coding run with commit authority, commit each checkable work unit before
starting the next: an implementation, experiment, dispatch preparation or ruling,
not each tool call. Use `goal(<slug>) step: <summary>` and the work-record fields in
[document-system.md](../skills/ultragoal/references/document-system.md#work-step-records).
Include actual product writers' native session IDs, including delegated writers;
they cannot later sign the independent review. A failed experiment can be a useful
recorded step: report its actual failure and unfinished work instead of calling it green.
Run `validate_artifact.py .goals --audit` before handoff and resolve missing step
fields/evidence. Inspect unrelated historical findings against their actual evidence.

The optional audit convention for an already observed completion attempt remains
`goal(<slug>) turn <N>: <summary> [anchor: green|red|unknown]`.
Legacy ordinary commits may use `goal(<slug>): <summary>`; they do not assert the
step-record contract. Without Git or commit authority, preserve necessary evidence
and Carry-over in their existing homes and disclose the missing Git history. Never
manufacture a commit or permission to make an audit look complete.

When you report how the run stands, use the disposition vocabulary and nothing looser:
`in_progress`, `input_required` (you lack something only the owner can give),
`blocked_retryable` (a failure that time or a retry can clear), `budget_exhausted` (the
ceiling or the denial bound is spent), `unachievable` (only with independent evidence
that the goal contradicts its frozen terms — a feeling of impossibility is
`in_progress` with a challenge row), `completed`, `canceled`. The anchor's colour is a
different axis: green, red and unknown are what one command did, not what the run is.

## To stop

```bash
root="${CLAUDE_PLUGIN_ROOT}"
[ -n "$root" ] || root="${ZCODE_PLUGIN_ROOT:-${KIMI_PLUGIN_ROOT:-${PLUGIN_ROOT}}}"
[ -n "$root" ] || root="${KIMI_CODE_HOME:-$HOME/.kimi-code}/plugins/managed/ultra-goal"
python3 "$root/skills/ultragoal/scripts/goal_run.py" disarm $ARGUMENTS
```

That disarms the gate without needing the agent's cooperation: the checked
removal of the marker (and any pending candidate), with the slug verified
against the marker's slug line - the same escape hatch `LOOP` never had.
Nothing in this plugin runs again until the marker returns; the events log
and both baselines stay for audit, and a deliberate fresh start removes them
by hand before the next `arm`. `rm .goals/active` remains the owner's
manual hatch when even the fence is out of reach.
