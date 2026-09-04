# Claude Code — pre-registered readings, before seeing any implementation

Written 2026-09-04, after dispatching the mission to zCode and **before** reading a line of
its output or of Codex's adapted tree. The point is the same as the blind judge in this
project's own design: a reviewer who reads the author's account first reviews the account.
These are the facts I went and got myself, so that agreement later means something.

Method: grep the running binaries, not the vendor docs, and quote what the code does.
Where the two disagree the docs win as *contract* — but a binary shows what will actually
happen on this machine tonight.

## Claude Code 2.1.260 — the continuation budget

```js
let Vd = a.CLAUDE_CODE_STOP_HOOK_BLOCK_CAP ?? 8;
if (Vd > 0 && qd > Vd) return … `A hook blocked the turn from ending ${qd}
  consecutive times — overriding and ending turn. ` +
  "For Stop/SubagentStop hooks, check stop_hook_active in the input and return
   success while it's true. Set CLAUDE_CODE_STOP_HOOK_BLOCK_CAP to raise this limit."
```

Source: `/Users/rocky243/.local/share/claude/versions/2.1.260`, window around
`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`. Nearby telemetry keys: `tengu_stop_hook_block_count`
with `{count, is_subagent, hit_max_turns, hit_cap, goal_active}`, and `nudge_exhausted`.

**Reading.** Default 8 consecutive blocks, raisable by environment variable. The
`stop_hook_active` advice is inside the cap-exceeded warning, so it is post-mortem advice
and not the general contract. `goal_active` in the same telemetry payload says the host
tracks native goal mode and Stop blocks together, which is evidence they compose rather
than substitute.

**What I will hold the implementation to.** A per-host budget, the host cap as backstop
rather than as the plan, and the gate's own reason as the last word — not the host's
"overriding and ending turn".

## Kimi Code — the hook output schema, verbatim

```js
HookSpecificOutputSchema = looseObject({
  message: OptionalStringSchema,
  permissionDecision: unknown().optional(),
  permissionDecisionReason: unknown().optional()
}).optional();
HookJsonOutputSchema = looseObject({
  message: OptionalStringSchema,
  hookSpecificOutput: HookSpecificOutputSchema
});
```

and the branch that acts on it:

```js
if (hookSpecificOutput?.permissionDecision !== "deny") return result;
return { action: "block", message: result.message,
         reason: hookSpecificOutput.permissionDecisionReason, structuredOutput: true };
```

Source: `/Users/rocky243/.kimi-code/bin/kimi` (kimi 1.49.0 per `agent-delegate list`).
String counts in that binary: `hookSpecificOutput` 11, `SessionStart` 109, `PostCompact` 9,
**`additionalContext` 0**, `stop_hook_active` 0, `STOP_HOOK_BLOCK_CAP` 0.

**Readings, and what each is worth.**

1. **Our deny already works on Kimi** — because the gate emits both documented forms, and
   `hookSpecificOutput.permissionDecision: "deny"` plus `permissionDecisionReason` is
   exactly what this branch honours. The decision to satisfy two conflicting authorities
   instead of picking one paid for itself on a host neither authority was about.
2. **Our allow paths say nothing at all on Kimi.** `_allow` emits `systemMessage`, and
   Kimi reads `message`; the obligation rides in `additionalContext`, which does not exist
   in this binary. So on Kimi today: the block speaks, and green / unknown / ceiling /
   not-progressing are silent. That is the adaptation gap I expect to be the largest.
3. **`additionalContext` absent from the whole binary** independently corroborates the
   claim that Kimi cannot inject context from `SessionStart` / `PostCompact`. Absence of a
   string is not proof — a key could be built dynamically — but for a JSON field name read
   by a zod schema, it is close.
4. **No `stop_hook_active` and no block cap string.** So Kimi's continuation limit, if it
   has one, is enforced somewhere I have not found. I am *not* asserting "one per turn";
   that number came from Codex's document and I have not verified it. Whoever claims it
   owes the code path.

## What I have not verified, and will not pretend to

- **zCode**: no binary on this machine (`which zcode` → not found), so every zCode claim in
  this mission is second-hand to me. Its Stop limit of 3, its lack of `PreCompact`, its
  `process` versus `command` handler split — all unverified by me.
- **Codex**: `codex.js` is a 7 KB launcher, so the real implementation is elsewhere; I have
  not read it. Its event table and its "no `PostToolUseFailure`" claim are unverified by me.
- **Kimi's continuation limit**, as above.

## Predictions, recorded so they can be wrong

1. The largest real defect after 4.1 and 4.2 will be **the allow paths going silent on
   Kimi**, not the manifests.
2. A per-host continuation budget will need a place to live that the run cannot edit —
   which puts it with `FROZEN_SECTIONS` in `goal_hooks.py`, not in the artifact. If the
   implementation makes it artifact-declared, I will argue it is a threshold the run can
   raise to escape its own ceiling.
3. Counting anchor checks as turns (the owner's ruling A) will break `--audit`'s join on
   the commit subject's `turn <N>`, and the honest repair is for the gate to tell the run
   which check number it is on, in the deny reason, so the claim and the measurement share
   one source.
4. Something in the four manifests will still register an event its host does not document,
   because the current `hooks.json` is shared by all four and the fix requires splitting it.
