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


## The Stop hook is not the sequencer

The question that produced this section: *if a graph has eighty tasks in a JSON file, what
does the Stop hook compose out of them?*

**Nothing.** It is the wrong layer, and answering it any other way is how a loop's gate
turns into a graph's engine.

A graph decides its routing at author time, so its position lives in the runtime that walks
it - `workflow.js` on a host that has one, or the delegation triad's own per-worker calls.
Those know which node is next because the author wrote the edges. A Stop hook knows one
thing: whether the anchor exited 0 just now. Handing it a task list would make it read a
position it did not write and choose a next node the author never routed to - inference-time
routing over an author-time graph, which is the confusion this Skill exists to prevent.

Two consequences worth keeping:

- **The per-turn payload must not grow with the work.** Whatever the artifact holds, the
  Stop hook's `additionalContext` names the mutable sections and counts the open acceptance
  lines: about 660 characters, the same for eight lines or eighty. See "What a hook inlines,
  and what it points at" in `document-system.md`.
- **A goal that has grown eighty ordered tasks was authored wrong.** `### Next` takes
  exactly one objective, and `## Acceptance` is unordered on purpose. A list of ordered
  steps is a plan, and a plan belongs in a graph - where a runtime, not a gate, holds the
  position.

The gate's power comes from being small enough to be certain. An exit code is something it
can know; which of eighty tasks should be next is not.
