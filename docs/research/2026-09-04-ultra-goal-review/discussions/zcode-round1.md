# zCode — Ultra Goal 对抗式设计评审,第 1 轮(独立)

评审对象:`sources/main`(HEAD b07e2a8,v2.8.0,已发布插件)与 `sources/adapt`(HEAD f15a003,v2.9.0 候选,**未发布**;其行为一律标注为候选)。评审日期 2026-09-04。身份:zcode。

证据分级约定:【事实-代码】读自快照源码;【事实-二进制】读自本机已安装 host 二进制(zCode 0.16.5、Claude Code 2.1.260、Kimi 0.40.1 未直接执行但引用了两位评审的 strings 证据);【事实-文档】读自官方 reference;【实验】我在自己目录里的隔离探针(脚本副本,快照未动);【推断】/【判断】为设计判断,明确标出。

---

## 0. 总判断(TL;DR)

1. **Stop 拦截只能"延长回合",不能"创造回合"。** 这个设计把 host 自带的 goal mode 贬为"便利品",用 Stop hook 当 loop 本体——但 Stop hook 在 4 台 host 里的 3 台(Claude 8 次、zCode 3 次、Kimi 每回合 1 次)受连续阻断上限约束,预算耗尽后 turn 结束,**没有任何机制发起下一个 turn**。"owner 离开后持续运行"这一产品核心承诺,在当前架构下只有 Codex(上限未证实为无)可能成立。这是全设计最大的单点错误,main 与 adapt 共有。
2. **完成(acceptance)判定没有任何机械前置。** anchor 绿 → gate 无条件放行,只附带一条劝告性消息;而这条消息在 zCode 与 Kimi 上**根本到不了模型**(zCode 为二进制证实,Kimi 为官方文档证实)。虚假完成(false completion)在这个设计里不是被 gate 挡住的,是被 prose 挡住的。
3. **证据链可伪造、且最强的证据最不持久。** `events.jsonl` 可被 run 追加伪造(git 只防"提交后篡改",不防"伪造后提交");reviewer/critic 的报告写在被 gitignore 的 `.goals/.work/` 里,压实了就消失;gate 从不写"完成"事件——整个设计里认识论最强的时刻(宣布完成)不留任何机器证据。
4. **ceiling 可被 run 静默上调**(实验证实):`## Stop condition` 不在冻结摘要里,gate 每次都重读当前值。唯一的硬资源边界是 Firm 层、run 可编辑、无告警。
5. **owner 合法 Modify 冻结节之后 run 永久死亡**(实验证实):`frozen_digest` 基线取自第一次检查且永不重置,`.goals/active` 仍在、每次 Stop 都 `frozen_spec_changed` 放行,文档没有给出任何 re-baseline 仪式。
6. main 的 stagnation 规则使"loop"退化为 nudge(实验证实:确定性红 anchor 只 block 一次);adapt 用 work-tree 摘要修复了它,方向正确,但摘要度量的是"动了"而非"有进展",而"动"对 run 极其便宜。

---

## 1. 我独立验证的 host 事实(这是我作为 zCode 评审员的独特贡献)

前两位评审(Codex、Claude Code)的机器上没有 zCode,所有 zCode 结论都是二手的。我在 zCode 0.16.5 本体上直接验证了以下事实,来源 `/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs`(minified,以下引用符号名为准):

