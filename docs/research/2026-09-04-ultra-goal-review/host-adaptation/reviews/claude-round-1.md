# Claude Code — round 1 review of `97d0780..HEAD`

Reviewed blind in the order this project's own design demands: run the suite and record the
verdict, then attack the diff, and only then read the author's account. My pre-registered
readings and predictions were written before the implementation existed and are in
`scratchpad/claude-preregistered.md`, deliberately kept outside this worktree so the
implementer could not read them.

## Verdict, before reading §8.1

```
$ python3 -m pytest tests/ -q
332 passed in 27.98s
```

302 at baseline, so +30 tests. The range is 5 implementation commits, 1291 insertions
across 26 files.

## Dimensions exercised, with the command for each

| Dimension | Command | Result |
|---|---|---|
| Suite | `python3 -m pytest tests/ -q` | 332 passed |
| Per-host budgets exist and cite sources | `git diff 97d0780..HEAD -- …/goal_hooks.py` | `HOSTS` table, budget = cap − 1, source string per host |
| Kimi's continuation limit | grep `stopHookContinuationUsed` in `~/.kimi-code/bin/kimi` | **confirmed independently**, see below |
| Kimi's output schema | grep `hookSpecificOutput`, `additionalContext`, `systemMessage`, `message` in the same binary | schema has none of the fields `_allow` emits → **F-1** |
| Manifest event surfaces | `python3 -c` over the four manifests + three hook files | see **F-3** |
| Review diff baseline | `grep -n diff …/skills/review/SKILL.md` | fixed, `.goals/<slug>.baseline`, explicit fallback wording |
| Turn semantics reaching the run | `git diff … -- commands/goal-run.md` | the gate's message is the source of `<N>` |
| Codex loader claim | `codex plugin read` on this tree | **not reproducible**, see **F-6** |
| zCode host detection | none possible — no zcode binary on this machine | **unexercised**, see **F-2** |

Not exercised at all, and I am naming it rather than implying coverage: no host other than
Claude Code ran a single one of these hooks. Everything below about Kimi, Codex and zCode is
read from binaries and manifests, not from a session.

## Where the implementation is right, and why that matters

Three of my four pre-registered predictions came out, and two of them came out as *correct
implementation* rather than as findings:

- **The per-host budget lives where the run cannot edit it.** `HOSTS` in `goal_hooks.py:81`,
  hardcoded beside `FROZEN_SECTIONS`, each entry citing its source. I had pre-registered
  that I would object if this became artifact-declared, because a declared budget is a
  budget the run can raise to escape its own ceiling. It did not.
- **Budget = host cap − 1**, so the gate's reason is the last word and the host's force-end
  is a backstop rather than the plan. That is the shape the envelope asked for, and
  `UNKNOWN_HOST` takes the smallest measured budget rather than Claude's, which is the
  right direction to be wrong in.
- **The gate now tells the run which check number it is on** and `goal-run.md` tells the run
  to use that number rather than counting: "`<N>` is the number in the gate's most recent
  message, not a number you count yourself." My prediction 3 was that ruling A would break
  `--audit`'s join and that the honest repair was one shared source for the number. This is
  that repair.

**Kimi's budget of 1 is verified, and I verified it separately from the claim.**
`goal_hooks.py:102` cites `!stopHookContinuationUsed` in `runStepLoop`. From
`/Users/rocky243/.kimi-code/bin/kimi`:

```js
if (!stopHookContinuationUsed) {
  const stopBlock = await this.agent.hooks?.triggerBlock("Stop", {
    signal, inputData: { stopHookActive: stopHookContinuationUsed } });
  if (stopBlock !== void 0) {
    stopHookContinuationUsed = true;
    this.agent.context.appendUserMessage([{ type: "text", text: stopBlock.reason }], …
```

The flag is a local in `runStepLoop`, so it resets per turn: one blocking Stop per host
turn, exactly as claimed. Two things that quote shows which the table does not say, and both
matter — see F-1 and F-5.

## Findings

### F-1 · Every allow path is mute on Kimi — `goal_stop.py:218`

`_allow` emits `{"systemMessage": …}` plus `hookSpecificOutput.additionalContext`. Kimi's
hook output schema, from its binary:

