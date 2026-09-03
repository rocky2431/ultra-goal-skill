# The document system

Four files and Git. Each answers exactly one question, and the split follows the one
SKILL.state draws: an immutable procedural specification, a mutable execution state, and the
observations that arrive between them.

| File | Role | Who writes it | When | Mutability | In Git |
|---|---|---|---|---|---|
| `<slug>.goal.md` — spec sections | the specification | owner + agent, together | Ask and explicit Modify **only** | **frozen for the duration of a run** | yes |
| `<slug>.goal.md` — `## Carry-over` | the execution state | the running agent | before finishing **every** turn | rewritten, never appended | yes |
| `<slug>.events.jsonl` | the observations | the hooks (and workers) | every turn | **append-only, never edited** | yes |
| `<slug>.decisions.md` | the decision tree | owner + agent | Ask and Modify | rows edited, never appended | yes |
| `.loops/.work/*` | worker intermediates | each delegated worker | while a round runs | disposable | **no** |
| `.loops/active` | which loop is running | owner or agent | on start and stop | one line | no |
| git history | the evolution | git | one commit per turn | immutable | — |

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
                     .loops/.work/  ─────►  git commit (one per turn)
                     [disposable, gitignored]
```

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
.loops/
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

Delete `.loops/active`. Keep `<slug>.goal.md`, `<slug>.decisions.md`, and
`<slug>.events.jsonl` in Git — together they are a complete record: what was attempted, why
it was designed that way, what was rejected along the road, and every anchor result. Delete
`.loops/.work/` without ceremony.

If the loop is never coming back, the durable parts belong in the repository's real
documentation, and the three files go. An empty `.loops/` means nothing is outstanding.
