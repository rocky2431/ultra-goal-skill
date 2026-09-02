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

Only `package.json` and the lockfile. Never touch application source, CI config, or a
pinned transitive override that carries an explanatory comment. Opening the PR is
authorized; merging it is not.

## Stop condition

Stop when `pnpm audit --audit-level=high` reports 0 findings, or after 6 turns.

## Anchor

```
pnpm test -- --run && pnpm build
```

Green here is the only evidence an upgrade is safe. A passing audit with a failing build
is a failed iteration, not a partial success.

## Verification

Hand the diff to a fresh agent that never saw the upgrade reasoning. It must run the
anchor command itself before it may pass anything, and it fails closed: no output from the
anchor means rejected, not "probably fine".

## Cadence

`/loop 1w` — advisories are published continuously but this codebase absorbs them weekly.
Running it daily costs six extra runs to find the same finding.

## Handoff

Run: `/goal Stop when pnpm audit --audit-level=high reports 0 findings, or after 6 turns.`
First iteration should produce: the audit output, the version bumps it implies, and the
anchor command's result.
