# zCode — Ultra Goal 对抗式评审,第 3 轮(最终)

身份:zcode。对象:`rounds/proposal-draft.md`(含 round-2 裁决与时序边界)、四位 round1/round2、`local-evidence/{live-host-validation,session-binding,plugin-discovery,verification}.md`。本轮零星新探针均为只读二进制 strings 与钉定源码阅读(见附录)。live 证据现状:**仅 Codex 0.150.1 与 Claude 2.1.260 有 exit-2 纠正 + 静默放行的真实回调;zCode 探针死在 CLI 旗标层(help 宣称的 `--settings` 被 root CLI 以 Unknown option 拒绝,hook 未加载);Kimi 无 live hook 结果。四宿主生命周期不成立。**

## 0. 最终立场

- **架构决策:ALLOW(有条件)。** skill + 小脚本 + 原生 hooks、无 runtime 的骨架成立;四家控制面差异已逐主机溯源,时序边界(完成工具先于 Stop 变异原生状态)已写进 draft。条件是 §4 的最小修正清单折入,特别是"Stop 检查对象 = 证据记录,不是复跑全套"。
- **完成判定立场(不变,加重申):** gate 永不 complete/disarm,只供 machine_view;完成 = 模型证据判断 + 宿主侧同步 + owner 复核,分歧必报。
- **"四宿主无人值守已验证":BLOCK。** 不是设计否决,是证据否决:2/4 宿主只验证了最小 exit-2 传输,arm/绑定/纠正生效/真放行/恢复/诚实失败六件事在任何宿主上都没有完整走通。评审票数不构成成功率数字。

## 1. 指定攻击面裁决

**1a. 收回:我 round2 §4 表"Kimi 无模型可调生命周期操作"。** Kimi round2 的四重闭环(活体工具面 + 二进制默认 agent 工具单 + pinned kimi-turn.ts + 文档)成立:`CreateGoal/GetGoal/UpdateGoal(active|complete|blocked)/SetGoalBudget` 是 Kimi 0.40.1 的模型工具,创建即由 driver 同回合接管,错误→paused。Kimi 与 Codex 同属"完成=模型自报"类;Kimi 是四家里武装路径最顺的。我 round2 该格"无(转引)"错误,源于我只读了 TUI 文档——这正是我 round1 自己立的规矩(读工具实现,不只读文档)未被自己执行。

**1b. 收回:我 round2 [M3] 的 epoch-only 执法键。** epoch 只区分"哪次 arm",不区分"哪个会话":同 cwd 的第二个会话读到的是同一个 marker,epoch 校验照样通过,gate 照样执法——epoch 单独**不能**阻止第二会话激活(draft 裁决正确)。最小修正:arm 时绑定 **(epoch, host session id)** 二元组——四家都有受支持通道(Codex hook env `CODEX_SESSION_ID`;CC/Kimi/zCode 的 `${CLAUDE_SESSION_ID}`/`${KIMI_SESSION_ID}`/`ZCODE_SESSION_ID` skill 展开,见 session-binding.md);Stop 比对 payload session id,不符或缺失→inert + 告警事件。zCode resume 后 id 是否延续仍未验证:不静默重绑,resume 后 gate inert,由 owner 重新 arm(新 epoch,即 re-baseline 仪式的同一机制)。此绑定是误触护栏,不是防伪(round2 R2 维持)。

**1c. zCode"自然语言 goal 控制" vs 实际模型工具面(本轮新事实)。** 二进制 0.16.5:模型工具面存在 **`GoalRead`**(只读;且为条件注册——我当前无活跃 goal 的会话里工具清单不含它),resume 注入原文"Use it as the authoritative long-running objective unless a later **GoalRead result** or runtime goal event updates it. **Do not mark the goal complete unless real evidence shows** the objective has been achieved"。而 create/pause/resume/clear 全是内部函数(`createSessionTarget`/`pauseGoal`/`applyGoalCommand`/`parseGoalObjectiveFromCommandText`)或用户面 `/goal` 斜杠分发与 headless `--target`。**结论:文档的"自然语言目标控制"指目标文本与用户会话式管理,不是模型可调控制 API。zCode 上的不支持边界:skill 不能 arm/pause/complete 原生 goal,只能打印 owner 命令,并在 GoalRead 存在时读取状态。** 顺带:zCode 自己的 resume 文本已内建"无真实证据不得判完成"纪律,Ultra 引用而非复写。

