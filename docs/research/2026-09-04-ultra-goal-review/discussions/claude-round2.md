# Ultra Goal 对抗式交叉质询 · 第 2 轮 · reviewer: claude

分工角度:宿主生命周期与模型反馈通道。本轮任务是回应 `rounds/codex-cross-examination.md`、挑战 zCode 的完成自动化、并修补或撤回我自己关于原生 goal 集成的假设。

已读:`reviewers/claude/round1.md`(我的)、`reviewers/zcode/round1.md`、`rounds/codex-round1.md`、`rounds/codex-cross-examination.md`、`rounds/challenge-cases.md`、`local-evidence/verification.md`、`work/task-state.md`。
Kimi 的 `reviewers/kimi/round1.md` **在我本轮开始与结束时均不存在**(`reviewers/kimi/` 下只有 0 字节的 `round1-result.json` 与 `round1-stderr.log`),按指示不等待。

## 本轮证据性质的前置声明

本轮我做的全部是:官方参考文档检索、已安装宿主二进制/源码检索、以及**一次文件系统观测**。
**我没有在任何宿主上启动过一次真实 goal 运行。** 我第 1 轮的 serde 复现、main 的 69 项 / adapt 的 93 项单元测试、以及各方的隔离夹具探针,全部属于**发射端/解析端测试**:它们证明"我们发出的字节是什么形状"和"某个结构体接不接受这个形状"。它们**不能**证明宿主的回合会计、评估器裁决、续跑上限在真实会话里如何交互。凡属后者,本报告一律标注【未证实】并给出判定方法。

---

## 1. 对 codex 八条质询的分类回应

| # | 质询 | 我的分类 |
|---|---|---|
| 1 | 不可伪造/信任边界是假的 | **同意,并撤回我自己的表述**(见 §2 R2) |
| 2 | 追踪消费者而非发射者;改用回合内普通工具验证 | **同意,且本轮取得了决定性证据**(见 §3.1、§2 R1) |
| 3 | 绿锚点+勾选框+新报告文件 ≠ 完成 | **同意,并据此挑战 zCode**(见 §4) |
| 4 | 逐宿主确定实际暴露的创建/暂停/恢复/完成操作 | **同意质询的必要性;本轮给出源码级答案**(见 §3.2) |
| 5 | 八次上限不是通用回合上限,五个计数器要分开 | **同意,撤回我第 1 轮的标题句**(见 §2 R4) |
| 6 | Kimi 唯一一次外部 Stop 修正可能已耗尽 | **同意,且有官方文档给出诚实出口**(见 §3.3) |
| 7 | 归属与证据标签订正 | 不涉及我的主张;我第 1 轮已把 adapt 标注为候选而非发布版 |
| 8 | 强制九问访谈/每任务研究文件/固定角色/每回合提交,辩护或撤回 | **部分撤回我自己的提案**(见 §2 R6) |

---

## 2. 我的撤回(按严重度)

### R1 —— 撤回 §4.2 的整个组合机制:`systemMessage` 不进模型上下文 【已证实 · 文档原文】

我第 1 轮 §4.2 把组合方案写成:

> 闸门每回合会在 `[ultra-goal]` 前缀的系统消息里报告它测到的 exit code —— 引用那条消息,不要引用你自己对代码的判断。

**这个机制不成立,整段撤回。** 官方 JSON 输出字段表(`hooks.md:926`)对 `systemMessage` 的定义是:

> `systemMessage` | none | **Warning message shown to the user.** In Agent SDK and `--output-format stream-json` output, it can arrive as an `SDKInformationalMessage`

它是**给用户看的告警**,不是会话消息。对比同一份文档对 `additionalContext` 的定义(`hooks.md:972`):

> The `additionalContext` field passes a string from your hook into Claude's context window. Claude Code wraps the string in a system reminder and **inserts it into the conversation** at the point where the hook fired.

两者是不同的投递目标。而 Claude Code 的 goal 评估器要读的正是会话:`ProposeGoal` 工具 `condition` 参数的自述原文(二进制字符串)是

> The completion condition to propose, written so a separate evaluator can **verify it from the conversation** (e.g. "all tests in test/auth pass (bun test exits 0)").

所以我设计的"让 stop condition 引用闸门系统消息"这一步,引用的是一条评估器**看不到**的东西。codex 第 2 条质询"UI 警告不是模型上下文里的证据"是对的,而我第 1 轮恰好犯了它点出的错误:**我追踪了发射者,没追踪消费者。**

顺带订正我第 1 轮 §4.4 输出表里 `allow -> {"systemMessage":M}` 的用途描述:这个形状本身是合法的(它不会像 `additionalContext` 那样触发续跑),但它只能用来**告知用户**,不能承载任何要给模型或评估器的内容。

### R2 —— 撤回"闸门写不可伪造的证据日志" 【已证实 · 一次文件系统观测】

我第 1 轮 §4.1 能力表里有一格写着"**写不可伪造的证据日志**",§9 还把它列进高置信。**撤回"不可伪造"。**

- 执行中的 agent 对 `.goals/<slug>.events.jsonl` 有写权限,可以追加伪造条目(zCode 的实验 C 已复现)。哈希链不构成障碍:同一个进程能读全部前序条目,也能重算链。
- zCode 3.2-5(b) 提出把宿主传入的 `session_id` 写进事件,理由是"模型上下文里看不到它"。**这个前提在 Claude Code 上是假的,我直接观测了:**

```
$ ls -la ~/.claude/projects/-private-var-…-reviewers-claude/
01176958-bd1a-4791-b4b9-f8299634673c.jsonl     (22:02,正在写)
61cf0a7d-5626-4644-abb4-f2e170c4c5e1.jsonl     (21:56)

$ head -1 …/01176958-bd1a-4791-b4b9-f8299634673c.jsonl | python3 -c "…"
sessionId: 01176958-bd1a-4791-b4b9-f8299634673c
```

会话 UUID 就是转录文件名,目录可枚举,mtime 最新的那个就是当前会话。**模型一条 `ls` 就能自知 session_id。** 它不是秘密能力。

**机制实际能证明什么(这是我认为应当写进设计的表述)**:事件条目证明**一个非模型进程在某个墙钟时刻观测到某条命令的退出状态**。它的价值是**来源标注(provenance)与遗漏检测**,不是抗篡改。一个协作式本地工作区里没有信任边界,加上一个假的信任边界比没有更糟:它会让 owner 以为 `--audit` 全绿意味着别的东西。

