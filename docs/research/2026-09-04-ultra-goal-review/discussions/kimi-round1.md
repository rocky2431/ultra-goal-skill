# Ultra Goal 对抗性设计评审 — 第 1 轮(kimi,独立评审)

评审对象:`sources/main`(ultra-goal-skill @ b07e2a8,v2.8.0)与 `sources/adapt`(ultra-goal-adapt @ f15a003,候选 v2.9.0,**未发布**)。本报告只把 adapt 当候选,不当已发布行为。两套测试我都复制到自己的目录后独立跑过:main `pytest tests/ -q` → **302 passed**(与基线声明一致);adapt pinned 快照 → **347 passed**(比 WIP 记录的 332 多,pin 点晚于两轮 WIP 评审的评审区间)。

证据等级标注:【文档】= 厂商官方参考;【二进制】= 本机安装的运行体(strings/控制流);【执行】= 我在自己目录里的隔离复现;【推断】;【未知】。决策性事实全部给到行号或链接。

---

## 0. 结论(先行)

1. **"The gate is the loop" 在机制上不成立,两家快照皆然。** Stop 钩子只能否决"当前 turn 的结束",不能启动下一个 turn;且四家宿主对连续 block 都有上限(Claude 8、zCode 3、Kimi 每 turn 1 次、Codex 未见上限)。main 自己的 `stop_hook_active` 守卫让每次链只 block 一次;adapt 移除了守卫、按宿主做了预算,方向正确但引入两个新致命伤和一个未修的泄漏(§3 P1-b/c/d)。**Stop 拦截本身不够——它是刹车,不是马达。**
2. 前半段(面试 → artifact → decisions 记录)是整个设计里最结实的部分,建议原样保留。
3. 我主张的最强方向:**刹车/马达分离** —— gate 只做刹车与取证,循环马达借用宿主原生 `/goal`(或调度器),载荷按宿主塑形,obligation 通道从 Stop-allow 迁到 turn 入口。详见 §5/§6。
4. adapt 的 manifest 分层(共享 hooks.json + claude.json + codex.json + kimi.plugin.json)经我对四家资料独立核对后**基本正确**;但它距可交付还差 §3 列出的三处必修。

---

## 1. 宿主机事实(独立核实,非转述)

### Claude Code 2.1.260(二进制 `/Users/rocky243/.local/share/claude/versions/2.1.260`;[hooks 参考](https://code.claude.com/docs/en/hooks);[goal 文档](https://code.claude.com/docs/en/goal))

- Stop 阻断:`decision: "block"` + `reason`(顶层)或退出码 2;`reason` 必填。【文档】
- **`hookSpecificOutput.additionalContext` 在 Stop 上也会继续对话,并与 block 共享同一个"连续 8 次"上限**:文档原文 "It keeps the conversation going through the same loop protections as decision: block, namely the stop_hook_active input and the 8-consecutive-continuation cap";二进制 Stop 处理把 `hook_additional_context` 消息 `Ce.push(...)` 进同一数组,`if(Ce.length>0) return {blockingErrors:Ce,...}`,调用侧 `qd=go+1; if(qd> Vd) force-end`,其中 `Vd = CLAUDE_CODE_STOP_HOOK_BLOCK_CAP ?? 8`。【文档+二进制】
- `stop_hook_active`:"true when Claude Code is already continuing as a result of a stop hook", cap 到时宿主直接结束 turn。【文档】`Vd>0` 才检查 → 环境变量设 0 等于关闭上限。【二进制,未实测】
- 连续 block 计数 `stopHookBlockingCount` 每个新 turn 归零(下一次用户 turn 重新开始)。【二进制】
- `/goal` = 会话级 prompt 型 Stop hook + 小模型(Haiku)评估器,**评估器自己不执行命令**,只读对话;无进展(连续几 turn 无工具调用)会停循环;idle check-in 每个 goal 至多 3 次;`/goal` 在 resume 各路径恢复。【文档】二进制确认评估器是注册进 sessionHooksRegistry 的 Stop hook,其 "not met" 作为 blockingError 计入同一个 8 次上限。【二进制】
- 插件 manifest 的 `hooks` 字段是**追加**而非替换:二进制 schema 描述原文 "Path to file with additional hooks (in addition to those in hooks/hooks.json, if it exists)";"The standard hooks/hooks.json is loaded automatically, so manifest.hooks should only reference additional hook files"。→ adapt 的 claude.json 拆法在 Claude 上成立。【二进制】
- Stop 的 `hookSpecificOutput.permissionDecision` 在 2.1.260 的归一化里只认 `hookEventName==="PreToolUse"`;Stop 分支只保留 additionalContext。main 的 `_deny` docstring 称"官方参考列出 Stop 的 permissionDecision"——以今天的参考页为准,该说法已过时(实际生效的是顶层 decision:block,功能无碍,理由失真)。【二进制+文档】

