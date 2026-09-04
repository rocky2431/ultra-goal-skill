# UltraGoal

An Agent Skill that interviews you into a **grounded** goal, then writes the prompt or
script that pursues it until an anchor says it is met.

The goal is the invariant. A loop and a graph are two shapes it compiles to, and neither is
an upgrade of the other — the distinction is when routing gets decided.

## The problem

"Make an agent keep doing this" is easy to say and hard to make work. The loops that fail
in production fail in the same few ways:

- there is no measurement that cannot be argued with, so the loop cannot tell progress
  from motion;
- the agent decides for itself when the work is good enough, and "good enough" drifts
  toward whatever ends the turn;
- the agent grades its own output, and it praises it;
- work gets split by workflow phase — plan, implement, test — so every handoff loses the
  context the next phase needed;
- agents check each other in a closed circle where everything is consistent and nothing
  is verified.

None of that is fixed by a better framework. It is fixed by answering five questions
before anything runs.

## What it does

It covers the whole life of a loop — create it, look at it, change it — and needs no other
Skill installed to do any of that.

0. **Recognizes the intent** before anything else: create a loop, modify one that exists,
   inspect what is running, or say this is not a loop at all. When the workflows directory
   is non-empty it checks status *before* the first question, so a request about work that
   already has a loop becomes a modification instead of a second artifact for the same job.

1. **Classifies** the work. One question: *can you sketch the whole thing on paper before
   running any of it?* Yes means graph-shaped — routing was decided at authoring time and
   the edges are code. "I'd need to know what step three returns" means loop-shaped —
   routing is decided during inference, every iteration, and billed every time. Topology
   is not the distinction; a loop is a directed cyclic graph. *When the routing decision
   gets made* is the distinction.

2. **Interviews** you, one question per turn, each carrying a recommended answer: intent,
   anchor, stop condition, **means**, boundary, verifier, split, surface, divergence. It
   looks up anything the repository can answer instead of asking you, and it refuses to
   emit an artifact with no anchor.

   The means question is the one that decides how much latitude the run has. You label each
   means `[load-bearing]` or `[droppable]`; the run may abandon a droppable one on evidence
   and must record the argument, and may not touch a load-bearing one at all. Without the
   labels, abandoning a feature is indistinguishable from scope drift, so the agent has to
   either stop at every surprise or drop things quietly — and neither is what you wanted.

3. **Compiles** one machine-consumable artifact — and stops there. Running it is not this
   Skill's job.

| Shape | Artifact | Consumer |
|---|---|---|
| Loop | `<slug>.goal.md` — the objective plus the goal line to paste | the host's goal mode |
| Graph, one vendor | `<slug>.workflow.js` — topology in code | a workflow runtime, where one exists |
| Graph, several vendors | `<slug>.delegation.md` — one adversarial-review triad | cross-agent delegation |
| Always | `<slug>.decisions.md` — Decision / Rejected / Why | you, next time |

The decisions record holds decisions, not architecture. The script or prompt is the only
description of what the thing does; a prose copy of it goes stale and starts lying. It is
also the interview's progress — written row by row as answers are confirmed, before the
artifact exists — so a session that dies mid-interview resumes instead of restarting.

4. **Tracks state without storing any.**

```bash
python3 scripts/validate_artifact.py .goals --status
```

Reports each artifact's shape, anchor, stop condition, phases or workers, and decision
count. The artifacts on disk are the only record; this is a projection recomputed on every
call, so it cannot drift the way a tracked state file would. `--run-anchors` executes each
anchor and reports its exit code — the one question that matters about a running loop — but
it runs commands the artifact names, in a shell, so it asks first and refuses to run
without `--status`.

