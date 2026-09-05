---
name: ultra-goal
description: "Turn \"make an agent keep doing this\" into a goal a host will hold to: interview for intent, anchor, stop condition, boundary, droppable means, roles and an adversarial verifier, refuse the shapes that fail, then emit the artifact - a goal package to start with /ultra-goal, a workflow script, or a cross-vendor delegation triad. Runnable, not a design note."
when_to_use: "When the owner wants work to keep running without them - \"make an agent keep doing this\", \"turn this into something that runs itself\", \"set up a loop for\", \"have it keep going until\" - or wants to inspect or change a goal already in .goals/. Not when a goal is already running and the request is a step of that work: that is the run doing its job."
license: MIT
metadata:
  author: rocky2431
  version: "2.15.1"
---

# UltraGoal

Turn the owner's objective into an executable goal they can start and leave running.
The goal is the invariant; loop and graph differ in **when routing gets decided**.
This skill defines the goal and hands it to the host. The host supplies execution,
continuation, permissions and resource controls.

**One goal contract, whatever the execution shape.** Every run owns
`.goals/<slug>.goal.md` and `<slug>.decisions.md`. A workflow or delegation package
is an optional attachment to that same contract. The model may change strategy,
workers and carried state within the accepted terms; it may not make success easier.

## Keep activation scoped

Use this skill to create, inspect or modify an executable goal package, workflow
script or delegation package. An ordinary task or a broader authority-model question
needs its own answer, not a goal interview. Assume no other Skill is installed.

## Recognize the intent first

| Intent | Signal | Action |
|---|---|---|
| **Create** | The owner wants to set up autonomous work | Interview, compile and validate below |
| **Modify** | The request changes an existing goal's terms | Read the goal and decisions; use Modify below |
| **Inspect** | The owner asks what exists, what ran or why it stopped | Use Inspect below; change nothing |
| **Executing** | A pasted goal line or a work step under an active goal | **Do not activate.** Do the work the goal asks for |
| **Not a loop** | A one-shot task or an answer | Do the requested work directly |

If `.goals/` has artifacts, **run the status command before the first question**.
An existing goal covering the request may make it Modify, not Create. State alone
is not the decision: changing its ceiling is Modify; upgrading its next package is
Executing. When uncertain, do the requested work rather than reopening an interview.
If missing goal terms materially hindered that work, name the missing term once.

## Read only what this stage needs

- **Creating or changing terms:** read [goal-contract.md](references/goal-contract.md)
  before writing an artifact. It owns the schema, criterion counterexamples,
  independent-review receipt and completion contract.
- **Choosing delegation or review:** read [agent-modes.md](references/agent-modes.md).
  For a chosen reviewer/critic exchange, also read
  [adversarial-review.md](references/adversarial-review.md). Its packaged role calls
  are `/ultra-goal:review <slug>` and `/ultra-goal:critic <slug>`.
- **Authored routing:** read [graph-topology.md](references/graph-topology.md).
  For trigger or scheduling choices, read [loop-primitives.md](references/loop-primitives.md).
- **Starting or resuming:** switch to [goal-run.md](../../commands/goal-run.md).
  Read [host-hooks.md](references/host-hooks.md) only to resolve a host capability,
  hook refusal or lifecycle limitation.
- **Recovery, evidence retention or a longer execution plan:** read
  [document-system.md](references/document-system.md). An unknown external effect
  also requires the recovery procedure in [goal-contract.md](references/goal-contract.md).
- **Changing the skill from accumulated experience:** use the tested-promotion
  procedure in [evolution-and-scope.md](references/evolution-and-scope.md).
  Ordinary goal execution does not need that maintenance procedure.

Do not preload all references. Read [anti-patterns.md](references/anti-patterns.md),
[zero-trust.md](references/zero-trust.md) or
[research-basis.md](references/research-basis.md) when a concrete design question
needs their failure analysis, control limits or source evidence.

## Interview protocol

- **Facts are yours, decisions are theirs.** Resolve repository, test, CI and
  standing-instruction facts first. Probe only unknowns that could change the goal;
  stop when resolved. Init is not permission to complete an unconfirmed deliverable.
- Ask only unresolved material owner decisions. The decisions below are **not nine
  mandatory turns**. **One question per turn**; each question **carries your
  recommended answer** and what would change it. Reuse explicit owner answers.
- **Definitions come from the vendor's reference documentation.** Examples and local
  probes show a supported case, not the full host contract. Check the actual session.
- Preserve the owner's material words and clarifications verbatim in `## Intent`,
  separately from your operational interpretation; include a source locator when
  available. Do not invent a quotation or substitute your summary for their request.