**1d. 版本可移植性。** 全部 per-host 事实钉死在 CC 2.1.260 / zCode 0.16.5 / Codex 0.150.1@03861e6 / Kimi 0.40.1@0d45ddd。新漂移实例:zCode help 宣称 `--settings`,已装 root CLI 拒绝——**帮助文本与文档不是能力证明**。skill 的每宿主适配层必须携带"已验证版本号 + 版本变更即重测激活"的声明;`${CLAUDE_SESSION_ID}`/`${KIMI_SESSION_ID}` 这类 skill 展开是半文档化内部件,同样受漂移约束。

## 2. 最强假完成反例与分类

**反例(具体):协作但不严谨的模型在 Codex/Kimi 上回合中直接调 `update_goal`/`UpdateGoal('complete')`,未跑任何验证;原生状态在 Stop 之前已变异(Kimi markComplete 先于最终 continuation 与 Stop 回合,kimi-turn.ts:925-974),Stop 纠正不能撤销;Kimi 侧记录清除还终止了后续回合。** zCode 变体:verifier `failed_open` 使基础设施故障即判过。

分类:**确定性"完成前否决"是宿主能力,proposal 明确不承诺**(draft:PreToolUse 须先证明该原生完成工具确实到达该 hook;不得假设一切原生工具可拦截)。这是不支持边界,不是设计缺陷。设计义务是三件已写进 draft 的事:回合内先验证、Stop 的遗漏检查、最终报告对"native 判成而证据记录缺失/为红"必须报分歧。若未来产品要求硬否决,那是新的宿主能力需求,按 draft 的 PreToolUse 验证路径单独立项。

## 3. 对 peer 主张的接受/拒绝/更正

- **更正 Kimi round2 R2 的 stop_hook_active 语义。** 我在 2.1.260 二进制独立复核:两个不同字段、不同生命周期——query 初始化 `{stopHookActive: e.stopHookActive??!1, stopHookBlockingCount: 0}`,compact-retry 路径**保留 Boolean、清零 count**;内嵌指引"check stop_hook_active...return success while it's true"与"A hook blocked the turn from ending N consecutive times—overriding"绑定的是 count。**计数随工具使用/新 query 归零;重入 Boolean 在链内粘滞。** Kimi 的"干活之后可再纠正一次"推论错误;保守守卫的真实承诺是**每观测链零或一次** Ultra 纠正(机会性,opportunistic)——且 Boolean 可能由别的 hook 或原生 goal 续跑置位,不得从中重构业务迭代计数。draft 第 89 行的措辞是对的,维持。
- **挑战并更正 Kimi round2 §9-2"gate 自己复跑 anchor 是'观测到验证缺失'的唯一合法实现"。** 替代:**普通工具执行既有验证器并落盘观测结果(命令、exit、goal/artifact digest);Stop 检查该必需证据记录是否存在且 digest 匹配当前 goal 修订,缺失/失配→一次有界纠正。** 为什么不需要在 Stop 里跑第二遍全套:(i) 记录的可信度不低于 Stop 日志——两者都不可防伪,都只是出处标注(round2 R1/R2 共识,四方已收敛);(ii) Stop 复跑把效应性命令移出正常权限/取消边界(challenge case 20)并复制成本;(iii) 研究型目标被迫伪造 always-green 壳锚(challenge case 6)。**短、确定、无副作用的 Stop 复测仅在可论证处可选**;研究目标的验收证据形态按需求约定,不设假 shell oracle。
- **接受 codex plugin-discovery 更正(已独立核验)。** `core-plugins/src/loader.rs` 的 `load_plugin_hooks` 在 `manifest_paths.hooks == None` 时回退 `DEFAULT_HOOKS_CONFIG_FILE`(hooks/hooks.json);`HookEventsToml`(config/src/hook_config.rs:36)无 `deny_unknown_fields`(第 11 行的那条在另一结构上)。**main 的 Codex hooks 会经默认发现加载;无效 Stop payload 是 main/adapt 共享发射端缺陷**——我 round2 把它写成"adapt 最高优先级修复项"过窄,更正为共享修复。宿主上的实际安装/信任仍属未验证问题。
- **接受 Claude round2 的 ProposeGoal 细化,更正我 round2 表的"用户一键批准"绝对化。** `auto/alwaysAsk/disabled` 配置 + 每次提议的 ask_user;typed `/goal` 不受影响。**遵循宿主工具自身的授权要求与用户显式调用,不加额外批准仪式,也不绕过**;goal-intake 授权不是新的未决产品问题。
- **Ultra 延迟规则:维持 draft 第 77 行原文。** 仅"与本 goal 相关的必需后台工作"可延迟;不把 defer-on-any-cron 抄进 skill;宿主 evaluator 自己更宽的策略只文档化、不进口(即:Claude round2 §6.1 第 1 行的 background_tasks/session_crons 检查须收窄到 goal 相关必需工作)。