5. **Makes the loop evolve.** An unattended loop wakes with an empty context every
   iteration. Unless something carries forward it rebuilds history from git logs and retries
   paths it has already proven dead, believing each time it is the first attempt. So a
   `/loop` or `/schedule` artifact gets a `## Carry-over` section, and **the prompt itself**
   is wired to read it before acting and rewrite it before finishing — a section nothing
   writes to stays empty forever.

   Three places, three jobs, no duplication:

   | What you want to see | Where it lives |
   |---|---|
   | What is true now | the `## Carry-over` section — current only, pruned |
   | How it became true | `git log -p <slug>.goal.md` — the diffs *are* the evolution |
   | What each iteration did | the commit message — one line per iteration |

   A goal with a cadence also gets **`## Acceptance`**: one unordered line per
   requirement, each carrying the state the run claims for it. One sentence plus one anchor
   answers *is the whole thing done* and cannot answer *which parts are* — and the second
   question is where a long run declares victory on the strength of the part it finished.
   Unordered, never numbered: ordered steps are a plan, a plan is an author-time
   decomposition, and that is a graph. `plan.md` and a dependency-ordered `tasks.json` stay
   refused; see
   [references/document-system.md](plugins/ultra-goal/skills/ultra-goal/references/document-system.md)
   for the line between them.

   Because the history is in Git, the document never has to hold it. Carry-over has three
   parts with different budgets: `### State` (where the work stands, at most 8),
   `### Lessons` (**why** something failed and what to do instead, at most 3), and
   `### Next` (the single objective for the following round, inside the frozen intent —
   exactly one, because a list of them is a plan and a goal with a plan should have been
   authored as a graph). `### Next` is the edge that closes the loop: without it a run
   re-attempts the same objective until the anchor goes green or the ceiling hits. The
   Lessons
   cap comes from Reflexion, which bounds its reflection memory at 1-3 because entries the
   model must reason over compete with the work for the same budget.

   A lesson is a cause and a next action, never an event. "The build failed" is the signal;
   "the build fails without a committed lockfile because CI runs `--frozen-lockfile` —
   commit the lockfile in the same change" is the reflection. Only the second one changes
   the next iteration.

6. **Keeps lessons in the project.** What a loop learns is true of one repository — one
   project's dead end is another project's correct answer. It never gets promoted to
   user-level configuration or into this Skill, which is versioned and shared. The Skill
   carries the criteria, the owner's configuration carries their standing preferences, the
   project carries what its loop learned, and the arrows only point down.

7. **Modifies by editing the decision, not appending to a log.** A changed decision replaces
   the old one in the Decision column and the old one moves to Rejected with why it changed.
   A request that contradicts something already in the Rejected column gets surfaced rather
   than quietly reversed. A change to the anchor itself reopens the interview — a loop whose
   anchor changed is a different loop.

## Starting a run: no host goal mode required

Four of five measured hosts have a `/goal` command, and none of them is needed. What kept a
model working there was re-prompting; here the Stop hook does it by refusing to let a turn
end while the anchor is red — so the loop was always ours. Item by item, goal mode duplicates
four of this Skill's own mechanisms and cannot do the one that matters: write `.goals/active`,
the marker without which every hook here is inert.

```
/ultra-goal:goal-run <slug>
```

Ships with the plugin. It validates the artifact, arms the gate, and hands over the spec in
one step. Where the plugin is absent, paste `## Handoff`'s text as a plain prompt and create
the marker by hand — the objective is portable even when the command is not.

## Hosts

Goal mode is the mechanism: paste one objective into your CLI, walk away, and the host keeps
the model working until it is met or a ceiling is hit. Measured on real installs:

| Host | Goal mode | Notes |
|---|---|---|
| Claude Code | `/goal <objective>` | backed by a stop hook; also has `/loop`, `/schedule` |
| Codex 0.150.1 | `/goal <objective>` | a `goal` extension accounts progress after every tool call |
| Kimi | `/goal <objective>` | plus `/goal pause` / `resume` / `cancel` |
| zCode 0.16.5 | `/goal <objective>` | also `--target` for a headless session |
| OpenCode 1.18 | not found | the same text works as a plain prompt |

"Not found" means no evidence in that host's help output or shipped binary, not proof of
absence. Cross-vendor delegation works on all of them.

**What goal mode does not do is decide what counts as done — it asks the model.** That gap
gets closed in the goal text itself, not with machinery around the host:

```
/goal <objective, inside <scope>>. You have not met this goal until you have actually run
`<anchor>` in this session and seen it <exact result> - do not claim completion from
reasoning, and do not state <confidence claim> without that output. Do not conclude
<inference> from documents alone; reproduce it. State which turn you are on at the start of
each turn. Rewrite the Carry-over section before you finish. Stop after <N> turns even if
unmet, and say so.
```

