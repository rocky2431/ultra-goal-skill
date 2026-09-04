# Codex Review — Host Adaptation Round 4

## Scope and authority

- Review object: `073a801..af56863` on `host-adaptation` (implementation commits `dc76c87..ed72ced`, probe receipts `038b10b`, and zCode report `af56863`).
- Requested review range for regression analysis: `97d0780..af56863`.
- Review only. No fixes, merge, push, install, or publish.

## Blind suite verdict

Recorded before opening `docs/wip/mission-host-adaptation.md` §8.1.

Command:

```text
/opt/anaconda3/bin/pytest -q
```

Observed output (exit 0):

```text
........................................................................ [ 18%]
........................................................................ [ 36%]
........................................................................ [ 54%]
........................................................................ [ 73%]
........................................................................ [ 91%]
..................................                                       [100%]
394 passed in 26.60s
```

Blind verdict: **PASS**. The current suite is green and collects 36 more passing tests than the round-3 close (358). This proves only the checked test surface; host-positive controls and the contract review remain open below.

## Findings

### F1 — P1 — Phase 0 did not close the launch-path exit-2 defect on the shipped Windows commands

`plugins/ultra-goal/hooks/hooks.json:11,25,39` and
`plugins/ultra-goal/hooks/claude.json:11` still invoke `py -3 <script>` directly. Unlike
the POSIX `command` beside each one, none checks that the script exists or converts a
launcher failure to exit 0. A missing Python file therefore still reaches the exact
pre-handler exit-2 path Phase 0 was required to eliminate. The regressions at
`tests/test_goal_hooks.py:460-466,512-531` select only `command`; the structural assertion
at `tests/test_package_surface.py:1779-1787` does the same. No test exercises
`commandWindows`.

Proving command (exit 0; the final two booleans are `has file guard`, `has fail-open`):

```text
python3 -c 'import json, pathlib; files=[pathlib.Path("plugins/ultra-goal/hooks/hooks.json"),pathlib.Path("plugins/ultra-goal/hooks/claude.json")]; rows=[]; [rows.append((str(p), event, h["commandWindows"], "[ -f" in h["commandWindows"], "exit 0" in h["commandWindows"])) for p in files for event, groups in json.loads(p.read_text())["hooks"].items() for group in groups for h in group["hooks"] if "commandWindows" in h]; print(*rows, sep="\n"); assert rows and all(not guarded and not fail_open for _,_,_,guarded,fail_open in rows)'
```

```text
('plugins/ultra-goal/hooks/hooks.json', 'Stop', 'py -3 "%CLAUDE_PLUGIN_ROOT%\\skills\\ultra-goal\\scripts\\goal_stop.py"', False, False)
('plugins/ultra-goal/hooks/hooks.json', 'SessionStart', 'py -3 "%CLAUDE_PLUGIN_ROOT%\\skills\\ultra-goal\\scripts\\goal_session_start.py"', False, False)
('plugins/ultra-goal/hooks/hooks.json', 'PostToolUseFailure', 'py -3 "%CLAUDE_PLUGIN_ROOT%\\skills\\ultra-goal\\scripts\\goal_tool_failure.py"', False, False)
('plugins/ultra-goal/hooks/claude.json', 'PreCompact', 'py -3 "%CLAUDE_PLUGIN_ROOT%\\skills\\ultra-goal\\scripts\\goal_pre_compact.py"', False, False)
```

The Darwin host cannot prove how a native Windows host consumes this field; it can prove
that the shipped Windows-specific path lacks the required guard. That is enough to fail
the plan's Phase-0 structural condition, while native Windows lifecycle behavior remains
unverified.

### F2 — P1 — zCode's documented plugin root selects `/skills/...` and silently disables every shared hook

The shared launcher resolves its script from
`${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}` at
`plugins/ultra-goal/hooks/hooks.json:10,24,38`, but uses the documented
`ZCODE_PLUGIN_ROOT` only to append `--host zcode`. In the environment the implementation
itself identifies as zCode's documented one, all three paths become `/skills/...`, fail
the new existence guard, and exit 0 without loading a hook. The test at
`tests/test_package_surface.py:1215-1222` checks only the host tag and misses the path.

Proving command (real shipped Stop command, environment contains the real plugin path only
as `ZCODE_PLUGIN_ROOT`; exit 0):

