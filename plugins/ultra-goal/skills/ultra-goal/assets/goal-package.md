<!--
Shared goal contract for every execution shape. Save as `<slug>.goal.md` next to
`<slug>.decisions.md`; workflow/delegation attachments reference this same contract.
Adapt every path, check and identity to the inspected project before confirmation.
This example assumes an existing tests/ directory and a pnpm workspace.
-->

# Goal: weekly-dep-upgrade

## Intent

Owner request (illustrative; replace with the actual material wording):
> Keep production dependencies free of high-severity advisories without breaking the build.

Agreed intent: resolve those advisories while preserving the existing product checks.

## Boundary

**Scope.** Only `package.json` and the lockfile. Never application source, CI config, or a
pinned transitive override that carries an explanatory comment. Committing to the run's own
branch is authorized; pushing and opening the PR is authorized; merging it is not. The
commit gate belongs here and nowhere else - a run whose boundary does not authorize commits
keeps its record in these files and says so, rather than treating a commit as owed each
turn.

**Confidence.** Never call an upgrade safe, passing, or done without the anchor command's
real output in this session.

**Inference.** Never conclude why a dependency broke from its changelog or an issue thread.
Reproduce it locally first.

## Stop condition

Stop when `pnpm audit --audit-level=high` reports 0 findings, or at the ceiling below.

success: verified
ceiling: 6

Write `ceiling: none` instead for a run that should continue until the anchor is green,
subject to the separately authorized native resource budgets. New goals require this
explicit field; omission fails validation. Exhaustion is an unverified exit, not success.
Use the actual host controls for time, tokens and spending. Within that authorization,
leave enough room for the required review, current verification and result delivery;
the completion ceiling does not reserve or expand those resources.

## Anchor

```
pnpm audit --audit-level=high && pnpm test -- --run && pnpm build
```

budget: 2 minutes

Success requires every check above and the required independent review below. A
passing audit with a failing build is a failed iteration, not a partial success.

This anchor crosses the whole path on purpose: `pnpm test` alone can be green while the
application does not start, because a unit suite exercises the code and not the product.
Where a build is not enough - a UI, an API contract, a payment path - the anchor has to
drive the running thing.

## Means

What we believe it takes to reach the intent, and whether the run may abandon it. The
labels are the owner's. Dropping a `[droppable]` one is authorized and costs one row in
`weekly-dep-upgrade.decisions.md` naming the evidence; dropping a `[load-bearing]` one is
not authorized at all - stop and report instead.

- `[load-bearing]` move versions through `package.json` and the lockfile only - anything
  wider changes what "safe" means here
- `[load-bearing]` keep the anchor green; an upgrade that breaks the build is not an
  upgrade
- `[droppable]` clear every advisory in one pass - drop it when a single dependency needs
  a source change to move, and report that one on its own
- `[droppable]` keep the change to one commit - drop it when a bisectable series would
  tell the reviewer more

## Roles

This example chooses a reviewer/critic triad and named roles. When authoring a new goal,
keep only roles required or useful for that goal and record the actual assignment; this
example does not require a critic, a design review or a fixed coder for every run.

- **lead**: this session, with the owner. Interview and spec.
  fallback: none; an interview cannot be delegated to something the owner is not talking to.
- **research**: fanned-out subagents, fresh context each, one per independent question.
  fallback: this session inline, narrower.
- **design critic**: `/ultra-goal:design-critic weekly-dep-upgrade`, run once at the end of
  the interview before any work starts. Use a host-supported fresh context and check input
  isolation; provide the original owner request and clarifications alongside the draft.
  fallback: an available independent context. If unavailable, disclose the limit before
  unattended execution; do not treat start authorization as a waiver or record a pass.
- **carry out**: this session. Writes the code and relevant checks; choose testing order for the change.
  fallback: an authorized worker given Carry-over, previous failed attempts and evidence.
- **judge**: this session, **blind first**. Run the anchor yourself, write the verdict to
  `weekly-dep-upgrade.judge-review.md`, and only then read the reviewer's and critic's
  reports and record where the three readings differ. fallback: none; a judge that reads
  the reports first has been persuaded before it decided.
- **anchor**: the command in `## Anchor`. No model in the path.
  fallback: none; if it cannot run the outcome is unknown, which is the answer rather than a
  failure.
- **reviewer**: `/ultra-goal:review weekly-dep-upgrade` as `independent-reviewer`. Use it only after confirming the host gives that fork a distinct native session ID.
  Otherwise invoke a separate reviewer session with the same instructions and approved
  identity. Give it the frozen inputs, boundary and raw anchor output, never this
  session's argument for correctness. fallback: another independent session using the same verifier
  identity and criteria; never the generating session. Otherwise pause unverified.
