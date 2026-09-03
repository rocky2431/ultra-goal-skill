---
name: loop-graph-design
description: "Turn \"make an agent keep doing this\" into a goal the host will actually hold to: interview for intent, anchor, quantified stop condition, boundary, and an independent verifier, refuse the shapes that fail, then emit the runnable artifact — a goal line to paste, a workflow script, or a cross-vendor delegation package. Use when the deliverable is runnable, not a design note."
license: MIT
metadata:
  author: rocky2431
  version: "0.8.0"
---

# Loop Graph Design

The owner has work they want an agent to keep doing. Your job is to interview them until
the loop has an intent, an anchor that cannot be argued with, a stop condition a machine
can evaluate, a boundary, and a verifier that is not the generator — then write the prompt
or script that starts it and hand it off.

Most work is a loop. Reach for a graph only when a loop provably cannot hold it.

## Keep activation scoped

Use this Skill when the deliverable is an **executable artifact**: a goal the owner pastes
into their CLI and walks away from, a workflow script, or a delegation package other agents
consume.

The loop's own boundary — what it may touch, and which of its effects need approval before
they run — is question 4 below and belongs here. A broader authority model for an agent
that is not a loop does not: answer that directly instead of building a loop around it.

Running the loop is not this Skill either. It stops when the artifact validates and the
owner has the command.

## Recognize the intent first

Work out which of these the owner is asking for before classifying anything. Guessing
wrong either wastes an interview or silently overwrites a loop that is already running.

| Intent | What it sounds like | Do this |
|---|---|---|
| **Create** | "make an agent keep doing this", "turn this into something that runs itself" | Run the interview below |
| **Modify** | "change the stop condition", "it keeps doing X", or the request names an existing slug | Jump to *Modify an existing loop* |
| **Inspect** | "what loops do we have", "is it still running", "why did it stop" | Report status and change nothing |
| **Not a loop** | a one-shot task, an ordinary code change, a question that wants an answer | Say so and do the work directly |

Derive it from the request plus what is on disk rather than asking. Whenever the project's
workflows directory is non-empty, **run the status command before the first question**: an
existing artifact covering the same subject means the intent is Modify, not Create.

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
3. **Stop condition** — when does it stop? Express it with the anchor plus a ceiling
   (`0 high-severity advisories, or 6 turns`). The owner defines "good enough"; the moment
   the agent decides that for itself, the loop optimizes its own comfort.
4. **Boundary** — three refusals, not one. A specified agent needs all three, and each
   answers a different way loops go wrong in production:
   - **Scope**: what must it never touch? Paths, effects, and the commit gate. Anything
     reversible inside the boundary needs no approval; anything outside does.
   - **Confidence**: what must it never claim without the anchor's output? "Safe",
     "passing", "done" are claims, and a loop that makes them from reasoning has stopped
     being grounded.
   - **Inference**: what must it never conclude from documents alone? A changelog, an
     issue thread, or another agent's report explains nothing until it is reproduced.
5. **Verifier** — who checks the result? It must be an agent that never saw the generator's
   reasoning. An agent grading its own output praises it. Also name what makes the verifier
   fail closed, or it will pass the work after a superficial look.
6. **Shape and split** — confirm loop or graph. If graph, the split must follow **context
   boundaries**, never workflow phases (see the refusals below), and each worker needs its
   own anchor.
7. **Read and write surface** — what does each turn *read*, and what does it *write*? This
   sharpens the boundary from "don't touch X" into "reads A, writes B", and it decides what
   `## Carry-over` has to hold: whatever a turn can read for itself does not belong there,
   and whatever it cannot must.
8. **Divergence handling** — when reality and the plan disagree, does the loop adjust itself
   or stop and report? Where is the line? **Recommended default: execution details adjust
   themselves; the intent, the anchor, and the boundary always stop and report.** A loop that
   can revise its own target drifts further from the owner the longer it runs, and that is
   the one failure no amount of anchoring catches.

Read [references/loop-primitives.md](references/loop-primitives.md) for which loop
primitive fits, and [references/graph-topology.md](references/graph-topology.md) when the
answer is a graph.

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
from reasoning, and do not state <confidence claim> without that output. Do not conclude
<inference> from documents alone; reproduce it. State which turn you are on at the start of
each turn. Rewrite the Carry-over section before you finish. Stop after <N> turns even if
unmet, and say so.
```

Six clauses, each closing one hole:

| Clause | Closes |
|---|---|
| objective inside a scope | scope creep |
| anchor as the only accepted evidence | claiming success from reasoning |
| no confidence claim without that output | inappropriate confidence |
| no conclusion from documents alone | inference beyond the data |
| state the turn at the start of each turn | losing count of the ceiling |
| rewrite carry-over before finishing | the loop never learning |

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
| Mechanical gate | `## Anchor` | executed, exit code only |
| Adversarial review | `## Verification` | fresh context, its verdict is advisory |
| Reflection | `### Lessons` | writes the next turn's input |
| Carried state | `### State` | rewritten each turn |
| Edges (what happens in what order) | the clause order of `## Handoff` | authored once |
| Proof an edge was actually taken | `<slug>.events.jsonl` | append-only |