```text
python3 -c 'import json, os, pathlib, subprocess; p=pathlib.Path("plugins/ultra-goal/hooks/hooks.json"); command=json.loads(p.read_text())["hooks"]["Stop"][0]["hooks"][0]["command"]; root=str(pathlib.Path("plugins/ultra-goal").resolve()); r=subprocess.run(["/bin/sh","-x","-c",command],input="{}",text=True,capture_output=True,env={"PATH":os.environ["PATH"],"ZCODE_PLUGIN_ROOT":root}); print("exit",r.returncode); print(r.stderr.strip()); assert r.returncode==0 and "P=/skills/ultra-goal/scripts/goal_stop.py" in r.stderr'
```

```text
exit 0
+ P=/skills/ultra-goal/scripts/goal_stop.py
+ '[' -f /skills/ultra-goal/scripts/goal_stop.py ']'
+ exit 0
```

This is stronger than the report's “zero live coverage” caveat: under the documented root
variable, the current launcher demonstrably cannot reach the gate.

### F3 — P1 — the first Stop, including a completion candidate, launders the authorized spec baseline

The arming fence validates the artifact and writes only the slug and Git review revision at
`plugins/ultra-goal/commands/goal-run.md:42-45`; it records no digest of the frozen
`## Intent`, `## Boundary`, and `## Anchor`. The gate instead chooses the first event that
happens to contain a digest at
`plugins/ultra-goal/skills/ultra-goal/scripts/goal_stop.py:573-580`. An ordinary Stop writes
one at `goal_stop.py:614-625`, but a completion candidate is allowed to be the first Stop,
and its `anchor_checked` row becomes the baseline. The audit repeats the same trust error:
`plugins/ultra-goal/skills/ultra-goal/scripts/validate_artifact.py:1472-1485` derives its
baseline from the first anchor check. The regression at
`tests/test_goal_hooks.py:1108-1111` proves only that a first Stop writes some digest; it
never proves that the digest is the artifact the owner authorized at arming.

The consequence is an authority bypass, not a bookkeeping defect. After arming an artifact
whose intent says `AUTHORIZED ORIGINAL` and whose anchor is `/usr/bin/false`, the probe
edits both frozen fields before the first Stop, writes a candidate, and gets a green allow
from `/usr/bin/true`. There is no `frozen_spec_changed` event. Clause 2 of the completion
contract is therefore absent on the run's first and most important candidate.
The selector also does not restrict the baseline row to a hook-authored event type: a
run-authored trace containing `spec_digest` is accepted. Replacing the earlier row with a
trace carrying the edited digest makes that trace a de facto re-baseline authorization.

Proving command (exit 0):

```text
/opt/anaconda3/bin/python /tmp/codex-r4-contract-probes.py
```

Relevant output:

```json
BASELINE_LAUNDER
{
  "decision": null,
  "events": ["anchor_checked"],
  "outcome": "green",
  "frozen_spec_changed": false
}
TRACE_REBASELINE_LAUNDER
{
  "decision": null,
  "events": ["run_authored_trace", "anchor_checked"],
  "outcome": "green",
  "frozen_spec_changed": false
}
```

### F4 — P1 — a turn boundary is treated as proof that required workers joined

`plugins/ultra-goal/skills/ultra-goal/scripts/goal_stop.py:408-418` classifies an ordinary
`stop_ordinary` as a recovery boundary, and `_unrecovered_failures` at
`goal_stop.py:421-440` forgets every `role_unavailable` before that boundary. There is no
success-side hook or worker-join event. The completion branch at `goal_stop.py:668-718`
therefore checks only that a failure is not in the current tail, not that all required
workers joined and no writer remains. This is not merely missing coverage: the regression
at `tests/test_goal_hooks.py:742-773` deliberately pins “ordinary Stop happened” as
recovery without recording a successful retry or fallback.

The probe records `role_unavailable`, gets the expected first refusal, ends an ordinary
turn without any successful worker/fallback observation, and makes a second claim. The
gate executes the anchor and allows completion. Clause 3 is therefore instructional only,
despite the shipped contract saying the gate checks it.

Proving command (exit 0):

```text
/opt/anaconda3/bin/python /tmp/codex-r4-contract-probes.py
```

Relevant output:

```json
WORKER_JOIN_BYPASS
{
  "first_decision": "block",
  "second_decision": null,
  "events": ["stop_ordinary", "role_unavailable", "candidate_refused", "stop_ordinary", "anchor_checked"],
  "success_or_join_event": false
}
```

