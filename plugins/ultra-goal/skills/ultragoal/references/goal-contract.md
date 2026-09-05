# One goal contract, any execution shape

Every run owns `.goals/<slug>.goal.md` and its decisions record. A workflow or
delegation file is an optional execution attachment with the same slug. Every
shape uses the same arming, frozen specification, evidence and completion path.
Do not emit a workflow without an installed, exercised consumer; a syntax check
does not establish that `agent()` or `pipeline()` exists in the current host.

## Author and confirm

Resolve repository facts before asking. Interview only material uncertainty, then
read back intent, each acceptance requirement, authority, success and exit
conditions, load-bearing/droppable means and verification obligations. Before
confirmation, attempt a counterexample where every check passes but the owner
would reject the result. Resolve that counterexample or disclose the remaining
uncertainty; a deterministic command cannot prove that its specification is right.

During Init, probe only an unknown that could change a material goal decision and
stop once it is resolved. Testing whether an existing entry point starts is a
feasibility check; completing the deliverable before the readback is execution.
Do not turn exploration into an unconfirmed implementation project.

A counterexample must identify an unmet part of the owner's actual intent.
Manual production of a correct one-off result is not a counterexample unless
repeatability is required. Do not promote a preferred method, reproducible
pipeline, extra report or architecture standard into acceptance by yourself.
Likewise, a checker proving that a report exists does not prove it is readable.
Reuse explicit owner answers; ask again only when new evidence invalidates them.

Preserve the owner's material words and clarifications verbatim in `## Intent`,
with a conversation/source locator when available, separately from the operational
interpretation. Do not invent a quotation or treat an agent summary as the source.
Show a draft to an independent reviewer before offering unattended execution,
when specification adequacy is unresolved, or when the owner requires it. The
reviewer compares each acceptance item with those original words, tries a concrete
all-green-but-unsatisfactory result and a satisfactory result the checks would
wrongly reject. Resolve material objections in the existing decisions record
before confirmation; no new ledger or numeric confidence vote is needed.
If the owner already approved the complete terms and said to start without more
questions, perform the independent critique against those terms before arming.
That approval removes a redundant confirmation, not the independent check. A clean
critique needs no further owner turn; only a material objection needs resolution.
An explicit owner waiver or an unavailable independent context must be disclosed
as a limit, never inferred from "start now" or recorded as a passing critique.
The reviewer needs the original owner request as well as the draft and evidence,
not just the author's rationale. Confirmation approves
the complete contract, not a blank authorization to invent weaker criteria later.

## Required machine contract

Every acceptance bullet has a stable ID. The text is frozen; `[ ]`/`[x]` are
mutable claims. A claim never supplies completion evidence.

````markdown
## Acceptance

- [ ] audit: No high-severity dependency advisories remain.
- [ ] build: Existing product acceptance checks and build pass.

## Stop condition

success: verified
ceiling: 6

## Anchor

```sh
pnpm audit --audit-level=high && pnpm test -- --run && pnpm build
```
````

`success: verified` means the current anchor is green and every required review
has passed on the current declared inputs. Thresholds belong in those checks.
The ceiling counts completion attempts, not tool calls, host turns, tokens or
money. Configure native budgets for those resources during setup; exhausting any
budget ends or pauses unverified, never successfully. `ceiling: none` is explicit.
Size the work against the actual native time/token/spend limits and observed tool
latency. Leave room within the approved budget for required review, verification
and delivery; an optional critic must not consume the only remaining opportunity
to close the goal. There is no universal reserved percentage or extra allowance.

`## Verification` contains exactly one JSON block with these fields:

```json
{
  "source": "owner-approved",
  "basis": "Owner accepted the independently inspected acceptance program and fixtures.",
  "protected": ["verification/acceptance.py", "verification/cases.json"],
  "covers": {"audit": "anchor", "build": "anchor"},
  "review": null
}
```

- `source`: `owner-approved` for an accepted evaluator definition or `external`
  for an authoritative external evidence source. Neither means self-review.
- `basis`: the concrete provenance and what the owner accepted. This is a
  declaration to inspect during confirmation, not an authenticated credential.
- `protected`: explicit project-relative evaluator files/directories. Pin the
  acceptance logic, fixtures and configuration it depends on, including indirect
  scripts. Arming records hashes in `<slug>.verification.baseline`; changes or
  missing inputs refuse verification. Do not protect the implementation being
  improved. External evidence may have no local evaluator inputs; declare that
  weaker local coverage honestly. All local definitions still need protection.
- `covers`: every acceptance ID maps exactly once to `anchor` or `review`. This
  checks declared coverage, not the semantic adequacy of the mapping.
- `review`: `null` when the accepted anchor fully covers the requirements, or
  the required independent review contract below. Additional advisory review is
  free to vary; a required review cannot be silently made optional.

An anchor is observational and must check the current requested result end to
end. It must not modify protected definitions or the reviewed product. Runtime
dependencies and external services can drift: either bind the relevant identity
in the evaluator or name the limit. A copied command string is not a pinned
evaluator. Generate project-specific checks only after settling the criteria;
allow independent inspection before the owner approves them.

