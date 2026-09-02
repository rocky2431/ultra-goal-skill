---
name: loop-graph-design
description: "Turn \"make an agent keep doing this\" into a running loop: interview for intent, anchor, quantified stop condition, boundary, and an independent verifier, refuse the shapes that fail, then emit the executable artifact — a /goal or /loop prompt, a Workflow script, or a cross-vendor delegation package. Use when the deliverable is a runnable prompt or script, not a design note."
license: MIT
metadata:
  author: rocky2431
  version: "0.1.0"
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
consume. Designing an agent's authority model, tool schemas, or approval boundaries is a
different job and belongs to a harness-design Skill. Running the loop afterwards is not
this Skill either — this Skill stops when the artifact validates.

Do not activate for a one-shot task, an ordinary code change, or a question that wants an
answer rather than a repeating process.

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

## Compile one artifact

Name it after the work, and always write the paired decisions record. Default location is
the project's `.claude/workflows/`.

| Answer | Artifact | Template |
|---|---|---|
| Loop | `<slug>.goal.md` — the prompt the owner runs with `/goal` or `/loop`, plus the cadence | [assets/goal-package.md](assets/goal-package.md) |
| Graph, one vendor | `<slug>.workflow.js` — topology written in code, `meta` first and a pure literal | [assets/workflow-script.js](assets/workflow-script.js) |
| Graph, several vendors | `<slug>.delegation.md` — one mission per worker, each with its own anchor | [assets/delegation-package.md](assets/delegation-package.md) |
| Always | `<slug>.decisions.md` — Decision / Rejected / Why, three columns | [assets/decisions-record.md](assets/decisions-record.md) |

The decisions record holds decisions, not architecture. The script or prompt is the only
description of what the thing does; a second prose copy of it goes stale and starts lying.
When the owner revises a decision later, **edit that row** and move the old decision into
the Rejected column — never append a history log.

Write the artifact yourself. Do not generate topology from a template engine: which nodes
exist and how they connect is the design, and it is yours and the owner's to author.

## Validate, then hand off

```bash
python3 scripts/validate_artifact.py .claude/workflows --json
```

It checks mechanical facts only — pairing, required sections, declared phases, known
delegation targets, JavaScript syntax — and never edits the artifact. Fix what it reports;
its silence is not evidence that the design is right.

Then hand off in one line: the command the owner runs (`/goal <file contents>`,
`/loop 30m <prompt>`, the Workflow invocation, or `agent-delegate run`), and what the first
iteration should produce. Do not run it yourself unless the owner asks.