### F5 — P1 — refused completion candidates do not consume the owner's completion-attempt ceiling

Attempt number is defined as `len(anchor_checked) + 1` at
`plugins/ultra-goal/skills/ultra-goal/scripts/goal_stop.py:568-570`. A candidate refused for
an unjoined worker returns at `goal_stop.py:668-718`, before the owner ceiling is evaluated
at `goal_stop.py:720-749`, and writes no `anchor_checked`. Thus the owner can declare
`ceiling: 1` while the gate accepts and denies an unbounded number of explicit completion
candidates, all called attempt 1. The test at `tests/test_goal_hooks.py:775-792` preloads
only anchor-check rows and does not cover pre-anchor candidate refusals.

This also makes F4 compound: insert an ordinary Stop after each refusal and the denial
budget resets, while neither the owner ceiling nor an anchor attempt advances. The ceiling
is documented as bounded completion attempts, but the implementation bounds only anchor
executions.

Proving command (exit 0):

```text
/opt/anaconda3/bin/python /tmp/codex-r4-contract-probes.py
```

Relevant output after three explicit candidates under `ceiling: 1`:

```json
CEILING_BYPASS
{
  "candidate_refused": 3,
  "candidate_turns": [1, 1, 1],
  "anchor_checked": 0,
  "ceiling_reached": 0
}
```

### F6 — P1 — arming a second slug silently replaces the active run

After validation, `plugins/ultra-goal/commands/goal-run.md:42-45` unconditionally rewrites
`.goals/active`; it never refuses an already armed different goal. The write-once baseline
test at `tests/test_package_surface.py:2109-2141` protects only re-arming the same `demo`
slug, so it does not exercise this collision. This can redirect every hook in the cwd from
one owner-authorized run to another without an explicit disarm.

Proving command (the last block of the same exit-0 probe executes the shipped fence twice,
first for `alpha`, then for `beta`):

```text
/opt/anaconda3/bin/python /tmp/codex-r4-contract-probes.py
```

```json
DOUBLE_ARM
{
  "exits": [0, 0],
  "active_after_both": "beta"
}
```

### F7 — P1 — shipped model instructions still teach the retired per-turn gate contract

The Phase-1 documentation migration changed the new gate section but left contradictory
instructions on the paths the model and owner actually consume:

- `README.md:136-150,219-254` still says the gate refuses every red turn, runs the anchor
  every turn, and derives its release from the host continuation cap. `README.md:314-326`
  still promises `additionalContext` on every ending turn, the exact live-proven shape that
  prevents Claude Code from ending it.
- `plugins/ultra-goal/skills/ultra-goal/SKILL.md:384-390,467-474,618-627` says a red anchor
  prevents every turn end, the anchor runs every turn, and every turn's commit carries an
  anchor verdict.
- The shipped template says the same at
  `plugins/ultra-goal/skills/ultra-goal/assets/goal-package.md:172-180,182-208`; its actual
  fallback handoff never tells the run to write a completion candidate, and requires a
  measured anchor verdict on every turn.
- `plugins/ultra-goal/skills/ultra-goal/references/zero-trust.md:27-37` and
  `references/document-system.md:7-16,23-38,51-71` still define measurements and audit as
  per-turn. `plugins/ultra-goal/skills/ultra-goal/evals/evals.json:255-260` still expects
  two identical anchor results to auto-release as “not progressing,” a rule the new gate
  explicitly retired.
- `tests/test_package_surface.py:263-277` actively requires the obsolete template command
  “Commit once per turn ... [anchor: ...]”, so the green suite protects the contradiction.

These are not harmless history under `docs/wip`: they are public documentation, active
Skill/reference/template inputs, eval expectations, and a test. A model following them can
omit `.candidate`, invent unmeasured per-turn verdicts, or expect an allow-context channel
that no longer exists.

Proving command (exit 0; each match is in a currently shipped surface):

```text
rg -n -F -e 'refuses to let a turn end while the anchor is red' -e 'Runs the anchor every turn' -e 'the anchor runs for real, every turn' -e 'additionalContext` | the model, on every turn that ends' -e 'Commit once per turn as `goal(weekly-dep-upgrade) turn' -e 'goal(<slug>) turn <N>: <one line on what changed>' -e 'two identical anchor results in a row mean the loop is not progressing' README.md plugins/ultra-goal tests/test_package_surface.py
```

