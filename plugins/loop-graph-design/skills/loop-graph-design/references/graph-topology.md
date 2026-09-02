# Graph topology

A loop is a directed cyclic graph, so the shape is not the question. The question is
**when the routing decision gets made**.

| | Who decides the next step | Cache behaviour | Fails when |
|---|---|---|---|
| Loop | The model, every iteration, from a rebuilt context | Prefix moves unless you pin it, so it misses | Routing tokens compound; reasoning is lost between turns |
| Graph | You, once, at authoring time | Each node's prompt is fixed, so it caches for free | The work needed a step or a branch you did not draw |

Loops are adaptive and expensive. Graphs are cheap and rigid. Neither is a virtue by
itself, and the graph's cache advantage is real but secondary — it saves routing tokens
*and* makes the remaining tokens cheaper, because the structure now lives in code instead
of being re-established in the prompt every pass.

## Earn the graph first

Multiple agents cost **3-10x** the tokens of a single agent for the same work, and a full
orchestrator-worker research topology has measured around **15x**. Token volume alone
explains most of the performance difference between runs, so the budget is the design.

Only three conditions justify the spend:

1. **Context isolation** — one task's retrieved material degrades a different task. Each
   worker gets a clean window focused on its own slice.
2. **Parallelization** — independent paths explored at once cover more ground than one
   agent can hold. Note that total wall-clock can still rise, because total computation does.
3. **Specialization** — a focused toolset (past roughly 15-20 tools reliability drops), a
   system prompt whose stance conflicts with another's, or domain context that would
   swamp a generalist.

If none of the three applies, better prompting on one agent usually matches an elaborate
topology. That outcome is common enough to expect it.

## Split on context, never on phase

Work may be split **only where context can be truly isolated**. Splitting by workflow
phase — planning, then implementation, then testing, as separate agents — fails because
each phase needs the previous phase's context, and every handoff loses some of it. The
symptom is workers spending more tokens coordinating than working.

The one topology that reliably pays: a **verification worker** that checks the main
agent's output against clear criteria as a blackbox, with no implementation context. Its
failure mode is declaring early victory after a superficial look, so state explicitly what
it must run before it may pass anything.

Read is parallelizable; write is usually not. Anthropic's research system fans out the
reading and then deliberately writes the synthesis in a single call with one agent.

## Same-vendor graph: a Workflow script

- `meta` is the first statement and a pure literal — no variables, calls, or interpolation.
- `pipeline()` streams each dimension into its own verification as soon as that dimension
  finishes, so nothing waits on the slowest sibling.
- `parallel()` fans out independent work; `phase()` labels progress for the owner.
- Pass a `schema` on any node whose result another node consumes.
- The runtime evaluates the script inside an async function, which is why top-level
  `await` and `return` are legal there.

## Cross-vendor graph: a star, not a mesh

Cross-vendor delegation is a blocking request/response. There is no shared state, no
checkpoint, and no worker-to-worker channel — so every edge runs through the orchestrator,
and the honest name for the shape is orchestrator-worker.

That constrains the design in three ways worth stating in the artifact:

- Each worker runs **its own loop internally**; the orchestrator sees the result, not the
  middle. Either re-delegate repeatedly and pay routing each time, or delegate once and
  give up visibility. There is no third option without a state file on disk.
- Handoffs must be **self-contained**: a worker does not know the others exist and cannot
  coordinate mid-task. Vague missions produce duplicated work.
- Different vendors are the one real defence against conformity. Agents differ only by
  context, scaffolding, and underlying model — so identical agents make identical mistakes
  and turn what should be isolated errors into systemic ones. Heterogeneous models are
  therefore worth the most where independence matters: verification and cross-review.

Confirm the registered targets before naming any of them in the artifact rather than
assuming a vendor is installed.
