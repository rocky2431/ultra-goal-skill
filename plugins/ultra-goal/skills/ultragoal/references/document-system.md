# The document system

Use the existing goal artifacts, observations and required evidence. The distinction
borrowed from SKILL.state is immutable specification versus mutable execution state;
the skill does not replace the host's context assembly or persistence.

| File | Role | Who writes it | When | Mutability | In Git |
|---|---|---|---|---|---|
| `<slug>.goal.md` — spec sections | the specification | owner + agent, together | Ask and explicit Modify **only** | **frozen for the duration of a run** | yes |
| `<slug>.workflow.js` / `<slug>.delegation.md` | an optional execution attachment, naming the contract above | owner + agent, at authoring time | Ask and explicit Modify | follows the contract; adds execution, never terms | yes |
| `<slug>.goal.md` — `## Carry-over` | the execution state | the running agent | before finishing **every** turn | rewritten, never appended | yes |
| `<slug>.events.jsonl` | the observations | **the gate and hook scripts, never model-authored rows** | at explicit verify attempts, Stop, prompt, delegation events and compaction | **append-only, never edited** | yes |
| `<slug>.decisions.md` | the decision tree | owner + agent | Ask and Modify | rows edited, never appended | yes |
| `.goals/.work/*` | worker intermediates | each delegated worker | while a round runs | disposable | **no** |
| `.goals/active` | which goal is running, and for which session | **the arming fence**, which writes the slug and the `session <id>` line together | on arming and disarming; ownership moves only by an explicit `rebind` | slug plus session, both written before any hook runs | no |
| `<slug>.spec.baseline` | the authorized digest of the frozen sections | **the arming fence, before any Stop ran** | once, at arming | **write-once** | yes |
| `<slug>.verification.baseline` | hashes of the declared `protected` evaluator files | **the arming fence** | once, at arming | **write-once**; a mismatch refuses instead of re-pinning | yes |
| `<slug>.review.json` by default | one independent verifier's declared verdict and input references | **the verifier, never the run** | when a required review completes | replaced by a fresh review after its inputs change | only with authority |
| `<slug>.reviews/<digest>.zip` | the exact reviewed evidence retained for later audit | **the gate, after the current checks** | during successful post-anchor review verification | content-addressed snapshot; historical, never a current receipt fallback | only with authority |
| `<slug>.candidate` | the run's completion claim, one line | the run, once per claim | at each claim | consumed by the gate when it rules | no |
| git history | the evolution | git | when an existing authorization permits a commit | immutable | — |

Git is the default for a goal run. Reuse an enclosing repository with a usable
`HEAD`; never initialize another repository inside it. With no repository or an
unborn one, propose `git init` plus a reviewed baseline commit before arming:
`git init` alone creates no revision. Show the exact status and inspect ignored or
suspicious paths before requesting authority to stage the baseline. Commit the
confirmed goal package with that baseline when authority permits.

"In Git" still describes intended tracked artifacts, not automatic permission to
commit or publish. If the workspace is not a project, the owner declines baseline
creation, Git is unavailable, or the baseline fails, arm with `--allow-no-git` and
disclose that step-history coverage and committed `Writer-Session` exclusion are
unavailable. Do not initialize a repository merely to version an unrelated home or
temporary directory. Arming writes
`.goals/.gitignore` for transient machinery such as `.work/` and `active`; required
evidence must survive cleanup in either mode.

```
decisions.md ──defines──► goal.md spec sections   [FROZEN during a run]
                                   │
                            read every turn
                                   ▼
                        goal.md ## Carry-over      [rewritten every turn]
                              ▲          │
                   written    │          │   read
                  every turn  │          ▼
                          events.jsonl                [append-only facts]
                              ▲          │
              worker results  │          │  source pointers + digests
                              │          ▼
                     .goals/.work/  ─────►  retained review + input archive
                     [scratch only]          [commit only if authorized]
```

## The one distinction that decides who writes what

Read the "who writes it" column again. Every row is on one side or the other of a single
line, and the line is what makes the trace worth keeping:

| Authored by | Files | What it is |
|---|---|---|
| the run | `## Carry-over`, the commit subject, its own report, any advisory review it wrote | **claims** |
| an independent verifier | the required review's receipt | a **checked declaration**: approved identity, distinct session, current input digest — provenance the gate verifies, not an authenticated credential |
| the hooks | `<slug>.events.jsonl` | **measurements** of the named operation, not semantic truth or authentication |
| the owner (with the agent) | `<slug>.decisions.md`, and the spec sections it defines | authorizations |

`validate_artifact.py .goals --audit` compares committed completion claims, when
they exist, with recorded gate observations. It also checks retained review archive
integrity. Missing history stays missing; agreement does not prove the original
criteria or review reasoning were adequate. Investigate a divergence from the
underlying inputs and events rather than automatically trusting either summary.

