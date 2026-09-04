# Codex adversarial review — round 2

Review object: `912bab3..HEAD` (`1ad2d64` through `62b930f`), four
implementation commits plus zCode's round-2 report. Review date: 2026-09-04.
I did not read mission §8.1 until after recording the blind suite verdict, and
I did not read Claude Code's round-2 report.

## Blind suite verdict

The first run was contaminated by this review's recovery file: its temporary
machine-specific path correctly tripped the repository hygiene test, producing
`1 failed, 346 passed in 43.53s`. After making that state repository-relative,
the implementation baseline was green:

```console
$ pytest -q
347 passed in 26.87s
```

Round 1 had 332 tests, so this range adds 15. This verdict was written to
`work/task-state.md` before §8.1 was opened.

## Verdict

**Request changes (provisional while the remaining axes are checked).** Codex
F2 is not closed: the hook observes a user-prompt event, then infers that this
is the host-turn boundary. Kimi exposes the actual boundary as `TurnStarted`
with `turn_id`, and not every turn has user origin.

_If this turn is cancelled again, the remaining sections are partial evidence
rather than a completed review._

## Finding closure

### Codex F1 — OPEN (P1): slug binding is fixed, but Kimi now arms without validation

**Location:** `plugins/ultra-goal/commands/goal-run.md:31-47` and
`:49-55`; the incomplete regression is
`tests/test_package_surface.py:1880-1897`.

Replacing `$1` with `$ARGUMENTS` closes the command-expansion half. The three
focused tests pass, and the current OpenAI custom-prompt reference also defines
`$ARGUMENTS` as all positional arguments:

```console
$ pytest -q tests/test_package_surface.py::AuditFixTests::test_the_command_binds_the_slug_through_the_documented_placeholder tests/test_package_surface.py::AuditFixTests::test_the_validator_step_degrades_loudly_when_no_root_reaches_it tests/test_package_surface.py::ArmingRangeContractTests::test_the_expanded_prompt_binds_the_slug_end_to_end
3 passed in 0.32s
```

But F1's settlement required the intended artifact to be validated before
`.goals/active` was written. The new `else` explicitly says "Arming
continues" when no root reaches command execution. Driving the real fenced
commands with an invalid artifact proves the hard precondition is now
fail-open:

```console
$ python3 -c 'import sys,tempfile; from pathlib import Path; sys.path.insert(0,"tests"); from test_package_surface import ArmingRangeContractTests as T; t=T(); text=t.command_text().replace("$ARGUMENTS","demo"); fs=t.fences(text); td=tempfile.TemporaryDirectory(); cwd=Path(td.name); (cwd/".goals").mkdir(); (cwd/".goals/demo.goal.md").write_text("invalid\n"); (cwd/".goals/demo.decisions.md").write_text("invalid\n"); v=t.run_sh(next(f for f in fs if "validator=" in f),cwd); t.run_sh(next(f for f in fs if "baseline" in f),cwd); print("validate_exit=",v.returncode); print(v.stdout.strip()); print("armed=",(cwd/".goals/active").read_text().strip()); td.cleanup()'
validate_exit= 0
ultra-goal: the validator is unreachable ... Arming continues ...
armed= demo
```

The alleged end-to-end regression executes only the arming fence; it never
runs validation or asserts that an invalid artifact cannot arm. A loud note in
the run's later report is not equivalent to the pre-arm validator: until the
first Stop, an artifact with no enforceable anchor or boundary is active. F1 is
closed only when Kimi has a real validation path, or when unreachable
validation refuses to arm rather than converting a hard gate into a declared
downgrade.

### Codex F2 — OPEN (P1): prompt submission is still an inferred turn boundary

**Location:** `plugins/ultra-goal/skills/ultra-goal/scripts/goal_prompt_submit.py:13-20`,
`plugins/ultra-goal/skills/ultra-goal/scripts/goal_stop.py:436-470`, and
`plugins/ultra-goal/kimi.plugin.json:20-40`.

The new fact is a `prompt_submitted` row written when this plugin's
`UserPromptSubmit` hook runs. The invocation is observable; the equivalence
"user prompt = new host turn" is inferred. Kimi's official event reference
separates the two: `UserPromptSubmit` means a user sent a message, while
`TurnStarted` fires for every new turn, exposes `turn_id`, and names `user`,
`task`, and `system_trigger` origins. The manifest does not register it.

```console
$ curl -fsS https://moonshotai.github.io/kimi-code/en/customization/hooks.md | rg -n -A 18 '## Event Reference|UserPromptSubmit|TurnStarted'
108:| `UserPromptSubmit` ... Triggered when the user sends a message ...
112:| `TurnStarted` ... `user`, `task`, `system_trigger` ... Triggered when a new turn begins; payload includes `turn_id` ...
```

The installed 0.40.1 binary implements that exact event rather than merely
documenting it:

```console
$ strings -a ~/.kimi-code/bin/kimi | sed -n '721575,721625p'
this._register(this.eventBus.subscribe(TurnStarted, (e) => this.notifyTurnStarted(e)));
this.fireAndForget("TurnStarted", {
turnId: event.turnId,
originKind: event.origin.kind,
...
```

The lifecycle counterexample remains. Without the synthetic prompt proxy,
two Stop invocations are indistinguishable to the gate and alternate
block/allow; inserting the proxy alone resets the budget:

```console
$ python3 -c 'import sys; sys.path.insert(0,"tests"); from test_goal_hooks import ContinuationBudgetTests as T; t=T(); t.setUp(); a=t.turn(host="kimi"); b=t.turn(host="kimi"); t.prompt(); c=t.turn(host="kimi"); print("no-observed-boundary=",[t.decision(a),t.decision(b)]); print("with-prompt-proxy=",t.decision(c)); t.tearDown()'
no-observed-boundary= ['block', None]
with-prompt-proxy= block
```

`test_two_fresh_kimi_turns_each_get_their_one_block` proves how the code reacts
after the test itself inserts `prompt_submitted`; it does not prove that row is
the host's turn boundary. A fresh task/system-triggered turn, or any other
fresh turn without a user submission, can still inherit the persistent log's
tail and arrive with its one-block budget already spent. Closure requires the
host's `TurnStarted.turn_id` (or another host-provided turn identity), plus a
regression with a non-user-origin turn.

_The remaining F1/F3-F6 and Claude findings are still under verification._

## New regressions

_Pending range audit._

## Dimensions exercised

| Dimension | Command | Result |
|---|---|---|
| Full executable suite, blind | `pytest -q` | `347 passed in 26.87s` after removing task-state-only hygiene interference. |

## Boundary and unverified work

- No implementation change, install, push, publication or deployment was performed.
- No host plugin was installed for this review; live four-host lifecycle acceptance remains outside the granted effects.