| # | 事实 | 级别 | 证据 |
|---|---|---|---|
| Z1 | zCode Stop 连续续跑上限恰为 3:`function OUr(e,t){return e.stopShouldContinue===!0&&e.additionalContexts.length>0&&t<Dui}`,`Dui=3`。续跑要求 **additionalContexts 非空** | 事实-二进制 | 反汇编符号 `OUr`/`Dui`;与官方文档 "After 3 consecutive continuations the run is force-ended to prevent infinite loops"(https://zcode.z.ai/en/docs/hooks)一致 |
| Z2 | Stop 输出解析(`function e6r`):顶层 `decision:"block"` 会把 `reason` **和** `systemMessage` 推进 additionalContexts 并置 `stopShouldContinue=true`;`hookSpecificOutput.additionalContext` 也被收集(符号 `Jei`)。**`systemMessage` 只在 block 分支被读,allow 时被完全忽略** | 事实-二进制 | `e6r`/`Jei` |
| Z3 | **Stop 的 additionalContext 只在续跑分支注入**:`injectHookAdditionalContextIntoMessageHistory(on.Stop, ...)` 的唯一调用点在 `shouldContinueAfterStopHooks(...)` 为真的分支里。allow 时(green/unknown/ceiling/stagnation)additionalContexts 被丢弃 | 事实-二进制 | 调用点搜索:SessionStart(startup/resume)、UserPromptSubmit、Stop-续跑,共 4 处;Stop-allow 无 |
| Z4 | **zCode 0.16.5 没有 PreCompact 事件;SessionStart 只以 `startup` 和 `resume` 两种 source 触发**(文档写 "common values are startup / clear / compact",与二进制互相矛盾——且二进制有 `resume` 而文档没写) | 事实-二进制 | `runSessionStartHooks("resume")` / `("startup")` 仅两处;`PreCompact` 全文 0 命中 |
| Z5 | `ZCODE_PLUGIN_ROOT` 与 `CLAUDE_PLUGIN_ROOT`(兼容)都会注入 plugin hook 子进程环境;插件 `hooks/hooks.json` 自动发现存在(符号 `listPluginHookSources`,`QAo=join("hooks","hooks.json")`) | 事实-二进制 | env 组装代码;`QAo` |
| Z6 | Stop hook 的 stdin 含 `sessionId` 与 `stopHookActive:stopHookContinuationCount>0`——即 zCode 的 `stop_hook_active` 语义 = "本次 Stop 是否为续跑"(与 Codex 文档语义同形) | 事实-二进制 | `runStopHooks`(符号 `PUr`)入参组装 |
| Z7 | zCode 原生 `/goal` 的续跑由一个**独立模型调用**判定:`GoalVerification:"goal_completion_verification"`,产出 `Reason:`/`Next action:`,再注入 "Continue working toward the active session goal." + `<untrusted_objective>` | 事实-二进制 | actorKind/System 调用表与 prompt 模板 |
| Z8 | UserPromptSubmit 的 additionalContext **会**在模型调用前注入(有独立调用点)——zCode 可以承载 Kimi 式的"下一回合恢复通道" | 事实-二进制 | `injectHookAdditionalContextIntoMessageHistory(on.UserPromptSubmit, ...)` |

其余 host 的事实,我核对了官方文档(Claude/Kimi/Codex 的 hooks reference)与 Claude 2.1.260 二进制的关键字符串(`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`、"A hook blocked the turn from ending N consecutive times — overriding and ending turn"、`stop_hook_active` 仅在超限后作为事后建议打印),与前两位评审的引用一致,不再重复列表。

**Z3 是本轮最重要的新事实**:它意味着 main 的 SKILL.md 第 655-657 行的主张——"Every turn that ends carries `additionalContext` naming `### Next`, `### Lessons`, `### State` …"——**在 zCode 上为假**。zCode 解析了这段 context,但只有 block(续跑)时才注入;allow 时丢弃。Claude 评审在 Kimi 上从 reference 发现了同类问题(F-1),但机制不同:Kimi 是协议上没有 allow 通道,zCode 是**解析了但不投递**。也就是说:main 在 zCode 上,gate 的全部 allow 话语(green 还有几行 acceptance、unknown 别猜、ceiling 到了、stagnation 了、以及每回合的 obligation 提醒)对模型一概不可见,对用户的 `systemMessage` 也不被读(Z2)。adapt 的 SKILL.md 没有纠正这一点,只在 Kimi 行写了 degradation。

---

## 2. 最强缺陷(按认识论危害排序)

### D1【判断,基于 Z1/Z7/文档事实】Stop 是回合延长器,不是 loop:"walk away" 在 3/4 host 上不成立

逐 host 的机械上限(连续阻断/每 host 回合):Claude 8(adapt 预算 7)、zCode 3(预算 2)、Kimi 1、Codex 未证实(adapt 取 None)。预算耗尽后 gate 自己放行 turn(adapt 的 `continuation_budget_spent`,诚实地"park")——**然后呢?** park 消息写着 "continue on the next prompt",但 unattended 的定义就是没有下一个 prompt。四位评审材料里没有任何机制创造下一回合:host goal mode 被明确降级(SKILL.md:377-388 "The gate is the loop, so a host's goal mode is no longer needed"),`/loop`、`/schedule` 只在 host 表格里被点名从未接线,cron 不存在。

产品语义因此分裂成两种,而文档没有区分:
- **短目标**(一个 host 回合内 anchor 能绿):Stop gate 足够,且是好的。
- **长目标**(多回合,`## Cadence` + `ceiling: 40` 存在的理由):Stop gate 只能把 40 次检查摊到 ~5 个 Claude 回合 / ~13 个 zCode 回合 / 40 个 Kimi 回合上,每个回合之间需要 owner 递 prompt。adapt 自己承认("On Kimi every turn parks after one block, so long unattended runs there are effectively attended")但没有把这句话推回产品层:**`## Cadence` 承诺的"多次自动启动"没有任何 host 机制兑现**。

讽刺的是,被降级的 host goal mode 恰好是 turn 创造器:Z7 证明 zCode 的 `/goal` 每回合注入 goal-continuation system-reminder(还带 completion verifier);Claude 的 `/goal`、Kimi 的 `/goal pause/resume/cancel` 同类。SKILL.md:381-383 说 goal mode "duplicates four of this Skill's own mechanisms, and cannot do the one that matters: write `.goals/active`"——这个论证是反的:写 `.goals/active` 是一行 `printf`(goal-run.md:36),而"创造下一回合"是 Stop hook **永远做不到**的那一件事。两个机制是互补而非重复:goal mode/loop 造回合,gate 在每个回合内执法、并把 ceiling 跨回合持久化在事件日志里(这已实现)。

**对应 owner 问题 "Is Stop interception actually enough?" 的回答:不够。** 它足够做三件事——红 anchor 时让回合继续(预算内)、每回合收集测量、会话边界重注入。它不足以做一件对产品定义生死攸关的事:发起下一个回合。

### D2【事实-代码 + 实验 E + Z3/Kimi 文档】完成路径没有机械前置;green = 无条件放行

`goal_stop.py`(main 508-529;adapt 同形)green 分支:`return _allow(...)`,附带消息说明还有几行 acceptance 开着、提醒"这是否等于完成要问 `## Stop condition`"。没有第二个硬条件:
- acceptance 行的 `[x]` 是纯断言,没有任何机制把某一行 join 到某次 anchor 证据上(`--audit` 只在 turn 粒度 join commit claim vs gate 测量);
- review/critic 是否跑过、是否比最后一次代码改动新,gate 不看、事件日志不记(PostToolUseFailure 只记失败,不记成功;`.work/` 文件在 `.goals/.gitignore` 里,见 D3);
- **gate 从不写"完成"事件**。事件类型里有 `anchor_checked`/`ceiling_reached`/`frozen_spec_changed`/`continuation_budget_spent`/`anchor_unavailable`/`pre_compact`/`role_unavailable`,没有 `completion_proposed` 或 `goal_complete`。认识论最关键的时刻不留痕迹。

再乘上 Z3 与 Kimi 文档("Only blockable events (PreToolUse, Stop, UserPromptSubmit)…All other events are observation-only",https://moonshotai.github.io/kimi-code/en/customization/hooks):**在 zCode 和 Kimi 上,green 时那段"还有 2 行 acceptance 开着,这不是完成"的警告根本不会到达模型。** 一个 run 在 zCode 上 anchor 变绿、20 行 acceptance 全开、没有任何 review,turn 平静地结束,没有任何机器痕迹表明"本该继续"。设计反复强调"a green anchor is not a pass"(review/SKILL.md:57),但把这句话变成机制的组件一个都没有。

实验 E(隔离探针):green + 2 行 open acceptance + 无 review → `decision` 缺省(allow),payload 仅 `systemMessage` + `hookSpecificOutput.additionalContext`。结论属实。

### D3【事实-代码】证据的可伪造性与易逝性:零信任叙事的三处漏洞

设计的原则(run 写主张,hook 写证据,`--audit` 对照)是对的,但三处实现削弱了它:

1. **`events.jsonl` 可由 run 伪造后提交。** "written by the hooks and never by the run"(SKILL.md:455)只是意愿;run 对该文件有写权限,事件无 MAC、无哈希链、无会话归属。git 只让"提交后篡改"可见,"伪造后提交"与真实 gate 写入不可区分(实验 C:我向日志追加了一条 turn 99 的伪造 green 事件,`--audit` 全绿通过)。SKILL.md:721-723 自己承认"tampering 是可见而非不可能",但没说**伪造(而非篡改)完全不可见**。
2. **review/critic 证据被 gitignore。** goal-run.md:37 写 `.goals/.gitignore` 含 `.work/`;review/critic SKILL.md 的产物都在 `.goals/.work/`。整个体系里最强的证据(对抗式审查的裁决)压实后即失,session 结束后无人能审计"验证到底有没有发生、结论是什么"。
3. **`.goals/active` 由 run 可写。** 解除是 owner 的(`rm .goals/active`),但 arm 同样一行 printf——一个想续命的 run 可以自己 re-arm、自己写 marker。配合 D4 的 ceiling 上调,一个对抗性 run 可以合法地无限延长自己的生命周期,且每个环节都有"文档依据"。

### D4【实验 D 证实】ceiling:owner 的硬边界,却是 run 的软旋钮

`FROZEN_SECTIONS = ("intent", "boundary", "anchor")`(goal_hooks.py:32)。`## Stop condition` 不在其中,gate 每次 Stop 都从**当前**文本重读 ceiling(goal_stop.py ` _ceiling`,main 83-105)。实验 D:ceiling=6 触顶后,把 `or after 6 turns` 改成 `or after 60 turns`(Firm 层,规则上只要求 decisions.md 一行——而那也是 run 可写的),gate 立刻继续检查 turn 7,无任何事件、无 `--audit` 发现。三层冻结表(SKILL.md:130-138)把 "stop condition 的阈值" 排在 Firm、把机制守护全部押在 Frozen 摘要上,结果:**goalpost 不可动,天花板可动**。对一个"防 run 漂移"的设计,资源边界的可动性比目标漂移更危险——目标漂移骗的是结论,天花板漂移烧的是 owner 的钱(尤其在 Codex 分支 budget=None 时,ceiling 是唯一的总量边界)。

同类不一致:SKILL.md 的 tier 表把 "`## Means`'s labels" 列为 Frozen("mechanically observed"),但 `FROZEN_SECTIONS` 不含 means——means 标签的冻结纯靠自觉。文档与代码二选一要改。

### D5【实验 B 证实】冻结基线无重置:owner 合法 Modify → run 永久死亡

`frozen_digest` 基线 = 第一条 `anchor_checked` 事件的 `spec_digest`(goal_stop.py:376)。实验 B:第一次检查后 owner 通过 Modify 流程改了 `## Boundary` 一行,此后**每次 Stop 都 `frozen_spec_changed` 放行**,事件日志里连记 3 条,`.goals/active` 仍指向该 artifact——SessionStart 继续注入 spec、Stop 继续拒绝执法,run 处于"活着但永远不工作"的僵死态。文档的出路只有"重跑 interview = 新 loop",但同一 slug 下的 artifact 就是改后的那份,基线还是旧的;唯一恢复手段是手删 `events.jsonl`,而这一点**没有任何文档记载**。admit 的 Modify 流程(SKILL.md:533-557)对冻结节的修改是"stop and report; reopens the interview"——闭环了,但 interview 产物如何回到一个可运行的 loop,断了。

### D6【事实-代码 + 判断】anchor 的认识论上限:单一命令、同一地形、540 秒

- **green 证明的只是"一条命令在 run 可写的地形上以 0 退出"。** anchor 通常测试 run 刚写的代码;`.venv`、测试文件、甚至被测行为本身都在 run 的写权限内。reviewer 被设计为补救("an assertion weakened to get green",review/SKILL.md:60),但 reviewer 在**同一个工作树**上自己跑 anchor(review/SKILL.md:24 "run the anchor command yourself")——被污染的地形对 gate 和 reviewer 是同一份。没有 clean-room(如 fresh clone + 重放)环节。
- **570 秒墙与"anchor 必须跨全路径"自相矛盾。** SKILL.md 反模式表要求 anchor "drive the running thing — build plus start plus one real interaction",而 `ANCHOR_BUDGET_CEILING = 570`(goal_hooks.py:52)之上永远 `unknown` → gate 永不执法。validator 自己也承认:"An anchor that genuinely needs longer should be split, or run outside the gate and its result reported"——"reported" 即自报,恰是 gate 存在要消灭的东西。慢 E2E 产品的硬 gate 在架构上会退化成装饰。
- **单 anchor = 单比特。** partial success 的粒度(哪一行 acceptance 被什么证据 settle)在 `--audit` 里不存在(join 键是 turn)。`## Acceptance` 让部分成功**可读**,但没有让它**可审计**——实验上,run 一口气把所有行勾成 `[x]` 再 commit,`--audit` 不会产生任何 finding(claims=green, measured=green)。

### D7【实验 A 证实(main);adapt 修复了方向,但换进了一个新启发式】

- main:`stop_hook_active` 硬退出(goal_hooks.py:141-143)使每 host 回合最多一次 block;**即使去掉这个 guard**,signature 相同即放行的 stagnation 规则(goal_stop.py:531-540)让确定性红 anchor 只被 block 一次。实验 A:4 次 Stop,第 1 次 block,第 2-4 次全放行。main 的"loop"是一个 nudge,两个机制各自独立保证这一点。
- adapt:删 guard、按 host 预算续跑、tree digest 只在"输出与工作树都没动"时放行。我的探针证实它确实修好了 Codex-F3 的两个半边:(a) 自变异 anchor(`printf x >> src.txt; exit 1`)在无模型工作时不被误判为进展(第 2 次检查即 stagnant 放行);(b) untracked 文件的内容改动(≤1MiB)被计入摘要,不再漏判。**但**摘要是"动了没有",不是"有没有进展":run 重排一次格式、touch 一个 tracked 文件、跑一次 commit(HEAD 变化计入摘要)都算"动"。对抗性 run 想避免 stagnation 放行,刷"动"的成本趋近于零;诚实的 run 在 `.goals/` 内做全部产出(摘要排除 `.goals`)会被误放。这个启发式现在承担着"红 anchor 下唯一的非 ceiling 出口",重要性远超其证据强度。启发式本身没问题,问题是它**有执法权**(直接决定放行)——按设计自己的 §1.8 原则("mechanise only when the measured quantity IS the judged quantity"),它更应该是 advisory(记录、提醒、由 ceiling 兜底),而不是裁决者。

### D8【事实-代码/二进制】主张与 host 现实的系统性错位(acceptance 层面)

- SKILL.md:655-657 "Every turn that ends carries `additionalContext`…" — zCode 假(Z3)、Kimi 假(文档)、Codex 存疑(其 reference 对 Stop 只文档化 `continue`/`stopReason`/`systemMessage`,`additionalContext` 只写在 SessionStart/UserPromptSubmit 名下)。四台里可能只有 Claude Code 全兑现。
- SKILL.md:377-388 "goal mode 不再需要" — 见 D1,论证方向反了。
- main 的 hooks.json 把 PreCompact 注册给所有自动发现 host — zCode 无此事件(Z4),是死注册;SessionStart matcher 含 `compact|fork`,zCode 二进制从不以这两种 source 触发(Z4)——注入只发生在 startup/resume。adapt 把 PreCompact 挪进 claude.json 是对的,但其 SKILL.md 里"zCode 的 compaction recovery rides `SessionStart`'s compact source"这句在二进制层面**为假**(0.16.5 没有 compact source;文档与二进制互相矛盾,按设计自己的"reference 优先"原则也该标注冲突)。
- main 的 `_allow` 只发 `systemMessage`(+optional additionalContext):zCode 二进制 accept `systemMessage` 进 schema 但 allow 分支不读(Z2);Kimi reference 无此字段。Claude 评审的 F-1(Kimi)我予确认,zCode 是新的同构案例。

### 其他值得记录的小缺陷

- **commit convention 是纯社会约定**:`--audit` 的 claims 来自 `git log --grep`;run 不 commit 就没有 claim,审计无从对照(没有任何机制要求每 turn 一个 commit)。
- **`--run-anchors` 以 `shell=True` 执行 artifact 内命令**,已有 consent 门挡(SKILL.md:528-531),可接受,但 anchor 在 hook 进程环境里跑(继承 host env)值得一句明示。
- main 的 `goal_hooks.run_hook` 对 `stop_hook_active` 的硬退出与 adapt 的按预算续跑相比,后者才符合 "gate is the loop" 的自我叙事;但 adapt 在 Kimi 上 budget=1 使每回合只续一次,`_block_streak` 的跨回合泄漏已被 `prompt_submitted` 边界事件修复(读代码确认),Codex-F2 的批评在最终候选里已解。
- Codex-F4 的 `none` 分支与 re-arm 覆盖基线问题,adapt 已修(review/SKILL.md 的显式分支 + goal-run.md:53 的 write-once `[ -s … ] ||`),我读码确认。
- Codex-F1 的 `$1` → `$ARGUMENTS`:adapt 的 goal-run.md:53 已用 `$ARGUMENTS`,方向正确;但整份文件其余 `$1` 引用是否全部换净我没有逐行数——留作第 2 轮核对项。

---

## 3. 最小可行架构(我的建议)

### 3.1 保留(这些是对的,而且是"小"的)

`<slug>.goal.md` + `<slug>.decisions.md` + `## Carry-over` 三件套、三层冻结、`## Challenges from the run` 单通道、validator 的"只查机械事实"、SessionStart 有限注入、"hook inlines only what it alone possesses"原则、不建 runtime/ledger/graph sequencer 的边界。这套核心小于 3 个文件 + 4 个 hook,是正确的小。

### 3.2 修(按性价比排序,每条都小)

1. **补 turn 创造者,不要与 host goal mode 为敌。** 两个层次任选:(a) 诚实路线——把产品语义改成"每个 owner prompt 触发一次有执法的工作爆发"(attended burst),文档明说 `## Cadence` 的"自动多次启动"仅 Codex 或许支持;(b) 组合路线——unattended 时显式用 host 的 goal mode / `/loop` / cron 作为回合驱动,gate 保持证据层。Z7 表明 zCode 原生 goal mode 每回合注入续跑提示且有独立 verifier;让 Stop gate 与之共存(gate 只在 anchor 红时 block,goal mode 负责下一回合)比替代它便宜得多。SKILL.md "goal mode duplicates four mechanisms" 一段应重写。
2. **给 green 加一次机械前置 block(本轮最重要的新 gate)。** 第一次出现 "green 且有 open acceptance 或 `.goals/.work/<slug>-review.md` 缺失/早于最后一次代码改动" 时,block **一次**,指令为跑 `/ultra-goal:review` + `:critic`;其后放行。判据全部是机械事实(事件日志 + 文件 mtime)。这一步把 advisory 三元组变成完成时刻的 precondition,直接封 D2 的主通道。逃逸:review fork 不可用 → `PostToolUseFailure` 已有记录,block 降级为 loud allow(`review_unavailable` 事件),不产生死锁。
3. **ceiling/budget 基线化。** 第一次 `anchor_checked` 时把解析出的 ceiling(及 `## Stop condition` 全文摘要)记进事件;后续变化 → `ceiling_changed` 事件 + 放行报警(与 frozen 同形)。owner 想加量走显式 re-arm 仪式(见 4)。一行常量、一个事件字段的事。
4. **re-baseline 仪式。** `goal-run.md` 在 `active` 已存在且指向同一 slug 时要求显式 `--resume-after-modify`(或删旧 `events.jsonl` 归档为 `.events.<n>.jsonl`),把"owner 授权的冻结节修改"变成有痕迹的新 epoch。解 D5 的僵死。
5. **事件日志完整性 + 完成事件。** (a) 每条事件带 `prev` 哈希(链);(b) hook 把 host 传入的 `session_id`(zCode Z6 有、Claude 文档有)写进事件——模型上下文里看不到它,跨会话伪造变得可检出;(c) 增加事件类型 `completion_proposed` / `goal_complete`(green + acceptance 全 `[x]` + review 新鲜,由 gate 写入并 disarm)。约 30 行。
6. **review 证据入库。** `.goals/.gitignore` 保留 `active` 但放行 `.work/`(或至少 review/critique 两类文件);"最强的证据最不持久"与零信任叙事直接冲突。
7. **acceptance 行与证据 join(可选但便宜)。** 约定行格式 `- [x] A works — turn 12`,`--audit` 校验该 turn 的 `anchor_checked` 事件存在且 green。20 行代码,把 partial success 从"可读"升级为"可审计"。
8. **means 标签进 `FROZEN_SECTIONS`** 或改文档,消除 D4 尾部的不一致。
9. **zCode 注册 UserPromptSubmit 指针行**(Z8 证明可注入):一行 artifact 指针 + 最近一次 gate 裁决,同 Kimi 的 `goal_prompt_submit.py`。这是 zCode 上 allow-mute(Z3)的最便宜补救。

### 3.3 不要建

同意设计的克制清单:不建 anchor-skip 缓存(无复现失败)、不注册 PostToolUse、不建 goal_host 转换 shim、不建 runtime。再加两条我方的:不要把 tree digest 升级成更多启发式(方向应是降权为 advisory);不要用 UserPromptSubmit 做错误激活拦截(指令级修复优先,与 SKILL.md 现有立场一致)。

---

## 4. Stop 应该何时 allow / block / continue / complete(决策表)

前提状态:active marker 存在、artifact 存在、`ULTRA_GOAL_HOOKS_DISABLED` 未设。

| 情形 | 决策 | 理由与动作 |
|---|---|---|
| 无 active / 无 artifact / host 重入已超自身预算 | **allow,静默/常规** | 现行为,保留 |
| anchor 不可解析/不可执行/超时 | **allow + loud**(`anchor_unavailable`/`unknown`) | 三值原则,保留;但 zCode/Kimi 需通过 UserPromptSubmit 通道补投(3.2-9) |
| 冻结摘要变化 | **allow + loud + 指向 re-baseline 仪式** | 现行为对;缺的是第 4 条的出口 |
| ceiling 触顶(按**基线** ceiling) | **allow + loud + park** | 现行为对;基线化后,篡改 ceiling 会先触发 `ceiling_changed` |
| ceiling 变化(新) | **allow + loud(`ceiling_changed`)** | owner 的量,机器只报告 |
| 红 + 无进展(输出与树均未动) | **allow + loud + park** | 保留,但标注为启发式;连击阈值可议(≥2 对) |
| 红 + 有进展 + 预算内 + 未触顶 | **block**(附 reason + obligation) | 现行为,核心价值,保留 |
| 红 + 有进展 + host 预算耗尽 | **allow + loud + park** | adapt 现行为,保留 |
| **绿 + 有 open acceptance 或 review 缺失/过期(且本 run 尚未为此 block 过)** | **block 一次,指令跑 review/critic** | 新增(3.2-2)——本设计目前唯一缺失的硬 gate |
| 绿 + acceptance 全闭 + review 新鲜 | **allow + 写 `goal_complete` 事件 + disarm** | 新增:完成留痕并终止 |
| 绿(其余情形) | **allow + loud** | 现行为 |

"continue" 语义(模型继续工作)只发生在 block 分支;complete 是 allow 的特例但必须有事件与 disarm——**现在的设计里完成与放弃在事件日志里不可区分**,这是 acceptance 语义上的实质缺口。

---

## 5. 工作分工与持久化更新如何保持灵活而不变成第二 runtime

- 三层冻结的**思想**是对的;错位在执行面的三处(D4 ceiling、means 标签、D5 re-baseline)。修完后,"Frozen=机器看,Firm=一行记录,Fluid=随便"才真正成立。
- 灵活性的真正来源是 `### Next` 单目标 + Lessons ≤3 + Challenges 单通道,这套已经足够小;不要加 ledger/index/state machine(同意现有边界)。
- 持久化更新的排序应当是:**事件日志(机器)> git 历史(commit + 审查文件)> artifact 可变节 > 会话内 prose**。现状把 review 证据放在最底层(会话外即失),第 6 条修复把它提到 git 层。
- gate 的职责上限应冻结为五件事:跑 anchor、比摘要、数检查、写事件、block/allow。stagnation 这类判断性启发式降为 advisory 事件(D7),防止 gate 自己长成小 runtime——这是"不变成第二 runtime"对**自身代码**的同一要求,现在只对产物提了。

---

## 6. 主机事实与限制汇总(带来源与置信)

| Host | Stop 能做什么 | 不能做什么 | 来源 | 置信 |
|---|---|---|---|---|
| Claude Code 2.1.260 | block 续跑(计数 per turn);allow 的 `additionalContext`/`systemMessage` 文档化;SessionStart 五种 source;PreCompact/PostToolUseFailure 存在 | 连续 block 上限 8(`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`),超限 host 强制结束;不创造下一回合 | 二进制 strings + https://code.claude.com/docs/en/hooks | 高(两位评审 + 我复核二进制字符串) |
| zCode 0.16.5 | block + reason 续跑(≤3,需 additionalContexts 非空——reason 即满足);UserPromptSubmit 可注入;插件 hooks.json 自动发现;`ZCODE_PLUGIN_ROOT` 存在 | **allow 时 additionalContext 丢弃、systemMessage 不读(Z2/Z3)**;无 PreCompact;SessionStart 仅 startup/resume;不创造下一回合 | 二进制(本文 Z1-Z8)+ https://zcode.z.ai/en/docs/hooks | 高(二进制直接验证;未做 live 插件安装) |
| Kimi 0.40.1 | 仅 PreToolUse/Stop/UserPromptSubmit 影响流;Stop deny 走 `hookSpecificOutput.permissionDecision`;每 host 回合至多一次阻断 Stop;UserPromptSubmit 返回文本入 context | Stop 无 allow 通道(reference);SessionStart observation-only;`$1` 不展开(命令 loader 只换 `$ARGUMENTS`);不创造下一回合 | https://moonshotai.github.io/kimi-code/en/customization/hooks + 两位评审的二进制 strings(我未重复 strings) | 高(reference)/中(二进制细节,转引) |
| Codex 0.150.1 | Stop `decision:block`+reason → 续跑并自动生成 continuation prompt;`stop_hook_active` 文档化("Whether this turn was already continued by Stop");manifest hooks 字段**替换** hooks.json;SessionStart 支持 compact source | 无 PostToolUseFailure;Stop 是否接受 `additionalContext` 文档未写;**无文档化连续上限,"None" 未证实**;不创造下一回合(除非无上限为真) | https://learn.chatgpt.com/docs/hooks | 高(reference)/低(无上限之否定命题) |

---

## 7. 置信度与未证实的主张

**已证实(可复现)**:D2 green 无条件放行(代码+实验);D4 ceiling 上调无告警(实验);D5 冻结基线死锁(实验);D7 main nudge(实验)、adapt stagnation 两半修复(实验);Z1-Z8(zCode 二进制);main 在 zCode 的 PreCompact 死注册与 allow-mute(Z3/Z4)。

**高置信但转引**:Kimi 二进制细节(stopHookContinuationUsed、$ARGUMENTS loader)——来自 codex-round-1/claude-round-1 的 strings,与官方 reference 一致,我未重复提取;Claude manifest hooks 附加语义——claude 评审引用了 2.1.260 schema 文本("in addition to those in hooks/hooks.json"),与我读到的 loader 描述一致但未独立复核控制流。

**未证实/待一轮 live 验证**:Codex 无连续上限(否定命题,只能 live 证伪);zCode 真实插件加载与 `${ZCODE_PLUGIN_ROOT:+--host zcode}` 在 zCode hook 执行路径里的展开(变量存在 Z5 已证,shell 展开链路未走);Claude manifest-additive 未被安装实验证明;Kimi 预算=1 的 live 行为;**任何 host 上都没有跑过一次真实的 unattended 多回合 goal run**(两位评审与 adapt 的 §8.1 都承认)——这是整个评审共同体目前最大的共同空白。

**我的设计判断(非事实)**:D1 的产品语义结论、3.2 的优先级、stagnation 降权、review 入库的权衡(git 噪音 vs 证据持久)。这些都应被下一轮反驳而不是接受。

---

## 8. 会证伪我方案的具体对抗案例

1. **证伪 Z3("zCode allow-mute")**:在 zCode 上 live 安装插件,构造 allow 路径(绿 anchor),若模型转述/响应了 obligation 内容(而非仅靠 goal 文本),则我的"丢弃"结论错,3.2-9 失去必要性。观测点:转写里出现 hook_context 附件。
2. **证伪 D1(组合路线不可行)**:任一 host 上同时启用原生 goal mode 与 Stop gate,若出现双重阻断死锁、重复 prompt 或 verifier 与 gate 裁决冲突且无仲裁通道,则"组合优于替代"错,应回到纯 gate + park 语义。
3. **证伪 3.2-2(green 前置 block)**:一个 review fork 持续不可用且 `PostToolUseFailure` 不触发(例如 fork 静默返回空)的场景,会使"block 一次"退化为无限 block 或每次 green 都 block——需要实测 fork 失败的实际事件形态;若两者都不可观测,该 gate 必须降级为 loud allow。
4. **证伪 3.2-3(ceiling 基线化)**:若 owner 确实频繁合法调 ceiling(如探索型 goal),基线化会造成大量误报警告事件,收益低于噪音——用 adapt 的真实 40-turn run 的事件密度估一下即可。
5. **证伪 D6 的 clean-room 缺失主张**:构造一个被测方污染 anchor 的案例(如 `.venv` 里 shim pytest),若 reviewer(同地形)稳定捕获,则"gate+reviewer 同地形"批评过重;我的预判是捕获率低,这是可实验的。
6. **证伪事件链+session_id(3.2-5)**:若各 host 的 hook stdin 实际不传 session 标识(Kimi 未知),该修复在那些 host 上退化为纯哈希链,只防手改不防伪造。

---

## 9. 与既有评审材料的关系(独立后的交叉对照)

我是在完成全部探针后才读 codex-round-1 与 claude-round-1 的;以下为交叉结论,不构成共识声明:
- 确认:Codex-F2 的跨回合预算泄漏在最终候选(`prompt_submitted` 边界 + `fresh_chain`)已解;Codex-F4、F1 的 `$ARGUMENTS` 部分已解;Claude-F-1(Kimi allow-mute)属实,zCode 是未报告的同构案例且机制不同。
- 补充:两位评审都没有 zCode 二进制;Z1-Z8(尤其 Z3 的"解析但不投递"、Z4 的 SessionStart source 矛盾、Z7 的原生 goal verifier)为本轮新增事实。
- 不同意:Claude 评审对"reference 优先"的教训总结我支持,但要补一句——zCode 的 case 里 reference 与二进制**互相矛盾**(文档写 compact source,二进制只有 startup/resume),此时两条都必须报告为冲突而不是择一;设计的"reference 优先"原则需要一条冲突条款。
- main 与 adapt 的总体关系:adapt 的方向(per-host 预算、树摘要、基线 diff、`$ARGUMENTS`)我基本支持且已独立验证关键修复;但 adapt 没有触碰 D1-D6 中任何一个认识论层缺陷——它们是两代实现共享的架构问题。

---

## 附:本轮执行的命令(供复核)

- zCode 二进制:`strings -a /Applications/ZCode.app/Contents/Resources/glm/zcode.cjs` + python 正则抽取 `OUr`/`e6r`/`Jei`/`PUr`/`Dui`/`runSessionStartHooks`/`ZCODE_PLUGIN_ROOT`/`GoalVerification` 等符号上下文。
- Claude 二进制:`strings -a ~/.local/share/claude/versions/2.1.260 | grep CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` 等。
- 文档:https://zcode.z.ai/en/docs/hooks 、https://code.claude.com/docs/en/hooks 、https://moonshotai.github.io/kimi-code/en/customization/hooks 、https://learn.chatgpt.com/docs/hooks 。
- 隔离探针(快照只读,脚本复制到 `reviewers/zcode/probe/`):main 的连续 Stop(stagnation)、green+open acceptance、ceiling 上调、冻结节修改死锁、伪造事件;adapt 的自变异 anchor、untracked 内容、zcode 预算续跑。

**报告路径**:`/var/folders/cm/zpwxmr512rq1qz4_0_ryz8t80000gn/T/ultra-goal-adversarial-20260904-ce29svvd/reviewers/zcode/round1.md`
