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

## Verification

A **reviewer** with a fresh context reviews the diff against this boundary, citing file:line
and the command whose output proves each finding. A **critic** then audits that review rather
than the code, sorting every point into exactly one of agreement, evidence-backed
disagreement, or concern-based disagreement. The reviewer answers a disagreement with
evidence, never with a rebuttal. At most 5 inner rounds; if round 1 converges with no
findings, accept.

The diff stays frozen for that exchange. Only after the review is consistent does the main
agent edit again.

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

## Handoff

Paste this into the host's goal mode - `/goal` on Claude Code, Codex, Kimi, or zCode; on a
host without goal mode, the same text as a plain prompt:

```
/goal Read the Carry-over section of .loops/weekly-dep-upgrade.goal.md first. Then upgrade
dependencies until `pnpm audit --audit-level=high` reports 0 findings, touching only
package.json and the lockfile - never application source or CI config.
You have not met this goal until you have actually run `pnpm test -- --run && pnpm build`
in this session and seen it exit 0: do not claim completion from reasoning about the code,
and do not call an upgrade safe without that output. Do not conclude why something broke
from a changelog alone - reproduce it. Open a PR but do not merge it.
State which turn you are on at the start of each turn.
Rewrite the Carry-over section before you finish - State gets where the work stands,
Lessons gets at most 3 causal findings, and delete what is no longer true.
Commit once with a one-line summary. Stop after 6 turns even if unmet, and say so.
```

Six clauses, one hole each: objective inside a scope, anchor as the only accepted evidence,
no confidence claim without it, no conclusion from documents alone, state the turn out loud,
rewrite carry-over. Host: Claude Code (recorded in the decisions record) - the objective is
portable, the `/goal` prefix is what changes.

First iteration should produce: the audit output, the version bumps it implies, the anchor
command's real output, and a rewritten Carry-over section.
