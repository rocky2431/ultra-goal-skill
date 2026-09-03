# Roles and modes

Who does what, in which stage, and which of those is actually a choice. An earlier version
of this file offered four "modes" side by side - same-model subagents, cross-vendor,
parallel triads, and a graph. That was a menu, not a taxonomy: three orthogonal axes
flattened into one column. The owner caught it. This is the repair.

## Every development round has four stages

Research → shape a plan → carry it out → review and feed back → round again. Loops nested
inside loops. Most of what looks like a choice about "multi-agent or not" is really a
question about **one stage**, and the stages differ in whether there is anything to choose
at all.

| Stage | Who | Choice? |
|---|---|---|
| **Lead** — turn the owner's intent into a spec | the main session, with the owner | **No.** An interview is a conversation with the owner; it cannot be delegated to something the owner is not talking to |
| **Research** — find out what is true before acting | **fanned-out subagents** | Yes: how wide, and whether any of it needs a different vendor |
| **Plan** — the spec, and one adversarial pass over it | main session + a design critic | Yes: whether the design critic runs |
| **Carry out** — write the code *and its tests* | **the main session** | **No**, and see below |
| **Verify at code level** — the anchor | a command, no model | **No.** Mechanical |
| **Review at semantic level** — what the anchor cannot see | not whoever wrote it | Yes: two independent axes |
| **Fan out** — anything with independent subjects | one worker per subject | Yes, with a hard precondition |

## Who writes the code: a recommendation, and the scale that flips it

**This is the owner's call.** Who does the work is a material trade-off, and an earlier
version of this page wrote it down as a rule - which was the Skill taking a decision it has
no standing to take. What follows is the recommendation and the evidence for it, on both
sides.

**For a small slice: the main session.** Anthropic runs both patterns deliberately, split by
task type:

> Claude Code uses this orchestrator-subagent pattern. **The main agent writes code, edits
> files, and runs commands itself**, dispatching subagents in the background when it needs
> to search a large codebase or investigate independent questions. This contrasts with the
> research system, where the lead agent delegates rather than directly handling code
> execution.

So research is delegated and code is not, on purpose. The reason matters more than the
authority: **`### Lessons` and every dead end live in the main context.** A fresh coder
subagent cannot see that turn 3 already tried this path and why it failed, which is the
only thing that makes turn 7 better than turn 1. Delegating the writing restarts the run
at turn 1, every turn.

**The conflict-of-interest objection is real and is answered elsewhere.** A main session
that both writes and judges would be referee and player. It does not judge: the **anchor's
exit code decides**, and no model is in that path. The reviewer never receives the author's
argument, and the critic audits the review rather than the code. The referee was moved out
of the writer's hands, which is what the zero-trust layer is for - not the writing.

**At scale it flips, and there is a working counterexample.** A long build in production on
this machine runs the opposite way, and runs well: the lead holds the loop, owns one ledger
exclusively, **writes no code**, and two cross-vendor executors alternate between build
rounds and review rounds - each taking a whole slice, so it is a role rotation rather than
the phase split this design refuses. Where a build is large enough that one context cannot
hold it, the argument above inverts: the lead's context is better spent on judging than on
editing.

What the main session must never author is its own acceptance. The anchor is the owner's,
set at question 2, and frozen.

## Judging blind

The referee-and-player objection has a sharper answer than "the anchor decides", and it came
from that same production run: **the judge records its verdict before reading the executors'
reports.** Run the anchor yourself, write the verdict to `<slug>.judge-review.md`, and only
then read what they said and note where the three readings differ.

This is context isolation applied to the judge rather than to the reviewer, and it closes a
hole the rest of this page leaves open. A judge that reads the reports first has been
persuaded before it decided - and no amount of "the exit code decides" helps, because
the exit code does not settle which findings mattered,
or whether a report was honest about what it did not check.

Cost: one extra file per round, and the discipline of doing the work before hearing about
it. Recommend it wherever the work is delegated.

**Test-first is not a choice either.** Whoever writes the code writes its tests, first.
Splitting the test from the code is a phase split, and phase splits are already refused:
each phase needs the previous phase's context.