Representative output:

```text
README.md:221:| `Stop` | Runs the anchor every turn | ...
README.md:319:| `additionalContext` | the model, on every turn that ends | ...
plugins/ultra-goal/skills/ultra-goal/SKILL.md:622:goal(<slug>) turn <N>: ... [anchor: green|red|unknown]
plugins/ultra-goal/skills/ultra-goal/references/zero-trust.md:31:...the anchor runs for real, every turn...
plugins/ultra-goal/skills/ultra-goal/assets/goal-package.md:207:Commit once per turn as ...
plugins/ultra-goal/skills/ultra-goal/evals/evals.json:259:...two identical anchor results in a row mean the loop is not progressing...
tests/test_package_surface.py:276:...Commit once per turn...
```

### F8 — P1 — the Codex payload fix disables Kimi's only blocking path

`plugins/ultra-goal/kimi.plugin.json:20-24` invokes the shared gate with `--host kimi`, but
the host never reaches the payload construction: `_deny` at
`plugins/ultra-goal/skills/ultra-goal/scripts/goal_stop.py:256-274` is host-independent,
and both refusal sites at `goal_stop.py:712-718,938-961` return its top-level
`decision/reason` pair. That pair is correct on the live Codex 0.150.1 control, but the
currently installed Kimi 0.40.1 parser accepts only `message` and `hookSpecificOutput` and
blocks only when `hookSpecificOutput.permissionDecision == "deny"`. It ignores the
top-level pair. A real red candidate through the shipped Kimi entry point emits exactly
that ignored pair.

The regression at `tests/test_goal_hooks.py:1696-1704` requires a top-level-only payload
without parameterizing the host; the Kimi-shaped calls immediately above it test allow
paths only. Commit `dc76c87` fixed Codex by deleting the nested form globally, thereby
regressing the divergent Kimi consumer. Kimi has no live hook run in this mission, but the
consumer code in the current installed binary makes the transport mismatch deterministic:
if the hook is loaded, red cannot block.

Proving commands:

```text
/Users/rocky243/.kimi-code/bin/kimi --version
# 0.40.1

strings -a -n 8 /Users/rocky243/.kimi-code/bin/kimi | rg -n -C 5 'permissionDecision|HookSpecificOutputSchema|HookJsonOutputSchema'
# HookJsonOutputSchema = { message, hookSpecificOutput }
# if (hookSpecificOutput?.permissionDecision !== "deny") return result;
# otherwise action: "block"

/opt/anaconda3/bin/python /tmp/codex-r4-host-output-probes.py
```

Relevant probe output:

```json
CURRENT_KIMI_DENY
{
  "keys": ["decision", "reason"],
  "decision": "block",
  "has_hookSpecificOutput": false
}
```

### F9 — P1 — the worker-refusal path creates a fourth gate outcome and audits it as a red anchor that never ran

When Kimi's one-denial budget is spent on an unrecovered worker,
`plugins/ultra-goal/skills/ultra-goal/scripts/goal_stop.py:692-703` writes
`continuation_budget_spent` with `"outcome": "workers_unjoined"`. No anchor has executed,
yet this is a fourth value in the gate's mechanical `outcome` field, outside
`green/red/unknown` and outside the separate run-disposition vocabulary. The audit then
compounds the category error: `plugins/ultra-goal/skills/ultra-goal/scripts/validate_artifact.py:1447-1469`
describes every such event as “the anchor still red.” The only regression for that audit
path covers a genuinely red anchor; `tests/test_validate_artifact.py:671-684` does not cover
the worker-refusal shape.

The probe spends the Kimi budget through two worker-refused candidates. It records zero
`anchor_checked` rows, then asks the real audit to interpret the resulting event.

Proving command (exit 0):

```text
/opt/anaconda3/bin/python /tmp/codex-r4-contract-probes.py
```

Relevant output:

```json
AXIS_LEAK
{
  "first_decision": "block",
  "second_decision": null,
  "anchor_checked": 0,
  "budget_event_outcome": "workers_unjoined",
  "audit_message": "1 attempt(s) ended with the anchor still red ..."
}
```

`impossible` and `unachievable` did not enter the gate code; that requested negative is
clean. The failure is a different fourth mechanical value that the same two-axis rule also
forbids.

### F10 — P1 — failed state transitions are reported as successful consumption, measurement, and disarm

