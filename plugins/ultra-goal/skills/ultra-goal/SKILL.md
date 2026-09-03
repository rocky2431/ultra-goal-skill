---
name: ultra-goal
description: "Turn \"make an agent keep doing this\" into a goal a host will hold to: interview for intent, anchor, stop condition, boundary, droppable means and an adversarial verifier, refuse the shapes that fail, then emit the artifact - a goal line to paste, a workflow script, or a cross-vendor delegation package. Runnable, not a design note. Not for carrying out a goal already running."
license: MIT
metadata:
  author: rocky2431
  version: "1.3.0"
---

# UltraGoal

The owner has an objective they want an agent to pursue without them in the room. Your job
is to interview them until that objective has an intent, an anchor that cannot be argued
with, a stop condition a machine can evaluate, a boundary, means labelled by whether they
may be dropped, and a verifier that is not the generator — then write the prompt or script
that pursues it and hand it off.

**The goal is the invariant; loop and graph are two shapes it compiles to.** Neither is an
upgrade of the other. The distinction is *when routing gets decided*, and a graph is what
you can only write once you already know the route. Most work is a loop. Reach for a graph
only when a loop provably cannot hold it.

The agent gets wide latitude inside that frame: it picks the method, drops means that turn
out not to serve the intent, and rewrites its own carried state. **That latitude is exactly
why every claim it makes has to be checkable against something it did not author.** Wide
authority and zero trust in self-report are the same design decision, not opposing ones.

## Keep activation scoped

Use this Skill when the deliverable is an **executable artifact**: a goal the owner pastes
into their CLI and walks away from, a workflow script, or a delegation package other agents
consume.

The goal's own boundary — what it may touch, and which of its effects need approval before
they run — is question 5 below and belongs here. A broader authority model for an agent
that is not pursuing a goal does not: answer that directly instead of building a goal
around it.

Running it is not this Skill either. It stops when the artifact validates and the owner
has the command.

## Recognize the intent first

Work out which of these the owner is asking for before classifying anything. Guessing
wrong either wastes an interview or silently overwrites a loop that is already running.

| Intent | What it sounds like | Do this |
|---|---|---|
| **Create** | "make an agent keep doing this", "turn this into something that runs itself" | Run the interview below |
| **Modify** | "change the stop condition", "it keeps doing X", or the request names an existing slug | Jump to *Modify an existing loop* |
| **Inspect** | "what loops do we have", "is it still running", "why did it stop" | Report status and change nothing |
| **Not a loop** | a one-shot task, an ordinary code change, a question that wants an answer | Say so and do the work directly |
| **Executing** | a pasted goal line, or a request from inside a run that is already underway | **Do not activate.** Do the work the goal asks for |

Derive it from the request plus what is on disk rather than asking. Whenever the project's
workflows directory is non-empty, **run the status command before the first question**: an
existing artifact covering the same subject means the intent is Modify, not Create.

### The one intent that is not a request for this Skill

A pasted goal line is dense with this Skill's own vocabulary — intent, anchor, boundary,
carry-over, turns, stop condition — because this Skill wrote it. That makes **executing a
goal** the intent most likely to pull the Skill in wrongly, and the damage is specific:
interviewing an owner who is not in the room, about a goal that was already agreed, while a
run burns its turn ceiling on the conversation.

Two signals, either of which is enough to stay out:

- The request **is** a goal line — it opens with a host's goal command, or it reads as
  instructions addressed to the agent rather than a request addressed to you.
- `.goals/active` names an existing artifact and the request is a step of that work rather
  than a change to its terms.

The second signal is worth reading twice, because the same project state means opposite
things depending on the request. "Make it stop after three turns" while a goal is active is
**Modify**. "Upgrade the next package" while a goal is active is **Executing** — the run
doing its job, and no business of this Skill's.

When you are unsure, do the work rather than the interview — and then **actually spend the
sentence.** A missed activation costs one sentence offering to design the goal properly; a
wrong activation costs a turn of the ceiling and replaces the run with a conversation. So:
do the work, and if the objective was underspecified in a way that cost you something, say
so once at the end, naming what was missing. That turns a miss into a lead instead of
silence, and it is the only reason erring this way is cheap.

## Interview protocol

- **One question per turn.** Wait for the answer. Several at once means the owner answers
  the easy one and skips the load-bearing one.
