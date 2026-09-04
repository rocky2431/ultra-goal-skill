# Mission: UltraGoal across four hosts, and the loop that is not looping

Owner: rocky2431. Implementer: **zCode**. Adversarial reviewers: **Claude Code** and
**Codex**, independently, three rounds. This file is the mission envelope and the shared
record; every party appends to its own section and edits nobody else's.

Working tree: `/Users/rocky243/Context Engineering/ultra-goal-adapt`, branch
`host-adaptation`, baseline `3dddfd1` (v2.8.0), **302 tests passing before any change**.

---

## 1. What this project is, so you can argue with it

UltraGoal turns "make an agent keep doing this" into a goal a host will actually hold to.
The owner interviews with the main skill, which compiles two files into `.goals/`:

- `<slug>.goal.md` — the specification plus the run's carried state
- `<slug>.decisions.md` — what was decided, what was rejected, and by whom

Then `/ultra-goal:goal-run <slug>` validates the artifact, writes `.goals/active` to arm
four hooks, and hands over the spec. Nothing in the plugin does anything in a project
without `.goals/active`.

The load-bearing ideas, in the order they matter:

1. **The anchor is an unarguable command whose exit code decides.** No model in the path.
   "No anchor, no artifact." It must cross the whole path — a green unit suite over a
   broken product is the failure it exists to catch.
2. **Three outcomes, never two: green / red / unknown.** An anchor that cannot run is
   *unknown*, not failed. A timeout is unknown: a clock cannot see whether work landed.
   Folding unknown into either verdict is how a mechanical gate starts lying.
3. **Claims versus measurements.** The run writes claims — the artifact, the carry-over,
   the commit subject, its reviews. Hooks write evidence to `<slug>.events.jsonl`,
   append-only, never edited by the run. `validate_artifact.py --audit` joins them; the
   first row where they disagree is the answer to "where did this go wrong".
4. **Three freeze tiers.** *Frozen* (intent, boundary's refusals, anchor, means labels —
   observed by a digest). *Firm* (thresholds, ceiling, verifier, cadence, dropping a
   droppable means — costs one row in `decisions.md`). *Fluid* (state, lessons, next,
   method).
5. **A wrong term gets challenged, not edited.** `## Challenges from the run` in
   `decisions.md` is the only part of that file the run authors. It is the one thing the
   run knows that the design side cannot: which term did not survive contact.
6. **Context isolation cures contagion of the author's argument; model independence cures
   shared blind spots.** They are different diseases and cost differently. A same-vendor
   fresh-context subagent cures the first completely and the second not at all.
7. **A hook inlines only what it alone possesses. Everything already on disk gets a
   path.** The Stop payload was 4,683 characters per turn on a real artifact; it is now
   ~660 and the same size whatever the artifact holds.
8. **Mechanise only when the measured quantity IS the judged quantity.** Counters,
   regexes, similarity scores, digests and timeouts are observations, never verdicts.
   Every hard gate must name its invariant, its authoritative fact source, the effect it
   blocks, and a reachable repair path — or it becomes advisory.

Read these before writing code: `plugins/ultra-goal/skills/ultra-goal/SKILL.md`, and in
`plugins/ultra-goal/skills/ultra-goal/references/`: `document-system.md`,
`adversarial-review.md`, `agent-modes.md`, `anti-patterns.md`, `graph-topology.md`.
`docs/wip/theory-sweep.md` sections 16-18 hold the recent findings and why each fix took
the shape it did.

## 2. The four hosts, and what "perfectly adapted" has to mean

Claude Code, Codex, Kimi Code, zCode. All four have hooks and plugins; their protocols,
continuation limits and context-recovery paths differ. Codex has already produced a
capability comparison and a patch against this exact baseline:

- `/Users/rocky243/Documents/Codex/2026-09-04/overthinking-agent-md/outputs/ultra-goal-host-adaptation.md`
- the patch and adapted tree referenced from that document

**Read it. You may adopt, adapt or reject any part of it — with an argument, in writing.**
It is one agent's proposal, not an instruction, and one of its claims about this repository
has already been shown to rest on a misread source (see §4).

Adapted means, concretely:

- Every host loads the plugin through **its own documented manifest**, and each manifest
  registers **only events that host documents**. Registering an event a host does not
  support is either an error or silence, and silence here means a dead gate.
- One copy of the business logic. Host differences live at the entry points, not in four
  forks of the gate.