### Codex 0.150.1(源码 `/Users/rocky243/Context Engineering/codex` @ 03861e69)

- Stop 输出 wire:`#[serde(deny_unknown_fields)]`,只允许 `continue / decision / reason / stopReason / suppressOutput / systemMessage`(hooks/src/schema.rs:452-464;生成的 schema 同)。**任何含 `hookSpecificOutput` 的 Stop 输出都会反序列化失败** → `parse_json` 返回 None → `Failed`("hook returned invalid stop hook JSON output"),不是 Blocked(output_parser.rs:345-358,stop.rs:326-341)。【源码+执行,见 §3 P1-b】
- block 后:reason 作为消息写回并 `continue`,`stop_hook_active = true`(core/src/session/turn.rs:507-545)。**全树未见连续 block 上限**;schema 里 `stop_hook_active` 为必填布尔。adapt 的 `HostFacts(None, …)` + UNVERIFIED 标注是诚实的写法。【源码】
- 事件清单:SessionStart、UserPromptSubmit、PreToolUse、PermissionRequest、PostToolUse、PreCompact、PostCompact、SubagentStart/Stop、Stop、Interrupt、SessionEnd —— **无 PostToolUseFailure**(schema/generated 目录枚举可证)。adapt 不给 Codex 注册它是正确的。
- SessionStart 输出允许 `hookSpecificOutput.{hookEventName, additionalContext}`(schema.rs:395-403)→ adapt/main 的 SessionStart 注入载荷在 Codex 合法。
- `/goal` 以扩展存在(codex-rs/ext/goal:accounting/budget/steering/runtime),按 turn/token/墙钟记账。【源码】

### Kimi 0.40.1(二进制 `/Users/rocky243/.kimi-code/bin/kimi`;官方 hooks 文档中文版,与 [英文站](https://moonshotai.github.io/kimi-code/en/customization/hooks) 同内容)

- 20 个事件;**只有 PreToolUse、Stop、UserPromptSubmit 可阻断**,其余"即发即忘,不管脚本返回什么,主流程都不会改变"。【文档】二进制的 `triggerBlock` 调用点确实只有 PreToolUse/Stop 两处(+UserPromptSubmit 的 block 处理)。【二进制】
- **Stop 每 turn 至多触发一次阻断**:`runStepLoop` 局部变量 `stopHookContinuationUsed=false`,阻断后置 true;turn 结束即重置(每 turn 重新进 runStepLoop)。阻断时 `stopBlock.reason` 以 `system_trigger/stop_hook` 用户消息注入上下文。【二进制;kimi-turn.ts:808-963】
- Stop 输入字段:源码写 `inputData:{ stopHookActive: stopHookContinuationUsed }`,但 hook 引擎 stdin 前做 camelCase→snake_case(`toHookInputData`),**线上实际是 `stop_hook_active: false`,恒 false**(因为它只在 `!stopHookContinuationUsed` 成立时传入)。【二进制】这一点 adapt 注释说"camelCase"只对了一半:线上拼写是 snake_case;而"恒 false 所以无信息"是错的——**恒 false 恰好就是"本 turn 的第一次 Stop"的信号**,因为 Kimi 每 turn 至多触发一次。
- Hook JSON 输出 schema 只有 `message` 与 `hookSpecificOutput.{message, permissionDecision, permissionDecisionReason}`(looseObject,未知字段被忽略)。**`systemMessage` 和 `additionalContext` 在 Kimi 上无人读**;阻断语义 = 退出码 2(stderr 为理由)或 `permissionDecision:"deny"`(+permissionDecisionReason)。【二进制 init_runner】→ adapt 的 `_deny` 双通道载荷在 Kimi 有效;`_allow` 的 systemMessage/additionalContext 全部落空(与 Claude 评审 F-1 一致,我独立核实)。
- UserPromptSubmit:**仅 `origin.kind === "user"` 触发**(`applyUserPromptHook` 首行即返回)。纯 stdout 文本会附加到上下文(`userPromptHookMessage` 先取 message、回退 stdout)。阻断则本轮不调用模型。【二进制;文档】→ **/goal 驱动的 continuation turn(origin 是 `system_trigger/goal_continuation`)不会触发它。**
- SessionStart(startup/resume)观察型;PreCompact"返回值被完全忽略";PostCompact 观察型。【文档】
- `/goal` 存在:`/goal [status|pause|resume|cancel|replace] | <objective>`;goal driver 在每 turn 结束后决定是否再跑一个 turn;**完成由模型 `UpdateGoal('complete')` 自报**,加 token/turn/墙钟预算(急停)。【文档;goal/index.ts】
- 插件:`kimi.plugin.json` 的 `hooks` 数组被读取,cwd=插件根,env 注入 `KIMI_PLUGIN_ROOT`(`enabledHooks`);commands **只展开 `$ARGUMENTS`**(`expandCommandArguments`:无占位符时追加 `ARGUMENTS: <args>` 尾行),`$1` 不展开;`context: fork`、`agent`、`allowed-tools` 等 Claude 字段 Kimi 不解释(其二进制自带 import-from-cc-codex 技能的警告清单原文列出 `context: fork`)。【二进制】
- hook 超时:文档 1–600 秒,默认 30;二进制默认 30。超时 SIGTERM→100ms 后 SIGKILL。【文档+二进制】

