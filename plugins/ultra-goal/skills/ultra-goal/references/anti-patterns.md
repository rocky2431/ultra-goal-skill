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

**And then this Skill recommended a reset anyway.** v2.5.0 told the owner to clear the
context before turn 1 so the run would start clean - a context reset, the exact mechanism
the paragraph above records as dropped on a stronger model, proposed by the file that
records it. The owner caught it in one question: *the context is never going to be clean
going into the loop anyway, is it?* It was removed in v2.6.0, and the four reasons
generalise past this instance:

- **A clean context is not reachable.** A fresh session already carries the host's setup,
  the project's instructions and every installed hook's injection before the owner types
  anything. "Cleaner" was the honest word; "clean" was the one that made it sound worth an
  action.
- **What the reset discarded was the most valuable context that will ever exist.** At the
  handoff the window holds why each term was chosen, what the design critic objected to and
  what the owner rejected. The artifact keeps at most three lessons. Trading the first for
  the second is a downgrade dressed as hygiene.
- **The worry it answered already had three answers**, one of them mechanical: the
  injection's own first line, `frozen_digest()` written and compared by machine, and the
  challenge row for a term that really is wrong. A fourth defence that costs the owner an
  action is not a defence, it is a tax.
- **The only real gain was token headroom**, which is a 200k-window instinct. It did not
  survive being asked how many tokens an interview actually is.

So ask of any proposed reset: what is in this window that is **wrong**, not what is in it
that is **large**. Only the first is a reason to drop it.

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

## A record with no consumer is not a fix

A comparison against a long-running autonomous project (its TRAJECTORY file, 6,663 lines
at the revision measured) surfaced the same lesson **six times** in that log — and the
process that log was supposed to feed (the per-round judge, which read a different file)
had hit on it **zero** times. The record existed, was appended to diligently, and changed
nothing, because nothing read it.

That single criterion retires more proposed mechanisms than it admits:

- A trajectory file nobody reads back is a diary, and a diary does not deflect the next
  failure.
- A ruling id is correlation, not authorization — any process that can write the file can
  write the id next to it.
- A retraction ledger is only worth what its reader does with it; a section in a review
  document serves the same turn.
- A checker for promises made in a log inherits every gap in the log, and adds its own.

The detector is not useless — the count of "six times" only became sayable because the
instrument existed — but detecting is not repairing. The repair is **promotion**: move
the rule into a document the recovery flow actually reads, and if no such reader exists,
building the record before the reader is building the diary. When you are tempted to add
a mechanism here, name its consumer first; "a record with no consumer is not a fix" is
the whole test.

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
