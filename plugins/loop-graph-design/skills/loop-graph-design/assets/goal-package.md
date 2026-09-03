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

Weekly. Advisories arrive continuously but this codebase absorbs them weekly, and running it
daily costs six extra runs to find the same finding.

Host: Claude Code, so `/loop 1w`. On a host with no built-in scheduler this becomes a `cron`
entry invoking that host's one-shot command - see Handoff. Nothing else in this file changes.

## Carry-over

Read this before acting; rewrite it before finishing. Delete anything no longer true - Git
keeps the history, this section keeps only what is still the case.

- `@types/node` 22 breaks tsconfig under `moduleResolution: bundler` - do not retry
- `pnpm build` fails on CI without a committed lockfile
- remaining after iteration 6: `packages/api`

## Handoff

The prompt is the same on every host; only the way it gets started differs.

**With a built-in loop command** (Claude Code):

```
/loop 1w <the prompt below>
```

**Without one** (Kimi, OpenCode, zCode - none of them has a scheduler), schedule it outside
the agent and invoke the host's one-shot command:

```
# crontab -e
0 9 * * 1 cd /absolute/repo && kimi -p "$(cat .loops/weekly-dep-upgrade.prompt.txt)"
```

`launchd`, a systemd timer, or a CI `schedule:` trigger all work the same way. zCode can
also carry the goal itself with `--target`.

**The prompt:**

```
Read the Carry-over section of .loops/weekly-dep-upgrade.goal.md first.
Then upgrade dependencies within the stated boundary until `pnpm audit --audit-level=high`
reports 0 findings, or 6 turns pass. Run the anchor command before claiming anything.
Rewrite the Carry-over section before you finish, deleting what is no longer true.
Commit once with a one-line summary of this iteration.
```

First iteration should produce: the audit output, the version bumps it implies, the anchor
command's result, and a rewritten Carry-over section.