### zCode 0.16.5([官方 hooks 文档](https://zcode.z.ai/en/docs/hooks);二进制 `/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs` 抽查)

- Stop:`decision:"block"` + reason(或退出码 2);"returning block lets the main-model loop continue, **at most 3 times in a row**"——原文确认上限 3。Stop 输入列出 `stop_hook_active` 但**未给语义**(adapt 的 HostFacts 注释准确)。【文档】
- 事件只有 SessionStart/UserPromptSubmit/PreToolUse/PermissionRequest/PostToolUse/PostToolUseFailure/Stop —— **无 PreCompact/PostCompact**;SessionStart 的 source 含 `compact`(压缩恢复走 SessionStart)。adapt 把 PreCompact 拆出共享文件是对的。
- UserPromptSubmit 可阻断(`continue:false`)可注入(additionalContext);未知字段被忽略;**非 JSON stdout 永不进模型上下文**。【文档】
- **项目级 hooks 当前版本整体不执行**;只有用户配置与插件两条路。插件标准位置 `hooks/hooks.json` 自动发现,manifest 的 `hooks` 字段可追加其它文件(不要重复指向标准文件);`ZCODE_PLUGIN_ROOT` 等四个变量注入 hook 进程,另注入 `CLAUDE_PLUGIN_ROOT` 兼容变量。【文档】→ adapt 的 `${ZCODE_PLUGIN_ROOT:+--host zcode}` 判别成立(对 `type:"command"` 走 shell 的情形;`process` 类型 argv 直传不展开——当前条目是 command,无碍)。
- `/goal` 存在:二进制含 `"/goal [pause|resume|clear|replace <objective>|<objective>]"`;`--target` 未独立验证。【二进制】
- zCode `/goal` 的完成验证器在输出非 JSON / 请求失败时判 `passed: true`("The completion verifier did not return valid JSON.")——宿主评估器朝"完成"方向 fail-open(/tmp/ultra-goal-research.j8qCAJ/zcode-verifier-result.jsonl 的隔离执行)。【执行】→ 宿主评估器不能当完成权威,这一点四家都成立(Claude 用小模型读对话、Kimi 自报、zCode fail-open、Codex 由扩展记账+模型)。

---

## 2. 中心问题:Stop 拦截到底够不够?

**不够,而且差的是两件不同的事:**

1. **刹车行程有上限。** Stop 只能否决"当前这次结束"。连续否决上限:Claude 8(可env调,0=不限)、zCode 3、Kimi 每 turn 1 次、Codex 未见上限(源码)。到了上限,宿主强制结束 turn。
2. **Stop 永远启动不了下一个 turn。** turn 结束后(放行、预算耗尽、强制结束),会话 idle;再启动只能靠:宿主 `/goal` 的驱动器/评估器、`/loop`/cron 调度、或主人再按一次回车。

