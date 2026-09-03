---
name: loop-graph-design
description: "Turn \"make an agent keep doing this\" into a running loop: interview for intent, anchor, quantified stop condition, boundary, and an independent verifier, refuse the shapes that fail, then emit the artifact the host can run — a goal prompt with its schedule, a workflow script, or a cross-vendor delegation package. Use when the deliverable is runnable, not a design note."
license: MIT
metadata:
  author: rocky2431
  version: "0.4.0"
---

# Loop Graph Design

The owner has work they want an agent to keep doing. Your job is to interview them until
the loop has an intent, an anchor that cannot be argued with, a stop condition a machine
can evaluate, a boundary, and a verifier that is not the generator — then write the prompt
or script that starts it and hand it off.

Most work is a loop. Reach for a graph only when a loop provably cannot hold it.

## Keep activation scoped

Use this Skill when the deliverable is an **executable artifact**: a prompt the owner will
run with `/goal` or `/loop`, a Workflow script, or a delegation package other agents
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
4. **Boundary** — what must it never touch? Name paths, effects, and the commit gate.
   Anything reversible inside the boundary needs no approval; anything outside does.
5. **Verifier** — who checks the result? It must be an agent that never saw the generator's
   reasoning. An agent grading its own output praises it. Also name what makes the verifier
   fail closed, or it will pass the work after a superficial look.
6. **Shape and split** — confirm loop or graph. If graph, the split must follow **context
   boundaries**, never workflow phases (see the refusals below), and each worker needs its
   own anchor.

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

## Know your host before compiling

You are the host. Use the primitives you actually have, not the ones a different agent has.
Measured on real installs they differ, and the differences change what you may emit:

| Capability | Claude Code | zCode | Kimi | OpenCode |
|---|---|---|---|---|
| Goal with a stop condition | `/goal` | `/goal`, `--target` | put it in the prompt | put it in the prompt |
| One-shot non-interactive run | — | `--prompt` / `-p` | `-p` / `--prompt` | `opencode run` |
| Built-in scheduling | `/loop`, `/schedule` | none | none | none |
| Single-vendor graph runtime | `pipeline`/`agent`/`phase` | none | none | none |
| Cross-vendor delegation | `agent-delegate` | `agent-delegate` | `agent-delegate` | `agent-delegate` |

Two consequences, and both change the artifact:

- **On most hosts, scheduling is external.** A built-in loop command is sugar for "feed this
  prompt again on a timer". Without one, the same loop is a `cron` entry, a `launchd` agent,
  a systemd timer, or a CI `schedule:` trigger invoking the host's one-shot command. The
  goal package is identical; only `## Cadence` and `## Handoff` change.
- **A single-vendor workflow script needs that runtime.** If your host has no workflow
  engine, do **not** emit `<slug>.workflow.js` — it would be a file nothing can run. Keep it
  one loop, or use the cross-vendor delegation shape, which works everywhere.

Write `## Cadence` and `## Handoff` for the host that will actually run this, and record
which host that is in the decisions record. If you are unsure whether you have a primitive,
check rather than assume — a cadence line naming a command the host does not have is worse
than an honest external schedule.

## Compile one artifact

Name it after the work, and always write the paired decisions record. Default location is
the project's `.loops/` — these are project assets that belong in Git and may be read by
whichever agent a teammate runs, so they do not go inside any one tool's private directory.

| Answer | Artifact | Template |
|---|---|---|
| Loop | `<slug>.goal.md` — the prompt the owner runs with `/goal` or `/loop`; an unattended one also needs `## Cadence` and `## Carry-over` | [assets/goal-package.md](assets/goal-package.md) |
| Graph, one vendor **(requires a workflow runtime)** | `<slug>.workflow.js` — topology in code, `meta` first and a pure literal, anchor on the top line as `` // anchor: `<command>` `` | [assets/workflow-script.js](assets/workflow-script.js) |
| Graph, several vendors | `<slug>.delegation.md` — one mission per worker, each with its own anchor | [assets/delegation-package.md](assets/delegation-package.md) |
| Always | `<slug>.decisions.md` — Decision / Rejected / Why, three columns | [assets/decisions-record.md](assets/decisions-record.md) |

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

An unattended loop wakes with an empty context every iteration. Unless something carries
forward it rebuilds history from git logs — expensively, unreliably — and retries paths it
has already proven dead, believing each time that it is the first attempt.

So a `/loop` or `/schedule` artifact gets a `## Carry-over` section, and the prompt itself
must instruct the loop to **read it before acting and rewrite it before finishing**. Without
that instruction the section stays empty forever and the loop never improves. A one-shot
`/goal` needs neither section.

A few lines, in whatever form each takes: a path already proven dead, a standing fact the
next iteration needs, where the work stopped.

**Rewrite, never append.** An item that stops being true gets deleted, and the validator
reports more than 20 items as unpruned. Three places, three jobs:

| What you want to see | Where it lives |
|---|---|
| What is true now | the `## Carry-over` section — current only |
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

## Validate, then hand off

```bash
python3 scripts/validate_artifact.py .loops --json
```

It checks mechanical facts only — pairing, required sections, declared phases, known
delegation targets, JavaScript syntax — and never edits the artifact. Fix what it reports;
its silence is not evidence that the design is right.

Then hand off in one line: the exact command the owner runs, and what the first iteration
should produce. Spell the command out — a goal or loop invocation, the workflow runtime's
own entry point, or one delegation call per worker with its working directory and mission
file. Assume no other Skill is installed to fill in the gaps, and state which effects the
owner has already authorized and which still need approval.

Do not run it yourself unless the owner asks.

## Version this Skill

Bump the version in three places together — the plugin manifest, this file's `metadata`,
and the installer's `VERSION`. A test fails if they disagree.
