# UltraGoal

[English](README.md) · [简体中文](README.zh-CN.md)

UltraGoal helps coding agents turn an open-ended request into a goal with clear
acceptance criteria, permission boundaries and a way to check the result. The
agent can then work through the task, keep its progress in files and ask for
input when a decision falls outside the agreed terms.

It runs inside Claude Code, Codex, Kimi Code or zCode as a Skill with Python
scripts and hooks. A hook is a script the host calls at an event such as the end
of a turn. The host provides the model, tools and continued execution; UltraGoal
provides the goal definition and verification procedure.

Use it for work that needs several rounds of investigation, implementation and
review. For a small one-off task, the agent can handle the request directly.

Version: 2.15.5. Core scripts require Python 3.10 or later.

- [Install and start](#install-and-start)
- [Your first goal](#your-first-goal)
- [How a goal runs](#how-a-goal-runs)
- [Files and progress](#files-and-progress)
- [Current limits](#current-limits)
- [Documentation](#documentation)
- [Development](#development)

## Install and start

You need a coding agent that can load Skills and run Python. To use automatic
verification at the end of a turn, it must also load the plugin's hooks.

### Claude Code

```bash
claude plugin marketplace add rocky2431/ultra-goal-skill
claude plugin install ultra-goal@ultra-goal
```

### Codex

```bash
codex plugin marketplace add rocky2431/ultra-goal-skill
codex plugin add ultra-goal@rocky-ultra-goal
```

The plugin includes the main Skill, the `goal-run` command, review roles and the
host's hook configuration. Reload plugins or start a new session, then check
that the components appear in your host. Enable one copy of the hooks to avoid
duplicate callbacks.

### Kimi Code and zCode

Adapters are included in `plugins/ultra-goal`: `kimi.plugin.json` for Kimi Code
and `.zcode-plugin/plugin.json` for zCode. Load that directory through the native
plugin facility in your installed build. Installation interfaces vary; some Kimi
distributions do not provide a `kimi plugin` CLI command.

The host must load both the manifest and its hooks for the verification hook to
run. See the [hook coverage table](docs/usage.md#hooks-and-host-coverage) for the
events each adapter registers.

### Local copy

The Kimi Code and zCode plugin loaders use a local package directory. Clone this
repository and enter it:

```bash
git clone https://github.com/rocky2431/ultra-goal-skill.git
cd ultra-goal-skill
```

### Native plugin entries

| Host | Main Skill entry |
|---|---|
| Claude Code | `/ultra-goal:ultragoal` |
| Codex | `$ultragoal` |
| Kimi Code | `/skill:ultragoal` |
| zCode | Select `ultragoal` in its Skill picker |

`ultra-goal` remains the plugin package ID. Claude writes plugin entries as
`<plugin>:<skill>`, which is why its command contains both names. UltraGoal does
not install separate user commands or forwarding Skills.

Kimi Code user installs honor `KIMI_CODE_HOME` (default `~/.kimi-code`),
including the `skills` subdirectory. The legacy Python CLI directory `~/.kimi`
is not migrated or deleted. See [Kimi Skill discovery](https://www.kimi.com/code/docs/kimi-code-cli/customization/skills.html).

## Your first goal

Open your coding agent in the project you want it to work on. Ask it to use
UltraGoal, either in plain language or through the main Skill entry:

> Use UltraGoal to turn this into an executable goal: make the CSV export usable
> by our operations team. Investigate what already exists, ask me only the
> material decisions, and show me the complete acceptance and authority contract.

The agent checks the project and any existing goals. It asks about unresolved
choices one at a time, then prepares the goal for you to review. You agree on:

- What the finished result must do and how to check it.
- Which files and external systems the agent may change.
- Which requirements must remain fixed and which methods it may replace.
- When it should stop, including attempt limits and any required independent review.

For a goal named `export-ready`, the agent writes the agreement to
`.goals/export-ready.goal.md` and records decisions in
`.goals/export-ready.decisions.md`. After you confirm the terms, the agent offers
to start. If you have already authorized execution, it can begin without another
prompt.

To start an already agreed goal on a host with the packaged slash command, use:

```text
/ultra-goal:goal-run export-ready
```

If your host does not expose that command, ask the agent to follow the
[run procedure](plugins/ultra-goal/commands/goal-run.md) for the existing goal.
Both goal files must be present before it starts.

## How a goal runs

1. The agent reads the agreed goal and chooses the next useful action. It may
   change methods within the permissions you gave it.
2. It does the work itself or assigns a bounded task through the host's
   delegation tools. It checks a worker's actual output before using the result.
3. It saves current facts, lessons and the next action in the goal file, then
   continues from that state.
4. Before reporting completion, it requests verification. The verification script runs the
   agreed check, called the **Anchor**, and validates any required review evidence.
   A passing result must refer to the current work.

You decide the outcome; the agent chooses how to reach it within the agreement.
Changes to success criteria, required methods, permissions or budgets need your
approval. It can resolve repository facts and ordinary implementation choices
without asking you again.

The same goal can drive a loop, where the agent chooses the next step during
execution, or a graph, where routes are written in advance. Both use the same
acceptance and authority contract. Execution comes from the host; UltraGoal does
not bundle a separate Agent Runtime or workflow engine.

## Files and progress

Each project keeps its goals in `.goals/`. For a goal named `export-ready`, the
main files are:

| File | Contents |
|---|---|
| `export-ready.goal.md` | Agreed requirements, verification rules and current progress |
| `export-ready.decisions.md` | Decisions, rejected alternatives and who made each choice |
| `export-ready.events.jsonl` | Observations recorded by verification and hook scripts |
| `active` | The goal and native session currently bound to the hooks |

The agent maintains the progress sections: `State` for current facts, `Lessons`
for what should affect the next decision, and `Next` for where to resume.
Scripts maintain verification records, baselines and review archives. See
[file maintenance](docs/usage.md#files-and-their-maintenance) for the complete list.

You can ask the agent to inspect progress or explain why a run stopped. For
manual status checks, session recovery and cancellation, follow the
[usage guide](docs/usage.md). Canceling a run requires stopping both the host's
native goal and UltraGoal's active binding.

## Current limits

Continued execution depends on the host's native goal mechanism and budgets.
A Stop hook runs when a turn ends; it cannot wake a closed agent. An ordinary
Stop without a completion claim does not run the Anchor. The agent should call
`verify` before its final answer so it can report the result in that answer.

The model is responsible for asking useful questions, choosing methods, saving
state and following the verification procedure. Scripts check explicit claims;
they cannot catch every unsupported statement or authenticate identities stored
in shared files. Timeouts, unavailable checks and exhausted budgets leave a goal
unverified.

The package includes four host adapters, but full unattended execution across
all four hosts and Windows lifecycle behavior remain unverified. See
[remaining validation scope](docs/wip/outstanding.md) before relying on a host
for unattended work.

## Documentation

- [Usage guide](docs/usage.md): task delegation, feedback, hooks, verification,
  recovery and troubleshooting. [简体中文](docs/usage.zh-CN.md).
- [Goal contract](plugins/ultra-goal/skills/ultragoal/references/goal-contract.md):
  fields, acceptance coverage and review receipts.
- [Skill instructions](plugins/ultra-goal/skills/ultragoal/SKILL.md): the procedure
  loaded by the agent.
- [Research basis](plugins/ultra-goal/skills/ultragoal/references/research-basis.md):
  prior work and the design choices it informed.

## Development

The scripts and test suite use the Python standard library. Run the checks from
the repository root:

```bash
python3 -m unittest discover -s tests -v
```

The suite covers goal validation, session binding, verification, interruption
recovery, retained evidence and packaging. These checks complement the host
lifecycle probes described in the [usage guide](docs/usage.md#validation-and-limits).

## License

[MIT](LICENSE).
