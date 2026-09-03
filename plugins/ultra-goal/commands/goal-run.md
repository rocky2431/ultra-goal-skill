---
description: Arm the gate and start a run against a goal artifact in .goals/
argument-hint: <slug>
allowed-tools: Bash, Read
---

Start the run for `$1`.

This command replaces a host's own goal mode. That mode kept a model working by
re-prompting it; here the Stop hook does that by refusing to let a turn end while the
anchor is red — so the loop is already ours, and what the host's goal mode could never do
is the one step that matters: **arming the gate**.

## 1. Find the artifact

```bash
ls .goals/$1.goal.md .goals/$1.decisions.md
```

If either is missing, stop and say so. Do not author one here — that is the interview's
job, and starting a run against an artifact nobody agreed to is the failure this whole
design exists to prevent.

## 2. Validate before arming

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/ultra-goal/scripts/validate_artifact.py" .goals/$1.goal.md
```

Errors stop the run: an artifact the validator refuses is one the gate cannot enforce.
Advisories are printed and do not stop it.

## 3. Arm the gate

```bash
printf '%s\n' "$1" > .goals/active
```

Until this file names the artifact, **every hook in this plugin does nothing at all** —
which is why a project that never asked for a goal pays nothing, and why this step cannot
be skipped.

## 4. Read the spec, then work

Read `.goals/$1.goal.md` in full. `## Intent`, `## Boundary`, `## Anchor` and
`## Means`'s labels are frozen: if one of them turns out to be wrong, stop and write a row
under `## Challenges from the run` in the decisions record rather than editing it.

Then follow `## Roles` for who does what this turn, `## Acceptance` for what is still not
true, and `### Next` for the one objective this round is aimed at.

**You are the run, not its designer.** The terms were agreed before you started; do not
reopen them as an interview.

At the start of each turn, state which turn you are on, which `## Acceptance` lines this
turn is for, and what output would prove them — before changing anything.

You have not met this goal until you have actually run the command in `## Anchor` and seen
it succeed in this session. Report the turn and the exit code you saw rather than
summarising them. Rewrite `## Carry-over` before you finish, `### Next` included, and
commit as
`goal($1) turn <N>: <one line> [anchor: green|red|unknown]`.

## To stop

```bash
rm .goals/active
```

That disarms the gate without needing the agent's cooperation, and it is the same escape
hatch `LOOP` never had: nothing in this plugin runs again until the marker returns.