main 的 `goal-run.md` 与 SKILL.md:376 宣称"Stop hook 做第一件事(反复提示)做得更好……host goal mode 不能做的恰是唯一重要的事:武装 gate"。但 main 自己的守卫(adapt 之前的 `run_hook`:`if event.get("stop_hook_active"): return 0`,main goal_hooks.py:142-143)让红 anchor 时每条链只 block **一次**——`ceiling: 40` 靠 gate 本身永远走不到,"owner 走开后自动跑 40 轮"在四个宿主上都不发生。这是使命 §4.1 的判断,我用 main 快照独立复现:第一个 stop 放行并带 obligation,之后 `stop_hook_active=true` 的 stop 全部静默 exit 0,`anchor_checked` 永远只有 1 条(执行:临时 fixture + 三连 stop,事件数=1)。

**结论:gate 是刹车与黑匣子;马达必须是宿主自己的 `/goal`(四家都有)、`/loop`、调度器或主人。** 这同时改变了设计叙事:不是"goal mode 是 convenience",而是"goal mode 是马达,gate 让它不敢撒谎"。

---

## 3. 最强缺陷(已证实优先;每条注明证据)

### P1-a【执行+文档+二进制|main 与 adapt 共有的设计错误】“gate 即循环”不成立
如上节。main 因守卫只能"点一下头"(每链一次 block/一次额外 pass);即便没有守卫,上限也在 8/3/1。**这不是参数问题,是 Stop 语义的上限。**

### P1-b【执行|adapt 候选引入,Codex 上 gate 全灭】
adapt 的 `_deny` 发 `{decision, reason, hookSpecificOutput:{...}}`,`_allow` 带 context 时也含 `hookSpecificOutput`。Codex 的 `StopCommandOutputWire` 是 `deny_unknown_fields` 且无 `hookSpecificOutput` 字段(schema.rs:452-464)。隔离执行(用 Codex 自己生成的 schema 校验):

```
deny            -> REJECTED: Additional properties are not allowed ('hookSpecificOutput' was unexpected)
allow+context   -> REJECTED: 同上
allow plain     -> VALID
```

后果:Codex 上 gate **永远无法 block**(parse 失败→Failed→fail-open 放行),带 obligation 的 allow 连 systemMessage 一起丢。而 Codex 恰恰是唯一"无连续 block 上限"的宿主——最值得 gate 长住的地方死透了。修复零成本:--host 已存在,把**输出塑形**也挂上去:codex 只发 `{decision, reason}` / `{systemMessage}`。(main 不给 Codex 注册 hooks,所以这是候选缺陷,不是线上缺陷。)adapt 自己的 347 个测试没有这一条——缺"载荷对每家宿主输出 schema 的 pin 测试",Codex 的 schema 文件就在它仓库里,可直接 vendored 进来当 fixtures。

### P1-c【文档+二进制+执行|adapt 候选引入,Claude 上 allow 路径软循环】
Claude 语义(§1):Stop 的 `additionalContext` 会**继续对话**并计入 8 次连续上限。`_obligation()` 只在"无 carry-over 子节且无未勾 acceptance"时返回 None——而规范要求 `### Next` 恒存在,所以**每个 cadenced run 的每次 allow 都带 context**。adapt 移除了 `stop_hook_active` 守卫,且预算只套在 block 上:

执行复现(adapt pinned 快照,绿 anchor,模拟 Claude 的 stop_hook_active 序列):

```
turn1(fresh):                allow, keys=[hookSpecificOutput, systemMessage]   ← Claude 会继续对话
turn2(stop_hook_active=true): allow, 又带 additionalContext, anchor 又跑了一次
turn3(stop_hook_active=true): 同上
anchor_checked 事件 = 3 条(每软续一次就重跑一次 anchor)
```

链条:allow+obligation → Claude 续跑 → 再 Stop(计入连续次数)→ gate 重跑 anchor → 又 allow+obligation → …… 直到宿主第 9 次强制结束并打印 "A hook blocked the turn from ending N consecutive times — overriding and ending turn"。**绿灯 turn、到顶 turn、停滞 turn、unknown turn 全都中招**:anchor 被重跑至多 8 次(owner 的真实 anchor 预算是 540 秒),`anchor_checked` 计数膨胀约 8 倍(天花板记账被污染),而且最后一句话是宿主的警告而不是 gate 的理由——正是 continuation-budget 设计要消除的结局。**main 因守卫恰好收敛**(放行=多一次模型 pass 再结束,anchor 不重跑),所以这是 adapt 相对 main 的回归;但 main 文档里"八步七放"在 Claude 上从不成立——带 obligation 的 allow 从来不是"让 turn 结束"。
修复:allow 路径**永不附加模型可见内容**(只发 systemMessage 给主人);obligation 迁到下一 turn 的入口(SessionStart 注入 / 下一次 block 的 reason / Kimi 的 UserPromptSubmit 一行)。这同时治愈 main 的"每次 allow 白送一次模型 pass"。