session 绑定仍然值得做,但理由要换成 **归属护栏**:阻止同一 cwd 下第二个会话(或被委派的 worker)去跑锚点、改状态、认领所有权。这是 codex 第 1 轮事实 2 与我第 1 轮的同一发现,它是**误触防护**,不是**防伪**。

### R3 —— 订正"hook 永远无法创造回合" 【文档 + schema 原文,但未做宿主实跑】

我第 1 轮 §4.1 表格写"跨用户回合续跑:宿主 goal ✅ / Stop hook ❌",§5 又说"续航 100% 交给宿主 goal 模式"。zCode 的 D1 更强:"四位评审材料里没有任何机制创造下一回合"。

**这在 Claude Code 上是错的。** `hooks.md:459` 的公共字段表:

> `asyncRewake` | no | If `true`, runs in the background and **wakes Claude on exit code 2**. The hook's stderr, or stdout if stderr is empty, is shown to Claude as a system reminder so it can react to a long-running background failure

`hooks.md:3690`:

> Hook output is delivered on the next conversation turn. If the session is idle, the response waits until the next user interaction. **Exception: an `asyncRewake` hook that exits with code 2 wakes Claude immediately even when the session is idle.**

二进制里的 schema 自述(2.1.260):

```
asyncRewake: O().optional().describe("If true, hook runs in background and wakes the model on exit code 2 (blocking error). Implies async.")
rewakeMessage: "@internal Custom prefix for the system-reminder shown to the model…"
rewakeSummary: '@internal One-line summary shown to the user … Defaults to "Stop hook feedback".'
```

`rewakeSummary` 的默认值直接就是 `"Stop hook feedback"`,这是它被用在 Stop 事件上的强指示。运行时符号还有 `flushPendingAsyncRewakeHooks`。

**所以"hook 只能延长回合、不能创造回合"这个四方共有的论断,在 Claude Code 上有反例。** 但我把边界划死,不让这条被过度使用:

1. `asyncRewake` 蕴含 `async`,而 `hooks.md:3591` 明说 **async hook 不能阻断,`decision` 之类字段一概无效**。所以它是**回合创造器,不是回合延长器** —— 它与"锚点红时不许结束回合"是两种不同的东西,不能互相替代。
2. 它是 **Claude Code 独有**。zCode 的 hook 事件枚举只有 7 个且无此字段;Kimi 的 `[[hooks]]` 只允许 `event/matcher/command/timeout` 四个键(多写会导致 config.toml 整体加载失败);Codex 的 `StopCommandOutputWire` 带 `deny_unknown_fields`。
3. **我找不到它的次数上限。** 二进制里 rewake 相关符号只有四个,没有 cap 常量;而 8 次上限那条是给同步 Stop 阻断的。一个恒定 exit 2 的 asyncRewake hook 是否会无限唤醒模型,**【未证实】**。找不到常量不等于没有上限。
4. 因此:**我撤回"hook 不能创造回合"的断言,但不把 `asyncRewake` 放进推荐设计。** 见 §7 的 C-2。

同理订正 zCode D1 的"unattended 只有 Codex 也许成立":Kimi 官方文档给出了一条真实的无人值守路径 —— `kimi -p "/goal …"`,**目标完成退出码 0、阻塞 3、暂停 6**(`docs/zh/guides/goals.md:151`)。那是宿主自带的无人值守 runner,不需要任何 hook 参与。

### R4 —— 撤回第 1 轮 §0 的标题句,接受 codex 第 5 条 【自相矛盾】

我第 1 轮 §0 写"Claude Code 实测 1 次/用户回合",§2.1 同一份报告里又写"一旦模型调用工具,计数归零 → 实际近似无界"。两句话说的是不同计数器,而我的标题句把它们坍塌成一个数字。codex 第 5 条质询指出了这一点,**我接受**。分开列(这是我建议写进设计的五个名字):

| 计数器 | 谁维护 | 会被什么复位 | 谁看得见 |
|---|---|---|---|
| **业务迭代**(第几个有意义的工作切片) | 模型/artifact | 什么都不复位 | 模型;闸门看不见 |
| **宿主回合**(一次用户提示到回合结束) | 宿主 | 每条用户提示 | 宿主;hook 通过 `stop_hook_active` 间接感知 |
| **工具/模型步**(回合内的 agentic loop) | 宿主 | 每个宿主回合 | 宿主 |
| **Stop 修正次数**(连续无进展保护) | 宿主 | **Claude:模型调用工具即归零**;zCode:`stopHookContinuationCount`;Kimi:硬 1 次 | 宿主;hook 只拿到布尔 |
| **闸门检查次数**(锚点被执行了几次) | 闸门自己 | 什么都不复位 | 闸门;**模型看不见** |

第 1 轮 D8 说的"turn 一词指四件不同的事"就是这张表的另一面。`## Stop condition` 的 `ceiling: 40` 数的是**最后一行**,而 SKILL.md 让模型"state which turn you are on"时,模型只能猜第一行。**最小修法不变:block 的 `reason` 里带上闸门自己的编号。** 这是 hook 独占的信息,符合 "a hook inlines only what it alone possesses"。

### R5 —— 收紧第 1 轮 §6 第 7 行的 zCode 分支 【zCode Z3 独立复核通过】

我第 1 轮判定表第 7 行(绿锚点+acceptance 未闭)写"continue:`additionalContext`(Claude/zCode)"。zCode 的 Z3 说 allow 分支会丢弃 additionalContext。**我独立复核了,Z3 成立**:

```
$ grep -o "injectHookAdditionalContextIntoMessageHistory([^)]*)" zcode.cjs | sort | uniq -c
   1 injectHookAdditionalContextIntoMessageHistory(on.SessionStart,A.additionalContexts)
   1 injectHookAdditionalContextIntoMessageHistory(on.SessionStart,C.additionalContexts)
   1 injectHookAdditionalContextIntoMessageHistory(on.Stop,o.additionalContexts)
   1 injectHookAdditionalContextIntoMessageHistory(on.UserPromptSubmit,D.additionalContexts)
```

Stop 那一处的上下文(同一份二进制,原文):

```js
return this.shouldContinueAfterStopHooks(o, e.stopHookContinuationCount)
  ? (e.stopHookContinuationCount += 1,
     this.injectHookAdditionalContextIntoMessageHistory(on.Stop, o.additionalContexts),
     e.turnMachine = new Va(e.turnMachine.aggregateResults()), "continue")
  : (e.activeTurn && await this.fallbackPendingGuidesToQueue({…}), …)
```

