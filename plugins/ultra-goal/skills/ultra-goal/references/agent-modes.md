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

The three role skills also carry `user-invocable: false`, which the skills reference
defines as "Claude Code hides it from the `/` menu and doesn't run it when you type
`/name`". That is not tidiness. A role invoked by hand forks with no frozen diff to audit
and no round to attach its file to, so the one aperture a user should see is the goal
skill itself - everything else is the graph calling its own nodes. Plugin skills are
namespaced (`/ultra-goal:review`, `/ultra-goal:critic`); bare names require standalone
user or project entries. The optional `UG` shortcut points only to the main skill.

Read the reference before choosing a mechanism. This one was reconstructed from installed
plugins for several versions while the field that does the job was documented all along.

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
process dies. The run should degrade, not break.

So every role in `## Roles` names a `fallback:`, and the rule is one line: **try the role,
then its fallback, then continue as the main session alone** - and record which happened.

| What | Who decides | Where it lives |
|---|---|---|
| who to fall back to | the **owner**, at design time | `## Roles` |
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

Degrading to the main session alone is **always** the last resort and always allowed. A run
that stops because a reviewer was out of quota has turned an optional check into a single
point of failure - and a review that cannot happen is a missing review, not a red anchor.
Say so in the report; do not let it read as a pass.