Nothing here auto-resolves a divergence. The log cannot know why a turn claimed green; it
knows only what it measured.

## Started verification and retained review evidence

The gate records `verification_started` with a `verification_id` and attempt number
before accepting the work of that attempt. Its settlement refers to the same ID.
A start without a settlement is pending/unknown, and a later owning gate can mark
it interrupted. An old green must not hide it. Recovery reads these facts; it does
not silently rerun the anchor or assume the interrupted operation had no effect.
This is local verification bookkeeping, not exactly-once business execution or a
guarantee that a host will resume.

Required reviews default to `.goals/<slug>.review.json`, outside disposable scratch.
At the post-anchor verification boundary, the gate retains
`.goals/<slug>.reviews/<digest>.zip`: the exact receipt, goal, all declared
`review.inputs`, and a SHA manifest. The event's `review_evidence.archive` holds
the archive path and SHA-256. Failure to retain required evidence refuses completion.
An audit checks the archive and member hashes without extracting it; it does not
repeat the semantic review.

This archive covers the **declared inputs only**. It cannot preserve an omitted
dependency, authenticate the reviewer, or recover undeclared remote facts. Include
the original evidence the review needs in those inputs; retain a stable source
identity and observation time when an external source cannot be copied. Local
hashes do not certify future freshness. A historical archive supports the past
conclusion and never substitutes for a fresh receipt after the current inputs change.

## What a hook inlines, and what it points at

Both hooks write into the model's context, and they had the same bug for different reasons:
they quoted files the model can open. The rule that settles it:

> **A hook inlines only what it alone possesses. Everything already on disk gets a path.**

| | Stop, at a completion claim | SessionStart, once per boundary |
|---|---|---|
| **Possesses alone** | the anchor verdict it just measured; the refusal's reason | the fact that a run exists at all |
| **Inlines** | verdict and obligation inside the deny's reason; the owner-facing one-liner | the frozen terms: intent, boundary, anchor, carry-over |
| **Points at** | the bodies of `### State`, `### Lessons`, `### Next`, `## Acceptance` | everything else, named when dropped |
| **Size** | bounded, **independent of the artifact** | bounded by `CONTEXT_LIMIT`, frozen terms exempt |

The asymmetry is not inconsistency. At a session boundary the run **does not know a goal
exists**, so it has no reason to open any file - the injection's job is to establish that
there is a run and what it may not do. A prohibition delivered by pointer is a prohibition
the run can decline to read, which is why `## Boundary` is inlined and `## Roles` is not.
Mid-run the model has already been told all of that, so the only thing it cannot get for
itself is what the anchor just did.

Two numbers from the first real artifact, which is where both rules came from: the Stop
payload was **4,683 characters per turn** against a 40-turn ceiling, and `## Anchor` alone
was **7,752 characters** - 97% of the injection budget, so every restart lost the anchor.
Neither was visible against the shipped template, whose sections are a quarter the size.

## `## Acceptance` is not a task ledger, and here is the line

This is the boundary most likely to be misread later, so it is drawn explicitly rather
than left to taste. An earlier version of this Skill refused a task ledger outright. That
refusal was half right, and the half that was wrong was conflating two different objects.

| | A plan / task ledger | An acceptance list |
|---|---|---|
| Shape | ordered, with dependencies | **unordered**; every line stands alone |
| Answers | *what to do next* | *what is still not true* |
| Decided | at authoring time | the run picks, every turn |
| Routing | can be revised by the model; authored executable edges form a graph | does not prescribe routing |
| Mechanically | a numbered list | `- [ ]` / `- [x]` lines, and `ACCEPTANCE_ORDERED` refuses a numbered one |

A plan says "first the API, then the web package, then release" and can change as
the model learns. An acceptance list says "these four things must be true" without
prescribing the route. The second is **the stop condition written out longhand**.
An optional plan file alone does not turn a loop into a fixed graph.

So the rule is about **this section's shape, not about the owner's planning method**:
`## Acceptance` is unordered, and `ACCEPTANCE_ORDERED` refuses a numbered one. How the
owner or the run plans its work — a scratch `plan.md`, a `tasks.json`, a checklist in a
ticket — is their choice. The main model can route from that plan and revise it as
evidence changes. The plan never substitutes for the acceptance evidence.

Why bother, when `## Stop condition` was already there: one sentence plus one anchor can
answer *is the whole thing done*, and cannot answer *which parts are*. The second question
is the one a long run gets wrong, by declaring victory on the strength of the part it
finished. Anthropic's long-running harness reached for the same object for the same reason
— a feature list initially failing, with passing status earned through real testing.
Its one-feature-per-session cadence was an experimental choice, not our contract.