Eight clauses, one hole each: scope creep, claiming success from reasoning, inappropriate
confidence, a verdict nobody can check against the log, inference beyond the data, silent
scope drift, losing count of the ceiling, and the run never learning or re-aiming. The same
text pastes into all four hosts.

**A workflow script needs a workflow runtime.** Only Claude Code has one, so elsewhere the
Skill will not emit that shape — the file would be something nothing can run.

Artifacts live in the project's `.goals/`, not inside any tool's private directory: they are
project assets that belong in Git and may be read by whichever agent a teammate runs.

## Install

```bash
git clone https://github.com/rocky2431/ultra-goal-skill
cd ultra-goal-skill
python3 scripts/install_user.py install                 # all supported hosts
python3 scripts/install_user.py install --hosts claude   # or pick them
python3 scripts/install_user.py doctor --json            # verify
```

Hosts: `hermes`, `claude`, `codex`, `kimi`, `zcode`, `opencode`. Installing keeps a
recovery copy and refuses to overwrite an unmanaged Skill of the same name.
`uninstall` removes only copies this installer manages.

The repo also ships a plugin manifest (`.agents/plugins/marketplace.json` and
`plugins/ultra-goal/.codex-plugin/plugin.json`) for hosts that install plugins
directly from a Git marketplace.

## The gate

On a host that exposes the events, hooks install with the Skill and turn the anchor from
a sentence in a prompt into something that actually runs. Which hooks register is a
per-host fact — each manifest registers only events its host documents, so zCode (no
`PreCompact`) and Codex (no `PostToolUseFailure`) each get their own set, and Kimi — whose
reference makes every event but `PreToolUse`, `Stop` and `UserPromptSubmit`
observation-only — registers no `SessionStart` at all; its `UserPromptSubmit` line carries
the pointer and the gate's last decision instead.

| Hook | Does | Can it block? |
|---|---|---|
| `Stop` | Runs the anchor every turn | **Yes, while the anchor is red** — up to the host's continuation budget |
| `SessionStart` | Re-injects the frozen spec and carried state after a restart (not registered on Kimi — that host ignores its output) | No |
| `PreCompact` | Records the carried state before the context is emptied | No |
| `PostToolUseFailure` | Records that a call naming a delegation target failed, so a degraded round cannot read as a clean one (no such event on Codex — the run's report is the only record there) | No |
| `UserPromptSubmit` | Kimi only: one fixed-size line per prompt — artifact pointer plus the gate's last decision — that host's documented channel for both | No |
| `TurnStarted` | Kimi only: records the host's own turn boundary (`turn_id`, `origin_kind`) for every new turn whatever its origin — a user prompt is one origin of a turn, not the boundary itself | No |

**The loop is the continuation budget.** A host keeps a Stop-blocked turn alive only so
many times in a row — Claude Code force-ends after 8 consecutive blocks, zCode after 3,
Kimi triggers a blocking Stop once per turn, Codex documents no cap — so the gate counts
its own blocks in the event log and releases one *before* the host's cap, ending the turn
loudly (`continuation_budget_spent`, surfaced by `--audit`) instead of letting the host's
force-end warning have the last word.

**The budget is scoped to the host turn by an observed boundary — and zCode has none.**
The count resets at a fact the host or the gate observed: Claude Code's and Codex's
documented `stop_hook_active`, Kimi's `TurnStarted` (fires for every new turn whatever
its origin, and carries `turn_id`), an allow, or a chain-ender the gate itself wrote.
zCode's reference lists `stop_hook_active` among Stop's inputs with no word of semantics
and its seven events include no turn boundary, so there the streak resets only on the
gate's own facts: a blocked chain that ends without one (an interrupt, an error, a
session end) carries its tail into the next turn, which can park one block early. A
declared gap — reading the undocumented field or treating a user prompt as the turn
boundary would be a proxy that looks grounded, which is the mistake this design made
twice before refusing it.

**Three outcomes, not two.** An anchor that cannot run — missing command, not executable,
timed out — is **unknown**, not failed. A timeout measures elapsed time and has no access to
success or failure, so reporting it as either is how a mechanical gate starts lying. Unknown
lets the turn end and says the result is unverified.

