# UltraGoal

[English](README.md) · [简体中文](README.zh-CN.md)

**Goal engineering for Claude Code, Codex, Kimi and zCode.** UltraGoal turns a vague
request into an agreed, inspectable goal, then helps a host agent pursue it using
current evidence. Version: **2.15.1**.

The goal is the invariant. A loop chooses its next route during execution; a graph
chooses routes ahead of execution. Both use the same goal contract.

UltraGoal is a **Skill, scripts and host hooks**. The main agent chooses methods
and workers. Scripts check narrow facts and evidence contracts. The host supplies
tools, permissions, session identity, continuation and cancellation. There is no
bundled Agent Runtime, background dispatcher or workflow engine.

## Contents

- [Install and start](#install-and-start)
- [From a request to an agreed goal](#from-a-request-to-an-agreed-goal)
- [Autonomy during execution](#autonomy-during-execution)
- [Dispatching agents and receiving feedback](#dispatching-agents-and-receiving-feedback)
- [When the agent asks the owner](#when-the-agent-asks-the-owner)
- [Files and their maintenance](#files-and-their-maintenance)
- [Arming and native continuation](#arming-and-native-continuation)
- [Hooks and host coverage](#hooks-and-host-coverage)
- [Completion verification](#completion-verification)
- [Independent review](#independent-review)
- [Recovery, cancellation and cleanup](#recovery-cancellation-and-cleanup)
- [Troubleshooting](#troubleshooting)
- [Knowledge and Skill maintenance](#knowledge-and-skill-maintenance)
- [Validation and limits](#validation-and-limits)

## Install and start

Python **3.10+** is required for the bundled scripts. Their runtime and tests use
the Python standard library. The host must be able to run the configured Python
command and discover the appropriate plugin components.

### Native plugins

Native installation provides the main Skill, the run command, review roles and
the host's hook profile. CLI syntax depends on the installed host version. These
Claude Code and Codex command forms were checked against local CLI help on
2026-09-05; that check does not establish a fresh installation or lifecycle pass.

Claude Code:

```bash
claude plugin marketplace add rocky2431/ultra-goal-skill
claude plugin install ultra-goal@ultra-goal
```

Codex:

```bash
codex plugin marketplace add rocky2431/ultra-goal-skill
codex plugin add ultra-goal@rocky-ultra-goal
```

For Kimi and zCode, use the native plugin facility available in your installed
build and load the package at `plugins/ultra-goal`. The package supplies
`kimi.plugin.json` and `.zcode-plugin/plugin.json`. A `kimi plugin` CLI subcommand
is not present in every distribution. If the build cannot load its manifest and
hooks, a copied Skill alone does not provide the gate.

Confirm discovery of the Skill, run command and configured hooks in the actual
host. Avoid enabling both native and legacy copies of the same hooks. A manifest
parse or a successful install message does not prove that the host invokes a hook
or honors its output.

### Legacy Skill-only installer

For hosts without the native package path, the repository also has a managed
copy installer:

```bash
git clone https://github.com/rocky2431/ultra-goal-skill.git
cd ultra-goal-skill
python3 scripts/install_user.py install --hosts claude
python3 scripts/install_user.py doctor --json
```

Available copy targets are `hermes`, `claude`, `codex`, `kimi`, `zcode` and
`opencode`. The installer backs up managed changes and refuses to overwrite an
unmanaged Skill. `uninstall --hosts <host>` removes its managed installation.

This route copies the main Skill and configures **only Claude's Stop,
SessionStart and PreCompact hooks**. It does not install the complete native
command/role package or the other hosts' hook profiles. Its doctor checks its own
files and registrations, not unattended behavior.

### Short names: UG and ultragoal

Keep the product name **UltraGoal**; use `UG` / `ug` as the short entry and
`ultragoal` as the entry without a hyphen. From a local checkout, add native
user shortcuts for the host you use:

```bash
python3 scripts/install_shortcuts.py --host claude
python3 scripts/install_shortcuts.py --host codex
```

`--host kimi` and `--host zcode` are also available. Reload skills or start a new
host session after adding them. The spelling follows each host's native interface:

| Host | Short entry | Full entry |
|---|---|---|
| Claude Code | `/UG` | `/ultragoal` |
| Codex | `$ug` | `$ultragoal` |
| Kimi Code | `/skill:ug` | `/skill:ultragoal` |
| zCode | Select `ug` in its Skill picker | Select `ultragoal` in its Skill picker |

These are tiny pointers to the original `SKILL.md`, so interviews, authority and
completion checks use the same instructions. The installer prints the created
paths, accepts an existing identical shortcut, and refuses conflicting files.
It adds no hooks or runtime and does not change the `ultra-goal` package identity,
old commands or goal files. Install the native plugin above for its hook/role support.

The pointers default to this checkout, which must stay on disk. Use
`--skill /path/to/ultra-goal/SKILL.md` to point at another installed copy instead.
To remove a shortcut, delete its printed file; to change its source, remove it
and rerun the command. Kimi uses `~/.kimi-code/skills`; for a custom
`KIMI_CODE_HOME`, put the printed Skill folders under that root's `skills/`.

Claude's bare `/UG` requires this standalone shortcut: plugin commands are
[namespaced](https://code.claude.com/docs/en/plugins).
[Codex uses explicit `$skill` invocation](https://learn.chatgpt.com/docs/build-skills),
and [Kimi uses `/skill:name`](https://moonshotai.github.io/kimi-code/en/customization/skills.html).
Do not assume bare `/UG` works in every host; zCode discovery still needs checking
in the installed build.

### First goal

In the **business project's directory**, ask the host to use UltraGoal:

> Use UltraGoal to turn this into an executable goal: make the CSV export usable
> by our operations team. Investigate what already exists, ask me only the
> material decisions, and show me the complete acceptance and authority contract.

The agent inspects existing goals before starting an interview. Once the terms
are confirmed, use the exposed `goal-run` command. On hosts with namespaced slash
commands, the packaged form is:

```text
/ultra-goal:goal-run export-ready
```

Where the host does not expose that command, ask it to follow the packaged
[run procedure](plugins/ultra-goal/commands/goal-run.md) using its actual tools.
The `.goal.md` and paired `.decisions.md` must already exist. Starting a run does
not authorize the agent to invent a missing agreement.

For unattended work, the host also needs an available, authorized native
continuation mechanism. Arming the gate alone cannot provide one.

## From a request to an agreed goal

The entry distinguishes creating, modifying, inspecting and executing a goal,
and ordinary work that does not need a goal loop. It reads references only when
the current phase needs them.

Init and research resolve facts that can change the goal. The agent investigates
repository state, tools and existing instructions itself. It asks only unresolved
material owner decisions: **one question per turn**, with a recommendation and
what would change it. These are dependencies to resolve, not nine mandatory
interview turns.

The resulting contract contains:

| Field | What it establishes |
|---|---|
| `Intent` | Material original owner words and a source locator where available, separate from the agent's interpretation |
| `Acceptance` | Unordered success requirements with stable IDs; an execution plan has a separate home |
| `Anchor` | An observational command that checks the agreed result, with an explicit time budget |
| `Stop condition` | `success: verified` and `ceiling: N` or `ceiling: none`; the ceiling counts completion attempts |
| `Means` | Complete declarations labelled `[load-bearing]` or `[droppable]` |
| `Boundary` | Scope/effects and approval limits; confidence claims needing measurement; inference limits |
| `Verification` | Evaluator provenance, protected evaluator inputs, coverage for every acceptance ID and any required review |
| Roles and surfaces | Worker responsibilities, approved fallbacks, readable/writable resources and integration ownership |
| `Carry-over` and `Handoff` | Current state, lessons, next action and the actual start/recovery procedure |

Before freezing, challenge both **false acceptance** (all checks pass but the
request is unmet) and **false rejection** (a valid outcome fails an unrequested
method constraint). A unit suite is enough only when it measures the requested
outcome; file existence is not proof of usability.

Before offering unattended execution, the instructions require independent
specification critique, using the original request, draft and evidence before
the author's defense. Resolve material objections, then read back the complete
contract. Existing explicit confirmation counts; silence does not. "Start now"
is not a review waiver. A clean critique of already approved terms does not
require another confirmation.

The critique and the quality of the interview are currently **model-followed
instructions**. Structural validation cannot establish that they happened or
that the criteria fully express the owner's intent.

See the [canonical goal contract](plugins/ultra-goal/skills/ultra-goal/references/goal-contract.md).

## Autonomy during execution

| Tier | Contents | Change rule |
|---|---|---|
| Frozen | Intent, Boundary, Anchor, Stop condition, Verification, acceptance requirement text and complete labelled Means | Owner authority and a new goal are required |
| Firm | Method, cadence, worker choice, abandoning an approved droppable means, using an approved verifier fallback | Adapt within authority and update the decision row with evidence |
| Fluid | State, Lessons, Next and ordinary execution planning | Rewrite as new evidence arrives |

The declaration that a means is droppable stays frozen; deciding to drop it is
an allowed strategy change. A decision row records a choice and never grants
permission to lower a threshold, increase a budget or waive required review.

A loop lets the main model select the next useful action from observations.
Optional `.workflow.js` and `.delegation.md` attachments name the same `.goal.md`
and cannot establish different terms. Emit a workflow only when its actual
consumer exists and its entry point has been exercised. Parsing JavaScript does
not prove that `agent()` or `pipeline()` can run.

## Dispatching agents and receiving feedback

**The main agent dispatches work. Hooks do not.** Honor owner-assigned roles;
otherwise choose a worker only when a bounded handoff is useful. Small work may
stay in the main session. There is no fixed vendor order or mandatory three-model
round on every task.

Use the host's actual delegation tools or an installed bridge. When the
`agent-delegate` bridge is available, `agent-delegate list --json` discovers its
registered targets. The Skill does not install or emulate that bridge.

Each mission supplies:

1. The accepted terms and the bounded objective of this assignment.
2. Current decisions, relevant original evidence and prior failed attempts.
3. Read/write scope, shared resources, limits and integration responsibilities.
4. The expected output location and how the result will be checked.
5. The conditions the worker can resolve itself and those it must return.

Workers can use `.goals/.work/` for mission/result files. Separate task files do
not isolate writes to a shared file, database or service. Parallelize genuinely
independent work and join all relevant writers before integrated review.

Feedback has different meanings:

| Observation | Main agent's responsibility |
|---|---|
| The call succeeded | Inspect the expected output; transport success is not completion |
| The worker reports completion | Read the artifact and its evidence against the mission |
| The worker failed | Preserve the observation, then choose an authorized retry, alternative or fallback |
| The worker requests input | Answer from existing terms where possible; ask the owner only for a material decision |
| The worker explicitly rejects | Examine the boundary and any authorized alternative |
| No response | Treat status as unconfirmed and inspect the native task; do not invent an input request or completion |

Even a call that *succeeds* while writing no file is insufficient:
**the round's evidence is the file the role was told to write**. A returned
summary is a claim, and model agreement is not independent evidence.

On the registered host profiles, recognized delegation failures produce
`role_unavailable`; a later success for the same target/tool produces
`role_recovered`. Recognition covers direct `agent-delegate run --to <target>`
commands or structured calls to that exact tool. Opaque scripts, compound
commands and arbitrary native delegation tools are not automatically observed.
Recovery describes the call, not every mission for that target.

These transport events are audit observations, not extra acceptance conditions.
An approved fallback may satisfy the goal while the original vendor remains
unavailable. A **required independent reviewer cannot fall back to generator
self-review**. Additional advisory reviewers or a reviewer/critic exchange are
optional unless the accepted goal requires them; repeated review needs a bound.

After reading feedback, the main agent rewrites `State`, `Lessons` and `Next`,
updates a decision row if strategy changed, and chooses the next action. This is
the feedback loop; there is no Python scheduler choosing the strategy.

## When the agent asks the owner

Questions come through the main agent's normal conversation or native input UI.
Hooks do not conduct the interview or forward every worker question verbatim.

| Situation | Action |
|---|---|
| Repository or tool fact can be checked | Investigate it |
| Change method/order or use an already approved fallback | Decide within authority and record a material choice |
| Change success criteria, load-bearing means, boundary or budget | Ask the owner |
| Need an effect outside existing authority | Ask before that effect; continue independent authorized work |
| Required reviewer unavailable, with no accepted independent fallback | Remain unverified and report the missing condition |
| External operation has an unknown outcome | Inspect its real effect before retrying or escalating |
| Frozen terms conflict | State the term, observed obstacle, recommendation and deciding fact |

Challenges belong in `## Challenges from the run` in the decisions record.
A challenge is not authorization to edit the term. Reuse existing approvals;
do not ask again for a decision already settled.

## Files and their maintenance

Artifacts belong in the business project's `.goals/`, not a vendor's private
Skill directory. `<slug>` names one goal, not a path.

| File | Writer | Maintenance rule |
|---|---|---|
| `<slug>.goal.md` | Owner + agent for the contract; main agent for Carry-over | Keep frozen terms; rewrite current execution state |
| `<slug>.decisions.md` | Owner + agent | Decision / Rejected / Why / Who; revise the affected row, distinguish `owner` from `agent` |
| `<slug>.events.jsonl` | Gate and hook scripts | Append observations; never insert model-authored claims as measurements |
| `active` | `arm`, `rebind`, `disarm` | Goal slug plus its owning native session ID; transient |
| `<slug>.spec.baseline` | Arming script | Write-once frozen-contract digest |
| `<slug>.verification.baseline` | Arming script | Write-once hashes of protected evaluator files |
| `<slug>.baseline` | Arming script | Starting Git revision or `none`; not a complete history |
| `<slug>.verification.lock` | Verification scripts | Native locking for serialized verification; keep the lock inode |
| `<slug>.candidate` | Main agent, optional fallback path | One pending completion claim, consumed by the gate |
| `<slug>.review.json` | Independent verifier | Default current receipt; review again after declared inputs change |
| `<slug>.reviews/<digest>.zip` | Gate | Retained receipt, goal and declared input snapshots for historical audit |
| `.work/` | Workers | Disposable intermediates only after necessary evidence has a retained home |
| `<slug>.workflow.js` / `<slug>.delegation.md` | Agent within the agreement | Optional execution attachments; no independent success terms |

Before ending each work turn, the main agent rewrites:

- **State:** current facts, evidence pointers and unfinished work.
- **Lessons:** conditional causes that change the next action, not an event diary.
- **Next:** one immediate recovery objective; link a longer plan when useful.

Three lessons and eight state entries are compactness suggestions, not validity
limits. Keep a necessary fourth lesson. Pruning a summary must not delete the
only source supporting a claim. Hooks do not write missing model reasoning or
automatically maintain all these documents.

Events retain bounded observations, digests and output excerpts, not every tool's
full stdout or all conversations. Required review archives contain **declared
inputs**, not the whole workspace. Preserve other material raw evidence explicitly.
Git preserves committed revisions only; tracking a file does not authorize a
commit or publication.

See [document maintenance](plugins/ultra-goal/skills/ultra-goal/references/document-system.md).

## Arming and native continuation

`arm` validates the goal and paired decisions, checks the real initiating session,
refuses another active goal/session, pins baselines, records session ownership and
then creates the marker. One project directory has one active goal marker.

The marker format is shown for inspection, not manual authoring:

```text
export-ready
session actual-native-session-id
```

Use explicit current native session identity. Do not guess one or adopt an
inherited parent process's ID. A foreign or identity-less event cannot consume
the owner's candidate or reset its state. Re-arming preserves baselines and prior
attempts. Explicit, authorized `rebind` transfers the session while retaining
those facts and discarding the previous pending claim.

For manual operation, replace the example paths, slug and identity below:

```bash
ULTRAGOAL_SCRIPTS="/path/to/ultra-goal-skill/plugins/ultra-goal/skills/ultra-goal/scripts"
ULTRAGOAL_PROJECT="/path/to/business-project"
ULTRAGOAL_SLUG="export-ready"
ULTRAGOAL_SESSION="actual-native-session-id"

python3 "$ULTRAGOAL_SCRIPTS/validate_artifact.py" "$ULTRAGOAL_PROJECT/.goals"
python3 "$ULTRAGOAL_SCRIPTS/goal_run.py" arm "$ULTRAGOAL_SLUG" \
  --root "$ULTRAGOAL_PROJECT" --session-id "$ULTRAGOAL_SESSION"
```

Arming activates the gate. Native goal mode supplies continued execution. When a
model-callable native mechanism exists and is authorized, use it; if the host
exposes only a user command, the owner must invoke that actual command. Without
a driver, the agent can work in the current turn but cannot promise later turns.
Do not start a detached process to evade native cancellation or continuation bounds.

## Hooks and host coverage

These are **the registrations shipped by this package**, not a claim of identical
vendor APIs or a fresh live installation on every host.

| Event | Claude Code | Codex | Kimi | zCode | Purpose |
|---|---|---|---|---|---|
| `Stop` | Yes | Yes | Yes | Yes | Ordinary stop observation or explicit candidate verification |
| `SessionStart` | Yes | Yes | No | Yes | Supported start/resume/clear/compact/fork recovery |
| `PreCompact` | Yes | Yes | Yes | No | Carry-over digest and counts before compaction |
| `PostToolUseFailure` | Yes | No | Yes | Yes | Recognized delegation failure |
| `PostToolUse` | Yes | No | Yes | Yes | Recognized call recovery |
| `UserPromptSubmit` | No | No | Yes | No | Goal pointer and last recorded decision on a user prompt |
| `TurnStarted` | No | No | Yes | No | Actual host turn ID/origin observation |

Common registrations are in `hooks/hooks.json`; Claude adds `hooks/claude.json`,
Codex uses `hooks/codex.json`, and Kimi declares its profile in `kimi.plugin.json`.
The package includes host-specific output and Windows command adapters; their
presence does not establish Windows lifecycle acceptance.

A normal Stop with **no completion candidate** does not run the Anchor or spend an
attempt. Stop is not a background service or a universal write-permission gate.
Frozen-spec changes are detected at Stop; evaluator protection is checked at
verification boundaries. Detection cannot undo a write or an external effect.

Blocking output follows the host contract: Claude/Codex/zCode use the top-level
`decision: block` and `reason`; Kimi uses nested
`hookSpecificOutput.permissionDecision: deny` and `permissionDecisionReason`.
An allowing Stop carries no added model context. Use ordinary tool output to make
a verdict visible before delivery; future recovery injection is best effort.

See [host hooks and lifecycle limits](plugins/ultra-goal/skills/ultra-goal/references/host-hooks.md).

## Completion verification

Prefer explicit `verify`, an ordinary tool call that returns the current result
**before** the agent's final answer. It uses the same gate as the Stop fallback:

```bash
python3 "$ULTRAGOAL_SCRIPTS/goal_run.py" verify "$ULTRAGOAL_SLUG" \
  --root "$ULTRAGOAL_PROJECT" --session-id "$ULTRAGOAL_SESSION" \
  --claim "The integrated result is ready for the accepted checks."
```

Before this call, finish outputs, update recovery state, join relevant writers
and obtain any required independent receipt. The verification path:

1. Confirms the active goal/session and acquires the native verification lock.
2. Reconciles a previous started-but-unsettled attempt as interrupted; never
   substitutes an older green or silently replays the Anchor.
3. Checks the frozen terms against the arming baseline.
4. Records `verification_started` with a unique ID before consuming the claim.
5. Applies the completion-attempt ceiling and checks evaluator protection and
   any required current review.
6. Runs the agreed Anchor within its declared budget.
7. Rechecks the terms, protected evaluator and review inputs after the Anchor.
8. Retains required review evidence and settles the same attempt ID.

A current recorded result must establish the whole accepted verification contract:
frozen terms intact, evaluator protection intact, current green Anchor and every
required review valid. `verification_passed` and `fresh_check` refer to the current
request; a missing recorded settlement cannot support completion.

| Condition | Gate behavior | Completion established? |
|---|---|---|
| Ordinary Stop, no claim | Allow without running the Anchor | No |
| Current full verification passes | Allow | Accepted checks passed |
| Anchor red or a required verification condition unmet | Refuse a refusable claim within the applicable denial bound | No |
| Command unavailable or timed out | Allow, result unknown | No |
| Completion-attempt ceiling exhausted | Allow and report remaining work | No |
| Consecutive-denial bound exhausted | End this turn; further work needs a native turn or prompt | No |
| Frozen specification changed | Close the run and remove active marker/candidate | No |
| Foreign/missing event identity on a bound goal | Inert | No judgment |
| Legacy/invalid unbound marker | Diagnostic on Stop; no handler or state mutation | No judgment |
| Hook cannot produce a reliable judgment | Do not trap the host; no completion proof | No |

Three limits are separate: the owner's **completion-attempt ceiling**, the gate's
**consecutive-denial bound**, and the **host's native budgets**. None is a synonym
for the others. `ceiling: none` does not remove host limits. The current Anchor
maximum is 570 seconds within a 600-second Stop hook configuration.

Anchor observations are `green`, `red` or `unknown`. Run dispositions are separate:
`in_progress`, `input_required`, `blocked_retryable`, `budget_exhausted`,
`unachievable`, `completed`, `canceled`. A failed check alone does not prove a goal
permanently unachievable.

The fallback writes `<slug>.candidate` and lets a real Stop check it **after** the
response. Until then it is pending. A following Stop does not rerun a claim already
consumed by explicit verification. If the model says "done" but neither invokes
`verify` nor writes a candidate, there is no natural-language completion detector
that forces this path. Following the claim protocol remains a model obligation.

## Independent review

Every acceptance ID maps to `anchor` or `review` in `Verification.covers`. For a
required review, the contract declares approved verifier identities/fallbacks,
bounded `inputs` and the receipt path. Obtain the current review packet with:

```bash
python3 "$ULTRAGOAL_SCRIPTS/goal_run.py" review-inputs "$ULTRAGOAL_SLUG" \
  --root "$ULTRAGOAL_PROJECT"
```

The **independent verifier** writes the receipt; the generator must not sign for
it. The gate checks the approved identity, a session distinct from current and
previous executing sessions, a digest binding the contract and declared inputs,
required IDs, passing verdict and per-ID `checks` with actual path/quote evidence.
Changed inputs require a new review. Native forks that share the execution
session's identity cannot satisfy that distinct-session requirement.

At the post-Anchor boundary, the gate retains a content-addressed ZIP with the
receipt, goal, manifest and declared input bytes. Historical audit validates that
archive, not today's replacement files. Missing or corrupted recorded archives
are reported, not silently rebuilt or reused as a current review.

These are checked declarations, not authenticated credentials. Shared filesystem
fields do not provide identity security; a quotation match does not prove the
claim logically follows. Fresh context and model diversity reduce some correlated
errors but do not establish correctness. Review the original evidence before an
author's persuasive explanation.

## Recovery, cancellation and cleanup

Before finishing each turn, save Carry-over. `PreCompact` records its digest and
counts; it does not summarize unsaved reasoning or block compaction. Supported
`SessionStart` injection restores priority terms/state and points to anything
omitted for space; read the complete contract before acting. Kimi's prompt hook
provides a pointer and last decision, while `TurnStarted` only observes the turn.

A started verification without settlement remains pending/unknown and spends an
attempt. Recovery can mark it interrupted after acquiring the lock. Reconcile
actual files and external effects before a new attempt. A request sent without a
response may already have taken effect: query the service before retrying. This
is verification bookkeeping, not exactly-once business execution.

For authorized session transfer with valid baselines:

```bash
python3 "$ULTRAGOAL_SCRIPTS/goal_run.py" rebind "$ULTRAGOAL_SLUG" \
  --root "$ULTRAGOAL_PROJECT" --session-id "$ULTRAGOAL_SESSION"
```

Recovery never renews authority, budgets or canceled work. Cancellation must be
reconciled in **both** native goal state and the Skill's gate. Disarming alone
does not cancel a native goal:

```bash
python3 "$ULTRAGOAL_SCRIPTS/goal_run.py" disarm "$ULTRAGOAL_SLUG" \
  --root "$ULTRAGOAL_PROJECT"
```

After a current verified completion, the agent reports deliverables, evidence and
limits, updates native goal state through its actual controls, and disarms the
gate. Keep the goal, decisions, events, baselines and required review evidence for
the agreed retention period. Remove only disposable scratch after checking that
necessary evidence survives. Never remove unsettled-attempt evidence just to make
a directory look complete. Commit, install and publish only with authority.

## Troubleshooting

| Symptom | Check and response |
|---|---|
| `active` exists, but nothing is verified | Check hook discovery, actual event `cwd`, marker format and owning session; an ordinary Stop also does not verify |
| Legacy marker contains only a slug, or its session binding is invalid | Version 2.15.1 emits a Stop `systemMessage` diagnostic; the gate remains inactive and files stay untouched |
| UI hides the allowing diagnostic | Inspect raw hook output/logs; emitting a diagnostic is not proof that every host UI displays it |
| Ordinary `arm` refuses a legacy marker | Use authorized `rebind` if its original baselines remain valid; otherwise explicitly disarm, validate the agreed goal and arm it |
| Baselines mismatch or the goal was closed after a spec change | Create a newly authorized goal, preferably a new slug; do not delete history or re-pin changed terms to conceal the change |
| Another session's hooks are silent | Intentional ownership isolation; do not steal the marker |
| Worker call succeeded but no result file exists | The mission is not joined; inspect the native task and retrieve its actual output |
| Anchor cannot execute or times out | Outcome is unknown; diagnose the executable, environment and budget |
| Receipt is missing/stale/self-authored | Obtain an accepted independent review of current inputs |
| Anchor passed, then verification was interrupted | Latest attempt is unverified; older green cannot settle it |
| Agent stops although the goal is unmet | Check native budgets, attempt ceiling and denial bound; a Stop hook cannot provide later execution |

The unbound-marker diagnostic uses the existing allowing `systemMessage` channel
and only runs on Stop. It does not auto-migrate the marker, run the handler,
consume a candidate, write an event or inject continuation context. Bound foreign
sessions remain silent. `ULTRA_GOAL_HOOKS_DISABLED=1` disables these hooks in the
host process environment; reconcile any native goal separately.

For read-only inspection and historical evidence checks:

```bash
python3 "$ULTRAGOAL_SCRIPTS/validate_artifact.py" "$ULTRAGOAL_PROJECT/.goals" --status
python3 "$ULTRAGOAL_SCRIPTS/validate_artifact.py" "$ULTRAGOAL_PROJECT/.goals" --audit
python3 "$ULTRAGOAL_SCRIPTS/goal_run.py" diff "$ULTRAGOAL_SLUG" --root "$ULTRAGOAL_PROJECT"
```

`--status --run-anchors` is different: it executes artifact-named shell commands
and requires their effects to be authorized. Audit findings identify divergences;
they do not automatically repair them or prove the specification was adequate.

## Knowledge and Skill maintenance

Keep raw observations, current state and conditional project knowledge distinct.
A lesson belongs in existing project documentation with its evidence, applicable
conditions and what would invalidate it. A business run may revise its own state;
it cannot automatically rewrite the installed Skill or global configuration.

An authorized maintenance change follows a small cycle: retain the failure,
formulate conditional knowledge, propose the smallest instruction/code change,
compare against a baseline on relevant and held-out work, then retain or roll back
the candidate. Preserve failed experiments. There is no permanent maintainer agent
or automatic rule promotion.

The [research basis](plugins/ultra-goal/skills/ultra-goal/references/research-basis.md)
links prior work from OpenAI, Anthropic, Google and others. WikiSkill informs the
separation of experience, knowledge and executable skills; SKILL.state informs
immutable specification versus mutable state. Their measured results and runtime
properties do not transfer automatically to this Skill. See the
[maintenance procedure](plugins/ultra-goal/skills/ultra-goal/references/evolution-and-scope.md).

## Validation and limits

Run the repository checks without installing test dependencies:

```bash
python3 -m unittest discover -s tests -v
```

The suite covers contract validation, session ownership, candidate verification,
interruption accounting, locks, retained review evidence, host output contracts
and packaging. The 2.15.1 regression exercises the unbound-marker diagnostic
through all four Stop adapters and checks that goal files remain byte-identical.
This is a script-level check, not a four-host UI or unattended lifecycle run.

The model still owns interview adequacy, specification critique, routing, joins,
state maintenance and invocation of the completion protocol. Scripts mechanize
narrow facts; they do not verify every natural-language statement, authenticate
shared-file identities or prove the original goal can never be wrong.

Historical product and host probes are bounded evidence. Full unattended closure
across all four hosts, Windows native lifecycle, all cancellation/recovery
combinations and a statistical reliability above 95% remain unestablished. Eval
scenario definitions are not completed model trials. See
[remaining validation scope](docs/wip/outstanding.md).

## License

[MIT](LICENSE).