- **Every question carries your recommended answer** and what would change it. A question
  without a recommendation moves work onto the owner instead of sharpening it.
- **Facts are yours, decisions are theirs.** Resolve anything the repository, git history,
  test config, CI, or a tool can tell you before asking. Check the project's and the user's
  `CLAUDE.md` (or equivalent) for a standing answer and skip that question when you find one.
- **Do not write the artifact until the owner confirms** the decisions read back correctly.
  Not the first plausible agreement — an explicit confirmation.

## Classify first, then confirm at the end

Ask the one-minute test before anything else:

> Can you sketch the whole thing on paper before running any of it?

- **Yes** → graph-shaped. Routing was decided at authoring time; the edges are code and
  cost nothing per run.
- **"I'd need to know what step three returns"** → loop-shaped. Routing is decided during
  inference, every iteration, and billed every time.

Topology is not the distinction — a loop is a directed cyclic graph. **When the routing
decision is made** is the distinction, and everything else follows from it.

The first answer is provisional. Re-check it after the interview: detail often turns an
imagined graph into one loop with a good stop condition, and occasionally the reverse.

## Three tiers of frozen

"The North Star does not move, the details do" needs a sharper line than that, because the
interesting cases are in between. Three tiers, and the middle one is the one worth naming:

| Tier | What | Changeable mid-run | On change |
|---|---|---|---|
| **Frozen** | `## Intent`, `## Boundary`'s three refusals, `## Anchor`, and `## Means`'s labels | **No** | Stop and report; this reopens the interview and lands in `decisions.md` |
| **Firm** | the stop condition's threshold, the turn ceiling, who verifies, the cadence, and **dropping a means labelled droppable** | Yes | Allowed, but **write the row in `decisions.md`** - a silently moved threshold is indistinguishable from a moved goal |
| **Fluid** | `### State`, `### Lessons`, `### Next`, how the work actually gets done | Yes | Just do it; that is what they are for |

The Firm tier is where the latitude lives. Dropping a droppable means is a real decision the
run is authorized to make on its own — that is the difference between an agent with judgement
and an agent that stops at every surprise — and the price of making it is one row saying what
the evidence was.

Two different things enforce these tiers, and it is worth knowing which is which.
**Frozen is mechanically observed**: the gate digests `## Intent`, `## Boundary` and
`## Anchor` on the first turn and compares on every later one, so a moved goalpost ends the
turn with an alarm and shows up in `--audit`.
**Firm is enforced socially**, by asking for the row — a threshold edit looks like any other
edit. What makes the asking worth it: the row is what tells a later reader whether the run
met a goal or met a goal that had been made easier.

## Interview in this order

Each answer unblocks the next. Skip any question whose answer you already derived.

Write `<slug>.decisions.md` as you go — one row per confirmed answer, before the artifact
exists. That record is also the interview's progress: if the session ends or context is
lost, read it and resume from the first unanswered question instead of starting over.

1. **Intent** — what gets better when this runs? One sentence about the outcome, not a
   list of steps. If they can only describe steps, the loop has no reference and cannot
   tell progress from motion.
2. **Anchor** — how do we know it actually got better? Demand a command whose output
   cannot be argued with: a test exit code, a build result, a query count, an on-chain
   receipt. A dashboard, a self-report, or another agent's opinion is not an anchor.
   **No anchor, no artifact** — say so plainly and go back to this question.
   **And it has to cross the whole path.** A unit suite exercises the code, not the
   product, so it can be green while the thing does not start — the failure Anthropic
   names as an agent that "would fail to recognize that the feature didn't work end to
   end", with unit-tests-only listed as the anti-pattern. Where a build is not enough — a
   UI, an API contract, a payment path — the anchor drives the running thing. Ask how long
   it takes, too, and write `budget: N minutes` under `## Anchor`: the gate's default is
   its own guess, and an anchor that overruns is reported *unknown*, never failed.
