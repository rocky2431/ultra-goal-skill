# Loop primitives

Pick the primitive from **what triggers the loop and what stops it**, not from how
sophisticated it looks. Every one of these runs the same cycle: gather context, take
action, verify the work, repeat.

## The four shapes

| Shape | Trigger | Stops when | Fits |
|---|---|---|---|
| Turn-based | The owner's prompt | The agent judges the task done or needs more context | Short, non-recurring work |
| Goal-based (`/goal`) | Manual, real time | The goal is met **or** the turn ceiling is reached | Anything with a verifiable exit |
| Time-based (`/loop`, `/schedule`) | A time interval | The owner cancels, or the work is finished | Recurring work; watching an external system |
| Proactive | An event or schedule, nobody watching | Each task exits when its goal is met; the routine runs until disabled | Streams of well-defined work: triage, migrations, dependency upgrades |

Goal-based is the default for this Skill. It is the only shape where the owner, not the
agent, owns the definition of "good enough" — which is the whole reason the interview
asks for a quantified stop condition.

**These four are shapes, not commands.** One host happens to expose all of them natively;
most expose a goal at best and none of the others. The shape survives the move — a
time-based loop on a host without a scheduler is an external timer invoking a one-shot run —
so classify by shape first and pick the mechanism from what the host actually has.

## Host primitives

- **`/goal <text>`** — registers the goal as a stop-time check. The agent cannot end its
  turn while the goal is unmet. `/goal clear` cancels it early. Available in trusted
  workspaces only.
- **`/loop <interval> <prompt>`** — re-runs the prompt on a fixed interval. Omit the
  interval to let the agent pace itself.
- **`/schedule`** — a cron-shaped routine that runs without anyone attached.
- **`Monitor`** — block until a condition holds, instead of polling in a loop.
- **A stop hook** — the mechanical floor under a goal check: it refuses the end of a turn
  while a named condition is unmet. Reach for it directly when the check must survive a
  session.

Prefer the host's own primitive when it has one. A loop you wrote yourself is a loop you now
maintain, and it will not survive a session restart unless you made it.

## Goal mode across hosts

Measured on this machine: `/goal` exists on Claude Code, Codex, Kimi, and zCode; no evidence
of it on OpenCode. Only Claude Code has a built-in *scheduler* (`/loop`, `/schedule`), but
that matters less than it sounds - a goal started by hand and left alone covers the same
ground for recurring work, and it is the shape all four hosts share.

Each host's goal mode differs in how it holds the model to the objective: Claude Code refuses
to end the turn, Codex accounts goal progress after every tool call, Kimi can pause and
resume a goal, zCode also offers a headless `--target`. None of that changes the artifact.

**Goal mode is the continuation service, and there is no substitute for it here.** It is what
starts the next turn after one ends. A Stop hook — this Skill's included — runs inside a turn
that is already ending: it can refuse that ending while a completion claim is refusable, but
it cannot schedule a turn and cannot revive a dead process. So where the host has goal mode,
an unattended run uses it; where it does not, the run is not unattended and the report says
the run is awaiting a prompt.

What every host has in common is the gap: **goal mode asks the model whether the objective is
met.** That is the half the anchor closes, in the goal text and in the gate — not by
replacing the host's continuation:

```
/goal <objective, inside <boundary>>. You have not met this goal until you have actually
run `<anchor>` in this session and seen it <exact result>. Do not claim completion from
reasoning. Stop after <N> turns even if unmet, and say so.
```

Two things to keep right when a goal runs unwatched:

- **The ceiling has to be in the text.** Nothing else will refuse to run forever.
- **Carry-over matters even within a single run.** Compaction may retain a summary
  while omitting a decisive fact; recover from the current state and its linked evidence.

## Lessons are reflections, not a log

Reflexion (arXiv 2303.11366) splits the work three ways: an Actor that acts, an Evaluator
that scores, and a Self-Reflection step that turns a sparse signal - a failing test, a red
build - into "nuanced and specific feedback" stored in memory for the next trial. The
reflection step is the one that makes the next attempt different, and it is the one agents
skip by default.

Two ideas transfer to Carry-over, within the experiment's limits:

- **Keep memory selective.** Reflexion's usual capacity of 1–3 was an experimental
  context-budget choice. Here three lessons is advisory: retain a necessary fourth
  lesson or link its detail, and preserve the evidence behind a pruned summary.
- **Amplify the signal into language.** A binary pass/fail carries almost no information for
  the next attempt. The value is in the sentence that says *which action* led to the failure
  and *what to do instead* - what the paper calls the credit assignment problem.

So `### Lessons` asks for a cause and a next action. "The build failed" is the signal.
"The build fails without a committed lockfile because CI runs `--frozen-lockfile` - commit
the lockfile in the same change" is the reflection. Only the second one changes anything.
