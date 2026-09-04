# Claude Code — round 3 review of `62b930f..HEAD`

```
$ python3 -m pytest tests/ -q
358 passed in 31.55s
```

347 at round-2 close, so +11. Blind, before §8.1.

## The two open P1s

### Codex F1 · arming — CLOSED, as a refusal and not a downgrade

`commands/goal-run.md` now reads:

```sh
if [ ! -f "$validator" ]; then
  printf '%s\n' "ultra-goal: arming refused - … This is a refusal, not a downgrade. …"
  exit 1
fi
python3 "$validator" .goals/$ARGUMENTS.goal.md || exit 1
printf '%s\n' "$ARGUMENTS" > .goals/active
```

Both halves refuse: no reachable validator, and a validator that reports errors. What makes
this a good fix rather than a strict one is the second sentence of the refusal — it names
each host's install root, the by-hand validation command, and two ways back
(`export PLUGIN_ROOT=…` or `echo $ARGUMENTS > .goals/active` once clean). The envelope asked
for the accepted primary path to stay usable, and a prohibition that names its cheap
alternative is the only kind that survives.

### Codex F2 · the turn boundary — CLOSED, with the host's own identity

`goal_turn_started.py` registers Kimi's `TurnStarted`, and `_block_streak` now takes a
second bound from it:

```py
if turn_id is not None and entry.get("turn_id") != turn_id:
    break
```

Registration verified in `kimi.plugin.json`: `['Stop', 'PreCompact', 'PostToolUseFailure',
'UserPromptSubmit', 'TurnStarted']`. And Codex's own closure bar — a regression with a
non-user origin — is met: `tests/test_goal_hooks.py:1289` drives `origin_kind="system_trigger"`
and `:1308`/`:1310` drive `"task"`.

One observation in that file is better than the argument either reviewer made. Kimi's binary
does pass a `stopHookActive` input, and round 2 declined to read it because the reference
does not document it. The real reason is stronger: it is **constant-false by construction**,
because it is only ever read inside the `!stopHookContinuationUsed` guard, so the field
carries no information at all. Declining to read an undocumented field is discipline;
knowing it is informationless is understanding.

## zCode's declared degradation — the right delivery

`goal_hooks.py:111-126`. zCode has neither usable boundary: its reference lists
`stop_hook_active` among Stop's inputs but **spells no semantics for it**, and its
exactly-seven event list has no turn boundary. The comment refuses the field for the first
reason and then names what the run loses for the second:

> a blocked chain that ends without one of those — an owner interrupt, an error, a session
> end — carries its tail into the next turn, which can park one block early (budget 2, so
> one block of it already spent). The release is loud and names its reason; what is never
> claimed is a turn-scoped budget this host cannot observe.

That last clause is the whole point. A proxy that looks grounded would have delivered worse
than a gap that is stated.

## My own findings

- **Round-2 new finding — SUBSUMED, and my proposed fix was wrong.** I proposed registering
  `UserPromptSubmit` for zCode. That would have installed the same inferred proxy Codex
  refuted, on the one host with no way to check it. The correct outcome was the declared
  degradation above.
- **The empty-delegation gap — ADDRESSED within its reach.** `REVIEW_UNEVIDENCED` looks for
  `.goals/.work/<slug>-review.md`, and its own text says reviewers writing elsewhere are
  beyond it. That is the honest scope: the only detector available from inside the plugin is
  "the expected artifact is absent", and it says so instead of implying more.

## What I did not exercise

No host other than Claude Code ran any of these hooks, in any round. Every zCode, Kimi and
Codex statement in all three of my reviews is read from references, binaries and manifests.
Specifically unexercised by me: the `$ARGUMENTS` expansion under a real Kimi command
invocation, `TurnStarted` firing in a live Kimi session, and the refusal path under Codex's
and zCode's actual command execution.

## For the joint conclusion

**Ship — for Claude Code only, and as a first run rather than a release.** The strongest
reason: the gate is the only part of this design that carries hard power, and on Claude Code
it has now been observed doing its job on a real artifact —
`{"event":"anchor_checked","turn":1,"outcome":"red","exit_code":1,"tail":"verify: 0/4 checks passed"}`
with the turn refused. Nothing equivalent exists for the other three hosts.

**Proven, with the command:**

- 358 tests, three-platform CI green through v2.9.2 — `python3 -m pytest tests/ -q`.
- The gate blocks a red anchor in a live Claude Code session — the owner's
  `agent-factor-edge` event log.
- Arming refuses without validation — the fenced commands driven against an invalid artifact
  (Codex's round-2 reproduction, now inverted).
- Kimi's one-continuation-per-turn ceiling — `stopHookContinuationUsed` as a `runStepLoop`
  local, plus `notifyTurnEnded` resetting it.
- Claude Code's cap of 8 — `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP ?? 8` in the 2.1.260 binary.
- Claude Code loads manifest hook files **in addition to** `hooks/hooks.json` — the loader's
  own schema text, "additional hooks (in addition to those in hooks/hooks.json, if it
  exists)".

**Unverified, and by whom:** everything about three of the four hosts. No install, no live
lifecycle, no four-host acceptance run. The 358 tests measure this repository's logic and
its packaging conventions; they do not measure a host honouring a registration. Also
unverified: Codex's `None` continuation budget (absence from a reference and from a string
scan is not proof of unbounded behaviour), and `turn_id` collision across two concurrent
Kimi sessions in one repository.

**Where we may still disagree:** unknown until Codex files. Its round 2 was killed before
reaching its own F3–F6, my findings, or its regression audit of the full range, so those
axes have exactly one reviewer's opinion on them.

**What I retracted across three rounds — four positions, all the same shape:**

| Round | Retracted | Beaten by |
|---|---|---|
| 1 | F-2, zCode's `ZCODE_PLUGIN_ROOT` was "a load-bearing guess" | zCode's hooks reference lists it among four plugin variables |
| 1 | F-3, Codex would still load `PostToolUseFailure` from the shared file | Codex's plugin reference: the manifest entry is used *instead of* the default |
| 1 | F-7, Claude Code's manifest `hooks` might replace discovery | the CC loader's schema text and control flow: additive |
| 2 | grading `prompt_submitted` as an observed turn boundary | Codex F2: the invocation is observed, the equivalence is inferred |

**The pattern is the finding.** Three times I measured a machine and did not read the
contract; once I accepted a mechanism without asking what the host itself exposes. All four
times I reported a gap in my own evidence as a defect in the work, and all four times the
implementer or the other reviewer had the better source. If any of this belongs in the
product rather than in a review file, it is the retraction ledger the Protoss study named:
without one, "this reviewer errs by trusting binaries over references" is information the
next round loses.
