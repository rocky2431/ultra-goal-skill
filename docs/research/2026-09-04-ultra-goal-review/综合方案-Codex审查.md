# 综合方案：Codex 最终对抗审查

2026-09-05。审查对象：`综合方案.md`；交叉材料：`方案与论证.md`、`evidence.json`。本文件只做审查，不修改实现。

> 🧠 **From Hindsight memory (Key decisions and rationale)** — 本项目既有的零自述信任边界是：run 写 claims，hook 写 measurements；完成判断应把二者关联，而不能让 run 自己写一行“证据”就获得机械可信度。该记忆仅用于定位审查问题，以下裁决仍以当前文档、源码和本轮实测为准。

## 当前已钉住的宿主事实

- 官方 OpenAI Hooks 文档对 Codex `Stop` 明确支持的续跑输出是顶层 `{"decision":"block","reason":"..."}`，另支持 exit 2 + stderr；它没有把 `hookSpecificOutput.permissionDecision` 列为 `Stop` 输出。因此，混合载荷不能从文档推导为有效，必须按本仓库的确切 `_deny` 形状实测。[OpenAI Docs: Stop](https://learn.chatgpt.com/docs/hooks#stop)
- `evidence.json` 中 `clean-codex-invalid-json` 只测到了不含 `additionalContext` 的相近混合载荷；它能证明该载荷没有纠正，不能代替精确 `_deny` 探针。

### 精确 `_deny` 探针：已确认失效，不再是“可能”

本轮在隔离临时目录对本机 `codex-cli 0.150.1` 做了配对探针。实验组逐字段复制候选 `goal_stop._deny(reason, context)` 的非空 context 形状：顶层 `decision:block`／`reason`，并带 `hookSpecificOutput.{hookEventName,permissionDecision:deny,permissionDecisionReason,additionalContext}`。结果是 **1 次 Stop 回调，最终只有 `PROBE_INITIAL`，没有续跑**。同目录、同版本、同一注册方式的正控只发顶层 `decision:block`／`reason`，结果是 **2 次 Stop 回调（第二次 `stop_hook_active:true`），模型输出 `PROBE_INITIAL` 后又输出 `PROBE_CORRECTED`**。

因此可以排除“hook 没加载”这个替代解释，并把结论收紧为：**候选的确切混合 `_deny` 载荷在 Codex 0.150.1 上使本应有效的顶层 block 一并失效。** `综合方案.md` 第 77 行的“可能”与第 242 行只要求 1.1／1.4 真探针都已过时；它应列为第五条阶段 0 合并阻断项，并以“删除 Codex 不支持的 nested Stop 字段”后的正控复验为门槛。

## 1. 是否诚实代表了《方案与论证》的发现

**大体诚实。** 第 0～2 节对以下结论的表述没有给我过度署名，也没有把限定删掉：主模型／脚本／hook／宿主的分工；CC allow + context 的续跑；解释器 fallback 吞 exit 2；启动前 exit 2 误阻塞；active 缺会话归属且 session ID 不是防伪密钥；CC 的 8 是“上次进展后的连续阻断”而不是业务轮次；相同签名不证明停滞；合法修约后要保留旧观察并建立新基线。

但有两处需要纠正，不然 owner 会以为是我主张的：

1. **我没有主张“每次业务迭代都跑完整 anchor”。** `方案与论证.md:82` 的原意是：验证发生在普通工作流里，按本次改动和验收项选择适用测试／真实路径；相关产物在验证后又变了，完成前才按影响复验。`综合方案.md:127` 把它升级为“每次业务迭代：运行 anchor”，只是把 Stop 的固定成本搬进业务循环，仍然过强。
2. **`clean-codex-invalid-json` 不是非法 JSON，也不能概括为“Codex 拒绝含 hookSpecificOutput 的 Stop 输出”。** 它是语法有效、但对 Codex `Stop` 不受支持的混合 schema。准确说法是：Codex 0.150.1 接受顶层 block；本轮又确认候选的 nested `permissionDecision` 混入后，整次续跑决定失效。`hookSpecificOutput` 在其他事件有合法用途，错误应钉在 event-specific schema，而不是字段名本身。

另一个不是“代表失真”而是综合时新增的弱化：我的“合法修改后 re-baseline”以**既有授权或 owner 新裁定**为前提；第 4 节后面的“留一条轨迹 + 裁定 ID 即可”没有保住这个权威边界，详见第 3 节。

## 2. 第 3 节：Anchor 分层

**裁决：方向可取，文字现状会开一个新的自述缺口；必须在两种互斥设计里明确选择“门亲自重跑”。**

第 128 行说“运行声明完成时，门跑一次”，第 134～135 行却说 run 把退出码与摘要写成事件，门再“比对这条证据”。这不是同一件事：

| 完成门实际做什么 | 是否有自述缺口 |
|---|---|
| 在完成候选的当前状态上**亲自执行当前 anchor**，只用本次 hook 写下的结果作机械裁决 | 没有新增的 stale-row 自述缺口；先前 run 的普通验证只负责反馈 |
| 接受 run 写下的 exit code／输出摘要，再用 hash 或工作树标识判断“对应” | 有；同一执行方同时作者化 claim 与所谓 evidence，匹配只能证明两段自述互相对应 |

应明确采用第一行，并删除“run 把结果写成 `events.jsonl` 证据供门验”的含义。普通工具输出可以留在 transcript 或任务自己的结果文件里；如果 run 自己写了摘要，它只能是 claim。最终门不读取历史 green 来放行，而是执行一次新的观察，所以“run 上次执行后到完成声明之间变了什么”不会让旧行通过——旧行根本不是 pass 输入。

最小可执行契约是：

1. run 发出一个**显式 completion candidate**。它可以是自述，因为只触发检查，不授予通过；不要靠自由文本猜“我是不是在声称完成”。普通 `Stop` 只表示想结束一个宿主 turn，不等于目标完成。
2. 门先核 session/run 归属、当前获授权的 spec baseline、当前 anchor identity；任一不匹配都不拿旧结果顶替。
3. 所有必要 worker 已 join、没有仍会改相关产物的写者后，门对当前状态执行当前 anchor **一次**。
4. hook 自己写 measurement，至少带 run/session identity、spec digest、anchor digest、相关产物或 post-anchor state identity、exit code 与 output digest。整树 hash 只是保守近似，不能让无关文件变化冒充相关性。
5. 本次检查后相关状态再变，completion candidate 失效；green 只证明这个 anchor 在这份状态上 exit 0，是否满足语义验收仍由模型／owner 按需求证据判断。

最省事也最可信的实现是：**门在同一次 Stop 调用里执行、裁决，再把结果落盘；落盘行只是审计记录，不是这次放行的输入。** 这样无需用 hash 假装获得防伪性。只有要在进程中断后复用历史 measurement 时，才需要额外证明该记录来自受信执行面且对应未变化状态；run 可写目录里的 JSONL、session ID、digest 都只提供关联，不提供这种权威性。

因此，“其他每次 Stop 只检查证据在不在”也要改：**只看存在不能阻塞或放行完成。** 非 completion Stop 最多做短的、确定性的遗漏提示；历史证据的存在、mtime、hash、勾选框都不是完成 oracle。

最后，把第 127 行改成“在相关变更后、需要反馈或准备完成时，run 用普通工具执行适用验证”。否则所谓分层仍把 540 秒 anchor 固定到每个业务迭代，只是换了调用位置。

## 3. 第 4 节：`impossible`

### 3.1 解冻方向对，但不能让“留痕”冒充授权

“冻结 owner 的条件，不冻结整份工作认识”是对的；“文件在物理上可编辑”却不等于 run 获得了修改目标、验收或权限的 authority。`综合方案.md:157-161` 目前只要求“一条轨迹 + 一个裁定 ID”就建立新基线，任何能写文件的 run 也能同时写这两样，于是可把未授权改约洗成新基线。ID 是关联信息，不是授权凭据，和 session ID 不是防伪密钥同理。

re-baseline 至少要记录变更 diff、旧／新 baseline、裁定来源，并先满足其中之一：owner 在当前受信通道明确批准；或旧约已经明确授权该类变更。agent 自己提出 challenge 可以，不能自己把 material goal change 裁成 owner change。这个边界必须先于新基线。

此外，“删除形状，代码不动”是事实错误。候选 `goal_stop.py:543-558` 永远拿第一条 `anchor_checked.spec_digest` 作基线；合法修改后它没有读取新 baseline 的路径。要让同一 run 继续，至少需要一个被 gate 消费的 re-baseline 记录或等价状态转移及回归测试。`综合方案.md:244` 同时写“代码不动”和“新基线机制有测试”，两者不能同时成立。

### 3.2 不要把 `impossible` 放进 anchor 的颜色轴

**red 不够表达永久不可达，但 `impossible` 也不应成为 green／red／unknown 的第四个同层 outcome。** 前三者是本次命令观察：通过、失败、无法测量；`impossible` 是对未来可达性的语义判断，属于 run disposition。一次 exit 1 既不能证明永久不可达，一次 timeout 也不能。

应保留两条正交轴：

| 轴 | 例子 |
|---|---|
| Anchor observation | `green` / `red` / `unknown` |
| Run disposition | `in_progress` / `input_required` / `blocked_retryable` / `budget_exhausted` / `unachievable` / `completed` / `canceled` |

缺凭据是 `input_required`，暂时服务故障是 `blocked_retryable`，会话或预算用尽是 `budget_exhausted`，当前 anchor exit 1 只是 `red`。只有目标在当前冻结约束／授权／环境下确实自相矛盾或永久失去实现路径，并经独立证据确认，才是 `unachievable`。主模型说“不可能”只能触发核查，不能成为证明。

这一区分作为报告词汇值得保留，且 `方案与论证.md:54` 已经要求把完成、需用户决定、暂时受阻、预算耗尽、运行错误分开；**现在没有证据要求再给 gate 加一个代码 outcome。** 只有当 `unachievable` 有真实消费者——例如停止后续重试、产生明确的未完成终态，而且该宿主确实能执行这个终止——才实现它。否则用现有 blocked/challenge + 证据即可；绝不能把它折成 red 后继续盲重试，也不能照搬 CC 的独立 evaluator 形状并声称四宿主共有。

## 4. 第 5 节：四个进化机制

**按第 8 节自己设的门槛——“每件对应一次复现过的失败”——当前是 4/4 都没有过门。** 这不等于四个想法都永远无用；第 4 项若第 1 项成为正式契约，就应作为同一特性的校验而不是另算一个卖点。但现有材料没有证明它们应成为每个 Ultra Goal 的默认形状。

### 4.1 `<slug>.trajectory.md`：引用的失败恰好证明“再加日志”不是修复

Protoss 的数字来自一个移动中的未钉版本快照：391 commits／354 个 `loop:` commits 对应 `17e8deb1e2f3b69f6fa8f7c53e88f927575ab9c9`，但该 revision 的 TRAJECTORY 是 6,663 行；文中 6,702 行出现在紧接着的 `9ee94611f0dd7d810049615ebf0b534ee7a92eec`，届时已是 392 commits。本轮读取 live repo 时又已到 459 commits。结论可以引用，但必须 pin revision；当前数字组合本身不是一个可重放的同一时点读数。

更关键的是，它引用的那条轨迹在原文下一段自己给出了反证：`TRAJECTORY.md:6306-6309` 说同一教训已经在 **TRAJECTORY 里出现六次**，但每轮真正重读的 `JUDGE.md` 中命中为 0，所以才把规则晋升进协议。那是“日志没有消费者／没有进入协议”的失败；**TRAJECTORY 已存在且没有防住它。** 拿这条失败来论证 Ultra 再加一份 trajectory，是把失败部件当成修复部件。

Ultra 的三条 Lessons 是 active working memory，不承担完整历史；历史已有 Git，material 取舍已有 decisions。尚未复现的是：某个 Ultra run 因这两处都找不到已知原因而重走死路，且补一条按 tick 追加的 trajectory 能防住它。先保留现有最小形状；真实长跑若仍重复遗忘，再增加**会被恢复流程实际读取的 material decision/evidence 记录**，而不是默认每 tick 写五字段日记。

### 4.2 裁定 ID／作者／覆盖：作者已有，删除前提不成立

`Who` 列早已区分 `owner|agent`；这不是新机制。当前 decisions 规则也要求变更时在同一行把旧值移进 `Rejected`，Git 保存 diff。稳定 ID 与 `supersedes` 在出现跨文件引用或多次覆盖难以辨认时会有价值，但当前材料没有复现这种歧义。

第 188 行的直接理由更是错的：`Delete anything no longer true` 位于 `goal-package.md` 的 `## Carry-over` 内，只约束 State/Lessons/Next；它不作用于独立的 `decisions.md`。decisions 有自己的保留／替换规则。不要为了修一个不存在的跨文件删除路径加编号体系。若以后确有跨引用，最小改动是给 material decision 一列稳定 ID + 可选 `supersedes`，不需要划线协议、双编号或 append-only 全史。

### 4.3 `## Retractions`：这轮已经用局部文档解决，没有默认产品失败

“六条撤回无处可记”在这份综合方案自身不成立：第 9 节就是完整撤回表，且每条带击败它的证据。尚无实例表明因为 Ultra goal 没有全局 Retractions 节，某个后续 run 重采了撤回主张或交付错误结果。

撤回对**这次对抗审查**有价值，就留在审查产物；不要因此让每个目标的 decisions 默认多一套评审方画像。等出现真实消费者（例如后续 judge 必须按历史误差校准同一 evaluator）和一次丢失造成的重复错误，再抽成共享结构。

### 4.4 “校验承诺”：若有承诺就该校验，但所提 join 已有可复现假阳性

如果 trajectory 成为强制契约，校验它是该特性的一部分，不是第四个独立演化机制。不过照抄 Protoss 的算法会把不完整轨迹判绿：checker 在找不到 SHA 时只取 commit subject 前 30 字符做 `grep -F`。在被引用的 391-commit revision 上已经有三组真实碰撞（组大小 3、2、2），包括三个都以 `loop: pay the pre-registration` 开头的提交；少一条记录可以被另一条同前缀记录冒充。tip 永远允许 pending，也意味着循环若在 tip 结束，最后一条承诺没有闭合检查。

“trajectory append-only、永不改已有条目”与“下一阶段回填上一条 SHA”也需要二选一；回填就是改旧条目。若未来真采用，使用 gate 已有的 `(run_id, turn/event_id)` 作为唯一键，commit 后由观察者记录完整 SHA，并让最终关闭检查不存在 pending；不要用 subject。更根本的是，`方案与论证.md:61,84,146` 已明确撤回每轮强制 Git commit，未授权时不自动提交。第 193～194 行和阶段 3 又把“一 tick 一 commit + 轨迹 join”带了回来，和已采纳的灵活架构直接冲突。

### 4.5 “scope 完全不相交是唯一并行写条件”是反例已经打穿的绝对句

同一份 Protoss `LEDGER.md:2174-2176` 记了连续三次事故：即使限定各自 path scope，多个 actor 仍共享一个 Git index，文件不相交也挡不住 staged 状态互相裹入；最终修复是独立 worktree。反过来，有 worktree／事务／明确 merge owner 时，scope 可以重叠，只是冲突必须显式解决。

所以正确规则是：**并行写需要互斥所有权、真实隔离或冲突控制；共享可变依赖则串行。** “scope 完全不相交”既不是充分条件，也不是唯一允许条件。

## 5. 全篇其他错误与最终裁决

**最终裁决：`REQUEST CHANGES`。** 一句话架构与“Stop 只做窄门”的方向成立，但综合方案还不能直接成为实现说明或合并依据。除了第 2～4 节已经展开的结论，还有以下跨节错误。

### 5.1 还需改掉的事实与契约错误

1. **阶段 0 不是四条，而是五条。** 精确配对探针已经把 Codex `_deny` 从待确认风险升级为当前版本上的实证缺陷。第 1 节标题、第 24～26 行、阶段 0 的内容与探针门槛都要同步改成五条；不能只在附录保留“可能”。
2. **“下一次可注入事件”不是放行反馈的保证通道。** 第 38～40 行把义务分给阻塞 reason 与下一次 `UserPromptSubmit`／`SessionStart`。前者只覆盖真正被 block 的分支；后者可能根本不来：Kimi 的 task／system-triggered turn 不等于 UserPromptSubmit，SessionStart 也不是每次续跑或下一 turn 的保证事件。因此，allow 必须无模型上下文；重要结果要在 Stop 前已由普通工具流可见，并在 allow 前写入耐久状态。下一事件注入只能是 best effort，不能承担 correctness。
3. **“`_block_streak` 按回合身份划界，所以安全”对 zCode 是假话。** 当前 `goal_hooks.py:109-125` 明说 zCode 既没有语义可用的 chain flag，也没有 turn boundary；上一条链在 interrupt／error／session end 后可把尾巴带进下一 turn，导致提前一个 block 放行。这是保守的 liveness 损失，不是 turn-scoped 机制。更重要的是，第 3 节若改成“只在 completion candidate 跑 anchor”，现有按 `anchor_checked` 累加的 streak 所测对象已经变了，不能在阶段 0 先宣告“原样保留”，然后阶段 1 再换生命周期。无限纠正已有历史失败，保留一个 gate-owned ceiling 有依据；但要在新完成协议确定后把它重定义为“有界 completion attempts”，明确 zCode 的降级，不能再称为 host cap − 1 或四家都按 turn 精确计数。
4. **“解冻是删除形状、代码不动”与源码和阶段门槛都冲突。** `goal_stop.py:543-558` 固定比较第一条 `anchor_checked.spec_digest`；它不会识别获授权的新 baseline。阶段 2 若真的支持同一 run re-baseline，就必须有被 gate 消费的状态转移与测试；若不改代码，就只能结束旧 run、由 owner 以新 spec 开新 run。二者选一个，不能同时写。
5. **“每个进化机制都有复现失败”目前不成立。** 按方案自己的阶段 3 门槛，四项都是 `NOT ADMITTED`：trajectory 的例子复现的是“已有日志却没有消费者”，decision ID 没有歧义实例且 `Who` 已存在，Retractions 只有本次审查的局部记录需求，audit 只是尚未获准 trajectory 的从属校验且 proposed join 已有碰撞。不要为了让阶段表齐全而倒推失败。
6. **“未验证不阻塞其他家”只能用于按宿主拆分的发布声明。** 第 7 节如实承认 Kimi 与 zCode 的真实 hook 加载覆盖为零，这可以不阻塞一个明确标为“仅 CC”或“仅 Codex”的结果；若同一版本仍声称四宿主支持，缺失的生命周期验收就必须阻塞该声明。测试数量、注册文件和 source inspection 不能替代这条边界。

### 5.2 建议交给 owner 的最小执行顺序

| 阶段 | 只做什么 | 通过条件 |
|---|---|---|
| **0** | 修五个已证实的宿主／启动缺陷：CC allow-context、解释器 fallback、启动前 exit 2、session ownership、Codex mixed `_deny` | 每个有针对性回归；CC、Codex 各有修后正向真探针；同 cwd 双 session 隔离实测 |
| **1** | 定义 completion candidate；门只在该时刻对当前状态亲跑一次当前 anchor，并当场裁决 | 旧 row、错 session/spec/anchor、检查后再写入都不能放行；一次真实完成路径通过 |
| **2** | 选择 re-baseline 语义：要么 owner 授权后同 run 状态转移，要么关闭旧 run 开新 run；把 anchor observation 与 run disposition 分轴 | 未授权改约不能建立 baseline；旧观察保留；暂不新增 `impossible` gate outcome |
| **3** | 暂不加入四个 evolution 默认机制 | 以后只在一个具体失败及其消费者同时出现时，加最小的一项；若加 trajectory，校验与它同批、用无碰撞 identity |
| **4** | 按宿主做完整生命周期验收并分别标注支持状态 | 只对实际通过的宿主作支持声明；共享“四宿主”声明需四家都通过 |

这个顺序也解决了原阶段表的依赖倒置：先定 completion 生命周期，才知道 streak、event schema 与 re-baseline 应挂在哪里；不能先保留旧计数，再在下一阶段把它所计的事件改掉。

### 5.3 对四个提问的最终短答

| 问题 | 裁决 |
|---|---|
| 是否诚实代表 Codex 发现 | **基本是。** 需删去“Codex 主张每业务迭代跑完整 anchor”的归因，并把旧探针称为“unsupported mixed schema”，不是 invalid JSON。 |
| Anchor 分层是否开自述缺口 | **按现文会。** 门若只比对 run 写的旧 evidence，就有缺口；门若在 completion candidate 上亲跑、当场裁决，历史行只作审计，就没有这个 stale-row 缺口。 |
| 是否增加 `impossible` | **保留语义，不加同层机械 outcome。** 用 `unachievable` 表达经独立核实的 run disposition；green/red/unknown 继续只表达 anchor observation。 |
| 四个 evolution 机制有几个无复现失败 | **4/4 尚未达到默认加入门槛。** trajectory audit 若将来获准，是同一个机制及其校验，不应算两项。 |
| 精确 Codex `_deny` 是否失效 | **是，在本机 Codex 0.150.1 已由配对正控确认。** 修复后仍需再跑同级正控，不能把本轮失败外推为所有版本。 |

因此，我同意把这份综合方案作为下一版的编辑底稿，不同意按现文开始实现或合并 `host-adaptation`。最小修订不是再添协议，而是：把五个已证实缺陷修实；让完成门自己测当前事实；把授权、观察、生命周期三个概念拆开；其余四件先不做。
