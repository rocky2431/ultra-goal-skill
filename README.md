# loop-graph-design

An Agent Skill that interviews you into a **grounded** agent loop, then writes the prompt
or script that starts it.

## The problem

"Make an agent keep doing this" is easy to say and hard to make work. The loops that fail
in production fail in the same few ways:

- there is no measurement that cannot be argued with, so the loop cannot tell progress
  from motion;
- the agent decides for itself when the work is good enough, and "good enough" drifts
  toward whatever ends the turn;
- the agent grades its own output, and it praises it;
- work gets split by workflow phase — plan, implement, test — so every handoff loses the
  context the next phase needed;
- agents check each other in a closed circle where everything is consistent and nothing
  is verified.

None of that is fixed by a better framework. It is fixed by answering five questions
before anything runs.

## What it does

1. **Classifies** the work. One question: *can you sketch the whole thing on paper before
   running any of it?* Yes means graph-shaped — routing was decided at authoring time and
   the edges are code. "I'd need to know what step three returns" means loop-shaped —
   routing is decided during inference, every iteration, and billed every time. Topology
   is not the distinction; a loop is a directed cyclic graph. *When the routing decision
   gets made* is the distinction.

2. **Interviews** you, one question per turn, each carrying a recommended answer: intent,
   anchor, stop condition, boundary, verifier, split. It looks up anything the repository
   can answer instead of asking you, and it refuses to emit an artifact with no anchor.

3. **Compiles** one machine-consumable artifact — and stops there. Running it is not this
   Skill's job.

| Shape | Artifact | Consumer |
|---|---|---|
| Loop | `<slug>.goal.md` — the prompt plus cadence | `/goal`, `/loop`, `/schedule` |
| Graph, one vendor | `<slug>.workflow.js` — topology in code | a workflow runtime |
| Graph, several vendors | `<slug>.delegation.md` — one mission per worker | cross-agent delegation |
| Always | `<slug>.decisions.md` — Decision / Rejected / Why | you, next time |

The decisions record holds decisions, not architecture. The script or prompt is the only
description of what the thing does; a prose copy of it goes stale and starts lying.

## Install

```bash
git clone https://github.com/rocky2431/loop-graph-design-skill
cd loop-graph-design-skill
python3 scripts/install_user.py install                 # all supported hosts
python3 scripts/install_user.py install --hosts claude   # or pick them
python3 scripts/install_user.py doctor --json            # verify
```

Hosts: `hermes`, `claude`, `codex`, `kimi`, `zcode`, `opencode`. Installing keeps a
recovery copy and refuses to overwrite an unmanaged Skill of the same name.
`uninstall` removes only copies this installer manages.

The repo also ships a plugin manifest (`.agents/plugins/marketplace.json` and
`plugins/loop-graph-design/.codex-plugin/plugin.json`) for hosts that install plugins
directly from a Git marketplace.

## The validator

```bash
python3 scripts/validate_artifact.py .claude/workflows --json
```

It observes facts and nothing else: file pairing, required sections, `meta` being a pure
literal and the first statement, phases declared before use, delegation targets that are
actually registered, and JavaScript syntax. It never edits an artifact and it never judges
whether a topology is the right one — that part is the design, and design belongs to you
and the model, not to a template engine.

Its silence is not evidence that the design is right.

## Scope

This Skill produces **executable artifacts**. Designing an agent's authority model, tool
schemas, or approval boundaries is a different job — see
[agent-harness-design](https://github.com/rocky2431/agent-harness-design-skill). Handing a
single mission to another agent now is
[agent-delegate](https://github.com/rocky2431/agent-delegate-skill).

## Sources

The guidance traces to primary sources, listed with URLs and a currency date in
[references/research-basis.md](plugins/loop-graph-design/skills/loop-graph-design/references/research-basis.md).
Anthropic's loop and multi-agent engineering posts are treated as doctrine; the July 2026
"graph engineering" essays are treated as argument.

## Tests

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

42 tests: the validator's rules, the package surface, version consistency across three
files, every relative link in `SKILL.md` resolving, and the shipped templates passing the
shipped validator.

## License

MIT
