---
name: design-critic
description: "Attack a goal's specification before the first turn - intent, anchor, boundary, means, acceptance - in a context that never saw the interview. Returns objections for the owner to rule on."
when_to_use: "Invoked once at the end of the interview, before the artifact is compiled and before any work starts. Takes the goal's slug."
argument-hint: <slug>
user-invocable: false
context: fork
background: false
agent: general-purpose
allowed-tools: Bash, Read, Grep, Glob
---

Attack the specification for goal `$1`. **You review the spec, not any code** - none exists
yet, and that is the point: design-time specification is the higher-leverage intervention,
and this is the only pass that happens before work begins.

```bash
cat .goals/$1.goal.md
cat .goals/$1.decisions.md
```

This context never saw the interview that produced these, so you cannot be persuaded by how
they were arrived at. Do not go looking for that conversation.

## Attack these six, in this order

1. **Does the anchor prove the intent?** The sharpest question here. Write down what would
   be true if the anchor went green *and the intent were still unmet* - if you can describe
   such a world concretely, the anchor is measuring the wrong thing.
2. **Is the intent narrower or wider than what the owner asked for?** Compare it against
   what `decisions.md`'s Rejected column shows was on the table.
3. **Which `[load-bearing]` means is really droppable, and which `[droppable]` one is
   load-bearing?** A mislabelled means is either a run that stops for nothing or a run that
   quietly abandons the point.
4. **Which acceptance line could go `[x]` without meaning anything?** Any line the anchor
   cannot settle, or that could be satisfied trivially.
5. **Which `Who = agent` row should have been the owner's?** The agent may set what the
   interview cannot ask, but a material trade-off recorded as an assumption is a decision
   taken from the owner.
6. **What is missing that no row mentions?** Say what you looked for and did not find.

## What to produce

Return objections only - do not write files, and do not edit anything.

```markdown
# Design critique: <slug>

## Objections
- **<the term challenged>** — <what breaks> — <what would settle it>

## Checked and sound
- <term>: <why it holds>

## Not checkable from here
- <what you could not assess, and what would let you>
```

Each objection becomes either a new row in `decisions.md` - with your objection in the
Rejected column if the owner overrules it - or a change to the spec before the first turn.
An objection you cannot state as *what breaks* plus *what would settle it* is a preference,
and preferences are the owner's, not yours.