The completion contract requires one claim/one judgment and a hook-authored measurement,
but both state transitions fail silently. Candidate read and unlink share one `try` at
`plugins/ultra-goal/skills/ultra-goal/scripts/goal_stop.py:639-646`; if unlink fails, the
handler clears only `claim_text`, leaves the candidate present, and continues to execute the
anchor. `append_event` swallows all write failures at
`plugins/ultra-goal/skills/ultra-goal/scripts/goal_hooks.py:380-387`, while `record` at
`goal_stop.py:816-842` has no success result to check. The green branch at
`goal_stop.py:860-883` therefore announces a passed attempt even when it wrote no
measurement. The Phase-2 terminal path has the same defect: `goal_stop.py:599-612`
swallows marker-unlink failure and still says the gate is disarmed. No permission-failure
regression exists in `tests/test_goal_hooks.py`.

Two real filesystem controls demonstrate both halves. With an unwritable event log, the
gate returns a green allow while the log stays zero bytes. With an unwritable `.goals`
directory, candidate unlink and event append both fail; two successive Stops each report a
passed attempt from the same surviving candidate. The same directory condition also makes
two successive frozen-spec checks each announce a terminal disarm while `.goals/active`
survives. Clauses 5 and 6 are not guaranteed on the exact I/O failures where durable
evidence matters most, and Phase 2 can become the “refuse forever” shape its normal path
was meant to avoid.

Proving command (exit 0):

```text
/opt/anaconda3/bin/python /tmp/codex-r4-contract-probes.py
```

Relevant output:

```json
MEASUREMENT_WRITE_FAILURE
{
  "decision": null,
  "message_has_passed": true,
  "event_bytes": 0
}
CANDIDATE_CONSUME_FAILURE
{
  "first_passed": true,
  "second_passed": true,
  "candidate_survived": true,
  "event_log_exists": false
}
FALSE_TERMINAL_ON_UNLINK_FAILURE
{
  "first_says_disarmed": true,
  "second_says_disarmed": true,
  "active_after_first": true,
  "active_after_second": true,
  "frozen_spec_changed_events": 2
}
```

## Dimension verdicts

### Phase 0 checkpoint

- `_allow`: **PASS on the required live positive control.** The current
  `goal_stop.py:234-253` returns `systemMessage` only. On Claude Code 2.1.260 the turn
  produced one Stop callback, payload keys `['systemMessage']`, and only
  `PROBE_INITIAL` was visible.
- `_deny`: **PASS on the required live positive control.** The current
  `goal_stop.py:256-274` returns only `decision` and `reason`. On codex-cli 0.150.1 it
  produced two Stop callbacks with chain flags `[False, True]` and
  `PROBE_CORRECTED`.
- POSIX interpreter selection, single execution, missing-script fail-open, argparse
  fail-open, and session ownership regressions: **PASS**, 22 targeted tests.
- Same-cwd isolation: **PASS on an actual two-live-session control.** Two independent
  Claude Code `--no-session-persistence` invocations in one temporary cwd supplied
  distinct session IDs. Session 1 claimed the marker and wrote one goal event; session 2
  still invoked the wrapper but received empty gate output and did not add an event
  (`goal_events_after_each: [1, 1]`). This is stronger than the supplied pre-owned-marker
  probe.
- Windows launch-path protection: **FAIL** (F1).
- zCode shared-launch reachability: **FAIL** (F2).
- Cross-host deny compatibility: **FAIL**. The Codex fix is live-correct but disables
  Kimi's block consumer (F8).

Commands:

```text
/opt/anaconda3/bin/python docs/wip/reviews/probes-round-4.py
# sandbox-external run: 3/3 PASS

/opt/anaconda3/bin/pytest -q tests/test_goal_hooks.py::LauncherContractTests tests/test_goal_hooks.py::SessionOwnershipTests tests/test_goal_hooks.py::StopPayloadContractTests
# 22 passed in 4.01s

/Users/rocky243/.local/share/claude/versions/2.1.260 --version
# 2.1.260 (Claude Code)
/Users/rocky243/.local/bin/codex --version
# codex-cli 0.150.1

/opt/anaconda3/bin/python /tmp/codex-r4-dual-session.py
# exit 0; cli_exits [0, 0]; session_ids_distinct true;
# first_gate_output_nonempty true; second_gate_output "";
# goal_events_after_each [1, 1]
```

