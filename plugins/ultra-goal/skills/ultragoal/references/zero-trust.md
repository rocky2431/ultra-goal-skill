# Zero trust

The run is given wide latitude on purpose. This is the list of what is therefore not taken
on trust, what each control actually distrusts, and — the part that matters most — what is
deliberately left unmechanized.

## The criterion

**Mechanize a check only when the quantity measured is the quantity judged.**

| Check | Measures | Judges | Same? |
|---|---|---|---|
| anchor exit code | the exit code | did this command report success on this state | **yes** |
| candidate count against the ceiling | consumed candidates in the event log | how many completion attempts have run | **yes** |
| frozen-spec digest | a sha256 of the frozen sections, the acceptance text and the labelled means bullets | did those bytes move | **yes** |
| evaluator baseline | hashes of the declared `protected` files | did the checker change since arming | **yes** |
| review receipt fields | the declared identity, a distinct session, the current input digest, the covered IDs, the verdict | does the receipt declare an approved verifier and current inputs | **yes** |
| `covers` completeness | the map against the acceptance IDs | is every requirement assigned to some evidence | **yes** |
| claim versus event log | two recorded strings | do they agree | **yes** |
| a timeout | elapsed seconds | did it succeed or fail | **no** |
| **the `covers` mapping's adequacy** | that an ID was assigned | is the anchor or the review the right judge of it | **no** |
| **a review receipt's substance** | that a verdict was recorded | was the review any good | **no** |
| a similarity score | token overlap | is this the same finding | **no** |
| a line-count ceiling | lines | is this document too long | **no** |

The two new "no" rows are the ones most likely to be misread as coverage. `covers` proves
every acceptance ID was assigned to *something*; whether the anchor can actually settle the
line it was assigned is a semantic judgement, which is why the owner confirms the mapping
and an independent reader is asked to attack it before the freeze. A receipt records a
current verdict declaring an approved identity and another session. The fields do not
authenticate that origin or score the review behind it.

The rows that answer "no" are observations, and an observation reported as a verdict is how
a gate starts lying. A timeout is the clearest case: it has no access to whether the work
succeeded, so it must report **unknown** — which is why the gate has three outcomes and not
two, and why folding unknown into either verdict was the single most expensive mistake
available here.

## What each control distrusts

| Distrusts | Control | Strength |
|---|---|---|
| the generator's opinion of its own output | the anchor runs for real at every completion claim | **hard** — a red anchor denies a claimed completion |
| **the generator reviewing itself** | a required review's receipt must name an approved verifier in a session that is not the run's owner | **hard over fields only** — missing, stale or same-session declarations deny; writer authentication is outside this plugin |
| **the checker being edited into agreement** | the declared `protected` evaluator files are hashed at arming and compared before *and* after the anchor runs | **hard** — detection, not isolation |
| the reviewer's verdict | a critic that audits the review, not the code | optional protocol; an advisory review's verdict informs, it does not gate |
| agreement between reviewer and critic | three disagreement classes, evidence required | soft |
| a shared model's blind spots | reviewer and critic on different vendors | soft |
| **the author's framing reaching the reviewer** | `inputs:` per role — the reviewer gets the artifact, the criteria and the anchor's output, not the argument for them | soft |
| **the run's account of its own attempt** | the commit's claim compared against the event log by `--audit` | observed, reported, never auto-resolved |
| **the run's account of its own target** | the frozen-spec digest, recorded by the arming fence before any Stop ran | observed; ends the turn with an alarm |
| **"a turn ended, so the worker must have joined"** | recovery is a positive observation (`role_recovered` from the success side), never a boundary inference | observed — **about the call only**, and it gates nothing |
| **"the call succeeded, so the worker finished"** | nothing mechanical; the run must join every role it invoked and read the artifact that role was told to write | **not mechanized** — see below |
| an owner-set threshold quietly moving | frozen: the threshold lives in the stop condition and the acceptance text, both inside the spec digest | **hard** — a moved one closes the run |
| a method or worker quietly changing | a row in `decisions.md` | social — asked for, not enforced |

**A delegation failure is not in this table on purpose.** It is an observation the hooks
record and `--audit` surfaces; it does not deny a completion claim, and waiting for one
particular target to recover was never the same question as whether the required evidence
exists. What settles the claim is the current anchor and the current receipt, which an
authorized fallback may have produced.

**And "hard" here means hard against a mistake, not against an adversary.** Hashes and
receipts live in the same writable filesystem as the run: a process that can rewrite any
file can rewrite a baseline or forge a receipt. This is detection and audit. Real isolation
comes from native permissions, a separate verifier workspace, or an authenticated external
receipt — and where the task needs that and it cannot be arranged, the honest move is to say
so before offering unattended work, not to describe these checks as if they were it.

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

Part of this is now checkable in every shape: a required review declares its bounded
`inputs`, the verifier digests exactly those, and the gate refuses a receipt computed over
anything else. What that checks is *which files* were reviewed, not what else reached the
reviewer's context — so keeping the author's argument out of it remains a stated rule and a
property of how the role is invoked, not something a hash can confirm.

## What the trace can and cannot prove

`<slug>.events.jsonl` is written by the hooks and never by the run. That asymmetry is the
only reason it is worth anything.

It **can** show: which turns the gate actually saw, what each anchor really exited with, a
digest of the output so the same failure twice is detectable, whether the frozen spec moved,
and when a compaction emptied the context.

It **cannot** prove itself. An agent can write any file it can read. What defends the log is
not permission but visibility: when committing is authorized, preserving it alongside the
artifact makes a later edit visible as a diff. Without that history, audit coverage is lower. **Visible, not impossible** — claiming more than that would be the same kind of
overreach as a timeout reporting failure.

## Deliberately not mechanized

- **Whether an asynchronous worker actually finished.** `role_recovered` observes that a
  call naming that target succeeded. It does not observe a join, and a call can succeed
  while writing nothing. The run waits for each role it invoked and reads the artifact the
  role was told to write; the file's presence and contents are the round's evidence, and
  `--audit` names a declared reviewer with no review file. There is no hook that can close
  this, which is why it is stated here rather than implied to be covered.
- **Whether a lesson is a real lesson.** A cause plus a next action is asked for in words.
  A regex could count bullets, which is not the same thing.
- **Whether a dropped means should have been dropped.** The label says the owner authorized
  the *class* of decision; the argument in `decisions.md` is for a human to read.
- **Whether the review found the real problem.** Nothing here scores a review. The receipt
  binds a verdict to an identity, a session and a set of inputs; the critic makes
  disagreement auditable. Neither makes the finding correct.
- **Whether the acceptance program is the right one.** `covers` checks that every
  requirement was assigned to some evidence. Whether that evidence can settle that
  requirement is the counterexample question asked before the freeze, and the reason an
  unresolved criterion goes to an independent reader instead of a stricter check.
- **The Firm tier.** Which worker ran a role, which method was tried, whether a droppable
  means should have been dropped: asked for as a row, not gated — and named as such in
  SKILL.md rather than quietly hoped for. Thresholds and verification obligations are *not*
  in this tier; they are frozen, and moving one closes the run.
- **Divergence between claim and measurement.** `--audit` reports it and stops. Auto-
  reverting a commit or rewriting an artifact on a digest mismatch would put a mechanical
  check in charge of semantic content, which is the one thing it must never own.
