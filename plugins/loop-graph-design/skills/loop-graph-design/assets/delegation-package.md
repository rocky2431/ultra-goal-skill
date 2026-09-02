<!--
Template for a cross-vendor graph. Save as `<slug>.delegation.md` next to
`<slug>.decisions.md`. Every worker needs target, mission, and anchor. Two workers minimum
- one worker is a loop, not a graph. Confirm targets with `agent-delegate list --json`
before naming them.
-->

# Delegation: settlement-audit

Star topology: the orchestrator holds all state and every edge passes through it. Workers
do not know about each other and cannot coordinate mid-task, so each mission is
self-contained. Different vendors are the point - identical agents make identical
mistakes, so independence comes from the model, not the prompt.

## Worker: codex

- target: codex
- mission: Audit `src/settlement/` for integer overflow and rounding loss on partial fills. Report each defect with the exact input that triggers it.
- anchor: `forge test --match-path test/Settlement.t.sol`

## Worker: kimi

- target: kimi
- mission: Audit the same module for reentrancy and external-call ordering. Do not report overflow issues; another worker owns those.
- anchor: `forge test --match-path test/Reentrancy.t.sol`

## Orchestration

Delegate both at once, then integrate. Neither worker's report is accepted without its
anchor command's real output; a claim without an exit code is unverified, not confirmed.

Re-delegation costs routing tokens on every round, so budget the number of rounds up front
rather than iterating until the reports agree. Reports that agree may just be two agents
making the same mistake.

## Handoff

```bash
agent-delegate run --to codex --cwd /absolute/repo --task-file /absolute/codex-mission.md
agent-delegate run --to kimi  --cwd /absolute/repo --task-file /absolute/kimi-mission.md
```
