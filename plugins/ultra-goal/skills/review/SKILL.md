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
base=$(cat .goals/$1.baseline 2>/dev/null)
if [ "$base" = none ] || [ -z "$base" ]; then
  printf '%s\n' "ultra-goal: no review range can be formed - this run recorded no git baseline, so there is no bounded change to review. Report the review as unavailable rather than reviewing an unbounded tree."
else
  git -C . merge-base --is-ancestor "$base" HEAD || printf '%s\n' "ultra-goal: baseline $base is not an ancestor of HEAD - history moved under the run and the recorded range is unreliable. Report that instead of trusting this diff."
  git -C . diff "$base"
  git -C . status --porcelain
fi
```

The diff starts from the revision recorded when the gate was armed — the run commits once
per turn, so `git diff HEAD` would show only the leftovers and you would be reviewing a
change you never saw. `status --porcelain` lists the untracked files a diff cannot show;
read any that the boundary suggests are part of the work. A `none` or missing baseline
means the project had no Git when the gate was armed: there is no range, and the honest
report is "review unavailable", not a once-over of the working tree — a review of an
unbounded tree reads as coverage it does not have. A baseline that is not an ancestor of
HEAD means history was rewritten under the run; say the range is unreliable. Uncommitted
changes that predate the run also fall inside the range: attribute them with `## Boundary`
rather than assuming the run made them.

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
