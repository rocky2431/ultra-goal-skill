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