```js
HookJsonOutputSchema = looseObject({
  message: OptionalStringSchema,
  hookSpecificOutput: looseObject({
    message, permissionDecision, permissionDecisionReason }).optional() });
```

Proven by: `python3 -c "…re.finditer…"` over `/Users/rocky243/.kimi-code/bin/kimi` —
`systemMessage` **0 hits**, `additionalContext` **0 hits**, `hookSpecificOutput` 11,
`message` 168.

So on Kimi the gate is silent on green, unknown, ceiling-reached, frozen-spec-changed and
not-progressing. Five of the eight steps say nothing at all, including the two whose entire
job is to speak — "stopping, report what is left rather than claiming success" and "the
result is unknown, not failed".

The block is fine, and `a7ef7e1` deserves credit for anticipating half of this: a one-block
host gets the park instructions inside the block, and Kimi appends `stopBlock.reason` to the
context as a user message, so that text does arrive. It is the *allow* half that is lost.

**Smallest fix**: emit `message` alongside `systemMessage`. It costs one key, it is the
field Kimi's schema actually reads, and it is the same reasoning that made `_deny` emit two
documented forms instead of betting on one — which is why the deny works on Kimi today.
**What would settle it otherwise**: a Kimi session showing an allow-path message reaching
the model.

### F-2 · zCode's whole budget hangs on an unverified variable name — `hooks/hooks.json:10`

The shared Stop entry is
`… goal_stop.py" ${ZCODE_PLUGIN_ROOT:+--host zcode} || python … ${ZCODE_PLUGIN_ROOT:+--host zcode}`.

So `--host zcode` is passed only if `ZCODE_PLUGIN_ROOT` is set in the hook's environment.
`goal_hooks.py:98` cites zCode's reference for the cap of 3, but **nothing cites the
variable name**, and `.zcode-plugin/plugin.json` declares no hooks at all, so this shared
file is zCode's only registration path.

If that variable is not what zCode exports, `host` is `None`, `DEFAULT_HOST` is `"claude"`,
and the gate blocks up to **7** consecutive times against a host that force-ends at **3**.
The failure is silent and it lands exactly on the outcome the budget-minus-one design exists
to prevent: zCode's own "force-ended to prevent infinite loops" becomes the last word.

I cannot test this: `which zcode` → not found on this machine, so zCode is second-hand to me
throughout. **What would settle it**: the zCode plugin reference naming the variable, or one
`env` dump from inside a zCode plugin hook. Until then this is a load-bearing guess wearing
a shell idiom.

**Also worth an answer**: `${VAR:+…}` needs a shell. zCode is documented as having a
`process` handler that takes argv directly and a `command` handler that goes through a
shell. If zCode ever reads this entry as `process`, the expansion is a literal argument.

### F-3 · The Codex split may not actually narrow anything — `.codex-plugin/plugin.json`

`hooks/codex.json` correctly omits `PostToolUseFailure`, which Codex's event table lacks.
But `hooks/hooks.json` still holds `Stop`, `SessionStart` **and** `PostToolUseFailure`, and
both hosts' plugin docs describe `hooks/hooks.json` as *default discovery* with the manifest
*supplementing* it. If discovery is additive, Codex loads `PostToolUseFailure` from
`hooks.json` regardless, and the split buys nothing for Codex.

Command: the manifest/hook-file dump in the table above. `.claude-plugin/plugin.json`
declares only `claude.json` (PreCompact) and relies on the same discovery for the other
three — which is evidence the author believes discovery *is* additive. Both beliefs cannot
hold at once.

**What would settle it**: either host's loader printing the events it registered for this
tree. Which brings me to:

### F-6 · The Codex loader evidence is not reproducible from the installed CLI

The host-adaptation document that seeded this mission reports "Codex `plugin/read`: 读取
2.8.0,发现 5 个 Skill、2 个 hook". On this machine:

```
$ codex plugin read --path plugins/ultra-goal
error: unrecognized subcommand 'read'
Commands: add, list, marketplace, remove, help
```

codex-cli 0.150.1 has no such subcommand, so that reading came from somewhere else — an ACP
or MCP method, most likely. Two problems. First, **"2 hooks" is already inconsistent with
`codex.json` holding three events**, so whatever was measured was not this tree in this
shape. Second, an evidence line I cannot re-run is a claim, and this mission's own rule is
that a capability claim carries the exact invocation. Codex owes the invocation.

