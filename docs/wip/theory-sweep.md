# 理论扫描:四家的长任务工程实践,与 UltraGoal 的逐条对照

状态:进行中。这份文档在"是否进入实践"这个决定做完、且下面的待决项清空后删除,
把留得住的内容折进 `references/`。

扫描日期 2026-09-04。所有引文与链接当天核过一次;数字会过期,重看时先核。

---

## 一、四家在说什么

### Anthropic —— 两篇正面主题的文章,之前一次都没引过

这是本次扫描最重要的发现:我们做的这件事,Anthropic 有两篇正面写它的工程文章。

**《Effective harnesses for long-running agents》**
- 核心问题定义得比我们更准:"finding a way for agents to quickly understand the state
  of work when starting with a fresh context window"。
- **"compaction isn't sufficient"** —— 这是厂商自己的原话,直接支撑我们 `## Carry-over`
  的全部前提。
- 他们的落盘物:`claude-progress.txt`(做过什么的日志)、**`feature_list.json`**
  (结构化需求清单,初始全部标记为 failing)、描述性 git commit、`init.sh`(拉起环境)。
- 纪律:**一次会话只做一个 feature**;"Only mark features as 'passing' after careful
  testing";"It is unacceptable to remove or edit tests"。
- 点名的失效模式与解法:一次想做完整个项目 → feature 清单;提前宣布完成 → 会话开始先
  读清单;进度和 bug 没记录 → 进度笔记 + commit + 基线测试;没测就标完成 → 明确要求
  端到端验证。
- **"Absent explicit prompting, Claude tended to make code changes but would fail to
  recognize that the feature didn't work end-to-end."**
- 浏览器自动化(Puppeteer MCP)让 agent"identify and fix bugs that weren't obvious
  from the code alone";**明确把"只有单测、没有端到端验证"列为反模式**。

**《Harness design for long-running application development》**
- 三 agent:Planner / Generator / Evaluator。**Generator 后来被删掉了** —— 模型变强后
  他们主动移除了一个组件。
- **Sprint contract**:每个 sprint 开工前,generator 和 evaluator **先就"这一块的 done
  长什么样"达成一致,然后才写代码**。
- Evaluator 用 Playwright 真去操作运行中的应用,按结构化判据打分,"if any one fell
  below it, the sprint failed and the generator got detailed feedback"。
- 自评偏宽的原话:"When asked to evaluate work they've produced, agents tend to respond
  by confidently praising the work—even when, to a human observer, the quality is
  obviously mediocre." 而且**分离本身不够**:"the separation doesn't immediately
  eliminate that leniency on its own... But tuning a standalone evaluator to be
  skeptical turns out to be far more tractable."
- **"context anxiety"** —— 一个我们此前完全没有名字的失效模式:模型接近它**自认为**的
  上下文上限时,会开始提前收尾。他们的解法是 context reset + 结构化 handoff;并指出
  "compaction preserves continuity, it doesn't give the agent a clean slate, which
  means context anxiety can still persist"。
- 本次扫描最好用的一句框架句:**"every component in a harness encodes an assumption
  about what the model can't do on its own, and those assumptions are worth stress
  testing."**
- 以及 "find the simplest solution possible, and only increase complexity when needed"。

链接:
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- https://www.anthropic.com/engineering/harness-design-long-running-apps
- https://www.anthropic.com/engineering/managed-agents (decoupling brain from hands)

### Google —— 模式即规格,以及一套跨 agent 的状态词汇

- **Teamwork**(已引):"A pattern is a specification rather than an executable program.
  It contains no orchestration code of its own." 五种 pattern 按任务自动选择;里程碑
  必须通过独立验证才能推进;Critic 做独立 review。
  https://antigravity.google/blog/teamwork-when-ai-becomes-a-research-partner
- **A2A 协议**(新):Agent Card 声明能力/地址/鉴权;**task 生命周期是命名状态机**:
  `submitted / working / input-required / completed / failed / canceled / rejected`;
  长任务用 SSE 推状态。A2A 与 MCP 分工:A2A 管 agent 之间,MCP 管 agent 到工具。
  https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/
- **能拿的是状态词汇,不是那套栈。**HTTP + SSE + JSON-RPC 服务端与我们"文本协议、零编排
  代码"的取向完全相反。但 `input-required` 和 `rejected` 这两个状态,我们的
  delegation 里确实没有。

### OpenAI —— 护栏分层与两个升级触发条件

