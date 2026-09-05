# Roles and modes

Who does what, in which stage, and which of those is actually a choice. An earlier version
of this file offered four "modes" side by side - same-model subagents, cross-vendor,
parallel triads, and a graph. That was a menu, not a taxonomy: three orthogonal axes
flattened into one column. The owner caught it. This is the repair.

## Assign the work that this goal needs

Init and research establish acceptance and authority. The main model then chooses the
next useful action, the worker if any, and the evidence needed before the next iteration.
These activities can overlap; they are not mandatory workflow phases.

Follow owner-assigned roles. Within delegated authority, resolve routine routing yourself:
use the current session for a small change; delegate a self-contained implementation or an
independent research question when that helps. Give each worker current state, prior failed
attempts, its writable scope and its expected result. Delegation need not lose the main
session's context when the handoff includes it.

A plan file or task list is allowed. Keep mutable execution planning separate from frozen
intent and acceptance. Use an existing graph runtime only when one is actually available
and the task calls for it; this skill does not introduce one.

## Choose an available delegation path

Inspect the current host's worker tools and any installed bridge. Use the capability
that fits the assignment; there is no mandatory vendor or transport order.

- Suitable native workers do not require `agent-delegation` or `agent-delegate`.
- If a bridge command and the needed target work but its Skill is not discovered,
  follow the bridge's available usage instructions. Do not reinstall its runtime merely
  to make a Skill appear in a menu.
- A Skill file alone does not establish that its command, target or authentication works.
  If the chosen bridge is absent, choose another available path that meets the same terms.
  Install a dependency only when it is needed and existing owner authority covers installation.
- If a required independent verifier has no usable path, resolve that requirement before
  unattended execution. During a run, continue independent authorized work, but retain the
  missing verification condition; the generator cannot replace that verifier.

For `agent-delegate`, inspect `agent-delegate list --json` only when the command is
available. First calls need `--caller <actual-registered-caller>`; nested calls preserve
the received caller and chain. Never substitute `human` or a renamed target to bypass
a rejection. A same-product worker can be a separate session; if the chosen bridge
cannot create it, use another supported path rather than claiming a circular delegation.

Give the worker a self-contained mission: accepted terms, existing authority, relevant
source evidence and failed attempts, actual read/write scope, result location and checks.
Include any required review receipt fields and the resolved checker path it needs.
The worker need not install this Skill to perform that mission. Its own further delegation
depends on capabilities available to it, not on whether it received the same Skill package.

Choose a path with observable progress or an input channel when the task needs one.
Use native task handles, actual logs and agreed artifact locations. A synchronous bridge
may return only at exit; do not promise live feedback or resume support it does not expose.
If the worker needs input, answer from existing terms or ask the owner for the unresolved
material decision, then use a supported reply/resume path. Inspect unfinished effects
before retrying. Stop hooks do not relay questions or keep a worker alive.

## Verification and review

Run the accepted anchor and inspect what it covers. Choose test order for the change:
a reproduced bug benefits from a regression check; a prose change needs structural
validation. There is no mandatory test-first rule or fixed implementation agent.

Independent review is required when the owner or accepted goal requires it, and useful
when a costly mistake can survive the anchor. One independent reviewer can be sufficient.
A reviewer plus critic is an optional adversarial protocol for unresolved disagreement or
false consensus. Its delegation template checks that protocol's fields; ordinary goal
verification does not have to use it.

**A required review is a role with a contract, not just an assignment.** Where an acceptance
ID is mapped to `review`, `## Verification` names which identities may sign it, which inputs
it reads and where its receipt lands, and the gate checks that receipt at completion. That
makes two things role decisions rather than prose: the verifier must be an identity the
owner approved (or an approved fallback), and it must run somewhere with its own session -
a fork that cannot obtain a session distinct from the run's cannot satisfy the condition,
however good its review is. Route that one to a separate session or another vendor, and say
so rather than signing from inside the run. Any additional advisory review is free to vary.

## Judging blind

For sensitive delegated work, consider recording a verdict from the artifact and anchor
before reading the worker's explanation. This can reduce persuasion by the report; it
is not proof that the verdict is correct. Reconcile disagreements against evidence.

## How to actually run a fresh-context role

Use the current host's supported mechanism to supply the intended reviewer inputs and
obtain its own session identity. Claude Code supports forked Skill execution through
frontmatter such as:

```yaml
context: fork          # run in a forked subagent context
agent: general-purpose # the packaged review roles also need to write their reports
```

This declares the execution request for a host that supports those fields. It does not
prove what every host injects into the worker, or that the worker can expose a distinct
native session ID. Check the actual session and accepted input isolation. Do not infer
that the worker sees only its Skill file and system prompt from these fields alone.

Where the packaged role call is supported, use it with the goal slug and required inputs.
Otherwise pass the relevant role instructions and actual artifact paths through a native
worker or an available bridge. Reviewers must have the capabilities their accepted checks
need; do not translate read-only review into an unrelated Shell or network ban.

