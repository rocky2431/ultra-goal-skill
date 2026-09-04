# Ultra Goal 最终对抗评审 · 第 3 轮 · reviewer: claude

角度:生命周期、普通验证交付、原生评估器共存、stop/allow 语义。已读 proposal-draft、challenge-cases、live-host-validation、session-binding、plugin-discovery、codex round1+cross-examination、kimi/zcode round1+2、我的 round1+2。

## 0 立场

**allow:候选的 allow 语义我完全接受**(静默放行、unknown 永不 block、异常 fail-open、归属不符即惰性)。
**block:接受"每观察链一次、短、确定性、无副作用"的有界纠正**,但必须先修 X1,否则纠正通道本身会被自己的配置错误劫持。
**completion:接受"gate 永不宣布完成"**。加一条:候选允许在宿主暴露操作上武装原生 goal,却把"无法停止"留给事后报告 —— 应改为武装前的准入条件(X2)。
**作为架构决策:可以定,条件是 X1/X2/X3 三条修正写进决策文本。四宿主无人值守实现:未验证,且现有证据不支持任何四宿主生命周期声明。**

## 1 仍然成立的反例(候选明文承诺之内)

### X1 非自愿 exit 2 会被四家读成有意纠正 【实测·本轮新增·最高严重度】

候选第 47 行承诺"Unexpected parsing/command failures must not leak exit 2 as an intentional control decision"。而共享 exit-2 传输恰好把最常见的一类脚本故障变成合法 block。本轮实测(`reviewers/claude/probe3/`):

```
python3 /nonexistent/goal_stop.py --host claude   -> exit 2, stderr "can't open file ...: [Errno 2]"
python3 ap.py --bogus                            -> exit 2, stderr "error: unrecognized arguments"
python3 -c 'raise RuntimeError("x")'             -> exit 1   (脚本内异常反而是安全的)
```

脚本顶层 try/except 只能保护解释器**进入脚本之后**;插件根变量未注入/路径改名(四家变量名不同,adapt 已经依赖 `${ZCODE_PLUGIN_ROOT:+--host zcode}` 这种 shell 展开)与 argparse 用法错误都发生在它之前,且都带非空 stderr —— 正是四家判定"有意阻断,stderr 即理由"的形状。后果按宿主:Kimi 1 次/回合、zCode 3、Claude 受粘性布尔与 8 次上限约束,**Codex 在已检查的 Stop 循环里没有固定上限**,一个装错路径的 hook 可以每次 Stop 都以 "can't open file" 作为纠正理由复读。

**最小修正**:注册的命令自身不得有能力返回 2。一行守卫即可,实测有效:

```sh
sh -c '[ -f "$1/goal_stop.py" ] || exit 0; exec python3 "$1/goal_stop.py"' _ "$PLUGIN_ROOT"
# 未设置/缺文件 -> exit 0,零 stderr;脚本有意阻断 -> exit 2,stderr 原样透传(已实测)
```

配套:**宿主判别改为从 stdin 载荷观测,不用需要 shell 展开的 flag**(消掉 argparse 那条路)。若某宿主的 command 不经 shell 解释,等价守卫必须放进一个自身不可能 exit 2 的启动器。不要用"再加一个包装脚本"以外的东西解决它。

### X2 Claude 上"可武装、不可停止"的不对称应前移为准入条件 【源码+活体探针】

`ProposeGoal` 可创建、**不能 clear**(二进制原文,round2 §3.2);zCode 无模型路径。候选第 58/63 行的处理是"如果原生终态不可观测/不可控,就报告这个边界"。但事后报告不能撤销效果:Ultra 判完成之后,Claude 的评估器仍在按它自己的 condition 推动回合,而 clean-claude-goal-coexistence 探针里模型正好产出了凭空发明的 token-rotation 文本 —— 这就是"被推着造工作"的形状(challenge case 21/22)。

**最小修正(一条准入规则,不是新机制)**:只在满足其一时武装原生 goal —— (a) 同一表面同时暴露技能可用的停止/完成路径(Codex `update_goal`、Kimi `UpdateGoal`);或 (b) condition 写成**普通验证工具的原始输出**即可让原生评估器自己判 met(Claude 评估器只读 transcript,`ProposeGoal` 原文 "from the conversation alone — it cannot run commands or read files")。二者都不成立时(zCode、以及 Claude 上 condition 无法由 transcript 判定的目标),不武装,交回主人显式命令。这把"去同步"从事后披露改成事前不发生。

