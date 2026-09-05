# UltraGoal 使用指南

[开始使用](../README.zh-CN.md) · [English](usage.md)

本指南说明目标文件、任务分配、验收和恢复的具体规则。安装和第一个目标的操作请先看 [README](../README.zh-CN.md)。下面的命令示例使用目标名 `export-ready`。

- [从一句要求到确认目标](#从一句要求到确认目标)
- [执行期间的自主权](#执行期间的自主权)
- [派送 Agent 与接收反馈](#派送-agent-与接收反馈)
- [什么时候问用户](#什么时候问用户)
- [文件及其维护](#文件及其维护)
- [绑定目标与原生续跑](#绑定目标与原生续跑)
- [Hook 与宿主覆盖](#hook-与宿主覆盖)
- [最终完成验收](#最终完成验收)
- [独立评审](#独立评审)
- [恢复取消与清理](#恢复取消与清理)
- [故障排查](#故障排查)
- [知识与 Skill 维护](#知识与-skill-维护)
- [验证方式与能力边界](#验证方式与能力边界)
- [单独安装 Skill](#单独安装-skill)
- [快捷入口维护](#快捷入口维护)

## 从一句要求到确认目标

UltraGoal 先判断你是要创建目标、修改已有目标、查看进度，还是继续执行。普通的一次性任务会直接处理。参考文件按当前阶段需要读取。

Agent 先检查仓库、可用工具和项目指令，只把无法从这些资料中确定的选择交给你。每次问一个问题，说明建议，以及哪些事实会改变建议。提问次数取决于还有多少问题没有确定。

最终契约包括：

| 字段 | 确定什么 |
|---|---|
| `Intent` | 保留关键用户原话；有来源位置时一并记录；与 Agent 的操作性解释分开 |
| `Acceptance` | 有稳定 ID 的无序验收项；执行计划另放 |
| `Anchor` | 检查约定结果的观测命令，以及明确的时间预算 |
| `Stop condition` | `success: verified`；`ceiling: N` 或 `ceiling: none`，上限计算完成验收尝试 |
| `Means` | 完整手段声明，标为 `[load-bearing]` 或 `[droppable]` |
| `Boundary` | 路径、影响和审批范围；需要实测的置信声明；不能直接推断的结论 |
| `Verification` | 检查依据、受保护的检查材料、每项验收的覆盖关系，以及必需评审 |
| 角色与资源 | 工作职责、已批准替补、读写范围、集成责任 |
| `Carry-over` 与 `Handoff` | 当前状态、经验、下一步和真实启动及恢复流程 |

冻结之前同时质询两种情况：**误放行**，即检查全绿但用户要求没满足；**误拒绝**，即有效结果被用户没要求的方法限制拒绝。只有单元测试确实覆盖所需结果时，它才足够；文件存在也不代表可用。

提供无人值守执行前，指令要求独立的规格质询。先给质询者原始要求、草案和证据，不先给作者的辩护。解决实质异议后回读完整契约。已有的明确确认可以沿用，沉默不能算确认。“直接开始”不等于放弃审查；对已批准条款的质询没有发现实质问题，就不需要再问一轮。

规格质询及面谈质量目前主要靠**模型遵守指令**。结构校验不能证明质询确实发生，也不能证明验收标准完整表达了用户意图。

详见[统一目标契约](../plugins/ultra-goal/skills/ultra-goal/references/goal-contract.md)。

## 执行期间的自主权

| 层次 | 内容 | 修改规则 |
|---|---|---|
| Frozen：冻结 | Intent、Boundary、Anchor、Stop condition、Verification、验收项文字、完整且已标记的 Means | 需要用户授权和新的目标 |
| Firm：允许调整但要说明 | 方法、节奏、工作者选择、放弃已批准可弃手段、使用已批准验证者替补 | 在现有授权内调整，更新决策行并给出证据 |
| Fluid：执行状态 | State、Lessons、Next、普通执行计划 | 随新证据重写 |

“某手段可以放弃”的声明被冻结，执行期间决定实际放弃它属于策略调整。决策行记录选择，不能给自己降低标准、增加预算或豁免必需评审的权限。

Loop 由主模型根据观测选择下一步。可选 `.workflow.js` 和 `.delegation.md` 附件引用同一个 `.goal.md`，不能另立条款。只有真实消费者存在且入口已走通过，才生成 workflow。JavaScript 能解析，不代表 `agent()` 或 `pipeline()` 能运行。

## 派送 Agent 与接收反馈

主 Agent 通过宿主的委派工具分配任务。你指定了角色，就按指定执行；其余任务由它判断是否需要其他工作者。小任务可以留在主会话中完成。Skill 不规定厂商顺序，也不要求每项任务都安排三家评审。

使用宿主真实提供的委派工具，或已经安装的桥接工具。如果存在 `agent-delegate`，可用 `agent-delegate list --json` 发现注册目标。Skill 不负责安装或模拟该桥接工具。

每个 mission 应给出：

1. 已确认条款，以及本次任务的明确目标。
2. 当前决策、相关原始证据、之前失败的尝试。
3. 读写范围、共享资源、限制与集成责任。
4. 预期产物位置，以及如何检查。
5. 哪些问题可以自行解决，哪些需要返回。

工作者可在 `.goals/.work/` 放置 mission/result 文件。两份任务文件不能隔离对同一源文件、数据库或服务的写入。并行只适用于实际独立的工作；集成评审之前，主 Agent 要等待相关写入者结束。

反馈需要区分：

| 观测 | 主 Agent 应如何处理 |
|---|---|
| 调用成功 | 检查约定产物；传输成功不代表完成 |
| 工作者报告完成 | 读取实际文件及证据，对照 mission |
| 工作者失败 | 保留观测，选择授权内重试、替代方法或替补 |
| 工作者需要输入 | 优先依据已有条款回答，只把实质用户决策转给用户 |
| 工作者明确拒绝 | 检查拒绝的边界及授权内替代路径 |
| 没有响应 | 状态为未确认；查询原生任务，不猜成等待用户或完成 |

**一次调用即使成功，但没有写出文件，也不能算交接完成。该轮证据是角色被要求写出的实际产物。** 返回摘要是声明，多模型意见一致也不等于独立证据。

在注册对应事件的宿主上，可识别的委派失败产生 `role_unavailable`；同一目标、同一工具的后续成功产生 `role_recovered`。识别范围是直接的 `agent-delegate run --to <target>`，或对该工具的结构化调用。不透明脚本、复合命令、任意原生子 Agent 工具，不会自动得到同等观测。恢复记录针对调用，不代表该目标的全部任务都完成。

这些传输事件用于审计，不是额外的验收条件。原厂商持续不可用时，获准的替补仍可以满足目标。**必需的独立评审者不能降级为生成者自审。** 额外建议性评审、reviewer/critic 对抗讨论，除非目标要求，否则按需使用；重复评审需要上限。

主 Agent 读取反馈后重写 `State`、`Lessons`、`Next`；策略改变时更新相应决策，再决定下一步。宿主执行工具调用，主 Agent 决定接下来采用什么方法。

## 什么时候问用户

提问由主 Agent 通过正常对话或宿主提问界面完成。Hook 不主持面谈，也不把每个工作者的问题原样转给用户。

| 情况 | 做法 |
|---|---|
| 可核对的仓库或工具事实 | 自行调查 |
| 调整方法、顺序或使用已有批准的替补 | 在授权内决定，记录实质选择 |
| 改验收标准、承重手段、边界或预算 | 问用户 |
| 需要现有授权之外的影响 | 在该影响发生前问；独立且已获授权的工作可以继续 |
| 必需验证者不可用，也没有合格替补 | 保持未验证，说明缺少的条件 |
| 外部操作结果未知 | 先查询实际效果，再决定重试或升级问题 |
| 冻结条款冲突 | 说明条款、实际障碍、建议及决定性事实 |

执行中的质疑写入决策文件的 `## Challenges from the run`。质疑本身不能授权修改条款。已有批准持续有效，不反复追问已经确定的选择。

## 文件及其维护

制品放在业务项目的 `.goals/`，不放在某家工具的私有 Skill 目录。`<slug>` 是一个目标名，不是路径。

| 文件 | 写入者 | 维护规则 |
|---|---|---|
| `<slug>.goal.md` | 用户与 Agent 共同定契约；主 Agent 写 Carry-over | 保留冻结条款，重写当前执行状态 |
| `<slug>.decisions.md` | 用户与 Agent | Decision / Rejected / Why / Who；修改对应行，区分 `owner` 与 `agent` |
| `<slug>.events.jsonl` | 验收器及 Hook 脚本 | 追加观测，不把模型声明写成测量 |
| `active` | `arm`、`rebind`、`disarm` | 目标名和拥有它的原生会话 ID；临时文件 |
| `<slug>.spec.baseline` | 启动脚本 | 冻结契约摘要，只在建立时写入 |
| `<slug>.verification.baseline` | 启动脚本 | 受保护检查材料的哈希，只在建立时写入 |
| `<slug>.baseline` | 启动脚本 | 启动时 Git 修订或 `none`，不等于完整历史 |
| `<slug>.verification.lock` | 验收脚本 | 原生锁串行化验收，保留锁文件 inode |
| `<slug>.candidate` | 主 Agent，可选后备路径 | 一次待验收的完成声明，由验收器消费 |
| `<slug>.review.json` | 独立验证者 | 当前凭据默认位置；声明输入变化后重新评审 |
| `<slug>.reviews/<digest>.zip` | 验收器 | 保留凭据、目标和声明输入快照，用于历史审计 |
| `.work/` | 各工作者 | 必要证据另有保留位置后，才可丢弃中间产物 |
| `<slug>.workflow.js` / `<slug>.delegation.md` | 获授权的 Agent | 可选执行附件，不另立成功条件 |

每个工作回合结束前，主 Agent 重写：

- `State`：当前事实、证据位置、未完成事项。
- `Lessons`：会改变下一步的、有适用条件的原因判断，不是事件日记。
- `Next`：一个立即恢复的目标；有需要时链接较长计划。

建议把摘要控制在三条经验、八条状态左右。第四条经验如果会影响下一步，就应保留。精简时也要保留结论的来源。这些文件由主 Agent 维护，Hook 只能读取已经保存的内容。

事件记录保留有界观测、摘要和输出片段，不自动保存全部 stdout 或所有对话。必需评审归档保存**声明的输入**，不自动保存整个工作区。其他重要原始证据要明确留存。Git 只保留已提交的版本；跟踪文件不等于授权提交或发布。

详见[文件维护规则](../plugins/ultra-goal/skills/ultra-goal/references/document-system.md)。

## 绑定目标与原生续跑

`arm` 校验目标和配套决策，确认真实启动会话，拒绝接管其他目标或会话，建立基线，记录会话归属，最后创建活动标记。一个项目目录只有一个活动目标标记。

以下是供检查的格式，不是让用户手动写入的指令：

```text
export-ready
session actual-native-session-id
```

必须明确使用当前真实原生会话 ID，不能猜测，也不能采用继承来的父进程身份。其他会话或缺少身份的事件不能消费拥有者的候选或重置状态。再次 `arm` 保留基线和历史次数。明确授权的 `rebind` 转移会话时，也保留这些事实，并丢弃前一会话的待验收声明。

手动操作时，替换下面的示例路径、目标名和身份：

```bash
ULTRAGOAL_SCRIPTS="/path/to/ultra-goal-skill/plugins/ultra-goal/skills/ultra-goal/scripts"
ULTRAGOAL_PROJECT="/path/to/business-project"
ULTRAGOAL_SLUG="export-ready"
ULTRAGOAL_SESSION="actual-native-session-id"

python3 "$ULTRAGOAL_SCRIPTS/validate_artifact.py" "$ULTRAGOAL_PROJECT/.goals"
python3 "$ULTRAGOAL_SCRIPTS/goal_run.py" arm "$ULTRAGOAL_SLUG" \
  --root "$ULTRAGOAL_PROJECT" --session-id "$ULTRAGOAL_SESSION"
```

`arm` 启用验收门，原生 Goal 模式提供继续执行的机会。存在已授权、模型可调用的原生机制时就使用；如果宿主只暴露用户命令，则由用户调用那条真实命令。没有续跑机制时，Agent 可以在当前回合工作，但不能承诺后续自动唤醒。不得通过后台脱离进程绕过宿主的取消或续跑限制。

## Hook 与宿主覆盖

下表表示**当前包注册了哪些事件**，不代表各家 API 相同，也不代表每家当前安装都已重新实测。

| 事件 | Claude Code | Codex | Kimi | zCode | 用途 |
|---|---|---|---|---|---|
| `Stop` | 是 | 是 | 是 | 是 | 普通结束观测或显式完成候选验收 |
| `SessionStart` | 是 | 是 | 否 | 是 | 支持的 start/resume/clear/compact/fork 恢复 |
| `PreCompact` | 是 | 是 | 是 | 否 | 压缩前 Carry-over 摘要和条目数量 |
| `PostToolUseFailure` | 是 | 否 | 是 | 是 | 可识别的委派调用失败 |
| `PostToolUse` | 是 | 否 | 是 | 是 | 可识别调用恢复 |
| `UserPromptSubmit` | 否 | 否 | 是 | 否 | 用户提交消息时提示目标位置与上次结论 |
| `TurnStarted` | 否 | 否 | 是 | 否 | 记录真实原生回合 ID 和来源 |

公共配置在 `hooks/hooks.json`；Claude 追加 `hooks/claude.json`；Codex 使用 `hooks/codex.json`；Kimi 在 `kimi.plugin.json` 内声明配置。包内有各宿主输出格式及 Windows 命令适配；存在这些配置不等于 Windows 生命周期验收通过。

普通 Stop **没有完成候选时**，不执行 Anchor，也不消耗验收次数。Stop 不是后台服务，也不是覆盖所有写入操作的权限门。冻结规格变化在 Stop 检查；检查材料保护在验收边界检查。发现变化不能撤销已经发生的写入或外部影响。

拦截输出遵循宿主契约：Claude/Codex/zCode 使用顶层 `decision: block` 和 `reason`；Kimi 使用嵌套的 `hookSpecificOutput.permissionDecision: deny` 与 `permissionDecisionReason`。放行 Stop 不附加模型上下文。交付前应通过普通工具输出取得判定，之后的恢复注入只能尽力而为。

详见[Hook 与生命周期限制](../plugins/ultra-goal/skills/ultra-goal/references/host-hooks.md)。

## 最终完成验收

优先显式调用 `verify`。它是普通工具调用，可以在 Agent 最终回答**之前**返回当前结果，与 Stop 后备路径使用同一套验收器：

```bash
python3 "$ULTRAGOAL_SCRIPTS/goal_run.py" verify "$ULTRAGOAL_SLUG" \
  --root "$ULTRAGOAL_PROJECT" --session-id "$ULTRAGOAL_SESSION" \
  --claim "The integrated result is ready for the accepted checks."
```

调用前要完成产物、更新恢复状态、等待相关写入者，并取得必需的独立评审凭据。验收路径如下：

1. 确认活动目标和会话，取得原生验收锁。
2. 将此前已开始却未结算的验收识别为中断；不能采用更早的绿色结果，也不自动重放 Anchor。
3. 对照启动基线检查冻结条款。
4. 消费候选前，写入带唯一 ID 的 `verification_started`。
5. 检查完成尝试上限、受保护检查材料、必需的当前评审。
6. 在约定时间预算内执行 Anchor。
7. Anchor 之后再次检查条款、检查材料与评审输入。
8. 留存必需评审证据，用同一个尝试 ID 结算。

当前记录必须证明整份验收契约通过：冻结条款有效、检查材料保护有效、本次 Anchor 为绿、全部必需评审有效。`verification_passed` 和 `fresh_check` 对应当前请求；没有可读取的本次结算，不能声称完成。

| 情况 | 验收门行为 | 是否证明完成 |
|---|---|---|
| 普通 Stop，没有完成声明 | 放行，不执行 Anchor | 否 |
| 当前完整验收通过 | 放行 | 约定检查通过 |
| Anchor 红，或必需验证条件不满足 | 在适用的连续拒绝上限内拒绝可拦截的声明 | 否 |
| 命令不可用或超时 | 放行，结果未知 | 否 |
| 完成尝试次数耗尽 | 放行，报告未完成工作 | 否 |
| 连续拒绝额度耗尽 | 结束当前回合，后续依赖原生回合或用户消息 | 否 |
| 冻结规格改变 | 关闭运行，移除活动标记及候选 | 否 |
| 已绑定目标遇到其他会话或缺少身份的事件 | 不介入 | 不判定 |
| 旧格式或无有效会话绑定的标记 | Stop 提示诊断，不执行处理器、不改状态 | 不判定 |
| Hook 无法形成可靠判断 | 不困住宿主，不能作为成功证据 | 否 |

三个限制相互独立：用户的**完成验收尝试上限**、验收门的**连续拒绝上限**、**宿主原生预算**。`ceiling: none` 不会解除宿主限制。当前单次 Anchor 最大 570 秒，外层 Stop 配置为 600 秒。

Anchor 观测是 `green`、`red` 或 `unknown`。运行状态另有一条轴：`in_progress`、`input_required`、`blocked_retryable`、`budget_exhausted`、`unachievable`、`completed`、`canceled`。一次检查失败不能证明目标永久不可能实现。

后备路径写 `<slug>.candidate`，让真实 Stop 在响应**之后**检查；此时只能说待验收。显式验收已经消费的声明，不会被接下来的 Stop 再跑一次。如果模型口头说完成，却既不调用 `verify` 也不写候选，当前没有自然语言完成检测器强制它进入验收。遵守声明协议仍是模型责任。

## 独立评审

每个验收 ID 都在 `Verification.covers` 中映射到 `anchor` 或 `review`。必需评审声明批准的验证者及替补、有界 `inputs` 和凭据位置。获取当前评审输入包：

```bash
python3 "$ULTRAGOAL_SCRIPTS/goal_run.py" review-inputs "$ULTRAGOAL_SLUG" \
  --root "$ULTRAGOAL_PROJECT"
```

由**独立验证者**写凭据，生成者不得代签。验收器检查：获准身份、区别于当前及历史执行者的会话、绑定契约和声明输入的摘要、所需验收 ID、通过结论，以及逐项 `checks` 中真实的路径与原文引用证据。

输入变化后需要重新评审。如果原生 fork 共用执行会话身份，就不能满足独立会话要求。

Anchor 后的边界会留存按内容寻址的 ZIP，包含凭据、目标、清单和声明输入的原始字节。历史审计检查归档，而不是拿今天的文件替换过去的材料。记录过的归档丢失或损坏会报告出来，不会静默重建，也不能拿旧归档代替当前评审。

这是可核对的声明，不是经过鉴权的凭证。共享文件中的字段不能提供身份安全；引用命中不证明结论逻辑成立。新上下文和不同模型可以减少部分相关错误，不能证明正确。先看原始证据，再看作者有说服力的解释。

## 恢复取消与清理

每轮结束前保存 Carry-over。`PreCompact` 记录它的摘要和数量，不总结未保存的思考，也不阻止压缩。支持的 `SessionStart` 注入优先条款与状态，并指出因空间省略的部分；行动前仍需阅读完整契约。Kimi 的用户消息 Hook 提供文件位置和上次结果，`TurnStarted` 只观测回合。

已开始但没有结算的验收仍为待定或未知，并占用一次尝试。恢复在取得锁后可以将它标为中断。新尝试之前核对真实文件及外部影响。请求发出却没有收到返回，可能已经产生作用，应先查询服务再重试。这是验收记账，不是业务操作的 exactly-once 保证。

已有授权且基线有效时，可以转移执行会话：

```bash
python3 "$ULTRAGOAL_SCRIPTS/goal_run.py" rebind "$ULTRAGOAL_SLUG" \
  --root "$ULTRAGOAL_PROJECT" --session-id "$ULTRAGOAL_SESSION"
```

恢复不会续期授权、增加预算或重新启动已取消工作。取消需要同时处理**原生目标状态和 Skill 验收门**。只解除绑定不会取消原生目标：

```bash
python3 "$ULTRAGOAL_SCRIPTS/goal_run.py" disarm "$ULTRAGOAL_SLUG" \
  --root "$ULTRAGOAL_PROJECT"
```

本次验收通过后，Agent 报告交付物、证据和限制，通过实际原生工具同步目标状态，再解除绑定。按约定期限保留目标、决策、事件、基线和必需评审证据。确认必要资料仍可读取之后，只清理可丢弃中间文件。不能为了让目录看起来完成就删掉未结算尝试的材料。提交、安装、发布仍需相应授权。

## 故障排查

| 症状 | 核对与处理 |
|---|---|
| 有 `active`，但没有验收发生 | 检查 Hook 发现、事件实际 `cwd`、标记格式和所属会话；普通 Stop 也不验收 |
| 旧标记只有目标名，或 session 绑定无效 | 2.15.1 的 Stop 输出 `systemMessage` 诊断；门保持未启用，文件不变 |
| UI 没显示放行诊断 | 查看原始 Hook 输出或日志；输出诊断不等于每家 UI 都会显示 |
| 普通 `arm` 拒绝旧标记 | 原始基线有效时走获授权的 `rebind`；否则显式 disarm，校验已确认目标，再 arm |
| 基线不匹配，或目标因规格改变而关闭 | 创建新授权目标，优先用新 slug；不删历史、不重新认定被改条款来掩盖变化 |
| 其他会话的 Hook 静默 | 属于预期的会话隔离，不接管标记 |
| 委派调用成功但没有产物 | 任务尚未完成交接，查询原生任务并读取实际输出 |
| Anchor 不可执行或超时 | 结果未知，检查命令、环境和预算 |
| 评审缺失、过期或由生成者写出 | 获取符合约定的当前独立评审 |
| 曾经 Anchor 通过，后来验收中断 | 最新尝试仍未验证，历史绿色不能替它结算 |
| 目标没完成，Agent 却停下了 | 核对原生预算、验收次数、连续拒绝上限；Stop 不能提供下一次唤醒 |

旧标记诊断复用已有的放行 `systemMessage` 通道，只在 Stop 发出。它不自动迁移、不执行处理器、不消费候选、不写事件，也不注入续跑上下文。已绑定目标上的其他会话仍保持静默。在宿主进程环境设置 `ULTRA_GOAL_HOOKS_DISABLED=1` 可以禁用这些 Hook；原生目标状态仍需单独处理。

只读查看及历史证据核对：

```bash
python3 "$ULTRAGOAL_SCRIPTS/validate_artifact.py" "$ULTRAGOAL_PROJECT/.goals" --status
python3 "$ULTRAGOAL_SCRIPTS/validate_artifact.py" "$ULTRAGOAL_PROJECT/.goals" --audit
python3 "$ULTRAGOAL_SCRIPTS/goal_run.py" diff "$ULTRAGOAL_SLUG" --root "$ULTRAGOAL_PROJECT"
```

`--status --run-anchors` 不同：它执行制品里声明的 shell 命令，需要这些影响已经获得授权。审计报告指出分歧，不自动修复，也不证明规格充分。

## 知识与 Skill 维护

区分原始观测、当前状态、有条件的项目知识。经验放在已有项目文档里，带证据、适用条件和失效条件。业务运行可以重写自己的状态，不能自动改已安装 Skill 或全局配置。

获授权的维护采用轻量循环：留存失败，形成条件性知识，提出最小指令或代码修改，在相关与未参与制订规则的案例上和基线比较，再保留或回滚候选修改。失败实验也保留。这里没有常驻维护 Agent 或自动规则晋升。

[研究依据](../plugins/ultra-goal/skills/ultra-goal/references/research-basis.md)链接 OpenAI、Anthropic、Google 等前人工作。WikiSkill 启发经验、知识和可执行 Skill 的分离；SKILL.state 启发不可变规格与可变状态的分离。论文的实测结果和 Runtime 性质不会自动转移到本 Skill。具体见[维护流程](../plugins/ultra-goal/skills/ultra-goal/references/evolution-and-scope.md)。

## 验证方式与能力边界

无需安装测试依赖，在仓库运行：

```bash
python3 -m unittest discover -s tests -v
```

测试覆盖契约校验、会话归属、候选验收、中断记账、锁、评审证据留存、宿主输出契约与包结构。2.15.1 回归通过四个 Stop 适配入口检查旧标记提示，并验证目标文件字节完全不变。这些测试检查脚本行为；宿主 UI 和无人值守运行需要单独进行生命周期验收。

面谈充分性、规格质询、路由、等待工作者、状态维护和调用完成协议，仍由模型负责。脚本机械化检查明确事实，不能验证每句自然语言、鉴权共享文件身份或证明原始目标永远正确。

产品和宿主探针的结果只覆盖实际测试过的场景。四家完整无人值守收口、Windows 原生生命周期、所有取消与恢复组合，以及超过 95% 的统计可靠性，仍未建立。Eval 场景定义不等于已经完成模型试验。详见[剩余验证范围](../docs/wip/outstanding.md)。

## 单独安装 Skill

复制安装器使用 `datetime.UTC`，需要 Python 3.11 或更新版本。核心目标脚本需要 Python 3.10 或更新版本。

没有原生插件安装路径时，仓库还提供受管理的复制安装器：

```bash
git clone https://github.com/rocky2431/ultra-goal-skill.git
cd ultra-goal-skill
python3 scripts/install_user.py install --hosts claude
python3 scripts/install_user.py doctor --json
```

可选复制目标为 `hermes`、`claude`、`codex`、`kimi`、`zcode`、`opencode`。安装器保留变更备份，并拒绝覆盖不属于它管理的同名 Skill。`uninstall --hosts <host>` 删除其管理的安装。

这条路径复制主 Skill，**只配置 Claude 的 Stop、SessionStart 和 PreCompact Hook**。它不安装完整的原生命令及角色包，也不配置其他宿主的 Hook。这里的 doctor 检查自身文件与注册，不能证明无人值守运行。

## 快捷入口维护

[快捷入口安装器](../scripts/install_shortcuts.py)生成用户命令或 Skill 文件，让它们读取原来的 UltraGoal `SKILL.md`。面谈、授权和完成判定使用同一份指令。插件包标识是 `ultra-goal`，启动命令和目标文件沿用各自的名称。

安装器会打印每个文件的路径，允许重复安装内容相同的入口，拒绝覆盖冲突文件。删除这些文件即可移除快捷入口。更换来源时，先删除，再用 `--skill /path/to/ultra-goal/SKILL.md` 重新安装，并将源文件保留在该位置。

Kimi 默认写入 `~/.kimi-code/skills`。使用自定义 `KIMI_CODE_HOME` 时，将生成的 Skill 文件夹放入该根目录的 `skills/`。

入口写法由宿主决定：[Claude 插件命令带命名空间](https://code.claude.com/docs/en/plugins)，[Codex 使用 `$skill`](https://learn.chatgpt.com/docs/build-skills)，[Kimi 使用 `/skill:name`](https://moonshotai.github.io/kimi-code/en/customization/skills.html)。Claude 的裸 `/UG` 由独立快捷文件提供。zCode 的实际发现情况仍需在安装版本中测试。

Claude Code 和 Codex 的插件安装示例已于 2026-09-05 对照本机 CLI 帮助核对。这个检查确认命令形式；安装、组件发现及 Hook 执行仍需在所用版本中验证。
