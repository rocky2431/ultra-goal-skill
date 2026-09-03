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

It covers the whole life of a loop — create it, look at it, change it — and needs no other
Skill installed to do any of that.

0. **Recognizes the intent** before anything else: create a loop, modify one that exists,
   inspect what is running, or say this is not a loop at all. When the workflows directory
   is non-empty it checks status *before* the first question, so a request about work that
   already has a loop becomes a modification instead of a second artifact for the same job.

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
| Loop | `<slug>.goal.md` — the objective plus the goal line to paste | the host's goal mode |
| Graph, one vendor | `<slug>.workflow.js` — topology in code | a workflow runtime, where one exists |
| Graph, several vendors | `<slug>.delegation.md` — one mission per worker | cross-agent delegation |
| Always | `<slug>.decisions.md` — Decision / Rejected / Why | you, next time |

The decisions record holds decisions, not architecture. The script or prompt is the only
description of what the thing does; a prose copy of it goes stale and starts lying. It is
also the interview's progress — written row by row as answers are confirmed, before the
artifact exists — so a session that dies mid-interview resumes instead of restarting.

4. **Tracks state without storing any.**

```bash
python3 scripts/validate_artifact.py .loops --status
```

Reports each artifact's shape, anchor, stop condition, phases or workers, and decision
count. The artifacts on disk are the only record; this is a projection recomputed on every
call, so it cannot drift the way a tracked state file would. `--run-anchors` executes each
anchor and reports its exit code — the one question that matters about a running loop — but
it runs commands the artifact names, in a shell, so it asks first and refuses to run
without `--status`.

5. **Makes the loop evolve.** An unattended loop wakes with an empty context every
   iteration. Unless something carries forward it rebuilds history from git logs and retries
   paths it has already proven dead, believing each time it is the first attempt. So a
   `/loop` or `/schedule` artifact gets a `## Carry-over` section, and **the prompt itself**
   is wired to read it before acting and rewrite it before finishing — a section nothing
   writes to stays empty forever.

   Three places, three jobs, no duplication:

   | What you want to see | Where it lives |
   |---|---|
   | What is true now | the `## Carry-over` section — current only, pruned |
   | How it became true | `git log -p <slug>.goal.md` — the diffs *are* the evolution |
   | What each iteration did | the commit message — one line per iteration |

   Because the history is in Git, the document never has to hold it. Carry-over has two
   parts with different budgets: `### State` (where the work stands, at most 8) and
   `### Lessons` (**why** something failed and what to do instead, at most 3). The Lessons
   cap comes from Reflexion, which bounds its reflection memory at 1-3 because entries the
   model must reason over compete with the work for the same budget.

   A lesson is a cause and a next action, never an event. "The build failed" is the signal;
   "the build fails without a committed lockfile because CI runs `--frozen-lockfile` —
   commit the lockfile in the same change" is the reflection. Only the second one changes
   the next iteration.

6. **Keeps lessons in the project.** What a loop learns is true of one repository — one
   project's dead end is another project's correct answer. It never gets promoted to
   user-level configuration or into this Skill, which is versioned and shared. The Skill
   carries the criteria, the owner's configuration carries their standing preferences, the
   project carries what its loop learned, and the arrows only point down.

7. **Modifies by editing the decision, not appending to a log.** A changed decision replaces
   the old one in the Decision column and the old one moves to Rejected with why it changed.
   A request that contradicts something already in the Rejected column gets surfaced rather
   than quietly reversed. A change to the anchor itself reopens the interview — a loop whose
   anchor changed is a different loop.

## Hosts

Goal mode is the mechanism: paste one objective into your CLI, walk away, and the host keeps
the model working until it is met or a ceiling is hit. Measured on real installs:

| Host | Goal mode | Notes |
|---|---|---|
| Claude Code | `/goal <objective>` | backed by a stop hook; also has `/loop`, `/schedule` |
| Codex 0.150.1 | `/goal <objective>` | a `goal` extension accounts progress after every tool call |
| Kimi | `/goal <objective>` | plus `/goal pause` / `resume` / `cancel` |
| zCode 0.16.5 | `/goal <objective>` | also `--target` for a headless session |
| OpenCode 1.18 | not found | the same text works as a plain prompt |

"Not found" means no evidence in that host's help output or shipped binary, not proof of
absence. Cross-vendor delegation works on all of them.

**What goal mode does not do is decide what counts as done — it asks the model.** That gap
gets closed in the goal text itself, not with machinery around the host:

```
/goal <objective, inside <scope>>. You have not met this goal until you have actually run
`<anchor>` in this session and seen it <exact result> - do not claim completion from
reasoning, and do not state <confidence claim> without that output. Do not conclude
<inference> from documents alone; reproduce it. State which turn you are on at the start of
each turn. Rewrite the Carry-over section before you finish. Stop after <N> turns even if
unmet, and say so.
```

Six clauses, one hole each: scope creep, claiming success from reasoning, inappropriate
confidence, inference beyond the data, losing count of the ceiling, and the loop never
learning. The same text pastes into all four hosts.