注入调用**在三元表达式的续跑分支内**。allow 时 `o.additionalContexts` 被丢弃。**我确认 zCode 的 Z3,并因此收紧自己的表:** 在 zCode 上,"continue" 必须走 `decision:"block"` + 非空 `reason`(`OUr` 要求 `additionalContexts.length>0`,而 `e6r` 会把 `reason` 推进 additionalContexts),不能靠 `hookSpecificOutput.additionalContext` 单飞。

更重要的推论(这是我这轮的立场核心):**闸门在任何宿主的 allow 路径上都不应该发"接着干"的文字。** 四个宿主各有各的失效方式 —— Claude 会静默续跑并消耗上限、zCode 丢弃、Kimi 没有通道、Codex 直接解析失败。**能同时在四家成立的规则只有一条:allow 就是安静地 allow。**

### R6 —— 撤回我第 1 轮 §8.1 的"必需 research 文件" 【回应 codex 第 8 条】

我第 1 轮 §8.1 提议新增**必需**产物 `<slug>.research.md`,并让 `validate_artifact.py` 强制"`## Anchor` 里的命令必须在 research.md 的 `## 约束` 里出现过"。

**撤回"必需文件"这一半。** codex 第 8 条对"每个任务一个研究文件"的反对是对的:owner 要的是更小、更自发的东西,而我提的是又一个模板 + 又一条校验器规则,来解决一个**用一条语法约束就能解决**的问题。

**保留的一半(它才是 D9 的真修法)**:`## Anchor` 必须是 fenced 单行或显式 `command:` 前缀,由 validator 拒绝歧义。我第 1 轮 D9 的失效样例(`See \`docs/anchor-rationale.md\` for why. Run \`pytest -q\`…` → 抽出 md 文件 → exit 126 → 永远 unknown → 闸门零效力)只需要这一条就封死,不需要新文件。

同理,我不再主张"每阶段固定 reviewer + critic"。审查的选择应当由**错误代价**决定,而不是由阶段决定 —— 这是 codex 临时替代方案里"Semantic review is selected when required by the task or cost of error"的表述,我同意。我第 1 轮 §8.2 说"`## Roles` 的划分是对的,我不动它"仍然成立,因为那张表本来就把"谁做"留给 owner 选。

---

## 3. 本轮新增的宿主事实(逐条带出处)

### 3.1 决定性事实:Claude Code 的 `/goal` 就是一个 Stop prompt hook,评估器读的是会话消息

`hooks.md` 的 Stop 段开头 Tip(原文):

> The [`/goal`](/docs/en/goal) command is a **built-in shortcut for a session-scoped prompt-based Stop hook**. Use it when you want Claude to keep working toward a condition without writing hook configuration.

二进制里对得上:goal 循环体判断某个 Stop hook 是否是目标自己的评估器,用的就是 `hook?.prompt === activeGoal.condition`;Stop hook 执行入口收到的是消息数组:

```js
o.executeStopHooks(ce(e).mode, e.abortController.signal, void 0, !1,
                   e.agentId, e, [...e.messages, ...s], void 0, "fork_dispatch")
```

**这一条同时回答了三件事:**

1. **codex 第 2 条的替代方案是对的,而且现在有证据。** 评估器是一次以会话消息为输入的模型调用。**唯一无歧义地在 `e.messages` 里的东西,是工具调用的结果。** 所以验证要想被评估器看见,就得是**回合内的一次普通工具调用**(模型自己跑锚点、拿到真实 exit code),而不是一个 hook 的输出。这同时满足 challenge case 20(命令留在宿主的权限与取消边界内,不被搬进 hook 绕过)和 codex 第 1 轮 E 条。
2. **"两个机制争夺终止权"在 Claude Code 上不是那种形态。** 闸门的 command Stop hook 与 goal 的 prompt Stop hook **是同一类机制,在同一次 Stop 聚合里一起跑**。闸门 block → 回合继续;评估器返回自己的 met/not-met 裁决。它们不是两个互不知情的循环。
3. **但它们的**顺序**关系【未证实】,而这正是本轮最重要的未决问题。** 评估器拿到的是 `[...e.messages, ...s]` 这个快照,而闸门的 `additionalContext` 是"inserted into the conversation at the point where the hook fired"。同一次 Stop 里闸门的输出是否已在评估器的快照内,我读 minified 代码**不敢断言**。**设计推论(不需要等这个问题解决就成立):任何承重证据都不能只放在闸门的 `reason`/`additionalContext` 里。** 放进工具结果就没有这个歧义。

评估器的失效方向(二进制,minified,标注为读码推断):`timedOut` 且该 hook 是目标条件 → `De="cancelled"` + `g("goal_met","evaluator_timeout")`;`hook_non_blocking_error` / `hook_error_during_execution` 落在目标条件上 → `De="error"` + `g("goal_met","evaluator_error")`;另有 `p("goal_met","impossible")` + `tengu_goal_failed` 与 `tengu_goal_achieved`。**没有一条把评估器故障映射成 met。** Claude Code 的完成判定是**失败关闭**方向。下面 3.2 会看到 zCode 恰好相反。

### 3.2 逐宿主实际暴露的操作表 —— 直接回答 codex 第 4 条

这张表是本轮对 codex 第 4 条的正面回答。**结论先行:四家宿主的"原生 goal"不是一件东西,完成判定分三种语义。任何把它当统一抽象的设计都是错的。**

| 宿主 | 模型/技能可创建? | 模型/技能可暂停/恢复? | 模型/技能可完成? | 完成由谁判定 | 判定器故障时 |
|---|---|---|---|---|---|
| **Claude Code 2.1.260** | ✅ `ProposeGoal` 工具(用户一键批准;`auto`/`alwaysAsk`/`disabled` 三档设置;**agent context 内不可用**) | ❌ 无 | ❌ **不能清除** | **独立评估器**(Stop prompt hook,读会话) | **失败关闭**:timeout→cancelled,error→error |
| **zCode 0.16.5** | ❌ 只有斜杠命令 `/goal`(别名 `target`) | ❌ 只有 `/goal pause\|resume\|clear` | ❌ | **独立模型调用** `TargetCompletionVerification` | ⚠️ **失败开放 —— 判为完成** |
| **Codex 0.150.1** | ✅ `create_goal(objective, token_budget?)` 工具 | ❌ 明文禁止 | ✅ `update_goal(status:"complete"\|"blocked")` | **agent 自己声明** | 不适用 |
| **Kimi 0.40.1** | ✅ `/goal <objective>`(prompt 模式也支持) | ❌ `/goal pause\|resume\|cancel` 是 TUI 控制命令 | ✅ agent 标记 `complete` | **agent 自己声明** | 运行时/供应商/模型错误 → **paused** |