- Keep confirmed decisions in `<slug>.decisions.md` as you go. That record is also
  the interview's progress: recover from it instead of restarting the interview.

Before freezing, test both **false acceptance** (all checks pass but the owner's
request remains unsatisfied) and **false rejection** (a valid result fails an
unrequested method constraint). Use the original request. A correct one-off result
need not have a pipeline unless repeatability was required; file existence does
not prove readability, and an exact quote does not prove the claim follows from it.

**Before offering unattended execution, independently critique the specification.**
Give the reviewer the original owner request, draft and evidence, not your argument
for it. `/ultra-goal:design-critic <slug>` is the packaged option. Resolve material
objections in the decisions record before freezing. If independent context is
unavailable or the owner explicitly waives it, disclose the limit rather than a pass.
**Start authorization is not a review waiver.** “Start now; do not ask again” means
run the critique against the already approved terms before arming; a clean result
needs no further owner turn. Only a material objection needs resolution.

Read back the **complete contract** against the original words: intent, every
acceptance requirement, authority, success and exit conditions, labelled means and
how each requirement will be verified. **Do not arm or present a draft as agreed
until the owner confirms.** An existing explicit confirmation of those terms counts;
silence does not. A clearly labelled draft may be written for independent critique.

## Settle the goal's decisions

Read the canonical contract for exact fields. Resolve these dependencies without
turning the list into a fixed interview script:

1. **Intent:** what outcome improves, and which original owner words define it?
2. **Anchor:** what observational command measures the requested result end to end?
   **No anchor, no artifact.** A unit suite is sufficient only when it measures the
   requested outcome. Otherwise drive the running product or external result.
   Settle criteria before generating a checker; inspect it before approval.
   Declare evaluator logic, fixtures and indirect configuration in `protected`;
   the anchor must not edit them or the reviewed product. Write `budget: N minutes`
   under `## Anchor`; timeout or an unavailable command means unknown, not failed.
3. **Stop condition and Acceptance:** every goal gets `## Acceptance` with stable
   IDs and a `covers` map to anchor or required review. **Unordered, never numbered**:
   requirements describe success; an optional plan describes execution. Checkboxes
   are claims. `success: verified` requires a current green anchor and every required
   review. Explicit `ceiling: N` or `ceiling: none` counts **completion attempts**,
   not host turns, tool calls, tokens or money. Set native budgets separately.
4. **Means:** label complete declarations `[load-bearing]` or `[droppable]`. The
   owner decides what may be abandoned; the run records why it drops an allowed means.
5. **Boundary:** specify **Scope**, **Confidence** and **Inference** refusals: allowed
   paths/effects and approval limits; claims needing measured evidence; conclusions
   that documents alone cannot establish. Existing authorization remains valid.
6. **Verifier:** who checks the result, and **who checks the checker?** A required
   review has accepted identities/fallbacks, bounded inputs, acceptance IDs and a
   receipt written by an independent verifier with its own session. The generator
   never signs it. Advisory review can vary; a critic is **not mandatory for every
   goal**. When choosing repeated review, specify a cap. Fresh context and different
   models can reduce correlation; neither guarantees independence or correctness.
7. **Shape and split:** start with the main model loop; split when each handoff can
   carry the context and return a verifiable result. Follow owner-assigned roles;
   otherwise the main model selects a suitable method within its authority.
8. **Read and write surface:** name what each worker reads, writes and returns,
   including shared files, databases, services and resource limits. One goal or one
   operating loop does not prevent resource collisions. Join writers before review.
9. **Divergence handling:** execution details may adapt; changing frozen terms stops
   and reports. Put the term, observed obstacle and what would settle it under
   `## Challenges from the run` in the decisions record. A challenge is not permission
   to change the term; do not invent one when there is no objection.

## Classify first, then confirm at the end

Can you sketch the whole thing on paper before running any of it? Known routes can
be authored; routes depending on new observations belong to inference. Mixed shapes
are normal. A plan or task list does not require a graph runtime or replace the goal.
Reconsider the initial shape after the decisions are clear.

For delegation, discover actual available targets rather than asking the owner to
inventory them. Use suitable native worker tools or an available bridge; another
Skill is not required. If using the installed delegation bridge, `agent-delegate list --json`
provides that inventory; do not assume the bridge is installed. A discovered Skill,
a callable bridge and a usable target are separate facts. Missing optional tooling
does not block ordinary authorized work. Pass current decisions, failures and evidence,
writable scope and expected results so a worker can act without this Skill installed.
Read the role reference before choosing the mechanism or fallback. Before unattended
execution, establish a usable path for every required verifier and for reading results;
resolve a missing required capability without silently changing the accepted contract.
Call success is not a join: inspect the expected artifact. Transport failures such
as `role_unavailable` are observations, not acceptance conditions. A required review
cannot fall back to generator self-review even when a vendor is unavailable.

