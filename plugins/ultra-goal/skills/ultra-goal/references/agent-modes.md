# Agent modes

Which agents do the work, which review it, and where each one runs. This is a decision the
owner makes; discovering what is available is not.

## Discover before asking

Run this yourself, before the question is put to anyone:

```bash
agent-delegate list --json
```

It reports each target's name, its argv, and the version actually observed. That is a fact,
and facts are yours - asking the owner which agents they have installed spends their turn on
something a command answers. If the tool is absent, say so: the modes below that need it are
unavailable, not merely unchosen.

Vendor matters for exactly one reason. **Agents differ by their context, their scaffolding,
and the model underneath.** Two agents on the same model make the same mistakes, so a critic
sharing the reviewer's model mostly agrees. Note the vendor per target when you present the
list, because that is the axis the choice turns on.

## The four modes

Four, not seven. The refusals in SKILL.md rule out most fan-out shapes, so padding this list
would contradict *Nodes added for sophistication* - the entry that exists to stop exactly
that.

### A — Internal triad (default)

```
M = the agent running the goal
R = a subagent, fresh context, same model
C = a second subagent, fresh context, same model
```

- **Cost**: an order of magnitude less than crossing vendors.
- **Buys**: the third role. In the source study that is the part that worked - a reviewer
  nobody audits converges on agreement rather than correctness.
- **Does not buy**: independence from the model's blind spots. R and C share M's model, so
  what M cannot see, they mostly cannot see either.
- **Enough when**: the anchor catches the failures that matter, and review is there to stop
  premature victory rather than to catch a class of error the anchor is blind to.

### B — Cross-vendor triad

```
M = the agent running the goal
R = a different vendor, delegated
C = a third vendor, delegated
```

- **Cost**: high. Two out-of-process calls per inner round, capped at five rounds.
- **Buys**: real independence. Different models have different blind spots.
- **Does not buy**: shared context. R and C cannot see what M tried and abandoned, so the
  mission file has to carry whatever they need - and deliberately not M's argument for why
  the work is right.
- **Reach for it when**: the review's independence is itself the thing at stake. Concretely:
  where a mistake is expensive and the kind that looks correct from inside - a silent
  overwrite, a survivorship or look-ahead bias, an off-by-one in money.

### C — Parallel triads

One triad per artifact, several artifacts at once.

- **Legal only when** the subjects are genuinely independent and **each has its own
  anchor**. Twenty factors, each with its own acceptance line and its own command.
- This is where parallelism went. It is not several reviewers on one artifact - that is the
  shape measured as unreliable - it is several artifacts, each with its own third role.

### D — Graph

Routing decided at authoring time, edges written as code.

- **Legal only when** the whole route can be drawn before running any of it.
- Needs a workflow runtime. Of the hosts measured, only Claude Code has one, so elsewhere do
  not emit a workflow script - it would be a file nothing can run.

## The mode can differ by turn, and usually should

Nothing requires one mode for the whole run. The useful shape is often A for the turns whose
failures the anchor catches, and B for the two or three turns where it does not. Say which
turns, in `## Verification`, in words.

## When does the review run

A separate question from who reviews, and it was missing from the interview until a real run
invented an answer for it. Three shapes:

| Cadence | Cost | Catches |
|---|---|---|
| **Every turn** | highest | drift early, before it compounds |
| **At proposed completion only** | lowest | premature victory, which is the failure review exists for |
| **At named acceptance lines** | in between | the specific lines where the anchor is known to be blind |

The middle one is the usual answer, and the reasoning is worth keeping: on intermediate turns
the anchor is already the check. Review earns its cost at the moment the run wants to declare
done - and at the specific lines where a green anchor would not prove the claim.

## What to record

One row in `decisions.md`, naming the mode, the targets, the review cadence, and the round
cap. The mode is a Firm-tier choice: changeable mid-run, but the row is what tells a later
reader whether a review was independent or a second opinion from the same model.
