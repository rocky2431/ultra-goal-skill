# Claude Code — round 4 review of `073a801..HEAD`

```
$ python3 -m pytest tests/ -q
394 passed in 25.91s
```

358 at round-3 close, so +36. Six commits. Blind, before §8.1.

## Phase 0 — four of five confirmed closed from here

| # | Defect | State | How I checked |
|---|---|---|---|
| 1.1 | CC allow + `additionalContext` continues | **closed in shape** | `_allow` returns `{"systemMessage": …}` only; `additionalContext` appears in `goal_stop.py` only inside the docstring that records why it went |
| 1.2 | `python3 X \|\| python X` swallows exit 2 | **closed** | manifest command now `if command -v python3; then exec python3 …; else exec python …; fi` — one selection, one `exec`, no second run |
| 1.3 | exit 2 from the launch path | **closed** | `[ -f "$P" ] \|\| exit 0` guards before the interpreter is chosen |
| 1.4 | no session ownership | **closed** | `goal_hooks.py:272-290` reads `session_id`, documents it as the field the CC reference names, and states what an unclaimed marker does |
| 1.5 | mixed `_deny` kills the block on Codex | **closed for Codex, and it broke Kimi** — see below |

The post-fix positive controls for 1.1 and 1.5 are Codex's to run; it produced the failing
evidence, so the mirrored control belongs with it. I am not claiming those two from a
grep.

## Finding · the deny is now inert on Kimi — `goal_stop.py:_deny`

```python
def _deny(reason: str) -> dict[str, Any]:
    return {"decision": "block", "reason": reason}
```

`grep -n kimi …/goal_stop.py` → nothing. `emit()` writes the payload verbatim. `host_facts`
is consumed at exactly one place, `goal_stop.py:671`, for the continuation budget. So the
host is known at runtime — `kimi.plugin.json` passes `--host kimi` — and the deny shape is
not translated for it.

Kimi reads only the nested form. From its own reference, and from its binary, which I read
in round 1:

```js
if (hookSpecificOutput?.permissionDecision !== "deny") return result;
return { action: "block", reason: hookSpecificOutput.permissionDecisionReason, … };
```

**Top-level `decision: block` is not a field Kimi's schema reads.** So on Kimi the gate now
neither blocks nor speaks: the allow paths are deliberately silent by the new design, and
the deny — the only channel a blocked turn has — is inert.

**What went wrong is not the fix, it is the shape of the fix.** The requirement was
per-host translation, and Codex's own document states it as a rule at line 20: *同一份 Stop
输出不能跨家混用* — one Stop output cannot be shared across vendors. This round collapsed
two shapes into one instead of translating, so it traded a dead block on Codex for a dead
block on Kimi.

**Smallest fix:** one translation point. Codex's `goal_host.py` already has its shape —
`output_for(host, event, payload)` — and already converts a top-level block into Kimi's
nested pair with the reason carrying the message. Its non-Kimi branch returns the payload
unchanged, which is now known-wrong for Codex, so adopt the *shape* and write the branches
against the plan: top-level only for Claude Code, Codex and zCode; nested only for Kimi.

**What would settle it otherwise:** a Kimi session where a red anchor's deny visibly keeps
the turn alive. `kimi 0.40.1` is installed, so this is runnable rather than theoretical.

## Phase 1 — the completion contract is implemented as written

Checked clause by clause, and the two that carry the weight are right:

- **The gate executes the anchor itself.** `goal_stop.py:785` is the anchor's
  `subprocess.run`. The other `subprocess.run`, at 385, is git — and it excludes `.goals`
  (`":!.goals"`) from the state identity, so a carry-over rewrite cannot masquerade as
  relevant change. That is the "whole-tree hash is a conservative approximation" limit
  handled properly rather than quoted.
- **One claim, one judgment.** `goal_stop.py:639-647` consumes `.goals/<slug>.candidate`
  *before* judging, and says why: state that changes after the check cannot resurrect a
  claim the gate already ruled on — a new claim needs a new marker.
- **Historical green is never a pass input** — stated at line 24 and consistent with the
  above, since the pass path runs a fresh anchor.
- **The ceiling was redefined.** `goal_hooks.py:81-112` now describes "attempts in a row it
  will deny within one host turn it can observe" and separates the one cap that was read
  precisely from the ones that were not. It no longer calls itself host cap − 1.

## Phase 2 — option (b), and it has an exit

`40e3f09` chose the no-code-change branch: a moved goalpost closes the run.
`goal_stop.py:597-609` states the terminal state and names the way out — the owner reopens
the interview and a new run carries the changed goal. So it is a terminal state with a
reachable exit, not a permanent refusal.

`impossible` did not sneak into the gate: `grep -rn "impossible\|unachievable" scripts/*.py`
returns one hit, and it is the pre-existing sentence in the digest's docstring about
visibility being the achievable property.

## Recommendation · adopt `goal_run.py`

Not a defect, a better shape, and it is already written. Codex's earlier adaptation tree
carries `scripts/goal_run.py` (102 lines): arming in Python, calling `validate_paths`
directly and raising on errors, with `arm` / `diff` / `disarm` subcommands and a guard
this project never produced — *"Another goal is armed; disarm it explicitly first."*

It makes phase-0 defects **1.2, 1.3 and 1.5 structurally impossible** rather than fixed:
no shell expansion to get wrong, no `$1` versus `$ARGUMENTS`, no interpreter selection in a
manifest string, and validation that cannot be fail-open because it is a function call whose
exception is the refusal. zCode's version is still shell fences plus guards — correct today,
and one more edit away from being wrong again.

The guards this round added are the right guards. They are just guarding a surface that does
not need to exist.

## What I did not exercise

No host other than Claude Code ran any of these hooks in this round either. The 1.1 and 1.5
post-fix controls, and the Kimi deny finding above, all need a live session. The two-sessions-
one-cwd isolation test that the plan lists as a phase-0 gate is also not something I ran.