### P1-d【执行|adapt 候选在 pinned 快照仍未修】Kimi 预算跨 turn 泄漏
`_block_streak`(adapt goal_stop.py:436-469)从持久事件日志尾部数连续 block,断链条件是 `prompt_submitted` 事件或 allow。但 Kimi 的 UserPromptSubmit **只在 user 起源触发**(§1),/goal 驱动的 continuation turn 不写 `prompt_submitted`。于是在 Kimi+/goal 驱动下:turn N 红→block;turn N+1 streak=1≥budget=1→`continuation_budget_spent`(本身是断链者)→turn N+2 又 block……交替。独立复现(pinned 快照 harness,三个无 user prompt 的 Kimi turn):`decisions=['block', None, 'block']`,第二条被标成 "budget spent" 而该 turn 一次 block 都没花。**现象与 WIP 里 Codex 的 F2 一致,我在 pinned 快照上确认未修。**
根因:用自己的持久日志反推宿主 turn 边界——可 Host 明明每次都在 input 里告诉了事实。修复:kimi 的 `chain_flag` 设为 `"stop_hook_active"`(线上恒 false ⇒ 每次 Stop 都是新链 ⇒ 每 turn 恰好 block 一次,与宿主能力精确对齐),删掉 `prompt_submitted` 的预算职责(保留它作为 Kimi 唯一的"放行通道":下一条 user prompt 携带上一次裁决)。`goal_prompt_submit.py` 本身是对的设计(固定尺寸一行),只是不该兼任 turn 边界传感器。

### P2【执行/源码|main 线上缺陷群】
1. **reviewer 看的是空 diff**:review/critic 用 `git -C . diff HEAD`(main skills/review/SKILL.md:20、critic/SKILL.md:20),而 run 每 turn 提交——验收时 reviewer 几乎什么都看不到,却能诚实地报"no findings"(使命 §4.2)。adapt 已修:arm 时 write-once 记录 `.goals/<slug>.baseline`,review/critic 读 `git diff <baseline>` + `status --porcelain`,`none` 显式分支 + `merge-base --is-ancestor` 检查。我在 pinned 快照核对了 diff,修复成立(Codex F4 的两条子缺陷在 pin 点已闭合)。
2. **Kimi 上 goal-run 不可用**:命令体用 `$1`(main goal-run.md:7,17,27,36),Kimi 只展开 `$ARGUMENTS`;`${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}` 在 Kimi 的命令路径里没有来源。adapt 已改 `$ARGUMENTS` 并对 validator 不可达声明性降级(else 分支明说"未经机器校验"),方向正确。
3. **main 对 Kimi 的事实层自相矛盾且陈旧**:installer 注释"Kimi exposes only SessionStart and PostCompact (and in TOML)"(install_user.py:32-34)量的是旧 Python kimi-cli;但同一版本的 kimi.plugin.json 又声明了 Stop/SessionStart/PreCompact/PostToolUseFailure 四个事件——在新 Kimi 0.40.1 上这些**会被加载**(enabledHooks 读 manifest.hooks),其中 SessionStart 是观察型死注册、PreCompact 返回值被完全忽略。一个说"没有"、一个注册了四个,两处矛盾。
4. **超时三处不一致**:main hooks.json Stop timeout=600 且被测试 pin 住 `HOOK_TIMEOUT_SECONDS=600`;但 kimi.plugin.json:24 是 **200**(< ANCHOR_BUDGET_CEILING 570 → 长 anchor 在 Kimi 上被宿主杀掉,永久 unknown);install_user.py:42 `HOOK_TIMEOUTS={"Stop":200}` 也没改——注释里写明"200 是我拍脑袋选的、是缺陷",但只修了 manifest 没修 installer。adapt 把两处都改成了 600(pinned 快照已核)。
5. installer 的 kimi 技能目录是 `~/.kimi/skills`(install_user.py:63)——旧 host 的路径;新 host 用 `~/.kimi-code`,插件应走插件管理器(kimi.plugin.json 格式本身就是新 host 的)。两个目录本机都在,但新 Kimi 只读后者。
6. installer 的 SessionStart matcher `^(startup|resume|clear|compact)$` 比 hooks.json 少一个 `fork`;且 installer 不注册 PostToolUseFailure(installer 只装 3 个事件,插件装 4 个)。小问题,两条安装路径行为不同。

