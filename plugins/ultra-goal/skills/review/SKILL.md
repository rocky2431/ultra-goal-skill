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

Review the change for goal `$ARGUMENTS`. You are the reviewer, and this context has never seen the
author's reasoning - that is the point, so do not go looking for it.

## What you are given

```bash
cat .goals/$ARGUMENTS.goal.md
# The accepted review.inputs bounds the review, including outside Git.
base=$(cat .goals/$ARGUMENTS.baseline 2>/dev/null)
if [ "$base" = none ] || [ -z "$base" ]; then
  printf '%s\n' "ultra-goal: no review range can be formed - this run recorded no git baseline, so no Git diff is available. Use the bounded review.inputs from the accepted contract; without either scope, report review unavailable."
else
  git -C . merge-base --is-ancestor "$base" HEAD || printf '%s\n' "ultra-goal: baseline $base is not an ancestor of HEAD - history moved under the run and the recorded range is unreliable. Report that instead of trusting this diff."
  git -C . diff "$base"
  git -C . status --porcelain
fi
```

Read the declared `review.inputs` in full. They are the required review's scope even
outside Git. A Git diff, when available, additionally shows the change since arming,
including authorized intermediate commits. `status --porcelain` identifies untracked
files the diff omits. Do not attribute pre-existing changes to this run without evidence.
A missing Git baseline means the diff is unavailable; it does not invalidate a review
whose accepted inputs are bounded. If neither scope exists, report review unavailable.
A non-ancestor baseline makes that diff unreliable; do not treat it as a clean range.

Read `## Boundary`, `## Acceptance`, `## Anchor` and `## Verification` from the artifact,
and the diff. Then run the anchor command yourself and keep its raw output.

`## Verification`'s JSON block tells you what this review is *for*. Its `covers` map names
the acceptance IDs settled by `review` rather than by the anchor — those are the ones you
must reach a verdict on. If it carries a `review` contract, note its `path`, its `verifiers`
list and its bounded `inputs`: you may be writing the receipt the completion gate reads.

**What you are not given, and must not seek**: the run's account of why the change is
correct. Do not read its session, its report, or any summary it wrote. A reviewer handed the
author's argument reviews the argument. If a report is itself an accepted deliverable
in `review.inputs`, review its substantive claims against original evidence; do not omit
it merely because the generator wrote it.

## What to produce

Write `.goals/.work/$ARGUMENTS-review.md` and return the same content. Every finding carries
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

## The receipt, when this review is a required one

A markdown report is what a human reads. When `## Verification` carries a `review`
contract, the gate reads a **JSON receipt** instead, and it is yours to write — the run may
not write it for you. Four things have to be true before you do:

1. **Your identity is approved.** The `verifier` you write must appear in the contract's
   `verifiers` list.
2. **Your session is your own.** Resolve this fork's actual native session ID and compare it
   with the `session <id>` line in `.goals/active` and the prior bindings in
   `.goals/$ARGUMENTS.events.jsonl`. A former executing session is not independent either. If they match, or you cannot resolve one
   at all, **do not write a receipt**: say in your report that this review cannot satisfy the
   required-review condition from here, so the run has to route it to a separate session or
   another vendor. A copied or invented ID is a forged receipt.
3. **The digest is one you computed.** Get it yourself; it binds the frozen terms as well as the contract's `inputs`:

   ```bash
   root="${CLAUDE_PLUGIN_ROOT:-${ZCODE_PLUGIN_ROOT:-${KIMI_PLUGIN_ROOT:-$PLUGIN_ROOT}}}"
   python3 "$root/skills/ultragoal/scripts/goal_run.py" review-inputs $ARGUMENTS --root .
   ```

4. **The verdict is what you found.** `pass` only when the acceptance IDs you cover are
   actually met on these inputs. Unresolved findings mean a non-pass verdict — never a pass
   with caveats in the prose.

Then write the contract's `path` (and keep the markdown report beside it):

```json
{
  "verifier": "<an identity from the contract's verifiers list>",
  "session_id": "<this fork's own native session id>",
  "input_digest": "<the SHA-256 review-inputs returned>",
  "covers": ["<each acceptance id mapped to review>"],
  "verdict": "pass",
  "evidence": "What you checked, what you observed, and what you could not settle.",
  "checks": {
    "<acceptance-id>": {
      "claim": "<the concrete conclusion independently reached>",
      "evidence": [{"path": "<file under review.inputs>", "quote": "<exact excerpt>"}]
    }
  }
}
```

Provide a `checks` entry for every ID assigned to review. Quote the actual current
inputs, including the original supporting evidence for material report claims.
Independently check figures, classifications, causal explanations and limitations;
an existence check or a plausible explanation is insufficient. The gate checks
references and freshness, not whether a quotation logically supports your verdict.

If the inputs change after you sign, the receipt is stale by construction and the gate will
say so. That is the run's problem to solve by asking for a fresh review, not yours to
pre-empt by signing loosely.

## The two things that make this worth running

- **A green anchor alone does not satisfy a required semantic review.** The anchor proves the code runs; you are here for what it
  cannot see - a passing unit suite over a broken product, a silent overwrite, an assertion
  weakened to get green, a test deleted, an acceptance line marked `[x]` on reasoning.
- **Say what you did not check.** A review that implies full coverage it did not have is
  worse than a short one, because the run will treat it as coverage.

Never edit the diff, the artifact, or the decisions record. You review; the run edits.
