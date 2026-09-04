# Codex adversarial review — round 1

Review object: `97d0780..HEAD` (`b5143a7` through `434d2c2`), 26 files,
1,291 insertions and 117 deletions. Review date: 2026-09-04. I did not read
§8.1 until after recording the blind test verdict.

## Verdict

**Request changes.** The suite is green (`332 passed`), but that does not make
the four-host product path true. I found four release-blocking defects:

1. Kimi does not expand this command's `$1`, and the command also names no
   Kimi-documented plugin-root variable.
2. Kimi's one-block budget is counted across host turns, so fresh turns alternate
   between one continuation and none.
3. The stagnation sensor can count an anchor's own mutation as model progress forever,
   while missing real content edits to an already-untracked file.
4. The review baseline's documented `none` path errors, and re-running `/goal-run`
   can move the baseline to `HEAD`, reducing a 26-file run to an empty diff.

There are also two evidence/documentation defects. The range therefore does not meet
§7's done condition: the gate does not yet drive the promised loop on Kimi, and the
reviewer does not reliably see the whole change.

## Blind suite verdict

I first ran the repository's documented Python form:

```console
$ python3 -m pytest -q
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3: No module named pytest
```

That is an environment failure, not an implementation verdict. I resolved the available
test runner without reading §8.1:

```console
$ which -a pytest python3
/opt/anaconda3/bin/pytest
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3

$ pytest -q
332 passed in 15.60s
```

Only after recording that output did I read zCode's report.

## Findings

### F1 — P1: Kimi cannot deterministically arm `/goal-run <slug>`

**Location:** `plugins/ultra-goal/commands/goal-run.md:7` (repeated at lines 17,
27, 36, 37, 61 and 78); the Kimi exposure is
`plugins/ultra-goal/kimi.plugin.json:47`.

The installed Kimi 0.40.1 command loader replaces only `$ARGUMENTS`. If a command body
does not contain that token, it appends `ARGUMENTS: <value>` and leaves `$1` untouched.
It then enqueues only that expanded text as a user prompt. Its plugin service visibly
attaches `KIMI_PLUGIN_ROOT` to hook and MCP child environments; neither its reference nor
the command-activation path documents or attaches a plugin-root variable to the prompt.
The shared command uses neither documented Kimi mechanism: it uses `$1`, and line 27
resolves the validator through `CLAUDE_PLUGIN_ROOT`/`PLUGIN_ROOT`.

**Proven by:**

```console
$ rg -n '\$1|\$ARGUMENTS' plugins/ultra-goal/commands/goal-run.md
7:Start the run for `$1`.
17:ls .goals/$1.goal.md .goals/$1.decisions.md
27:python3 "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/.../validate_artifact.py" .goals/$1.goal.md
36:printf '%s\n' "$1" > .goals/active
37:git rev-parse HEAD > .goals/$1.baseline ...
61:Read `.goals/$1.goal.md` in full. ...
78:`goal($1) turn <N>: ...`
```

```console
$ strings -a ~/.kimi-code/bin/kimi | sed -n '712820,712910p'
function expandCommandArguments(body, args) {
const replaced = body.replaceAll("$ARGUMENTS", args);
if (!body.includes("$ARGUMENTS") && args.length > 0) return `${replaced}\n\nARGUMENTS: ${args}`;
return replaced;
```

```console
$ strings -a ~/.kimi-code/bin/kimi | sed -n '713970,714025p;759340,759400p'
enabledHooks() { ... env: { KIMI_CODE_HOME: this.kimiHomeDir,
KIMI_PLUGIN_ROOT: record.root ...
enabledCommands() { ... loadPluginCommand({ commandPath: entry.path, ...
...
const expanded = expandCommandArguments(def.body, commandArgs);
...
text: expanded
```

The immediate shell consequence of executing the emitted snippets literally is also
observable:

```console
$ sh -c 'printf "<%s>\n" "$1"'
<>
```

**What breaks:** `/ultra-goal:goal-run demo` reaches Kimi with literal `$1`; the arming,
artifact lookup, validation and commit-subject instructions are therefore not bound to
`demo`. Even if the model guesses the slug from the appended `ARGUMENTS:` line, the
validator path still relies on variables not documented for this command path. A model
guess is not a host adaptation.

**What would settle it:** use Kimi's documented `$ARGUMENTS` command contract and a
Kimi-valid way to reach validation, then run an installed-plugin invocation showing that
the rendered prompt contains `demo`, contains no unresolved `$1`, validates the intended
artifact and writes `.goals/active` with exactly `demo`.