And `[x]` is a claim. It is written by the run, so it sits on the claims side of the line
above, and the evidence that settles it is named rather than assumed: each line carries a
stable ID, and `## Verification`'s `covers` map says whether that ID is settled by the
anchor or by a required review. The line's *text* is frozen with the rest of the spec; only
the checkbox moves. `--audit` is where claim and measurement meet.

## What the gate says, and to whom

Two channels, and confusing them wastes the deny - the one contact with the model that
still ends nothing.

| Channel | Read by | Carries |
|---|---|---|
| the deny, in the asking host's own shape | the model, when a claimed completion may not stand | why it may not stand, and the one thing to do first |
| `systemMessage` | the owner | one line of what happened |

There is no per-turn injection channel, and that is a measured fact, not a preference: on
Claude Code 2.1.260 an allow carrying `additionalContext` continues the turn instead of
ending it. What the run owes (carry-over rewritten, lessons written, commits only if authorized) rides
the skill's standing instructions and the deny's reason - the reminder inside the reason
names `### Next`, `### Lessons`, `### State` and the still-open `## Acceptance` lines,
never a frozen section: what the gate reminds the run of is exactly what it may change.

A deny also cannot be one payload for all hosts, and both halves are measured: the mixed
payload (top-level `decision: "block"` plus nested `permissionDecision`) was inert on
Codex 0.150.1, while deleting the nested form globally left Kimi 0.40.1 - whose parser
reads `hookSpecificOutput.permissionDecision` only - with no blocking path at all. One
Stop output cannot be shared across vendors, so the gate reconstructs exactly one
allowlisted shape per asking host, and every test pins the shape per host rather than
what one script emits. A payload contract is a claim until something outside the emitter
agrees with it.

## Why the spec is frozen while a run is in flight

A run changing its own acceptance could make an easier problem look like the
requested result. Frozen terms keep that decision with the owner while leaving
methods and routing to the model. A slower, authorized design pass may revise the
target; ordinary execution cannot silently do so.

So divergence splits by layer:

| The plan was wrong about | Write it in | May the loop continue? |
|---|---|---|
| an approach — this path is dead, this dependency has a trap | `### Lessons` | yes, adjust and carry on |
| the extent — bigger than expected, three modules left | `### State` | yes, adjust and carry on |
| **the target** — the anchor is not measuring what we actually want | `## Challenges from the run` in decisions, with the counterexample | do not claim success against the wrong target; resolve revised terms with owner authority |

The third row is the one worth enforcing socially even though no mechanism can catch it. An
anchor that turns out to measure the wrong thing is the most valuable finding a loop can
produce, and also the one it is most tempted to quietly route around.

## What history these files actually retain

Version control holds committed revisions, not every attempted or abandoned step:

- `git log -p <slug>.goal.md` — the before and after of authorized committed changes.
- `git log --oneline <slug>.goal.md` — one line per commit, not necessarily per turn.
- `<slug>.events.jsonl` — observed events, including verification start and settlement;
  it does not contain every tool call or business effect.
- Required review archives and native receipts/traces — the sources needed to check
  the conclusions they support, retained independently of a mutable summary.

Carry-over answers "what should the next turn know now". Link the important
observations instead of appending a full narrative. Without commits, an overwritten
summary cannot be reconstructed unless its needed facts were retained elsewhere.

One consequence worth stating: **a summary is a derived checkpoint, not a source of truth.**
Where a summary is unavoidable, it carries the id or digest of what it summarizes, so a later
reader can locate the evidence and detect relevant changes. A digest detects a
changed file; it cannot reconstruct a deleted file or establish semantic correctness.

## Work-step records

For a long coding goal with commit authority, Git is the trajectory. Commit each
checkable work unit before starting another; a tool call is not necessarily a unit.
Use one commit for a coherent change or supported experiment, not an empty commit
for every status message. Preserve unrelated user changes outside the commit.

```text
goal(example) step: fix batch timeout

Reason: The existing timeout interrupts valid batches.
Check: The batch smoke command exited 0 on the updated implementation.
Evidence: tests/batch-smoke.txt
Remaining: Concurrent batches have not been checked.
Writer-Session: actual-native-writer-session
```

`Reason`, `Check`, `Evidence` and `Remaining` are nonempty work-record fields.
The check names the actual command and result; use an honest not-run reason for a
checkpoint that has not been checked. `Remaining: none` is valid when nothing is
unresolved. Give one `Evidence:` line per repository-root-relative regular file
retained in that commit: a changed artifact, test, result or note locating the
original observation. External evidence can stay in its authorized home; retain
its stable locator and limitations in the referenced note. Do not commit private
source material without authority. This record is a decision summary, not private
reasoning or independent proof that the check ran.