- **critic**: `/ultra-goal:critic weekly-dep-upgrade`, after the reviewer. Audits the
  review, not the code. fallback: none; without the third role the review is nobody's job to
  audit, so a round without a critic is reported as unreviewed.

**This example uses context independence.** Keep the author's argument out of the
reviewer input. A same-model reviewer may share blind spots; a different vendor can
also share them. Choose a reviewer appropriate to the accepted criteria and verify
its evidence instead of inferring correctness from model diversity.

**Review runs at proposed completion**, not every turn: on intermediate turns the anchor is
already the check.

## Verification

```json
{
  "source": "owner-approved",
  "basis": "Owner accepted the existing product tests; independent review checks that manifest scripts and dependency scope were not weakened.",
  "protected": ["tests"],
  "covers": {"audit": "anchor", "build": "anchor", "scope": "review"},
  "review": {
    "path": ".goals/weekly-dep-upgrade.review.json",
    "verifiers": ["independent-reviewer"],
    "inputs": ["package.json", "pnpm-lock.yaml"]
  }
}
```

Pin the project's actual evaluator definitions and fixtures, including configuration
used indirectly. The paths above are examples, not a complete dependency inventory.
The independent reviewer writes the current receipt described in the skill's
goal-contract reference; a markdown report or tool success alone is insufficient.
Keep the required receipt and the gate's `.goals/weekly-dep-upgrade.reviews/` input
archives when cleaning disposable worker scratch. Only declared review inputs are
retained automatically; include every original source needed to check its conclusion.

Run `/ultra-goal:review weekly-dep-upgrade`, then `/ultra-goal:critic weekly-dep-upgrade`.
Both are forked skills: the fork never sees the invoking conversation, so the author's
account of why the change is correct cannot reach them - and that account is what a reviewer
conforms to. Every finding cites file:line and the command whose output proves it. A **critic** then audits that review rather
than the code, sorting every point into exactly one of agreement, evidence-backed
disagreement, or concern-based disagreement. The reviewer answers a disagreement with
evidence, never with a rebuttal. This example allows at most 5 inner rounds; if round 1
converges with no findings, accept. When authoring another goal, choose a repeated-review
cap and native resource budget appropriate to it rather than inheriting this number.

The critic receives the review and the diff, and not the main agent's opinion of the
review. The diff stays frozen for that exchange. Only after the review is consistent does
the main agent edit again.

## Acceptance

Unordered: each line stands alone and the run picks which to attempt. `[x]` is the run's
claim; the anchor's output is the evidence, so a line moves to `[x]` only after that output
showed it. Keep execution steps in a separate plan; this section records outcomes.

- [ ] audit: `pnpm audit --audit-level=high` reports 0 high-severity findings across the workspace.
- [ ] build: The independently accepted product checks and build pass.
- [ ] scope: Manifest scripts and acceptance definitions were not weakened; dependency changes stay within the boundary.

## Cadence

Roughly weekly, started by hand. Advisories arrive continuously but this codebase absorbs
them weekly, and starting it daily costs six extra runs to find the same finding.

Cadence schedules repeated starts. Carry-over is also required for a single start
that may compact or be interrupted.

## Carry-over

Read this before acting; reconcile it with the cited evidence and rewrite it before
finishing. Remove stale summaries while retaining their necessary source evidence.
Git retains committed revisions only; an uncommitted rewrite has no automatic history.

### State

Where the work stands and where to verify it. Prefer a compact set (eight is a review
prompt, not a validity limit); link longer evidence or an existing plan.

- remaining after iteration 6: `packages/api`
- last fully green run: iteration 5

### Lessons

Why something failed and what to do instead — a supported cause and a next action.
Prefer a few relevant lessons; three is a compactness suggestion. Keep a necessary
fourth lesson or link its details rather than deleting evidence to satisfy the count.

- `@types/node` 22 breaks tsconfig because the bundler resolver rejects its new conditional
  exports - pin at 20 and revisit when tsconfig moves to `node20`
- `pnpm build` fails on CI without a committed lockfile because CI runs
  `--frozen-lockfile` - commit the lockfile in the same change

### Next

The one objective for the next round, derived from this round's anchor verdict and the
review findings that survived it, inside the frozen intent. Exactly one immediate action;
link a longer execution plan from here if useful.

- get `packages/api` to a green anchor with `@types/node` pinned at 20

## Handoff