- Where a host cannot do something (Kimi cannot inject context from
  `SessionStart`/`PostCompact`, per Codex's document — verify it), the adaptation uses
  that host's real alternative and **says in the artifact that it degraded**, rather than
  pretending parity.
- **Definitions come from each vendor's reference documentation.** Not from blogs, not
  from strings printed by a binary in isolation, not from an example that happens to work
  on this machine. An example shows one thing that works; a reference says what is
  allowed. When two authoritative sources conflict, satisfy both and record the conflict.
  Cite the URL or the file path for every capability claim you make.

## 3. The owner's ruling, already made

**One anchor check is one turn.** `ceiling: 40` in a stop condition means forty anchor
checks, not forty conversation turns. This follows the owner's own artifact, whose stop
condition reads "40 red" and whose acceptance reasons about the number of red results.

Consequence you must handle: a single host turn can now produce several anchor checks, so
the run's commit subject (`goal(<slug>) turn <N>: … [anchor: green|red|unknown]`) and the
gate's own turn count can diverge. `--audit` joins claims to measurements and must keep
working. Decide how, and say why in the report.

## 4. The two defects that started this, with their evidence

### 4.1 The loop is not looping — one continuation instead of eight

`goal_hooks.run_hook` returns 0 as soon as `stop_hook_active` is true, so the gate blocks
at most once per host turn. Read from the running Claude Code binary (2.1.260), not from
the docs:

```js
let Vd = a.CLAUDE_CODE_STOP_HOOK_BLOCK_CAP ?? 8;
if (Vd > 0 && qd > Vd) return … `A hook blocked the turn from ending ${qd}
  consecutive times — overriding and ending turn. ` +
  "For Stop/SubagentStop hooks, check stop_hook_active in the input and return
   success while it's true. Set CLAUDE_CODE_STOP_HOOK_BLOCK_CAP to raise this limit."
```

So the host counts consecutive blocks, default cap **8**, raisable by environment
variable. **The advice about `stop_hook_active` is printed only when the cap is exceeded**
— it is post-mortem advice, not general guidance, and reading it as general guidance is
how the current one-shot guard got written.

Confirmed live: the owner's real run left exactly one `anchor_checked` event and the turn
ended. The gate gave the run one nudge, not a loop; `ceiling: 40` is unreachable by the
gate alone.

The shape the fix probably wants: keep blocking while the anchor is red, count consecutive
blocks in the event log (a measurement, hook-written), and **stop blocking a little before
the host's cap** so the last word is the gate's own reason rather than the host's
"overriding and ending turn" warning. The host cap is the backstop, not the budget.
**Challenge this shape if you have a better one** — including whether a run should ever be
allowed to end with a red anchor, and what an unattended run is supposed to do when the
continuation budget is spent.

Each host has its own limit, and they are not the same number. zCode's and Kimi's are
claimed in Codex's document; **verify them against each vendor's reference** and make the
budget a per-host fact, not a constant copied from Claude Code.

### 4.2 The reviewer reviews an empty diff

`plugins/ultra-goal/skills/review/SKILL.md` runs `git -C . diff HEAD`, which shows only
uncommitted work — while the run commits once per turn. At proposed completion the
reviewer therefore sees almost nothing and can honestly report "no findings", which the
run then treats as coverage. `critic` inherits the same defect.

Codex's proposal: record the starting Git revision when the gate is armed and review
`<start>..HEAD`. Note the wrinkle its own document raises — uncommitted changes that
predate arming also land in that diff, so the reviewer still has to attribute by
`## Boundary`.

## 5. Everything else is challengeable, and here is how to challenge it

The owner has said the whole design is open, not just these two fixes. So: if a mechanism
in this repository fails the criterion in §1.8, say so. Candidates the reviewers already
argue about, listed so you do not have to rediscover them:

- **`## Acceptance` is not a task ledger** — the boundary is drawn in
  `document-system.md`. A graph's eighty ordered tasks belong to a workflow runtime, and
  `graph-topology.md` argues the Stop hook must never become the sequencer. Attack it.
- **Two identical anchor signatures in a row releases the stop** as "not progressing".
  This is a heuristic about stagnation and it cannot prove the code is not advancing.
- **`FROZEN_SECTIONS` is hardcoded** in `goal_hooks.py` rather than declared in the
  artifact, deliberately: a declared freeze is a freeze the run can edit. Thresholds
  (`ceiling:`, `budget:`) are declared; what counts as frozen is not.
- **The frozen digest is not tamper-proof** and does not claim to be. It makes a moved
  goalpost *visible* in `--audit` and in `git log`.
- **`FROZEN_SECTIONS_OVER_BUDGET` and `CONTEXT_LIMIT = 12000`** — the limit is derived
  from one real artifact. That is better than the previous guess and still one data point.
- **The gate runs the anchor on every Stop**, including a turn that changed nothing. Known
  cost, deliberately unfixed for lack of a reproduced failure. The owner's anchor has a
  540-second budget, so this is not hypothetical any more.

A challenge that names *what breaks* and *what would settle it* is an objection. Without
both it is a preference, and preferences are the owner's.

## 6. Working rules

- **Tests first for every logic change.** Write the failing test that defines the contract,
  then the code. For a bug, reproduce it in a test first.
- **Never weaken an assertion, skip a test, or edit an expectation to get green.** Several
  assertions in this suite encode contracts that changed legitimately — when that happens,
  rewrite the assertion to the *new* contract and say so in the report. If a shipped
  document needs reflowing to satisfy a pinned phrase, reflow the document.
- **Evidence for every claim.** "Tests pass" needs the exact command and its real output.
  A capability claim about a host needs a URL or a file path. Fabricating source, runtime
  state, logs, or test results is the most serious violation available here.
- Code, identifiers, comments, commit messages and test names in **English**. This file
  and any report the owner reads may be Chinese.
- Every changed line traces to this mission. Do not improve adjacent code.
- The eight version sites are pinned equal by a test; a bump touches all eight.
- Do not push, do not install, do not publish. Commit on `host-adaptation` only.

## 7. Protocol

1. **zCode implements.** Commit in coherent steps on `host-adaptation`. Then write §8.1:
   what changed, what you refused and why, what you could not verify, and the exact test
   command with its output.
2. **Round of adversarial review.** Claude Code and Codex review the same frozen diff
   independently, neither reading the other's report first, each writing to its own file
   under `docs/wip/reviews/`. Every finding cites `file:line` and the command whose output
   proves it. A dimension reported as clean with no command named counts as unexercised.
3. **zCode answers each finding** with evidence or a change — never with a rebuttal alone —
   and sorts every point into agreement, evidence-backed disagreement, or concern-based
   disagreement.
4. Three rounds of 1-3, or fewer if a round converges with no findings that survive.
5. **Claude Code and Codex then produce one joint conclusion for the owner**, including
   every point where they still disagree. Two reviewers who both say "looks fine" have
   produced one opinion reported twice; where you agree, say what evidence made you agree.

Done means: the four manifests register only events their host documents, the gate drives
a real multi-turn loop within each host's own continuation budget, the reviewer sees the
whole change, 302-plus tests pass with the command shown, and every unverified claim is
named as unverified.

---

## 8. Records

### 8.1 zCode — implementation

**Round 1.** Five implementation commits on `host-adaptation` (frozen diff
`3dddfd1..a7ef7e1`): `b5143a7` (4.1, the loop), `77e8cb0` (4.2, the reviewer's
diff), `a8b2d1d` (the four manifests), `dc2f70d` (shipped documents + v2.9.0,
all eight version sites), `a7ef7e1` (one-block-host deny addendum). Not pushed,
not installed, not published.

#### Test command and its real output

```
$ python3 -m pytest tests/ -q
332 passed in 19.08s
```

Baseline, re-run for this report at the mission's own baseline commit:

```
$ git checkout 3dddfd1 && python3 -m pytest tests/ -q
302 passed in 7.67s
```

Also run, real output: `claude plugin validate plugins/ultra-goal` →
`✔ Validation passed` (and again under `--strict`, which fails on unrecognized
fields — relevant because this round adds a `hooks` field to two manifests).
Version: 2.8.0 → 2.9.0 at all eight sites, equality pinned by
`test_every_manifest_declares_the_same_version_as_the_skill`.

#### What changed, per defect

**4.1 — the loop.** `goal_hooks.run_hook` no longer hard-exits on
`stop_hook_active`; a continuation is a gated turn. The guard against a gate
that denies forever is now the per-host continuation budget in
`goal_hooks.HOSTS` (`plugins/ultra-goal/skills/ultra-goal/scripts/goal_hooks.py`),
each entry carrying its citation:

| Host | Budget (consecutive blocks) | Source, read directly |
|---|---|---|
| claude | 7 | host cap 8: `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` default, Claude Code 2.1.260 binary (the mission's own §4.1 quote) |
| zcode | 2 | host cap 3: "After 3 consecutive continuations the run is force-ended" — https://zcode.z.ai/en/docs/hooks |
| kimi | 1 | the host triggers a blocking Stop only while `!stopHookContinuationUsed`, reset in `notifyTurnEnded` — Kimi 0.40.1 binary (`/Users/rocky243/.kimi-code/bin/kimi`, `runStepLoop`); its reference documents no cap |
| codex | none | no cap in https://learn.chatgpt.com/docs/hooks and none greppable in the 0.150.1 binary; the gate's own ceiling binds |

An unknown `--host` gets budget 1, never Claude's 7. Every `anchor_checked`
event now records `"blocked": true|false` (the streak measurement);
`goal_stop._block_streak` counts trailing blocks and the gate releases one
**before** the host's cap, writing a `continuation_budget_spent` event that
`--audit` surfaces as a `CONTINUATION_BUDGET_SPENT` advisory
(`validate_artifact.py`). The release message names the commit subject with the
gate's turn number; on claude it also names `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`.

**The not-progressing rule had to change with it, and this was forced by a
test, not chosen in the abstract.** A deterministic anchor prints the same
failing summary until the work lands, so under the output-only rule the second
check released the turn — 4.1's defect in a new costume. Stagnation is now
measured on what the anchor can see: `goal_stop._tree_digest` digests
`git rev-parse HEAD` + `git status --porcelain` + `git diff HEAD`, all
excluding `.goals` (whose event log grows every check and would mask
stagnation), and `_stagnant` releases only when neither the output nor the
tree moved. Projects without Git keep the old output-only rule as fallback.

**4.2 — the reviewer's empty diff.** `goal-run.md` step 3 now records
`git rev-parse HEAD > .goals/$1.baseline` (`none` without Git); `review` and
`critic` SKILL.md read `git diff "$(cat .goals/$1.baseline)"` — working tree
against the arming revision, so committed *and* uncommitted work shows — plus
`git status --porcelain` for untracked files a diff cannot show. The
boundary-attribution wrinkle Codex's document raised is stated in the reviewer
skill itself: pre-arming uncommitted work falls inside the range and is
attributed by `## Boundary`. The critic is told the range is the same one the
reviewer saw, so findings citing files outside it are findings about the
review. The baseline is committed with the run's first turn, so moving it
afterwards is visible in `git log`.

**The four manifests.** One logic copy; host facts live at entry points.
Layout and the loading semantics each rest on (binary- or reference-)verified
ground:

- `hooks/hooks.json` — auto-discovered by Claude Code **and** zCode, so it
  carries only events **both** document: Stop, SessionStart,
  PostToolUseFailure. Its Stop entry self-tags zCode via
  `${ZCODE_PLUGIN_ROOT:+--host zcode}` (the env variable zCode's hooks
  reference documents for hook commands; Claude Code does not set it), and an
  untagged run defaults to claude. Verified in `sh`: unset expands to nothing,
  set expands to `--host zcode`; the full command line was run end-to-end
  against a fixture and blocks/allows correctly.
- `hooks/claude.json` — PreCompact only, named by `.claude-plugin/plugin.json`
  `"hooks"`, which Claude Code treats as **additional** files on top of
  auto-discovery — read from the 2.1.260 binary's own schema description
  ("manifest.hooks should only reference additional hook files").
- `hooks/codex.json` — Stop `--host codex`, SessionStart, PreCompact; named by
  `.codex-plugin/plugin.json` `"hooks"`, which **replaces** the default file
  location (documented at developers.openai.com/plugins/build/plugins), so
  Codex never sees the shared file and never inherits the
  `PostToolUseFailure` it does not document. Codex loses the
  `role_unavailable` recording for the same reason — the run's report is the
  only record of a degraded round there, which is a declared loss, not parity.
- `kimi.plugin.json` — the four events tagged `--host kimi`, Stop timeout
  200 → 600 (200 would kill a 540s-declared anchor into permanent `unknown` —
  the clock-cap defect class), plus `UserPromptSubmit` → new
  `goal_prompt_submit.py`: Kimi's SessionStart output is fire-and-forget
  (reference: only PreToolUse, Stop and UserPromptSubmit affect the flow), so
  the documented alternative injects one fixed-size pointer line per prompt —
  a declared degradation, tested to be the same size whatever the artifact.
- zCode needs no extra file: the shared core is exactly its documented subset.
  `install_user.py`: Stop timeout 200 → 600 and the registration tags
  `--host claude`.

**§3 — one anchor check is one turn.** The gate's counter already counted
checks, so its meaning is unchanged; what changed is that a host turn can now
hold several. The run's commit subject cites the number from the gate's most
recent message — spelled out in the budget-spent release, in the one-block-host
deny reason, and in `goal-run.md` ("`<N>` is the number in the gate's most
recent message, not a number you count yourself"). `--audit`'s join key is
unchanged; a run citing a number the gate never measured is caught by the
existing `CLAIM_UNWITNESSED`.

#### Answers to the shape questions §4.1 asked

- **May a run end a turn with a red anchor?** In exactly three ways — budget
  spent, not progressing, ceiling — each loud (event + message + commit
  subject). The alternative, never releasing, is mechanically impossible
  against a host cap and would only trade the gate's last word for the host's
  force-end warning.
- **What does an unattended run do when the budget is spent?** It parks:
  carry-over written, committed red, turn ended. On Claude Code the message
  names `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` so the owner can raise 8 → N; at the
  default, a ceiling of 40 checks costs roughly five owner prompts (8 checks
  per host turn). That is the host's mechanical limit — stated, not hidden. On
  Kimi every turn parks after one block, so long unattended runs there are
  effectively attended. Codex, with no known cap, does not park at all.

#### Codex's proposal: adopted, adapted, rejected

- **Adopted**: the baseline-diff shape for 4.2 including the wrinkle; per-host
  budgets as cited facts (their CC=8 / zCode=3 / Kimi=1-per-turn claims were
  re-derived from primary sources and all three held; their Kimi one-continuation
  claim, which their own doc marks as binary-derived, is now independently
  confirmed at `runStepLoop`).
- **Adapted**: Kimi's `UserPromptSubmit` alternative — as a one-line pointer,
  not spec injection (per-prompt cost must be fixed-size; the full spec is
  what SessionStart injection is for, and Kimi cannot have that).
- **Rejected**: their `goal_host.py --host kimi` input/output conversion shim
  and six-event Kimi declaration — a translation layer is a second copy of
  host knowledge, against the mission's one-logic-copy rule; `--host` at the
  manifest entry points does the same job with no shim. Also rejected their
  `hooks/zcode.json` (holding PostToolUseFailure): zCode unions
  auto-discovery with manifest declarations, so a zcode.json re-registering
  PostToolUseFailure would double-register it. Their
  `hooks/hooks.json = Stop + SessionStart`-only split was widened: PostToolUseFailure
  belongs in the shared file because both auto-discovering hosts document it.

#### Objections (§5), each with what breaks and what would settle it

1. **Anchor re-runs under continuations are now the dominant clock cost.**
   What breaks: a 540s anchor with a 7-block Claude Code budget can spend
   about an hour of anchor time per host turn — the owner's clock spent on
   checks, not work. What would settle it: the tree digest this round already
   measures "nothing changed"; skipping the anchor and re-reporting the
   cached outcome (without advancing the turn counter) is now cheap to build.
   It stays unbuilt because its failure case — a Stop with no work since the
   last check — has not been reproduced under the new loop shape, and the
   stagnant pair costs at most one anchor run today. One real run's timing
   data settles build/don't-build.
2. **The tree digest sees untracked paths, not untracked content.** What
   breaks: a run whose work only rewrites the *content* of untracked files
   (scratch outputs, build dirs outside git) reads as stagnant if the anchor
   output is also identical. What would settle it: hashing untracked file
   content, or the first real run that trips it — whichever comes first.
3. **`CONTEXT_LIMIT = 12000` and `FROZEN_SECTIONS_OVER_BUDGET` still rest on
   one artifact.** What breaks: nothing silently — overruns are loud since
   2.7.2 — but the budget's *fit* is one data point. What would settle it:
   the next real artifact's measurement.
4. **`FROZEN_SECTIONS` hardcoded in `goal_hooks.py` — defended, not
   challenged.** A freeze declared in the artifact is a freeze the run can
   edit; keeping the list outside the artifact's reach is the property, and
   the cost (new frozen sections need a code change) is the price of it.
5. **The shared `hooks/hooks.json` now carries one zCode-specific shell
   expansion.** What breaks: a hypothetical CC-compatible host that
   auto-discovers this file, has a cap below 7, sets no `ZCODE_PLUGIN_ROOT`,
   and runs no POSIX shell would get claude's budget and meet its host's
   force-end (backstop, not corruption). What would settle it: zCode
   documenting replace-semantics for its manifest `hooks` field (its reference
   was asked and does not answer), which would let every host own its file.

#### Tests rewritten to new contracts (none weakened silently)

- `test_stop_hook_active_is_a_hard_early_exit` →
  `test_stop_hook_active_still_reaches_the_handler`: the forever-guard moved
  from an input flag to the budget.
- `test_kimi_hooks_name_the_same_events_as_the_claude_manifest` → asserts the
  shared core is contained in Kimi's set; identical event sets across hosts is
  exactly what this round removes.
- `test_the_gate_table_counts_the_hooks_that_ship` → five hooks, per-host
  registration, union of events across files.
- Hygiene expectations for the script list and the shared file's event list.
- **Flagged for the reviewers' ruling**: the package hygiene scan
  (`test_package_ships_hooks_but_no_mcp_or_machine_specific_paths`) is now
  scoped to the shipped tree and excludes `docs/wip/`. Pre-existing failure:
  the mission envelope itself (commit `97d0780`) cites two absolute paths
  (`docs/wip/mission-host-adaptation.md:7,66`) and the old scan red-ed the
  suite on the owner's own notes — verified by `git stash` before any of my
  changes touched anything. I did not edit the envelope (protocol: my section
  only) and did not delete the guard: it still scans everything that installs.

#### What I could not verify — named, not smoothed over

1. **Codex's budget of `None`.** No cap in the reference or the binary, but no
   live Codex goal run proved that unbounded blocking is honored. If a hidden
   cap exists, the host's force-end is the backstop.
2. **zCode's union semantics.** Inferred from its reference's "do not point
   the manifest at the same file again"; the merge-vs-replace question for a
   *different* path is explicitly unanswered by that page. A live zCode plugin
   install would settle it — and installing is outside this mission's rules.
3. **Claude Code's manifest-hooks-are-additional.** Read from the 2.1.260
   binary's schema text and consistent with `plugin validate --strict`
   passing; not proven by installing the plugin into a live session.
4. **Kimi's one-continuation-per-turn.** Binary-verified control flow, not
   observed in a live Kimi goal run.
5. **The `${ZCODE_PLUGIN_ROOT:+--host zcode}` expansion under zCode's real
   hook execution.** Verified in `sh` and end-to-end from a shell; zCode's own
   command invocation path was not exercised.
6. **No live four-host run.** The loop fix is proven by git-backed tests that
   model continuations, plus one manual end-to-end invocation of the exact
   manifest command — not by an unattended run on any host. The mission's own
   minimal acceptance (two failures then success, pause, context recovery, a
   graph node, independent review) remains unexecuted.
7. **The baseline-diff review flow** is file changes plus tests; no live
   review round exercised it.
8. **Kimi's plugin-hook working directory** (plugin root; project from event
   `cwd`) is from Codex's document and was not re-verified against Kimi's
   plugin reference.

#### Refused, with reasons

- **No live installs or runs on any host** — mission rule ("do not push, do
  not install, do not publish"), so every host-behavior claim above stops at
  reference, binary, or shell evidence and is labeled accordingly.
- **No `goal_host.py` conversion shim** — second copy of host knowledge;
  rejected in favor of `--host` at entry points.
- **No anchor-skip optimization** — no reproduced failure under the new loop
  shape (objection 1 above records the settlement condition).
- **No edit to any section of this envelope but §8.1.**

**Round 2.** Four implementation commits (`434d2c2..3a108e6`): `1ad2d64`
(Codex F2 + F3 + Claude F-1 — the turn-scoped budget and the stagnation
sensor), `0da0a96` (Codex F1 + F4 — the command contract and the review
baseline), `f15a003` (Claude F-4 + Codex F5 + F6 — the Kimi manifest, the
shipped documents, the installer tag), `3a108e6` (v2.9.1, all eight sites).
Not pushed, not installed, not published.

#### Round-2 test command and its real output

```
$ pytest -q
347 passed in 48.24s
$ pytest -q
347 passed in 27.24s
```

(332 at round 1; +15 tests, every one written failing-first.) Also run,
real output: `claude plugin validate plugins/ultra-goal --strict` →
`✔ Validation passed`.

#### Codex F2: the observable fact, and why it is observed rather than inferred

The scoping fact for Kimi is the **`prompt_submitted` event written by this
plugin's own registered `UserPromptSubmit` hook**. A host turn on Kimi begins
with a user prompt; the hook runs because and only because the host submitted
one, so the event is the invocation itself recorded — nothing is inferred
about when some previous turn ended. Kimi's reference lists UserPromptSubmit
among the three flow-affecting events
(moonshotai.github.io/kimi-code/en/customization/hooks), and its 0.40.1
binary resets the one-block guard in `notifyTurnEnded` (re-verified here:
`strings -a ~/.kimi-code/bin/kimi | grep -c stopHookContinuationUsed` → `10`;
`notifyTurnEnded` present). Two further boundaries are observed the same way:
an allow written by the gate itself (an allow ends every host's chain), and
`stop_hook_active` read as a boundary **only** where its semantics are
documented in words — Claude Code ("check stop_hook_active … while it's
true", hooks reference + 2.1.260 cap message) and Codex ("Whether this turn
was already continued by Stop", learn.chatgpt.com/docs/hooks). zCode's
reference names the field in Stop's input table but spells no meaning, and
Kimi passes camelCase `stopHookActive` constant-false by construction (it is
read only inside the `!used` guard) — reading either as "fresh chain" would
be inference from a name, so neither is read, and that residual is named
below.

#### Round-2 answers, one line per finding

- **Codex F1 (Kimi cannot arm `$1`) — agreement.** `$ARGUMENTS` everywhere
  in `goal-run.md` (documented by Claude Code, zCode and Kimi; Claude Code's
  `$1` is its *second* argument, so the old file bound the slug
  deterministically on zCode alone), the validator tries all four documented
  plugin-root variables, and where none reaches command execution — Kimi's
  reference documents none — it declares "not machine-validated" loudly
  instead of half-expanding a path. `pytest -q
  tests/test_package_surface.py::AuditFixTests::test_the_command_binds_the_slug_through_the_documented_placeholder
  tests/test_package_surface.py::AuditFixTests::test_the_validator_step_degrades_loudly_when_no_root_reaches_it
  tests/test_package_surface.py::ArmingRangeContractTests::test_the_expanded_prompt_binds_the_slug_end_to_end`
  → `3 passed`; the last drives the real fenced command with Kimi's
  documented substitution and shows `.goals/active` receives exactly `demo`.
- **Codex F2 (budget leaks across host turns) — agreement.** Streak scoped
  to observed boundaries (above). `pytest -q
  tests/test_goal_hooks.py::ContinuationBudgetTests` → `18 passed`, including
  `test_two_fresh_kimi_turns_each_get_their_one_block` (both fresh turns
  block, no `continuation_budget_spent` event) and
  `test_a_stop_reporting_a_fresh_chain_resets_the_streak`; same-turn re-entry
  stays bounded in `test_kimi_blocks_at_most_once`.
- **Codex F3 (stagnation sensor, both directions) — agreement.** The
  comparison base is now the post-anchor state the previous check recorded,
  and untracked-not-ignored content is hashed (1 MiB per file, `.goals`
  excluded). `pytest -q
  tests/test_goal_hooks.py::ContinuationBudgetTests::test_a_mutating_anchor_cannot_pose_as_progress
  tests/test_goal_hooks.py::ContinuationBudgetTests::test_edits_inside_an_existing_untracked_file_are_progress`
  → `2 passed` (both failed before the change).
- **Codex F4 (baseline `none` errors; re-arm empties the diff) —
  agreement.** Baseline line is `-s`-guarded (write-once); review and critic
  branch `none`/missing into "no review range can be formed — report the
  review as unavailable", and check `merge-base --is-ancestor` before
  diffing. The ancestor check lives at review time, not arming time, because
  at arming the baseline is HEAD and trivially an ancestor — it can only
  stop being one later. `pytest -q
  tests/test_package_surface.py::ArmingRangeContractTests` → `4 passed`
  (write-once across a commit, none-branch executable output, non-ancestor
  reported, slug bound end to end).
- **Codex F5 (mutually exclusive evidence contracts in shipped docs) —
  agreement.** SKILL.md, README and agent-modes.md now state one contract:
  order declared; failure measured where the host fires
  `PostToolUseFailure` (Claude Code, zCode, Kimi → `role_unavailable` →
  `ROUND_DEGRADED`); Codex documents no such event and the run's report is
  the only record there; adequacy is always a claim; and UserPromptSubmit's
  Kimi registration is separated from the unbuilt wrong-activation proposal.
  Codex's own search rerun on this tree returns consistent contracts only
  (`rg -n -C 1 'UserPromptSubmit.*not registered|UserPromptSubmit.*Kimi
  only|declared and reported, not measured|role_unavailable|ROUND_DEGRADED'
  README.md plugins/ultra-goal/skills/ultra-goal/SKILL.md
  plugins/ultra-goal/skills/ultra-goal/references/agent-modes.md
  plugins/ultra-goal/skills/ultra-goal/scripts/validate_artifact.py` →
  hits, all stating the same contract). `pytest -q
  tests/test_package_surface.py::RolesByStageTests::test_the_degradation_contract_is_the_same_everywhere`
  → `1 passed`.
- **Codex F6 (receipt claims host tags the code does not emit) —
  agreement.** `HOOK_ARGS` is keyed by script name as `_hook_command` looks
  it up, so the generated registration now really carries `--host claude`;
  `pytest -q
  tests/test_hook_registration.py::RegistrationTests::test_the_registered_stop_command_names_its_host`
  → `1 passed`. The round-1 receipt errors are corrected below.
- **Claude F-1 (Kimi's Stop has no allow-channel; five steps end in
  silence) — agreement.** The reviewer's own addendum names the documented
  repair and it is built: `goal_prompt_submit.py` now carries the gate's
  last decision from the event log on the next prompt, fixed-size, beside
  the pointer; `_allow` gains no undocumented `message` field, per the same
  addendum's warning. `pytest -q
  tests/test_goal_hooks.py::PromptSubmitTests` → `6 passed`, including
  `test_the_prompt_carries_the_gate_s_last_decision` (pointer plus verdict,
  two lines, bounded).
- **Claude F-4 (Kimi's SessionStart cannot deliver by design) —
  agreement.** SessionStart is dropped from `kimi.plugin.json` (four events
  remain; the manifest's own description says why), rather than given the
  pre-compact treatment — `goal_pre_compact.py` earns its place by writing
  an event, and `goal_session_start.py` has nothing to record. `pytest -q
  tests/test_package_surface.py::HostManifestTests::test_kimi_hooks_name_the_same_events_as_the_claude_manifest
  tests/test_package_surface.py::PerHostHookRegistrationTests::test_kimi_registers_four_events_all_documented`
  → `2 passed`.
- **Claude F-5 (one docstring spoke of one `stop_hook_active` spelling) —
  agreement.** `run_hook`'s docstring and the `HOSTS` entries now name both
  spellings and which hosts' references document meaning; the `HOSTS`
  citation test now also pins exactly which hosts' chain flags are read
  (`pytest -q
  tests/test_goal_hooks.py::ContinuationBudgetTests::test_every_host_budget_carries_a_citation`
  → `1 passed`).
- **Claude F-6 (`codex plugin read` not reproducible) — agreement.**
  Re-verified here: `codex --version` → `codex-cli 0.150.1`; `codex plugin
  read --path plugins/ultra-goal` → `error: unrecognized subcommand 'read'`
  (subcommands: add, list, marketplace, remove, help). The claim originates
  at line 100 of the external capability document this mission cites and is
  **retired from this repository's evidence set**: nothing in the repo
  repeats it (`rg 'plugin/read|plugin read|原生插件' README.md plugins/`
  → no hits), and no load-bearing Codex fact rests on it — the manifest
  semantics come from developers.openai.com/plugins/build/plugins and the
  event table from learn.chatgpt.com/docs/hooks. The "2 hooks" count also
  cannot describe this tree's three-event `codex.json`.
- **Claude's withdrawn F-2, F-3, F-7 — no change.** ZCODE_PLUGIN_ROOT
  discrimination, Codex's manifest-replaces-discovery split, and Claude
  Code's hooks-are-additional merge stand as round 1 left them; a withdrawn
  finding is not a soft request.

#### Round-1 receipt corrections (Codex F6's second half)

- Round 1 said Kimi's events were "tagged `--host kimi`". Wrong twice: the
  manifest held **five** events and only Stop carried the tag. The tag is
  correct as design (only the gate is host-sensitive; the recovery hooks
  take no `--host`) — the receipt was not. Kimi now registers four events,
  still with Stop alone tagged.
- Round 1 said the installer "tags `--host claude`". It did not —
  `HOOK_ARGS` was keyed by event name and never matched (F6 above). Now it
  does, and a test holds it.

#### New and carried unverified claims, named

1. **zCode's `stop_hook_active` semantics.** Its reference lists the field
   among Stop's inputs but documents no meaning; it is not read as a
   boundary. Residual: a zCode Stop chain ended without an observed allow
   (owner interrupt mid-chain) carries its tail into the next turn, so a
   fresh chain can park one block early (budget 2). Settled by zCode
   documenting the field's meaning, or one live zCode run.
2. **Codex's command-argument contract.** Neither codex reference page
   reachable here documents a command-body placeholder, so `$ARGUMENTS` on
   Codex commands is unverified (Claude Code, zCode and Kimi each document
   it). Codex's own plugin manifest declares the commands file; live
   invocation settles it.
3. **The prompt marker's live delivery on Kimi.** The reference documents
   UserPromptSubmit; the binary implements `$ARGUMENTS` and the per-turn
   Stop guard (re-verified here by `strings`); no live Kimi session ran
   this hook. Also unverified: whether Kimi fires UserPromptSubmit for the
   internally-appended Stop continuation — if it did, the marker is
   harmless on Kimi (one Stop per turn means no same-turn budget to
   mis-scope), but it is unmeasured.
4. **The 1 MiB untracked-content bound** in the tree digest: an edit
   confined past the first mebibyte of an untracked file is invisible to
   the sensor. The release it could cause is loud ("not progressing" plus
   the obligation text), not silent.
5. **Upgraded-mid-flight stagnation base.** Events written before this
   round carry pre-anchor digests; a mutating anchor can hide stagnation
   for at most one check after the upgrade, then the new base takes over.
6. Carried unchanged from round 1: Codex's `None` budget, zCode's union
   semantics, Claude Code's manifest-hooks-additional (binary-read), the
   `${ZCODE_PLUGIN_ROOT:+…}` expansion under zCode's real command
   invocation, no live four-host run, no live baseline-diff review round,
   Kimi's plugin-hook working directory.

**Round 3.** One implementation commit (`f77e7c2`) plus the release commit
(`27a8c50`, v2.9.2 at all eight sites). One commit instead of one per
finding because the findings share three files — `SKILL.md`, `README.md` and
`tests/test_package_surface.py` each carry halves of both P1s — and a split
would have left every intermediate commit half-described. Not pushed, not
installed, not published.

#### Round-3 test command and its real output

```
$ pytest -q
358 passed in 27.11s
```

(347 at round-2 close; +11, every one written failing-first.) Also run, real
output: `claude plugin validate plugins/ultra-goal --strict` →
`✔ Validation passed`.

#### Round-3 answers, one line per finding

- **Codex F1 (arming is fail-open) — agreement.** The validate step and the
  arming step are now ONE fence (`goal-run.md` §2): the validator's error
  stops the script with `|| exit 1` before `.goals/active` is written, the
  candidate roots gained Kimi's documented managed-install default
  (`$KIMI_CODE_HOME/plugins/managed/ultra-goal`, `~/.kimi-code` when unset —
  the plugin reference documents the location, the config reference and the
  0.40.1 binary the default), and where no documented root reaches, arming
  REFUSES and names what the owner does instead (validate by hand from the
  install root — Kimi's managed copy, Codex's `~/.codex/plugins/cache/
  <marketplace>/ultra-goal/<version>` — then re-run with `PLUGIN_ROOT`
  exported or arm by hand). Kimi's primary path stays usable because it
  validates for real through that documented default. The reviewer's own
  repro, re-driven on this tree: `validate_exit= 1`, "ultra-goal: arming
  refused - …", and `.goals/active` is **not written** (round 2 printed
  `validate_exit= 0` / `armed= demo` on the same inputs). `pytest -q
  tests/test_package_surface.py::ArmingRangeContractTests` → `7 passed in
  0.61s`, including `test_an_invalid_artifact_cannot_arm_when_no_root_reaches_the_command`
  (the repro, as a refusal) and
  `test_the_documented_kimi_install_default_validates_and_gates_arming`
  (a validator under the managed copy decides arming: error → no marker,
  pass → armed).
- **Codex F2 (the turn boundary is inferred) — agreement, including the
  correction aimed at both reviewers.** Kimi now registers `TurnStarted`
  (new `goal_turn_started.py`; `kimi.plugin.json` carries five events, all
  documented): it fires for every new turn whatever its origin — the
  reference names `user`, `task`, `system_trigger` and the payload carries
  `turn_id` and `origin_kind` — and the 0.40.1 binary dispatches it from
  `startTurn` for every new turn while the stop-hook continuation stays
  inside the running `runStepLoop` call, so the gate's own block never fires
  one. `_block_streak` resets at `turn_started` rows and keys the count by
  the host's `turn_id`; every `anchor_checked` records which host turn it
  happened in. The demanded regression exists with a NON-user origin:
  `pytest -q tests/test_goal_hooks.py::ContinuationBudgetTests` → `21
  passed in 16.44s`, including `test_a_non_user_origin_turn_gets_its_own_budget`
  (a `system_trigger` turn arrives with a fresh budget after a spent
  user-origin turn — this exact sequence allowed, i.e. parked, before the
  change) and `test_turn_identity_scopes_the_streak_within_a_turn` (two
  `task`-origin turns each block once; only the same-turn continuation
  parks; checks carry `["t1", "t2", "t2"]`). `prompt_submitted` remains a
  boundary — the invocation is still an observed fact — but it is no longer
  *called* the turn boundary anywhere, including in
  `goal_prompt_submit.py`'s own docstring, which now records the round-2
  over-claim and the correction.
- **Codex F2, the zCode half — the mission's question answered with
  evidence, and the answer is: neither, so declare it.** zCode's hooks
  reference (zcode.z.ai/en/docs/hooks) lists Stop's input fields as
  "stop_hook_active, last_assistant_message" and spells **no meaning** for
  either; it names exactly seven events with no turn boundary among them
  and no turn identity anywhere (its own shipped zcode-guide skills agree);
  the documented cap is "After 3 consecutive continuations the run is
  force-ended". So zCode has neither a readable chain flag nor a turn
  identity, and the honest delivery is the declared degradation now stated
  in `HOSTS`, SKILL.md and README: a blocked chain that ends without one of
  the gate's own observed facts (an owner interrupt, an error, a session
  end) carries its tail into the next turn, which can park one block early —
  budget 2, so one block of it already spent. What the run loses is that
  one block, once, loudly (`continuation_budget_spent` names its reason);
  what it never gets is a proxy that looks grounded — reading the
  undocumented field, or treating a user prompt as the turn boundary, are
  the two mistakes this design already made and this round refuses a third.
- **Claude round-2's zCode finding (neither observable boundary) —
  agreement with the gap, the proposed repair not implemented (it was
  withdrawn).** Registering zCode's `UserPromptSubmit` would install exactly
  the inferred proxy Codex round 2 refuted; the declared degradation above
  is the delivery instead.
- **The silent-success delegation — decided, and the detector placed where
  the run must look.** It is not detectable from inside this plugin:
  `PostToolUseFailure` fires on failures only, and the one event that fires
  on success (`PostToolUse`) is deliberately unregistered — it spawns once
  per tool call — and could not attribute which artifact a successful call
  owed without inferring from prompt text. The only real detector is the
  expected artifact's absence, and it now lives in three places: the run's
  instructions (`goal-run.md` §3: "the round's evidence is the file the
  role was told to write … check the file exists before you treat the round
  as done"), the stated contract (SKILL.md, README, agent-modes.md — pinned
  by `pytest -q
  tests/test_package_surface.py::RolesByStageTests::test_a_succeeded_delegation_with_no_artifact_is_named`
  → `1 passed in 0.10s`), and the owner's view (`--audit` gains
  `REVIEW_UNEVIDENCED`, an advisory fired when a begun run declares a
  reviewer and `.goals/.work/<slug>-review.md` is absent; a review file on
  disk settles it. `pytest -q tests/test_validate_artifact.py::AuditTests`
  → `14 passed in 2.04s`). The finding's own text names its bound: a
  reviewer that writes elsewhere is invisible to it.

#### Round-3 receipt corrections

- Round 1 and 2 cited "reset in `notifyTurnEnded`" for Kimi's one-block
  guard. Reading the 0.40.1 binary's `runStepLoop` this round shows the
  guard is a **local variable of that function** — one call per host turn —
  so it resets by construction, not by a reset call. Same number, sharper
  citation; `HOSTS` now says so.
- Round 1's unverified claim #8 (Kimi's plugin-hook working directory, from
  Codex's external document) is now **reference-verified**: the plugin
  reference states "Each hook runs with its working directory set to the
  plugin root", and "The hook process receives two extra environment
  variables: `KIMI_CODE_HOME` and `KIMI_PLUGIN_ROOT`"
  (moonshotai.github.io/kimi-code/en/customization/plugins).
- Round 2's unverified claim #3, second half — whether Kimi fires
  `UserPromptSubmit` for the internally-appended Stop continuation — is
  **binary-resolved**: the continuation is appended to the running turn's
  context directly (`context.appendUserMessage(..., {kind:
  "system_trigger", name: "stop_hook"})`), not submitted through the prompt
  pipeline, so no `UserPromptSubmit` fires for it. The prompt marker cannot
  mis-scope the same-turn budget. Still not observed in a live session.

#### What remains unverified, and by whom

The suite above is mine. **Codex's round 2 was killed mid-review and never
reached its F3–F6 or Claude's findings, and it says so** — so the round-2
closures of Codex F3 (stagnation sensor), F4 (baseline `none` branch), F5
(evidence contracts), F6 (host tags) and Claude F-1/F-4/F-5 rest on my tests
and Claude Code's round-2 review alone, and the joint conclusion must not
report them as confirmed by both. Claude round 2 explicitly did not verify
`0da0a96`'s two claims (`$ARGUMENTS` binding, write-once baseline) either;
my round-3 `ArmingRangeContractTests` re-drives both end to end, but that is
still one implementer's evidence.

New this round, none verified by a live host (installs are outside the
mission's rules):

1. **Kimi's `TurnStarted` registration and payload shapes** — reference and
   binary derived; no Kimi session fired the hook. The manifest command is
   `python3 ./skills/ultra-goal/scripts/goal_turn_started.py`, relative to
   the plugin-root cwd the reference documents.
2. **The managed-copy validation path on a real Kimi install** — the
   location and default home are documented and the fence is driven in
   tests with a stub and with the real validator, but whether a marketplace
   (as opposed to local) install also lands under `plugins/managed/` is not
   in the reference; such an install would hit the refusal and the by-hand
   path.
3. **Claude Code's `${CLAUDE_PLUGIN_ROOT}` substitution in command bodies**
   — its plugins reference documents the placeholder for "skill and agent
   content … anywhere the placeholder appears" and classifies commands as
   skills; no Claude Code session ran the fence.
4. **Codex and zCode command execution** — Codex's plugin reference
   documents no command-body placeholder at all (not even `$ARGUMENTS`) and
   zCode's documents `$ARGUMENTS` only; on both, arming may refuse and
   require the by-hand path. That is the honest outcome Codex's own finding
   demands, and the refusal message carries the repair.
5. **`turn_id` collision across concurrent sessions** — Kimi's ids are
   per-session ordinals; two concurrent sessions in one repository could
   collide. Named as a bound in `_current_turn_id`; no failure measured.
6. **`REVIEW_UNEVIDENCED`'s reach** — it sees `.goals/.work/<slug>-review.md`
   only; reviewers writing elsewhere are beyond it, and the finding says so
   in its own text.

Carried unchanged from round 2: Codex's `None` budget as honored live,
zCode's union semantics, Claude Code's manifest-hooks-additional (binary
read), the `${ZCODE_PLUGIN_ROOT:+…}` expansion under zCode's real command
invocation, no live four-host run, no live baseline-diff review round.

**Round 4.** The implementation round for `最终方案.md` (phases 0, 1 and 2;
phase 3 deliberately nothing). Six implementation/docs commits on
`host-adaptation` after `073a801`, not pushed, not installed, not published.
Version 2.9.2 → 2.10.0 at all eight pinned sites.

#### Test command and its real output

```
$ python3 -m pytest tests/ -q
394 passed in 38.66s
```

Baseline at the round's start (`073a801`): `358 passed in 33.02s`. Every logic
change landed test-first: 5 payload-contract regressions, 7 launcher
regressions, 8 session-ownership regressions, 13 completion-contract tests,
and 3 closing-the-run tests were all written and shown failing before their
fixes. Where the plan retired a contract, the old assertions were rewritten
to the new contract and the change named — never weakened: the per-turn
anchoring tests became candidate-driven; the two not-progressing releases
now pin that nothing but the ceiling and the denial bound releases a red
claim; the `|| python` test that pinned "these hooks exit 0 whenever they
run" (the ten-second-testable claim the plan refuted) now pins the
select-once/exec-once form.

#### What changed, per phase

**Phase 0 — the five confirmed defects** (`dc76c87`, `b31561d`, `89bdda9`).

1. *Allow + `additionalContext` continues the turn.* `_allow` returns
   `systemMessage` only; the five call sites that attached the obligation
   dropped it. The obligation moved to the run's own loop, not to "the next
   injectable event": `goal-run.md` §3 now instructs the run to run the
   applicable verification with ordinary tools after relevant changes, make
   results visible in the ordinary tool output before any Stop, and write
   durable state before a turn is allowed to end — with the reason stated:
   the next injectable event is best-effort recovery and never carries
   correctness.
2. *`python3 X || python X` swallows exit 2.* Every registered command now
   selects the interpreter first (`command -v`), checks the script exists,
   and `exec`s it once; exec replaces the shell, so a deliberate exit 2
   survives. LauncherContractTests drive the shipped command strings through
   `sh -c` with a stub that deliberately exits 2: exactly one run, exit 2.
3. *Exit 2 from the launch path.* A missing script is now a fail-open allow
   (exit 0, silent) rather than Python's exit-2 block; `goal_stop.py`'s
   `__main__` wraps argparse and the launch in the same fail-open
   (`--host` with no value: exit 0, reproduced then guarded); the
   installer's registered commands carry the same guard.
4. *`.goals/active` has no session ownership.* The marker gained a
   `session <id>` line, claimed by the first session-carrying Stop;
   `run_hook` turns every other session's event away below all handlers, so
   a stranger session gets no gating, no streak resets, no spec injection.
   The limit is in the code and tests: ownership information, not an
   anti-forgery key; first-Stop-wins; Kimi's Stop input carries no session
   identity at all and zCode has never loaded a hook, so there ownership
   stays open — declared degradations, not proxy reads.
5. *The mixed `_deny` payload kills the block on Codex.* `_deny` is exactly
   `{"decision": "block", "reason"}`; the obligation rides the reason — the
   only channel a deny has.

**Phase 1 — the completion contract** (`9ac94fb`). The anchor runs at
completion candidates only (`.goals/<slug>.candidate`, self-reported,
consumed by its judgment — one claim, one judgment, so later state changes
cannot resurrect a judged claim and a stale green forces a re-run). At a
candidate the gate checks the spec baseline and anchor identity (no old
result substitutes), refuses while a delegated role's failure is the log's
last word for the turn (`candidate_refused`, window closed by any observed
turn boundary), bounds attempts by the owner's ceiling, then executes the
current anchor once against the current state and writes the measurement:
session identity, spec digest, anchor digest, post-anchor tree identity,
exit code, output digest, and the claim's first line. An ordinary Stop is
never blocked, runs nothing, and carries one deterministic omission line.
`_block_streak` became `_denial_streak` over refused claims, and the
continuation budget is redefined as the gate's own bound on consecutive
denied attempts within one observed host turn — the "host cap − 1" framing
and the per-turn counting claim are gone from `HostFacts`, the messages and
the audit advisory; Claude Code's cap is recorded as the no-progress-run
backstop it is, and zCode's degradation stays declared. The identical-
signature auto-release was retired **here** rather than in phase 2 because
its measurement window (per-turn checks) no longer existed once the anchor
moved: a repeated signature is recorded and named in the refusal
("byte-identical … does not prove no progress"), and the releases that
remain are the ceiling and the denial bound.

**Phase 2 — authorization, observation, lifecycle** (`40e3f09`, `ed72ced`).
The re-baseline semantics is **(b): a legitimate goal change ends the old
run; the owner opens a new one with a new spec.** Why: the current code
always compares the first recorded digest with no path that could recognize
a new baseline, so "deletion-shaped, code unchanged" was never available;
and (a) would require verifying authority, which no artifact this gate can
read can carry — a script the agent can also run is the ruling-id mistake
again (correlation, not authorization). Concretely, `frozen_spec_changed`
now closes the run: the gate disarms itself (`.goals/active` and any
pending candidate go; the observations stay for `--audit` and Git), and the
message names the reopening procedure. Re-baseline requires the owner's
authority, not a trace; an agent may raise a challenge, never rule its own
material change into an owner change. The two axes are split in SKILL.md —
anchor observation `green/red/unknown` versus run disposition
(`in_progress`, `input_required`, `blocked_retryable`, `budget_exhausted`,
`unachievable`, `completed`, `canceled`) as report vocabulary that
`goal-run.md` tells the run to use — with **no fourth mechanical gate
outcome** and `unachievable` explicitly not implemented because it has no
consumer.

**Phase 3 — nothing**, as ruled. The four Protoss-derived mechanisms were
not implemented and no failure was reverse-engineered to justify one. The
one surviving sentence is in `references/anti-patterns.md` as a criterion,
with its evidence: **a record with no consumer is not a fix** — the
TRAJECTORY that carried the same lesson six times while the per-round judge
that read a different file hit on it zero times.

#### Post-fix live probes (the plan's phase-0 pass condition)

Receipts: `docs/wip/reviews/probe-receipts-round-4.json`, driver
`docs/wip/reviews/probes-round-4.py`; each registers the real gate behind a
logging wrapper in an isolated directory.

- `clean-claude-allow-no-context` (Claude Code 2.1.260): **one** Stop
  callback, payload keys exactly `["systemMessage"]`, turn ended,
  `PROBE_INITIAL` untouched — against the pre-fix probe's second callback
  and model acting on the injected text.
- `clean-codex-deny-toplevel` (codex-cli 0.150.1): the top-level-only deny
  **blocks** — two Stop callbacks, chain flags `[false, true]`, the model
  emitted `PROBE_CORRECTED` after the correction. Same-class positive
  control; bounded to 0.150.1, not extrapolated to other versions.
- `clean-claude-dual-session`: a session that is not the marker's owner is
  invisible — one callback, empty gate output, no event written.

Isolation note, recorded because it cost a diagnosis: claude probes must
pass `--setting-sources project`; user-scope hooks on this machine
(including hindsight memory injection) otherwise reach every `--print`
session and derail the probe model.

#### What was refused

- No mid-run re-baseline mechanism, no ruling ids, no trajectory file, no
  retraction ledger, no promise-checking — 4/4 not admitted by the plan's
  own gate, and nothing here reverses that.
- No fourth gate outcome for `unachievable`.
- No proxy session or turn identity for Kimi/zCode: their payload facts are
  what they are, and the degradations are stated where a reader will look.
- No weakening of an assertion to make a suite pass: every rewritten test
  names the contract change that forced it.

#### What could not be verified

- **zCode and Kimi remain at zero live hook coverage.** zCode has still
  never loaded one of these hooks (`Unknown option --settings` in every
  attempt so far); every claim about zCode rests on its reference and on
  tests, not on a loaded hook. Kimi's Stop path has no live probe either.
- The Codex deny result is bounded to codex-cli 0.150.1 on this machine.
- The claim-stamping direction of session ownership (a second session
  stopping first over a just-armed goal claims it wrongly) is a named bound
  with unit coverage, not a live dual-session race.
- `commandWindows` paths are untested on this darwin machine, as before.
- No live verification that the completion-candidate flow reads correctly
  to a working model across a real multi-turn run; the probes verify
  transport and ruling, not the experience.

### 8.2 Claude Code — review rounds

_(Claude Code writes here, and in `docs/wip/reviews/claude-round-N.md`)_

### 8.3 Codex — review rounds

**Round 1.** Independent report: [`docs/wip/reviews/codex-round-1.md`](reviews/codex-round-1.md).
Verdict: request changes; the blind suite passed 332 tests, but Kimi command activation and
per-turn budgeting, stagnation evidence, and the review baseline still have reproduced gaps.

### 8.2 Claude Code — review rounds

- **Round 1** — [`reviews/claude-round-1.md`](reviews/claude-round-1.md). Six findings, and
  an addendum retracting three of them after reading the vendors' references and the Claude
  Code loader. Blind verdict 332 passed.
- **Round 2** — [`reviews/claude-round-2.md`](reviews/claude-round-2.md). Two of its
  surviving findings closed; one new (zCode had neither observable turn boundary). Blind
  verdict 347 passed.
- **Round 3** — [`reviews/claude-round-3.md`](reviews/claude-round-3.md). Both open P1s
  closed; its own round-2 proposal retracted as wrong. Blind verdict 358 passed.
- Pre-registered readings, written before any implementation existed and kept outside this
  worktree until both round-1 reports were filed:
  [`reviews/claude-preregistered.md`](reviews/claude-preregistered.md).

### 8.3 Codex — review rounds

- **Round 1** — [`reviews/codex-round-1.md`](reviews/codex-round-1.md). Complete. Request
  changes, 4 P1 + 2 P2, blind verdict 332 passed. Its F2 was the deepest finding of the
  three rounds.
- **Round 2** — [`reviews/codex-round-2.md`](reviews/codex-round-2.md). **Partial**, and it
  says so in its own text: the session ended mid-review after two P1s, with F3-F6, the other
  reviewer's findings, and its regression audit unreached. Blind verdict 347 passed. The two
  P1s it did produce - fail-open arming, and the turn boundary still being inferred - were
  the whole content of round 3.
- **Round 3** — [`reviews/codex-round-3.md`](reviews/codex-round-3.md). **Blind verdict
  only** (358 passed, matching independently), then "Findings: Verification pending."

### 8.4 Joint conclusion

**There is no joint conclusion, and saying so is the conclusion.** The owner asked for one
report from two reviewers with their disagreements included. Codex's third-round half does
not exist, so what follows is one reviewer's conclusion plus the parts of Codex's work that
completed. Presenting it as joint would be the exact failure this project's own
`adversarial-review.md` refuses: two reviewers who both say "looks fine" have produced one
opinion reported twice, and here the second reviewer did not speak at all.

**Why it does not exist, with the records:**

| attempt | target | stop reason | duration | wrapper reported |
|---|---|---|---|---|
| round 2 | codex | `cancelled` | 130s | `exit=0 status=success` |
| round 2 retry | codex | killed (harness) | — | `[killed]`, receipt written |
| round 3 | codex | killed (harness) | ~7 min | no `result.json` at all |

The first is the one worth keeping as a finding rather than an inconvenience: **a review that
never happened was reported as a success.** 41k tokens, 200 output tokens, no protocol error,
no quota exhaustion, no file. `PostToolUseFailure` writes `role_unavailable` only when a call
*fails*, so nothing in this plugin could see it. That is what `REVIEW_UNEVIDENCED` now exists
for, and this run is its first real instance - the detector was built in round 3 because the
delegation layer produced the failure in round 2.

**What is actually settled, and by whom:**

- The suite: 358 passed, verified independently by both reviewers in round 3
  (`358 passed in 31.55s` and `358 passed in 41.75s`).
- Codex F1 (fail-open arming) and F2 (inferred turn boundary): closed, verified by Claude
  Code in round 3 against the closure bar **Codex itself set** - a host-provided turn
  identity plus a non-user-origin regression. Codex has not confirmed its own closures.
- Claude Code's three surviving findings: closed, one of them by a repair Claude Code
  proposed and one by retracting the repair Claude Code proposed.
- Codex's F3, F4, F5, F6 from round 1: **only zCode's own account says these are closed.**
  Neither reviewer verified them. F6 in particular is Codex's own unreproducible evidence
  line, and it was never withdrawn or substantiated.

**What no round of this exercise touched:** no host other than Claude Code ran a single one
of these hooks. Three of the four host adaptations are read from references, binaries and
manifests only. The 358 tests measure this repository's logic and packaging conventions;
they do not measure a host honouring a registration.

**The reviewers' retraction record**, which the Protoss study argued should be a product
artifact rather than a footnote:

| Round | Claude Code retracted | Beaten by |
|---|---|---|
| 1 | zCode's `ZCODE_PLUGIN_ROOT` called "a load-bearing guess" | zCode's hooks reference lists it among four plugin variables |
| 1 | "Codex would still load `PostToolUseFailure` from the shared file" | Codex's plugin reference: the manifest entry is used *instead of* the default |
| 1 | "Claude Code's manifest `hooks` might replace discovery" | the CC loader's own schema text and control flow: additive |
| 2 | grading `prompt_submitted` as an observed turn boundary | Codex F2: the invocation is observed, the equivalence is inferred |
| 3 | its own round-2 fix proposal (register `UserPromptSubmit` for zCode) | it would have installed the refuted proxy on the one unverifiable host |

Codex retracted nothing across three rounds, and never reached the section where it was
asked whether any of the above was conceded wrongly.

**Five retractions, four of one shape:** measure the machine, skip the contract, report the
gap in your own evidence as a defect in the work. The implementer read the references; the
reviewer did not. That is the most reusable result of the exercise, and it is an argument for
the retraction ledger this design still lacks.