### F2 — P1: Kimi's continuation budget leaks across host turns

**Location:** `plugins/ultra-goal/skills/ultra-goal/scripts/goal_stop.py:399-412`
and `:640-650`; the mistaken lifecycle is encoded at
`tests/test_goal_hooks.py:1187-1190`, while the same suite correctly states the host fact
at `tests/test_goal_hooks.py:1227-1230`.

`_block_streak()` counts trailing blocked checks in the whole persistent event log. Kimi,
however, invokes the blocking Stop hook only once in a host turn and resets its internal
guard when that turn ends. Thus the second call in `test_kimi_blocks_at_most_once` cannot
be a same-turn budget check; it is necessarily a fresh host turn, whose budget has reset.

**Proven by the installed Kimi 0.40.1 binary:**

```console
$ strings -a ~/.kimi-code/bin/kimi | sed -n '624858,624878p;721700,721725p'
if (!stopHookContinuationUsed) {
const stopBlock = await this.agent.hooks?.triggerBlock("Stop", {
...
stopHookContinuationUsed = true;
...
notifyTurnEnded(event) {
this.stopHookContinuationUsed = false;
...
if (this.stopHookContinuationUsed) return void 0;
```

**Proven end to end through the existing harness:**

```console
$ python3 -c 'import sys; sys.path.insert(0, "tests"); from test_goal_hooks import ContinuationBudgetTests as T; t=T(); t.setUp(); ps=[t.turn(host="kimi") for _ in range(2)]; print("decisions=", [t.decision(p) for p in ps]); print("events=", [(e["turn"], e.get("blocked"), e["event"]) for e in t.events()]); t.tearDown()'
decisions= ['block', None]
events= [(1, True, 'anchor_checked'), (2, False, 'anchor_checked'), (2, None, 'continuation_budget_spent')]
```

The two focused tests pass, demonstrating that the test contract itself models the
impossible second same-turn invocation:

```console
$ pytest -q tests/test_goal_hooks.py::ContinuationBudgetTests::test_kimi_blocks_at_most_once tests/test_goal_hooks.py::ContinuationBudgetTests::test_a_one_block_host_carries_the_park_instructions_on_the_block -vv
2 passed
```

**What breaks:** with an always-red moving anchor, Kimi host turns alternate `block,
allow, block, allow`. Every second fresh turn receives zero continuation, while the event
log says `continuation_budget_spent` even though that turn spent no block. Both the loop
and its claimed measurement are wrong.