### X3 回合内验证与完成声明之间的证据漂移

候选要求"完成前用普通工具做适用验证",但同一回合里验证之后仍可继续授权修改,再调用完成工具。**最小修正**:捕获脚本在记录验证结果时一并落盘 artifact/goal 标识;完成声明必须引用该记录的标识;标识与当时不一致就重新观测。这是候选第 43 行"capture verification outputs and artifact/goal identity"的直接用法,不需要新组件、不需要 hook 有裁决权。

### 不算设计缺陷的(候选没有承诺,应保持为明写边界)

无 portable 后台唤醒;四家都不向 hook/skill 暴露 pause/resume;原生评估器越权或 zCode `failed_open`;进程死亡/凭据耗尽恢复;用户中断时 Stop 不触发导致时间轴留洞。这些是宿主能力缺失,候选已如实标注,**不应用任何 Ultra 机制假装覆盖**。

## 2 时序与 stop_hook_active:按要求订正 Kimi

Kimi round2 §3 R2 附注说"Claude 上 `stop_hook_active` 在工具调用后归零",并把它记在我 round1 名下。**这是把布尔与计数器混为一谈,予以订正。** 本轮在 2.1.260 里定位到状态解构点:

```
{messages:Fn,…,pendingToolUseSummary:vo,stopHookActive:No,stopHookBlockingCount:go,turnCount:Nr}=
```

即 `No` 是**传入的布尔**、`go` 是传入计数。工具分支写回 `stopHookActive:No, stopHookBlockingCount:0, transition:{reason:"next_turn"}` —— **布尔原样透传,只有计数归零**;阻断分支写 `stopHookActive:!0, stopHookBlockingCount:qd`。所以:计数随工具调用复位(8 次是无进展保护),**重入布尔在链内粘住**。Kimi 那条统一规则("只在宿主说本回合没续跑过时 block")在 Claude 上因此**不是**"干活之后可再纠正一次",而是**每链至多一次**。

同向的本轮新事实:终止路径(max_turns、上限触顶、preventContinuation)仍会跑一次 Stop 反应,但阻断被明确丢弃 —— `[stop-hooks] Turn-end reaction hook block discarded`。所以某些 Stop 调用在结构上不可能纠正,而 hook 无法从载荷分辨。**结论与使命一致:保守重入守卫承诺的是机会性纠正,不是每业务迭代一次;不得从这个布尔重建任何回合计数。** 再叠加 Kimi `markComplete` 先于最终续行与外部 Stop 回调(update-goal.ts;kimi-turn.ts:925-974),Stop 对已发生的状态迁移没有否决权 —— 不要因此推荐通用 PreToolUse 拦截:没有任何一家的原生完成工具被证明会到达 PreToolUse。

## 3 "Stop 复测是全栈唯一非模型测量" —— 拒绝这个表述

zCode §1-4/§7 与 Kimi §6 攻击 2 都用它给 Stop 复测背书。**普通工具调用的退出码同样不是模型产生的**,它由 OS 产生并原样进 transcript(而这恰是 Claude/zCode 评估器唯一读得到的东西)。Stop 的独有属性只有一个:**不请自来** —— 它不由模型在声明完成时挑选。测量能力不是它的独有属性。

由此:普通工具跑既有验证器 + 捕获脚本落盘"观测到的结果 + artifact 标识",Stop 只检查这条**任务实际要求的**证据记录是否存在、标识是否匹配,缺失即请求一次纠正。记录当然可伪造 —— 但 Stop 自己的日志也一样(zCode 实验 C 已证)。二者的差别只在发起方,不在可信度。**所以在 Stop 里再跑一遍完整套件需要单独理由**(耗时、权限、可取消性、宿主超时都在 hook 侧变差,challenge case 20),短而确定、无副作用的复检在有理由处才可选。这同时修掉我 round2 §6.1 第 6 行被 Kimi 正确指出的不可实现之处:gate 看不见回合内的工具调用 —— 可实现的形式是**记录**,不是复测。研究型目标据此不需要伪造一个恒绿的 shell 锚点(challenge case 6):它要求的证据形式就是被引用的来源与评审结论。

## 4 我的撤回