### F-4 · `SessionStart` on Kimi is a registration that cannot do its job — `kimi.plugin.json:28`

Kimi's manifest registers `goal_session_start.py`, whose only output is
`hookSpecificOutput.additionalContext` — 0 hits in Kimi's binary — and which writes no
event to the log (unlike `goal_pre_compact.py`, which does, and is therefore genuinely
useful on Kimi even with its message dropped).

So on Kimi that hook reads the artifact, builds up to 12,000 characters, and discards all
of it, once per session boundary. Not harmful. But this plugin's own criterion is that a
mechanism which cannot produce its result **reads as coverage**, and a Kimi user seeing
`SessionStart` in the manifest will believe context recovery is wired when
`goal_prompt_submit.py` is what actually carries it.

`goal_prompt_submit.py` itself is the right shape and says its own degradation out loud —
a one-line pointer, not a body, because "a hook inlines only what it alone possesses".

**Fix**: drop `SessionStart` from Kimi's manifest, or give it the `pre_compact` treatment so
it at least records that a boundary happened.

### F-5 · Kimi spells the field `stopHookActive`, not `stop_hook_active` — `goal_hooks.py:102`

From the quote above: `inputData: { stopHookActive: stopHookContinuationUsed }`. Camel case.
This is why my pre-registered grep for `stop_hook_active` found 0 hits in Kimi's binary and
why I did not assert Kimi's limit from that absence.

No live bug: `run_hook` no longer reads the field at all, which is the fix under review. But
its docstring now says "There is deliberately no `stop_hook_active` early exit here" as
though the field has one spelling across four hosts. One line in `HOSTS` naming the Kimi
spelling would stop the next person from reading `event.get("stop_hook_active")` and getting
`None` on Kimi forever.

## The design question I am not raising as a finding

Envelope §5 invites attacks on the mechanisms themselves. I have one, and it is a *concern*
rather than an evidence-backed objection, so I am labelling it as such.

**With the budget spent, an unattended run on Kimi gets exactly one continuation.** Claude
Code gets seven, Codex an unknown number, zCode two. So the same artifact, with the same
`ceiling: 40`, reaches wildly different real depths per host — and the gate is now the thing
that varies, when the whole design rests on the gate being the invariant. The park
instructions make the *stop* graceful, but nothing makes 40 checks reachable on a host that
allows one continuation per turn. Whatever restarts the turn is outside this plugin.

What would settle it: one unattended run per host, counting `anchor_checked` events until
the run genuinely stops. That is the acceptance test this mission still lacks, and no amount
of unit testing substitutes for it.


---

# Addendum — the vendors' own documentation, read after the findings above

The owner had to point this out twice, and he was right both times. Everything above was
built from installed binaries. A binary answers *what will happen on this machine tonight*;
a reference answers *what is allowed*. This project's own rule says definitions come from
the reference — I put that rule in the mission envelope for the implementer and then did not
follow it myself. Five official pages, read after the fact, changed four of the seven
findings.

| Source | Read |
|---|---|
| zCode hooks | https://zcode.z.ai/en/docs/hooks |
| Codex plugins | https://developers.openai.com/plugins/build/plugins |
| Codex hooks | https://learn.chatgpt.com/docs/hooks |
| Kimi hooks | https://moonshotai.github.io/kimi-code/en/customization/hooks |
| Claude Code plugins | https://code.claude.com/docs/en/plugins-reference |

## F-2 — WITHDRAWN. I was wrong.

zCode's hooks reference lists the four variables a plugin hook receives:
`ZCODE_PLUGIN_ROOT`, `ZCODE_PLUGIN_DATA`, `ZCODE_PLUGIN_ID`, `ZCODE_PLUGIN_NAME`, plus
`CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` "for legacy compatibility".

So `${ZCODE_PLUGIN_ROOT:+--host zcode}` is exactly right, and the discrimination is sound:
zCode sets both variables, Claude Code sets only the Claude one. The implementer had the
better information and I called it "a load-bearing guess wearing a shell idiom". It was not.

The cap is confirmed verbatim too — "After 3 consecutive continuations the run is
force-ended to prevent infinite loops" — so a budget of 2 is right, and zCode's Stop
protocol is the top-level `{"decision": "block", "reason": "..."}` the gate already emits.