### P2【二进制|设计层面的宿主可移植性】审查隔离是 Claude 私有机制
review/critic/design-critic 靠 `context: fork` 获得"从未见过作者论证"的隔离。Kimi 不解释该字段(其二进制自带导入技能的警告清单原文包含 `context: fork`);zCode/Codex 的 skill frontmatter 对该键的支持未证实。**SKILL.md 说"isolation 是文件的属性"只在 Claude 成立。** 在其它三家,等价物是 subagent/agent-delegate(新进程、新上下文),SKILL.md 的角色表应该按宿主给出隔离路径,而不是把 fork 说成普遍机制。否则在 Kimi 上 `/ultra-goal:review` 就在 run 自己的上下文里跑——正是该设计要防的传染。

### P3【候选自带 UNVERIFIED,我复核后同意】
Codex 无上限 = 源码未见 + 文档未提,不等于没有;若存在隐藏上限,宿主 force-end 兜底。zCode 的 3 只有文档(无二进制佐证,本机 zcode.cjs 未深查 cap 实现)。Kimi "每 turn 一次" 是二进制控制流,未在活的 /goal run 里观察。

### 设计判断(明确标注为非事实)
- **J1**:adapt 的 `_block_streak`/`prompt_submitted` 机制是从自己的日志重建宿主状态——滑向"脆弱工作流引擎"的第一步,违反自家准则"mechanise only when the measured quantity IS the judged quantity"(mission §1.8)。turn 边界只能由宿主亲口说(chain_flag)或不测。
- **J2(灵活性天花板)**:后半段的任务选择被有意做成"恒温器而非调度器":`### Next` 恰好一个目标、无任务账本、## Roles 在设计时钉死(运行时改派只有 fallback 链 + decisions.md 行)。owner 任务书说后半段"选择任务、选择谁做"——当前设计**有意拒绝**这件事(graph-topology.md 反对 Stop hook 变 sequencer)。这不是 bug,是产品分歧点,第三轮前需要 owner 明示:要恒温器,还是要带账本的分派器。
- **J3**:main 的 `_deny` docstring 里"两源冲突就都发"的策略在 Codex 面前是错的——双发只在"未知字段被忽略"的宿主上安全;Codex 是 deny_unknown_fields。**正确抽象不是"都发",是"按宿主塑形"**(adapt 已有 --host,只差输出侧)。

---

## 4. adapt 候选总评

- **采纳方向**:去守卫 + 每宿主预算 + "宿主上限是 backstop 不是预算" + 一 check 一 turn;manifest 分层(claude.json 追加 PreCompact、codex.json 替换式、共享文件只装两家共有事件、Kimi 去掉 SessionStart 加 UserPromptSubmit);`$ARGUMENTS`;write-once baseline;stagnation 双快照(tree_before 对上次 tree_after,排除了 anchor 自己的脚印——我把 Codex F3 的两个复现都在 pinned 快照上重跑:变异 anchor 不再骗过停滞检测,未跟踪文件内容编辑也能看见;>1MiB 未跟踪文件的尾部编辑不可见是代码里点名的边界)。
- **必修三处**:P1-b(Codex 载荷)、P1-c(Claude allow 软循环)、P1-d(Kimi 泄漏)。前两个是"修了A宿主、弄死B宿主"型的移植缺陷,根因相同:预算按宿主分,**载荷没有按宿主分**。
- **证据纪律**:WIP 两份评审各有撤回项(Claude 撤 F-2/F-3/F-7,Codex 的 F1/F3/F4/F6 在 pin 点已修),两边剩下的真发现与我独立复现一致。我没有把任何候选行为当成已发布行为。
- **测试缺口**:载荷↔各宿主输出 schema 的 pin 测试(Codex 的生成 schema 可直接 vendored);"allow 不带模型可见内容"的契约测试;Kimi 恒 false `stop_hook_active` 的 fixture 测试。

---

## 5. 建议的 allow / block / continue / complete 决策

**Block(否决 turn 结束)——同时满足才成立:**
anchor 可运行且本次为红;且工作树或输出有移动(非停滞);且未达 ceiling;且 frozen digest 未变;且本宿主连续 block 预算未耗尽(claude 7 / zcode 2 / kimi 1 / codex 不设、未知宿主 1)。block 的 reason 携带:轮次(gate 计数)、写一条 `### Lessons` 的义务、以及(单 block 宿主)停靠与提交指令。阻塞是唯一"continue"。