Verdict on the five original defects: **not all dead**. The Claude allow, Codex deny,
POSIX launcher, POSIX launch-error, and normal writable session-ownership paths pass their
controls. The shipped Windows launch paths still lack the protection, the zCode launcher
cannot resolve its documented root, and the globally applied deny shape creates the Kimi
regression.

### Phase 1 — completion contract

| Contract clause | Verdict | Evidence |
|---|---|---|
| 1. Explicit candidate grants nothing | **PASS** | `goal_stop.py:639-646,778-883`; a candidate triggers judgment and a green says only what the command measured. |
| 2. Ownership + authorized baseline + anchor identity first | **FAIL** | Ownership is checked before the handler at `goal_hooks.py:364-372`, but no authorized baseline exists before the first Stop; F3 proves a changed candidate establishes it. |
| 3. Required workers joined; no writer remains | **FAIL** | F4 proves an ordinary boundary substitutes for a successful worker/fallback, and the code states that a remaining writer is unobservable. |
| 4. Gate executes the current anchor itself, once | **PASS** on the normal path | `goal_stop.py:778-805`; the witness file gains exactly one byte for one candidate. |
| 5. Hook writes the measurement | **FAIL** as a contract | The normal writable path records every required field at `goal_stop.py:816-842`; F10 proves a write failure is ignored while green is still announced. |
| 6. Later state change invalidates the candidate | **FAIL** as a contract | Normal judgment removes the marker before execution, but F10 proves unlink failure leaves it reusable for multiple passed Stops. |
| Historical green is never a pass input | **PASS** | Two candidates execute the anchor twice; old checks are read for count/audit, never substituted for the current run. |

Named clean-path command:

```text
/opt/anaconda3/bin/pytest -q tests/test_goal_hooks.py::CompletionContractTests::test_an_ordinary_stop_runs_nothing_and_never_blocks tests/test_goal_hooks.py::CompletionContractTests::test_a_candidate_runs_the_anchor_once_against_current_state tests/test_goal_hooks.py::CompletionContractTests::test_the_candidate_is_consumed_by_its_judgment tests/test_goal_hooks.py::CompletionContractTests::test_a_stale_green_is_never_a_pass_input tests/test_goal_hooks.py::CompletionContractTests::test_green_proves_only_this_anchor_on_this_state tests/test_goal_hooks.py::CompletionContractTests::test_a_wrong_session_candidate_is_never_judged tests/test_goal_hooks.py::FrozenSpecTests
# 14 passed in 4.30s
```

Adversarial command for the failed clauses:

```text
/opt/anaconda3/bin/python /tmp/codex-r4-contract-probes.py
# exit 0: BASELINE_LAUNDER, WORKER_JOIN_BYPASS, CEILING_BYPASS,
# MEASUREMENT_WRITE_FAILURE, CANDIDATE_CONSUME_FAILURE
```

The ceiling prose in `goal_hooks.py:77-140` and the new Skill section at
`plugins/ultra-goal/skills/ultra-goal/SKILL.md:704-717` does correctly redefine the gate
bound as consecutive denied completion attempts, records the host cap only as a backstop,
and names zCode's degradation. The implementation nevertheless fails the bounded-attempt
semantics in F5, and the public README still describes the old host-cap-derived scheme in
F7. “No longer host cap − 1” is therefore true of the new core section, not of the shipped
documentation as a whole.

### Phase 2 — close-and-reopen semantics

The normal writable path is a real terminal state, not a permanent refusal. On a changed
frozen digest, `goal_stop.py:581-612` appends `frozen_spec_changed`, removes both active and
candidate markers, allows the Stop, and leaves the event log. The next Stop is inert.
After the owner-style fresh-start procedure documented at
`plugins/ultra-goal/commands/goal-run.md:83-97` removes the old event/baseline state, the
same shipped arming fence creates a reachable new run. The focused regressions at
`tests/test_goal_hooks.py:1149-1205` agree.

The normal-path control is explicit:

The arming fence in this lifecycle-only fixture uses a success stub for the validator; the
test is of terminal/reopen reachability, not a second artifact-validation claim.

```text
/opt/anaconda3/bin/python /tmp/codex-r4-contract-probes.py
```