Start it with **`/ultra-goal:goal-run weekly-dep-upgrade`** where this plugin is installed:
one step to validate the artifact and arm the gate, through the one fence that binds the
run to this session and records its authorized baselines. The run then works in ordinary
host turns, and the gate judges completion claims - it refuses a claim while the claimed
completion's anchor is still red.

**Arming is not a continuation service.** The gate decides what the run may claim; it does
not supply the next turn. This host has goal mode, so an unattended run is started under
`/goal` **as well as** armed - and on a host without one, the run stops at each turn
boundary and the report says it is awaiting a prompt rather than running unattended.

Where the plugin is absent, paste the text below as a plain prompt. Without the plugin
there is no gate to satisfy: run the anchor yourself, show its real output, and report
against it honestly. If the plugin's install root is reachable, arm from it - `python3
<plugin-root>/skills/ultra-goal/scripts/goal_run.py arm weekly-dep-upgrade --session-id
<this session's native id>` - and the gate goes live. The session id is required: arming
refuses without one rather than leaving the run unowned for whichever session stops first.

```
/goal Read the Carry-over section of .goals/weekly-dep-upgrade.goal.md first. Then upgrade
dependencies until `pnpm audit --audit-level=high` reports 0 findings, touching only
package.json and the lockfile - never application source or CI config.
You have not met this goal until you have actually run `pnpm test -- --run && pnpm build`
in this session and seen it exit 0: do not claim completion from reasoning about the code,
and do not call an upgrade safe without that output. When you report on the anchor, name
the attempt number and the exit code you saw rather than summarising it.
Do not conclude why something broke from a changelog alone - reproduce it.
Open a PR but do not merge it.
You are the run for weekly-dep-upgrade, not its designer: the terms below were already
agreed, so do not reopen them as an interview.
If a means labelled droppable turns out not to serve the intent, drop it and write the
argument into .goals/weekly-dep-upgrade.decisions.md; never drop a load-bearing one, and
preserve the complete frozen contract: Intent, Boundary, Anchor, Stop condition,
Verification, Acceptance requirement text and all labelled Means declarations.
Only Acceptance checkboxes are mutable claims within those sections. If a frozen term
turns out to be wrong, stop and
write a row under `## Challenges from the run` in that same file naming the term, what you
hit, and what would settle it - then say you stopped for that reason.
At the start of each turn, state which turn you are on,
which `## Acceptance` lines this turn is for, what you need to find out before touching
anything, and what output would prove those lines - before changing anything.
If a role in `## Roles` could not be reached, say so in the report and put it in
`### Lessons`: a review that could not happen is a missing review, not a pass. Retry the
role or its declared fallback before claiming completion, and wait for every role you
invoked to finish.
Rewrite the Carry-over section before you finish - State gets where the work stands,
Lessons gets the relevant causal findings and source pointers, Next gets the single
objective for the following round. Prune stale summaries, not their only evidence.
If a push or PR creation times out, retain the known operation/branch identity and
query the actual remote state before retrying. Missing confirmation is unknown,
not proof that nothing happened or that the owner must answer another question.
When you believe the goal is met, finish all output edits and required review, then call
goal_run.py verify weekly-dep-upgrade --root <project> --session-id <current-native-session-id>
using the installed script path. Read its current recorded verdict before final delivery;
only verification_passed true permits a success claim. Do not edit reviewed outputs afterwards. Committing is authorized for
this goal, so commit ordinary work turns as `goal(weekly-dep-upgrade): <summary>`, and a
completion attempt the gate has measured as
`goal(weekly-dep-upgrade) turn <N>: <summary> [anchor: green|red|unknown]`, with <N> the
number in the gate's message - and if a commit is ever refused, say so and leave the state
in the files rather than working around it. Stop after 6 completion attempts even if
unmet, and say so.
```

Ten clauses, one hole each: objective inside a scope, anchor as the only accepted
evidence, no confidence claim without it, the verdict reported as an attempt number and
an exit code rather than a summary, no conclusion from documents alone, **the run is the
run and not the designer**, droppable means droppable with a wrong term challenged rather
than edited, state the turn out loud, rewrite carry-over including Next, and completion
checked through the shared gate before final delivery. Host: Claude Code (recorded in
the decisions record) - the objective is portable, and `/ultra-goal` starts it wherever the plugin is installed.

First iteration should produce: the audit output, the version bumps it implies, the anchor
command's real output, and a rewritten Carry-over section.

Afterwards, `validate_artifact.py .goals --audit` puts each completion attempt's committed
verdict beside the verdict the gate measured for it. They should agree on every row; a row
where they do not is where to start reading.