One narrow residue survives: zCode's `command` handler "hands the full string to the system
shell", so the expansion works there, while its `process` handler runs argv directly with no
shell and would pass `${ZCODE_PLUGIN_ROOT:+--host zcode}` as a literal. The entry is
`type: command`, so this is a note for whoever converts it, not a defect.

## F-3 — WITHDRAWN. I was wrong, and the reference is explicit.

Codex's plugin documentation: *"If you define `hooks` in `.codex-plugin/plugin.json`, Codex
uses that manifest entry instead of the default `hooks/hooks.json`."* Declaration
**replaces** discovery, so Codex loads `codex.json` only and never sees the
`PostToolUseFailure` entry in the shared file. The split does exactly what it claims.

And Codex's hooks reference confirms the omission was correct: its event list is
SessionStart, SessionEnd, SubagentStart, PreToolUse, PermissionRequest, PostToolUse,
PreCompact, PostCompact, UserPromptSubmit, SubagentStop, Stop, Interrupt. **No
`PostToolUseFailure`.** It documents no continuation cap, which makes `HostFacts(None, …)`
plus an explicit UNVERIFIED note the honest entry rather than a gap.

## F-1 — CONFIRMED by the vendor, and it is worse than I wrote

Kimi's hooks reference: *"All other events are observation-only events: they fire and forget,
and the main flow is unaffected regardless of what the script returns."* Only `PreToolUse`,
`Stop` and `UserPromptSubmit` can affect the flow. Its documented Stop output is:

```json
{ "hookSpecificOutput": { "permissionDecision": "deny",
                          "permissionDecisionReason": "…" } }
```

with exit code 2 as the alternative, and stderr as the rationale.

So `additionalContext` is not merely unread on Kimi — **Kimi's Stop has no allow-channel at
all** in its documented protocol. My "smallest fix: also emit `message`" was aiming at the
binary, which does read a `message` key; the reference documents no such field for a
non-blocking return. Emitting it would be building on an undocumented affordance, which is
the thing this project keeps getting caught doing.

The finding therefore changes shape and gets sharper. On Kimi, anything the gate must say
has to ride on **the block** or on **the next `UserPromptSubmit`**, because those are the two
channels the vendor documents. Which means `a7ef7e1` — park instructions folded into the
block for a one-block host — was not a partial fix, it was the *correct* fix, and the
remaining gap is the other four allow paths: green, unknown, ceiling and not-progressing all
end a Kimi turn in silence, and the documented repair is `goal_prompt_submit.py` carrying
the last verdict rather than only a pointer.

## F-4 — CONFIRMED by the vendor

Same sentence. `SessionStart` on Kimi is observation-only and its return value is ignored,
so the registration in `kimi.plugin.json:28` cannot deliver context by design, not by
accident. Drop it or make it record an event.

## F-5 — stands, and now has both spellings from authorities

Codex's reference documents `stop_hook_active: boolean — Whether this turn was already
continued by Stop`. Kimi's binary passes `stopHookActive` in camel case. Two hosts, two
spellings, and `run_hook`'s docstring speaks of one.

## F-7 — NEW, and it is the most serious thing in this review

`.claude-plugin/plugin.json` now declares `"hooks": ["./hooks/claude.json"]`, holding only
`PreCompact`, and relies on Claude Code auto-discovering `hooks/hooks.json` for the other
three. **Claude Code's own reference does not settle whether that is true.** It groups
`hooks` under "own merge rules" — neither the documented "replaces the default" list
(`commands`, `agents`, `workflows`, …) nor the "adds to the default" list (`skills`) — and
the section it points to does not state the merge behaviour.

Two failure modes, in opposite directions, both silent:

- If declaration **replaces** discovery, as it explicitly does on Codex and as it does for
  `commands` on Claude Code, then Claude Code loads **only `PreCompact`**. No Stop. The gate
  does not exist on the host the owner is actually testing on.
- If the array-of-paths form is not honoured in a plugin manifest at all, `claude.json` is
  ignored and Claude Code loses `PreCompact`.

Evidence that the question is live rather than theoretical, from the 2.1.260 binary:
`"hooks: the file-path and array forms are not yet supported in a marketplace entry."` and
`"Define hooks in the plugin's own hooks/hooks.json (or its plugin.json), or inline them
here as an object mapping hook event names to matcher arrays."` The restriction is stated
for marketplace entries, so it does not settle plugin.json — but it shows the file-path and
array forms are the ones with sharp edges in this loader.

