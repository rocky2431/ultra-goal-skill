<!--
Example of one optional adversarial-review triad. Save as `<slug>.delegation.md` next to
`<slug>.decisions.md`. Here a main agent edits, a reviewer reviews the artifact and a
critic reviews the review. Adapt the roles and use the current host's available tools.
If choosing an installed agent-delegate bridge, confirm its registered targets with
`agent-delegate list --json` before naming them. The bridge is optional.
See references/adversarial-review.md for why the third role is the one that matters.
-->

# Delegation: settlement-audit

goal: `settlement-audit.goal.md`

This execution attachment inherits the shared goal's authority, acceptance and
verification contract. Arm that goal before running; worker calls do not replace
its completion check. Adapt the optional review protocol to the goal's needs.

Adversarial review over a frozen artifact. In this example the orchestrator edits it
only after the review exchange. The reviewer and critic use different vendors as a
possible source of differing observations; vendor diversity is not evidence of
independence or correctness. Each judgment still needs the original facts.

## Reviewer

- target: codex
- mission: Review `src/settlement/` for overflow on partial fills, reentrancy, external-call ordering, and gas regressions. Every finding cites file:line and the command whose output proves it. Report "no finding" for a dimension only if you actually exercised it, and name the command you ran.
- anchor: `forge test --match-path test/Settlement.t.sol`
- inputs: `.goals/settlement-audit.goal.md`, the frozen contents of `src/settlement/`, and the anchor's own output. Follow the shared goal's boundary and acceptance. Not the orchestrator's account of why the code is correct.

## Critic

- target: kimi
- mission: Audit the reviewer's review, not the code. Sort every point into exactly one of agreement, evidence-backed disagreement (cite what shows it), or concern-based disagreement (say what evidence would settle it). Treat any "no finding" that names no command as unexercised rather than clean.
- anchor: `forge test --match-path test/Settlement.t.sol`
- inputs: `.goals/settlement-audit.goal.md`, the reviewer's review and the same frozen source. Follow the shared goal's boundary and acceptance. Not the orchestrator's opinion of the review, and not the reviewer's reasoning about its own confidence.

## Convergence

The artifact stays frozen for the whole inner loop - neither role edits it. The reviewer
answers a disagreement with evidence, never with a rebuttal. This example allows at
most 5 inner rounds; if round 1 converges with no findings, accept and stop. Choose
the actual repeated-review cap and native budget during setup, retaining room for
integration, required verification and delivery. No new allowance is created here.

A worker's report ends in exactly one named outcome, so that a blocked worker and a finished
one cannot look alike:

- **completed** - the mission was carried out and the anchor's output is attached.
- **failed** - it was attempted and did not work; say what was tried.
- **input-required** - it cannot proceed without something specific; name that thing. This
  is a paused mission with an explicit unanswered question, not a successful result.
- **rejected** - the mission is outside what this worker should do; say why. A worker that
  declines loudly is worth more than one that improvises.

Silence is none of these. A worker that returns nothing is **unconfirmed**. Inspect
its native task, process or delegation receipt before deciding: it may be running,
finished with a lost reply, failed, or waiting for input. Use `input-required` only
for an actual question or explicit native waiting-for-input state. If inspection
is unavailable, retain unknown and its readback/retry condition; do not invent a
question for the owner. Only after the review is consistent does the orchestrator
edit, and then a new outer round begins.

## Handoff

Use the host's supported worker tools or an installed bridge. Give each worker the
accepted goal and a self-contained mission; it does not need this Skill installed.
The commands below illustrate a registered Claude caller with Codex and Kimi targets.
Replace caller, targets and paths with the actual available identities and resources.
First bridge calls must supply `--caller`; nested calls preserve the received chain.

```bash
agent-delegate run --to codex --caller claude --cwd /absolute/repo --task-file /absolute/reviewer-mission.md
agent-delegate run --to kimi  --caller claude --cwd /absolute/repo --task-file /absolute/critic-mission.md
```

When the bridge is missing, use another available path that meets the same contract;
do not copy or install a runtime merely to execute this example. Ordinary work can
return to the main session. A required independent review still needs an accepted
independent verifier and its receipt; an unavailable verifier cannot become self-review.

The critic's mission file carries the reviewer's review as its input. Neither report is
accepted without its anchor command's real output: a role's claim of success is a claim, and
the orchestrator runs the anchor itself.

Worker scratch may go in `.goals/.work/`. The required receipt defaults to
`.goals/settlement-audit.review.json`; keep it and the gate's corresponding
`.goals/settlement-audit.reviews/` archives after the round. Retain other necessary
original evidence before cleaning scratch. An event hash and a lesson cannot
reconstruct a deleted review. Commit or publish only under existing authority.

If adapting this attachment to parallel implementation, name each worker's actual
files/resources, shared interfaces and integration owner. Different artifact names
do not isolate shared writes. Join the writers and check the integrated state before
the independent review and final verification.