- 《A practical guide to building agents》:护栏是**分层防御**,"set up guardrails that
  address risks you've already identified for your use case and layer in additional
  ones as you uncover new vulnerabilities";类型包括 relevance / safety / PII。
- 编排两类:manager pattern(中心编排器派给专家)与 decentralized(agent 直接交接控制权)。
- **人类介入的两个触发条件**,第一个正是我们的轮次上限:**exceeding failure thresholds
  (set limits on agent retries or actions)**,以及高风险动作。
- 并且明确建议**增量推进**而不是一上来就建一个完全自主的复杂架构。
  https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf

### Cognition —— 反方,但它反的不是我们这一种

- 《Don't Build Multi-Agents》:naive 的 fan-out 里,每个 subagent 只看到任务的一部分,
  各自对风格、边界情况、解释做出隐含决定,**而这些决定互相冲突**;上下文无法充分共享。
- 但它给出的正面原则恰好**背书我们的三角**:**"extra agents are fine when they
  contribute intelligence, reading and analyzing, but the writes, the actions that
  change state, should stay single-threaded."**(即 Single Writer 原则)
- 我们的 M/R/C 正是这个形状:只有 M 编辑制品,R 和 C 只读、只产出评审。所以 Cognition
  反对的是我们**已经用 refusal 表拒掉**的那种按领域切分的 fan-out。
  https://cognition.com/blog/dont-build-multi-agents

### Manus —— 三条与我们第三部分几乎一一对应的实践

- **Recitation**:反复重写 `todo.md`,把全局计划"背诵"进上下文**末端**,推进模型最近的
  注意力窗口。一个典型任务约 50 次工具调用,长上下文里极易漂移。
- **文件系统即终极上下文**:无限、持久、agent 可直接操作;压缩要可恢复(丢网页正文但
  留 URL)。
- **把错误留在上下文里**:藏掉错误会让模型学不到东西;失败动作和 stack trace 是关键
  学习信号。
  https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus

---

## 二、长任务的数学(这一块是硬的)

- **Toby Ord,《Is there a half-life for the success rates of AI agents?》**
  (arXiv 2505.05115):agent 在长任务上的成功率可以用一个极简模型解释 ——
  **人类每分钟工作量上的恒定失败率(constant hazard rate)**,于是成功率随任务长度
  **指数衰减**,每个 agent 有自己的"半衰期"。机制解释:长任务"involve increasingly
  large sets of subtasks where failing any one fails the task"。
- **METR 时间视界**:当前前沿模型在人类耗时约 4 分钟以内的任务上接近 100% 成功,而在
  人类耗时超过约 4 小时的任务上成功率低于 10%;50% 可靠度对应的任务长度约每 7 个月
  翻倍(TH1.1 修正为 2023 年后约 131 天)。
  https://metr.org/blog/2026-1-29-time-horizon-1-1/

**对我们的直接推论(这是本次扫描里最可操作的一条):**

如果失败率对时间近似恒定,那么**成功率对"每轮的工作量"是指数关系**。所以把每轮的活切
一半,green 的概率**不止翻倍**。而我们的访谈里从来没有一个问题问过"一轮的活有多大"——
只问了停止条件和轮次上限。按这个数学,**每轮工作量才是决定这个 loop 能不能跑通的变量**,
上限只决定它什么时候放弃。

而 anchor + 轮次结构的理论价值也由此说清:它把一次指数衰减的长尝试,换成一串各自落在
可靠区间内的短尝试。这是我们此前只有定性说法的地方。

---

## 三、逐条对照:验证了什么、冲突在哪、缺什么

### 被外部证据验证的(不用改)

| 我们的设计 | 支撑 |
|---|---|
| `## Carry-over` 存在的理由 | Anthropic 原话 "compaction isn't sufficient" |
| 生成者不能自评 | Anthropic:分离不够,但"调一个怀疑的独立 evaluator 更可解" |
| 只有 M 写、R/C 只读 | Cognition 的 Single Writer 原则 |
| 拒绝按领域切分的 fan-out | Cognition 对 naive fan-out 的整段论证 |
| 轮次上限 | OpenAI 的第一个人类介入触发条件(failure thresholds) |
| 制品放项目内文件、不放工具私有目录 | Manus"文件系统即终极上下文" |
| 纯文本协议、不写编排代码 | Teamwork"pattern is a specification, not a program" |
| 先简单、被证明不足才加机制 | Anthropic 与 OpenAI 都明确这么说;Anthropic 还真删掉了一个 agent |

