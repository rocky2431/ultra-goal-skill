# Ultra Goal 对抗式设计评审 · 第 1 轮 · reviewer: claude

审计对象:`sources/main`(HEAD `b07e2a8`)为主,`sources/adapt`(HEAD `f15a003`)作为独立候选评估。
宿主证据来自本机安装的运行时源码/二进制、官方参考文档,以及我在自己目录里做的两个隔离复现实验。

---

## 0. 一句话结论

**"Stop 拦截就是循环,所以宿主的 goal 模式不再需要"这个论断是错的,而且是可证伪地错的。**
在四个宿主上,Stop hook 能提供的自主续跑分别是:Claude Code 实测 **1 次/用户回合**(因为本设计自己的重入守卫)、Kimi **硬上限 1 次/回合**、zCode **硬上限 3 次/回合**、Codex **0 次**(payload 被宿主 schema 拒绝)。
而 `## Stop condition` 里写的 "6 turns / 40 turns" 被 SKILL.md 和 goal-run.md 描述成"闸门驱动的迭代",实际上它数的是**用户敲了几次回车**。

正确的方向是把结论反过来:**宿主的 goal/target 模式是循环,Stop 闸门是它缺的那个不可争辩的裁判。** 详见 §4。

---

## 1. 证据分级

本报告每条事实标注来源等级:

| 标记 | 含义 |
|---|---|
| **[源码]** | 读了本机安装的运行时源码/反汇编字符串,给出符号名与上下文 |
| **[文档]** | 厂商官方参考,给出 URL 与原文引用 |
| **[实测]** | 我在自己目录里跑出来的输出,命令与输出都在下面 |
| **[推断]** | 由前三者推出,但没有直接观测 |
| **[未知]** | 明确未验证 |

---

## 2. 宿主事实表(决策关键)

### 2.1 Stop 的阻断契约与每回合续跑上限

| 宿主 | 阻断契约 | 每个用户回合的续跑上限 | Stop 能否注入 additionalContext | stop_hook_active |
|---|---|---|---|---|
| Claude Code 2.1.260 | `decision:"block"` + `reason`,或 exit 2 **[文档]** | **连续 8 次"无工具调用"的续跑**;一旦模型调用工具,计数归零 → 实际近似无界 **[源码]** | 能,**但它同样会续跑,不会结束回合** **[文档]** | 有;首次阻断后在整个用户回合内保持 `true` **[源码]** |
| Codex 0.150.x | 仅顶层 `decision:"block"` + `reason`;输出结构 `deny_unknown_fields` **[源码]** | 源码中 `turn.rs` 的 `loop` 无上限 **[源码]** | **不能** —— `StopOutput` 结构里根本没有 `additional_context` 字段 **[源码]** | 有 **[源码]** |
| Kimi 0.40.1 | `hookSpecificOutput.permissionDecision:"deny"` + `permissionDecisionReason`,或 exit 2 **[文档]** | **恰好 1 次,硬编码** **[源码]** | 无该字段;阻断原因被追加为一条 user message **[源码]** | 传 camelCase `stopHookActive`,且由 `!used` 守卫保证恒为 `false` **[源码]** |
| zCode 0.16.5 | `decision:"block"`;且要求 `additionalContexts` 非空 **[源码]** | **3 次,硬编码** **[源码]** | 能 **[源码]** | 有,snake_case,值为 `continuationCount > 0` **[源码]** |

出处:

- **Claude Code**:`/Users/rocky243/.local/share/claude/versions/2.1.260` 字符串:
  `let Vd = a.CLAUDE_CODE_STOP_HOOK_BLOCK_CAP ?? 8; if (Vd>0 && qd>Vd) return ... "A hook blocked the turn from ending ${qd} consecutive times — overriding and ending turn."`
  阻断分支写回 `{... stopHookActive:!0, stopHookBlockingCount:qd, transition:{reason:"stop_hook_blocking"}}`;
  工具执行分支写回 `{... stopHookActive:No, stopHookBlockingCount:0, transition:{reason:"next_turn"}}`。
  **两点结论**:(a) `stopHookActive` 一旦为真就在本用户回合内不再复位;(b) 8 次上限只数"两次阻断之间没有工具调用"的连续次数 —— 它是**无进展保护**,不是循环上限。
  文档:<https://code.claude.com/docs/en/hooks> "Stop input" 段原文:*"The `stop_hook_active` field is `true` when Claude Code is already continuing as a result of a stop hook. ... Claude Code overrides the hook and ends the turn after 8 consecutive blocks."*

- **Codex**:`codex-rs/hooks/src/schema.rs:451-464`
  ```rust
  #[serde(rename_all = "camelCase")]
  #[serde(deny_unknown_fields)]
  #[schemars(rename = "stop.command.output")]
  pub(crate) struct StopCommandOutputWire {
      #[serde(flatten)] pub universal: HookUniversalOutputWire,
      #[serde(default)] pub decision: Option<BlockDecisionWire>,
      #[serde(default)] pub reason: Option<String>,
  }
  ```
  `codex-rs/hooks/src/engine/output_parser.rs:56-61` 的 `StopOutput` 没有 `additional_context`。
  `codex-rs/hooks/src/engine/output_parser.rs:345-358` 的 `parse_json` 在反序列化失败时返回 `None`。
  `codex-rs/hooks/src/events/stop.rs:326-341`:解析失败且 `looks_like_json` 为真时 →
  `status = HookRunStatus::Failed` + `"hook returned invalid stop hook JSON output"`。

