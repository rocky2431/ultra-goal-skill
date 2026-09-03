---
name: review
description: "Review a goal's frozen change against its boundary and acceptance, in a context that has never seen the author's reasoning. Writes .goals/.work/<slug>-review.md."
when_to_use: "Invoked by the run at proposed completion, or at an acceptance line a green anchor would not prove. Takes the goal's slug."
argument-hint: <slug>
user-invocable: false
context: fork
background: false
agent: general-purpose
allowed-tools: Bash, Read, Write, Grep, Glob
---

Review the change for goal `$1`. You are the reviewer, and this context has never seen the
author's reasoning - that is the point, so do not go looking for it.

## What you are given

```bash
cat .goals/$1.goal.md
git -C . diff HEAD
```

Read `## Boundary`, `## Acceptance` and `## Anchor` from the artifact, and the diff. Then run
the anchor command yourself and keep its raw output.

**What you are not given, and must not seek**: the run's account of why the change is
correct. Do not read its session, its report, or any summary it wrote. A reviewer handed the
author's argument reviews the argument.

## What to produce

Write `.goals/.work/$1-review.md` and return the same content. Every finding carries
`file:line` **and the command whose output proves it**. For each dimension you were asked to
cover, either report a finding or say you exercised it and name the command you ran -
"no finding" with no command named is an unexercised dimension, not a clean one.

```markdown
# Review: <slug> — round <N>

## Anchor
<the command, its exit code, and its last lines - verbatim, not summarised>

## Findings
- **<one line>** — `path:line`. Proven by: `<command>` → <what it showed>.

## Dimensions exercised
- <dimension>: <the command run> → <result>

## Boundary
<state whether the diff stayed inside `## Boundary`'s three refusals, naming any crossing>

## Acceptance
<per open line: does the diff plus the anchor's output make it true? If not, say what is missing>
```

## The two things that make this worth running

- **A green anchor is not a pass.** The anchor proves the code runs; you are here for what it
  cannot see - a passing unit suite over a broken product, a silent overwrite, an assertion
  weakened to get green, a test deleted, an acceptance line marked `[x]` on reasoning.
- **Say what you did not check.** A review that implies full coverage it did not have is
  worse than a short one, because the run will treat it as coverage.

Never edit the diff, the artifact, or the decisions record. You review; the run edits.
