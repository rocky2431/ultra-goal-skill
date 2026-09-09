# Pi host support

## Load the package

From a local source checkout, add the plugin directory as a Pi package:

```bash
pi install /absolute/path/to/ultra-goal-skill/plugins/ultra-goal
```

This registers its Skills, the `goal-run` prompt and the TypeScript extension.
Restart Pi or use `/reload`. Use `/skill:ultragoal` to prepare a goal. Loading
only the Markdown Skill does not enable automatic verification or recovery.
For an isolated test without changing package settings, use
`pi --extension <plugin-root>/pi/extension.ts --skill <plugin-root>/skills/ultragoal`.

The extension uses Pi's bundled `typebox` and standard Node modules, plus the
existing Python scripts. Python 3.10+ must be available as `python3`; set
`ULTRA_GOAL_PYTHON` to another Python executable when needed. No companion Skill,
MCP server, or new goal engine is required.

## Identity and execution

`ultra_goal` is a native tool with these actions:

| Action | Inputs | Behavior |
|---|---|---|
| `session` | None | Return this Pi session's actual ID for worker/reviewer receipts |
| `arm` | `slug`, optional `allowNoGit` | Validate the accepted contract and bind this native session |
| `rebind` | `slug` | Explicitly recover an authorized goal into this session |
| `verify` | `slug`, nonempty `claim` | Run the existing frozen evaluator/review checks and return the measured result |
| `diff` | `slug` | Show the runner's baseline diff |
| `disarm` | `slug` | Disable this goal's hooks, retaining its evidence |

The extension supplies `ctx.sessionManager.getSessionId()` and `ctx.cwd` to the
runner. It never selects an inherited Codex/Claude session variable. A fork/new
session cannot claim the previous session's goal merely by opening its directory.
Arming/rebinding still follows the accepted contract and existing authority;
the extension cannot approve a goal on the owner's behalf.

## Lifecycle mapping

| Pi event | Existing behavior |
|---|---|
| `session_start`, `before_agent_start` | Recover the owning goal's frozen terms and Carry-over |
| `session_before_compact`, `session_compact` | Record compaction, refresh recovery for subsequent model context |
| `context` | Inject current recovery for the owning session only |
| `input` from interactive/RPC | Record a new user prompt; extension follow-ups do not reset its correction bound |
| `tool_result` for `bash` | Feed existing direct-delegation observation hooks |
| `agent_end` after a normal assistant stop | Consume an explicit candidate through the same verification gate |

A rejected candidate can enqueue **one corrective follow-up per user prompt**
through `pi.sendMessage(..., {deliverAs: "followUp", triggerTurn: true})`.
This is the adapter's bound, not a claimed Pi native limit. The owner's completion
attempt ceiling still applies. Ordinary stops without a candidate do not launch
another turn. Aborted/error runs and pending user messages do not trigger a
correction. Resume/reload cannot by itself restart a stopped process.

Prefer the explicit `verify` tool for a machine-readable verdict, including in
headless/RPC use. Pi's `agent_end` callback cannot retract text already streamed
to a client; it can verify a candidate and request correction. Tool-level failures
remain errors, and hook failures remain fail-open without claiming verification.

On cancellation, interrupt Pi and disarm the goal using existing authority.
Disarming does not terminate spawned processes. With no selected/owned goal,
hooks remain silent. `ULTRA_GOAL_HOOKS_DISABLED=1` disables recovery and callbacks.

## Verification and limits

The opt-in test loads the extension through the installed Pi loader and exercises
the Python gate with local fixtures; it makes no provider calls:

```bash
ULTRA_GOAL_TEST_PI_SDK=/absolute/path/to/node_modules/@earendil-works/pi-coding-agent \
  python3 -m unittest discover -s tests -p test_pi_extension.py -v
```

It checks session isolation, compacted recovery, canceled-run silence, rejected
candidate correction and its bound, and successful explicit verification. It
does not certify arbitrary long-running goals, reviewer teams, all providers,
or Windows native lifecycle behavior. Independent Pi workers can use their native
CLI as described in [agent-modes.md](agent-modes.md#pi-independent-workers).

References (checked 2026-09-09 against local Pi 0.85.1):
- [Pi Extensions](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md)
- [Pi Packages](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/packages.md)
- [Pi RPC](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/rpc.md)
