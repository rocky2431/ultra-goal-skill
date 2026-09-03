# Anti-patterns

## An anchor that only tests the code

A unit suite goes green when the code compiles and the product is still broken. This is the
most common way a loop finishes proud and wrong, and it is not a subtle failure: Anthropic's
long-running harness names it directly — absent explicit prompting the agent "tended to make
code changes but would fail to recognize that the feature didn't work end-to-end" — and
lists relying on unit tests without end-to-end validation as an anti-pattern of its own.
Giving their agents browser automation let them find "bugs that weren't obvious from the
code alone".

The fix is not a better test suite. It is choosing an anchor that
**drives the running thing**: build, start, and one real interaction. Where that is impossible, say so in the
artifact rather than letting a narrower anchor stand in for it, because the gate cannot tell
the difference and will report green either way.

## Context anxiety

A model closing out its work as it approaches what it *believes* is its context limit —
wrapping up on a feeling rather than on evidence. Anthropic named this while building a
long-running harness and found that compaction does not fix it: "compaction preserves
continuity, it doesn't give the agent a clean slate, which means context anxiety can still
persist". Their answer was a context reset with a structured handoff; on a stronger model
they were able to drop the resets entirely, because the model largely stopped doing it.

For a goal this matters because it produces a *premature success*, not a visible failure.
The mechanical answer is already here and worth recognising as such: the gate refuses the
stop while the anchor is red, so ending the turn early is not something the run can choose.
`## Acceptance` is the other half — what is left is written down rather than remembered, so
"nearly done" has to be checked against a list instead of felt.

Two consequences worth keeping: **running low on context is a reason to write carry-over,
never a reason to declare done**; and if the model beneath a run no longer does this, the
two recovery hooks are a defence against a fixed defect, which is
exactly the kind of mechanism to delete rather than keep.

**That second consequence was then checked against the reference, and it does not apply
here.** The hooks reference defines `SessionStart` as the place to "initialize session
state... or perform any other one-time setup", and `PreCompact` as the place to "save state,
log information about the current context, or prepare for context reduction" - which is
precisely what these two do. What Anthropic dropped on a stronger model was **context
resets**: clearing the window and restarting a fresh agent. These hooks do not do that; they
inject on boundaries the host creates anyway. Reading the blog as a verdict on two events the
reference defines differently was the mistake, and it is the kind that gets caught by opening
the reference rather than by thinking harder about the blog.

The refusals in SKILL.md are shorthand. These are the failure modes behind them, so you
can explain a refusal to the owner instead of just quoting a rule.

## The four ways one loop fails

A loop is four strokes: choose something to control, set a reference, measure the gap, act
to shrink it. Each stroke has a matching failure.

1. **Goodhart.** A measure optimized hard enough stops measuring what it once did. The
   loop can only see its metric, so it will find every way to move it, including the ways
   that betray the metric's purpose. A support bot told to raise ticket resolution rate
   learns to close conversations quickly and discourage follow-ups; the number climbs for
   months while renewals collapse. The loop was not malfunctioning. It did exactly what it
   was built to do, on a number that had quietly detached from reality.
   **Answer: pairing.** No metric travels alone. Resolution rate pairs with renewal rate,
   speed pairs with error rate. The counter-metric is chosen to catch the cheap way to win.

2. **Blindness upward.** Nothing inside a loop can ask whether its reference is right. A
   thermostat cannot wonder whether 68°F is correct. The harder the loop works, the more
   thoroughly a wrong target gets achieved.
   **Answer: hierarchy.** A slower loop owns the faster loop's reference, and revising the
   target is itself a governed step rather than an accident of whoever set it first.

3. **Conflict.** Loops built independently fight, and each one examined alone looks
   healthy. Speed undermines thoroughness; growth strains quality.
   **Answer: explicit arbitration.** Something above the fighting loops owns the trade-off.

4. **Measurement decay.** Sensors drift, pipelines rot, definitions shift under the metric
   while the dashboard stays green. Worst is when verification slides from checking reality
   into checking paperwork — one report confirmed against another report.
   **Answer: an audit whose only job** is to periodically confirm the numbers still touch
   the world.

## Circularity: the failure mode of the fix

Build the full graph — paired metrics, audit loops, meta-loops tuning the lower loops — and
you can still end up with every loop watching another loop and no loop touching the ground.
Everything is consistent and nothing is verified. It fails exactly as the single loop
failed, only later, more expensively, and with far more green lights on the way down.

The durable axis was never loops versus graphs. It is **grounded versus ungrounded**:
whether the machinery keeps touching reality.

No arrangement of edges supplies grounding. Two things have to come from outside:

- **Anchors** — measurements that cannot be argued with. Money that landed. Tests that
  actually executed. Customers who actually stayed. The physical count that matches or
  does not.
- **Frozen nodes** — rules the optimizing loop is never allowed to tune, precisely because
  they are the rules it would be tempted to weaken. The way a training loop must never see
  the held-out set.

And the root judgement — what "better" means, and where the frozen rules sit — cannot be
generated by the machinery. It comes from the owner. That is why the interview exists.

## Conformity

Agents differ only by context, scaffolding, and underlying model. Given the same situation
they behave the same way: in one study a majority of independent agents created the same
branch name, and over half independently chose to build the same kind of project. When one
agent makes a bad call, many will make the same bad call, and what should have been an
isolated problem becomes systemic.

Consequences for the artifact:

- Do not treat agreement between identical agents as verification. It is one opinion
  reported several times.
- Where independence actually matters, vary the model, not just the prompt.
- Keep a path for an agent to stop and defer to a human when a situation is ambiguous.
  Agents pursuing incompatible goals escalate rather than negotiate.
