# Ultra Goal 对抗性评审 · 第 3 轮(终轮)· reviewer: kimi

主攻角度:用户侧灵活性、Init/Research 退出条件、运行时任务选择/委托、压缩恢复。输入:proposal-draft、challenge-cases、live-host-validation、session-binding、plugin-discovery、三家 round2、codex-round1 与 cross-examination、我的 round1/round2。本轮未做新探针;结论全部复用已检源码与既有探针。

---

## 0. 最终立场(先行)

- **架构决策:有条件通过(allow)。** proposal-draft 经两轮裁决补丁后是可辩护的最小最强形态:skill 拥有决策、宿主拥有执行;不建 runtime/dispatcher/数据库/哈希链信任宣称/固定多代理仪式/自动 commit/通用 hook 能力。所附条件(§2/§4)全部是措辞与范围修正,不是结构改动。
- **四宿主无人值守实现:未验证(block 该宣称)。** live 证据仅有 Codex/Claude 的 exit-2 纠正 + 静默放行。Kimi/zCode 的 hook 消费仍只有源码/探针级证据;zCode 的 `--settings` 探针在加载任何 hook 前即被根 CLI 拒绝(exit 1、零回调,`local-evidence/host-probes/clean-zcode/result.json`)——这是失败的 setup 探针,不是 live hook 结果。原生 goal 评估器与 gate 的优先级在四家均未实测。不从评审票数的巧合制造任何成功率数字。
- **completion(可否进入实现):可以。** 实现期的验收门 = §6 的最小 live 矩阵;通过前,文档只能写"已在 2/4 宿主实测 Stop 传输"。

## 1. 主攻角度:反例搜索结果

**在候选自己陈述的承诺范围内,我构造不出击倒性反例。** 承诺是"有纪律、可恢复的工作循环",并明示排除"跨任意宿主中断的无条件无人值守"。两个最硬的案例落在承诺边界上、且 proposal 已自行划界——它们击倒的是对候选的强读法,不是候选本身:

1. **完成工具的时序边界。** Kimi 的 `UpdateGoal('complete')` 在最终消息与外部 Stop 回调**之前**即生效(update-goal.ts;kimi-turn.ts:925-974),Codex 的 `update_goal` 同为工具侧效果。这在结构上必然:Stop 运行于回合的全部工具调用之后。**事后的 Stop 纠正不能当作对已完成状态迁移的否决。** 因此任何"gate 是全局硬门"的表述被禁止;PreToolUse 普遍执法不予推荐——原生完成工具是否到达 PreToolUse 在四宿主均未证实,未证前不得假设可拦截,更不得为此建语义策略分类器。
2. **纠正额度可被他人花掉。** `stop_hook_active` 可由另一个 hook 或原生 goal 续跑置位(Claude 上 /goal 评估器本身就是 Stop prompt hook)。保守守卫的实际承诺是**每次观察到的链上零或一次机会性纠正**,不是每个业务迭代保证一次;不得从这个布尔重建任何回合计数。

**灵活性对账(指定任务)。** owner 任务书已指定"运行时选任务、灵活委托"。我 round1 的强制九问访谈、设计时钉死角色、禁动态账本,round2 已撤回其强制形态;本轮确认最终调和:保留内核 = goal.md/decisions.md 产物对 + 带 re-baseline 仪式的意图冻结摘要 + ceiling 基线化;放弃形态 = 固定问题数、固定角色、禁宿主计划工具、每回合 commit。proposal 前半段(只问后果重大的不确定项、最小目标契约、授权内直接澄清并记录)与 owner 指定产品一致。Init/Research 的退出条件是模型判断(证据足以支撑下一个已授权动作及其验证,或精确识别出一个主人决策点)——这是设计选择而非缺陷;反"研究空转"的机械绊线不存在,由主人中断与宿主预算兜底,proposal 对此如实声明。运行时任务选择/委托走宿主原生能力(subagent/agent-delegate/TodoList),Ultra 不建分派设施——我 round2 §6 的三条攻击该路线全部存活,本轮维持。

## 2. 我的撤回(新增,编号续 round2 的 R1–R5)