Evidence for what does work, measured on the installed baseline:

```
$ claude plugin details ultra-goal
ultra-goal 2.8.0
  Hooks (4)  Stop, SessionStart, PreCompact, PostToolUseFailure
```

v2.8.0's manifest has **no `hooks` field at all** — keys are name, version, description,
author, homepage, repository, license, keywords, commands — and all four events register
through discovery alone.

**Recommended fix, and it inverts the current design.** Put all four Claude Code events back
in `hooks/hooks.json` and delete the manifest `hooks` field, because that shape is *measured
to work*. zCode auto-discovers the same file and would then see a `PreCompact` entry its
seven documented events do not include — an inert registration, which is a smaller and more
visible cost than an unverified gate on the owner's primary host. Codex is unaffected either
way: its declaration replaces discovery, so it keeps `codex.json`.

If the split is kept instead, it needs the empirical check, and `claude plugin details`
after an install of *this* tree is the whole test: four hooks or one.

## F-6 — stands

`codex plugin read` does not exist in codex-cli 0.150.1 (`Commands: add, list, marketplace,
remove, help`), and "2 hooks" does not match a `codex.json` holding three events.

## What this addendum says about the review process, not the code

Two of my seven findings were wrong, and both were wrong in the same way: I had measured the
machine and not read the contract, so I reported a *gap in my evidence* as a *defect in the
work*. The implementer had read the references; I had not. Worth recording because the
adversarial-review design in this repository assumes the reviewer's evidence is at least as
good as the author's, and here it was not.


## F-7 — WITHDRAWN. I was wrong, and the loader settles it.

Codex's table asserted that Claude Code loads `hooks/hooks.json` *plus* the manifest's hook
files. I had reported the opposite as the most serious finding in this review. The loader in
the 2.1.260 binary settles it against me. Its schema description for the manifest field,
verbatim:

> "Path to file with **additional hooks (in addition to those in hooks/hooks.json, if it
> exists)**, relative to the plugin root"

and the control flow reads the standard file first, then merges the manifest's files into the
same collection:

```js
Ct = Dd(e,"hooks","hooks.json"); En = await Y7o(f, Ct);
if (En === "present") { … `Read hooks.json for plugin ${N.name}` … }
if (N.hooks) { … tn = oer(tn, Cn.hooks) … `Read manifest hooks for plugin ${N.name}` … }
```

with a duplicate guard whose message states the rule outright: *"The standard
hooks/hooks.json is loaded automatically, so manifest.hooks should only reference additional
hook files."*

So the split is additive and correct. And withdrawing this shows something the finding had
hidden: zCode's `.zcode-plugin/plugin.json` declares no hooks, so zCode auto-discovers
`hooks/hooks.json` and receives exactly Stop, SessionStart and PostToolUseFailure — the three
its own reference documents — while `PreCompact` stays in `claude.json` where zCode never
looks. The arrangement is not merely safe, it is precise, and my review called it unverified.

## Scorecard, because it is the useful part of this round

Three of my seven findings withdrawn: F-2, F-3, F-7. All three failed the same way — I
measured the machine and did not read the contract, then reported **a gap in my own evidence
as a defect in the work**. The implementer had read the references; the reviewer had not.

Codex produced four P1 findings I did not reach at all, one of which (its F2: continuation
accounting counts the tail of a persistent log while the host's counter resets per turn) is
deeper than anything in my report and lands exactly on this project's own criterion —
mechanise only when the measured quantity is the judged quantity.

What survives as mine: F-1 (Kimi's Stop has no allow-channel, so five of eight steps end a
Kimi turn in silence), F-4 (Kimi's `SessionStart` registration cannot deliver by design), and
F-6 (the `codex plugin read` evidence line is not reproducible on the installed CLI). Codex's
report contains zero occurrences of `additionalContext` or `systemMessage`, so that axis was
genuinely unexamined by it.

The cross-vendor axis paid for itself in both directions, and not the direction I predicted:
Codex read the code better, I read the host contracts better, and the reviewer who
manufactured false findings was the one working from binaries alone.