3. **Stop condition** — when does it stop? Express it with the anchor plus a ceiling
   (`0 high-severity advisories, or 6 turns`). The owner defines "good enough"; the moment
   the agent decides that for itself, the loop optimizes its own comfort.
   **If it will be started more than once, enumerate it.** One sentence plus one anchor
   answers *is the whole thing done*; it cannot answer *which parts are*, and that second
   granularity is where a long run declares victory early. So a goal with a `## Cadence`
   also gets `## Acceptance`: one unordered line per requirement, each carrying the state
   the run claims for it. `[x]` is a claim; the anchor's output is the evidence.
   **Unordered, never numbered** — ordered steps are an author-time decomposition, which
   is a plan, which is a graph. See
   [references/document-system.md](references/document-system.md) for where that line
   sits, because a list of requirements is the thing most easily mistaken for a ledger.
4. **Means** — what do you believe it takes to get there, and **which of those would you
   give up if it turned out not to serve the intent?** Label each one `[load-bearing]` or
   `[droppable]`. This is the question that decides how much latitude the run actually has:
   without the labels, abandoning a feature is indistinguishable from scope drift, so the
   run must either stop on everything or drop things quietly. Neither is what you want. The
   labels are yours; the argument for using one is the agent's, and it costs a row in
   `decisions.md`.
5. **Boundary** — three refusals, not one. A specified agent needs all three, and each
   answers a different way loops go wrong in production:
   - **Scope**: what must it never touch? Paths, effects, and the commit gate. Anything
     reversible inside the boundary needs no approval; anything outside does.
   - **Confidence**: what must it never claim without the anchor's output? "Safe",
     "passing", "done" are claims, and a loop that makes them from reasoning has stopped
     being grounded.
   - **Inference**: what must it never conclude from documents alone? A changelog, an
     issue thread, or another agent's report explains nothing until it is reproduced.
6. **Verifier** — who checks the result, and **who checks the checker?** Two roles, because
   one is measurably not enough: a reviewer with a fresh context (an agent grading its own
   output praises it), plus a critic that audits the *review* rather than the code. Name the
   round cap too, and name **what each role is given**: the reviewer gets the frozen
   artifact, the criteria, and the anchor's output — never the author's account of why the
   work is correct, because a reviewer handed that account reviews the account. See [references/adversarial-review.md](references/adversarial-review.md);
   the short version is that three roles beat a five-agent panel, and the third role is why.
7. **Shape and split** — confirm loop or graph. If graph, the split must follow **context
   boundaries**, never workflow phases (see the refusals below), and each worker needs its
   own anchor.
8. **Read and write surface** — what does each turn *read*, and what does it *write*? This
   sharpens the boundary from "don't touch X" into "reads A, writes B", and it decides what
   `## Carry-over` has to hold: whatever a turn can read for itself does not belong there,
   and whatever it cannot must.
9. **Divergence handling** — when reality and the plan disagree, does the loop adjust itself
   or stop and report? Where is the line? **Recommended default: execution details adjust
   themselves; the intent, the anchor, and the boundary always stop and report.** A loop that
   can revise its own target drifts further from the owner the longer it runs, and that is
   the one failure no amount of anchoring catches.
   **And "report" needs somewhere to land.** A stop-and-report that exists only as prose in
   a session is gone at the next compaction, so it goes into `## Challenges from the run` in
   the decisions record: the term, what the run hit, and what would settle it. See
   *The one thing the goal can learn from* below.

Read [references/loop-primitives.md](references/loop-primitives.md) for which loop
primitive fits, and [references/graph-topology.md](references/graph-topology.md) when the
answer is a graph.

## The one thing the goal can learn from

Look at what learns and what does not. `### Lessons` carries **method** forward: this
approach failed for this cause, try that instead. `### Next` re-aims **within** the terms.
Both improve how the work is done. Neither can say *the terms themselves are wrong* — that
is frozen, and correctly so.

So there is exactly one thing a run knows that the design side cannot: **which of the terms
turned out to be unworkable in contact with reality.** And until now that was the only kind
of turn that wrote nothing down. Every other outcome writes an event; "the goal is wrong"
produced a sentence in a session that gets compacted away.

`## Challenges from the run` is that channel, and it is deliberately small:

| | |
|---|---|
| **Written by** | the run, and only the run — it is the one part of `decisions.md` the owner does not author |
| **Ruled on by** | the owner. A challenge is not a decision, and `--status` counts them apart for that reason |
| **Shape** | the term challenged, what the run hit, what would settle it. All three, or it is a complaint rather than an objection |
| **Instead of** | editing the term. A run that edits the term has moved the goalpost; a run that challenges it has done the owner a favour |
| **Read by** | the next Modify pass, which already has to read this file first — so the objection lands exactly where the next design pass is required to look |