### 冲突,需要裁决

**冲突 1:`feature_list.json` vs 我们拒绝的 task ledger。**
我在 `document-system.md` 里明写拒绝 `tasks.json` 和 `plan.md`,理由是"台账是作者时的
分解,那使它成为 graph;loop 的定义是推理时决定下一步"。而 Anthropic 的长任务 harness
把 `feature_list.json` 当作"一次想做完整个项目"和"提前宣布完成"这两个失效的**主要解法**。

我的理由是否仍然成立:**部分成立,但我混淆了两样东西。**
- **plan**(有序、有依赖的步骤)是作者时分解 → 拒绝是对的。
- **acceptance checklist**(无序的需求集合,每条带一个可验证的通过状态)**不是 plan**,
  它是**把停止条件列举化**。而它解决的正是我们目前只在"整个目标"粒度上才有防线的那个
  失效:提前宣布完成。
- 所以这不是"要不要台账",而是"**停止条件在跨多次会话的目标上,是否要可列举**"。

**冲突 2:Manus"把错误留在上下文里" vs 我们的 `### Lessons` 上限 3 + "重写不追加"。**
不是真冲突,但边界要说清:Manus 说的是**单次会话内**模型自己的上下文(它应该看到自己
的失败);我们剪的是**跨会话携带的文档**。两个作用域。不过我们从没写下这条区分,
而它会被读成矛盾。

**冲突 3:一次连续会话 + 自动 compaction(Anthropic 最新做法) vs 我们的 context reset
+ 结构化 handoff。**Anthropic 在 Opus 4.6 上**把 context reset 整个删掉了**,因为模型
自己不再有 context anxiety。我们的 SessionStart/PreCompact 走的是 reset 那一路。
这不是错,但要知道:**这两个 hook 赌的是一个可能已经被模型修掉的缺陷。**

### 缺的(按分量排)

1. **每轮验收(per-turn acceptance)。三个独立来源指向同一处。**
   Anthropic harness #1 的"一次一个 feature";harness #2 的 sprint contract("开工前先
   就这一块的 done 达成一致");Ord 的指数衰减数学。我们只有整个目标的 done,没有这一轮
   的 done。
2. **anchor 必须端到端。**Anthropic 明确把"只有单测没有端到端"列为反模式,并有原话说
   模型会改完代码而**认不出功能整体是坏的**。我们的第 2 问只要求 anchor 是"输出不可争辩
   的命令",没有要求它穿过整条路径。一个绿的单测完全可以配一个坏掉的功能。
3. **"context anxiety" 没有名字。**我们的 anchor 门恰好是它的机械解(红了不许收尾),
   `--audit` 的 `CLAIM_CONTRADICTED` 恰好是它的事后证据。但 refusal 表和 anti-patterns
   里都没有这一条,所以这个防御是**碰巧**成立的,不是**设计**成立的。
4. **跨 agent 缺两个状态。**A2A 的 `input-required`(worker 缺东西没法继续)和
   `rejected`(worker 拒接)。我们的 delegation 里 worker 只有"返回"或"没返回"。
5. **`init.sh` 一类的"怎么把这个项目跑起来"。**对熟悉的仓库无所谓,对跨会话进入陌生
   仓库的目标是真缺口。优先级低于上面四条。
6. **"不许删测试/改断言"没有进默认 boundary。**你的 handbook 里有,我们的模板里没有。

---

## 四、硬编码与机械限制:全量清点

判据用 Anthropic 那句:**每一个机械组件都在赌"模型自己做不到某件事",这些赌注值得被
压力测试。**下表就是我们所有的赌注。

### 能阻塞的东西(全部)

| 位置 | 判据 | 测的量 = 判的量? | 能否阻塞 |
|---|---|---|---|
| `goal_stop.py` 唯一的 `_deny` | anchor 退出码非 0 且与上轮签名不同 | **是** | **能**(唯一一处) |
| `frozen_spec_changed` | 三节的 sha256 变了 | **是** | 不能(放行 + 报警) |
| 轮次上限 | 事件计数 > ceiling | **是** | 不能(放行) |
| `validate_artifact.py` 退出码 1 | 41 条形状规则 | 形状=形状,**是** | 只影响 CI/人,不阻塞 agent |

### 可疑的常量(赌注,附我的评估)

