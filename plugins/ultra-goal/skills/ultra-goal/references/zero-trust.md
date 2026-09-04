# Zero trust

The run is given wide latitude on purpose. This is the list of what is therefore not taken
on trust, what each control actually distrusts, and — the part that matters most — what is
deliberately left unmechanized.

## The criterion

**Mechanize a check only when the quantity measured is the quantity judged.**

| Check | Measures | Judges | Same? |
|---|---|---|---|
| anchor exit code | the exit code | did the work land | **yes** |
| candidate count against the ceiling | consumed candidates in the event log | how many completion attempts have run | **yes** |
| frozen-spec digest | a sha256 of three sections | did the goal move | **yes** |
| claim versus event log | two recorded strings | do they agree | **yes** |
| a timeout | elapsed seconds | did it succeed or fail | **no** |
| a similarity score | token overlap | is this the same finding | **no** |
| a line-count ceiling | lines | is this document too long | **no** |

The rows that answer "no" are observations, and an observation reported as a verdict is how
a gate starts lying. A timeout is the clearest case: it has no access to whether the work
succeeded, so it must report **unknown** — which is why the gate has three outcomes and not
two, and why folding unknown into either verdict was the single most expensive mistake
available here.

## What each control distrusts

| Distrusts | Control | Strength |
|---|---|---|
| the generator's opinion of its own output | the anchor runs for real at every completion claim | **hard** — the only thing that may deny a claimed completion |
| the reviewer's verdict | a critic that audits the review, not the code | soft: must happen, verdict advisory |
| agreement between reviewer and critic | three disagreement classes, evidence required | soft |
| a shared model's blind spots | reviewer and critic on different vendors | soft |
| **the author's framing reaching the reviewer** | `inputs:` per role — the reviewer gets the artifact, the criteria and the anchor's output, not the argument for them | soft |
| **the run's account of its own attempt** | the commit's claim compared against the event log by `--audit` | observed, reported, never auto-resolved |
| **the run's account of its own target** | the frozen-spec digest, recorded by the arming fence before any Stop ran | observed; ends the turn with an alarm |
| **"a turn ended, so the worker must have joined"** | recovery is a positive observation (`role_recovered` from the success side), never a boundary inference | hard |
| an owner-set threshold quietly moving | a row in `decisions.md` | social — asked for, not enforced |

## Why input isolation is a separate control from vendor choice

Different vendors buy **different blind spots**. They do not buy independence: hand two
different models the same framing of why a change is correct and both will tend to review
the framing. Anthropic's own write-up of multi-agent failure modes names conformity and low
variance between agents as a primary problem, not a secondary one.

So the isolation is about **inputs**, not identity:

- The reviewer receives the frozen artifact, the acceptance criteria, and the anchor's raw
  output. It does not receive the main agent's explanation, its confidence, or its summary
  of what it tried.
- The critic receives the review and the same frozen artifact. It does not receive the main
  agent's opinion of the review.

Only the delegation package can check this mechanically — the `inputs` field is either there
or it is not. In a single-agent goal package `## Verification` is prose, and pattern-matching
prose for the right words would be keyword-guessing dressed as a check. It stays a stated
rule there.

## What the trace can and cannot prove

`<slug>.events.jsonl` is written by the hooks and never by the run. That asymmetry is the
only reason it is worth anything.

It **can** show: which turns the gate actually saw, what each anchor really exited with, a
digest of the output so the same failure twice is detectable, whether the frozen spec moved,
and when a compaction emptied the context.

It **cannot** prove itself. An agent can write any file it can read. What defends the log is
not permission but publication: it is committed alongside the artifact, so an edited log is
a diff. **Visible, not impossible** — claiming more than that would be the same kind of
overreach as a timeout reporting failure.

## Deliberately not mechanized

- **Whether a lesson is a real lesson.** A cause plus a next action is asked for in words.
  A regex could count bullets, which is not the same thing.
- **Whether a dropped means should have been dropped.** The label says the owner authorized
  the *class* of decision; the argument in `decisions.md` is for a human to read.
- **Whether the review found the real problem.** Nothing here scores a review. The critic
  makes disagreement auditable; it does not make it correct.
- **The Firm tier.** A threshold edit is indistinguishable from any other edit. Asked for,
  not gated — and named as such in SKILL.md rather than quietly hoped for.
- **Divergence between claim and measurement.** `--audit` reports it and stops. Auto-
  reverting a commit or rewriting an artifact on a digest mismatch would put a mechanical
  check in charge of semantic content, which is the one thing it must never own.
