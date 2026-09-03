# Research basis

Current as of 2026-09-03. Claims in this Skill trace to these sources; re-check them
before treating any specific number as still true.

## Loop engineering (primary)

- Anthropic, *Getting started with loops* — the four loop shapes, owner-defined success
  criteria, a separate agent for review, quantitative self-verification, scripts over
  reasoning for deterministic work.
  https://claude.com/blog/getting-started-with-loops
- Anthropic, *Building effective agents* — "agents are typically just LLMs using tools
  based on environmental feedback in a loop"; the workflow patterns beneath it.
  https://www.anthropic.com/engineering/building-effective-agents
- Anthropic, *Effective context engineering for AI agents* — context as the scarce
  resource across iterations.
  https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

## Long-running harnesses (primary)

- Anthropic, *Effective harnesses for long-running agents* — the closest published work to
  what this Skill builds. States plainly that **"compaction isn't sufficient"**, which is
  the whole basis for `## Carry-over`. Their artifacts: a progress log, a structured
  `feature_list.json` of requirements all initially failing, descriptive commits, and an
  `init.sh`. Discipline: one feature per session, and "Only mark features as 'passing'
  after careful testing". Names the failure this Skill's anchor exists for: "Absent
  explicit prompting, Claude tended to make code changes but would fail to recognize that
  the feature didn't work end-to-end" — and lists "relying on unit tests without
  end-to-end validation" as an anti-pattern.
  https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Anthropic, *Harness design for long-running application development* — Planner /
  Generator / Evaluator, with the generator later **removed** as the model improved. Two
  things taken directly: the **sprint contract**, where generator and evaluator agree what
  "done" means for a chunk before any code is written; and **context anxiety**, a named
  failure where a model wraps up early as it approaches what it believes is its context
  limit. Also the criterion this Skill's own mechanism audit uses: "every component in a
  harness encodes an assumption about what the model can't do on its own, and those
  assumptions are worth stress testing."
  https://www.anthropic.com/engineering/harness-design-long-running-apps

## The arithmetic of long tasks

- Ord, *Is there a half-life for the success rates of AI agents?* (arXiv 2505.05115) — a
  constant per-minute failure rate fits the data, so success decays **exponentially** with
  task length, because long tasks "involve increasingly large sets of subtasks where
  failing any one fails the task". The consequence for this Skill: success is exponential
  in the size of one turn, so halving the work per turn more than doubles the chance of a
  green turn. The turn ceiling decides when a run gives up; the turn *size* decides
  whether it can succeed at all.
  https://arxiv.org/abs/2505.05115
- METR, *Time Horizon 1.1* — near-100% success on tasks under roughly four minutes of
  human time, under 10% beyond roughly four hours; the 50%-reliability horizon doubling
  every 4-7 months. Re-check the numbers before quoting them.
  https://metr.org/blog/2026-1-29-time-horizon-1-1/

## Single writer, and the case against multi-agent

- Cognition, *Don't Build Multi-Agents* — the argument this Skill's phase-split refusal
  rests on: fanned-out subagents each act on a partial view and make conflicting implicit
  decisions. Its positive rule endorses the triad exactly: **"extra agents are fine when
  they contribute intelligence, reading and analyzing, but the writes, the actions that
  change state, should stay single-threaded."** That is M editing while R and C only read.
  https://cognition.com/blog/dont-build-multi-agents

## Context engineering in production

