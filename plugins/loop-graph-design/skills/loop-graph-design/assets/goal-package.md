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

Roughly weekly, started by hand. Advisories arrive continuously but this codebase absorbs
them weekly, and starting it daily costs six extra runs to find the same finding.

Because it gets started more than once, it needs the Carry-over section below.

## Carry-over

Read this before acting; rewrite it before finishing. Delete anything no longer true - Git
keeps the history, this section keeps only what is still the case.

- `@types/node` 22 breaks tsconfig under `moduleResolution: bundler` - do not retry
- `pnpm build` fails on CI without a committed lockfile
- remaining after iteration 6: `packages/api`

## Handoff

Paste this into the host's goal mode - `/goal` on Claude Code, Codex, Kimi, or zCode; on a
host without goal mode, the same text as a plain prompt:

```
/goal Read the Carry-over section of .loops/weekly-dep-upgrade.goal.md first. Then upgrade
dependencies, touching only package.json and the lockfile, until `pnpm audit
--audit-level=high` reports 0 findings. You have not met this goal until you have actually
run `pnpm test -- --run && pnpm build` in this session and seen it exit 0 - do not claim
completion from reasoning about the code. Open a PR but do not merge it.
Rewrite the Carry-over section before you finish, deleting what is no longer true, and
commit once with a one-line summary. Stop after 6 turns even if unmet, and say so.
```

Three clauses do the work: the objective with its boundary, the anchor as the only accepted
evidence, and the turn ceiling. Host: Claude Code (recorded in the decisions record) - the
objective is portable, the `/goal` prefix is what changes.

First iteration should produce: the audit output, the version bumps it implies, the anchor
command's real output, and a rewritten Carry-over section.
