# The document system

Four files and Git. Each answers exactly one question, and the split follows the one
SKILL.state draws: an immutable procedural specification, a mutable execution state, and the
observations that arrive between them.

| File | Role | Who writes it | When | Mutability | In Git |
|---|---|---|---|---|---|
| `<slug>.goal.md` — spec sections | the specification | owner + agent, together | Ask and explicit Modify **only** | **frozen for the duration of a run** | yes |
| `<slug>.goal.md` — `## Carry-over` | the execution state | the running agent | before finishing **every** turn | rewritten, never appended | yes |
| `<slug>.events.jsonl` | the observations | **the hooks, never the run** | at every Stop, prompt, delegation event and compaction | **append-only, never edited** | yes |
| `<slug>.decisions.md` | the decision tree | owner + agent | Ask and Modify | rows edited, never appended | yes |
| `.goals/.work/*` | worker intermediates | each delegated worker | while a round runs | disposable | **no** |
| `.goals/active` | which goal is running, and for which session | owner or agent to arm; the first session-carrying Stop adds the `session <id>` line | on start and stop | slug, plus the session line once claimed | no |
| `<slug>.spec.baseline` | the authorized digest of the frozen sections | **the arming fence, before any Stop ran** | once, at arming | **write-once** | yes |
| `<slug>.candidate` | the run's completion claim, one line | the run, once per claim | at each claim | consumed by the gate when it rules | no |
| git history | the evolution | git | one commit per turn | immutable | — |

The two "no" rows are arranged, not just asserted: arming writes `.goals/.gitignore`
holding `.work/` and `active`. For three versions this table called them gitignored while
nothing wrote the rule, so a run that staged with `git add -A` committed the reviewer's
intermediates — a documented property that only the document believed.

```
decisions.md ──defines──► goal.md spec sections   [FROZEN during a run]
                                   │
                            read every turn
                                   ▼
                        goal.md ## Carry-over      [rewritten every turn]
                              ▲          │
                   written    │          │   read
                  every turn  │          ▼
                          events.jsonl                [append-only facts]
                              ▲          │
              worker results  │          │  summary + digest
                              │          ▼
                     .goals/.work/  ─────►  git commit (one per turn)
                     [disposable, gitignored]
```

## The one distinction that decides who writes what

Read the "who writes it" column again. Every row is on one side or the other of a single
line, and the line is what makes the trace worth keeping:

| Authored by | Files | What it is |
|---|---|---|
| the run | the spec sections, `## Carry-over`, the commit subject, a review | **claims** |
| the hooks | `<slug>.events.jsonl` | **measurements** |
| the owner (with the agent) | `<slug>.decisions.md` | authorizations |

`validate_artifact.py .goals --audit` is the join: each completion attempt's committed
verdict beside the verdict the gate measured for it. Rows that agree are unremarkable. The
first row where they part company is the answer to "where did this go wrong", which is the
only question a finished run is ever asked.

Nothing here auto-resolves a divergence. The log cannot know why a turn claimed green; it
knows only what it measured.

## What a hook inlines, and what it points at

Both hooks write into the model's context, and they had the same bug for different reasons:
they quoted files the model can open. The rule that settles it:

> **A hook inlines only what it alone possesses. Everything already on disk gets a path.**

| | Stop, at a completion claim | SessionStart, once per boundary |
|---|---|---|
| **Possesses alone** | the anchor verdict it just measured; the refusal's reason | the fact that a run exists at all |
| **Inlines** | verdict and obligation inside the deny's reason; the owner-facing one-liner | the frozen terms: intent, boundary, anchor, carry-over |
| **Points at** | the bodies of `### State`, `### Lessons`, `### Next`, `## Acceptance` | everything else, named when dropped |
| **Size** | bounded, **independent of the artifact** | bounded by `CONTEXT_LIMIT`, frozen terms exempt |

The asymmetry is not inconsistency. At a session boundary the run **does not know a goal
exists**, so it has no reason to open any file - the injection's job is to establish that
there is a run and what it may not do. A prohibition delivered by pointer is a prohibition
the run can decline to read, which is why `## Boundary` is inlined and `## Roles` is not.
Mid-run the model has already been told all of that, so the only thing it cannot get for
itself is what the anchor just did.

