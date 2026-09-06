# Graph topology

A loop is a directed cyclic graph, so the shape is not the question — and neither is
**when the routing decision gets made**. That was this page's earlier answer, and it
flattened two independent axes into one. A graph expresses tasks, dependencies and
joins; a loop expresses the feedback pass that corrects the next action from the
latest result. Either shape can be static or dynamic: a graph can be regenerated or
extended between runs, and a loop can execute a fixed route deterministically. "Graph"
is not a synonym for a rigid author-time route, and "loop" is not a synonym for free
inference-time exploration.

| | What it expresses | When its routing is decided | Fails when |
|---|---|---|---|
| Loop | the correction process: observe, compare, act, repeat | fixed by a script, or chosen by the model from a rebuilt context each pass | the feedback signal does not measure the actual goal |
| Graph | tasks, dependencies and joins | drawn at authoring time, or regenerated at runtime as results arrive | the work needed a step or a branch nobody drew |

Routing time is a design choice inside either shape, not the boundary between them.
Author-time edges are inspectable before the run; inference-time choices adapt to what
the last step found. What a shape costs in tokens or cache on a given host is a
measurement, not a property of the shape: one community essay argues author-time
routing reuses a prompt prefix better, but this project has measured no such universal
advantage, and this page claims none.

## Earn the extra agents

The spend under discussion is additional agents, whatever shape connects them — a
graph's nodes and a loop's delegated passes both multiply it. Anthropic measured about
**3-10x** the tokens of a single agent for the same task, and their orchestrator-worker
research topology about **15x ordinary chat** (the agents alone were about 4x chat in
the same discussion). Those numbers are their workload and their models; treat them as
a budget warning from a measured case, not a universal multiplier.

Only three conditions justify the spend:

1. **Context isolation** — one task's retrieved material degrades a different task. Each
   worker gets a clean window focused on its own slice.
2. **Parallelization** — independent paths explored at once cover more ground than one
   agent can hold. Note that total wall-clock can still rise, because total computation does.
3. **Specialization** — a focused toolset, a system prompt whose stance conflicts with
   another's, or domain context that would swamp a generalist.

If none of the three applies, better prompting on one agent usually matches an elaborate
topology. That outcome is common enough to expect it.

## Split where the handoff works

Prefer independent scopes with clear expected results. A phase handoff can also work when
it includes the preceding decisions, evidence and constraints. Keep a small slice in one
session when coordinating it costs more than doing it. These are planning choices, not
hard gates imposed by this skill.

For parallel work, make writable ownership explicit and join the results before synthesis.
For review, require inspection of the actual artifact and relevant checks.

## Same-vendor graph: a Workflow script

A script is an **attachment**, not a replacement contract, and not a runtime. The sample
in `assets/` targets one specific host feature — a workflow engine that provides
`agent()`, `pipeline()`, `parallel()` and the `meta` block. This Skill ships the sample
and the checks; it does not implement, bundle or emulate that engine, and the file is
not a portable Goal runner. The script carries the same slug as the `.goal.md` it
serves and names it on its own line:

```js
// goal: `nightly-audit.goal.md`
```

Acceptance, stop condition, verification and boundary are read from that file. A script that
restates them differently has created a second contract, and the weaker one is the one that
gets satisfied.

**Prove the consumer before you write the file.** What the Skill's own validator does to
a script is structural: `validate_artifact.py` checks the `meta` literal, the declared
phases and the `// anchor:` comment, then asks `node --check` to parse the source wrapped
in an async function. None of that executes anything, and none of it proves `agent()` or
`pipeline()` exists in this session. Being on a host that ships a workflow feature is not
proof either — exercise the entry point, or emit the goal alone. An unrunnable script is
worse than none, because it reads as a delivered mechanism.

Nor is the script's own return value Goal completion. The sample ends in
`return { confirmed }`; that object is the runtime's answer to the script, and a
`confirmed` flag inside it is one node chain's claim about itself. Completion is settled
only by the shared contract the script serves: the frozen specification and protected
evaluator baselines, the required independent review where one is declared, and the
current anchor run — the same gate every other shape submits its completion candidates
to.

