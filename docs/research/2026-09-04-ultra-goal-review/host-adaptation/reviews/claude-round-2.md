# Claude Code — round 2 review of `912bab3..HEAD`

Blind order again: suite first, then the diff, then §8.1.

```
$ python3 -m pytest tests/ -q
347 passed in 37.43s
```

332 at round-1 close, so +15. Four implementation commits, 928 insertions across 20 files.

## My round-1 findings

**F-1 · Kimi's Stop has no allow-channel — CLOSED, by the repair I named.**
`goal_prompt_submit.py` now carries the last verdict, not only a pointer: it holds the text
"still red and this host's continuation budget was spent - the run …". Kimi's documented
channels are `PreToolUse`, `Stop` and `UserPromptSubmit`; the gate's allow paths could not
reach the first two, so the third is the only place left, and it is now used. This is the
fix my round-1 addendum asked for after the vendor's reference showed my first suggestion
(emit `message`) was aiming at an undocumented affordance.

**F-4 · Kimi's undeliverable `SessionStart` — CLOSED.** `kimi.plugin.json` now registers
`Stop`, `PreCompact`, `PostToolUseFailure`, `UserPromptSubmit` and no `SessionStart`.
Verified: `python3 -c` over the manifest. `PreCompact` correctly stays, because it records
an event and does not depend on a return value reaching the model.

**F-6 · the `codex plugin read` evidence line — OUTSTANDING, and it is Codex's to answer.**
Not something zCode can fix.

## Codex's F2, which was the deepest finding of round 1

The question I set for both reviewers: *what fact does the hook now use to know it is
inside the same host turn, and is that fact observed or inferred?*

`_block_streak` answers with three boundaries and the docstring is explicit that a bare log
tail is not one of them:

- **`prompt_submitted`** — written by the registered `UserPromptSubmit` hook, so it exists
  only because the host submitted a new prompt. **Observed.** And the reasoning for why a
  continuation does not produce one is sound: a stop-block continuation is host feedback,
  not a user submission.
- **an allow**, or any decision in `_CHAIN_ENDERS`
  (`anchor_unavailable`, `ceiling_reached`, `frozen_spec_changed`,
  `continuation_budget_spent`). **Observed**, and written by the gate itself.
- **`fresh_chain`** — the host's own flag, and the docstring restricts it to hosts whose
  reference documents the field and its meaning. **Observed**, and delegated to the host.

That is a real answer rather than a renamed inference, and one detail deserves credit
because it is the kind of thing a reviewer usually has to argue for: Kimi's binary *does*
pass `stopHookActive`, and `HOSTS` still sets `chain_flag=None` for Kimi, because Kimi's
**reference** does not document the field. Declining to read an undocumented field that
happens to be there is the rule this project keeps failing to follow, applied correctly.

## New finding · zCode has neither observable boundary — `goal_hooks.py:119`

The boundary coverage is not uniform, and the one host nobody can test is the one left
uncovered:

| host | `chain_flag` | `UserPromptSubmit` registered | boundary available |
|---|---|---|---|
| claude | `stop_hook_active` | no | the host flag |
| codex | `stop_hook_active` | no | the host flag |
| kimi | `None` (undocumented) | **yes**, `kimi.plugin.json` | `prompt_submitted` |
| **zcode** | **`None`** | **no** | **neither** |

Proven by: `grep -n chain_flag …/goal_hooks.py` → lines 107, 119, 132, 143; and the manifest
dump showing `hooks/hooks.json → ['Stop', 'SessionStart', 'PostToolUseFailure']`, with
`UserPromptSubmit` only in `kimi.plugin.json`.

**What breaks.** On zCode the streak resets only when the gate itself writes an allow or a
chain-ender. In the ordinary path that is fine — the budget of 2 releases before zCode's cap
of 3, so `continuation_budget_spent` lands and the chain breaks. The gap is every path where
a *blocked* turn ends without the gate running again: an interrupt, an abort, an error, a
session end. Then the streak survives into the next host turn, and that turn starts already
spent — exactly the alternating `block, allow, block, allow` failure Codex diagnosed for
Kimi, moved to the host that has no binary here to catch it with.

**What would settle it, and it is cheap.** zCode's hooks reference lists `UserPromptSubmit`
among its seven events ("Add context before the model call, or block the request"), so
`prompt_submitted` is available to zCode and simply is not registered. Registering it in the
shared `hooks/hooks.json` gives zCode the same observed boundary Kimi has. Claude Code
supports the event too, which would make the boundary two-deep there rather than resting on
one flag — at the cost of one process spawn per prompt, which is the same cost Kimi already
pays.

The narrower alternative — declare zCode's chain flag if its reference documents one — I
cannot check: `which zcode` still returns nothing on this machine, so I have not read its
Stop input schema. If it documents an equivalent of `stop_hook_active`, that is the smaller
fix and it should win.

## Dimensions exercised

| Dimension | Command | Result |
|---|---|---|
| Suite | `python3 -m pytest tests/ -q` | 347 passed |
| Budget scoping | `git diff 912bab3..HEAD -- …/goal_stop.py` | three observed boundaries, no tail counting |
| Boundary coverage per host | `grep -n chain_flag`, manifest dump | **gap on zcode** |
| Kimi allow-channel | read `goal_prompt_submit.py` | closed |
| Kimi manifest | manifest dump | `SessionStart` gone, three deliverable events plus the prompt channel |
| `$ARGUMENTS` / baseline | commit `0da0a96` subject and diff | claimed closed; **not independently verified by me — see below** |

**Not exercised, and I am naming it rather than implying coverage:** I did not verify
`0da0a96`'s two claims myself (the `$ARGUMENTS` binding on every host, and the write-once
baseline with an honest `none` branch). Those were Codex's findings F1 and F4 and it is
better placed to check its own; if it reports them clean without naming a command, that pair
is unexercised by both of us and should be said so in the joint conclusion.

No host other than Claude Code has run any of these hooks. Every zCode, Kimi and Codex
statement in this review is read from references, binaries and manifests.