**Seven of the eight steps allow.** Frozen spec changed, ceiling reached, run not
progressing, continuation budget spent, anchor unrunnable, anchor green, no anchor, no
active goal — all let the turn end and say why. It refuses only when it is certain.

**It also remembers which goal it was pointed at.** On the first turn the gate records a
digest of `## Intent`, `## Boundary` and `## Anchor`; on every later turn it compares. When
they differ the run is no longer pursuing the goal you authorized, so the turn ends loudly
and the anchor is not run at all — proving something about an edited spec proves the wrong
thing. It allows rather than denies on purpose: the answer to a moved goalpost is to hand
the decision back, not to work harder against it.

### What it costs a project that never asked for one

Every hook's first act is one check: is there a `.goals/active` marker naming an artifact that
exists? Without one, nothing is read, nothing is written, no command runs — a process start
and a `stat`. That early exit is the only thing between an installed hook and an unrelated
project, so it is pinned from nine angles in `tests/test_goal_hooks.py`, including that an
inactive project executes no anchor and that a handler which raises still exits 0.

Escape hatches, neither of which needs the agent's cooperation: `rm .goals/active`, or
`ULTRA_GOAL_HOOKS_DISABLED=1`.

Registration is idempotent, backs up `settings.json` first, preserves every hook it does not
own, and `doctor` reports `missing` or `partial:<events>` if something later removes it.

`PostToolUse` is deliberately not registered — it fires once per tool call, and its value
duplicates what `SessionStart` injects. It gets added when a real run shows a loop retrying a
path its own lessons already ruled out.

## The validator

```bash
python3 scripts/validate_artifact.py .goals --json
```

It observes facts and nothing else: file pairing, required sections, every shape carrying
an anchor, `meta` being a pure literal and the first statement, phases declared before use,
delegation targets that are actually registered, and JavaScript syntax. It never edits an artifact and it never judges
whether a topology is the right one — that part is the design, and design belongs to you
and the model, not to a template engine.

Its silence is not evidence that the design is right.

## Three roles that ship as isolated skills

The reviewer, the critic and the design critic are not ad-hoc subagent calls. Each is a
skill with `context: fork` and `background: false`, which the skills reference defines as
running the skill's content as the whole prompt in a subagent that **never sees the invoking
conversation**:

| Invoke | Reads | Writes |
|---|---|---|
| `/ultra-goal:design-critic <slug>` | the spec and the decisions record, before any work starts | nothing — returns objections |
| `/ultra-goal:review <slug>` | the artifact, the frozen diff, the anchor's own output | `.goals/.work/<slug>-review.md` |
| `/ultra-goal:critic <slug>` | that review and the same frozen diff | `.goals/.work/<slug>-critique.md` |

The contagion worth preventing is the **author's argument**, and the author is the session
doing the invoking — so making isolation a declared property of the file removes the step
where the caller has to remember to arrange it. Crossing vendors instead is the same
protocol with `agent-delegate` in place of the fork: same inputs, same refusals, one extra
process, a different set of blind spots.

## What the gate says, and to whom

| Channel | Read by | Carries |
|---|---|---|
| `decision: "block"` + `reason` | the model, when the turn may not end | why, and the one thing to do first |
| `additionalContext` | the model, on every turn that ends | **exactly the sections the run may change**, with current values |
| `systemMessage` | you | one line of what happened |

The middle row follows a rule worth stating alone: **what the gate reminds you of should be
exactly what you may change.** A mutable section it never mentions is the one that goes
stale; a frozen section it does mention is an invitation to edit. So the reminder holds
`### Next`, `### Lessons`, `### State` and the still-open `## Acceptance` lines — nothing
frozen.

This corrects a belief that sat in the code for the gate's whole life: blocking was emitted
as `hookSpecificOutput.permissionDecision`, which is the **PreToolUse** shape. Stop takes
only `hookEventName` and `additionalContext` there and blocks on the top-level pair — so the
one hard power in this design was wired to a field the host does not read, and every test
checked what the script emitted rather than what the host honours. A payload contract is a
claim until something outside the emitter agrees with it.