- **Kimi**:`/tmp/ultra-goal-research.j8qCAJ/kimi-turn.ts:940-960`
  ```ts
  // 3. The external Stop hook gets exactly one continuation; the cap
  //    is intentionally separate from (and does not cap) goal mode.
  if (!stopHookContinuationUsed) {
    const stopBlock = await this.agent.hooks?.triggerBlock('Stop', {
      signal, inputData: { stopHookActive: stopHookContinuationUsed },
    });
  ```
  注意 `stopHookActive` 的实参就是守卫变量本身,进到这一行时必然为 `false` —— 该字段对 hook 零信息量。
  Kimi hooks 文档(`kimi-hooks.md`)另确认:`[[hooks]]` 只允许 `event/matcher/command/timeout` 四个字段,多写会导致 **config.toml 整体加载失败**;可阻断事件只有 `PreToolUse`、`Stop`、`UserPromptSubmit`,其余事件"发即忘"。

- **zCode**:`/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs`
  ```js
  function OUr(e,t){ return e.stopShouldContinue===!0 && e.additionalContexts.length>0 && t<Dui }
  ...
  Dui=3, Nui=24e3, Lui=4e3;
  ```
  调用点:`this.shouldContinueAfterStopHooks(o, e.stopHookContinuationCount) ? (e.stopHookContinuationCount+=1, ...)`;
  Stop 输入构造:`case on.Stop: t.last_assistant_message=..., t.stop_hook_active = e.stopHookActive;`,而 `stopHookActive: o` 的实参是 `e.stopHookContinuationCount > 0`。
  hook 事件枚举只有 7 个:`["SessionStart","UserPromptSubmit","PreToolUse","PermissionRequest","PostToolUse","PostToolUseFailure","Stop"]` —— **没有 PreCompact / SubagentStop / SessionEnd**。
  插件 hook 发现:`QAo = join("hooks","hooks.json")` 自动发现,未知事件名只是 `severity:"warning"` 并跳过该事件,不会废掉整个文件。
  另有完整的原生 target(goal)子系统:`readSessionTargetForContext / continueActiveTargetLoop / targetContinuationCandidate / accountTargetTurnCompletion / pauseActiveTargetForCancellation / activatePausedTargetAfterResume / recordGoalStateChangeReminder`。

### 2.2 一条被 SKILL.md 反向理解的官方定义

`https://code.claude.com/docs/en/hooks` · "Stop decision control" 原文:

> Use `additionalContext` when the hook is working as designed and giving Claude guidance, such as "run the test suite before finishing". **It keeps the conversation going through the same loop protections as `decision: "block"`, namely the `stop_hook_active` input and the 8-consecutive-continuation cap**, but the transcript labels it `Stop hook feedback` and no hook error notification is shown.

同一段的字段表里,Stop 只有三个可返回项:`decision`、`reason`、`hookSpecificOutput.additionalContext`。
**没有 `permissionDecision`。** 这与 `goal_stop.py:219-254` 的 `_deny()` docstring 中"官方 hooks 参考为 Stop 列出了 `hookSpecificOutput.permissionDecision: allow|deny`"这一断言直接冲突。

---

## 3. 现设计最强的缺陷

排序依据:是否让"闸门"这个核心承诺失效。

### D1 —— 自设的重入守卫把"闸门即循环"降级成"每个用户回合多干一步" 【已证实 · 实测】

`goal_hooks.py:141-143`:

```python
# Re-entry guard. Without it, a denied stop can be denied forever.
if event.get("stop_hook_active"):
    return 0
```

我在自己目录建了最小夹具(红锚点 `sh -c "exit 1"`,ceiling 3,两条未完成 acceptance),用 main 的 `goal_stop.py` 实跑:

```
=== turn 1 (stop_hook_active false) ===
{"decision": "block", "reason": "demo: anchor `sh -c \"exit 1\"` is still failing (exit 1) on turn 1 of 3, ...
=== turn 2 (stop_hook_active TRUE) ===
[无输出]                      # 未读 artifact、未跑锚点、未写事件
=== events ===
{... "event":"anchor_checked","turn":1, "outcome":"red" ...}   # 只有一行
```

结合 §2.1 已确认的宿主语义(Claude Code 首次阻断后 `stop_hook_active` 在本用户回合内不复位;zCode 的 `stopHookActive = continuationCount>0` 同理),结论是硬的:

> **在 Claude Code 和 zCode 上,这个闸门每个用户回合最多只会拦一次。第二次 Stop 直接 exit 0,锚点甚至不会被执行。**

由此坍塌的一串承诺:

- SKILL.md:342 行、376-388 行 "The gate is the loop, so a host's goal mode is no longer needed" —— 不成立。
- SKILL.md:465 行 "Context anxiety … the gate refuses the stop while the anchor is red, so ending the turn early is not available" —— 第二次就可用了。
- `_ceiling()` 里精心处理的 `ceiling: none` / 词形数字 / 12 默认值,数的是**用户提示次数**,不是自主迭代次数。一个 40-turn 的 artifact 要求 owner 敲 40 次回车。
- `goal-run.md:78` "nothing in this plugin runs again until the marker returns" 这段把 gate 描述成 `LOOP` 的替代品 —— 但 `LOOP` 至少真的会 loop。

**严重度**:这是整个产品定位的地基。`adapt` 候选已经独立发现并删掉了这个守卫(`goal_hooks.py` diff),这一点我同意,但它的替代方案仍有问题,见 §7。

**这是事实,不是设计判断。**

### D2 —— `_allow(reason, context)` 在 Claude Code 上根本不是 allow 【已证实 · 文档原文】

`goal_stop.py:202-216` 的 `_allow()` 在有 `context` 时会发出 `hookSpecificOutput.additionalContext`。按 §2.2 的官方原文,这**会让对话继续**,走的是和 `decision:"block"` 完全相同的续跑通道。

于是这四条路径的文案与机制自相矛盾:

| 路径 | 文案 | 实际(Claude Code) |
|---|---|---|
| `ceiling_reached`(:420) | "ceiling of N turns reached … **Stopping**." | 继续 |
| anchor unknown(:501) | "… **Stopping**. Say it is unverified" | 继续 |
| anchor green(:526) | "anchor passed on turn N." | 继续 |
| 无进展(:535) | "the run is not progressing. **Stopping**." | 继续 |

只有 `frozen_spec_changed`(:388)和 `anchor_unavailable`(:366)两条不带 context,是真的 allow。

也就是说 SKILL.md:650 的 "**Seven of the eight steps allow**" 与 `goal_stop.py` 模块 docstring 的 "Eight steps, seven of which let the turn end" 都是错的:在 Claude Code 上是 **2 条真 allow、6 条 continue**。

实际后果被 D1 的守卫掩盖了 —— 因为第二次 Stop 会 exit 0,所以只多烧一个模型回合。**但 adapt 候选删掉了守卫,这个缺陷就从"多烧一步"变成"预算会计彻底算错"**:adapt 给 Claude 的 `continuation_budget=7` 只数 `blocked:true` 的事件,而 Claude 的 8 次上限同时数 additionalContext 续跑。

**这是事实,不是设计判断。**

### D3 —— Codex 上闸门不但不生效,而且每回合报一次 hook 错误 【已证实 · 编译级复现】

`_deny()` 与带 context 的 `_allow()` 都在顶层输出 `hookSpecificOutput`。Codex 的 `StopCommandOutputWire` 带 `deny_unknown_fields`。
`deny_unknown_fields` 与 `#[serde(flatten)]` 同时存在时行为不显然,所以我没有推断,而是用 serde 1.0.229 编译了一份与 `schema.rs:451-464` 逐字段等同的复现(离线,只用本机已解压的 crate,产物在我自己目录 `probe/`):

```
REJECTED | deny payload emitted by goal_stop.py _deny() | -> parse_stop returns None
         | serde error: unknown field `hookSpecificOutput`
PARSED   | deny payload without hookSpecificOutput | decision=Some(Block) reason=Some("anchor red")
REJECTED | allow payload emitted by goal_stop.py _allow() with context | -> parse_stop returns None
         | serde error: unknown field `hookSpecificOutput`
PARSED   | allow payload, systemMessage only | systemMessage=Some("[ultra-goal] x")
```

`parse_stop` 返回 `None` → `events/stop.rs:326-341` 判定 `HookRunStatus::Failed`,并向用户抛出 `"hook returned invalid stop hook JSON output"`。

在 `main` 里这是**潜伏**缺陷:`install_user.py:36` 的 `HOOK_HOSTS = ("claude",)`,且 `.codex-plugin/plugin.json` 没有 `hooks` 键,所以 Codex 上根本不会注册。
但 `adapt` 候选新增了 `hooks/codex.json` 明确注册 Stop —— **该缺陷在候选里会直接变成线上故障**,而且是"每回合一条红色错误 + 闸门零效力"这种最难被误判为正常的形态。

`_deny()` docstring 里"两个权威来源冲突,同时满足两边只花几个字节"的推理,在第三个宿主上恰好是**代价最高**的选择:多出来的那几个字节让整份 payload 被丢弃。

**这是事实,不是设计判断。**

### D4 —— 一条 "Definitions come from the vendor's reference documentation" 自己违反了自己 【已证实】

SKILL.md:97-104 立了一条很好的规矩:定义只能来自厂商参考。
`_deny()` docstring 却把 "官方 hooks 参考为 Stop 列出了 `permissionDecision`" 当作既成事实写进了代码注释,并据此设计了双发。我按 §2.2 核对了现行参考:Stop 的可返回项只有三个,不含 `permissionDecision`。

这个字段在 **Kimi** 上是有用的(Kimi 的阻断 JSON 契约恰恰是 `hookSpecificOutput.permissionDecision:"deny"`),所以"双发"这个动作本身在 Kimi 上救了场 —— 但**理由是编造的**,而 SKILL.md 自己说编造理由是这个项目里出过三次的错误类型。这条值得单列,因为它说明规矩没有被机制保住:没有任何测试或探针会发现一条注释在说谎。

### D5 —— 宿主能力表与安装器互相矛盾,且对 Kimi 的判断已过时 【已证实】

`install_user.py:31-33` 的注释:

> Measured, not assumed: **Kimi exposes only SessionStart and PostCompact** (and in TOML), OpenCode has no declarative hooks at all.

同一仓库的 `plugins/ultra-goal/kimi.plugin.json:26-45` 却注册了 `Stop / SessionStart / PreCompact / PostToolUseFailure` 四个 hook。

实测:`strings /Users/rocky243/.kimi-code/bin/kimi` 里 `"Stop"`、`"PreCompact"`、`"PostCompact"`、`"PostToolUseFailure"`、`"SubagentStop"`、`"SessionEnd"`、`"UserPromptSubmit"` 全部存在;Kimi hooks 文档的事件一览表也把它们全列了出来,并明确 `Stop` 是可阻断事件。

**这个矛盾比它的内容更重要**:同一份仓库里两处"宿主能力"事实,一处过时一处不同,而且都是散落的注释。没有单一数据源,就没有办法让第三处(`hooks/hooks.json`)与它们保持一致。这是 §4 里我坚持"宿主能力必须是数据 + 可执行探针"的原因。