## Three tiers of frozen

| Tier | Terms | Changes during a run |
|---|---|---|
| **Frozen** | Intent, Boundary, Anchor, Stop condition, Verification, Acceptance requirement text and complete labelled Means declarations | Owner authority and a new goal required |
| **Firm** | Method, cadence, worker choice, dropping a droppable means or using a pre-authorized verifier fallback | Within existing authority; **write the row in `decisions.md`** with evidence |
| **Fluid** | State, Lessons, Next and ordinary execution planning | Rewrite as needed inside the frozen terms |

**A decisions row records an action; it never grants authority.** It cannot lower a
threshold, raise a resource limit, weaken required verification or retire acceptance.
**Frozen is mechanically observed** through the spec/evaluator baselines; checkbox
state remains mutable. **Firm is enforced socially** through the decisions record.
A moved goalpost closes the run; do not restore a baseline to conceal the change.

## Refuse these shapes

| Failure | Correction |
|---|---|
| Generator grades its own claim | Use the accepted external observation or independent verifier |
| **False consensus** / Review conclusions merged without evidence | Reconcile observations against the artifact; add a critic only when it resolves a real risk |
| **A verdict with no receipt** | Retrieve the current measurement or required review; report missing evidence as missing |
| **The reviewer gets the author's argument** | Give criteria, original evidence and bounded inputs before an author's explanation |
| **An anchor that only tests the code** while acceptance concerns a running product | Exercise that product path |
| **Wrapping up because the context feels full** | Named *context anxiety*: save recovery state; only actual verification establishes completion |
| A workflow consumer nobody exercised | Keep the goal alone until its consumer is proven |
| An attachment or decisions row with easier terms | Preserve the one contract; raise a challenge for owner resolution |

## Compile one artifact

Default location is the project's `.goals/`, not one host's private directory.

| When | Artifact | Template |
|---|---|---|
| Always | `<slug>.goal.md`, including Acceptance, Verification, Carry-over and Handoff | [goal-package.md](assets/goal-package.md) |
| Always | `<slug>.decisions.md` — Decision / Rejected / Why / Who | [decisions-record.md](assets/decisions-record.md) |
| Authored routing, with a proven consumer | `<slug>.workflow.js`, naming `// goal: <slug>.goal.md` | [workflow-script.js](assets/workflow-script.js) |
| Delegated routing | `<slug>.delegation.md`, naming `goal: <slug>.goal.md` | [delegation-package.md](assets/delegation-package.md) |

A workflow **requires a workflow runtime**. Exercise the actual entry point; parsing
JavaScript does not prove `agent()` or `pipeline()` exists. Without a consumer,
do **not** emit `<slug>.workflow.js`. An attachment adds execution, never its own terms.
Do not generate topology from a template engine: author the necessary route yourself.

**The fourth column is `Who`, and it holds `owner` or `agent`.** Mark assumptions
honestly; an agent-authored row is not owner confirmation. Edit a revised decision's
row and move the old answer into Rejected with its reason. Do not append another
history table or a second prose architecture; the executable artifact owns the route.

## Make the loop evolve

Every compiled goal includes `## Carry-over`, even a single start that may compact
or be interrupted. `## Cadence` only declares repeated scheduling. The handoff must
say **read it before acting and rewrite it before finishing**:

- `### State`: current facts, evidence pointers and unfinished work.
- `### Lessons`: compact causal findings that change the next action.
- `### Next`: exactly one immediate recovery objective inside the frozen intent;
  link a longer plan when useful.

**A lesson is a cause and a next action, not an event.** Keep the relevant lessons;
three is a compaction suggestion, not a correctness limit. **Rewrite, never append**
the current summary; retain the evidence it cites. Compaction is not necessarily an
empty context, and a carried claim is not proof that the environment still matches it.
Reconcile current files, results, resources and pending effects before resuming.
Recovery does not renew authorization, budgets or canceled work. For an external
operation with an unknown outcome, inspect its actual effect before retrying.

Lessons stay conditional on their project and evidence: one project's dead end is
another project's correct answer. Never automatically promote them to user-level
configuration or this Skill. A skill change needs the tested promotion/rollback
procedure in the evolution reference. Git can preserve the diffs when committing is
authorized; the event log and retained review evidence remain useful without Git.