## Required independent review

When semantic acceptance needs independent judgment, replace `review: null`:

```json
{
  "path": ".goals/demo.review.json",
  "verifiers": ["claude-reviewer", "kimi-reviewer"],
  "inputs": ["src", "report.md"]
}
```

The list authorizes equivalent verifier identities/fallbacks; it does not
authorize the generator to review itself. The independent verifier reads the
criteria and actual bounded inputs, obtains its own native session identity,
and computes a digest binding the frozen goal terms and current input files with:

```sh
python3 /installed/skill/scripts/goal_run.py review-inputs demo --root /project
```

Resolve the actual installed script path and project root. The verifier writes
the configured JSON receipt itself, alongside any detailed human-readable review:

```json
{
  "verifier": "claude-reviewer",
  "session_id": "actual-independent-native-session-id",
  "input_digest": "the SHA-256 returned by review-inputs",
  "covers": ["semantic-requirement-id"],
  "verdict": "pass",
  "evidence": "Checks performed, observations and remaining limits.",
  "checks": {
    "semantic-requirement-id": {
      "claim": "The report's material conclusion agrees with the original evidence.",
      "evidence": [{"path": "report.md", "quote": "An exact excerpt read from this input"}]
    }
  }
}
```

Use a non-pass verdict when unresolved findings remain. Do not manufacture a
passing receipt for a missing review. The completion gate checks the approved
identity, a session distinct from every recorded bound execution session, current
input digest, required IDs, passing verdict and an evidence-backed `checks` entry
for each requirement assigned to review. Each entry has a concrete `claim` and
nonempty `evidence` references; every `path` must be a file under `review.inputs`
and each `quote` must occur there verbatim. For a report, include both the claimed
result and the original supporting evidence in the review inputs, then check all
material factual statements and limitations, not merely presence or readability.
Quotes provide inspectable references; matching text does not prove the claim
follows from it. The reviewer must establish that relationship independently.
The generator must wait for invoked writers before requesting review
and must request a new review after changing those inputs.

Keep required receipts outside disposable `.work/` by default. After the current
anchor and review checks pass, the gate retains an archive of the exact receipt,
goal and all declared `review.inputs` in `.goals/<slug>.reviews/<digest>.zip`.
The event records its path and SHA-256; inability to retain the evidence refuses
completion. The archive survives scratch cleanup and supports later integrity
audit. It never replaces a current receipt, authenticates the author, or includes
undeclared upstream facts automatically. Choose the evidence location and any
commit/publication with the task's existing data and authority boundaries.

This is provenance checking in an owner-controlled environment, not identity
authentication. A process that can rewrite every file can forge receipts and
baselines. Use native permissions, isolated verifier workspaces or authenticated
external receipts when the task requires stronger protection. An older receipt must be regenerated when upgrading to this contract-bound digest
and per-requirement evidence format. If the needed
boundary cannot be established, disclose that before offering unattended work.

## Evidence counterexamples

Use these when the corresponding risk is present in the goal; they are checks on
the criteria and verifier, not new requirements for the business result:

- **All green, wrong intent:** a checker verifies that a report exists while the
  material conclusion is unsupported; a correct row count hides the wrong people.
  Compare the result with original source facts and the owner's words.
- **Correct result, wrong rejection:** a one-off output satisfies every outcome
  through an authorized alternative method, but the checks demand the initial
  droppable tool. Remove that extra method requirement before freezing the goal.
- **Protected entrypoint, unprotected dependency:** change a helper or fixture
  the checker imports. If a bad product can pass, include the relevant dependency
  in the existing `protected`/`basis` contract, or disclose the remaining coverage.
- **True quote, false conclusion:** the cited sentence occurs in the input but
  contradicts the reviewer's conclusion, omits a qualifier or refers to another
  population. Exact quotation matching is necessary provenance, not entailment.
- **Unchanged file, expired fact:** a remote result or environment identity has
  changed while local hashes still match. Record the source identity, observation
  time and validity condition; re-observe when the condition no longer holds.

Calibrate semantic reviewers on independently settled good and bad examples where
this judgment is load-bearing. Keep the evaluator blind to the generator's defense
and compare against actual source facts, computation or a user-visible path.
Record false acceptance and false rejection; agreement among reviewers is not a
substitute for that independent reference. A missing calibration run is a limit,
not evidence of passing one.

## Autonomy and recovery

Frozen: intent, boundary, full success/exit contract, verification obligations,
acceptance requirement text and complete labelled means declarations. Changing
these needs owner authority and a new goal. A decisions row records an action;
it cannot grant authority to lower acceptance or enlarge resource limits.

Within those terms the model chooses strategy, ordering, tools, workers, plans
and execution shape. It may drop a droppable means or use a pre-authorized
verifier fallback, recording the evidence in decisions. Carry-over/State/Lessons/
Next are freely rewritten. Expose a genuinely impossible term through Challenges;
do not relabel it or pretend budget exhaustion is success.

