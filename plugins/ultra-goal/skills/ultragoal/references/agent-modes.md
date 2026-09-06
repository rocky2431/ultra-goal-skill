# Roles and modes

Who does what, in which stage, and which of those is actually a choice. An earlier version
of this file offered four "modes" side by side - same-model subagents, cross-vendor,
parallel triads, and a graph. That was a menu, not a taxonomy: three orthogonal axes
flattened into one column. The owner caught it. This is the repair.

## Assign the work that this goal needs

Resolve the collaboration scope below before assigning any worker.

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

## Confirm collaboration scope

After understanding intent and basic boundaries, inspect native worker tools and
registered external targets read-only. Do not launch a worker as an availability
probe before authorization. Resolve this owner decision before the first dispatch,
including research, specification critique and review:

> May this goal use only this host's native workers, or may it also delegate to the listed external agents?

- **Current-host only:** use this host's native subagents or independent sessions.
- **External delegation allowed:** also permit the concrete agent targets the owner
  accepts; their presence in an inventory does not grant permission to use them.

Recommend the current-host path when it can satisfy the goal. Name the external
targets being proposed and disclose untested capabilities. Reuse an explicit,
applicable owner answer; otherwise ask once and wait for the answer. An unresolved
choice leaves dispatch and unattended startup pending while authorized local
preparation can continue.

Keep the original answer and its source in the existing decisions record. Put the
allowed collaboration scope in `## Boundary`, the independent verifier and accepted
fallbacks in `## Verification`, and assignments in `## Roles`. A template's example
scope is not an owner answer. Both choices preserve the same final-review rule:
the main agent may implement and self-test, but a non-implementing verifier in its
own session must supply the required independent review. A lone execution session
cannot satisfy that role.

Within the confirmed scope, choose task splits, workers and accepted fallbacks
without repeating the question. Expanding the scope or changing required review
needs an owner decision; during a run, use the existing frozen-contract challenge
procedure instead of editing `Boundary` or `Verification` yourself.

## Choose an available delegation path

Inspect the current host's worker tools and any installed bridge. Use a capability
within the confirmed collaboration scope that fits the assignment; there is no
mandatory vendor or transport order.

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
available. On top-level calls, pass `--caller <actual-host-label>` when it is known;
otherwise the wrapper records `unknown`. Nested calls preserve the received caller and
chain. Never substitute `human` or a renamed target to bypass a rejection. A same-product
worker can be a separate session; if the chosen bridge cannot create it, use another
supported path rather than claiming a circular delegation.

The bridge version checked for this text, `agent-delegate` 0.4.0, exposes **task
handles and non-owning observation** (`submit` returns an ID; `status` and `wait` read
it), **named native sessions** (`--session <name>` on `submit` or `run`, continued by
repeating the same target, directory and name), **task or session cancellation and
session close**, and a private per-run receipt directory holding events and diagnostics
during execution. Those are wrapper facts at that version: a wrapper that lacks a knob
says nothing about what the underlying protocol could do, and a newer wrapper may expose
more. Check the installed version rather than assuming either direction, and keep any
platform-specific limit you state tied to the version you actually observed.

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

### Before dispatching long-running work

Use the existing mission or delegation attachment. Before dispatch, record the
criteria, candidate failure cases and the commands or observations that would
settle them. Separate an attack on the worker's result from a missing requirement
in your own assignment; the latter is an assignment correction, not a worker failure.
Retain this original version before the worker begins. When Git commits are
authorized, commit it and give the worker that revision and the starting product
revision; keep necessary evidence outside disposable scratch or retain it first.

Check four concrete facts in the worker's actual directory:

- Inputs, tools and expected output locations are reachable with its capabilities.
- Required prior work is integrated: `git merge-base --is-ancestor <required-commit> HEAD`
  checks a Git prerequisite; a promised merge is not an integrated dependency.
- Ignored or external resources are actually accessible there. Inspect the named
  paths in that worktree; its creation does not copy ignored files. Reuse authorized
  links or mounts for needed resources, without changing the goal's write boundary.
