# Evolution and scope

Read this when designing recovery state or maintaining the skill from observed
failures. Ordinary execution needs the goal and its linked evidence, not a new
knowledge-maintenance workflow on every turn.

## Why a long task needs carried state

A resumed or compacted host may retain a summary and still omit a decisive fact.
Carry-over makes the current objective, unresolved work, useful failed approaches
and evidence locations recoverable without replaying the entire conversation.
It does not replace the evidence it summarizes, and a recent summary is not proof
that an external fact remains current.

SKILL.state replaces append-only conversation history at the **runtime** boundary:
each step receives the immutable specification, current state and latest observation.
Its bounded-context result depends on the state being sufficient and bounded. The
five-field schema used across 100 InterCode CTF instances was authored for that
domain. UltraGoal borrows the separation of specification and state; a skill cannot
control how every host assembles context or promise the paper's complexity bound.

WikiSkill separates raw experience, consolidated knowledge and executable skills.
Its default arrangement gives the wiki to the skill proposer rather than to the
training rollout's inference agent. The reported 48.7% to 63.7% ablation is a
particular Gemini-3.5-Flash, four-benchmark comparison, not a predicted gain here.
It supports testing how experience improves a skill, not making every stored
lesson a rule. Neither paper establishes our four-host unattended reliability.
See [research-basis.md](research-basis.md) for sources and limits.

## Keep evidence, current state and history distinct

| Material | Existing home | Update rule |
|---|---|---|
| Intent, acceptance and authority | frozen goal terms and decisions | change only with the appropriate owner authority |
| What to do with current knowledge | Carry-over | rewrite; retain links to facts still needed for recovery |
| What was actually observed | gate events, native receipts/traces, required review archives and actual inputs/outputs | retain enough original material to check material claims |
| What may transfer to another attempt | the project's existing documentation or knowledge page | state conditions, evidence and what would invalidate the lesson |
| A reusable operating instruction | versioned skill and references | change through the maintenance comparison below |

Git records **committed** revisions. `git log -p <slug>.goal.md` does not recover an
uncommitted attempt or an overwritten Carry-over. Commit only when authorized;
without that authority, keep necessary observations in the existing event/evidence
files. Do not invent one commit per turn or call an incomplete local log full history.

Keep the live state compact. Three lessons and eight state entries are useful
review prompts, not validity thresholds. A fourth necessary lesson may stay; move
long explanations to an existing evidence or project document and link them.
Reflexion's small experimental memory is not a universal limit. Pruning a summary
must not delete the only evidence of a failed attempt or a required review.

## Promote knowledge only through a tested change

This is a **skill-maintenance** loop, used when a change is requested or otherwise
authorized. A business run may revise its project state and propose a lesson; it
does not gain authority to edit the installed skill or the owner's global settings.
Reuse existing documents, Git diffs and executable probes; no permanent maintainer
agent, parallel knowledge tree or general evolution runtime is required.

1. **Retain the observation.** Link the actual failing input, output, event or
   native trace and its relevant environment/version. Keep observed behavior
   separate from the author's causal explanation. For a sensitive source, retain
   an authorized local reference rather than copying it into public documentation.
2. **Write conditional project knowledge.** State the suspected cause, the context
   where it applies, the next action and a condition that would disprove or retire
   it. An observation that a command failed is not yet proof of why it failed.
3. **Propose a minimal skill change.** Name the reproduced failure it addresses and
   the valid behavior it might reject. Keep a baseline diff so that the candidate
   can be removed without reverting unrelated work. Do not silently add a universal
   gate from one example or one paper's parameter.
4. **Compare on held-out work.** Reuse the relevant existing regression tests and
   business probe; include a task or counterexample not used to write the rule.
   Keep the task semantics, model/host version, tools and authorized total budget
   comparable. Record actual completion, false acceptance/rejection, recovery,
   authority/effect behavior and cost where relevant. Missing model runs, quota
   failures and unfinished trials stay visible; structural checks alone do not
   establish a behavioral improvement.
5. **Promote or roll back the candidate.** Keep the change only to the extent the
   evidence supports it. When it regresses, remove that candidate and retain the
   failed experiment's evidence and narrower lesson. Correct disproved knowledge;
   preserving an experiment does not mean preserving a false conclusion. Version,
   commit, install and publish only with their existing authorizations.

The maintenance result belongs beside the existing probe or project review and
records the candidate/baseline, evidence locations, held-out cases, observed
results, limitations and decision. It is not another per-turn ledger. A new model
or host version can invalidate a workaround; repeat the relevant comparison rather
than keeping obsolete constraints forever.

## Scope remains skill, scripts and hooks

The model chooses methods and routing within the accepted goal. Existing scripts
record narrow facts and check the evidence contract. The host supplies continuation,
task identity, permissions and isolation; external services supply effect readback
and deduplication. A state file or a Stop refusal cannot manufacture those powers.

Add a helper only after an observed failure needs a fact the current artifacts or
native tools cannot provide reliably. Keep optional planning and project knowledge
in their existing homes. A useful change should make the next action or verification
more reliable, not merely add another place to repeat the same account.