- Manus, *Context Engineering for AI Agents* — three practices that map onto this Skill's
  document system: **recitation** (rewriting a todo file so the objective is pushed into
  the model's most recent attention), **the file system as the ultimate context** (which
  is why artifacts live in the project rather than a tool's private directory), and
  **keeping errors in context** rather than cleaning them away. Note the scope difference
  on the last one: Manus means one session's own context, while `### Lessons` is what gets
  carried *between* sessions and is therefore pruned.
  https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus

## Cross-agent coordination

- Google, *Agent2Agent (A2A)* — an Agent Card advertising capability, and a named task
  lifecycle: `submitted / working / input-required / completed / failed / canceled /
  rejected`. The transport (HTTP, SSE, JSON-RPC) is the opposite of this Skill's
  text-protocol stance and is **not** adopted; the state vocabulary is what transfers, and
  `input-required` and `rejected` are two states a delegation package currently lacks.
  https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/
- OpenAI, *A practical guide to building agents* — guardrails as a **layered defense**,
  added "as you uncover new vulnerabilities" rather than up front; manager versus
  decentralized orchestration; and two triggers for human intervention, the first of which
  is this Skill's turn ceiling: **exceeding failure thresholds — set limits on agent
  retries or actions**.
  https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf

## Multi-agent cost and decomposition (primary)

- Anthropic, *When to use multi-agent systems (and when not to)* — 3-10x token overhead,
  the three justified conditions (context isolation, parallelization, specialization),
  context-centric rather than phase-centric decomposition, the verification subagent and
  its early-victory failure.
  https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them
- Anthropic, *How we built our multi-agent research system* — orchestrator-worker topology,
  about 15x tokens, token volume explaining most performance variance, self-contained
  worker task descriptions, synthesis kept in a single agent.
  https://www.anthropic.com/engineering/multi-agent-research-system
- Anthropic, *Patterns and problems in multiagent systems* — conformity and low variance
  between agents, epistemic brittleness, goal-incompatibility escalation, and the case for
  keeping a human deferral path.
  https://www.anthropic.com/research/multiagent-systems

## Graph engineering (community)

The term dates to July 2026; the practice does not. Treat these as argument, not doctrine.

- Carlos E. Perez, *From Loop Engineering to Graph Engineering?* — the four single-loop
  failures, the graph of loops, circularity, and the grounded-versus-ungrounded resolution.
  https://medium.com/intuitionmachine/from-loop-engineering-to-graph-engineering-d3ebeb08511c
- LangChain, *3 Years of Graph Engineering with LangGraph* — "a loop is just a directed,
  cyclic graph"; production agents need cycles; dynamic routing; nesting agents in nodes.
  https://www.langchain.com/blog/3-years-of-graph-engineering-with-langgraph
- Sangam Pandey, *Graph Engineering: When an Agent Loop Should Be a Graph* — routing
  decided at authoring time versus inference time, the per-run cost consequence, and the
  prefix-cache asymmetry.
  https://sangampandey.info/blog/graph-engineering-agent-loops-to-graphs

## Adversarial review

- *Adversarial Review* (arXiv 2608.18167) — the M/R/C triad this Skill's `## Verification`
  and delegation packages implement. Built one step at a time (zero-shot, self-refine, one
  reviewer, two reviewers, a five-agent panel, then AR), each step added to fix a measured
  failure of the last. Three findings carry the design: AR outperformed the five-agent panel
  using three agents; adding independent reviewers alone did not reliably improve results;
  and the naive protocol reproduced **false consensus**, which the three disagreement classes
  exist to break. It was evaluated as a portable pure-text protocol handed to an autonomous
  agent, with no orchestrator program — which is why this Skill emits text and not a DSL.
  https://arxiv.org/html/2608.18167
- Google Antigravity, *Teamwork: When AI Becomes a Research Partner* (2026-08-27) — a
  multi-agent framework for long-horizon work in which agents propose, critique and refine
  each other's output over hours or days. The line that endorses the shape here:
  "A pattern is a specification rather than an executable program. It contains no
  orchestration code of its own."
  Ships five patterns selected per task, and requires candidate changes to pass
  independent verification before a milestone is approved, with a Critic performing the
  independent review. URL and quotation re-verified 2026-09-04; an earlier draft of this file
  cited a mistyped URL.
  https://antigravity.google/blog/teamwork-when-ai-becomes-a-research-partner
  https://antigravity.google/docs/teamwork/

## Reflection and bounded memory

- Shinn et al., *Reflexion: Language Agents with Verbal Reinforcement Learning* (NeurIPS
  2023) — the Actor / Evaluator / Self-Reflection split, verbal feedback as a "semantic
  gradient", the credit assignment problem, and the episodic memory bound Ω "usually set to
  1-3". This is the basis for the `### Lessons` cap and for asking for a cause plus a next
  action rather than an event.
  https://arxiv.org/abs/2303.11366

## Design-time specification

- Yu and Zhao, *4D-ARE: 4-Dimensional Attribution-Driven Agent Requirements Engineering*
  (2026) — argues design-time specification is the higher-leverage intervention over runtime
  reasoning frameworks, and names three failures a specification must prevent:
  hallucination beyond data, scope creep, and inappropriate confidence. This is the basis
  for splitting the boundary question into scope, confidence, and inference.
  https://arxiv.org/pdf/2601.04556
- Wang et al., *Plan-and-Solve Prompting* (ACL 2023) — devise a plan, then execute it;
  aimed at missing-step errors in zero-shot chain of thought.
  https://arxiv.org/abs/2305.04091

## Failure taxonomy

- Cemri et al., *Why Do Multi-Agent LLM Systems Fail?* — 14 failure modes catalogued
  across seven multi-agent frameworks.
  https://arxiv.org/abs/2503.13657