Two numbers from the first real artifact, which is where both rules came from: the Stop
payload was **4,683 characters per turn** against a 40-turn ceiling, and `## Anchor` alone
was **7,752 characters** - 97% of the injection budget, so every restart lost the anchor.
Neither was visible against the shipped template, whose sections are a quarter the size.

## `## Acceptance` is not a task ledger, and here is the line

This is the boundary most likely to be misread later, so it is drawn explicitly rather
than left to taste. An earlier version of this Skill refused a task ledger outright. That
refusal was half right, and the half that was wrong was conflating two different objects.

| | A plan / task ledger | An acceptance list |
|---|---|---|
| Shape | ordered, with dependencies | **unordered**; every line stands alone |
| Answers | *what to do next* | *what is still not true* |
| Decided | at authoring time | the run picks, every turn |
| Makes it | a graph — routing already decided | still a loop — routing decided at inference |
| Mechanically | a numbered list | `- [ ]` / `- [x]` lines, and `ACCEPTANCE_ORDERED` refuses a numbered one |

A plan says "first the API, then the web package, then release". An acceptance list says
"these four things are not true yet" and lets the run decide which to attempt with what it
knows this turn. The first takes the routing decision away from the run, which is the
definition of a graph. The second is **the stop condition written out longhand**.

So the rule stays one-directional and unchanged: **`plan.md` and a dependency-ordered
`tasks.json` are still refused.** What was added is the enumerated form of a section that
already existed.

Why bother, when `## Stop condition` was already there: one sentence plus one anchor can
answer *is the whole thing done*, and cannot answer *which parts are*. The second question
is the one a long run gets wrong, by declaring victory on the strength of the part it
finished. Anthropic's long-running harness reached for the same object for the same reason
— a feature list, every entry failing at the start, one entry per session, and a state that
may only move to passing after real testing.

And `[x]` is a claim. It is written by the run, so it sits on the claims side of the line
above, and the anchor's output is what settles it. `--audit` is where the two meet.

## What the gate says, and to whom

Two channels, and confusing them wastes the deny - the one contact with the model that
still ends nothing.

| Channel | Read by | Carries |
|---|---|---|
| the deny, in the asking host's own shape | the model, when a claimed completion may not stand | why it may not stand, and the one thing to do first |
| `systemMessage` | the owner | one line of what happened |

There is no per-turn injection channel, and that is a measured fact, not a preference: on
Claude Code 2.1.260 an allow carrying `additionalContext` continues the turn instead of
ending it. What the run owes (carry-over rewritten, lessons written, work committed) rides
the skill's standing instructions and the deny's reason - the reminder inside the reason
names `### Next`, `### Lessons`, `### State` and the still-open `## Acceptance` lines,
never a frozen section: what the gate reminds the run of is exactly what it may change.

A deny also cannot be one payload for all hosts, and both halves are measured: the mixed
payload (top-level `decision: "block"` plus nested `permissionDecision`) was inert on
Codex 0.150.1, while deleting the nested form globally left Kimi 0.40.1 - whose parser
reads `hookSpecificOutput.permissionDecision` only - with no blocking path at all. One
Stop output cannot be shared across vendors, so the gate reconstructs exactly one
allowlisted shape per asking host, and every test pins the shape per host rather than
what one script emits. A payload contract is a claim until something outside the emitter
agrees with it.

## Why the spec is frozen while a run is in flight

A loop that can edit its own intent, anchor, or boundary will edit them — and the edit will
always be in the direction that makes the current turn easier. That is not misbehaviour; it
is what optimizing against a reference does when it also owns the reference. The answer is
topological rather than motivational: **a slower loop owns the faster loop's target**, and
here the slower loop is you.

So divergence splits by layer:

| The plan was wrong about | Write it in | May the loop continue? |
|---|---|---|
| an approach — this path is dead, this dependency has a trap | `### Lessons` | yes, adjust and carry on |
| the extent — bigger than expected, three modules left | `### State` | yes, adjust and carry on |
| **the target** — the anchor is not measuring what we actually want | **nothing; stop and report** | **no** — this reopens Ask, and the answer lands in `decisions.md` |

The third row is the one worth enforcing socially even though no mechanism can catch it. An
anchor that turns out to measure the wrong thing is the most valuable finding a loop can
produce, and also the one it is most tempted to quietly route around.

## Why history is not in any of these files

Version control already holds it, at full fidelity and for free:

- `git log -p <slug>.goal.md` — every change with its before and after. That *is* the
  evolution.
- `git log --oneline <slug>.goal.md` — one line per turn. That is the trajectory.
- `<slug>.events.jsonl` — the machine-checkable facts of each turn, which is a different
  thing from a narrative and much cheaper to query.

So the documents answer only "what is true now". A changelog section inside the artifact
would be a second copy of what Git holds, growing without bound, read by nobody.

One consequence worth stating: **a summary is a derived checkpoint, not a source of truth.**
Where a summary is unavoidable, it carries the id or digest of what it summarizes, so a later
reader can tell whether it has gone stale. That is why the event log stores digests rather
than prose.

## Where multi-worker rounds put things

Delegating to several agents does not add a document type; it adds one directory that Git
never sees.

```
.goals/
  active                        # the running slug
  audit.goal.md                 # spec + carry-over, owned by the orchestrator
  audit.decisions.md
  audit.events.jsonl            # the coordinator's event log
  .work/                        # gitignored, one round's lifetime
    codex.mission.md
    codex.result.md
    kimi.mission.md
    kimi.result.md
```

Three rules make this work, and they come from the same place — separating a worker's private
context from typed artifacts from an immutable coordinator log:

1. **Workers never share a transcript.** Each gets a self-contained mission and writes a
   typed result. Passing conversation history between agents costs a large multiple in tokens
   and buys duplicated work, because a worker that can see another's reasoning starts
   agreeing with it.
2. **The orchestrator runs the anchor, not the workers.** A worker's report of success is a
   claim; the anchor's exit code is evidence. This is the same rule as the single-agent case,
   and it is the reason worker intermediates can be thrown away.
3. **What survives the round is the event log line and the lesson** — not the discussion. The
   discussion's durable content is exactly what got written into `### Lessons`; if nothing
   did, the round produced no knowledge and the transcript would not have saved it.

## What is left behind when a loop is done

Delete `.goals/active`. Keep `<slug>.goal.md`, `<slug>.decisions.md`, and
`<slug>.events.jsonl` in Git — together they are a complete record: what was attempted, why
it was designed that way, what was rejected along the road, and every anchor result. Delete
`.goals/.work/` without ceremony.

If the loop is never coming back, the durable parts belong in the repository's real
documentation, and the three files go. An empty `.goals/` means nothing is outstanding.


## If you also run a spec-driven development harness

A full harness — an init/research/plan/dev pipeline with a task ledger — and this Skill solve
adjacent problems, and it is worth being explicit about which owns what, because running both
without deciding produces two half-authorities.

| Harness artifact | Here | Why |
|---|---|---|
| `north-star.md` | `## Intent` | One artifact is one loop, so its intent *is* its North Star |
| `specs/product.md`, `specs/architecture.md` | `## Boundary` + `## Anchor` | Condensed to what a loop needs: what it may touch, and what proves it worked |
| a change's `intent.md` | `<slug>.goal.md` | The same document under a different name |
| `decisions/` | `<slug>.decisions.md` | Same role |
| `evidence/`, `verification.md` | `<slug>.events.jsonl` | Stronger here: execution receipts rather than a written account of them |
| `contexts/TEMPLATE.md` | `### State` + `### Lessons` | Condensed to what the next turn must read |
| `changes/{active,archive,abandoned}` | `.goals/active` + Git | Three states are a workflow; one marker plus history is enough for one loop |
| **`tasks.json`** | **deliberately absent** | See below |
| **`plan.md`** | **deliberately absent** | A loop's plan is its goal text; a written plan for it would be the routing decision made twice |

### Why there is no task ledger

A task ledger is a decomposition made at authoring time, which makes it a graph. A loop is
defined by deciding the next step at inference time. Give a loop a task ledger and it becomes
a graph — and a worse one than a harness built for graphs, because it inherits neither the
dependency ordering nor the traceability that make a ledger worth having.

One part of a ledger's job is genuinely needed: **what is left**. That already lives in
`### State` as a line or two. What stays out is dependency order, acceptance-criteria
tracing, and integration checkpoints — those belong to the harness, and a loop that wants
them is telling you it should have been a planned change instead.

The two compose in one direction: a planned task in a harness can *be* a loop, with this
Skill's artifact as how that task gets executed. The reverse — a loop that grows a plan —
is the thing to refuse.