出处:

- **Claude Code**,二进制 2.1.260 字符串:
  `ProposeGoalTool`;工具描述 *"Propose a session goal condition, with one-keypress user approval; once set, Claude keeps working until a separate evaluator confirms it is met"*;
  *"**ProposeGoal only proposes a new goal; it cannot clear one. The user can clear an active goal with `/goal clear`.**"*;
  *"ProposeGoal cannot be used in agent contexts"*;
  设置项 `@internal`:*"'auto' (the default when absent) lets the model choose per proposal whether to ask for approval via its `ask_user` parameter; 'alwaysAsk' routes every model-proposed goal through the approval dialog; 'disabled' turns the tool off. A typed /goal is unaffected. **Consent-affecting**…"*
- **zCode**,`/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs`:
  斜杠命令注册项 `{aliases:["target"], name:"goal", usage:"/goal [pause|resume|clear|replace <objective>|<objective>]"}`;运行时符号 `createSessionTarget / clearSessionTarget / pauseActiveTargetForCancellation / activatePausedTargetAfterResume / continueActiveTargetIfIdle / continueActiveTargetAfterTurn / TargetCompletionVerification`。我在工具名清单里没找到任何 target/goal 工具 —— 只有斜杠命令。
- **Codex**,`codex-rs/ext/goal/src/spec.rs`(公共修订 03861e6):
  `get_goal` / `create_goal` / `update_goal` 三个 `ToolSpec::Function`。`create_goal` 描述:*"Create a goal only when explicitly requested by the user or system/developer instructions; do not infer goals from ordinary tasks. … **Fails if an unfinished goal exists**"*。`update_goal` 描述:*"Set status to `complete` only when the objective has actually been achieved and no required work remains. … **You cannot use this tool to pause, resume, budget-limit, or usage-limit a goal; those status changes are controlled by the user or system.**"* 另有 `api.rs` 的 `set_thread_goal`/`clear_thread_goal` 与 `runtime.rs` 的 `apply_external_goal_set`/`apply_external_goal_clear`/`usage_limit_active_goal_for_turn`(宿主内部路径,非工具)。
- **Kimi**,`docs/zh/guides/goals.md`(已抓取副本):第 13 行"每个轮次结束后,它会检查目标是完成/阻塞/暂停还是活跃";第 39、67 行 agent 自行判断并标记 `complete`;第 104 行"**暂停**:你暂停了它、中断了当前轮次、恢复了原本有目标的会话,或**遇到模型、供应商或运行时错误**";第 105 行 blocked 的三个条件;第 96-98、151 行管理命令为 TUI 控制;第 151 行 prompt 模式退出码 0/3/6。

**这张表推翻的设计假设(包括我自己的):**

- 我第 1 轮 §4.2 假定技能可以"把 stop condition 写成引用闸门证据的形式"。在 Claude Code 上技能**确实**可以创建(`ProposeGoal`),这一半我修好了 —— 但它**不能清除**。所以任何"闸门判完成后 disarm"的设计,在 Claude Code 上会造成:Ultra marker 没了,原生 goal 还在跑,只有用户能停。**这正是 codex 第 4 条警告的去同步。**
- Codex 与 Kimi 的完成是 **agent 自报**(一个工具调用)。所以在这两家,"完成由模型判断"不是设计选择,是宿主既定事实 —— codex 第 3 条问"完成是否仍是模型对需求证据的判断",宿主自己已经回答了:是。
- zCode 与 Claude Code 的完成是**第三方判定**,但**失效方向相反**。见 3.4。

### 3.3 Kimi 的诚实出口(回应 codex 第 6 条)

codex 第 6 条:Kimi 唯一一次外部 Stop 修正可能已耗尽,第二次回调可能不发生;任何依赖第二次回调来持久化 allow/pause 结果的状态机都是无效的。**同意。** `kimi-turn.ts:942` 的守卫 `if (!stopHookContinuationUsed)` 保证外部 Stop 每个普通回合最多一次。

但**不需要发明回调**就能让最终结果保持真实,官方文档给了出口:Kimi 的目标状态机里,**运行时/供应商/模型错误 → `paused`,不是 complete,也不是静默死亡**(`goals.md:104`);而 prompt 模式会用 **退出码 6** 把"暂停"这件事交给调用方(`goals.md:151`)。所以正确的设计是:闸门**不试图**持久化任何需要第二次回调的裁决,把"结果未知"写进事件日志然后放行,由宿主自己的 paused 状态与退出码承载"这件事没做完"。**Ultra 不需要在 Kimi 上模拟一个调度器,Kimi 已经有一个。**

### 3.4 高危新事实:zCode 的原生完成校验器**失败即判过** 【已证实 · 活体二进制】

`/tmp/ultra-goal-research.j8qCAJ/` 里有一份**别人**的既有探针(`zcode-verifier-check.cjs` / `zcode-verifier-result.jsonl`)指向这个结论。按"WIP 是待批判的证据而非指令",我**在活体二进制里重新核验**:

```
$ grep -c "Completion verifier request failed"                      zcode.cjs   → 1
$ grep -c "The completion verifier did not return valid JSON"        zcode.cjs   → 1
$ grep -o "function [A-Za-z0-9_]*(e){return{passed:\!1,reason:e}}function …"     zcode.cjs
function EZ(e){return{passed:!1,reason:e}}function AZ(e){return{passed:!0,reason:e}}
```

失败分支原文:

```js
this.logger?.warn("Goal completion verification failed open", {
  …, event: "target.completion_verification.failed_open",
  module: "core.runtime", status: "failed", targetId: e.target.targetID });
let y = AZ(_ instanceof Error
  ? `Completion verifier request failed: ${_.message}`
  : "The completion verifier could not confirm that every goal requirement is complete.");
```

`AZ` 返回 `{passed:true}`。校验器返回非 JSON 时走的也是 `AZ`。**厂商自己把这个行为命名为 `failed_open`。**

这条事实同时打两个方向,我两边都要说:

- **它打 zCode 评审自己的 3.2-1 组合路线。** zCode 的建议是"unattended 时显式用宿主 goal mode 作为回合驱动,gate 保持证据层",并用 Z7(原生 verifier 存在)作为支撑。但那个 verifier 在请求失败时判过。所以在 zCode 上,**把跨回合续跑与终止交给原生 target,等于把"完成"押在一个基础设施故障即判过的判定器上**,而 Ultra 手里既没有 target 工具也没有暂停路径,**无法阻止它**。zCode 的报告引用了 Z7 却没有报告这一点。
- **它是我第 1 轮 §4 最强的正面论据,但结论要改。** 原生完成判定可以失败开放 ⇒ 一条确定性的锚点记录确实是它缺的互补物。但闸门能做的**不是**阻止 —— allow 不能暂停一个外层原生目标(codex 第 4 条),而 zCode 上技能连 target 操作都没有。闸门能做的只有一件:**在日志里留下"宿主报告完成,而闸门在该修订上测到 exit 1"这句可对照的真话。** 这是 challenge case 23 的答案,也是这个机制在 zCode 上唯一诚实的承诺。

---

## 4. 我挑战的 peer 命题:zCode 的完成自动化(3.2-2 与 3.2-5)

这是我本轮的指定攻击面。zCode 把 3.2-2 称为"本轮最重要的新 gate",我认为**这两条应当被拒绝**,并给出替代。

### 4.1 挑战 3.2-2:"绿 + open acceptance 或 review 文件缺失/早于最后一次代码改动 → block 一次"

zCode 原文把判据描述为"**判据全部是机械事实**(事件日志 + 文件 mtime)"。文件 mtime 确实是机械事实。**但它机械地度量的量,不是被判断的量。** 逐条:

1. **缺失 vs 存在是不对称的,而 zCode 把它们当成一个判据。**
   - 文件**不存在** ⇒ 审查确定没发生过。这是**合法的遗漏检测**,我支持。
   - 文件**存在且更新** ⇒ 关于内容与结论**什么都没证明**。一份写着 `REJECT` 的 review 文件完全满足这个 gate。codex 第 3 条"新报告可能说 REJECT;匹配的哈希证明同一性而非正确性"正是这一点。
2. **释放条件制造了错误的机械激励。** 规则是"block 一次,其后放行"。所以对一个想结束回合的 run,最便宜的合规动作是**写一个文件**,不是**做一次审查**。这比它要修的 D2 更糟:D2 里 false completion 至少还要模型自己撒谎;有了这个 gate,撒谎被替换成一个 `Write` 调用,而且留下了一份看起来像证据的产物。
3. **它踩到 zCode 自己的 D3-2。** zCode 的 D3-2 说 review/critic 产物在 gitignore 的 `.goals/.work/` 里、"压实了就消失、最强的证据最不持久"。而 3.2-2 让完成的机械前置条件**恰好落在这份非持久产物上**。同一份报告里的两条建议互相削弱:3.2-6 要把 `.work/` 放进 git 才能让它承重,那就得先接受 git 噪音;不接受,gate 就在读一个会消失的东西。
4. **"早于最后一次代码改动"需要算出"最后一次代码改动",而这是 `_tree_digest` 的同一个坑。** 我第 1 轮 D6 打过:有后台任务在跑时工作树一直在动。zCode 自己的 D7 也承认树摘要度量的是"动了"而不是"有进展"。更具体的坏路径:审查本身要读代码、跑锚点、写文件;审查结束后模型一次 format 或一次 commit 就让 review 重新"过期",于是绿锚点再次被 block —— 而它已经用掉了"block 一次"的额度,或者要维护"per green episode 已 block 过"的状态,**闸门就长出了它声称不建的那个 runtime**(这正好是 zCode 自己 §5 对自身代码提出的要求)。

**我的替代(更小,且不假装语义)**:闸门只允许对**缺失**做一次遗漏 block,并且措辞只陈述它观测到的事:

> `reason`: "本 goal 的 `.goals/.work/<slug>-review.md` 不存在。若 `## Acceptance` 的判定需要审查,现在做;若这个目标不需要审查,在 `## Challenges from the run` 里说明理由。"

闸门**永不**把"存在且更新"读成"通过",**永不**因为 mtime 陈旧而 block。审查结论是语义判断,它的归属是模型与 owner,机器只负责"我没看到它发生过"。

### 4.2 挑战 3.2-5(c):"绿 + acceptance 全 `[x]` + review 新鲜 → gate 写 `goal_complete` 并 disarm"

**这一条我认为是本轮四方提案中最危险的一条,应当整条拒绝。**

1. **它把模型写的 markdown 勾选框变成了机器效果。** `[x]` 是 run 写的纯断言 —— zCode 自己的 D2 第一句就是这么说的。3.2-5(c) 让这些断言直接触发 disarm。于是 run 获得了一条**合法的自我终结路径**:勾满勾选框 → 闸门 disarm → 目标在日志里被记成 `goal_complete`。zCode 的 D3-3 已经指出 `.goals/active` 是 run 可写的、run 可以自己续命;3.2-5(c) 把同一个漏洞装上了**自动关机**开关,而且这次是闸门亲手写下"完成"这个词。
2. **它与我第 1 轮 §6 第 8 行直接冲突,而我坚持我那一行。** 我第 1 轮的判定是:绿 + acceptance 全闭 → **complete 语义只记事件,不自动删 `.goals/active`**;"判完成是 stop condition 的事,不是闸门的"。main 的 `goal_stop.py:511-524` 那段自我克制写对了,adapt 也没破坏它。**zCode 提议移除的正是这份克制。**
3. **它在 Claude Code 上必然去同步。** §3.2 已证:技能**不能**清除 Claude Code 的原生 goal(`"it cannot clear one. The user can clear an active goal with /goal clear"`)。所以闸门 disarm 掉 Ultra marker 之后,原生 goal 仍在运行,而 Ultra 的 SessionStart 注入已经消失 —— 后续回合里模型失去 artifact 上下文,原生评估器却还在推动它继续。这是 challenge case 22 的最坏具体形态,而它是**由 3.2-5(c) 制造的**。
4. **在 zCode 上它还会与 `failed_open` 叠加。** 宿主可能因为一次请求失败判过,闸门可能因为勾选框判过。两个判过没有一个读了需求证据。