顺带两条同源事实:
- `hooks/hooks.json` 注册的 `PreCompact` 在 zCode 上不存在 → zCode 会记一条 `plugin_hook_unsupported_event` 警告并跳过(只是警告,不影响其他事件)。
- `hooks/hooks.json` 的 Stop 条目带 `"matcher": "*"`。Claude Code 文档:*"If you add a `matcher` field to an event without matcher support, it is silently ignored."* Stop 无 matcher 支持。无害,但说明这份 manifest 是按 PreToolUse 的心智模型写的。

### D6 —— 后台工作完全没有进入闸门的视野 【已证实 · 文档 + 源码】

Claude Code 的 Stop 输入带 `background_tasks` 与 `session_crons` 两个数组,文档写明其用途:

> The `background_tasks` and `session_crons` arrays let hooks distinguish "session is done" from "session is paused waiting for background work to wake it back up".

而 Claude 自己的 `/goal` 就用了这个:*"If a subagent or a background shell command is still running when a turn ends, Claude Code skips the evaluation for that turn."*

`goal_stop.py` 一个字都没读。后果是两个方向都错:

1. **假红**:后台构建/subagent 还在跑时,回合结束触发 Stop,锚点在半成品工作树上执行 → red → 闸门阻断 → 模型被推去修一个正在被修的东西。
2. **假绿**:锚点是 `npm test` 而后台还在编译,测的是上一次的产物。

而 SKILL.md 通篇把"锚点是唯一不经过模型的事实"当作设计基石(:461、:724)。**锚点在错误的时刻执行,它就不再是事实,只是一个更有说服力的错误。** 这个缺口正好落在 owner 给我的"background workers"对抗角度上。

adapt 的 `_tree_digest` 尝试解决相邻问题(区分"没进展"和"输出相同但在动"),但它测的是工作树,不是"有没有东西正在写工作树" —— 反而更糟:一个后台任务在跑,工作树每次都在变,`_stagnant` 永远为假,于是闸门永远不释放。

### D7 —— 取消与用户引导没有设计,唯一逃生口是文件系统 【设计判断,证据支撑】

`goal-run.md:71-78` 给出的唯一停机方式是 `rm .goals/active`(外加 `ULTRA_GOAL_HOOKS_DISABLED=1`)。对比宿主原生能力:

- Claude Code:`/goal clear`,别名 `stop/off/reset/none/cancel`;`/clear` 也清;`Ctrl+C` 中断非交互 goal;鉴权失败/额度耗尽/上下文溢出/模型不可用会**自动清除**并打印原因。
- Kimi:`/goal pause` / `resume` / `cancel`;`Interrupt` 事件专门覆盖用户 Esc(此时 **Stop 不触发**)。
- zCode:`pauseActiveTargetForCancellation` / `activatePausedTargetAfterResume`。

Ultra Goal 的闸门对这些一无所知。具体的坏路径:

- **用户中断**:Claude Code 文档明说 Stop *"Does not run if the stoppage occurred due to a user interrupt"*;Kimi 同样用 `Interrupt` 取代 `Stop`。所以用户按 Esc 之后,事件日志里那一回合**不留任何痕迹** —— `--audit` 会把它读成"这一回合没发生过",turn 计数错位。
- **错误路径**:Claude Code 有独立的 `StopFailure` 事件(API 错误时触发,取代 Stop)。Ultra Goal 没注册,所以一次 API 失败对闸门是不可见的;但对 `/goal` 是可见的(它会因不可恢复错误清除目标)。
- **凭据/额度耗尽**:`.goals/active` 还在,下一个会话 SessionStart 继续注入"有一个 goal 在跑",而实际上什么都不会跑。

### D8 —— "turn" 一词在四个地方指四件不同的事 【设计判断】

1. `goal_stop.py:370` 的 `turn = len(anchor_checked) + 1` —— 闸门自己数的锚点检查次数(≈ 用户提示次数,见 D1)。
2. goal 文本要求模型"state which turn you are on"(SKILL.md:406) —— 模型**看不到** ①,只能猜。
3. commit message `goal(<slug>) turn <N>` —— 模型写的,即 ②,即猜的。
4. Claude Code 的 `/goal` status 里的 turn count —— 第四个计数器。

`--audit` 的整个价值主张是"把 run 声称的裁决与闸门测到的裁决并排放"。但 run 声称的 turn 号和闸门的 turn 号来自两个互不可见的计数器 —— **对齐这件事本身就没有机制保证**。闸门知道自己的编号却不告诉模型,是一个几乎零成本就能补上的缺口(`_obligation` 里加一行 `This is gate turn N`)。

### D9 —— 锚点抽取用"section 里第一段 inline code"这个启发式 【已证实 · 读码】

`goal_stop.py:114-146`:先找 fenced block(多行则拒绝,这个处理是对的),否则取 `INLINE.search(text)` —— **整个 `## Anchor` 段里第一个反引号片段**。

失效样例:

```markdown
## Anchor
See `docs/anchor-rationale.md` for why. Run `pytest -q` and require exit 0.
budget: 5 minutes
```

抽出的是 `docs/anchor-rationale.md`。`_resolvable()` 会因为文件存在而返回 `True`,于是 shell 执行它 → exit 126 → 落进 `UNRUNNABLE_EXITS` → **永远 unknown**。而 unknown 是 allow,所以整个 run 从头到尾闸门零效力,`--audit` 里每行都写着 `unknown`,没有任何一处说"你的锚点抽错了"。