1. **撤回 round2 §6.1 第 1 行的 `session_crons` 非空即延后。** 无关 cron / 常驻监控会让 Ultra 无限挂起。改为:只对**与本目标相关联的必需后台工作**延后;Claude 的原生评估器有它自己更宽的策略,记录该差异,不复制进技能。
2. **撤回 round2 §4.1 的"review 文件缺失 → 一次遗漏 block"。** 文件缺失不是"没做过审查"的证明(内联审查、原生 subagent 审查都不留该文件)。改为:只检查**该验收项明文要求的证据形式**;验收行点名了文件才谈缺失。
3. **撤回 round1 D3 关于 main 的归属结论**("`.codex-plugin/plugin.json` 无 hooks 键,所以 Codex 上根本不会注册")。`core-plugins/src/loader.rs:1178-1232` 默认发现 `hooks/hooks.json`(`loader_tests.rs:638-662` 有直测),main 带该标准文件,`HookEventsToml` 也不拒未知事件字段。载荷不兼容属于 **main/adapt 共享的发射端代码**,不是候选独有;实际安装与信任状态另论,仍未验证。D3 的解析器级事实(serde 复现)不变。
4. **保留但收紧** round2 R3:`asyncRewake` 存在(可创造回合),但无上限证据,继续不作为续航基础。

## 5 peer 主张裁决

| 主张 | 裁决 | 依据 |
|---|---|---|
| Kimi:exit-2 + 非空 stderr 作为四家共享 Stop 传输 | **接受**,附加 X1 | Codex/Claude 已 live 验证;Kimi/zCode 仍无 live hook 结果 |
| Kimi:`CreateGoal/GetGoal/UpdateGoal/SetGoalBudget` 是模型可调工具 | **接受,并撤回我 round2 的"无法判定"** | 活体工具面 + 二进制默认 agent 工具单 + pinned 源码 |
| Kimi:Claude 布尔随工具调用归零 | **拒绝** | §2 解构点 |
| Kimi:我 §6.1 第 2 行的 Kimi 括注会把 gate 清零 | **接受订正** | Kimi 恒 false 是"无信号",每回合一次由宿主守卫提供 |
| zCode/Kimi:Stop 复测是唯一非模型测量 | **拒绝表述,保留"不请自来"这一半** | §3 |
| zCode R4 / 我 round2 §4.2:gate 不写 `goal_complete`、不 disarm | **共同结论,维持** | `[x]` 与 mtime 都是模型可控信号 |
| Codex:验证改为回合内普通工具 | **接受为主通道** | 评估器只读 transcript |

## 6 未决 · 条件置信 · 最小验收

**决定性残余不确定性有两条,不是一条**:(a) 原生完成/评估路径与 Ultra 必需证据缺失或为红时的**优先级**(Claude 同次 Stop 聚合内的先后未证实;zCode `failed_open` 已证实机制但后果未观测);(b) **Kimi/zCode 上共享 exit-2 传输能否到达一个真正注册的 hook** —— zCode 探针在根 CLI 就以 `Unknown option '--settings'` 失败于加载 hook 之前(`local-evidence/host-probes/clean-zcode/result.json`),那是失败的 setup 探针,不是 live hook 结果。

**最小验收运行**(每宿主 1 条用户输入 × 3 个观测,不需要 4×N 矩阵):
1. 装错插件根路径的 hook:确认 X1 守卫下 0 次纠正、无 stderr、回合正常结束。
2. 必需检查确定失败的一次运行:数实际回调次数、exit 2 是否真产生一次纠正、释放时是否没有写下任何成功、原生状态在 Stop 之前/之后各是什么。
3. 同一目标改为真实通过:确认完成声明引用的验证记录标识与当时一致,且原生侧与 Ultra 报告不矛盾;不一致时报告必须报分歧。

**条件置信**:在 X1/X2/X3 写入决策文本的前提下,我对**架构方向**(宿主拥有循环、验证在回合内、Stop 只做不请自来的有界遗漏纠正、gate 永不宣布完成)给高置信 —— 它的每个承重点都有源码或 live 证据,且失效方向是"少一次纠正",不是"假完成"。对**四宿主无人值守实现**给低置信:live 覆盖只有两家的一小段传输路径,Kimi/zCode 注册路径与四家的原生优先级都还是零 live。**不报任何投票式成功率。**

---

*reviewer: claude · round 3 · 新增 X1(实测)与 Claude 状态解构证据;撤回 cron 延后、review 文件缺失判据、main-Codex 未注册归属;拒绝"Stop 是唯一非模型测量"与"布尔随工具归零"*