Checked against the four ways a single loop fails, plus the way a graph of loops fails:

| Failure | What closes it here |
|---|---|
| Goodhart — the metric gets gamed | `## Verification` is the paired counter-check; the anchor is the half that cannot be argued with |
| Blindness upward — the loop cannot question its target | `## Intent` is frozen; question 8 sends target-level divergence back to the owner |
| Conflict — independent loops undermine each other | one operating loop per artifact, so there is no collision surface |
| Measurement decay — nobody watches the watcher | the anchor runs for real every turn, and reports *unknown* when it cannot |
| Circularity — everything confirms everything, nothing touches reality | the anchor is the one node whose verdict passes through no model at all |

## Compile one artifact

Name it after the work, and always write the paired decisions record. Default location is
the project's `.loops/` — these are project assets that belong in Git and may be read by
whichever agent a teammate runs, so they do not go inside any one tool's private directory.

| Answer | Artifact | Template |
|---|---|---|
| Loop | `<slug>.goal.md` — objective, boundary, stop condition, anchor, verifier, and `## Handoff` holding the goal line to paste; add `## Cadence` + `## Carry-over` if it will be started more than once | [assets/goal-package.md](assets/goal-package.md) |
| Graph, one vendor **(requires a workflow runtime)** | `<slug>.workflow.js` — topology in code, `meta` first and a pure literal, anchor on the top line as `` // anchor: `<command>` `` | [assets/workflow-script.js](assets/workflow-script.js) |
| Graph, several vendors | `<slug>.delegation.md` — one mission per worker, each with its own anchor | [assets/delegation-package.md](assets/delegation-package.md) |
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
python3 scripts/validate_artifact.py .loops --status
```

Reports each artifact's shape, anchor, stop condition, declared phases or workers, how many
decisions its record holds, and any validation finding.

**Nothing is stored.** The artifacts on disk are the only record and this is a projection of
them, recomputed on every call — so the report cannot drift out of date the way a tracked
state file would.

Add `--run-anchors` to execute each anchor and report its exit code. That answers the only
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

It has two parts, with different jobs and different budgets:

- **`### State`** — where the work stands. Facts, cheap to carry: what is left, what the
  last green build was, which shard is next. At most 8.
- **`### Lessons`** — **why something failed and what to do instead.** At most 3.

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

Commit once per iteration that changed anything. That is what puts the evolution in Git, and
why the document never has to hold history itself.

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
| `Stop` | Runs the anchor. Seven steps, six of which let the turn end | **Yes, in exactly one case**: the anchor ran and was red |
| `SessionStart` | Re-injects the frozen spec and the carried state after a restart or resume | No |
| `PreCompact` | Records the carried state and the fact of the compaction into the event log | No |

**Three outcomes, not two.** An anchor that cannot run — command missing, not executable,
timed out — is **unknown**, not failed. Folding unknown into either verdict is how a
mechanical gate starts lying, and a timeout is the clearest case: it measures elapsed time
and reports it as success or failure, two things it has no access to. Unknown lets the turn
end and says the result is unverified.

**Six of the seven steps allow.** The gate refuses only when it is certain. Ceiling reached,
loop not progressing, anchor unrunnable, anchor green, no anchor at all, no active loop — all
let the turn end and say why.

### What it costs a project that never asked for one

Every hook's first act is the same check: is there a `.loops/active` marker naming an
artifact that exists? Without one, nothing is read, nothing is written, no command runs.

| Situation | Cost |
|---|---|
| No `.loops/` at all | One process start and one `stat` per registered hook |
| `.loops/` with no `active` marker | Same |
| `active` naming a missing artifact | Same, plus one line saying so |
| A re-entered Stop (`stop_hook_active`) | Hard early exit — this is the guard against a gate that denies forever |
| Anything raising an exception | Exit 0. A hook that cannot decide must let the host continue |
| **Escape** | `rm .loops/active`, or `LOOP_GRAPH_HOOKS_DISABLED=1`. Neither needs the agent's cooperation |

`PostToolUse` is deliberately **not** registered: it fires once per tool call, so its cost
scales with tool use, and its value duplicates what `SessionStart` already injects and what
the goal text already demands each turn. It gets added when a real run shows the loop
retrying a path its own `### Lessons` already ruled out — not before.

Read [references/document-system.md](references/document-system.md) for which file owns what.

## Validate, then hand off

```bash
python3 scripts/validate_artifact.py .loops --json
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