这与 `_first_command` docstring 自己讲的那个故事(两行 fenced block 只跑第一行)是**同一个错误的另一面**,而修法它自己已经写出来了:拒绝歧义。单行 inline 的歧义没有被拒绝。
最小修法:要求 `## Anchor` 用 fenced block 或一个显式 `command:` 前缀,由 `validate_artifact.py` 强制。

### D10 —— 前半段(Init / Ultra Research)在 main 里没有任何机制 【设计判断】

owner 的产品意图是"前半段是 Init 与 Ultra Research:澄清目标含义与循环的约束条件"。
main 里能找到的是:一份 9 问访谈提纲(SKILL.md:149-299),以及 `## Roles` 表里一行 "Research — find out what is true first | fanned-out subagents"。

**没有任何机制承载它**:没有 research 产物文件(`<slug>.research.md` 不存在)、没有 `validate_artifact.py` 检查、没有 hook 记录 research 是否真的发生过、`INJECT_ORDER` 里没有它的位置。
结果是最贵的一个环节完全靠 `SKILL.md` 的散文约束一个模型 —— 而这正是 SKILL.md 自己反复反对的形态("零信任自报告")。

这条同时解释了 D9 为什么会发生:一个没有做过 research 的 goal,`## Anchor` 就是被临时编出来的一句话,而闸门对"这句话能不能跑"只做了 `shutil.which` 级别的检查。

### D11 —— 常驻上下文成本没有被算进"这个 Skill 值多少" 【设计判断】

`SKILL.md` 792 行 / 约 40KB,`references/` 另有 9 个文件共约 1100 行。SKILL.md:773 明确说 "The host keeps this Skill's content in the conversation after the handoff"。
同时 `goal_session_start.py` 的 `CONTEXT_LIMIT = 12000` 字符会在每次 startup/resume/clear/compact/fork 时再注入一次 artifact。

`_obligation()` 的重写把每回合 4683 字符压到约 660 —— 这个优化本身很好,而且它总结出的规则("A hook inlines only what it alone possesses")是这份设计里最好的一条。**但同一条规则没有被应用到 SKILL.md 自己身上**:792 行里绝大部分是设计论证(为什么三层冻结、为什么 Reflexion 限 3 条、为什么 critic 优于第二个 reviewer),这些是给**作者**看的,不是运行时需要的。

---

## 4. 我的建议:最小可行架构

### 4.1 反转核心论断

> **不是"闸门是循环所以宿主 goal 模式多余",而是"宿主 goal 模式是循环,闸门是它缺的那个不可争辩的裁判"。**

理由是四条互补的事实:

| 能力 | 宿主 goal 模式 | Stop hook |
|---|---|---|
| 跨用户回合续跑 | ✅(Claude/Kimi/zCode/Codex 都有) | ❌ 1~3 次/回合 |
| 暂停 / 取消 / 恢复 | ✅ | ❌ 只有 `rm` |
| 后台工作时延后评估 | ✅(Claude 明确;Kimi print-drain) | ❌ |
| 不可恢复错误时自动清除 | ✅(Claude 四类) | ❌ |
| 回合/时长/token 会计 | ✅ | ❌ |
| **运行真实命令拿 exit code** | ❌(Claude 评估器"不调工具,只读对话") | ✅ |
| **写不可伪造的证据日志** | ❌ | ✅ |
| **比对冻结摘要** | ❌ | ✅ |

两边的强弱是**互补而非重叠**的。SKILL.md:376-388 的对比表("goal mode duplicates four of this Skill's own mechanisms")只比了重叠的部分,没有比不重叠的部分。

### 4.2 组合方式(这是关键的一步)

Claude 的评估器只能读对话里已经出现的东西 —— 那正好是闸门 `systemMessage` 落地的地方。所以把 stop condition 写成**引用闸门证据的形式**:

```
/goal <目标>。完成的唯一判据是:本会话中 ultra-goal 闸门最近一次 anchor_checked
的 outcome 为 green,且 `## Acceptance` 全部为 [x]。闸门每回合会在
[ultra-goal] 前缀的系统消息里报告它测到的 exit code —— 引用那条消息,
不要引用你自己对代码的判断。若无该消息,视为未验证。
```

这样:
- **续航**由宿主原生 goal 提供(跨回合、可取消、后台感知、自动清错)。
- **裁决**由闸门提供(真跑命令、真 exit code、写日志)。
- **评估器的幻觉面**被收窄成"它有没有正确读一条格式固定的系统消息",这是小模型能做对的事。
- 闸门保留它那 1 次阻断,用途从"循环引擎"改为"廉价的额外一步 + 强制写 carry-over"。

### 4.3 组件清单(比现在少)

| 组件 | 内容 | 相对现状 |
|---|---|---|
| `SKILL.md` | 削到 ~200 行:识别意图、9 问、拒绝的形状、编译产物、交接。设计论证全部移入 `references/` | -75% 常驻上下文 |
| `hosts.json` | **唯一**的宿主能力数据源:事件名、Stop 阻断契约、每回合续跑上限、是否支持 additionalContext、原生 goal 命令、取消命令。每条带 `source` 字段 | 取代散落在 3 处、且已互相矛盾的注释 |
| `goal_gate.py` | 单脚本,`--event {stop,session-start,prompt-submit}` 分派。读 `hosts.json` 决定 payload 形状 | 合并 4 个脚本;彻底消除 D3 |
| `goal_doctor.py` | **可执行探针**:对每个已安装宿主,构造一个必然 red 的临时 goal,实跑一次,报告"这个宿主上闸门到底能不能拦、拦几次"。这是 D4/D5 的机制性修复 | 新增 |
| `validate_artifact.py` | 保留;新增强制:`## Anchor` 必须是 fenced 单行或 `command:` 前缀(修 D9) | 收紧 |
| 模板 | `goal-package.md` + `decisions-record.md` + **新增 `research.md`** | 修 D10 |