| 常量 | 值 | 它在赌什么 | 评估 |
|---|---|---|---|
| `ANCHOR_TIMEOUT_SECONDS` | 180(门) / 300(校验器) | 超过这个时长的 anchor 不值得等 | **最该改的一条。**这正是我自己在 `zero-trust.md` 里点名"测的量≠判的量"的那一类;而且两处不一致。后果:一个正常需要 4 分钟的 anchor 对门**永久不可知**。这就是你最初警告我的 zCode 30 秒那个问题的同构。修法现成:让时长由制品声明,而不是常量 |
| `STATE_MAX` | 8 | 携带 8 条以上事实会稀释注意力 | **没有任何引用来源,是我拍的。**且现在是硬失败(exit 1) |
| `LESSONS_MAX` | 3 | 同上 | 有来源(Reflexion Ω=1-3),但那是 2023 年的模型 |
| `DEFAULT_CEILING` | 12 | 业主没写上限时的兜底 | 向宽松失败,可接受;本次已让它**明说自己是默认值** |
| `CONTEXT_LIMIT` | 6000 | 注入超过这个长度不划算 | 本次修掉了它的截断缺陷(见下) |
| `NEXT_NOT_SINGLE` | 恰好 1 条 | 多于一条就变成 plan | 推理得出,未实测 |
| `KNOWN_TARGETS` | 6 个厂商写死 | 不在表里的就是打错了 | 第七个厂商会**硬失败**在 `UNKNOWN_TARGET` |
| `DISAGREEMENT_CLASSES` | 三个字面词 | critic 会照着写这三个词 | **关键词匹配**,同义改写就失败。属于我在别处批评过的那一类 |
| `ROUND_CAP` / `TURNS` | 正则 | 业主会用可解析的写法 | `TURNS` 本次已加宽并加"未声明"标记;`ROUND_CAP` **还是老样子** |

### 41 条校验规则

全部是形状检查,不判语义,不改文件。风险不在单条,在**总量**:goal package 现在有 7 个
必需小节,每一个都在赌"不强制我就不会问那个问题"。这是整套机制里最大的一块赌注,而它
**从来没有被行为 eval 测过**。

---

## 五、本次扫描顺手修掉的两个真缺陷

都是当场跑出来的,不是推测。

1. **`SessionStart` 会在出厂模板上就把注入截断。**实测:注入 6042 字符触顶,**在讲
   "挑战条款"的那句话中间被切断**。一条被切一半的指令仍然读起来像指令,比它不在更糟。
   修法:按恢复所需的优先级**整节注入**(Intent → Boundary → Anchor → Stop → Means →
   Carry-over → Verification → Cadence),**排除 `## Handoff`**(它装的是启动命令,而运行
   已经启动了),放不下的整节丢弃并**列出丢了哪些**。修后 4349 字符,无半句截断。
2. **轮次上限的静默回落。**`TURNS` 只认 `<数字> turn(s)`,所以 "six turns"、
   "6 iterations"、"6-turn ceiling" 全部匹配失败 → **静默按 12 执行**。业主写六轮、门
   按十二轮跑,而这是一个"看起来跟业主自己的数字一模一样"的被挪动的阈值。修法:加宽
   (数字与英文数词 × turn/iteration/round/pass/cycle),并且**解析不出时明说这是门的
   默认值**,同时在事件日志记 `ceiling_source`。
   开发中还抓到一个近失:`pass` + `s?` 匹配不了 `passes`,而它**恰好回落到 12、与正确
   答案相同,把 bug 藏住了**。断言必须查那个 flag,不能只查数字。

---

## 六、刻意不做的

- **A2A 那套栈**(HTTP/SSE/JSON-RPC 服务端)。只取状态词汇。
- **`UserPromptSubmit` hook**。它能精确抓错误激活(比对制品自己的 `## Handoff` 块),
  但指令层修法尚未被证明失效。触发条件已记在 SKILL.md。
- **WikiSkill 的那套机器**(inference agent / wiki maintainer / skill proposer /
  按验证集 gating)。那是训练框架。
- **`plan.md` 与有依赖排序的 `tasks.json`**。这一条不变;可列举的验收清单是另一回事,
  见冲突 1。

---

## 七、本次已落地(v1.3.0)

第三节"缺的"六条,业主 2026-09-04 全部批准,全部已做:

1. **`## Acceptance`** —— 只在带 `## Cadence` 的目标上要求(与 `## Carry-over` 同一条
   判据线,不引入新概念)。无序、每行带 `[ ]`/`[x]` 状态;**编号列表直接拒绝**
   (`ACCEPTANCE_ORDERED`),因为那就是 plan。与台账的边界写死在
   `references/document-system.md` 的专门一节里。
   每轮的验收(sprint contract)折进了 goal 文本原有的"报轮次"那条从句:开工前先说这一轮
   针对哪几行 Acceptance、什么输出能证明它们。
