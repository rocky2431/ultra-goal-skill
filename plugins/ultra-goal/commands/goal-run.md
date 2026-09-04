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

## 2. Validate, then arm - one fence, because they are one step

```bash
root="${CLAUDE_PLUGIN_ROOT}"
[ -n "$root" ] || root="${ZCODE_PLUGIN_ROOT:-${KIMI_PLUGIN_ROOT:-${PLUGIN_ROOT}}}"
[ -n "$root" ] || root="${KIMI_CODE_HOME:-$HOME/.kimi-code}/plugins/managed/ultra-goal"
validator="$root/skills/ultra-goal/scripts/validate_artifact.py"
if [ ! -f "$validator" ]; then
  printf '%s\n' "ultra-goal: arming refused - no documented plugin root reaches this command, so the artifact cannot be machine-validated, and an unvalidated artifact is one the gate cannot honestly enforce. This is a refusal, not a downgrade. Validate it by hand from the plugin's install root (Kimi manages installs at ${KIMI_CODE_HOME:-$HOME/.kimi-code}/plugins/managed/ultra-goal; Codex at ~/.codex/plugins/cache/<marketplace>/ultra-goal/<version>): python3 <plugin-root>/skills/ultra-goal/scripts/validate_artifact.py .goals/$ARGUMENTS.goal.md. Fix what it reports, then either export PLUGIN_ROOT=<plugin-root> for this session's shell and run this command again, or - once it is clean - arm by hand: echo $ARGUMENTS > .goals/active"
  exit 1
fi
python3 "$validator" .goals/$ARGUMENTS.goal.md || exit 1
printf '%s\n' "$ARGUMENTS" > .goals/active
[ -s .goals/$ARGUMENTS.baseline ] || git rev-parse HEAD > .goals/$ARGUMENTS.baseline 2>/dev/null || printf '%s\n' none > .goals/$ARGUMENTS.baseline
[ -f .goals/.gitignore ] || printf '%s\n' '.work/' 'active' '*.candidate' > .goals/.gitignore
```

Validation is a hard precondition of arming, and the fence is shaped to make
that mechanical rather than aspirational:

- **One fence, not two.** Round 2 shipped validation and arming as separate
  steps, so anything that ran the second could skip the first - and when no
  plugin root reached the command, the unreachable branch even announced that
  arming would continue, letting an artifact the validator would refuse arm
  the gate (Codex round-2 F1). Here the validator's error stops the script
  with `|| exit 1` before `.goals/active` is written: no prose to obey, no
  second fence to jump to. Errors stop the run; advisories print and do not.
- **The candidate roots are each documented**, in order: the four
  plugin-root variables (Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}` in
  command content per its plugin reference; `${ZCODE_PLUGIN_ROOT}` and
  `${KIMI_PLUGIN_ROOT}` exist for hook processes and are read where a host's
  tool shell inherits them; `PLUGIN_ROOT` is Codex's hook-process name), then
  Kimi's managed-install default - local installs are copied to
  `$KIMI_CODE_HOME/plugins/managed/<id>/` (default `~/.kimi-code`), and this
  plugin's id is `ultra-goal` - which is what keeps Kimi's primary path
  usable: it validates for real, against the same copy its hooks run from.
- **Where nothing reaches, arming refuses** and says what the owner does
  instead: validate by hand from the install root, then re-run with
  `PLUGIN_ROOT` exported or arm by hand. Kimi's and Codex's references
  document no root variable for command bodies at all, and zCode's documents
  `$ARGUMENTS` only - so on those hosts this branch is the honest outcome,
  not a bug to improvise around. Do not invent a path the references do not
  name.

The last three lines are not housekeeping, and they only run after the
validator passed:

- `.goals/.work/` holds the reviewer's and critic's reports for one round
  and `.goals/active` is a switch, and the document system says neither
  belongs in Git - but saying so is not the same as arranging it, and a run
  that stages with `git add -A` commits both. A `.gitignore` **inside**
  `.goals/` makes the claim true without touching a file the owner owns.
- The `baseline` line records where the run's reviewable change starts, and
  it is **write-once**: it is only written when it does not already hold a
  revision. The run commits once per turn, so by the time the reviewer is
  invoked almost everything is already committed — and a reviewer handed
  `git diff HEAD` sees only the leftovers and can honestly report "no
  findings" on a change it never saw. The reviewer and critic read their
  diff from this revision instead. Write-once is what keeps that true
  across restarts: re-running this command on an active run must not move
  the baseline to the current HEAD and hand both roles an empty range for a
  real change. It is committed with the run's first turn, so deleting or
  rewriting it afterwards shows in `git log`. A deliberate fresh start
  removes the baseline (and the events log) by hand; nothing here does it
  for you. Work that was already uncommitted when the gate was armed also
  falls inside the range: the reviewer attributes it against `## Boundary`
  rather than guessing.