**我的替代**:闸门写 `completion_claimed` 事件,字段是**并列的两栏** —— run 的主张(acceptance 全闭、review 存在与否)与闸门的测量(锚点命令、退出码、artifact 摘要、闸门回合号)。它**不写 `goal_complete`,不 disarm**。disarm 是 owner 的效果;在 Codex/Kimi 上它还额外是宿主给模型的一个工具(`update_goal` / 标记 complete),那条路已经存在,Ultra 不该造第二条。

### 4.3 我同意 zCode 的部分(明确记录,避免被读成全面反对)

- **Z3(zCode allow-mute)成立**,我独立复核通过(§2 R5),并把结论推得更远:allow 路径在四家都不该带模型可读文字。
- **D5(冻结基线无重置 → run 永久僵死)成立**,`frozen_digest` 取自首条 `anchor_checked` 且永不重置,而 owner 合法 Modify 之后每次 Stop 都 `frozen_spec_changed` 放行。**它的 3.2-4 re-baseline 仪式是对的**,我采纳进 §5。这一条是本轮我认为 zCode 最有价值的贡献。
- **D4(ceiling 是 run 的软旋钮)成立**,`## Stop condition` 不在 `FROZEN_SECTIONS` 里。**3.2-3 基线化是对的**,我采纳。
- **D7 后半(树摘要有执法权而证据强度不足,应降为 advisory)** 我同意,且这与我第 1 轮 D6 是同一个洞的两面。

---

## 5. 我推荐的最小修订设计

相对我第 1 轮的 §4,这一版**更小**:去掉了 `hosts.json` 的续跑上限列、去掉了必需 research 文件、去掉了"锚点红时硬阻断"作为核心承诺。相对 codex 的临时替代方案,我只增加两条它没有明说的机械约束(re-baseline 与 ceiling 基线化,都来自 zCode 的发现)。

### 5.1 五条原则

1. **回合循环归宿主,而且它在每家是不同的东西。** 技能不模拟调度器、不模拟运行时。技能声明一张 §3.2 那样的逐宿主表:**我可以创建什么、只有用户能做什么、完成由谁判、判定器怎么失效**。原生完成**不是证据** —— 在 zCode 上它可能是 `failed_open`,在 Codex/Kimi 上它是 agent 自报。
2. **验证是回合内的一次普通工具调用,不是 hook。** 模型自己跑验收命令,拿到真实退出码。四条理由,都有出处:(a) 工具结果无歧义地在 Claude Code 评估器读的 `e.messages` 里(§3.1);(b) 命令留在宿主的权限与取消边界内(challenge case 20);(c) 模型在**同一回合内**拿到真实输出,还有机会解释它并更新状态(codex 第 1 轮的判断);(d) 它在四家的行为完全一致,不依赖任何会随版本漂移的常数。
3. **Stop hook 只是遗漏兜底。** 只做短而确定的检查,每宿主回合最多一次 block,**永不宣布完成**,永不在 allow 路径发模型可读文字。
4. **事件日志是来源标注,不是证明。** append-only;每条带**观测者**(hook / run)与 artifact 摘要。不加哈希链、不加 MAC、不声称抗篡改(§2 R2)。session 绑定保留,但理由是归属护栏。
5. **不增加文件。** `<slug>.goal.md`(契约 + 当前状态 + carry-over)、`<slug>.decisions.md`、`<slug>.events.jsonl`、`.goals/active`。没有 research 文件、没有 ledger、没有数据库、没有每回合提交。

### 5.2 相对 main 需要的改动(全部很小)

| 改动 | 修的缺陷 | 出处 |
|---|---|---|
| `## Anchor` 必须 fenced 单行或 `command:` 前缀,validator 拒绝歧义 | 我的 D9(抽错命令 → 永远 unknown → 闸门零效力) | 我第 1 轮读码 |
| 重入守卫保留,但**必须写一条事件**(main 现在完全静默) | 我的 D1 的后半(`--audit` 看不见被跳过的回合) | 我第 1 轮实测 |
| allow 路径一律不带 `additionalContext`;按宿主选输出形状 | 我的 D2/D3、zCode 的 Z3 | 文档 926/2553、serde 复现、zCode 二进制 |
| block 的 `reason` 带闸门自己的回合号 | 我的 D8(两个互不可见的计数器) | 我第 1 轮读码 |
| 首条事件记录 ceiling 基线;后续变化 → `ceiling_changed` + 放行 | zCode 的 D4 | zCode 实验 D |
| `active` 已存在且指向同一 slug 时要求显式 re-baseline(旧 `events.jsonl` 归档) | zCode 的 D5 僵死 | zCode 实验 B |
| Claude Code 上读 `background_tasks` / `session_crons`,非空则记 `deferred` 并放行 | 我的 D6(假红/假绿) | `hooks.md:2478` |
| 树摘要降为 advisory 事件,不再直接决定放行 | zCode 的 D7 后半 + 我的 D6 | 双方一致 |
| 注册 `StopFailure`(Claude Code)只记事件 | 我的 D7(API 错误对闸门不可见) | `hooks.md` StopFailure 段 |
| SKILL.md 削到运行时真正需要的部分,设计论证移入 `references/` | 我的 D11(常驻上下文成本) | `SKILL.md:773` |

**不做的事(逐条撤回或拒绝)**:不新增 research 文件(§2 R6);不做哈希链/MAC(§2 R2);不做 `goal_complete` + disarm(§4.2);不做 review mtime 新鲜度判据(§4.1);不用 `asyncRewake` 当续航基础(§2 R3 第 4 点);不要求每回合 git commit(challenge case 24,当前 owner 授权的是研究,不是提交)。

---

## 6. 精确的 allow / block / complete 语义

**前提:allow、continue、complete 是三种不同的输出形状与三种不同的事件,不能合并进一个 `_allow` 里 —— 那是 main 的 D2 的根源。**

### 6.1 判定顺序(自上而下,首个命中即返回)

