# Evolution and scope

Why the carry-over boundaries in SKILL.md are drawn where they are.

## Why an unattended loop needs carried state at all

A `/loop 1w` wakes seven days later with an empty context. Its only options are to rebuild
history from git logs and PRs, or to carry a small amount of state forward.

Rebuilding is worse on three counts. It costs tokens every iteration for information that
did not change. It is unreliable, because a git log records what was committed rather than
what was attempted and abandoned. And it silently loses the most valuable thing the loop
learned: which paths are already proven dead. A loop that cannot see its own failed
attempts retries them, and believes each time that it is the first attempt.

The research support is direct. SKILL.state (arXiv 2608.26263) replaces append-only
conversational history with an explicit mutable execution state — the model receives the
immutable specification, the current state, and the latest observation, and intermediate
reasoning is discarded after each validated update. That holds prompt size flat instead of
growing quadratically. Two findings matter here:

- The schema is small and reused. Across 100 InterCode CTF instances the agent worked from
  a single five-field schema — `discovered_flags`, `tested_hypotheses`, `active_files`,
  `working_dir`, `cmd_summary` — authored once per domain, not per task. So "a schema is too
  heavy for this" is not true at the size we need.
- `tested_hypotheses` exists specifically to keep the model from repeating failed commands.
  That is the same failure an unattended loop has, one week apart instead of one step apart.

WikiSkill (arXiv 2608.27454) makes the complementary point about accumulation: separating
raw experience, consolidated knowledge, and executable skills, and letting knowledge persist
across iterations, raised average benchmark performance from 48.7% to 63.7% in their
ablation. Their conclusion is that the persistent layer is the critical variable, not the
skill edits themselves.

What we deliberately do **not** take from WikiSkill is its machinery: an inference agent, a
wiki maintainer, a skill proposer, and a gating-and-rollback mechanism scored against a
validation set. That is a training framework for automatic skill evolution. A loop designed
with an owner in the room has no validation set and needs no proposer. The carry-over
section is the one part of it that survives contact with our scale.

## Why history belongs to Git and not to the document

It is tempting to have the document record each iteration, so the evolution is visible.
Version control already does that, better:

- `git log -p <slug>.goal.md` shows every change with its before and after. That *is* the
  evolution, at full fidelity, with no effort.
- `git log --oneline <slug>.goal.md` shows one line per iteration — the trajectory.
- The document itself then only has to answer one question: what is true right now.

Recording iterations inside the document produces a second copy of what Git holds, and that
copy grows without bound. A carry-over section that only ever grows has become a log, and a
log is read by nobody and trusted by nobody after the third page.

The full execution trace is a third thing again, and it belongs nowhere near either. One
iteration's raw trace is tens of thousands of tokens of tool calls. Committing that would
bloat the repository to store something no human will read. One line in a commit message
carries what is actually needed.

## Why lessons stay in the project

A loop's carried state is true of one repository. `@types/node` 22 breaking a tsconfig is a
fact about this project's module resolution, not about TypeScript. Promoting it to user-level
configuration would apply one project's dead end to every project, including the ones where
that path is the correct answer.

The three layers exist because they have different lifetimes and different owners:

| Layer | Holds | Changes when |
|---|---|---|
| This Skill | the criteria — what makes a loop grounded | the Skill is versioned and released |
| The owner's configuration | standing preferences that are true across their projects | the owner decides they are |
| The project, beside the artifact | what this loop learned | the loop runs |

Arrows point down only. The Skill never reads the project's carry-over; the project never
writes the owner's configuration. A Skill that accumulated per-project lessons into itself
would ship one user's history to everyone who installed it.

## Why the shape stops at a document and Git

The structure here — an immutable target, revisable details, a project-scoped knowledge
layer, history in version control — is the skeleton of a spec-driven development harness.
The resemblance is a constraint, not a licence to grow the rest of one.

Harnesses that added a directory tree, a derived index, a progress ledger, and a state
machine have had to delete them again: the derived copies drifted from the artifacts they
described, and the maintenance cost outlived the benefit. Every one of those parts answers a
question that either the artifact or `git log` already answers.

So the shape is fixed at: one artifact, one decisions record, one carry-over section, and
Git. Adding a part requires naming a question none of those four can answer.