```json
TERMINAL_AND_FRESH_START
{
  "closed": {
    "active_exists": false,
    "candidate_exists": false,
    "events": ["stop_ordinary", "frozen_spec_changed"]
  },
  "rearm_exit": 0,
  "active_after_rearm": true,
  "new_event": "anchor_checked",
  "new_outcome": "green"
}
```

There is no *named* trajectory row or ruling-id transition in the scripts; the only
documented reopening instruction is “only the owner reopens” at `goal-run.md:107-113`.
But the generic first-`spec_digest` selector is itself a trace consumer: the
`TRACE_REBASELINE_LAUNDER` control replaces the old log with a run-authored event carrying
the changed digest, then receives green. That is an authority instruction, not an
authenticated or mechanically required precondition. F3 also permits the simpler
pre-first-Stop laundering, and F6 lets the shell path replace an active goal.
So option (b) is correctly terminal only after a trustworthy baseline exists and unlink
succeeds. Authority is **not** an effective precondition across the whole reachable path.
F10 also proves the supposedly terminal path repeats forever while falsely saying
“disarmed” when marker deletion fails.

Search used to check for a trace-based transition:

```text
rg -n -i 're.?baseline|trajectory|ruling|authorized|authority' plugins/ultra-goal/skills/ultra-goal/scripts plugins/ultra-goal/commands/goal-run.md
# no named re-baseline/ruling transition; the generic spec_digest reader is the de facto consumer in F3
```

### Two axes

**FAIL overall** because of F9, with the requested narrow negative clean. The
`anchor_checked` path assigns only `green`, `red`, or `unknown` at
`goal_stop.py:793-804,816-842`; `impossible` and `unachievable` do not occur in gate code,
and the run-disposition vocabulary remains prose in `SKILL.md:741-757` and
`goal-run.md:176-182`. But the worker-budget path emits
`outcome: workers_unjoined` and the audit converts it into a nonexistent red anchor (F9),
so the mechanical event vocabulary does not in fact preserve the split.

Commands:

```text
/opt/anaconda3/bin/pytest -q tests/test_goal_hooks.py::AnchorGateTests tests/test_package_surface.py::RolesByStageTests::test_the_stop_hook_reminds_only_what_may_change
# 12 passed in 1.94s

python3 -c 'from pathlib import Path; p=Path("plugins/ultra-goal/skills/ultra-goal/scripts/goal_stop.py"); s=p.read_text(); assert "outcome = \"green\"" in s and "outcome = \"red\"" in s and "outcome = \"unknown\"" in s; assert "unachievable" not in s.lower() and "impossible" not in s.lower(); print("anchor observations: green red unknown"); print("mechanical impossible/unachievable: absent")'
# anchor observations: green red unknown
# mechanical impossible/unachievable: absent

/opt/anaconda3/bin/python /tmp/codex-r4-contract-probes.py
# AXIS_LEAK: zero anchor checks; outcome workers_unjoined; audit says anchor still red
```

### Full four-round regression range (`97d0780..HEAD`)

**FAIL.** The range contains 25 commits and changes 40 files. The full suite is green, but
the range audit found one direct newly introduced host regression: `dc76c87` fixes Codex by
globally deleting the nested deny shape and disables Kimi (F8). F3-F5, F9, and F10 are
defects in the new completion lifecycle itself; F7 is an incomplete migration that leaves
old and new contracts active at once. F1, F2, and F6 are carried defects: the baseline
`97d0780` already had the unguarded Windows commands, ignored `ZCODE_PLUGIN_ROOT` for its
script path, and overwrote `.goals/active`. They are not new regressions, but they remain
open against this final review's acceptance bar.

Commands:

```text
git log --oneline 97d0780..HEAD
# 25 commits

git diff --stat 97d0780..HEAD
# 40 files changed, 6215 insertions(+), 440 deletions(-)

git diff --name-status 97d0780..HEAD
# complete 40-file inventory inspected

git diff --check 97d0780..HEAD
# one round-3 documentation whitespace warning in docs/wip/reviews/codex-round-3.md:23;
# no implementation whitespace error

git show 97d0780:plugins/ultra-goal/hooks/hooks.json
git show 97d0780:plugins/ultra-goal/commands/goal-run.md
# proves F1/F2/F6 shapes were present at the range baseline

/opt/anaconda3/bin/pytest -q
# 394 passed in 26.60s (blind, before §8.1)
# 394 passed in 27.93s (final repeat after report completion)
```

## External implementation ruling