| 序 | 条件 | 判定 | 事件 | 理由 |
|---|---|---|---|---|
| 0 | 无 `.goals/active` / 环境变量禁用 / 事件名不符 / artifact 缺失 / cwd 或 session 归属不符 | **静默 allow** | 不写 | 未参与项目零成本;归属不符时**禁用执法而不是回退到无关 cwd**(codex 第 1 轮事实 2) |
| 1 | `background_tasks` 或 `session_crons` 非空(仅 Claude Code 有此字段) | **静默 allow** | `deferred` | 半成品工作树上的测量不是事实,只是更有说服力的错误 |
| 2 | 本回合已续跑过(Claude/zCode 的 `stop_hook_active`,Kimi 恒为 false 故按"已用"处理) | **allow** | `already_continued` | 每宿主回合最多一次修正,四家统一。main 的守卫方向对,只是不写事件 |
| 3 | `## Anchor` 无法抽出唯一命令 / 可执行文件不存在 | **allow** | `anchor_unavailable` | 三态设计保留;**unknown 永不 block** |
| 4 | 冻结摘要 ≠ 基线 | **allow** | `frozen_spec_changed` | 保留 main 的行为,`reason` 里指向 re-baseline 仪式(修 zCode D5) |
| 5 | 基线 ceiling 已达 | **allow** | `ceiling_reached` | ceiling 数的是**闸门检查次数**,文档必须说清它 ≠ 自主迭代次数(§2 R4) |
| 5b | 当前 ceiling ≠ 基线 ceiling | **allow** | `ceiling_changed` | owner 的量,机器只报告(采纳 zCode 3.2-3) |
| 6 | **本回合没有观测到针对当前 artifact 摘要的验证记录,或观测到的退出码 ≠ 0** | **block(每回合仅一次)** | `anchor_checked` | **这是唯一的硬拒绝。** 它是一条遗漏/失败检测:机器事实是"我没有在这个回合看到那条命令成功" |
| 7 | 退出码 = 0 且 `## Acceptance` 仍有 `[ ]` | **allow** | `acceptance_open` | **不 block、不发劝告文字。** 在 zCode/Kimi 上那段文字到不了模型(§2 R5);义务的归属是 artifact 与原生 goal 条件,那两处才真的会被读 |
| 8 | 退出码 = 0 且 acceptance 全 `[x]` | **allow** | `completion_claimed` | 并列记录 run 的主张与闸门的测量。**不写 `goal_complete`、不 disarm、不删 marker**(§4.2) |

**闸门没有 complete 裁决。** 它只有 `completion_claimed`。完成的判定权在:owner、或宿主的判定器(Claude 评估器 / zCode verifier)、或宿主给模型的工具(Codex `update_goal` / Kimi 标记 complete)。Ultra 的贡献是让这三者的判断可以和一条测量并排放。

### 6.2 逐宿主输出形状(订正我第 1 轮 §4.4)

```
claude : block  -> {"decision":"block","reason":R}
         allow  -> exit 0 无输出;仅当内容确实是给「用户」看的告警时 {"systemMessage":M}
         禁止   -> allow 路径上的 hookSpecificOutput.additionalContext(会静默续跑并消耗 8 次上限)

codex  : block  -> {"decision":"block","reason":R}
         allow  -> exit 0 无输出
         禁止   -> 任何 hookSpecificOutput(StopCommandOutputWire 带 deny_unknown_fields;
                   我第 1 轮的 serde 复现:解析返回 None -> HookRunStatus::Failed
                   -> 每回合一条 "hook returned invalid stop hook JSON output")

kimi   : block  -> {"hookSpecificOutput":{"hookEventName":"Stop",
                    "permissionDecision":"deny","permissionDecisionReason":R}}
         allow  -> exit 0 无输出

zcode  : block  -> {"decision":"block","reason":R}   # R 必须非空:OUr 要求 additionalContexts 非空,
                                                     # e6r 会把 reason 推进 additionalContexts
         allow  -> exit 0 无输出                     # systemMessage 在 allow 分支不被读(Z2)
```

**跨四家唯一成立的规则:allow 就是安静地 allow。** 想让模型做什么,只有两条真通道 —— block 的 `reason`(那一步本来就要继续),或 artifact / 原生 goal 条件(下一回合会被读)。

---

## 7. 剩余的高危反例

### C-1(最高严重度)——原生完成压过红色证据

- **zCode:已证实机制,后果未实跑观测。** `target.completion_verification.failed_open` → `AZ` → `passed:true`。如果 verifier 请求恰在锚点为红的那个回合出错,zCode 判 target 完成;Ultra **没有任何组件能阻止**(allow 不暂停外层 target;zCode 未向模型暴露 target 操作)。Ultra 诚实的输出上限就是日志里那句"宿主报告完成,闸门在摘要 X 上测到 exit 1"。
- **Claude Code:【未证实】,且这是我认为最该先花钱验证的一条。** 闸门的 command Stop hook 与 goal 的 prompt Stop hook 在同一次 Stop 聚合里。**同一次聚合中,评估器给出 `met` 的裁决能否与闸门的 `decision:"block"` 并存,以及谁赢,我读 minified 代码不敢断言。** 失效方向比 zCode 安全(timeout→cancelled、error→error,都不是 met),但"安全的失效方向"不等于"红证据一定压过 met 裁决"。

**判定方法(这是真实宿主生命周期验证,不是发射端测试)**:每家宿主跑一次真实运行 —— 锚点恒红、goal 条件为模型口头声称即可满足的形式、模型被引导声称完成。数三样东西并排:闸门 `events.jsonl` 里的 `anchor_checked` 条数与 outcome、宿主的完成遥测(Claude 的 `tengu_goal_achieved` / `goal_status met:true`;zCode 的 `target.completion_verification` 日志)、以及转录里评估器实际读到的消息。**若任一宿主在锚点恒红时判 met,则"闸门 + 原生 goal 组合"的价值就退化为事后记账,我第 1 轮 §5 的方案 B(闸门完全不阻断,只记录+注入)才是最小可行架构。**

### C-2 —— `asyncRewake` 没有找到上限

如果有人(包括第 3 轮)想用 `asyncRewake` 当续航基础:一个恒定 exit 2 的 Stop hook 是否会无限唤醒模型,**【未证实】**。我在 2.1.260 里只找到 `asyncRewake / rewakeMessage / rewakeSummary / flushPendingAsyncRewakeHooks` 四个符号,**没有 cap 常量**;而 8 次上限那条明确是给同步 Stop 阻断的。**找不到常量不是没有上限的证明。** 判定方法:配一个恒 exit 2 的 asyncRewake Stop hook,在空闲会话里数唤醒次数;或在二进制里定位 rewake 的计数路径。**在此之前不要建立在它上面** —— 这也是我不把它放进 §5 的原因,尽管我在 §2 R3 里为它撤回了"hook 不能创造回合"。

### C-3 —— 闸门文字对评估器的可见时序