Every compiled goal includes compact `## Carry-over` with State, Lessons and Next,
even when started only once. Read it before acting and rewrite it before finishing
or a known context transition; link to current evidence and unfinished work. Cadence
only specifies repeated scheduling. Recovery does not renew authority or budgets.
Compaction may retain a summary; it does not guarantee that every necessary fact
survives. Reconcile Carry-over against the named inputs, host state and current
observations before relying on it. Compactness is advisory: keep a necessary
fourth lesson rather than discarding evidence to satisfy a bullet count.

A failed delegation is a transport observation. It stays in the audit even if
a fallback succeeds. Required output/review evidence decides completion; the
original target need not recover. Call success is neither a join nor a review.
Silence or a lost reply is unconfirmed, not `input-required`. Read the native
task/receipt state: a worker may still be running or may already have finished.
Use `input-required` only for a concrete unanswered question or an explicit native
waiting-for-input state. Unavailable status is an unknown observation; name its
readback/retry condition instead of inventing a question for the owner.

Separate artifacts do not isolate shared products. For parallel writers, name
their actual files/resources, shared interfaces and integration owner in the
existing mission. Reuse available worktrees or scratch isolation where appropriate;
join and validate the integrated state before review and a completion claim.

Arming and rebind record requested execution-session bindings before activation.
Previous bound sessions remain excluded from required review after recovery. These
records do not discover every delegated writer: the caller must also keep a worker
that authored the result out of its independent review. A recorded frozen-contract
closure cannot be undone by ordinary re-arming, even after restoring the original
text. Each observed closure is audited; it consumes an attempt only if a completion
candidate was present. Use a newly authorized goal to pursue revised terms.

## Recovery after an unknown external effect

Apply this only when a task can perform an external effect that is not safely
repeatable. Before an authorized request, retain the available operation identity
or service-supported idempotency key, target and read-only outcome lookup in the
existing State/evidence record. Record returned IDs as soon as they are available;
do not invent an ID that the service does not recognize.

A timeout or disconnect can occur after the effect succeeds. Leave its outcome
`unknown` until observed. On recovery, query the actual service using that identity
and reconcile its receipt before deciding to retry. If the same authorized action
is safe to retry, reuse its existing idempotency key; a new key may create a second
effect. Never put a business write into the observational anchor to obtain retries.

For example, if a record was created but the response was lost, lookup of the
existing request should settle whether it exists before another create is sent.
If neither readback nor deduplication is available, do independent safe work and
leave that action unresolved. Ask the owner only for an actual authority or risk
decision, not for a fact they cannot supply. Record the missing observation and
what would make retry safe. Local locks/events cannot guarantee exactly-once
effects, and Stop cannot reverse a write or wake a crashed host.

## Setup and final result

Before the owner leaves, exercise the actual artifact entry point, confirm the
native continuation service and resource controls, arm using the current native
session identity, and establish where the owner will read results. Native
authorization/sandbox controls own effects; Stop cannot undo a forbidden write.
Estimate closeout needs from the actual consumer and relevant checks during setup;
respect native quota signals during execution. If a limit prevents the accepted
review or verification, preserve the pending work and report incomplete instead
of weakening checks or extending the budget by assumption.

Ordinary Stop means only a turn ended. A completion candidate triggers current
verification. The event's `verification_passed` is the accepted-contract result;
native goal status and agent prose are separate claims. The event also carries
review provenance when required. `validate_artifact.py .goals --status --json`
exposes `last_verification` separately from `last_anchor_check`: a pending candidate or
newer refusal or unfinished verification takes precedence over an old green.
`verification_started` and settlement share one attempt ID; an unfinished start is
pending/unknown until reconciled and may be marked interrupted by a later owning
gate. It is counted once and is not silently retried. This is a historical observation
(`fresh_check: false`), not a live recheck of subsequently edited outputs.
For final delivery, finish all output edits and required review, then call:

```sh
python3 /installed/skill/scripts/goal_run.py verify demo --root /project --session-id <current-native-session-id> --claim "Accepted result ready"
```

This explicit completion attempt uses the same gate as Stop and returns its actual
recorded observation as JSON before the final response. Exit 0 requires this attempt's
`verification_passed: true`; a missing record, refusal, unknown or exhausted ceiling
returns nonzero. It never starts a model or simulates a host lifecycle event. Read the
result, reconcile native goal status using the host's real tools, and deliver the
output/evidence paths, attempt and remaining limits. Do not edit reviewed outputs
after verification; changes require fresh review and verification. Subsequent ordinary
Stop does not repeat the consumed attempt. The observation is about that measured
state, not future edits.

The candidate-file Stop path remains a fallback. Its final model response may precede
verification: report pending until a real event is observed, and use status/audit or
a later native turn to reconcile. A host without the needed continuation or result
delivery is a supported interactive run, not an unattended one.