**Allow(结束 turn)——其余一切,且分两种声道:**
- 对**主人**:systemMessage(或 Kimi 上等下一条 user prompt 的一行)说明为什么结束:绿/unknown/到顶/停滞/预算耗尽/frozen 变动/无 anchor。
- 对**模型**:什么都不说。**Stop-allow 不携带任何模型可见内容**(Claude 会因此续跑并计入上限;Kimi 会丢弃;zCode 未证实)。obligation(改写 carry-over、剩余 acceptance 计数)迁到 turn 入口:SessionStart 注入(Claude/zCode/Codex)、下一次 block 的 reason、Kimi 的 UserPromptSubmit 固定行。理由:turn 末尾的提醒本来就到不了"下一个上下文"——它只教育即将被丢掉的上下文;入口注入才教育新 turn。

**Complete:** gate 永不宣布完成(现设计正确,保持)。完成 = stop condition 文本满足 + anchor 绿 + acceptance 无未勾 + review/critic 咨询性结论 + 主人可见的提议;`## Acceptance` 的 `[x]` 只是声明,anchor 输出才是证据。

**马达(新增,goal-run.md 按宿主输出):**
- Kimi:必须用宿主 `/goal` 包裹 handoff 文本(或主人手动续 prompt);文本里写"不要 UpdateGoal('complete'),直到 anchor 绿";用 SetGoalBudget 给硬上限。gate 每 turn 至多一次否决作为刹车。
- Claude:无人值守用 `/goal <条件,条件里点名 anchor 命令与其输出>`;gate 与其共享每 turn 8 次上限(评估器的 not-met 也是 block),需要在文档里明说"同一预算两个消费者"。
- zCode:`/goal` 同理;上限 3;zCode 评估器 fail-open(§1)更要靠 gate 的锚。
- Codex:gate 单独即可在一个 turn 内无限自持(无上限),跨 turn 仍需 `/goal` 或主人;先修 P1-b 否则免谈。
- 任何一家:`rm .goals/active` 永远是 escape hatch(保持)。

---

## 6. 最小可行架构 与 一个有意义的替代

**MVA(我主张):** ① 面试 + artifact 对 + decisions 记录(不动);② `.goals/active` 武装(不动);③ Stop = 刹车 + 黑匣子,按 §5 决策表,**输出与预算都按宿主塑形**;④ 马达 = 宿主 `/goal` 或调度器,goal-run.md 负责按宿主打印那条马达命令,不再宣称"不需要 goal mode";⑤ SessionStart/PreCompact/PostToolUseFailure/(Kimi)UserPromptSubmit 按 adapt 的分层注册;⑥ review/critic 在非 Claude 宿主走 subagent 委托获得隔离;⑦ 事件日志与 --audit 不动。全部落在"skill 指令 + 本地脚本 + 原生 hooks + 薄打包"边界内,不引入第二个 runtime。

**替代方案(诚实的另一条路):宿主原生循环,gate 只做证人。** 完全不 block:宿主 `/goal` 全权驱动与判定(条件文本里点名 anchor 并要求贴输出),Stop 钩子只记事件,--audit 事后把"run 的声称"和"gate 的测量"对齐追责。优点是零预算管理、今天就在四家上都能跑、恢复语义全靠宿主;代价是完成权威回到模型手里(zCode 评估器甚至朝"完成" fail-open;Kimi 是自报),红线场景不适用。适用:低风险的看守/提醒型循环。两条路的分界线 = **"红 anchor 能不能机械地否决一次结束"对你这件事值多少钱**。

---

## 7. 灵活性与恢复(我的主攻角度)