**Optional on purpose.** Most runs raise none, and demanding one per run would produce
invented objections — the same failure as a reviewer who must find something. An empty
section gets deleted, not filled.

This is the edge that makes the goal itself iterate rather than only the method. Without it
a wrong term survives every round: the anchor keeps failing, the lessons keep explaining
*how* it failed, and nothing ever says *what was wrong to ask for*.

## Refuse these shapes

Name the refusal, name the cheap alternative, and go back to the relevant question.

| Shape | Why it fails | Cheap alternative |
|---|---|---|
| Split by phase (plan / implement / test as separate agents) | Each phase needs the previous phase's context; handoffs degrade it and coordination outspends the work | One agent for the whole slice, plus one independent verifier |
| Generator grades itself | It praises its own output; tuning a skeptical separate evaluator is far more tractable | A second agent with a fresh context and blackbox criteria |
| Stop condition left to the agent's judgement | "Good enough" drifts toward whatever ends the turn | Anchor command plus a turn ceiling |
| No anchor | Everything stays internally consistent while quietly detaching from reality | Stop and answer question 2 |
| Loops that only watch other loops | A closed network of mutual confirmation fails like a single loop, later and with more green lights | At least one node reads the world; freeze the rules the optimizer would want to weaken |
| One optimized metric, alone | Optimized hard enough, it stops measuring what it once did | Pair it with a counter-metric that catches the cheap way to win |
| Nodes added for sophistication | Every extra agent is another failure point and 3-10x the tokens | Ship the loop; promote to a graph when it provably breaks |
| **False consensus** — two agents both say "looks fine" | That is one opinion reported twice, and a loop cannot tell it from verification | A critic that audits the *review*, sorting each point into agreement / evidence-backed disagreement / concern-based disagreement |
| **Wrapping up because the context feels full** | Named *context anxiety*: a model begins closing out as it nears what it *believes* is its limit, so the run ends on a feeling rather than on the anchor. Compaction does not fix it — continuity is preserved, the sense of pressure is not | The gate is the mechanical answer: it refuses the stop while the anchor is red. State the turn out loud, and treat "running low" as a reason to write carry-over, never as a reason to declare done |
| **An anchor that only tests the code** | A unit suite is green when the code compiles and the product is still broken; this is the single most common way a loop finishes proud and wrong | Make the anchor drive the running thing — build plus start plus one real interaction |
| **A verdict with no receipt** — "tests pass", "the anchor is green" | The log the gate writes is the evidence; a sentence is a claim, and after a compaction the run cannot tell its own claims from its evidence either | Report the turn and the exit code seen, and let `--audit` compare them |
| **The reviewer gets the author's argument** | Handed an explanation of why the work is right, a reviewer reviews the explanation; this is context contagion, and it survives changing vendors | Give the reviewer the frozen artifact, the criteria, and the anchor's output — nothing about the author's confidence |
| **Reviewers split by domain** — one per concern, reports merged | Nobody audits either report, and the orchestrator has no independent evidence to arbitrate; measured as unreliable | Domains become one reviewer's checklist; add a critic instead of a second reviewer |

Read [references/anti-patterns.md](references/anti-patterns.md) for the failure modes
behind this table.

## Goal mode, on whichever host you are

You are the host. Goal mode is the mechanism: the owner pastes one objective into their CLI,
walks away, and the host keeps the model working until the objective is met or a ceiling is
hit. Four of the
five hosts measured on this machine have it as an interactive command:

| Host | Goal mode | Notes |
|---|---|---|
| Claude Code | `/goal <objective>` | backed by a stop hook; also has `/loop`, `/schedule` |
| Codex 0.150.1 | `/goal <objective>` | a `goal` extension accounts progress after every tool call |
| Kimi | `/goal <objective>` | plus `/goal pause` / `resume` / `cancel` |
| zCode 0.16.5 | `/goal <objective>` | also `--target` for a headless session |
| OpenCode 1.18 | not found | fall back to a plain prompt with the ceiling stated in words |