2. **anchor 必须端到端** —— 第 2 问加了要求,`anti-patterns.md` 加了专节。
3. **context anxiety** 进 refusal 表 + 失效对照表 + `anti-patterns.md` 专节,并写明:
   如果模型不再有这个毛病,那两个恢复 hook 就是"防一个已被修掉的缺陷",该删。
4. **anchor 时长由制品声明** —— `## Anchor` 里写 `budget: N minutes`;两处不一致已统一;
   并且发现了一个**此前没被说明的耦合**:`hooks.json` 的 Stop timeout(200s)是所有预算
   的上限,现在 `HOOK_TIMEOUT_SECONDS` 单点声明、有测试钉住它与 manifest 一致,超出上限
   的预算报 advisory。
5. **`STATE_MAX` 降级** —— 为此给 `Finding` 加了 `severity`。判据:**error = 制品按字面
   做不成事;advisory = 这个 skill 对它能做多好的判断。**只有 error 影响退出码。
   `LESSONS_MAX` 留在 error(它有 Reflexion 的来源),`STATE_MAX` 转 advisory(它没有)。
   这个不对称本身也是一个判断,记在这里。
6. **A2A 的两个状态** —— `input-required` 与 `rejected` 进 delegation 契约
   (`WORKER_OUTCOMES_UNDECLARED`),并写明**沉默等于 input-required,永远不等于
   completed**。

## 八、第一次真实运行暴露的,以及 v1.5.0–1.6.0 的处置

一次访谈就跑出四条,三条是制品自己招的。

1. **折行锚让门控变成装饰**(v1.5.0)。`_first_command` 取围栏第一行,于是 `run` + `verify`
   两行只跑了 `run`,断言产品命题的那一半永不执行,门控在「pipeline 跑过了」上变绿。
   修复时复现出更糟的一种:```bash 块以 `set -e` 开头 → 门控跑 `set -e`,退出 0,**报绿而
   什么都没测**。两种自动修法都更糟(跑整块 → 裁决交给最后一行;`&&` 拼 → 悄悄改写作者
   意思),所以**两边都不猜**:门控返回原因、不跑任何东西、放行并说明;`ANCHOR_MULTILINE`
   在作者时就拒。
2. **模式决定从未被做出**(v1.6.0)。记录里只有 "reviewer + critic",**全程没有 target**——
   所以那次复核是独立的还是同模型的第二意见,事后无法分辨。第 6 问现在先自己跑
   `agent-delegate list --json`(事实),再端出四模式 + 三个子决定(在哪跑 / 何时跑 /
   轮次上限),带推荐,由 owner 选。`references/agent-modes.md` 105 行,每个模式都写了
   **买到什么**和**没买到什么**。
3. **「什么时候复核」这个维度是 run 自己发明的**(v1.6.0)。它选了「仅在拟停机时跑一次」,
   理由正确(中间轮次已有锚在管)。第 6 问原本没这一问,现在有了。
4. **`decisions.md` 分不清"你决定的"和"我假设的"**(v1.6.0)。两条 Why 单元格里写了
   「(我的内联假设,owner 未反对)」和「(我直接定死,未作为选项)」来绕过。加了第四列
   `Who`(`owner`/`agent`),`--status` 单独计数 `assumed=N`。**agent 行是正当的、常常是
   必要的;不标记才不正当。**
5. 顺带把审计里那个赌注修了:`KNOWN_TARGETS` 不再硬编码,改为先问
   `agent-delegate list --json`,问不到才回落到常量,且回落时 `UNKNOWN_TARGET` **降为
   advisory**——工具缺席时不该因为名字对不上就判制品不合格。

## 九、第二轮修正:业主指出我把分类学做成了菜单(v2.0.0)

**我的错**:A/B/C/D 四个"模式"并列,把三个正交的轴压进一列——A/B 是"谁审",C 是"扇不扇",
D 是"路由何时决定"。业主直接点出来了。修法不是换名字,是换骨架。

1. **按阶段分职责,并明说哪几段根本不是选择。**四阶段(research → 方案 → 落实 → review)
   套在角色上,得到七个角色,其中**四个是定死的**:lead(访谈不可派发)、carry out
   (主对话自己写)、anchor(机械)、以及 test-first(拆开就是 phase split)。
2. **"不要你自己写代码"这条我顶回去了,带证据。**Anthropic 原话:CC 的 main agent
   自己写代码改文件,subagent 只用于搜索和独立调查,**而 research system 才是 lead 派发**——
   两种模式按任务类型分。更硬的理由:`### Lessons` 和所有死胡同只在主上下文里,派出去等于
   每轮从第 1 轮重来。**"裁判+教练+运动员"的担心是真的,但解法是判定权不在写的人手上,
   而 anchor 退出码早就不经过任何模型了。**