即使采纳 §5,如果有人把承重证据放回闸门的 `reason` / `additionalContext`,C-3 就复活:评估器拿的是 `[...e.messages, ...s]` 快照,而 hook 的注入点是"the point where the hook fired"。同一次 Stop 内的先后【未证实】。**§5 原则 2 之所以把验证放进普通工具调用,就是为了让这个不确定性不再承重。** 判定方法:同一次实跑里检查转录,看 hook feedback 是否出现在评估器收到的消息里。

### C-4 —— 挑战案例里我的设计仍然只能给"不满意但真实"的答案

- **case 15/16(worker 还在跑时协调者结束回合)**:Claude Code 有 `background_tasks` 可以延后测量(§6.1 第 1 行);**其余三家没有这个字段**,所以在那三家上,"worker 结果如何被收集"没有 hook 层答案。**这个限制必须明写,不能用一个 pause 字段假装解决**(codex 第 4 条)。
- **case 13(用户中断/要求暂停)**:Claude Code 文档明说 Stop *"Does not run if the stoppage occurred due to a user interrupt"*;Kimi 用 `Interrupt` 取代 Stop 并把目标转为 `paused`。所以**用户意图靠宿主自己的路径胜出,闸门不参与**,也不该用正则去解读任意文本当授权。代价是 `--audit` 的时间轴在被中断的回合上有洞 —— 这是真实缺口,不是可以补的。
- **case 18(压实/崩溃)**:zCode 0.16.5 没有 PreCompact 事件、SessionStart 只有 startup/resume(zCode Z4,我第 1 轮也独立读到事件枚举只有 7 个)。所以"压实恢复"在 zCode 上只能靠 SessionStart 的两种 source,而**历史 active marker 不是新授权**。

---

## 8. 我挑战了哪条 peer 命题,以及什么证据改变了推荐

| peer 命题 | 我的裁决 | 改变推荐的证据 |
|---|---|---|
| zCode 3.2-2:green 前置 block,判据含 review 文件 mtime 新鲜度 | **拒绝(降级为仅对缺失的一次遗漏 block)** | mtime 度量的量 ≠ 被判断的量;释放条件使"写文件"成为最便宜的合规动作;判据落在 zCode 自己称为非持久的 `.work/` 上 |
| zCode 3.2-5(c):gate 写 `goal_complete` 并 disarm | **拒绝整条** | `[x]` 是 run 写的断言;Claude Code 二进制原文证明技能**不能清除**原生 goal,disarm 必然去同步 |
| zCode 3.2-5(b):session_id 使跨会话伪造可检出 | **前提被否证** | `~/.claude/projects/<slug>/<uuid>.jsonl` 目录可枚举、文件名即 sessionId、最新即当前会话(我直接观测) |
| zCode D1:"没有任何机制创造下一回合","unattended 只有 Codex 也许成立" | **过强** | Claude Code 的 `asyncRewake`(exit 2 空闲唤醒);Kimi 的 `kimi -p "/goal …"` 退出码 0/3/6 |
| zCode 3.2-1:组合路线,原生 goal mode 当回合驱动 | **方向同意,但缺一条关键事实** | zCode 原生 verifier `failed_open` 判过;而 Ultra 在 zCode 上无 target 操作可用,无法阻止 |
| codex 第 2 条:改用回合内普通工具验证 | **同意并采纳为核心** | `/goal` = Stop prompt hook;评估器输入是 `[...e.messages]`;`systemMessage` 只给用户(926) |
| 我自己第 1 轮 §4.2 的组合机制 | **撤回** | 同上 |

---

## 9. 证据等级与我明确不知道的事

**已证实(文档原文 / 活体二进制 / 源码 / 直接观测,可复核)**
`systemMessage` 只给用户(hooks.md:926);`additionalContext` 进会话且 Stop 上会续跑(972、2542、2553);`/goal` 是 session 级 prompt Stop hook(Stop 段 Tip);`background_tasks`/`session_crons` 的用途(2478);`asyncRewake` 的存在与语义(459、3690 + 二进制 schema 自述);`ProposeGoal` 可创建、不可清除、agent context 不可用(二进制字符串);Codex 三个 goal 工具及 `update_goal` 明文禁止 pause/resume(spec.rs);Kimi 的四状态、错误→paused、TUI-only 管理命令、prompt 模式退出码(官方 docs);zCode `failed_open`(活体二进制,厂商自命名);zCode Stop 注入仅在续跑分支(4 个调用点 + 三元表达式上下文);会话 UUID 即转录文件名(直接观测)。

**读码推断(minified,标注为推断)**
Claude Code goal 循环里 `evaluator_timeout → cancelled`、`evaluator_error → error` 的映射;`blockingError` 使回合继续。我给出了符号与片段,但没有跑通控制流。

**明确未知**
C-1 的三家实跑结果;C-2 的 `asyncRewake` 上限;C-3 的同 Stop 内注入与评估器快照的先后;zCode/Kimi 是否存在我没找到的模型可调用 goal 操作(我搜的是工具名清单与斜杠命令注册,**不是穷尽搜索**)。

关于 Kimi 的一条精确未决:定长检索确认 `kimi` 二进制里存在 `update_goal`(17 次)、`goal_control`(18 次)、`goal_objective`(18 次)以及 `init_create_goal` / `init_update_goal` / `init_get_goal` / `init_set_goal_budget` 等符号,**但我三次尝试提取它们的上下文都撞上工具限制**(两次 120s 超时、一次 ugrep 复杂度上限),因此**无法判定它们是对模型暴露的工具名,还是内部 RPC/事件名**。所以 §3.2 表中 Kimi 那一行的依据**只有官方文档**(agent 自行标记 `complete`、管理命令为 TUI-only),不含这些符号。若 Kimi 实际也暴露 `update_goal` 这类工具,它与 Codex 同属"agent 自报完成"那一类,§3.2 的分类结论不变,但"模型可创建"一列的机制描述需要修正。判定方法:在 Kimi 会话里列一次可用工具,或对该二进制做分块提取。

**我没有做的事**:任何宿主上的一次真实 goal 运行。所以本报告里所有"谁赢""几次""是否到达"的问题,凡未标【已证实】者,都是待实跑判定的。**一条精确的未支持边界优于一个制造出来的确定性。**

---

*reviewer: claude · round 2 · 回应 codex 交叉质询,挑战 zCode 完成自动化,撤回本人 §4.2 组合机制与"不可伪造"表述*