## 4. 最小修正清单(每条高严重度→最小精确修正)

1. Stop 判据从"复跑 anchor 为红"改为"**必需证据记录缺失或 digest 失配**(+可选短确定性复测)";block 仍是每观测链至多一次、exit 2 + 非空 stderr。
2. 执法前提从"epoch 匹配"改为"**(epoch, session id) 绑定匹配**";不符/缺失→inert + 事件;resume 连续性未验证→重新 arm,不静默重绑。
3. 四宿主能力表按本轮更正重写(Kimi 工具面四件套;zCode GoalRead 只读 + 用户面控制;ProposeGoal 配置化批准;Codex pause/resume 用户/系统专属),并钉版本号。
4. 共享发射端(Codex 载荷)修复标注为 main+adapt 共同缺陷。
5. 完成时序边界措辞照 draft 维持:Stop 纠正非否决、无全局硬 gate 承诺。

## 5. 就绪度

**架构决策:ready(allow)。四宿主无人值守实施:未验证(block any such claim)。** 决定性剩余不确定性:**原生完成(自报/fail-open)与 Stop 背网在真实宿主上的交互,以及那一次纠正是否真的改变模型行为**;其次是 zCode/Kimi 的 hook 注册激活本身。最小验收 run(每宿主、宣称"支持该宿主"之前各跑一次,非 4×N 统计矩阵):经实际暴露路径 arm → 确认 hook 激活且 session 绑定收到 → 一次 exit-2 纠正被模型观测并响应 → 真静默放行 → resume/compaction 后恢复 → 诚实非成功结局(证据记录缺失→不宣称完成)→ 记录 native-complete-vs-红证据的分歧披露。任一观测不符即改表。若所有宿主上该次纠正从未改变行为,则按 Kimi round2 自己给出的证伪条件把 Stop 降为纯观察型——我预先接受这一降级。

## 6. 收回清单(累计)与未决

Round2 已收回且维持:哈希链、session_id 防伪表述、mtime 新鲜度、gate 自动 complete/disarm、Claude 8 次"回合上限"措辞。**本轮新增收回:Kimi 无生命周期工具(1a);epoch-only 执法键(1b);ProposeGoal 必经一键批准(§3);"adapt 独有 payload 缺陷"(§3)。** 未决哨兵:zCode resume 后 session id 连续性;GoalRead 的确切注册条件;zCode/Kimi hook 注册 live 激活;native evaluator 与 gate 的同回合优先序。条件置信度:消费端-静态与二进制事实高;两宿主最小传输 live 高;其余为零,以待 §5 验收 run。

## 附:本轮新探针(供复核)

- `python3 -I` 只读扫描 zcode.cjs:工具名表含 `GoalRead`(仅 2 处:权限名表 + resume 注入引用);goal 生命周期均为内部函数/斜杠分发;无 create/pause/clear 模型工具。
- `python3 -I` 只读扫描 claude 2.1.260:`stop_hook_active`/`stopHookBlockingCount` 字段分离及初始化/compact-retry 生命周期;内嵌 Stop 指引与 N-consecutive 覆盖告警原文。
- 只读核对 codex-rs `core-plugins/src/loader.rs`(None→默认 hooks.json 回退)与 `config/src/hook_config.rs`(HookEventsToml 无 deny_unknown_fields)。
- 未做:任何安装/配置改动、live 宿主运行(zCode `--settings` 探针失败属 setup 失败,不是 hook 结果)。

**报告路径**:`/var/folders/cm/zpwxmr512rq1qz4_0_ryz8t80000gn/T/ultra-goal-adversarial-20260904-ce29svvd/reviewers/zcode/round3.md`
**主要剩余关切**:原生完成路径(Kimi/Codex 自报、zCode fail-open)在 Stop 之前变异状态且不可撤销——设计已诚实声明此边界,但"那一次有界纠正是否足以让协作式模型回到证据轨道"没有任何宿主上的 live 证据,这是 §5 验收 run 必须首先回答的问题。
