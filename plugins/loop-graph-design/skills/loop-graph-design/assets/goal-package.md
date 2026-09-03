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

Scheduled outside the agent, so this is host-independent: a `cron` entry, `launchd` agent,
systemd timer, or CI `schedule:` trigger invoking the runner. See Handoff.

## Carry-over

Read this before acting; rewrite it before finishing. Delete anything no longer true - Git
keeps the history, this section keeps only what is still the case.

- `@types/node` 22 breaks tsconfig under `moduleResolution: bundler` - do not retry
- `pnpm build` fails on CI without a committed lockfile
- remaining after iteration 6: `packages/api`

## Handoff

Goal mode is enforced by the runner, not by the model: the anchor's exit code decides whether
the goal is met, and the ceiling is a for-loop.

```bash
bash .loops/weekly-dep-upgrade.runner.sh
```

Copy `goal-runner.sh` to `.loops/weekly-dep-upgrade.runner.sh` and fill in SLUG, MAX_TURNS,
ANCHOR, and run_host for whichever host runs this. Then schedule the runner:

```bash
# crontab -e
0 9 * * 1 cd /absolute/repo && bash .loops/weekly-dep-upgrade.runner.sh
```

`launchd`, a systemd timer, or a CI `schedule:` trigger are equivalent. On a host that also
has a goal primitive, layer it on for per-turn self-checking; the runner still decides the run.

**The prompt** - `.loops/weekly-dep-upgrade.prompt.txt`, byte-identical on every host:

```
Read the Carry-over section of .loops/weekly-dep-upgrade.goal.md first.
Then upgrade dependencies within the stated boundary until `pnpm audit --audit-level=high`
reports 0 findings. Run the anchor command before claiming anything.
Rewrite the Carry-over section before you finish, deleting what is no longer true.
Commit once with a one-line summary of this iteration.
```

First iteration should produce: the audit output, the version bumps it implies, the anchor
command's result, and a rewritten Carry-over section.
