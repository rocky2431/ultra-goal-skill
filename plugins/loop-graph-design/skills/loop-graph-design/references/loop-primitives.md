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

## Host primitives

- **`/goal <text>`** — registers the goal as a stop-time check. The agent cannot end its
  turn while the goal is unmet. `/goal clear` cancels it early. Available in trusted
  workspaces only.
- **`/loop <interval> <prompt>`** — re-runs the prompt on a fixed interval. Omit the
  interval to let the agent pace itself.
- **`/schedule`** — a cron-shaped routine that runs without anyone attached.
- **`Monitor`** — block until a condition holds, instead of polling in a loop.
- **A stop hook** — the mechanical floor under `/goal`: it refuses the end of a turn while
  a named condition is unmet. Reach for it directly when the check must survive a session.

Prefer the host's own primitive over a hand-rolled scheduler. A loop you wrote yourself is
a loop you now maintain, and it will not survive a session restart unless you made it.

## Writing the stop condition

The stop condition is the artifact's load-bearing sentence. Shape it as:

```
Stop when <anchor command> reports <exact threshold>, or after <N> turns.
```

- Anchor command, not a feeling. `pytest -q` exiting 0 is a stop condition; "tests look
  healthy" is not.
- A ceiling, always. Without one, a loop that cannot reach its threshold runs until
  someone notices the bill.
- Quantitative beats qualitative: the more numeric the check, the less the agent has to
  guess whether it is finished.

## Token discipline

- Run deterministic work as a script. Running a script is cheaper than reasoning about it,
  and it produces the same answer twice.
- Do not schedule a routine more often than the thing it watches actually changes.
- Pin the stable part of the prompt — system instructions, the spec, the boundary — at the
  front so the prefix caches. A loop that rebuilds its context in a different order every
  iteration pays full price every iteration; that is the most expensive way to run an agent.
- Match the model to the job rather than defaulting to the largest one for every node.
