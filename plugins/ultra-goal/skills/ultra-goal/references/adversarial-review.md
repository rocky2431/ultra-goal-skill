# Adversarial review

The verification protocol this Skill asks for, and why it has three roles rather than five
reviewers.

## The shape

```
M (main)      the only role that edits the artifact
R (reviewer)  reviews the artifact, and produces a review
C (critic)    reviews R's review - not the code
```

```
M ──produces──►  artifact + change log
                      │   [FROZEN for the whole inner loop]
                      ▼
                 R writes a review
                      │
                      ▼
                 C audits that review
                      │
             disagreement? ──yes──►  back to R, who answers with evidence ──┐
                      │                                                     │
                      no                                          (≤5 rounds)│
                      ▼ ◄────────────────────────────────────────────────────┘
              a consistent review
                      │
                      ▼
                 M edits → next outer round
```

Two rules make this different from "get a second opinion":

- **The artifact is frozen during the inner loop.** The review is a procedure over a fixed
  artifact, not an editing procedure over it. Without this, the agents jointly rewrite the
  solution while they are still disagreeing about what is wrong.
- **Only the main agent edits, and only after the review stabilises.** The reviewer and the
  critic never touch the artifact.

## Why three roles beat five reviewers

Adversarial Review (arXiv 2608.18167) builds the protocol one step at a time — zero-shot,
self-refine, single reviewer, two reviewers, a five-agent panel, then AR — adding each step
to fix a measured failure of the previous one. Two findings matter here:

- **AR outperformed the five-agent panel using three agents.** The panel was one author,
  three reviewers and one meta-reviewer.
- **Adding independent reviewers alone did not reliably improve results.** More eyes on the
  code is not the mechanism. Someone auditing the eyes is.

So the count is not the point. The third role is.

## The failure it exists to prevent: false consensus

Left naive, the protocol reproduced a specific failure — agents converging on agreement
without sufficient evidence. Two agents that both say "looks fine" have produced one opinion
reported twice, and a loop cannot tell that from verification.

The fix is textual and it is the whole trick. **The critic must sort every point into exactly
one of three classes:**

| Class | Means | Obligation |
|---|---|---|
| **agreement** | the reviewer is right | none |
| **evidence-backed disagreement** | the reviewer is wrong, and here is what shows it | cite the evidence |
| **concern-based disagreement** | something is unresolved, no evidence either way | say what evidence would settle it |

And then: **the reviewer answers a disagreement with evidence, not with a plausible
rebuttal.** That is what turns a disagreement into an auditable object rather than a
negotiation.

The lesson the paper draws is worth keeping verbatim in mind: multi-agent oversight should
not be judged by whether the agents converge, but by whether the path to convergence
preserved dissent, evidence and accountability.

## Termination

- **First pass**: if R and C converge immediately with no findings, accept and stop. This is
  what keeps the protocol cheap on work that was already correct.
- **Cap**: at most 5 inner rounds, then take the review as it stands. An unbounded review
  loop is the review-side version of a loop with no ceiling.

## What each role is given

Choosing different vendors buys **different blind spots**. It does not buy independence, and
conflating the two is the easiest way to think this protocol is stronger than it is. Hand two
different models the same account of why a change is correct and both will tend to review the
account rather than the change.

So the isolation that matters is over inputs:

| Role | Receives | Does not receive |
|---|---|---|
| R | the frozen artifact, the acceptance criteria, the anchor's raw output | M's explanation, M's confidence, M's summary of what it tried |
| C | R's review and the same frozen artifact | M's opinion of the review, R's account of its own confidence |

State this per role in the delegation package as an `inputs:` field, where it is mechanically
checkable. In a single-agent goal package `## Verification` is prose and the rule is stated
rather than checked - pattern-matching prose for the right words would be keyword-guessing
wearing the costume of a check.

## Choosing R and C

Where the roles are separate agents, **give them different underlying models.** Agents differ
only by their context, their scaffolding, and the model beneath them — which is why identical
agents make identical mistakes, and why a critic sharing the reviewer's model will mostly
agree with it. Different vendors buy real independence rather than a differently worded
prompt.

A workable assignment on a machine with several CLIs:

| Role | Runs as |
|---|---|
| M | the orchestrator — the agent running this Skill |
| R | a different vendor, delegated |
| C | a third vendor, delegated |

Within a single agent, R and C are two subagents with fresh contexts. That costs an order of
magnitude less and still keeps the third role, which is the part that works. Reach for
separate vendors when the review's independence is the thing at stake.

## When a worker cannot proceed

A text protocol still needs the two states that a blocked worker and a finished one differ
by. Google's A2A task lifecycle names them, and they transfer even though its transport
does not:

| Outcome | Means | The orchestrator's obligation |
|---|---|---|
| **completed** | the mission was carried out | run the anchor yourself; the report is a claim |
| **failed** | attempted, did not work | read what was tried before re-dispatching |
| **input-required** | cannot proceed without something specific | supply that thing, or drop the mission. **Not a failure, and never scored as one** |
| **rejected** | the mission is outside what this worker should do | take the objection seriously; a worker that declines loudly beats one that improvises |

**Silence is `input-required`, never `completed`.** This is the whole reason to name the
states: without them, a worker that returned nothing and a worker that found nothing look
identical, and the orchestrator reads the second one as agreement — which is the false
consensus this protocol exists to break, arriving through a different door.

## Cost

Each inner round is two calls, one for R and one for C, capped at five rounds. First-pass
termination means work that was already correct costs two calls, not ten. Compare that to
fanning out to N reviewers: N calls, and N reviews nobody audited.

## What this replaces

An earlier version of this Skill split delegation by **domain** — one worker for overflow,
another for reentrancy — and had the orchestrator merge their reports. That is the
two-reviewers step the source study measured and found unreliable, for the reason above: no
one audits either report, and the orchestrator has no independent evidence with which to
arbitrate between them.

Domains do not disappear. They become the reviewer's checklist. Parallelism does not
disappear either — it moves from "several reviewers on one artifact" to "several artifacts,
each with its own triad".