- **Init/Research 进入**:意图识别表 + "workflows 目录非空先跑 status" 是对的;"Executing" 防误激活目前只有指令层(SKILL.md 自认 UserPromptSubmit 精确匹配探测器未建,触发条件已写明)——可接受,但该探测器的建造触发条件应该被记录为已知风险而不是脚注。
- **理解变更**:Challenges 通道(run 写、owner 裁)+ Modify 流程 + frozen digest 三件套自洽;"改 anchor/ intent 就是另一个 loop,重新面试"这条边界画得对。
- **自发任务/代理指派**:运行时没有机制,只有 fallback 与 droppable means——见 J2。若保持恒温器定位,建议在 SKILL.md 明说"任务分派发生在面试,不在运行中",免得使用者按任务书的字面期待。
- **语义模型自主权**:wide latitude + zero trust in self-report 是全书最强的一组对偶论证,保留。
- **结果整合**:events.jsonl(hook 写)+ --audit(join 声称与测量)成立;adapt 的 `blocked` 字段与 `continuation_budget_spent` 事件与"一 check 一 turn"的 join 键兼容(turn=check 数)。
- **compaction/resume**:Claude/zCode/Codex 有 SessionStart 注入(zCode 的 compact 走 SessionStart source;Codex 注入字段合法已核)。**Kimi 有真实缺口**:SessionStart 观察型、PreCompact 返回值完全被忽略、UserPromptSubmit 又不在 goal-continuation turn 触发——/goal 驱动下压缩后的 Kimi run 永远收不到任何重置信号,只剩宿主自己的 /goal reminder。缓解:handoff 文本让 `/goal` 目标本身携带"先读 Carry-over 再动手"(Kimi 每 turn `injectGoal`),把重锚定交给宿主马达的提示词而不是钩子。
- **会不会变成第二个 runtime**:目前没有;危险斜坡只有一处——从日志反推宿主 turn 边界(P1-d 的机制)。守住"只机械化宿主亲口说的或直接可测的"这条线即可。

---

## 8. 信心与未证实

- **高置信(文档+二进制+执行三重一致)**:Claude 连续上限 8 与 `additionalContext` 续跑语义;Kimi 每 turn 一次阻断、输出 schema、`$ARGUMENTS`-only、UserPromptSubmit 仅 user 起源;Codex `deny_unknown_fields` 拒绝 adapt 载荷(隔离执行通过其官方生成 schema)。
- **中置信(单一来源)**:zCode 上限 3(仅文档);Codex 无上限(源码未见≠没有);Kimi 恒 false 的 `stop_hook_active` 可用于断链(二进制控制流,未在活会话观察)。
- **未证实(任何一方都没做)**:四家都没有一次真实的无人值守全程跑;"宿主 /goal + gate"组合无死锁(共享上限、双评估者抢收尾)只有纸面分析;`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP=0` 关闭上限是二进制分支推断;zCode 上 additionalContext@Stop 是否续跑未知。
- 我不因多方一致而报数字成功率:两家 WIP 评审 + 我本 round 的一致点全部来自**同一份静态证据**,缺的那个证据(活跑)一次都还没产生。

## 9. 能否定本报告的对抗性用例

1. 活跑 Claude:若 Stop 的 `additionalContext` 实际**不**续跑(文档与二进制同时错),P1-c 崩塌,obligation 留在 allow 里也可行。
2. 活跑 Codex:若运行时容忍 `hookSpecificOutput@Stop`(运行时与生成的 schema 不一致),P1-b 崩塌,双发策略反而对。
3. 活跑 Kimi:若 goal-continuation turn 也触发 UserPromptSubmit(我对 origin 检查的理解错了),P1-d 的根因错——但交替现象已在 pinned 快照复现,仍需修。
4. 组合死锁实验:Claude 上 /goal 评估器与 ultra-goal 共享 8 次上限,anchor 已绿但评估器说"未满足"时谁收尾——若实测出现互相续跑/抢结束,§5 的马达组合表要重写。
5. 若 owner 第三轮明示"运行时需要多任务分派/账本",J2 的恒温器辩护失效,需要 graph/账本层——那正是 graph-topology.md 拒绝的方向,产品定义本身将被迫改。
6. Kimi 若在某条路径(如子代理 Stop)把 `stop_hook_active` 置 true,我的 chain_flag 修复会过度放行——需要一个"subagent Stop 是否也走 runStepLoop"的核实。

## 10. 最重要的未解决分歧

**gate 该不该继续扮演"循环的马达"。** adapt 的方向是加码(每宿主预算表、从日志数连续 block、用 prompt 事件断链);我的方向是解耦(刹车归刹车、马达归宿主 `/goal`,gate 永不宣称自己能驱动多 turn)。双方共享同一个证据缺口:没有一家做过真实的全程无人值守跑。可检验的裁决实验:同一 artifact(红两次后转绿、中途一次压缩)在四宿主各跑一次,数 `anchor_checked` 直到 run 真的停——这一步在任何一方的测试套件里都还不存在。