"Not found" means no evidence in that host's help output or shipped binary, not proof of
absence — **check your own host rather than trusting this table**, and say so when it is
wrong. Use the host's own goal mode; it is better integrated than anything this Skill could
wrap around it.

### The host decides when to stop asking. The anchor decides what counts as done.

A host's goal mode keeps the model working, but it asks **the model** whether the objective
is met. That is the gap this Skill closes, and it closes it in the goal text itself rather
than with any machinery:

```
/goal <what to achieve, inside <scope>>. You have not met this goal until you have actually
run `<anchor command>` in this session and seen it <exact result> - do not claim completion
from reasoning, and do not state <confidence claim> without that output. When you report on
the anchor, name the turn and the exit code you saw rather than summarising it. Do not
conclude <inference> from documents alone; reproduce it. You are the run for <slug>, not its
designer: the terms were already agreed, so do not reopen them as an interview. If a means
labelled droppable turns out not to serve the intent, drop it and write the argument into
<slug>.decisions.md; never drop a load-bearing one, and never edit Intent, Boundary or
Anchor - if one of those is wrong, stop and write a row under `## Challenges from the run`
naming the term, what you hit, and what would settle it. At the start of each turn, state
which turn you are on, which `## Acceptance` lines this turn is for, and what output would
prove them - before changing anything. Rewrite the Carry-over section before you finish,
including the single objective under `### Next`. Stop after <N> turns even if unmet, and
say so.
```

Nine clauses, each closing one hole:

| Clause | Closes |
|---|---|
| objective inside a scope | scope creep |
| anchor as the only accepted evidence | claiming success from reasoning |
| no confidence claim without that output | inappropriate confidence |
| the verdict reported as a turn and an exit code | a verdict nobody can check against the log |
| no conclusion from documents alone | inference beyond the data |
| the run is the run, not the designer | this Skill re-activating inside its own output and interviewing nobody |
| droppable means droppable; a wrong term gets challenged, not edited | silent scope drift, stopping at every surprise, and an objection that dies in the session |
| the turn, its acceptance lines, and their evidence stated up front | losing count of the ceiling, and a turn whose "done" was decided after the work |
| rewrite carry-over, `### Next` included | the run never learning, and never re-aiming |

The turn clause matters more than it looks. A host may hand the model a live iteration count
— Claude Code attaches `{condition, iterations, durationMs, tokens}` to every turn under an
active goal — but the model will not use it unless told to. Saying the number out loud each
turn makes the ceiling real rather than a number it estimates by feel.

Written this way the same text works on all four hosts, and on the fifth as a plain prompt.

Record which host it was written for in the decisions record — the objective is portable, the
command that starts it is not.

## This is a graph, and here is where its nodes live

The artifact is not a document that happens to describe a loop. It **is** the graph, with one
node per section. Naming that explicitly is what makes it checkable against the ways loops
fail:

| Node | Lives in | Kind |
|---|---|---|
| North Star | `## Intent` | **frozen** — the run may never edit it |
| Scope / confidence / inference limits | `## Boundary` | frozen |
| What may be given up, and what may not | `## Means` | labels frozen; dropping a droppable one costs a `decisions.md` row |
| Mechanical gate | `## Anchor` | executed, exit code only, on the artifact's own budget |
| The stop condition, enumerated | `## Acceptance` | required once there is a cadence; unordered, each line's state a claim the anchor settles |
| Adversarial review — reviewer | `## Verification` | fresh context, verdict advisory |
| Adversarial review — critic | `## Verification` | audits the review, not the artifact |
| Reflection | `### Lessons` | writes the next turn's input |
| Carried state | `### State` | rewritten each turn |
| Re-aim | `### Next` | exactly one objective, inside the frozen intent |
| The run's objection to its own terms | `## Challenges from the run` in `<slug>.decisions.md` | written by the run, ruled on by the owner |
| Edges (what happens in what order) | the clause order of `## Handoff` | authored once |
| Proof an edge was actually taken | `<slug>.events.jsonl` | append-only, **written by the hooks and never by the run** |

Checked against the four ways a single loop fails, plus the way a graph of loops fails:

