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

### 8.2 Claude Code — review rounds

_(Claude Code writes here, and in `docs/wip/reviews/claude-round-N.md`)_

### 8.3 Codex — review rounds

_(Codex writes here, and in `docs/wip/reviews/codex-round-N.md`)_

### 8.4 Joint conclusion

_(Claude Code and Codex, after the final round)_