## A ceiling you did not choose is not a ceiling

`## Stop condition` takes a declared line: `ceiling: 6`, or **`ceiling: none`** for a run
that should continue until the anchor is green however long that takes. Read first, before
any prose.

This was a live defect, and the case that found it was real: a long run whose stop condition
said "no ceiling" would have been stopped by this gate at turn 13 while reporting *ceiling
reached* — in the owner's own voice, at a number they never wrote. When neither a `ceiling:`
line nor a turn count can be read, the gate now applies its default **and says that it is
its own**, and `CEILING_UNDECLARED` warns at authoring time.

## Two severities, because two different things were being reported alike

An artifact missing its anchor is broken. An artifact carrying nine `### State` entries
against a budget this Skill *invented* is worth a sentence — and failing over that number
would be the Skill enforcing its own guess as if it were a fact. So findings carry a
severity, and only errors move the exit code:

- **error** — the artifact cannot do its job as written (no anchor, no handoff, a reviewer
  with no critic, an acceptance line with no state);
- **advisory** — this Skill's judgement about how well it will work (`STATE_UNPRUNED`,
  whose budget has no cited basis; `ANCHOR_BUDGET_UNREACHABLE`, where the number is simply
  above what the host's hook timeout permits).

`LESSONS_UNPRUNED` stays an error because it has a basis: Reflexion bounds its reflection
memory at 1-3 entries, since entries the model must reason over compete with the work.
`STATE_MAX = 8` has no such source, and now says so.

## Claims, measurements, and the audit

The run authors the artifact, its carried state, its commit messages and its reviews. All of
that is a **claim**. The hooks author `<slug>.events.jsonl` — exit codes, output digests,
spec digests — and only that is a **measurement**. Wide latitude for the model is exactly
why the small set of checkable facts has to stay out of its hands.

```bash
python3 scripts/validate_artifact.py .goals --audit
```

Each turn's committed verdict beside the verdict the gate measured for that turn, with every
divergence named: a claim the log contradicts, a claim for a turn the gate never saw, a run
with no gate at all, a moved frozen spec, or no history to audit against. On a run that went
wrong, the first row where the two part company is where to start reading.

Nothing auto-resolves a divergence, and the limits are stated rather than implied: the run
can write any file it can read, `events.jsonl` included. What defends the log is not
permission but publication — it is committed, so a rewritten history is a diff. Making a
moved goalpost **visible** is the achievable property; making it impossible is not.

## Roles, and which of them are actually choices

Every development round has four stages — research, shape a plan, carry it out, review and
feed back — and most of what looks like a "multi-agent or not" question belongs to exactly
one stage. So `## Roles` is settled per stage, and the Skill says which parts you get to
decide:

| Stage | Who | Your call? |
|---|---|---|
| Lead — intent into a spec | this session, with you | **No** — an interview cannot be delegated |
| **Research** | fanned-out subagents | how wide, and whether any needs another vendor |
| Plan — the spec, plus one adversarial pass over it | this session + a design critic | whether the design critic runs |
| **Carry out** — the code **and its tests, test first** | **this session** | **No** — see below |
| Verify at code level | the anchor | **No** — mechanical |
| Review semantically | not whoever wrote it | the one real choice |
| Fan out | one worker per subject | only where subjects are independent and **each has its own anchor** |

**Who writes the code is your call**, and the recommendation cuts both ways. For a small
slice: the main session. Anthropic runs both patterns
split by task type: "Claude Code uses this orchestrator-subagent pattern. The main agent
writes code, edits files, and runs commands itself... This contrasts with the research
system, where the lead agent delegates." The reason matters more than the authority:
`### Lessons` and every dead end live in the main context, so a fresh coder subagent would
restart the run at turn 1 every turn. **At scale it flips**, and there is a working
counterexample on this machine: a long build where the lead holds the loop, owns one ledger,
writes no code, and two cross-vendor executors alternate between build rounds and review
rounds — each taking a whole slice, so it is a role rotation rather than the phase split this
design refuses.

The referee-and-player objection is answered somewhere else entirely — the **anchor's exit
code decides**, with no model in that path, and the reviewer never receives the author's
argument. Moving the referee out of the writer's hands is what the zero-trust layer is for.

