---
description: Arm the gate and start a run against a goal artifact in .goals/
argument-hint: <slug>
allowed-tools: Bash, Read
---

Start the run for `$ARGUMENTS`.

This command replaces a host's own goal mode. That mode kept a model working by
re-prompting it; here the Stop hook does that by refusing to let a turn end while the
anchor is red — so the loop is already ours, and what the host's goal mode could never do
is the one step that matters: **arming the gate**.

`$ARGUMENTS` is the one argument placeholder every host documents for command bodies:
Claude Code defines it as "all arguments passed when invoking the skill" (its numbered
shorthands count from zero, so a first argument is not what they mean), zCode as
"$ARGUMENTS stands for all user-provided arguments", Kimi as "whatever you type after the
command replaces $ARGUMENTS in the body". The slug below is therefore bound by the host
before you see this text — never guessed.

## 1. Find the artifact

```bash
ls .goals/$ARGUMENTS.goal.md .goals/$ARGUMENTS.decisions.md
```

If either is missing, stop and say so. Do not author one here — that is the interview's
job, and starting a run against an artifact nobody agreed to is the failure this whole
design exists to prevent.

## 2. Validate before arming

```bash
root="${CLAUDE_PLUGIN_ROOT}"
[ -n "$root" ] || root="${ZCODE_PLUGIN_ROOT:-${KIMI_PLUGIN_ROOT:-${PLUGIN_ROOT}}}"
validator="$root/skills/ultra-goal/scripts/validate_artifact.py"
if [ -f "$validator" ]; then
  python3 "$validator" .goals/$ARGUMENTS.goal.md
else
  printf '%s\n' "ultra-goal: the validator is unreachable from this host's command path - no plugin-root variable reaches command execution here (Kimi's reference documents none; only hook processes receive one). Arming continues, and the run's first report must say the artifact was not machine-validated at arming. The Stop gate still enforces the anchor on every turn."
fi
```

Errors from the validator itself stop the run: an artifact the validator refuses is one
the gate cannot enforce. Advisories are printed and do not stop it. The `else` branch is
a declared degradation, not a skipped step: on a host whose command execution carries no
plugin-root variable, say the validation did not run rather than improvising a path.

## 3. Arm the gate

```bash
printf '%s\n' "$ARGUMENTS" > .goals/active
[ -s .goals/$ARGUMENTS.baseline ] || git rev-parse HEAD > .goals/$ARGUMENTS.baseline 2>/dev/null || printf '%s\n' none > .goals/$ARGUMENTS.baseline
[ -f .goals/.gitignore ] || printf '%s\n' '.work/' 'active' > .goals/.gitignore
```

The second line is not housekeeping. `.goals/.work/` holds the reviewer's and critic's
reports for one round and `.goals/active` is a switch, and the document system says neither
belongs in Git - but saying so is not the same as arranging it, and a run that stages with
`git add -A` commits both. A `.gitignore` **inside** `.goals/` makes the claim true without
touching a file the owner owns.

The `baseline` line records where the run's reviewable change starts, and it is
**write-once**: it is only written when it does not already hold a revision. The run
commits once per turn, so by the time the reviewer is invoked almost everything is already
committed — and a reviewer handed `git diff HEAD` sees only the leftovers and can honestly
report "no findings" on a change it never saw. The reviewer and critic read their diff from
this revision instead. Write-once is what keeps that true across restarts: re-running this
command on an active run must not move the baseline to the current HEAD and hand both
roles an empty range for a real change. It is committed with the run's first turn, so
deleting or rewriting it afterwards shows in `git log`. A deliberate fresh start removes
the baseline (and the events log) by hand; nothing here does it for you. Work that was
already uncommitted when the gate was armed also falls inside the range: the reviewer
attributes it against `## Boundary` rather than guessing.

Until this file names the artifact, **every hook in this plugin does nothing at all** —
which is why a project that never asked for a goal pays nothing, and why this step cannot
be skipped.

## 4. Read the spec, then work

Read `.goals/$ARGUMENTS.goal.md` in full. `## Intent`, `## Boundary`, `## Anchor` and
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
`goal($ARGUMENTS) turn <N>: <one line> [anchor: green|red|unknown]`.

One anchor check is one turn, and a host turn can hold several checks when the gate keeps
the turn alive — so `<N>` is the number in the gate's most recent message, not a number
you count yourself. `--audit` joins your commit subject to the gate's measurements by that
number.

## To stop

```bash
rm .goals/active
```

That disarms the gate without needing the agent's cooperation, and it is the same escape
hatch `LOOP` never had: nothing in this plugin runs again until the marker returns.