- **R6 —— 撤回 round1 "main 不给 Codex 注册 hooks"的归因。** 仅 manifest 缺 `hooks` 字段不支撑该结论:Codex loader 在 `manifest.hooks` 缺席时默认加载 `hooks/hooks.json`(core-plugins/src/loader.rs:1178-1232;loader_tests.rs:638-662 有默认发现测试),main 含该标准文件;discovery.rs:264-266 注入 PLUGIN_ROOT/CLAUDE_PLUGIN_ROOT;HookEventsToml 忽略未知事件字段。Stop 载荷不兼容(`deny_unknown_fields` 拒 `hookSpecificOutput`)是 **main/adapt 共享发射端代码**的缺陷,main 在真实宿主上的安装/信任是另一个未验证问题。P1-b 改定性为"共享缺陷,候选继承"。
- **R7 —— 更正 round2 R2 "Claude 上 stop_hook_active 在工具调用后归零"。** 混淆了布尔与计数器:随工具调用归零的是 `stopHookBlockingCount`(无进展计数);`stop_hook_active` 重入布尔在链内 sticky。统一规则(为 false 才 block)在 Claude/zCode/Codex 上的真实语义是**每链至多一次纠正**,不是"干活之后可再纠正一次"。规则本身保留(零日志反推、零每宿主常数),效果描述按 §1-2 改为机会性。
- **R8 —— 撤回 round2 §9/§11 "Stop 复测 anchor 是默认且唯一的非模型测量"。** 挑战成立:回合内普通工具执行验证 + 保存带 digest 身份的证据记录 + Stop 检查该必需记录缺失/陈旧并请求纠正,与 Stop 重跑在证据强度上等价——记录可伪造,Stop 日志同样可伪造,协作地形下二者都不防伪。Stop 内重跑的残余价值只有一处:检查短、确定性、无副作用,且需要在回合末尾(全部编辑落定后)重测以抓同回合的验证后回归。**默认 = 回合内工具验证;Stop 内复测 = 逐目标可选,且须先论证"为何需要在 Stop 里再跑一遍"。** 研究型目标不得配恒绿的假 shell anchor:验收证据是引用与评审,gate 只做身份/遗漏检查。
- **R9 —— 撤回 round2 §11 "skill 自助武装 vs 主人明示是待决产品问题"。** 这不是新的开放问题:遵循宿主工具自身的授权要求与用户的显式调用。Claude `ProposeGoal` 有 auto/alwaysAsk/disabled 三档(默认 auto 让模型按 `ask_user` 自选是否请求批准;手输 `/goal` 不受影响);Kimi `CreateGoal` 与 Codex `create_goal` 的契约文本各自约束创建条件。不得断言每次创建都需主人再点一次,也不得绕过原生批准。

## 3. 对 peer 主张的裁决

**接受**:Codex 的 exit-2+stderr 共享传输(live 已证于 Codex/Claude;两条边界必须写进契约:空 stderr 在 Codex 不阻断;意外错误永不以 exit 2 漏出);Claude R1/R2 与 zCode R1–R4 的同向撤回;zCode 的 D4/D5 补丁;"验证主通道 = 回合内普通工具"的四方收敛(R8 将其固定为默认)。**维持拒绝**:任何形式的 gate 机械完成/自动 disarm;把 deferral 写成"存在任意 cron/后台任务即挂起"——只对**与本目标相关的必需后台工作**推迟,原生评估器若有更宽规则是宿主自己的事,不抄进 skill。**维持我的主张**:gate 永不宣布完成;allow 静默;session 绑定是归属护栏而非防伪;Kimi 恢复指针住进目标文本(§5)。

## 4. 剩余高严重度问题与最小修正

1. **C-1(最高):原生完成压过红色证据。** zCode verifier `failed_open`;Codex/Kimi 模型自报先生效(§1-1);Claude 评估器与 command hook 同次 Stop 的次序未证实。最小修正三条,均为顺序与措辞而非新机制:(a) 硬顺序规则——任何完成调用之前,先用普通工具实跑适用验证并把原始输出留在 transcript;(b) 最终报告在原生判完成而 gate 证据为红/缺失时**必须显式报分歧**(challenge case 23);(c) 不推荐 PreToolUse 执法,直至逐宿主证实原生完成工具到达该 hook。
2. **机会性纠正的文档措辞。** 写死:每观察链零或一次;额度可能被其它 hook/原生续跑先消耗;禁止从 `stop_hook_active` 重建回合或业务迭代计数。
3. **Kimi skill-only 模式无恢复通道。** SessionStart 观察型、PreCompact 被忽略、UserPromptSubmit 仅 user 起源——不武装原生 goal 时,无人值守恢复没有任何通道。逐宿主表须明示"Kimi skill-only = 仅 attended"。
4. **zCode/Kimi 证据等级。** 实现期文档对这两家只能写"源码/探针级";zCode 连一条 hook 注册的 live 证据都还没有(§0)。