And there is a sharper answer still, taken from that production run: **the judge records its
verdict before reading the executors' reports.** Run the anchor, write the verdict to
`<slug>.judge-review.md`, and only then read what they said. That is context isolation
applied to the judge rather than the reviewer, and it closes what "the exit code decides"
does not — the exit code cannot settle which findings mattered, or whether a report was
honest about what it never checked.

**The only genuine choice in review is model independence**, because the two axes cure
different diseases:

| Axis | The disease | Cost |
|---|---|---|
| **Context isolation** | the author's *argument* reaching the reviewer, who then reviews the argument | negligible — **and not optional** |
| **Model independence** | *shared blind spots*: two agents on one model make the same mistake and agree about it | ~10x |

So a same-model subagent is not a cheap substitute for a different vendor. It cures the
first completely and the second not at all. When review runs and the round cap are
parameters of that choice, not peers of it.

## Declared degradation

An agent runs out of quota, a target does not answer, a process dies. Every role in
`## Roles` names a `fallback:` — try the role, then its fallback, then continue as the main
session alone, and record which happened.

| What | Who decides | Where it lives |
|---|---|---|
| who to fall back to | **you**, at design time | `## Roles` |
| whether a target answered | observed at call time | — |
| that a fallback was used | the run, in its report and `### Lessons` | a **claim**, not evidence |

**Whether a delegation failed is measured where the host fires `PostToolUseFailure`**
(Claude Code, zCode, Kimi): the hook writes `role_unavailable` and `--audit` surfaces it
as `ROUND_DEGRADED`. This passage once said the opposite — that no code could write the
event — and that was true of the version it described: the only writer considered was the
run, and a run's statements are claims, so `events.jsonl` was the wrong place and the
finding was deleted. The hooks reference settled that a *host* observes the failed call,
which is why the finding exists again with a hook writing it. Codex documents no such
event, so there the run's report is the only record — a declared loss, not parity. Whether
the fallback was *adequate* stays a claim on every host, which is the last row above.

And a call that *succeeds* while writing no file is a degradation **no hook can measure**:
the failure event fires on failures only, and the success-side events fire once per tool
call and are deliberately not registered — a round that returned success and produced
nothing reads as a clean one from inside the plugin (it happened to a review round on
this project). The only real detector is the expected artifact's absence — the round's evidence is the file the role was told to write — so the run does not count a round until
that file exists, and `--audit` reports a declared reviewer with no review file as
`REVIEW_UNEVIDENCED`. A review that returned success and left nothing is a missing
review, not a pass.

`fallback: none` is a legitimate answer and says the run stops rather than degrading; silence
does not. And a review that could not happen is a **missing review, not a red anchor** — the
report has to say so, and the goal text now asks for it.

## The one thing the goal can learn from

## Owner-decided versus agent-assumed

`decisions.md` has a fourth column, `Who`, holding `owner` or `agent`. It exists because a
real run needed it and did not have it: its first artifact carried "(my inline assumption,
the owner did not object)" and "(I set this outright, not offered as an option)" inside Why
cells. Both were the right call. Neither was a decision the owner made — and without the
column an assumption is indistinguishable from an agreement, so `--status` counts them apart:

```
closed-loop-skeleton  [loop]  decisions=12  assumed=2  **challenges=1**
```

An `agent` row is legitimate and often necessary. Leaving it unmarked is not.

## The one thing the goal can learn from

`### Lessons` carries method forward. `### Next` re-aims within the terms. Neither can say
*the terms themselves are wrong* — that is frozen, and correctly so. So there is exactly one
thing a run knows that the design side cannot: which term turned out to be unworkable in
contact with reality. Until v1.2.0 that was the only outcome that wrote nothing down.

`## Challenges from the run`, in the decisions record, is that channel:

- **written by the run**, and only the run — the one part of that file its owner does not
  author;
- **ruled on by the owner**, so `--status` counts challenges apart from decisions and an
  unresolved objection never reads as a settled decision;
- **the term challenged, what the run hit, and what would settle it** — all three, or it is
  a complaint rather than an objection;
- **instead of editing the term.** A run that edits a frozen term has moved the goalpost; a
  run that challenges it has done its owner a favour;
