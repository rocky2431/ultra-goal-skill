<!--
Template for a loop artifact. Save as `<slug>.goal.md` next to `<slug>.decisions.md`.
Replace the content, keep every `##` heading: the validator requires all five, and each
one is a question the owner answered during the interview.
The example below is real and passes validation - read it as the standard, not as filler.
-->

# Goal: weekly-dep-upgrade

## Intent

Keep production dependencies free of high-severity advisories without breaking the build.

## Boundary

**Scope.** Only `package.json` and the lockfile. Never application source, CI config, or a
pinned transitive override that carries an explanatory comment. Opening the PR is
authorized; merging it is not.

**Confidence.** Never call an upgrade safe, passing, or done without the anchor command's
real output in this session.

**Inference.** Never conclude why a dependency broke from its changelog or an issue thread.
Reproduce it locally first.

## Stop condition

Stop when `pnpm audit --audit-level=high` reports 0 findings, or after 6 turns.

## Anchor

```
pnpm test -- --run && pnpm build
```

Green here is the only evidence an upgrade is safe. A passing audit with a failing build
is a failed iteration, not a partial success.

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

## Verification

A **reviewer** with a fresh context reviews the diff against this boundary, citing file:line
and the command whose output proves each finding. It receives the frozen diff, this
boundary, and the anchor's own output - never the main agent's account of why the change is
correct, because that account is what a reviewer conforms to. A **critic** then audits that review rather
than the code, sorting every point into exactly one of agreement, evidence-backed
disagreement, or concern-based disagreement. The reviewer answers a disagreement with
evidence, never with a rebuttal. At most 5 inner rounds; if round 1 converges with no
findings, accept.

The critic receives the review and the diff, and not the main agent's opinion of the
review. The diff stays frozen for that exchange. Only after the review is consistent does
the main agent edit again.

## Cadence

Roughly weekly, started by hand. Advisories arrive continuously but this codebase absorbs
them weekly, and starting it daily costs six extra runs to find the same finding.

Because it gets started more than once, it needs the Carry-over section below.

## Carry-over

Read this before acting; rewrite it before finishing. Delete anything no longer true - Git
keeps the history, this section keeps only what is still the case.

### State

Where the work stands. At most 8.

- remaining after iteration 6: `packages/api`
- last fully green run: iteration 5

### Lessons

Why something failed and what to do instead - a cause and a next action, never just an
event. At most 3, because entries here compete with the work for reasoning budget.

- `@types/node` 22 breaks tsconfig because the bundler resolver rejects its new conditional
  exports - pin at 20 and revisit when tsconfig moves to `node20`
- `pnpm build` fails on CI without a committed lockfile because CI runs
  `--frozen-lockfile` - commit the lockfile in the same change

### Next

The one objective for the next round, derived from this round's anchor verdict and the
review findings that survived it, inside the frozen intent. Exactly one: a list of them is
a plan, and a goal with a plan should have been authored as a graph.

- get `packages/api` to a green anchor with `@types/node` pinned at 20

## Handoff

Paste this into the host's goal mode - `/goal` on Claude Code, Codex, Kimi, or zCode; on a
host without goal mode, the same text as a plain prompt:

```
/goal Read the Carry-over section of .goals/weekly-dep-upgrade.goal.md first. Then upgrade
dependencies until `pnpm audit --audit-level=high` reports 0 findings, touching only
package.json and the lockfile - never application source or CI config.
You have not met this goal until you have actually run `pnpm test -- --run && pnpm build`
in this session and seen it exit 0: do not claim completion from reasoning about the code,
and do not call an upgrade safe without that output. When you report on the anchor, name
the turn and the exit code you saw rather than summarising it.
Do not conclude why something broke from a changelog alone - reproduce it.
Open a PR but do not merge it.
You are the run for weekly-dep-upgrade, not its designer: the terms below were already
agreed, so do not reopen them as an interview.
If a means labelled droppable turns out not to serve the intent, drop it and write the
argument into .goals/weekly-dep-upgrade.decisions.md; never drop a load-bearing one, and
never edit Intent, Boundary or Anchor. If one of those turns out to be wrong, stop and
write a row under `## Challenges from the run` in that same file naming the term, what you
hit, and what would settle it - then say you stopped for that reason.
State which turn you are on at the start of each turn.
Rewrite the Carry-over section before you finish - State gets where the work stands,
Lessons gets at most 3 causal findings, Next gets the single objective for the following
round, and delete what is no longer true.
Commit once per turn as `goal(weekly-dep-upgrade) turn <N>: <summary> [anchor: green|red|
unknown]`. Stop after 6 turns even if unmet, and say so.
```

Nine clauses, one hole each: objective inside a scope, anchor as the only accepted
evidence, no confidence claim without it, the verdict reported as a turn and an exit code
rather than a summary, no conclusion from documents alone, **the run is the run and not the
designer**, droppable means droppable with a wrong term challenged rather than edited,
state the turn out loud, rewrite carry-over including Next. Host: Claude Code (recorded in
the decisions record) - the objective is portable, the `/goal` prefix is what changes.

First iteration should produce: the audit output, the version bumps it implies, the anchor
command's real output, and a rewritten Carry-over section.

Afterwards, `validate_artifact.py .goals --audit` puts each turn's committed verdict beside
the verdict the gate measured for that turn. They should agree on every row; a row where
they do not is where to start reading.