- `meta` is the first statement and a pure literal — no variables, calls, or interpolation.
- `pipeline()` streams each dimension into its own verification as soon as that dimension
  finishes, so nothing waits on the slowest sibling.
- `parallel()` fans out independent work; `phase()` labels progress for the owner.
- Pass a `schema` on any node whose result another node consumes.
- The runtime evaluates the script inside an async function, which is why top-level
  `await` and `return` are legal there.

## Cross-vendor graph: a star, not a mesh

Cross-vendor delegation is a request/response through the orchestrator. The bridge
version checked for this text, `agent-delegate` 0.4.0, supports task IDs with
asynchronous `submit`/`status`/`wait`, **named native sessions** (`--session <name>`,
continued by repeating the same target, directory and name), **task or session
cancellation and session close**, and a private per-run receipt directory where events
and diagnostics land during execution. So a worker can be re-entered and its task
observed without a second registration. This interface still provides no worker-to-worker
channel or shared cross-vendor state: every edge runs through the orchestrator, and the
honest name for the shape is orchestrator-worker. Exit 0 from `submit`, `status` or an
expired `wait` can mean only that submission or observation succeeded; even terminal
`success` says the ACP turn ended normally, never that the mission's product is done.
The result is a claim until its artifact and checks are inspected.

That constrains the design in three ways worth stating in the artifact:

- Each worker runs **its own loop internally**. A named session lets the orchestrator
  continue the same worker context instead of re-delegating cold, and the receipt's
  events show what the turn did — but neither makes the worker's middle the
  orchestrator's own state. Past that there is no third option without a state file on
  disk.
- Handoffs must be **self-contained**: a worker does not know the others exist and cannot
  coordinate mid-task. Vague missions produce duplicated work.
- Different vendors buy different blind spots, not independence. Agents differ by context,
  scaffolding and underlying model, so identical agents make identical mistakes and turn
  what should be isolated errors into systemic ones. But the correlation runs in both
  directions: two brands handed the same account of why the work is correct will both
  review the account, and one vendor can run two genuinely separate sessions over isolated
  inputs. Heterogeneous models are worth the most where independence matters — verification
  and cross-review — while a brand name, same or different, proves nothing by itself.
  A required review instead checks that its declared verifier is owner-approved, its
  session is distinct from the run's, and its receipt matches the bounded current inputs.

Confirm the registered targets before naming any of them in the artifact rather than
assuming a vendor is installed — `agent-delegate list --json` answers that on a machine
that has the bridge. A delegation package is an attachment too: it names its
contract with `` goal: `<slug>.goal.md` `` and adds who runs what, never its own acceptance.


## The Stop hook is not the sequencer

The question that produced this section: *if a graph has eighty tasks in a JSON file, what
does the Stop hook compose out of them?*

**Nothing.** It is the wrong layer, and answering it any other way is how a loop's gate
turns into a graph's engine.

A graph's position lives in whatever walks it - the runtime evaluating a `workflow.js` on
a host that has one, or the delegation triad's own per-worker calls. Those know which node
is next because they hold the route, however it was produced: authored once, or regenerated
between nodes. A Stop hook holds no route. What it can know at one moment is the goal's
verification state: whether the frozen specification still matches its armed digest,
whether the protected evaluator inputs still match their baseline, whether a required
independent review has passed on the current input digest, and the outcome of the one
anchor command it just ran against that state. That is a gate on a completion claim, not
a position in a plan. Handing it a task list would make it read a position it did not
write and choose a next node nobody routed to - a gate masquerading as an engine, which
is the confusion this Skill exists to prevent.

Two consequences worth keeping:

- **The gate's payload must not grow with the work.** Whatever the artifact holds, the
  deny's reason names the mutable sections and counts the open acceptance lines, and the
  allow carries one owner-facing line: the same size for eight acceptance lines or eighty.
  See "What a hook inlines, and what it points at" in `document-system.md`.
- **The main model owns the plan.** A goal may use a task list, with `### Next` pointing
  to its immediate action. The list is neither the anchor nor input for a hook scheduler.


The gate's power comes from being small enough to be certain. A current anchor outcome
against unmoved baselines, with whatever required review the contract declares, is
something it can check; which of eighty tasks should be next is not.