For a step that implements or changes the product, add `Writer-Session:` for each
actual contributing native session, including workers. Preserve those identities
when squashing worker commits. Preparation and independent review records do not
make their authors product writers; do not add their sessions under that label.
Resolve unknown writer identities before calling the review independent; never
copy the coordinator's identity or invent one for a worker.

The existing `--audit` reads `goal(<slug>) step:` commits since the arming-time Git
baseline, checks these fields and checks each evidence file in its **original
commit**, even if the file was later moved or removed. It reports missing records
and inaccessible evidence; it does not replay checks, certify a conclusion or
discover uncommitted work. Legacy commit titles remain available to the older
claim audit and are not retroactively required to contain these fields. No Git
baseline means no step-history coverage. Keep the work unit's state current before
its commit; Git then retains each committed revision without a duplicate trajectory.

The required-review gate also excludes `Writer-Session` identities declared in this
goal's commits. These are inspectable declarations, not authenticated authorship;
they do not discover omitted writers or work on an unjoined branch. Join writers
before review, retain their records, and check the actual role assignment.

## Where multi-worker rounds put things

Delegating uses scratch missions/results and retains the evidence needed for accepted
conclusions. Separate goal files do not isolate shared product writes: declare actual
resource ownership and integration responsibilities when workers write in parallel.

```
.goals/
  active                        # the running slug
  audit.goal.md                 # spec + carry-over, owned by the orchestrator
  audit.decisions.md
  audit.events.jsonl            # the coordinator's event log
  audit.review.json             # the current required independent receipt
  audit.reviews/                # retained receipt, goal and declared input snapshots
  .work/                        # gitignored, one round's lifetime
    codex.mission.md
    codex.result.md
    kimi.mission.md
    kimi.result.md
```

Three rules make this work, and they come from the same place — separating a worker's private
context from typed artifacts from an immutable coordinator log:

1. **Give workers the context their mission needs.** Pass the accepted terms,
   relevant decisions, previous failures and original evidence. For independent
   review, exclude the generator's persuasive argument. Do not blindly replay
   complete transcripts or withhold a shared decision the worker needs.
2. **The orchestrator runs the anchor, not the workers.** A worker's report of success is a
   claim; the actual output and current required review settle the contract. Join
   writers and validate the integrated result, not just each worker's isolated output.
3. **Retain the evidence, prune the discussion.** A required receipt and its
   supporting inputs must survive the round. A lesson or event digest is not a
   substitute for the only inspectable source. Delete scratch only after checking
   that necessary evidence has a retained home.

## What is left behind when a loop is done

Disarm through the owning run's normal entry point. Keep the goal, decisions,
events and required review evidence for the agreed audit/recovery lifetime. Commit
only if authorized. They document the recorded contract and observations, not an
automatically complete history of every attempted action.

Remove only disposable `.goals/.work/` material after the required receipt/input
archive and other necessary sources are retained and readable. Do not remove an
unsettled attempt's recovery evidence. Retiring a goal may move useful knowledge
into the project's existing documentation; it does not authorize deleting its only
audit source or publishing private inputs. An empty marker is not proof that all
business work succeeded.


## If you also run a spec-driven development harness

A full harness — an init/research/plan/dev pipeline with a task ledger — and this Skill solve
adjacent problems, and it is worth being explicit about which owns what, because running both
without deciding produces two half-authorities.

| Harness artifact | Here | Why |
|---|---|---|
| `north-star.md` | `## Intent` | One artifact is one loop, so its intent *is* its North Star |
| `specs/product.md`, `specs/architecture.md` | `## Boundary` + `## Anchor` | Condensed to what a loop needs: what it may touch, and what proves it worked |
| a change's `intent.md` | `<slug>.goal.md` | The same document under a different name |
| `decisions/` | `<slug>.decisions.md` | Same role |
| `evidence/`, `verification.md` | events plus required receipt/input archives | source material and measured facts support the written account |
| `contexts/TEMPLATE.md` | `### State` + `### Lessons` | Condensed to what the next turn must read |
| `changes/{active,archive,abandoned}` | `.goals/active` + Git | Three states are a workflow; one marker plus history is enough for one loop |
| **`tasks.json`** | optional execution plan | Use when dependencies need a durable list |
| **`plan.md`** | optional execution plan | Link the current plan from Carry-over rather than duplicating it |

### Optional execution planning

A short goal usually needs only Carry-over. A longer task can use `plan.md`, `tasks.json`,
or the repository's existing planning tool. The main model chooses and revises execution
steps within the frozen intent and authority. A plan is not completion evidence, and a
list of steps does not require a new runtime.

Keep `## Acceptance` for observable outcomes and `### Next` for the immediate recovery
action. The Stop hook checks a completion candidate; it does not walk the task list.