- The declared writable files/resources do not collide with another active writer.
  Resolve overlap through an explicit integration order or available isolation.

Keep the observed checks with the mission, then submit using an available task
handle for work that must outlive its observer. Read results through that handle;
an observer timeout does not authorize another worker on the same unfinished work.
Include the work-step record convention in implementation missions and collect the
worker's actual native session identity. Check committed work against the registered
failure cases while it is in flight, without editing the worker's active checkout.
A tentative finding remains tentative until the joined result is reviewed.

Run the accepted anchor and inspect what it covers. Choose test order for the change:
a reproduced bug benefits from a regression check; a prose change needs structural
validation. There is no mandatory test-first rule or fixed implementation agent.

Independent review is required when the owner or accepted goal requires it, and useful
when a costly mistake can survive the anchor. One independent reviewer can be sufficient.
A reviewer plus critic is an optional adversarial protocol for unresolved disagreement or
false consensus. Its delegation template checks that protocol's fields; ordinary goal
verification does not have to use it.

For the long-running coding protocol, the main agent may implement and delegate;
final independent acceptance belongs to a reviewer who did not implement the result.
Declare that required review when authoring the goal. The main agent can integrate
findings and run its own checks, but those are not an additional independent verdict.
Keep every actual product writer out of the review assignment, including delegated
writers and prior bound sessions. Recorded `Writer-Session` commit fields are also
checked by the gate; absent records cannot establish that a worker was independent.
The bound main session remains ineligible even if it only coordinates. Running
review checks alone does not make a reviewer a product writer.

**A required review is a role with a contract, not just an assignment.** Where an acceptance
ID is mapped to `review`, `## Verification` names which identities may sign it, which inputs
it reads and where its receipt lands, and the gate checks that receipt at completion. That
makes two things role decisions rather than prose: the verifier must be an identity the
owner approved (or an approved fallback), and it must run somewhere with its own session -
a fork that cannot obtain a session distinct from the run's cannot satisfy the condition,
however good its review is. Route that one to a separate session or another vendor, and say
so rather than signing from inside the run. Any additional advisory review is free to vary.

## Judging blind

For the long-running protocol, retain the independent initial verdict before reading
the worker's explanation. Give the reviewer the criteria, original evidence and fixed
product inputs. It first writes its checks and verdict; only then may it receive the
execution report and record worker-only findings, reviewer-only findings and actual
disagreements. Keep the initial review intact and put reconciliation after it or in
the existing review discussion. Do not replace the initial account with a later one.

With Git, retain the preregistration revision before the first worker commit and the
initial review revision before the reconciliation commit. Check those relationships
with `git merge-base --is-ancestor <earlier> <later>`; timestamps alone are insufficient.
For a lighter task, this order remains an evidence-based option. It is not proof that
the verdict is correct, and Git does not prove which messages reached a model's context.
Use an actual isolated input path; reconcile disagreements against evidence.

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
neither eliminates shared errors. The brand correlation runs in both directions: a
different vendor is not proof of independence, and the same vendor is not proof of
dependence — one vendor can run two genuinely separate sessions over isolated inputs,
and two vendors can share a model or the author's framing. A required review's contract
checks that the declared verifier name is owner-approved, the verifier session differs
from the run's, and the receipt matches the bounded current inputs. Select reviewers by
risk, availability and cost.

For a repeated exchange, choose a round cap and stop early when the issue is settled.
The optional triad template uses at most five rounds. That cap does not apply to a
single check or force a critic into every review.

## Fan-out, and its precondition

Delegate in parallel when scopes are independent and each worker has a clear result to
return. Join the required workers and inspect their evidence before synthesis. Several
reviewers may examine separate concerns on one artifact; the main model must reconcile
their findings rather than count agreement as proof.

## What is *not* on this page

**Loop versus graph is not a role question.** A graph expresses tasks, dependencies and
joins; a loop expresses the feedback pass that corrects the next action from the latest
result - and either shape can fix its routing at authoring time or decide it during
inference. That is the shape question, and it belongs to `graph-topology.md`, not here.
Putting it in a list of role options was the clearest symptom of the original mistake.

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
