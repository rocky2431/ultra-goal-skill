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

_(zCode writes here)_

### 8.2 Claude Code — review rounds

_(Claude Code writes here, and in `docs/wip/reviews/claude-round-N.md`)_

### 8.3 Codex — review rounds

_(Codex writes here, and in `docs/wip/reviews/codex-round-N.md`)_

### 8.4 Joint conclusion

_(Claude Code and Codex, after the final round)_