### 4.4 按宿主发什么 payload(修 D2/D3)

```
claude : block  -> {"decision":"block","reason":R}
         allow  -> {"systemMessage":M}            # 绝不带 additionalContext
         nudge  -> {"hookSpecificOutput":{"hookEventName":"Stop","additionalContext":C}}
codex  : block  -> {"decision":"block","reason":R}
         allow  -> {"systemMessage":M}            # 顶层 6 字段以外一律不发
kimi   : block  -> {"hookSpecificOutput":{"hookEventName":"Stop","permissionDecision":"deny","permissionDecisionReason":R}}
         allow  -> exit 0,无输出
zcode  : block  -> {"decision":"block","reason":R}
         allow  -> {"systemMessage":M}
```

要点:**allow 必须真的 allow**。想让模型写 carry-over,就把它写进 block 的 `reason`(那一步本来就要继续),或者靠 goal 文本,而不是靠一个会顺带续跑的 `additionalContext`。

---

## 5. 有意义的替代方案(方案 B)

**闸门完全放弃阻断,只做"记录 + 注入"。**

- Stop:跑锚点、写 `events.jsonl`、发 `systemMessage`。永不 block。
- SessionStart:注入冻结项 + carry-over。
- UserPromptSubmit:记 `prompt_submitted`(给 `--audit` 一个真实的回合边界)。
- 续航 100% 交给宿主 goal 模式。

**优点**:跨四个宿主行为完全一致;D1/D2/D3 全部消失;没有任何一处需要知道 `Dui=3` 或 `?? 8` 这种会随版本漂移的常数;`hosts.json` 只需要一列(事件名)。
**代价**:失去"锚点红时不许结束回合"的硬保证。

**但这个代价的真实大小需要如实说**:那个保证在 Kimi 上只有 1 次、Codex 上 0 次、Claude/zCode 上因自设守卫也只有 1 次。**它现在换来的,已经接近方案 B 的水平了。** 方案 B 用"少一次续跑"换掉了四类宿主适配缺陷和一整套会漂移的常数。

我的推荐是 §4(保留一次阻断),但方案 B 是一个诚实的对手,如果第 2/3 轮有人能说明"一次阻断在实践中价值不大",我会切到 B。

---

## 6. allow / block / continue / complete 的判定表

前提:allow 与 continue **必须是两个不同的输出形状**(现设计把它们混在一个 `_allow` 里,是 D2 的根源)。

| 序 | 条件 | 判定 | 输出 | 理由 |
|---|---|---|---|---|
| 0 | 无 `.goals/active` / 环境变量禁用 / 事件名不符 | **allow(静默)** | exit 0 | 未参与的项目零成本 |
| 1 | **`background_tasks` 非空** | **allow(静默)+ 记 `deferred`** | exit 0 | 修 D6。锚点在半成品树上跑没有意义。宿主 `/goal` 就是这么做的 |
| 2 | `stop_hook_active` 为真 **且** 本回合续跑次数 ≥ `hosts.json` 的上限 - 1 | **allow(带原因)** | `systemMessage` | 最后一句话是闸门的,不是宿主的强制结束警告 |
| 3 | `## Anchor` 无法抽出唯一命令 / 可执行文件找不到 | **allow(带原因)** | `systemMessage` | 已经是现设计的行为,正确 |
| 4 | 冻结摘要与首回合不符 | **allow(带原因)+ 记 `frozen_spec_changed`** | `systemMessage` | 已经是现设计的行为,理由写得很好,保留 |
| 5 | 锚点超预算 / 126 / 127 / 9009 | **allow(带原因)** = unknown | `systemMessage` | 三态设计是这份工作里最好的部分,保留 |
| 6 | ceiling 已达 | **allow(带原因)** | `systemMessage` | 但 ceiling 的语义必须改成"闸门检查次数",并在文档里说清它 ≠ 自主迭代次数 |
| 7 | 锚点 green **且** `## Acceptance` 仍有 `[ ]` | **continue** | `additionalContext`(Claude/zCode)/ block+reason(Kimi/Codex) | 这才是应该续跑的场合:证据有了,工作没完 |
| 8 | 锚点 green **且** acceptance 全 `[x]` | **complete** | `systemMessage` + 记 `goal_met`;**不**自动删 `.goals/active` | 判"完成"是 stop condition 的事,不是闸门的。现设计:511-524 这段自我克制写得很对,保留 |
| 9 | 锚点 red **且** 输出签名与工作树都未变 | **allow(带原因)** | `systemMessage` | 无进展。adapt 的双因子判据方向对,但需要排除后台任务(见 D6 对 `_tree_digest` 的攻击) |
| 10 | 锚点 red,其余 | **block** | `decision:"block"` + `reason`(按宿主形状) | 唯一的硬拒绝 |

两条跨行规则:

- **每次判定都写事件**,包括 allow。现设计里 `anchor_unavailable` 之外的早退路径不写,`--audit` 因此看不见它们。
- **`reason` 里必须带闸门自己的回合号**(修 D8),让模型报的 turn 和闸门记的 turn 可对齐。

---

## 7. 对 `adapt` 候选的评估