3. **两个复核轴分开,因为它们治不同的病。**fresh context 治**说辞传染**(不可选);
   跨厂商治**盲区共享**(可选,10x)。同模型 subagent 不是跨厂商的廉价替代品——它把第一种
   病治干净,第二种一点没治。
4. **"何时复核 / 轮次上限"降级为参数**,不再是并列的第二第三个问题。
5. **loop vs graph 移出这一页**——它是"路由何时决定",属于第 7 问。把它放进角色选项列表
   是原来那个错误最明显的症状。
6. **声明式降级**:每个角色写 `fallback:`,`fallback: none` 是正当答案(意思是停而不降级),
   沉默不是。`ROLE_FALLBACK_MISSING` 查它。运行期写 `role_unavailable` 事件,`--audit`
   报 `ROUND_DEGRADED`(advisory)。判据:**"谁不可用"是观测事实,"降给谁"是设计期决定**,
   所以不需要编排器。
7. **`/goal` 去掉了。**逐项对比:goal 模式重复了本 skill 四个机制,而**做不到最要紧的那件事
   ——写 `.goals/active`**(给门上膛)。改为插件自带 `/ultra-goal <slug>`:校验制品 → 上膛 →
   交出 spec,一步完成,四家宿主同一形态,没装插件的地方粘贴 `## Handoff` 文本 + 手写 marker。

## 十、这一轮自己抓到的两个实错

都不是推理出来的,是端到端跑出来的。

1. **`ROLE_FALLBACK_MISSING` 误报 4 个正确的角色。**根因:`BULLET_LINE` 只读 bullet 的
   第一行,而 `fallback:` 落在续行上。**是检查器错了,不是文档错了。**加了
   `bullet_blocks()` 把续行折进来,`MEANS_UNLABELLED` 的同一个潜在缺陷一起修掉。
2. **`## Roles` 一加,恢复注入就把 `## Carry-over` 挤掉了。**实测:roles 占 2120 字符,
   预算 5300,carry-over(1111)排在它后面所以被整节丢弃——**而那正是这个 hook 存在的
   全部理由**。修法两条:优先级重排(冻结三节 → carry-over → 其余),预算 6000 → 8000
   (承重节实测约 5.9k),并加 `ESSENTIAL` 守卫:承重节装不下就**大声说出来**,而不是
   悄悄恢复一个看不见自己条款的运行。有测试钉住"承重节永不排在可选节后面"。

## 十一、刻意还没做

- **74 道 eval 仍然只有题目没有成绩,连执行器都没有。**这是唯一还没有任何证据的一半:
  所有依赖"我照着做"的东西 —— 访谈顺序、9 条 refusal、means 标签、真教训 vs 事件、
  挑战条款而不是改条款、不在粘贴的 goal 行上激活 —— 全部零测量。
- **一次真实运行也没跑过。**这台机器上真实 `.goals/` 制品为零,hook 从未安装
  (`doctor: hooks=missing`)。
- 第三节"缺的"第 5 条(`init.sh` 一类"怎么把项目跑起来")**判定为不做**:第一次真实运行里
  锚本身就是环境契约(`.venv/bin/python -m ...`),venv 不存在 → 锚 unknown → 第一轮的活
  就是让它可执行。再加一个 `init.sh` 是第二份同职责的东西。
- **`claude plugin eval` 存在**,是 CC 一等公民功能(`<eval dir>/**/case.yaml` 或
  `prompt.md` + `graders/*.md`)。我们那 74 道题格式不对,但**执行器不需要自己写**。这是
  eval 那个空白的具体修法,也是下一个大项目。
- 第三节"冲突 3"仍未裁决:我们的两个恢复 hook 走的是 context reset 那一路,而 Anthropic
  在更强的模型上**把 reset 整个删掉了**。这两个 hook 可能是在防一个已经不存在的缺陷。
  判据已写进 `anti-patterns.md`,但没有实测。