- **read first by the next Modify pass**, which already had to read this file — so the
  objection lands exactly where the next design pass is required to look.

Optional on purpose: most runs raise none, and demanding one per run produces invented
objections, the same failure as a reviewer who must find something.

## Adversarial review

Verification is two roles, not one, because one is measurably not enough. A **reviewer**
reviews the artifact; a **critic** reviews the review — not the code.

```
M (main)      the only role that edits the artifact
R (reviewer)  reviews the artifact          [artifact FROZEN during the exchange]
C (critic)    reviews R's review
```

The failure this prevents is **false consensus**: two agents that both say "looks fine" have
produced one opinion reported twice, and a loop cannot tell that from verification. The fix is
textual — the critic sorts every point into exactly one of **agreement**, **evidence-backed
disagreement** (cite it), or **concern-based disagreement** (say what would settle it), and
the reviewer answers with evidence rather than a rebuttal. That turns a disagreement into an
auditable object.

Three roles outperformed a five-agent panel in the source study
([arXiv 2608.18167](https://arxiv.org/html/2608.18167)), and adding independent reviewers
alone did *not* reliably help. The count is not the mechanism; the third role is. Where the
roles are separate agents they get **different vendors** — agents sharing a model share its
blind spots. Inner loop capped at 5 rounds, with first-pass termination so work that was
already correct costs two calls.

This replaced an earlier shape that split delegation by domain — one worker per concern, the
orchestrator merging their reports. That is the two-reviewer step the study measured and found
unreliable. Domains became the reviewer's checklist; parallelism moved from "several reviewers
on one artifact" to "several artifacts, each with its own triad".

## Scope

**It stops at a document and Git.** One artifact, one decisions record, one carry-over
section, and version control. No directory tree, no derived index, no progress ledger, no
state machine, and no second copy of anything Git already holds. The shape resembles a
spec-driven development harness and that resemblance is a constraint, not an invitation:
harnesses that grew those parts have had to delete them again. Adding one requires naming a
question that neither the artifact nor `git log` can answer.

This Skill produces **executable artifacts** and is self-contained: it assumes no
neighbouring Skill is installed, and its hand-off spells out the command in full rather than
leaving another Skill to fill in the gap.

The loop's own boundary — what it may touch, which effects need approval — is one of the six
questions and belongs here. A broader authority model for an agent that is not a loop does
not: that gets answered directly, not wrapped in a loop. If you do happen to run
[agent-harness-design](https://github.com/rocky2431/agent-harness-design-skill) or
[agent-delegate](https://github.com/rocky2431/agent-delegate-skill), the eval set records
where each would take over — as `optional_skills`, never as a dependency.

## Sources

The guidance traces to primary sources, listed with URLs and a currency date in
[references/research-basis.md](plugins/ultra-goal/skills/ultra-goal/references/research-basis.md).
Anthropic's loop and multi-agent engineering posts are treated as doctrine; the July 2026
"graph engineering" essays are treated as argument.

The carry-over design rests on two papers, with what was taken and what was deliberately
left behind spelled out in
[references/evolution-and-scope.md](plugins/ultra-goal/skills/ultra-goal/references/evolution-and-scope.md):
**SKILL.state** ([arXiv 2608.26263](https://arxiv.org/abs/2608.26263)) for explicit carried
state over replayed history — including the finding that one five-field schema served 100
task instances — and **WikiSkill** ([arXiv 2608.27454](https://arxiv.org/html/2608.27454))
for persistent knowledge being the critical variable in skill evolution (48.7% → 63.7% in
their ablation). WikiSkill's machinery — inference agent, wiki maintainer, skill proposer,
gating against a validation set — is **not** adopted: it is a training framework, and a loop
designed with its owner in the room has no validation set.

## Tests

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

273 tests: the validator's rules at two severities, the status projection, the
claim-versus-measurement audit
against a real Git repository, the gate's eight outcomes, the package surface, version
consistency across three files, every relative link in `SKILL.md` resolving, and the shipped
templates passing the shipped validator. Three are safety tests — that an anchor is never
executed unasked, that it is not executed once the frozen spec has moved, and that the
validator never edits an artifact.

## License

MIT