先说对的:**adapt 独立发现了 D1,并且删掉了 `stop_hook_active` 早退守卫。** 那段 docstring 里"该守卫使闸门每个宿主回合只阻断一次,这是循环与轻推的区别"的判断,与我的实测完全一致。这是这份候选最重要的一步。
`hooks/claude.json` / `hooks/codex.json` 的拆分也对 —— 我验证过 zCode 的事件枚举只有 7 个且不含 PreCompact,拆分确有必要(虽然 zCode 对未知事件只是警告)。

**仍然存在的问题:**

1. **Codex 预算 `None`(不设上限)是危险的。** 我的复现证明 Codex 上这份 payload 根本进不了解析器,所以现在无害;但一旦 payload 修好,`turn.rs` 的 `loop` 里 `stop_hook_active = true; continue;` 没有可见上限 —— 变成一个真正的死循环风险。**未设上限不等于可以不设上限。**
2. **Claude 预算 7 算错了对象。** Claude 数的是"两次阻断之间没有工具调用"的连续次数(工具调用会把 `stopHookBlockingCount` 归零),而 adapt 数的是事件日志里连续的 `blocked:true`。一个健康的、每回合都调工具的 run,Claude 允许它几乎无限续跑,adapt 会在第 7 次把它释放掉。**保守方向的错,但是错。**
3. **zCode 的 `chain_flag=None` 过度保守。** adapt 的注释说 zCode 参考"列了 `stop_hook_active` 但没写语义"。二进制里语义是明确的:`t.stop_hook_active = e.stopHookActive`,而实参是 `e.stopHookContinuationCount > 0`。既然这个项目已经在读二进制定 `Dui=3`,同一份二进制里读出的字段语义没有理由不用。
4. **D2 没有修。** `continuation_budget_spent` 那条路径仍然是 `_allow(message, _obligation(...))` —— 带 additionalContext,在 Claude 上会继续。也就是说"预算花完了,回合到此为止"这句话本身会再烧一次续跑,而且不计入 adapt 自己的 streak(因为记的是 `blocked:False`),下一次又能从 0 开始阻断。**预算控制被自己的输出形状绕过了。**
5. **`_tree_digest` 每次 Stop 跑 4 个 `git` 子进程,外加对每个未跟踪文件读 1 MiB。** 在有大量未跟踪产物的仓库上,这可能比锚点本身还贵,而且它落在 hook 超时预算里(`ANCHOR_BUDGET_CEILING = 570` 是按"只跑锚点"算的)。同时如 D6 所述,有后台任务时工作树永远在动,`_stagnant` 永远为假。
6. **`${ZCODE_PLUGIN_ROOT:+--host zcode}` 依赖 hook 命令经过 shell 参数展开。** Claude Code 文档说明 `command` 在没有 `args` 时才走 shell;其他宿主是否如此未验证。这是把宿主识别押在一个**未证实**的执行细节上,而 `--host` 本可以从 stdin 的事件形状推断(Codex 有 `turn_id`,zCode 同时有 camelCase 与 snake_case 双份字段,Kimi 有 `client_type: "kimi_code_cli"`)—— 那是**观测**,不是配置。

---

## 8. 灵活分工与耐久更新(front-to-back)

### 8.1 前半段:Init + Research 必须留下产物

现在的 9 问访谈是好的,但它的产物只有 `decisions.md`。建议加一个**必需**产物 `<slug>.research.md`,结构固定三段:

- `## 事实`(每条带来源路径或 URL,不带来源的一律删)
- `## 未知`(明确列出没查到的,这是 anchor 质量的先行指标)
- `## 约束`(循环运行时的环境条件:什么命令能跑、要多久、需要什么凭据)

`validate_artifact.py` 强制:`## Anchor` 里的命令必须在 `research.md` 的 `## 约束` 里出现过。**这一条机制性地封死 D9**:一个没被 research 验证过能跑的命令,做不成 anchor。

research 用宿主原生 subagent 扇出(这是 SKILL.md 已有的正确判断),`SubagentStop` / `PostToolUseFailure` 记事件作为"确实扇出过"的证据。

### 8.2 后半段:谁做什么,保持灵活的边界在哪

现设计里 `## Roles` 表把"谁做"当作 owner 的选择,只有两行是约束 —— 这个划分是对的,我不动它。要改的是**耐久更新的落点**:

| 谁写 | 写什么 | 读作 |
|---|---|---|
| hooks | `events.jsonl`(exit code、摘要、回合边界、后台延迟) | 证据 |
| run | `### State/Lessons/Next`、commit、review | 声明 |
| run(唯一例外) | `## Challenges from the run` | 对条款的异议,由 owner 裁决 |
| owner | 冻结项、`decisions.md` 的 Decision/Rejected | 授权 |

这套划分是现设计最好的一部分,**我建议原样保留**,包括 `Who` 第四列(owner/agent)和 challenges 单独计数。唯一补充:`events.jsonl` 现在只在 Stop 里写,应该把 `prompt_submitted`(回合边界)和 `deferred`(后台延迟)也写进去,否则 `--audit` 的时间轴是残缺的。

### 8.3 "不变成第二个运行时"的判据

我建议用一条可检验的规则替代"感觉不像运行时":

> **闸门只允许拥有三类状态:一个 marker 文件、一个 append-only 事件日志、以及从 artifact 现算的投影。任何需要"更新"而非"追加"的机器状态都不允许。**

现设计满足这条(`--status` 那段"Nothing is stored"讲得很好)。adapt 的 `_tree_digest` 仍然满足(它存在事件里,append-only)。但 `stopHookContinuationCount` 这类"当前回合已续跑几次"的状态如果要精确维护,就会突破这条线 —— 这也是我倾向 §4 那种"把续航还给宿主"方案的原因之一:**宿主已经在维护这个状态了,我们不该维护第二份。**

---