**What would settle it:** scope continuation accounting to the actual host turn (using the
host's Stop lifecycle fact, not the global tail of the run log). A regression must feed two
fresh Kimi Stop events and show that both block once; any same-turn re-entry must remain
bounded according to that host's real behavior.

### F3 — P1: the stagnation sensor confuses anchor side effects with work and misses untracked content

**Location:** `plugins/ultra-goal/skills/ultra-goal/scripts/goal_stop.py:347-375`,
`:528-573` and `:620-625`.

The tree digest is captured before the current anchor runs. Consequently, mutations left
by the *previous* anchor appear at the next check as if the model moved the work tree. A
red anchor that appends to a tracked file can keep the plugin's Codex branch returning
`block` indefinitely even when the model did no work after the first check (whether the
host honors those blocks indefinitely is separately unverified):

```console
$ python3 -c 'import sys; sys.path.insert(0, "tests"); from test_goal_hooks import ContinuationBudgetTests as T; t=T(); t.setUp(); a="sh -c \"printf x >> src.txt; exit 1\""; ps=[t.turn(host="codex", anchor=a, work=(i==0)) for i in range(3)]; es=[e for e in t.events() if e["event"]=="anchor_checked"]; print("decisions=", [t.decision(p) for p in ps]); print("checks=", [(e["turn"],e["tree_digest"],e["blocked"]) for e in es]); t.tearDown()'
decisions= ['block', 'block', 'block']
checks= [(1, '633921fe1eb3', True), (2, '94767cdd1506', True), (3, 'd7e434ca711d', True)]
```

The inverse error is also reproducible. `git status --porcelain` contributes an untracked
path but not its content, while `git diff HEAD` omits untracked files. Editing the same
untracked file therefore leaves the alleged content digest unchanged:

```console
$ python3 -c 'import sys; sys.path.insert(0, "tests"); from test_goal_hooks import ContinuationBudgetTests as T; t=T(); t.setUp(); t.turn(host="codex"); import goal_stop as g; p=t.cwd/"new.txt"; p.write_text("one", encoding="utf-8"); a=g._tree_digest(t.cwd); p.write_text("two", encoding="utf-8"); b=g._tree_digest(t.cwd); print("first=", a, "second=", b, "equal=", a==b); t.tearDown()'
first= 54f45a8950e7 second= 54f45a8950e7 equal= True
```

**What breaks:** anchor-generated churn can defeat the plugin's only stagnation escape; on
the current Codex branch the plugin imposes no continuation budget and falls through to
an unknown host backstop. Genuine work in an existing untracked file can instead trigger
a false "not progressing" release. The heuristic observes neither quantity it claims to
judge reliably.

**What would settle it:** distinguish model work from the previous anchor's footprint—for
example, compare a current pre-anchor snapshot to the previous post-anchor snapshot—and
include relevant untracked content or explicitly forbid it. Two regressions must cover the
mutating-anchor/no-model-work case and same-untracked-path/content-changed case.

### F4 — P1: the review baseline has a broken `none` branch and is mutable by re-arming

**Location:** `plugins/ultra-goal/commands/goal-run.md:37`;
`plugins/ultra-goal/skills/review/SKILL.md:20-21`;
`plugins/ultra-goal/skills/critic/SKILL.md:20-21`.

The arming command writes literal `none` when `git rev-parse HEAD` fails, but POSIX
`${base:-HEAD}` only substitutes for unset/empty values, not the non-empty string `none`:

```console
$ sh -c 'base=none; git -C . diff "${base:-HEAD}" --stat'; printf 'exit=%s\n' "$?"
fatal: ambiguous argument 'none': unknown revision or path not in the working tree.
Use '--' to separate paths from revisions, like this:
'git <command> [<revision>...] -- [<file>...]'
exit=128
```

Line 37 also overwrites an existing baseline every time `/goal-run` is invoked. Modeling a
re-arm at the current `HEAD` makes this frozen review object disappear:

```console
$ sh -c 'base=$(git rev-parse HEAD); moved=$(git diff "$base" --name-only | wc -l | tr -d " "); frozen=$(git diff 97d0780..HEAD --name-only | wc -l | tr -d " "); printf "moved-baseline-files=%s frozen-range-files=%s\n" "$moved" "$frozen"'
moved-baseline-files=0 frozen-range-files=26
```

**What breaks:** the promised non-Git fallback errors before review, and a restart/retry of
the documented arming command can silently hand both reviewer and critic an empty range.
The fact that the rewrite is visible in Git history does not repair the review command;
neither role consults that history.

**What would settle it:** make `none` an explicit branch with an honest, executable
non-Git behavior (or refuse that mode), make the run-start baseline write-once and validate
that it is an ancestor, and add end-to-end regressions for both `none` and re-arming an
already-active run. The reviewer should fail loudly rather than silently narrow its range.

### F5 — P2: the shipped owner guidance gives mutually exclusive evidence contracts

**Location:** `plugins/ultra-goal/skills/ultra-goal/SKILL.md:272-275`, `:646-647`
and `:717-724`; `README.md:223-224` and `:435-440`;
`plugins/ultra-goal/skills/ultra-goal/references/agent-modes.md:168-178`; the
contradicting implementation is
`plugins/ultra-goal/skills/ultra-goal/scripts/validate_artifact.py:1389-1407`.

One part says delegation degradation is only a claim and `ROUND_DEGRADED` cannot be
produced; another says `PostToolUseFailure` writes `role_unavailable`, and the validator
does produce `ROUND_DEGRADED`. One paragraph says `UserPromptSubmit` is not registered,
while the same Skill's table and Kimi manifest register it.

**Proven by:**

```console
$ rg -n -C 1 'UserPromptSubmit.*not registered|UserPromptSubmit.*Kimi only|declared and reported, not measured|role_unavailable|ROUND_DEGRADED' README.md plugins/ultra-goal/skills/ultra-goal/SKILL.md plugins/ultra-goal/skills/ultra-goal/references/agent-modes.md plugins/ultra-goal/skills/ultra-goal/scripts/validate_artifact.py
README.md:435:**This one is declared and reported, not measured** ...
README.md:436:claimed ... a `role_unavailable` event surfaced by `--audit` ...
plugins/ultra-goal/skills/ultra-goal/SKILL.md:646:| `PostToolUseFailure` | Records `role_unavailable` ...
plugins/ultra-goal/skills/ultra-goal/SKILL.md:647:| `UserPromptSubmit` | Kimi only ...
plugins/ultra-goal/skills/ultra-goal/SKILL.md:717:`UserPromptSubmit` is not registered either ...
plugins/ultra-goal/skills/ultra-goal/references/agent-modes.md:178:a `ROUND_DEGRADED` finding that no code could ever produce ...
plugins/ultra-goal/skills/ultra-goal/scripts/validate_artifact.py:1394:degraded = [e for e in events if e.get("event") == "role_unavailable"]
plugins/ultra-goal/skills/ultra-goal/scripts/validate_artifact.py:1402:"ROUND_DEGRADED",
```

**What breaks:** an owner cannot tell whether role failure is a hook measurement or a run
claim, nor whether `UserPromptSubmit` is an actual shipped recovery channel. That ambiguity
undermines the project's load-bearing claims-versus-measurements distinction.

**What would settle it:** reconcile every shipped passage to one current contract, clearly
separating the Kimi recovery registration from the unbuilt wrong-activation proposal, and
run the same search with no contradictory hits. If `role_unavailable` is intentionally only
partial evidence, state its exact observation boundary.

### F6 — P2: zCode's implementation receipt claims host tags the code does not emit

**Location:** `scripts/install_user.py:49` and `:200`;
`docs/wip/mission-host-adaptation.md:314` and `:322-323`.

`HOOK_ARGS` is keyed by event name (`Stop`), but `_hook_command` looks it up by script name
(`goal_stop.py`). The generated legacy Claude registration therefore has no explicit
`--host claude`, contrary to §8.1. The same report describes the Kimi events as tagged,
while only Stop carries a host tag (and the manifest has five events, not four).

**Proven by:**

```console
$ python3 -c 'import pathlib,sys; sys.path.insert(0,"scripts"); import install_user as i; print(i._hook_command(pathlib.Path("/tmp/home"), "claude", "goal_stop.py"))'
"/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" "/tmp/home/.claude/skills/ultra-goal/scripts/goal_stop.py"
```

```console
$ jq '[.hooks[] | {event, tagged: (.command | contains("--host kimi"))}]' plugins/ultra-goal/kimi.plugin.json
[
  {"event":"Stop","tagged":true},
  {"event":"SessionStart","tagged":false},
  {"event":"PreCompact","tagged":false},
  {"event":"PostToolUseFailure","tagged":false},
  {"event":"UserPromptSubmit","tagged":false}
]
```

**What breaks:** the legacy install happens to select Claude only because
`DEFAULT_HOST == "claude"`; the claimed explicit-entrypoint invariant is dead configuration
and will drift if the default or installer scope changes. More immediately, §8.1 is not a
reproducible account of the range it asks reviewers to judge.

**What would settle it:** key the argument lookup by the value actually passed (or by the
event before it is discarded), add an assertion on the emitted command, and correct §8.1
to distinguish the one host-sensitive Stop tag from the other Kimi event registrations.

## Host-capability verification

I used fresh vendor reference pages on 2026-09-04 and installed binaries where noted.
The source field in `goal_hooks.py:84-117` is not treated as proof by itself.

| Host | Reference/runtime checked | Verdict on claimed capability and budget |
|---|---|---|
| Claude Code | [Hooks reference](https://code.claude.com/docs/en/hooks), [plugins reference](https://code.claude.com/docs/en/plugins-reference), installed `claude 2.1.260` | Reference confirms Stop re-entry and force-end after 8 consecutive blocks; installed binary names `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`. A gate budget of 7 is confirmed. Reference/binary also confirm the four selected events and that standard `hooks/hooks.json` plus an additional manifest hook file are loaded. `claude plugin validate plugins/ultra-goal --strict` returned `Validation passed`. No installed-plugin lifecycle was run. |
| zCode | [Hooks reference](https://zcode.z.ai/en/docs/hooks), [plugin reference](https://zcode.z.ai/en/docs/plugin) | Reference confirms force-end after 3 consecutive continuations, so budget 2 is confirmed. It documents the shared three-event subset, automatic `hooks/hooks.json`, and `CLAUDE_PLUGIN_ROOT` compatibility. `command -v zcode` returned no path, so actual loading and shell expansion on this machine are unverified. |
| Kimi Code | [Hooks reference](https://moonshotai.github.io/kimi-code/en/customization/hooks), [plugin reference](https://moonshotai.github.io/kimi-code/en/customization/plugins.html), installed `kimi 0.40.1` | Reference confirms the five registered events and that only `PreToolUse`, `Stop` and `UserPromptSubmit` can affect flow. The binary confirms one blocking Stop invocation per host turn, so capacity 1 is confirmed; F2 shows the implementation does not reset with that capacity. Reference and binary confirm `$ARGUMENTS`, not `$1`, for plugin commands; F1 applies. No installed-plugin lifecycle was run. |
| Codex | [Hooks reference](https://learn.chatgpt.com/docs/hooks), [plugin reference](https://developers.openai.com/plugins/build/plugins), installed `codex-cli 0.150.1` | Reference confirms the selected three events, Stop block continuation, manifest-hook replacement, and `PLUGIN_ROOT`/Claude-compatible root variables. Neither the reference nor a targeted binary string scan yielded a continuation cap. **`None` remains unverified**: absence from documentation and strings cannot prove unbounded behavior. No installed-plugin lifecycle was run. |

Commands supporting the binary part of that table:

```console
$ claude --version
2.1.260
$ strings -a ~/.local/share/claude/versions/2.1.260 | rg -F -m1 'For Stop/SubagentStop hooks, check stop_hook_active'
For Stop/SubagentStop hooks, check stop_hook_active ... Set CLAUDE_CODE_STOP_HOOK_BLOCK_CAP to raise this limit.

$ command -v zcode
# no output

$ kimi --version
0.40.1

$ codex --version
codex-cli 0.150.1
$ strings -a ~/.local/lib/node_modules/@openai/codex/node_modules/@openai/codex-darwin-arm64/vendor/aarch64-apple-darwin/bin/codex | rg -i -m20 'STOP_HOOK_BLOCK_CAP|consecutive (stop )?blocks|stop hook.*(cap|limit)|(?:cap|limit).*stop hook'
# no output, exit 1 — negative evidence only
```

## Open design mechanisms

Every objection below says what breaks and what would settle it. Items without a reproduced
break remain the owner's trade-off rather than findings.

| Mechanism from §5 | Exercise | Result |
|---|---|---|
| `## Acceptance` is not a task ledger; graph sequencing stays outside Stop | `pytest -q tests/test_validate_artifact.py::AcceptanceTests::test_a_numbered_acceptance_list_is_a_plan tests/test_package_surface.py::SweepFindingsTests::test_acceptance_is_required_only_where_it_earns_its_keep tests/test_package_surface.py::SweepFindingsTests::test_the_ledger_boundary_is_written_hard`; `rg -n 'graph|tasks\.json|plan\.md|dependenc|sequenc' plugins/ultra-goal/skills/ultra-goal/scripts/goal_stop.py` | `3 passed`; `rg` had no match (exit 1). No finding: the exercised artifact rule rejects a numbered ledger, and Stop contains no graph-sequencing path. |
| Two identical signatures release as stagnation | The two F3 repro commands above | Finding F3. What breaks and settlement are stated there. |
| Hardcoded `FROZEN_SECTIONS` | `pytest -q tests/test_goal_hooks.py::FrozenSpecTests` | Passed inside the 18-test group below; no reproduced bypass. Keeping the authority boundary outside the run-editable artifact is defensible. |
| Frozen digest is visible, not tamper-proof | `pytest -q tests/test_goal_hooks.py::FrozenSpecTests tests/test_validate_artifact.py::AuditTests` | `16 passed`; no finding. The implementation detects drift; it does not falsely claim cryptographic authorship. |
| `CONTEXT_LIMIT = 12000` and frozen-section budget | `pytest -q tests/test_goal_hooks.py::FrozenSpecTests tests/test_goal_hooks.py::InjectionBudgetTests tests/test_validate_artifact.py::FrozenSectionBudgetTests` | `18 passed`. No correctness finding; empirical fit beyond the one measured artifact remains explicitly unverified, as the mission requires. |
| Run anchor on every Stop | F3's mutating-anchor repro | Finding F3 shows a correctness failure when the anchor has side effects. The separate 540-second cost concern remains unverified until a real timed host run demonstrates unacceptable latency; I do not promote it to a finding on preference alone. |

## Dimensions exercised

| Dimension | Command | Result |
|---|---|---|
| Frozen range and patch hygiene | `git log --oneline --reverse 97d0780..HEAD`; `git diff --stat 97d0780..HEAD`; `git diff --check 97d0780..HEAD` | Six commits including the report; 26 files, +1291/-117; diff check clean. |
| Full executable suite, blind | `pytest -q` | `332 passed in 15.60s`. |
| JSON parse, manifest event subsets and eight-site version equality | `pytest -q tests/test_package_surface.py::PerHostHookRegistrationTests tests/test_package_surface.py::HostManifestTests::test_every_manifest_declares_the_same_version_as_the_skill tests/test_package_surface.py::AuditFixTests::test_the_gate_table_counts_the_hooks_that_ship`; `python3 -c 'import json, pathlib; fs=[p for p in pathlib.Path(".").rglob("*.json") if ".git" not in p.parts]; [json.loads(p.read_text(encoding="utf-8")) for p in fs]; print(f"parsed {len(fs)} JSON files")'` | `11 passed`; `parsed 11 JSON files`. No static-shape finding. |
| Claude plugin schema | `claude plugin validate plugins/ultra-goal --strict` | `Validation passed`. No static-schema finding. |
| Kimi command activation | `rg` plus installed-binary `strings` commands in F1 | Finding F1. |
| Per-host continuation lifecycle | `pytest -q tests/test_goal_hooks.py::ContinuationBudgetTests`; installed-binary and harness commands in F2 | Unit class `13 passed`; lifecycle counterexample is F2. |
| Stagnation/progress evidence | Both harness commands in F3 | Finding F3 in both directions. |
| Review range and non-Git fallback | Both shell commands in F4 | Finding F4. |
| Freeze and context budgets | `pytest -q tests/test_goal_hooks.py::FrozenSpecTests tests/test_goal_hooks.py::InjectionBudgetTests tests/test_validate_artifact.py::FrozenSectionBudgetTests` | `18 passed`; no finding. |
| Acceptance/graph boundary | The three exact tests in the design table | `3 passed`; no finding. |
| Audit join and event findings | `pytest -q tests/test_validate_artifact.py::AuditTests` | `11 passed`; no algorithmic finding, but F5 documents a contradictory public contract. |
| Hook interpreter and clock ceiling | `pytest -q tests/test_package_surface.py::AuditFixTests::test_every_hook_runs_without_python3_on_path tests/test_package_surface.py::AuditFixTests::test_the_stop_clock_is_the_documented_default` | `2 passed`; no finding. |
| Python syntax | `python3 -m py_compile plugins/ultra-goal/skills/ultra-goal/scripts/*.py scripts/install_user.py` | Exit 0; no syntax finding. |
| Repository hygiene | `pytest -q tests/test_package_surface.py::HygieneTests::test_package_ships_hooks_but_no_mcp_or_machine_specific_paths` | `1 passed`; no finding. |
| Shipped documentation consistency | `rg` command in F5 | Finding F5. |
| Implementer receipt accuracy | Python and `jq` commands in F6 | Finding F6. |

## Boundary and unverified work

- I made no implementation change, installation, publication, deployment, push or commit.
- Per the mission's prohibition on installation, I did not run the packaged plugin through
  a fresh install on Claude, Codex or Kimi. zCode is not installed. Those four live-load
  paths are **unexercised**, not clean.
- zCode's POSIX compatibility-variable path is reference-confirmed, but its Windows
  `commandWindows` behavior was not documented or executable here; it remains unverified.
- Codex's `continuation_budget=None` is explicitly unverified, not repeated as a fact.
- The reference pages and binaries support the static capability matrix; they do not
  substitute for §7's required real multi-turn loop. F1 and F2 already prevent claiming
  that acceptance for Kimi.

## Acceptance assessment

- **Four documented manifests/event subsets:** statically supported by reference comparison,
  JSON checks and package tests; live loading remains unverified.
- **One shared business-logic copy:** satisfied in the reviewed tree; host differences are
  entry-point data/manifest choices.
- **Real multi-turn loop within each host budget:** **not satisfied** because of F1 and F2;
  additionally no four-host live run was performed.
- **Reviewer sees the whole change:** **not satisfied** because of F4.
- **302-plus tests with command shown:** satisfied (`332 passed`).
- **Every unverified claim named:** §8.1 names its live-run and Codex-cap gaps; satisfied
  for the reviewed claims. This review adds the zCode/Windows boundary explicitly.