**A workflow script needs a workflow runtime.** Only Claude Code has one, so elsewhere the
Skill will not emit that shape — the file would be something nothing can run.

Artifacts live in the project's `.loops/`, not inside any tool's private directory: they are
project assets that belong in Git and may be read by whichever agent a teammate runs.

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

## The gate

On a host that exposes the events, three hooks install with the Skill and turn the anchor from
a sentence in a prompt into something that actually runs.

| Hook | Does | Can it block? |
|---|---|---|
| `Stop` | Runs the anchor every turn | **Yes, in exactly one case**: the anchor ran and was red |
| `SessionStart` | Re-injects the frozen spec and carried state after a restart | No |
| `PreCompact` | Records the carried state before the context is emptied | No |

**Three outcomes, not two.** An anchor that cannot run — missing command, not executable,
timed out — is **unknown**, not failed. A timeout measures elapsed time and has no access to
success or failure, so reporting it as either is how a mechanical gate starts lying. Unknown
lets the turn end and says the result is unverified.

**Six of the seven steps allow.** Ceiling reached, loop not progressing, anchor unrunnable,
anchor green, no anchor, no active loop — all let the turn end and say why. It refuses only
when it is certain.

### What it costs a project that never asked for one

Every hook's first act is one check: is there a `.loops/active` marker naming an artifact that
exists? Without one, nothing is read, nothing is written, no command runs — a process start
and a `stat`. That early exit is the only thing between an installed hook and an unrelated
project, so it is pinned from nine angles in `tests/test_loop_hooks.py`, including that an
inactive project executes no anchor and that a handler which raises still exits 0.

Escape hatches, neither of which needs the agent's cooperation: `rm .loops/active`, or
`LOOP_GRAPH_HOOKS_DISABLED=1`.

Registration is idempotent, backs up `settings.json` first, preserves every hook it does not
own, and `doctor` reports `missing` or `partial:<events>` if something later removes it.

`PostToolUse` is deliberately not registered — it fires once per tool call, and its value
duplicates what `SessionStart` injects. It gets added when a real run shows a loop retrying a
path its own lessons already ruled out.

## The validator

```bash
python3 scripts/validate_artifact.py .loops --json
```

It observes facts and nothing else: file pairing, required sections, every shape carrying
an anchor, `meta` being a pure literal and the first statement, phases declared before use,
delegation targets that are actually registered, and JavaScript syntax. It never edits an artifact and it never judges
whether a topology is the right one — that part is the design, and design belongs to you
and the model, not to a template engine.

Its silence is not evidence that the design is right.

## Scope

**It stops at a document and Git.** One artifact, one decisions record, one carry-over
section, and version control. No directory tree, no derived index, no progress ledger, no
state machine, and no second copy of anything Git already holds. The shape resembles a
spec-driven development harness and that resemblance is a constraint, not an invitation:
harnesses that grew those parts have had to delete them again. Adding one requires naming a
question that neither the artifact nor `git log` can answer.

This Skill produces **executable artifacts** and is self-contained: it assumes no
neighbouring Skill is installed, and its hand-off spells out the command in full rather than
leaving another Skill to fill in the gap.

The loop's own boundary — what it may touch, which effects need approval — is one of the six
questions and belongs here. A broader authority model for an agent that is not a loop does
not: that gets answered directly, not wrapped in a loop. If you do happen to run
[agent-harness-design](https://github.com/rocky2431/agent-harness-design-skill) or
[agent-delegate](https://github.com/rocky2431/agent-delegate-skill), the eval set records
where each would take over — as `optional_skills`, never as a dependency.

## Sources

The guidance traces to primary sources, listed with URLs and a currency date in
[references/research-basis.md](plugins/loop-graph-design/skills/loop-graph-design/references/research-basis.md).
Anthropic's loop and multi-agent engineering posts are treated as doctrine; the July 2026
"graph engineering" essays are treated as argument.

The carry-over design rests on two papers, with what was taken and what was deliberately
left behind spelled out in
[references/evolution-and-scope.md](plugins/loop-graph-design/skills/loop-graph-design/references/evolution-and-scope.md):
**SKILL.state** ([arXiv 2608.26263](https://arxiv.org/abs/2608.26263)) for explicit carried
state over replayed history — including the finding that one five-field schema served 100
task instances — and **WikiSkill** ([arXiv 2608.27454](https://arxiv.org/html/2608.27454))
for persistent knowledge being the critical variable in skill evolution (48.7% → 63.7% in
their ablation). WikiSkill's machinery — inference agent, wiki maintainer, skill proposer,
gating against a validation set — is **not** adopted: it is a training framework, and a loop
designed with its owner in the room has no validation set.

## Tests

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

124 tests: the validator's rules, the status projection, the package surface, version
consistency across three files, every relative link in `SKILL.md` resolving, and the shipped
templates passing the shipped validator. Two are safety tests — that an anchor is never
executed unasked, and that the validator never edits an artifact.

## License

MIT