Until the marker is written, **every hook in this plugin does nothing at
all** — which is why a project that never asked for a goal pays nothing, and
why this step cannot be skipped. The marker holds the slug alone; the first
Stop that carries a session identity adds a `session <id>` line claiming the
run for this session, and every hook then ignores other sessions working in
the same directory. That line is ownership information, not a key — removing
it re-opens the claim.

## 3. Read the spec, then work

Read `.goals/$ARGUMENTS.goal.md` in full. `## Intent`, `## Boundary`, `## Anchor` and
`## Means`'s labels are frozen: if one of them turns out to be wrong, stop and write a row
under `## Challenges from the run` in the decisions record rather than editing it. You may
raise a challenge; you may not edit the term or treat your own challenge as an owner's
ruling — a moved goalpost closes the run and disarms the gate, and only the owner reopens.

Then follow `## Roles` for who does what this turn, `## Acceptance` for what is still not
true, and `### Next` for the one objective this round is aimed at.

**Results are made visible before the Stop, not after.** An allow from the gate carries
no model context — on Claude Code an injected "one more thing" would keep the turn
alive instead of ending it, so the gate stopped carrying one — and the next injectable
event is best-effort recovery that some turns never fire. That makes two habits
load-bearing, and they are yours, not the hook's:

- After a relevant change, when you need feedback or are preparing completion, run the
  applicable verification with ordinary tools — the tests this change touches, the real
  path this change claims to fix. Not the full suite every iteration: the applicable
  check for the change at hand.
- Before you end any turn: make this turn's important results visible in the ordinary
  tool output above, and write the durable state — `## Carry-over` rewritten, `### Next`
  re-aimed, the work committed. What is only in your context when the turn ends is gone.

When you invoke a reviewer or critic, **the round's evidence is the file the role was
told to write** (`.goals/.work/$ARGUMENTS-review.md`, `-critique.md`) — never the call's
exit status. A delegation can return success and produce nothing; it happened to a review
round on this project, and no hook can see it, because the failure event fires on
failures only. So check the file exists before you treat the round as done: if it is
absent, the round did not happen — fall back as `## Roles` declares and say the round ran
degraded in your report. A review that returned success and left nothing is a missing
review, not a pass. Wait for every delegated role you invoked to finish before you claim
completion: the gate refuses a claim while a role's failure is the event log's last word
for the turn.

**You are the run, not its designer.** The terms were agreed before you started; do not
reopen them as an interview.

At the start of each turn, state which turn you are on, which `## Acceptance` lines this
turn is for, and what output would prove them — before changing anything.

## Claiming completion

You have not met this goal until the anchor says so on the current state — and the
anchor's verdict at completion belongs to the gate, not to you. So when you believe the
goal is met:

1. Run the command in `## Anchor` yourself with ordinary tools and read its output. You
   are claiming a state of the world; look at it first.
2. Write `.goals/$ARGUMENTS.candidate` — one short line naming what you claim (which
   `## Acceptance` lines, at what evidence). The claim is yours and self-reported: it
   triggers the gate's check and grants nothing.
3. End your turn.

The gate consumes the claim, executes the anchor once against the current state, and
rules on that measurement alone. Green proves the anchor exited 0 on this state — whether
that satisfies the stop condition stays with you and the owner, so report the attempt
number, the exit code, and what a green does not cover. Red refuses the claim and the
turn continues; a failed role this turn refuses it before the anchor even runs. A
historical green is never a pass input: new work and a new claim are re-measured, always.

Commit an attempt the gate has measured as
`goal($ARGUMENTS) turn <N>: <one line> [anchor: green|red|unknown]`; ordinary work turns
commit as `goal($ARGUMENTS): <one line>`. One completion attempt is one `<N>` — the
number in the gate's most recent message, not a number you count yourself — and
`--audit` joins your commit subject to the gate's measurements by it. Ordinary turns
carry no `[anchor: ...]` verdict: nothing measured one.

When you report how the run stands, use the disposition vocabulary and nothing looser:
`in_progress`, `input_required` (you lack something only the owner can give),
`blocked_retryable` (a failure that time or a retry can clear), `budget_exhausted` (the
ceiling or the denial bound is spent), `unachievable` (only with independent evidence
that the goal contradicts its frozen terms — a feeling of impossibility is
`in_progress` with a challenge row), `completed`, `canceled`. The anchor's colour is a
different axis: green, red and unknown are what one command did, not what the run is.

## To stop

```bash
rm .goals/active
```

That disarms the gate without needing the agent's cooperation, and it is the same escape
hatch `LOOP` never had: nothing in this plugin runs again until the marker returns.
