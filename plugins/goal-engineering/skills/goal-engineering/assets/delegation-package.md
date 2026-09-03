<!--
Template for one adversarial-review triad. Save as `<slug>.delegation.md` next to
`<slug>.decisions.md`. Three roles, not N reviewers: a main agent that edits, a reviewer
that reviews the artifact, and a critic that reviews the review. Confirm targets with
`agent-delegate list --json` before naming them.
See references/adversarial-review.md for why the third role is the one that matters.
-->

# Delegation: settlement-audit

Adversarial review over a frozen artifact. The orchestrator is the only role that edits it,
and only after the review has converged. The reviewer and the critic are different vendors on
purpose: agents that share a model share its blind spots, so a same-model critic would mostly
agree - which is the false consensus this protocol exists to break.

## Reviewer

- target: codex
- mission: Review `src/settlement/` for overflow on partial fills, reentrancy, external-call ordering, and gas regressions. Every finding cites file:line and the command whose output proves it. Report "no finding" for a dimension only if you actually exercised it, and name the command you ran.
- anchor: `forge test --match-path test/Settlement.t.sol`
- inputs: the frozen contents of `src/settlement/`, the acceptance criteria above, and the anchor's own output. Not the orchestrator's account of why the code is correct - a reviewer given the author's argument reviews the argument.

## Critic

- target: kimi
- mission: Audit the reviewer's review, not the code. Sort every point into exactly one of agreement, evidence-backed disagreement (cite what shows it), or concern-based disagreement (say what evidence would settle it). Treat any "no finding" that names no command as unexercised rather than clean.
- anchor: `forge test --match-path test/Settlement.t.sol`
- inputs: the reviewer's review and the same frozen source. Not the orchestrator's opinion of the review, and not the reviewer's reasoning about its own confidence.

## Convergence

The artifact stays frozen for the whole inner loop - neither role edits it. The reviewer
answers a disagreement with evidence, never with a rebuttal. At most 5 inner rounds; if round
1 converges with no findings, accept and stop. Only after the review is consistent does the
orchestrator edit, and then a new outer round begins.

## Handoff

```bash
agent-delegate run --to codex --cwd /absolute/repo --task-file /absolute/reviewer-mission.md
agent-delegate run --to kimi  --cwd /absolute/repo --task-file /absolute/critic-mission.md
```

The critic's mission file carries the reviewer's review as its input. Neither report is
accepted without its anchor command's real output: a role's claim of success is a claim, and
the orchestrator runs the anchor itself.

Worker intermediates go in `.goals/.work/` and are not committed. What survives the round is
the event-log line and whatever became a lesson.