| Failure | What closes it here |
|---|---|
| Goodhart — the metric gets gamed | `## Verification` is the paired counter-check; the anchor is the half that cannot be argued with |
| **False consensus — the check agrees without evidence** | the critic sorts each point into agreement / evidence-backed / concern-based, and the reviewer must answer with evidence |
| Blindness upward — the loop cannot question its target | `## Intent` is frozen; question 9 sends target-level divergence back to the owner |
| Conflict — independent loops undermine each other | one operating loop per artifact, so there is no collision surface |
| Measurement decay — nobody watches the watcher | the anchor runs for real every turn, and reports *unknown* when it cannot |
| **Context anxiety — the run closes out on a feeling** | the gate refuses the stop while the anchor is red, so ending the turn early is not available; `## Acceptance` makes what is left explicit rather than a memory |
| Circularity — everything confirms everything, nothing touches reality | the anchor is the one node whose verdict passes through no model at all |

## Compile one artifact

Name it after the work, and always write the paired decisions record. Default location is
the project's `.goals/` — these are project assets that belong in Git and may be read by
whichever agent a teammate runs, so they do not go inside any one tool's private directory.

| Answer | Artifact | Template |
|---|---|---|
| Loop | `<slug>.goal.md` — objective, boundary, stop condition, anchor, verifier, and `## Handoff` holding the goal line to paste; add `## Cadence` + `## Acceptance` + `## Carry-over` if it will be started more than once | [assets/goal-package.md](assets/goal-package.md) |
| Graph, one vendor **(requires a workflow runtime)** | `<slug>.workflow.js` — topology in code, `meta` first and a pure literal, anchor on the top line as `` // anchor: `<command>` `` | [assets/workflow-script.js](assets/workflow-script.js) |
| Graph, several vendors | `<slug>.delegation.md` — one adversarial-review triad: reviewer, critic, convergence rule | [assets/delegation-package.md](assets/delegation-package.md) |
| Always | `<slug>.decisions.md` — Decision / Rejected / Why, three columns | [assets/decisions-record.md](assets/decisions-record.md) |

**A workflow script needs a workflow runtime.** Of the hosts measured, only Claude Code has
one, so where yours does not, do **not** emit `<slug>.workflow.js` — it would be a file
nothing can run. Keep it one goal, or use the cross-vendor delegation shape.

The decisions record holds decisions, not architecture. The script or prompt is the only
description of what the thing does; a second prose copy of it goes stale and starts lying.
When the owner revises a decision later, **edit that row** and move the old decision into
the Rejected column — never append a history log.

Write the artifact yourself. Do not generate topology from a template engine: which nodes
exist and how they connect is the design, and it is yours and the owner's to author.

## Inspect what is running

```bash
python3 scripts/validate_artifact.py .goals --status
```

Reports each artifact's shape, anchor, stop condition, declared phases or workers, how many
decisions its record holds, and any validation finding.

**Nothing is stored.** The artifacts on disk are the only record and this is a projection of
them, recomputed on every call — so the report cannot drift out of date the way a tracked
state file would.

```bash
python3 scripts/validate_artifact.py .goals --audit
```

Puts each turn's committed verdict beside the verdict the gate measured for that turn, and
names every row where they disagree. This is the reverse-tracing view: on a run that went
wrong, the first row where claim and measurement part company is where to start reading.
It reads Git history and the event log; it runs nothing.

Add `--run-anchors` to `--status` to execute each anchor and report its exit code. That answers the only
question that really matters about a running loop — *did the work actually land?* — but it
runs commands the artifact names, in a shell. Ask the owner first, and never run it against
an artifact you have not read.

## Modify an existing loop

Read both files before changing either. The artifact says what runs; the decisions record
says what was already rejected and why, which is usually the answer to "why doesn't it just
do X".

1. Run the status command to confirm which artifact and which shape.
2. Find the decision the owner wants to change. **If the request contradicts a row already
   in the Rejected column, say so** and ask whether the reason has stopped holding. Do not
   quietly reverse a decision the owner made for a reason they may still hold.
   **Read `## Challenges from the run` before anything else in that file.** If the run
   objected to a term, that objection is the most informed thing in the record — it came
   from contact with reality rather than from the interview — and it should be put to the
   owner in this pass rather than left standing. Once ruled on, the row moves into the
   decisions table (accepted, with the old term in Rejected) or is deleted with the reason.
3. Change the artifact.
4. **Edit the affected row** of the decisions record: the new decision replaces the old one
   in the Decision column, and the old one moves to Rejected with why it changed. Never
   append a second table or a dated log.