## Inspect what is running

Resolve these scripts from this skill's installed directory; run them in the project.

```bash
python3 <skill-dir>/scripts/validate_artifact.py .goals --status
python3 <skill-dir>/scripts/validate_artifact.py .goals --audit
```

Status is recomputed on every call; **nothing is stored by the status command**.
It reports artifacts, contract findings and recorded observations, not fresh proof
that current outputs pass. Audit reads Git history and the event log; it runs nothing.
Read evidence when a record is pending, interrupted or older than the current result.
`--run-anchors` executes the artifact's shell commands. Read them first and use
existing authorization for their effects; ask only if it is missing.

## Modify an existing loop

Read the artifact and paired decisions before changing either. Run status to identify
the goal. **Read `## Challenges from the run` before anything else in that file.**
Surface an applicable rejected decision and its rationale; resolve whether that reason
still holds rather than silently reversing it. **Edit the affected row**, placing the
old decision in Rejected, then validate both files.

Changing intent, anchor, boundary or any other frozen term ends the old run and needs
owner-approved new terms. A loop whose anchor changed is a different loop. Repeat only
the affected interview decisions and the independent adequacy check; preserve answers
that remain valid. An objection does not authorize rebaselining an active run.

## Starting a run, on whichever host you are

**Goal mode supplies the turns; the gate judges the claims.** The run works in ordinary
host turns. A Stop can refuse a completion claim within a bound; it **cannot schedule
the next turn** or revive an exited process. Arming alone is not unattended execution.

| Host surface previously measured | Native goal entry | Check in this session |
|---|---|---|
| Claude Code | `/goal <objective>` | CLI/native continuation and resource controls |
| Codex | `/goal <objective>` | Application goal service; do not infer parity in `codex exec` |
| Kimi | `/goal <objective>` | Native pause/resume/cancel and current hook support |
| zCode | `/goal <objective>` | Interactive mode or supported headless target mode |
| OpenCode | No goal entry found in the measured surface | Absence of evidence, not proof of absence |

Check your own host rather than trusting this table. The host reference and actual
session decide capabilities. Read the host-hooks reference for per-host contracts and
measured limits. **Windows is unverified**; structural checks are not a native lifecycle.
Finite probes do not establish statistical 95% unattended reliability.

## Validate, then offer to start it

```bash
python3 <skill-dir>/scripts/validate_artifact.py .goals --json
```

The validator checks mechanical facts and never edits the artifact; its silence is
not evidence that the design is right. Finish independent specification critique.
**Use an existing explicit start authorization; otherwise offer to start the run.**
Name the artifact, anchor, attempt ceiling, open requirements and exact command:
**`/ultra-goal:goal-run <slug>`**. If start authority is missing, ask whether to start
now or change the artifact first. Never read silence or an unrelated reply as consent.

**Do not send them to clear the context first.** The accepted interview still helps;
carry source decisions forward rather than forcing a reset by default.
**When they say start it, this manual stops applying to you.** Invoke the run command
and follow [goal-run.md](../../commands/goal-run.md): the host keeps this Skill's
content in the conversation, but you are now the run, not its designer. Frozen-spec
checks and `## Challenges from the run` preserve that boundary without another interview.

Before the owner walks away, finish the authorized setup: exercise the actual entry
point, confirm native continuation and resource controls, arm with the current native
session identity, and establish where results will be read. An attachment runs against
the same armed contract. Native permissions own effects; Stop cannot undo a write.
If continuation or result delivery is missing, state the interactive limitation.
If the owner declines starting, hand off the exact command and expected first result.

## Verification before final delivery

The execution handoff must require the run to finish output edits, join writers and
obtain required review before `goal_run.py verify <slug> --root <project>
--session-id <current-native-session-id> --claim <claim>`. Read this attempt's recorded
`verification_passed` result **before** the final claim. A historical green, native
completed status, a checkbox or a worker's success message does not replace it.
The candidate-file Stop path is a fallback: until its real measurement is available,
report verification as pending. Changes after a pass require fresh review and verification.

### Wide latitude, zero trust in self-report

The run's report and mutable state are claims. Gate events are observations; required
receipts carry checked provenance. Writable hashes and session IDs provide **detection
and audit, not isolation or authentication**. A shared-filesystem writer can forge them.
Use native permissions, an isolated verifier or authenticated external evidence where
required, and disclose an unavailable boundary before unattended work. No digest proves
criterion adequacy or that a quotation supports its claim.