## 9. 置信度与仍未证实的部分

**高置信(有源码/文档/实跑三者之一直接支撑,可复现)**
- D1 的实测输出、D2 的官方原文、D3 的 serde 复现、Kimi 的"exactly one continuation"、zCode 的 `Dui=3`、Claude 的 `?? 8` 与两处 `stopHookBlockingCount` 赋值、Codex `StopOutput` 无 `additional_context`、Stop 的官方可返回字段表、D5 的注释矛盾。

**中置信(单一来源,推理链短)**
- Claude Code 上 `additionalContext` 会**计入** 8 次上限:文档明说"same loop protections … namely the 8-consecutive-continuation cap",但我没有在二进制里逐行确认 `additionalContexts` 进入 `blockingErrors`。
- "工具调用使 `stopHookBlockingCount` 归零 ⇒ 8 次上限只防无进展":我看到了两处赋值(`next_turn` 置 0、`stop_hook_blocking` 置 `qd`),推断出这个语义,但没有跑 Claude Code 验证。
- zCode Stop 输出的 zod 对象非 `.strict()`,故多余键被剥离而非报错。我读到的片段里没有 `.strict()`,但没有穷尽搜索。

**明确未知,需要第 2/3 轮或实跑解决**
- Kimi 是否真的从 `kimi.plugin.json` 的 `hooks` 数组注册 hook(我确认了它会读 `kimi.plugin.json`,没确认它认这个键)。文档只写了 `config.toml` 的 `[[hooks]]`,且明说多余字段会让配置整体加载失败。
- Kimi 的 SessionStart 是"发即忘"事件 —— `additionalContext` 是否会被采纳?文档说"stdout 有内容可附加到上下文",若成立,注入的会是**原始 JSON 字符串**。
- Codex 的 Stop 阻断循环是否真的没有上限(`turn.rs` 那个 `loop` 我只读了 Stop 分支)。
- 四个宿主上 `_deny` 到底哪一路生效 —— 这一条 `_deny()` docstring 自己就承认是 claim(*"Which one the host honours is still a claim until a live run settles it"*),而**至今没有任何机制去 settle 它**。这就是我提议 `goal_doctor.py` 的直接理由。

**我没有做的事**:没有真的启动任何一个宿主跑一次完整 run。上面所有"每回合 N 次"的数字都来自源码常量与我的隔离复现,不是端到端观测。

---

## 10. 能证伪我这份提案的对抗案例

我把话说死,好让第 2/3 轮能打:

1. **如果有人给出一次真实的 Claude Code 会话录像/transcript,显示 ultra-goal 的 Stop hook 在一个用户回合内连续阻断了 ≥2 次** —— 那么 D1 错,`stop_hook_active` 的语义不是我读的那样,§4 的前提松动。
   *可证伪方式*:装 main 的 hook,armed 一个必红的 goal,发一个提示,数 `events.jsonl` 里 `anchor_checked` 的条数。**> 1 则我错。**

2. **如果 Claude Code 上 `hookSpecificOutput.additionalContext` 实际会结束回合** —— 那么 D2 错,官方文档那句话应作别解,`_allow` 的命名是对的。
   *可证伪方式*:写一个只发 `{"hookSpecificOutput":{"hookEventName":"Stop","additionalContext":"x"}}` 的 Stop hook,看回合是否结束。

3. **如果 Codex 实际会忽略未知字段** —— 那么 D3 错。我的复现只覆盖了 serde 1.0.229 与我手抄的结构定义;若 Codex 实际用的 serde 版本行为不同,或 `flatten` 的存在使 `deny_unknown_fields` 在真实构建里失效,结论翻转。
   *可证伪方式*:在 Codex 里注册一个发送带 `hookSpecificOutput` 的 block payload 的 Stop hook,看回合是否被拦。**被拦则我错。**

4. **如果宿主原生 goal 模式在实际长跑中比闸门更容易被模型骗过** —— 例如 Claude 的小模型评估器把"我觉得测试应该过了"读成 met —— 那么 §4.2 的组合方案的价值就取决于评估器读闸门系统消息的可靠性,而那是我没有测过的。
   *可证伪方式*:跑一个锚点恒红但模型口头宣称完成的 goal,看 `/goal` 是否提前判 met。**若在有闸门 systemMessage 的情况下仍判 met,§4.2 失效,应退回 §5 方案 B 或保留强阻断。**

5. **如果 owner 的实际用法是"我坐在旁边,每回合敲一次回车"** —— 那么 D1 根本不是缺陷,现设计的 1 次/回合完全够用,我这份报告的第一顺位排错了。
   *这是 owner 才能回答的问题,也是我最想先听到答案的一个。*

6. **如果 `hosts.json` + `doctor` 的维护成本超过它防住的错误** —— 四个宿主每月发版,常数会漂移。若三轮下来发现每次宿主升级都要改表,那么 §5 的方案 B(不依赖任何宿主常数)才是最小可行架构,§4 是过度工程。

---

## 附:我在本轮里做过的可复现实验

1. `probe/`(我的目录):用 serde 1.0.229 复现 Codex `StopCommandOutputWire`,验证 `hookSpecificOutput` 被拒。
   `CARGO_TARGET_DIR=./target cargo run --offline`(仅用本机已解压的 crate,未安装任何依赖)。
2. `fixture/`(我的目录):最小 goal artifact + 两次 Stop 输入,验证 `stop_hook_active=true` 时 main 的闸门完全静默。

两个快照仓库、两个 live checkout、宿主全局配置均未修改。

---

*reviewer: claude · round 1 · 独立判断,未与其他评审协调*
