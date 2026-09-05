# Research basis

Rechecked 2026-09-05. These sources describe particular systems and experiments;
they are evidence to test against this task, not universal operating rules. Keep
the source's model, task, version and comparison when quoting a result. The
project's transfer judgments and implementation guarantees are separate claims.

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

- Anthropic, *Effective harnesses for long-running agents* (2025-11-26) — progress
  notes, an initially failing feature list, environment initialization and actual
  functional checks helped its application-development agents cross context windows.
  One feature per session was an experimental response to that model taking on too
  much, not a rule for every goal. Compaction alone did not preserve everything
  needed for recovery; that does not mean compaction empties the context. Commits
  in their setup do not grant commit authority in ours.
  https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Anthropic, *Harness design for long-running application development* (2026-03-24)
  — Planner / Generator / Evaluator remained; context resets and later sprint
  segmentation were removed as the models improved. The generator was not removed.
  Agreeing on observable acceptance before implementation transfers; fixed sprints
  do not. The evaluator needed calibration against human judgment, and the last
  iteration was not necessarily the best. Re-test whether each added component
  still addresses a demonstrated weakness.
  https://www.anthropic.com/engineering/harness-design-long-running-apps
- OpenAI, *Harness engineering* (2026-02-11) and *Run long horizon tasks with
  Codex* — short entrypoints route to maintained repository knowledge; a stable
  specification, revisable plan, executable environment and real feedback support
  sustained work. These are case studies, not a universal entrypoint line limit
  or a measured unattended reliability rate.
  https://openai.com/index/harness-engineering/
  https://developers.openai.com/blog/run-long-horizon-tasks-with-codex

## The arithmetic of long tasks

- Ord, *Is there a half-life for the success rates of AI agents?* (arXiv 2505.05115)
  — analyzes an exponential relationship between task length and success in the
  studied data. Human task duration is not a host turn. Even assuming
  `p(t) = exp(-lambda*t)`, halving length gives `sqrt(p(t))`, not universally more
  than twice the success rate. Two independently required halves still have joint
  success `p(t)` without another change. Our inference: decomposition needs a
  concrete isolation, feedback or recovery benefit; a smaller turn alone proves none.
  https://arxiv.org/abs/2505.05115
- METR, *Time Horizon 1.1* — measures task horizons against human completion time.
  Use the dated model and reliability threshold when interpreting a horizon; this
  is not a per-turn budget recommendation or a promise for arbitrary project work.
  https://metr.org/blog/2026-1-29-time-horizon-1-1/

## Shared context and concurrent work

- Cognition, *Don't Build Multi-Agents* (2025-06-12) — warns that agents with partial
  context can make conflicting implicit decisions; the author qualifies this by
  the capabilities then available. Our application is to coordinate shared
  decisions and resources. Independent writes with explicit ownership and an
  integration check can run in parallel. The earlier purported quotation about
  all writes staying single-threaded was not found in the original and is withdrawn.
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
  `input-required` requires an explicit missing input. Silence or a lost response
  establishes only an unconfirmed state until the native task can be inspected.
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
  its early-victory failure. The multiplier is the authors' equivalent-task
  comparison against a single agent, not this project's budget rule.
  https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them
- Anthropic, *How we built our multi-agent research system* — orchestrator-worker
  topology and self-contained worker missions. The reported approximately 15x
  token use is relative to ordinary chat (agents were about 4x chat in the same
  discussion), not 15x a single agent. These observations concern their research
  workload; useful parallelism depends on task structure and total cost.
  https://www.anthropic.com/engineering/multi-agent-research-system
- Anthropic, *Patterns and problems in multiagent systems* — conformity and low variance
  between agents, epistemic brittleness, goal-incompatibility escalation, and the case for
  keeping a human deferral path.
  https://www.anthropic.com/research/multiagent-systems

## Graph engineering (community)

These essays discuss graph engineering. Treat their framing as argument, not doctrine.

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
  gradient", the credit assignment problem, and a small episodic memory used in
  its experiments. The usual capacity of 1–3 was a context-budget choice, not
  evidence that a fourth necessary lesson makes a goal invalid. Transfer the causal
  reflection and selective retrieval; keep compactness advisory and preserve the
  evidence behind a pruned summary.
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
  across seven multi-agent frameworks, including missing information, premature
  termination and inadequate or incorrect verification. A reviewer's presence
  alone is not proof of adequate acceptance.
  https://arxiv.org/abs/2503.13657

## State, knowledge and skill updates

- *SKILL.state: Scalable Long-Horizon Agent Skills*, v2 — the runtime constructs
  each step from immutable specification, mutable state and latest observation.
  Its bounded-context result depends on sufficient, bounded state; it is not a
  property a skill obtains merely by writing Markdown. A five-field InterCode CTF
  schema reused across 100 instances is a domain example, not a universal schema.
  https://arxiv.org/html/2608.26263v2
- *WikiSkill: Compiling Agent Experience into Persistent Knowledge for Skill
  Evolution*, v1 — separates raw evidence, accumulated knowledge and proposed
  skill changes, accepting or rolling back changes using validation. The
  48.7% to 63.7% ablation is a Gemini-3.5-Flash average over four benchmarks under
  specific wiki-access settings, not this skill's expected gain. It did not
  establish multi-hour unattended operation. We reuse a small maintenance loop
  in `evolution-and-scope.md`, not its always-running agent arrangement.
  https://arxiv.org/html/2608.27454v1

## Recovery and evaluation boundaries

- LangGraph, *Checkpointers* and *Interrupts*, and Temporal, *Activity Definition*
  — recovery can replay work after a saved boundary. An effect may complete before
  its acknowledgment is saved; the target service must implement idempotency or
  provide a way to inspect the outcome. Our existing events record started and
  settled verification; they are not an external exactly-once executor.
  https://docs.langchain.com/oss/python/langgraph/checkpointers
  https://docs.langchain.com/oss/python/langgraph/interrupts
  https://docs.temporal.io/activity-definition#idempotency
- *SkillsBench*, v4 — compare skills on the same tasks and model/harness settings.
  Benefits vary; shorter or more elaborate instructions need measurement rather
  than a universal module count. *Towards a Science of Scaling Agent Systems*,
  v3, likewise finds that decomposition and coordination costs affect the value
  of additional agents. *Tau-bench* evaluates repeated success and notes that
  correct end state can still conceal unauthorized intermediate actions.
  https://arxiv.org/abs/2602.12670v4
  https://arxiv.org/abs/2512.08296v3
  https://arxiv.org/abs/2406.12045