## 5. 恢复建议对 UserPromptSubmit origin 发现的检验(指定)

**建议成立,且是 Kimi 上唯一可行形态。** kimi-turn.ts:761 的 `origin.kind !== "user"` 早退(Codex 已接受该发现)使 goal-continuation 回合没有任何 hook 注入通道;而 `injectGoal` 在每个续跑回合重注入目标提醒(turn.ts:814-817)。把规范 goal-state 路径与重读义务写进原生目标文本,指针随提醒穿透压缩。两条明示边界:mid-turn 压缩 ≠ 新 prompt——注入在**下一个续跑回合**到达,不是压缩后立即(proposal 已写明);goal 因错误转 `paused` 后再恢复,同样只有提醒文本可用,Kimi 的 SessionStart resume 是观察型。zCode 文档虽列出 compact 的 SessionStart source,但已检安装调用点只见 startup/resume,不得在 live 结果前承诺压缩注入。

## 6. 就绪性、决定性残余不确定、最小验收跑

架构就绪性见 §0;四宿主无人值守**未验证**。决定性残余不确定只有一个:**原生 goal 机制与 gate 在真实多回合运行中的交互**——续跑是否发生、唯一纠正是否到达、红证据下原生侧判什么、压缩后重读义务是否被恢复、预算耗尽形态。两轮以来这些断言全部只有静态/解析器证据,live 数为零。
**最小验收跑(每宿主一条,共四条)**:用该宿主实际暴露的路径武装原生 goal;目标="让 anchor 转绿",anchor 设计为两红后转绿;中途诱导一次未完成即声称完成;制造一次 mid-run 压缩;观测 (a) 自动续跑回合数,(b) Ultra Stop 每观察链至多一次纠正,(c) 红期间原生侧是否误判完成、最终报告是否报分歧,(d) 压缩后重读义务是否被提醒文本恢复,(e) 预算耗尽的宿主形态。Kimi 腿具体化:`CreateGoal` + `SetGoalBudget(5 turns)` + 恒红 anchor + 目标文本内嵌重读指针——同时结案"外部 Stop 是否在 goal 续跑回合触发"(turn.ts:925-974 的静态读法需 live 确认)。zCode 腿须先换一条受支持的注册路径(`--settings` 已证伪)。任一观测不符即回改 §4 表述;全过才可把"四宿主"写进文档。

## 7. 条件化信心

- **高**(多源静态一致 + 两家 live 传输):架构骨架、exit-2 传输、allow 静默、gate 不宣布完成、§2 各撤回。
- **中**(多源静态、零 live):逐宿主武装路径表、恢复拓扑、机会性纠正语义。
- **低/未证**:原生评估器与 gate 的交互;zCode/Kimi 全生命周期。若验收跑显示唯一纠正从不改变 run 行为,我改投纯观察型 Stop;若显示红证据下原生完成压过一切,则"分歧披露"就是 Ultra 在该宿主的全部诚实输出——候选仍成立,只是承诺更窄。

---

**报告路径**:`/var/folders/cm/zpwxmr512rq1qz4_0_ryz8t80000gn/T/ultra-goal-adversarial-20260904-ce29svvd/reviewers/kimi/round3.md`
**主要剩余关切**:原生完成工具的效果先于一切 Stop 纠正(Kimi 已定位到 update-goal.ts / kimi-turn.ts:925-974),且纠正额度可被其它续跑源消耗——gate 最多是机会性背网;设计已如实划界,剩余只能由 §6 的四条 live 验收跑裁决。

*reviewer: kimi · round 3 · 撤回 R6–R9,维持 R1–R5 修正后立场;架构有条件通过,四宿主无人值守未验证*