5. Re-validate. A modification that breaks the pairing or a required section is not a
   modification, it is a broken artifact.

If the change alters the intent or the anchor rather than a detail, stop modifying and run
the interview again. A loop whose anchor changed is a different loop.

## Make the loop evolve

An unattended loop wakes with an empty context every iteration — and inside one long goal
run, compaction has the same effect. Unless something carries forward it rebuilds history
from git logs and retries paths it has already proven dead, believing each time that it is
the first attempt.

So any artifact with a `## Cadence` — it will be started more than once — gets a
`## Carry-over` section, and the goal text itself must tell the loop to
**read it before acting and rewrite it before finishing**.
Without that instruction the section stays empty forever and the loop never improves. A goal
started once and watched needs neither section.

It has three parts, with different jobs and different budgets:

- **`### State`** — where the work stands. Facts, cheap to carry: what is left, what the
  last green build was, which shard is next. At most 8.
- **`### Lessons`** — **why something failed and what to do instead.** At most 3.
- **`### Next`** — the one objective for the next round, derived from this round's anchor
  verdict and the review findings that survived it, inside the frozen intent. **Exactly
  one.** A list of them is a plan, and a goal that has grown a plan should have been
  authored as a graph — which is also why there is no task ledger here.

`### Next` is the edge that closes the loop. Without it a run re-attempts the same objective
until the anchor goes green or the ceiling hits; with it, each round aims at what the last
round's evidence actually implies. The frozen intent is what keeps re-aiming from becoming
drifting.

The Lessons budget is not arbitrary. Reflexion (arXiv 2303.11366) bounds its reflection
memory at 1-3 entries, because entries the model must actually reason over compete with the
work for the same budget. Twenty lessons is a log nobody reads.

**A lesson is a cause and a next action, not an event.** This is the difference between a
loop that learns and one that keeps a diary:

| Not a lesson | A lesson |
|---|---|
| "the build failed" | "the build fails without a committed lockfile because CI runs `--frozen-lockfile` — commit the lockfile in the same change" |
| "`@types/node` 22 broke" | "`@types/node` 22 breaks tsconfig because the bundler resolver rejects its new conditional exports — pin at 20 until tsconfig moves to `node20`" |

The left column is what an agent writes by default. Asking for the right column is the whole
mechanism: it forces the credit assignment that makes the next iteration different.

**Rewrite, never append.** An entry that stops being true gets deleted. Three places, three
jobs:

| What you want to see | Where it lives |
|---|---|
| What is true now | `### State` and `### Lessons` — current only, pruned |
| How it became true | `git log -p <slug>.goal.md` — the diffs *are* the evolution |
| What each iteration did | the commit message — one line per iteration |

Commit once per iteration that changed anything, with a message shaped so the log is the
trajectory:

```
goal(<slug>) turn <N>: <one line on what changed> [anchor: green|red|unknown]
```

`git log --oneline -- .goals/<slug>.goal.md` then reads as the run, one line per turn, with
each turn's verdict on it. That is what puts the evolution in Git, and why the document never
has to hold history itself.

What a loop learns stays in that project, beside its artifact:
one project's dead end is another project's correct answer.
**Never** promote it to user-level configuration or into
this Skill. And keep the shape at one artifact, one decisions record, one carry-over
section, and Git: no directory tree, no index, no ledger, no state machine, and no second
copy of what Git already holds.

Read [references/evolution-and-scope.md](references/evolution-and-scope.md) for why each of
those boundaries is drawn where it is.

## The gate: what the hooks do, and what they cost

On a host that exposes the events, three hooks ship with this Skill and register on install.
They turn the anchor from a sentence in a prompt into a gate that actually runs.

| Hook | Does | Can it block? |
|---|---|---|
| `Stop` | Digests the frozen spec, then runs the anchor. Eight steps, seven of which let the turn end | **Yes, in exactly one case**: the anchor ran and was red |
| `SessionStart` | Re-injects the frozen spec and the carried state after a restart or resume | No |
| `PreCompact` | Records the carried state and the fact of the compaction into the event log | No |