The role skills carry `user-invocable: false`; menu visibility and invocation behavior are
host-specific. Plugin role names such as `/ultra-goal:review` and `/ultra-goal:critic`
are not portable tool APIs. Invoke the main Skill through the host's plugin surface.

## Review choices

Decide whether review is required or useful, what each reviewer receives, and what would
resolve a finding. Fresh context and a different model can reduce correlated judgment;
neither eliminates shared errors. Select them by risk, availability and cost.

For a repeated exchange, choose a round cap and stop early when the issue is settled.
The optional triad template uses at most five rounds. That cap does not apply to a
single check or force a critic into every review.

## Fan-out, and its precondition

Delegate in parallel when scopes are independent and each worker has a clear result to
return. Join the required workers and inspect their evidence before synthesis. Several
reviewers may examine separate concerns on one artifact; the main model must reconcile
their findings rather than count agreement as proof.

## What is *not* on this page

**Loop versus graph is not a role question.** It asks when routing gets decided - at
authoring time or during inference - and it belongs to the shape question, not here. Putting
it in a list of role options was the clearest symptom of the original mistake.

## Declared degradation

An agent can become unavailable mid-run: a quota runs out, a target does not answer, a
process dies. Preserve the required outcome while choosing another workable method.

Each declared role names a `fallback:`; `none` is a valid answer. For ordinary work or
advisory review, choose a suitable worker or continue in the main session within authority.
For required review, use only a verifier or fallback accepted by `## Verification`, in
a distinct session with the required inputs and evidence. If none is available, keep
that requirement unmet. Continuing other work does not permit a completion claim.

| What | Who decides | Where it lives |
|---|---|---|
| ordinary worker or advisory-review fallback | the **main agent**, within existing authority and owner-assigned roles | `## Roles` and material decisions |
| required verifier or its fallback | the **accepted verification contract** | `## Verification` |
| whether a target answered | **observed at call time** | — |
| that a fallback was used | the run, in its report and in `### Lessons` | a **claim**, not evidence |

The last row is the honest one, and this page has now been wrong about it in both
directions. An earlier draft promised that a degraded round would show up in the event log
and be surfaced by `--audit` while only the run could write it - a claim inside the
evidence file, exactly what `events.jsonl` being hook-written exists to prevent - so the
finding was deleted, and the page then overcorrected: it declared the finding one nothing
could ever produce. The hooks reference settles the split: `PostToolUseFailure` fires
after a failed tool call, which is a host-observed fact, not the run's account of itself.

So the fallback order is **declared; the failure is measured** on the hosts that register
the event (Claude Code, zCode, Kimi: the hook writes `role_unavailable`, and `--audit`
surfaces `ROUND_DEGRADED`). Codex documents no such event, so there the run's report is
the only record - a declared loss, not parity. And whether the fallback was *adequate* is
a judgement on every host: the run says it out loud, and the answer is the claim in the
last row. Saying which half you hold is the point - a `ROUND_DEGRADED` finding nothing
could produce would be worse than none, because it reads as coverage, and so would a
"measured" verdict about adequacy nothing can measure.

**Recovery is measured on the same hosts, and it measures less than its name suggests.**
`PostToolUse` is registered there and writes `role_recovered` when a later call naming the
same target succeeds - a positive observation rather than the turn-boundary inference it
replaced. But a tool call returning success is a
fact about the *call*. It is not proof that the worker finished, and not proof that it wrote
anything: a call that *succeeds* while writing no file still reads as clean from inside the
plugin, and a review round on this project produced exactly that.

**Neither the failure nor its recovery gates completion.** Both are observations kept for
the audit. An earlier design held a completion claim open until the failed target was
positively observed working again, which made an unreachable vendor into a stop condition
the owner never wrote - a run with a perfectly good fallback result could not finish.
Completion is settled by the current required outputs and the current review evidence, so
an authorized fallback can satisfy it while the original target stays down. The failure
still belongs in the report and in `### Lessons`; what changed is that it is a fact about
transport, not a missing acceptance condition.


Detection is deliberately narrow: a recognized direct `agent-delegate run --to <target>`
command (or a structured call to that exact tool). Search strings, tool output, opaque
scripts and compound shell commands are not delegation evidence. Unsupported shapes
remain unobserved and the main model must inspect their actual results. A success for
the same target/tool clears an observed call failure; it does not prove every mission
for that target completed.

**So joining is the run's job, not the hook's.** Wait for every role invoked, then open the
artifact it was told to write and read it —
the round's evidence is the file the role was told to write.
The run does not count a round until it exists, and `--audit` reports a
declared reviewer with no review file as `REVIEW_UNEVIDENCED`. For rounds delegated to a target that writes somewhere else,
even that cannot see the artifact; the report is the only record there, which is exactly the
Codex row above.

An unavailable advisory reviewer need not stop the work. An unavailable required reviewer
leaves verification incomplete unless an accepted independent fallback supplies it.
A review that cannot happen is a missing review, not a red anchor. Say so in the report;
do not let it read as a pass or ask the owner to solve ordinary routing choices.