## How to actually run a fresh-context role

Not an ad-hoc subagent call. The skills reference documents a frontmatter field for exactly
this:

```yaml
context: fork          # run in a forked subagent context
agent: Explore         # and which agent type executes it
```

With `context: fork` the task is written in the skill and an agent type executes it, and the
built-in `Explore` and `Plan` agents skip CLAUDE.md and git status, so **a forked skill sees
only its own SKILL.md content and the agent's system prompt**. That is context isolation as
a declared property of the file rather than something the caller has to remember to arrange -
which matters, because the caller here is the author whose argument must not reach the
reviewer.

Read the reference before choosing a mechanism. This one was reconstructed from installed
plugins for several versions while the field that does the job was documented all along.

## The two axes of semantic review

These are independent, and conflating them was the original error. They defend against
different diseases.

| Axis | The disease | The control | Cost |
|---|---|---|---|
| **Context isolation** | **Contagion of the author's argument.** Handed an explanation of why the work is right, a reviewer reviews the explanation | a fresh context - a subagent that never saw the reasoning cannot be persuaded by it | negligible |
| **Model independence** | **Shared blind spots.** Two agents on one model make the same mistake and agree about it | a different vendor | roughly an order of magnitude |

A fresh-context subagent on the same model is **not** a cheap substitute for a different
vendor. It cures the first disease completely and the second not at all: it catches "you
did not do what the spec says" and misses "the spec and the code are wrong in the same
way". Reach for a different vendor where a mistake is expensive **and** looks correct from
inside - a silent overwrite, a survivorship or look-ahead bias, an off-by-one in money.

Context isolation is **not optional**. Model independence is the choice.

## Parameters, not peer choices

Two things depend on the review and are not alternatives to it:

- **When it runs**: every turn · at proposed completion · at named acceptance lines.
  Default the middle one: intermediate turns already have the anchor, and review earns its
  cost at the moment the run wants to declare done.
- **Round cap**: a number, default 5, accepting round 1 if it converges with no findings.

## Fan-out, and its precondition

Legal when the subjects are genuinely independent and **each has its own anchor**. Twenty
factors, each with its own acceptance line and its own command. Research is the other case,
and the usual one.

This is where parallelism lives. It is not several reviewers on one artifact - that is the
shape measured as unreliable - it is several subjects, each with its own verdict.

## What is *not* on this page

**Loop versus graph is not a role question.** It asks when routing gets decided - at
authoring time or during inference - and it belongs to the shape question, not here. Putting
it in a list of role options was the clearest symptom of the original mistake.

## Declared degradation

An agent can become unavailable mid-run: a quota runs out, a target does not answer, a
process dies. The run should degrade, not break.

So every role in `## Roles` names a `fallback:`, and the rule is one line: **try the role,
then its fallback, then continue as the main session alone** - and record which happened.

| What | Who decides | Where it lives |
|---|---|---|
| who to fall back to | the **owner**, at design time | `## Roles` |
| whether a target answered | **observed at call time** | — |
| that a fallback was used | the run, in its report and in `### Lessons` | a **claim**, not evidence |

The last row is the honest one, and an earlier draft of this page got it wrong. It promised
that a degraded round would show up in the event log and be surfaced by `--audit`. It cannot:
**the only thing that can observe a failed delegation is the run that attempted it**, and the
run's statements are claims - `events.jsonl` is written by the hooks precisely so that it is
not. Writing the event from the run would have put a claim inside the evidence file and
broken the one distinction the whole design rests on.

So degradation is **declared and reported**, not measured. The order is a decision the owner
already made, and whether it was used is something the run has to say out loud. That is
weaker than a mechanical check, and saying which of the two you have is the point:
a `ROUND_DEGRADED` finding that no code could ever produce would have been worse than none,
because it reads as coverage.

Degrading to the main session alone is **always** the last resort and always allowed. A run
that stops because a reviewer was out of quota has turned an optional check into a single
point of failure - and a review that cannot happen is a missing review, not a red anchor.
Say so in the report; do not let it read as a pass.