**Three outcomes, not two.** An anchor that cannot run — command missing, not executable,
timed out — is **unknown**, not failed. Folding unknown into either verdict is how a
mechanical gate starts lying, and a timeout is the clearest case: it measures elapsed time
and reports it as success or failure, two things it has no access to. Unknown lets the turn
end and says the result is unverified.

**Seven of the eight steps allow.** The gate refuses only when it is certain. Frozen spec
changed, ceiling reached, run not progressing, anchor unrunnable, anchor green, no anchor at
all, no active goal — all let the turn end and say why.

**A moved goalpost allows on purpose.** The gate records a digest of `## Intent`,
`## Boundary` and `## Anchor` on the first turn and compares it on every later one. When it
differs, the run is no longer pursuing the goal the owner authorized — and denying the stop
would only make it work harder against a target nobody agreed to. So the turn ends, loudly,
and the owner gets the decision back.

### What it costs a project that never asked for one

Every hook's first act is the same check: is there a `.goals/active` marker naming an
artifact that exists? Without one, nothing is read, nothing is written, no command runs.

| Situation | Cost |
|---|---|
| No `.goals/` at all | One process start and one `stat` per registered hook |
| `.goals/` with no `active` marker | Same |
| `active` naming a missing artifact | Same, plus one line saying so |
| A re-entered Stop (`stop_hook_active`) | Hard early exit — this is the guard against a gate that denies forever |
| Anything raising an exception | Exit 0. A hook that cannot decide must let the host continue |
| **Escape** | `rm .goals/active`, or `ULTRA_GOAL_HOOKS_DISABLED=1`. Neither needs the agent's cooperation |

`PostToolUse` is deliberately **not** registered: it fires once per tool call, so its cost
scales with tool use, and its value duplicates what `SessionStart` already injects and what
the goal text already demands each turn. It gets added when a real run shows the loop
retrying a path its own `### Lessons` already ruled out — not before.

`UserPromptSubmit` is not registered either, and it is the more tempting of the two: it
could catch a wrong activation exactly, by checking whether the submitted prompt contains an
artifact's own `## Handoff` block — an exact match against a file on disk, not a keyword
guess. It stays unbuilt because the instruction-level fix comes first and has not been shown
to fail: the exclusion is in this Skill's `description`, and the goal text itself says *you
are the run, not its designer*, which reaches all four hosts rather than only this one. The
trigger to build it: a real session where a pasted goal line pulled this Skill into an
interview anyway.

### Wide latitude, zero trust in self-report

The run picks its own method, drops means that stop serving the intent, and rewrites its own
carried state. Every one of those is a semantic judgement and none of them is mechanically
checkable. **That is exactly why the few facts that are checkable must be kept out of the
run's hands:**

| Written by | What | Read as |
|---|---|---|
| the run | the artifact, `### Lessons`, the commit message, a review | a claim |
| the hooks | `<slug>.events.jsonl` — exit codes, output digests, spec digests | evidence |

Nothing sits in between, and `--audit` is the comparison. A divergence is reported, never
resolved: the gate does not know *why* turn 4 claimed green, only that it measured red.

Two limits, stated because a control that oversells itself is worse than no control. The run
can write any file it can read, `events.jsonl` included — what stops tampering is that the
log is committed, so a rewritten history shows up in `git log` instead of passing silently.
Making a moved goalpost **visible** is the achievable property; making it impossible is not.
And the review's verdict stays advisory: only the anchor may deny a stop, because only its
exit code is a fact rather than an opinion about one.

Read [references/zero-trust.md](references/zero-trust.md) for which control distrusts what,
and [references/document-system.md](references/document-system.md) for which file owns what.

## Validate, then hand off

```bash
python3 scripts/validate_artifact.py .goals --json
```

It checks mechanical facts only — pairing, required sections, declared phases, known
delegation targets, JavaScript syntax — and never edits the artifact. Fix what it reports;
its silence is not evidence that the design is right.

Then hand off in one line: the exact command the owner pastes, and what the first iteration
should produce. Spell it out — this host's goal line, the workflow runtime's own entry point,
or one delegation call per worker with its working directory and mission file. Assume no other Skill is installed to fill in the gaps, and state which effects the
owner has already authorized and which still need approval.

Do not run it yourself unless the owner asks.

## Version this Skill

Bump the version in three places together — the plugin manifest, this file's `metadata`,
and the installer's `VERSION`. A test fails if they disagree.