Both proposals have a shape worth adopting; neither file is safe to copy as-is.
Line references in this section are under
`/Users/rocky243/Documents/Codex/2026-09-04/overthinking-agent-md/work/ultra-goal-adaptation/plugins/ultra-goal/skills/ultra-goal/scripts/`;
the `-v280` sibling has identical SHA-1s for both files.

**`goal_run.py`: adopt the Python arming shape, not this exact revision.** At
`goal_run.py:22-60` it validates through the existing `validate_paths`, raises on errors,
records the arming-time frozen digest, rejects a different active goal, and keeps the whole
transition in one program. That directly closes the shell-fence class behind F3 and F6 and
is the simpler long-term path. However, the exact comparison at `goal_run.py:34-42` and
disarm check at `goal_run.py:91-94` compare the entire marker text with the slug. The
current marker's second `session <id>` line makes both legitimate same-goal re-entry and
disarm fail. It also omits `*.candidate` from the ignore entries at `goal_run.py:55-59`, and
its bundled review-diff path at `goal_run.py:63-73` lacks the current ancestor guard.
Port the arming behavior into the current marker/lifecycle contract; do not replace the
shell file byte-for-byte.

**`goal_host.py`: adopt only an allowlisted output-normalization function, not the
dispatcher or passthrough.** The Kimi branch at `goal_host.py:30-44` is now justified by a
reproduced consumer difference (F8). But line 31 returns every non-Kimi payload unchanged,
which preserves the mixed payload that the live Codex probe proved inert. Its dispatcher
at `goal_host.py:47-67,70-83` also uses the old two-argument handler interface, while the
current `run_hook` invokes three arguments at `goal_hooks.py:372`; copied as-is, the outer
fail-open would silently disable the hook. A safe central mapper must reconstruct each
host's allowlisted output shape, never pass unknown/mixed fields through. The shortest fit
for this branch may be one host-aware output function in the existing Stop path rather than
restoring the whole routing module.

Commands:

```text
shasum /Users/rocky243/Documents/Codex/2026-09-04/overthinking-agent-md/work/ultra-goal-adaptation/plugins/ultra-goal/skills/ultra-goal/scripts/goal_run.py /Users/rocky243/Documents/Codex/2026-09-04/overthinking-agent-md/work/ultra-goal-adaptation-v280/plugins/ultra-goal/skills/ultra-goal/scripts/goal_run.py /Users/rocky243/Documents/Codex/2026-09-04/overthinking-agent-md/work/ultra-goal-adaptation/plugins/ultra-goal/skills/ultra-goal/scripts/goal_host.py /Users/rocky243/Documents/Codex/2026-09-04/overthinking-agent-md/work/ultra-goal-adaptation-v280/plugins/ultra-goal/skills/ultra-goal/scripts/goal_host.py
# both goal_run.py copies: 0f71fe24...; both goal_host.py copies: 9ea7764a...

/opt/anaconda3/bin/python /tmp/codex-r4-host-output-probes.py
```

```json
EXTERNAL_OUTPUT_FOR
{
  "codex_same_object": true,
  "codex_keys": ["decision", "hookSpecificOutput", "reason"],
  "kimi_keys": ["hookSpecificOutput"],
  "kimi_nested_decision": "deny"
}
EXTERNAL_GOAL_RUN
{
  "same_goal_with_session": "Another goal is armed; disarm it explicitly first.",
  "disarm_exit": 1,
  "disarm_error": "The active marker does not name this goal.",
  "different_goal": "Another goal is armed; disarm it explicitly first."
}
```

## Final verdict

**REQUEST CHANGES.** The blind suite is green and the two most important live positive
controls pass, but the implementation does not meet the signed-off Phase-0/1/2 contract.
Ten P1 findings remain: three shipped-host launch/output failures (F1, F2, F8), four
completion/authority/liveness failures (F3-F5, F10), an unsafe active-run transition (F6),
contradictory shipped instructions (F7), and a false fourth-outcome/audit report (F9).

The minimum acceptance retest is not “394 tests again.” It is: preserve the Claude and
Codex live controls; exercise the corrected Kimi-specific deny consumer; drive zCode from
its documented root; add a native Windows or equivalent launch consumer; arm an immutable
baseline before any Stop; make worker recovery positively observable; count every
candidate against the owner ceiling; make consume/record/disarm state transitions checked;
and rerun the adversarial probes above plus the full suite.
