# 拿 Protoss 当基准:UltraGoal 差的到底是哪五件事

读的是 `~/projrect-Protoss`(391 提交)与它的 `docs/wip/loop-engineering/`(14,561 行)。
~~跑它的是 Kimi Code 的原生目标模式(`~/.kimi-code/sessions/wd_protoss-*`)~~
**⚠️ 这句是错的(2026-09-04,业主指出)。** 驱动它的是 **Claude Code 自己的原生目标模式**。
`~/.kimi-code/sessions/wd_protoss-*` 证明的是 Kimi **被派工**:LEDGER.md 里写着
`slot 009a → kimi`、`slot 009b → zcode`。我把"某个 CLI 在那个目录里跑过"读成了"那个 CLI
是循环的引擎"——一次典型的把共现当因果。代由 git worktree 承载(`protoss-021a` 的 `.git`
是文件,`loop/021a` 分支)。

**这不是"它比我们好"的感想,是可量的结构差。** 下面每条都带证据位置。

## 一、先看它的形状

```
354/391 提交是 loop:(一个 tick 一条),其余是 round NNNx / merge / judge
175 次改动  TRAJECTORY.md   6702 行   只增不删
 63 次      LEDGER.md       2552 行   当前状态,修剪
 42 次      JUDGE.md         969 行   判定方自己的规则,带条款号
 38 次      GOAL.md         1084 行   ← 目标本身被改了 38 次
 29 次      ANCHOR-PATH.md   548 行
  7 次      tools/check-trajectory.sh  134 行  ← 机械校验"文档承诺"
```

提交标题不是"做了什么",是"我错在哪":

```
loop: the seven daemons went to zero, so what I wrote at minute 104 was wrong
loop: I had written a command into a criterion without running it, so I ran it
loop: anchor 4's mechanism question settled, and I was wrong three times, each time in my own check
loop: the variance reading I have cited a dozen times came from the smallest of the 106 tasks
loop: 021a/021b pre-registration, and writing it exposed a self-contradictory criterion of my own
loop: today's most repeated lesson lived only in the log, not the protocol
judge: round 021a ruled pass; two caliber errors by the judge recorded
```

最后两条是整份材料里最值钱的两句。第一句是**循环发现自己缺一条从教训到协议的通路**;
第二句是**判定方记录自己的裁决错误**。

## 二、它有、而我们结构上做不到的五件事

### 1 · 历史与状态是两份文件,两种可变性

TRAJECTORY.md 开头原文:

> 这份文件与 `LEDGER.md` 的分工:LEDGER 是**当前状态**(修剪,只反映此刻);
> TRAJECTORY 是**历史**(append-only,一个 commit 一条,永不改写已有条目)。

而**每条轨迹必须有四样**:commit sha、谁做的、**为什么这么做(不只是做了什么)**、证据在哪。
再加一句:

> 凡是判断,写下当时的理由与**当时不知道的东西**——事后回看时,当时不知道什么比当时做了
> 什么更有信息量。

我们只有修剪的那一半。`### Lessons` 上限 3、"rewrite never append",而历史被推给了 git。
**但 git 的标题装不下"我当时不知道什么"。** 我们当初的理由是"二十条教训是没人读的日记";
Protoss 的 6702 行轨迹说明真正的问题不是长度,是**没有分工**:修剪的那份该短,历史的那份
该长,两份都要有。

**我们的 3 条上限不是预算,是失忆装置。**

### 2 · 冻结是"晋升的结果",不是"开跑的前置"

GOAL.md 的 `## 2 · 验收线(冻结块 · 你不可改)` 里,四个锚各自带日期和入块方式:

```
#### 锚 3 · N2 自进化(2026-09-03 探测通过,入冻结块)
#### 锚 4 · N4 常驻(2026-09-03 探测通过,入冻结块,过线待定)
#### 已显式降级的候选(不许静默替换成更容易的题面)
```

**候选 → 探测 → 通过则入冻结块,带日期。** 降级是合法的,但必须以"已显式降级"的形式留在
文档里,并附一条禁止静默替换的规则。

我们的设计要求业主在第一轮之前就把 anchor 定对,之后只能挑战不能改。
`## Challenges from the run` 是这条阶梯的种子,但它只到"业主裁决"为止 ——
**没有候选到冻结的上升通道,一个不成熟的 anchor 只能一直错着。**

### 3 · 裁定有身份、有作者、能覆盖前一条

两套编号并行:`DEC-005/006/007`(业主的决定)与 `裁定 P/Q/S/V-1/Z/H/L³`(判定方的裁定)。
而覆盖是**划掉加指路**,不是删除:

```
~~这一轮之后,按裁定 P,可建清单只剩两项~~
⚠️ 这句话是错的,已由裁定 S 更正为四项(见 GOAL.md §裁定 P 更正)
```

`DEC-005` 的说明里写着"推翻 DEC-001 的 loop 所有权"。

我们的 `decisions.md` 是四列的行,**没有 ID、没有覆盖关系**,而 `## Carry-over` 明写
"delete anything no longer true"——**我们的规则会把上面那个划线连同它指向的更正一起删掉。**

### 4 · 机械校验的是"承诺",不是"形状"

`tools/check-trajectory.sh` 的头部注释:

> Enforce the traceability contract: every commit has a TRAJECTORY.md entry, every round dir
> names its commit, and no credential material sits in the repo.
>
> This exists because traceability was promised twice and broken once already: commit
> 01966de swept a worker's in-flight tree because the judge ran `git add -A`.
> **A promise that is not checked is not a contract.**

我们的 `validate_artifact.py` 校验制品的**形状**(节是否齐、phase 是否声明、目标是否已注册)。
它校验的是**契约是否被履行**(每个提交有没有对应的轨迹条目)。这是"声明 vs 测量"那条线
应用到**文档**上,而我们只把它应用到了 anchor 上。

顺带一条:那个脚本解决了我们 `--audit` 同样的问题,而且解法更好——

> A commit cannot contain its own sha -- amending to insert it changes the sha again,
> forever -- so the entry is keyed by subject at write time and the sha is filled in by
> the next stage.

我们是拿提交标题里的 `turn <N>` 去 join。它是**按标题写入、下一阶段回填 sha**。

### 5 · 撤回本身是一份台账

阶段 0 的总结:

> 这一段最重要的产出不是文档,是方法:对抗性分派 + 独立终裁 + 可重跑脚本 + **撤回台账**。
> 它抓出了自己终裁者的两处错(R5 发现 R4 终裁的两处保证类型错标),**四方每一方都至少
> 撤回过一次**。

LEDGER.md 还有编号的 `盲区台账 #8`,而整份 LEDGER 以判定方的自查开头:
"**这个循环不在通往 95% 的关键路径上**",三条事实里第二条是"**我 ledger 里记的 C 线
阻塞项是错的**"。

今天这一轮对抗审查里我撤回了三条发现。**除了散文没有任何地方记着这件事**——
我们没有撤回台账,所以"这个评审方在什么上系统性地错"这个信息每轮都丢一次。

## 三、我们有、它没有的三件(所以答案是并集,不是替换)

1. **一个真的会跑 anchor 并拒绝回合结束的机械门。** Protoss 的锚纪律活在散文和判定方
   手里,循环靠原生目标模式驱动;我们的 Stop hook 让它**不可选**。今天的实测:
   `{"outcome":"red","exit_code":1,"tail":"verify: 0/4 checks passed"}`,门拦住了。
2. **`events.jsonl` 只由 hook 写。** 运行无法作者化的测量通道。TRAJECTORY.md 是运行自己
   写的,校验脚本只保证"有条目",不保证条目内容为真。
3. **没被要求时零成本,以及四家宿主可移植。** Protoss 是一个项目的定制装置。

**结论:Protoss 强在进化与认知记录,UltraGoal 强在机械上的不可选。要做的是并集。**

## 四、最深的一条差别,一句话

**我们把"冻结"实现成了禁止,它把"冻结"实现成了晋升 + 可见。**

而这恰恰违反了我们自己写下的判据。`frozen_digest` 的注释原文:

> This is not tamper-proof - an agent can write any file it can read - but the event log is
> committed, so a moved goalpost turns up in `--audit` and in `git log` instead of passing
> silently. **Making it visible is the achievable property; making it impossible is not.**

我们对 digest 用了"可见即可",对目标本身用了"禁止修改"。**同一条原则,只用了一半。**

## 五、具体改什么,按价值排序

| # | 改动 | 换来什么 | 代价 |
|---|---|---|---|
| 1 | 加 `<slug>.trajectory.md`,append-only,一 tick 一条,四要素含**当时不知道什么**;`### Lessons` 保持修剪 3 条不变 | 从教训到协议的通路;可回看的认知史 | 一个新文件 + 一条"每轮必写"的义务 |
| 2 | 裁定加 ID 与覆盖:`decisions.md` 行编号,更正用划线 + 指向新行,禁止删除 | 目标可以进化而不失去可审性 | `## Carry-over` 的"删掉不再为真的"要**排除** decisions |
| 3 | 候选 → 探测 → 冻结的阶梯:`## Anchor` 允许 `status: candidate`,通过一次探测后由业主晋升并记日期 | 不成熟的 anchor 能成熟,而不是只能一直错 | 门要认这个状态:candidate 期间红不 deny,只记录 |
| 4 | 撤回台账:`decisions.md` 加 `## Retractions`,任何一方撤回过的主张连证据一起留 | 知道每个评审方系统性错在哪 | 一节,人写 |
| 5 | 校验承诺而非形状:`validate_artifact.py --audit` 增加"每个 `goal(<slug>) turn N` 提交是否有轨迹条目",并改成**按标题写入、回填 sha** | 可追溯性从承诺变成契约 | 一条检查 |

**我不打算照搬的:** 1084 行的 GOAL.md、七步固定流程、两套判定编号体系、按 vendor 派 slot 的
并行调度。那些是一个巨型项目的定制装置;UltraGoal 是可复用的 skill,把它们塞进模板会
让第一次用的人写不出制品。**但"scope 完全不相交"作为并行的合并规则是对的**,值得写进
`graph-topology.md` 作为唯一允许并行写入的条件。

## 六、还没验的

- Protoss 的循环由**谁**驱动下一轮:原生目标模式、判定方手动、还是脚本?这决定第 3 条阶梯
  能不能落到我们的门上。`.kimi-code/sessions/` 里应该有答案,还没读。
- 它的 anchor 是不是真的每轮都跑,还是判定方读报告。TRAJECTORY 里能查。


---

# 七、原生目标模式到底是什么(2026-09-04,业主指出后从二进制里挖出来)

业主的原话:"目标模式最根本的不就是 stop hook 吗?stop hook 里的提示词决定了这是可以继续
还是可以终结的。"**准确。** 从 `claude 2.1.260` 二进制里读到的实现:

## 它是一个 `type: prompt` 的 Stop hook

目标被设定时,那句条件被注册成一个 Stop hook 进入**会话 hook 注册表**;达成时被摘掉:

```js
f.sessionHooksRegistry.remove(K(), "Stop", vn);
```

会话状态是 `activeGoal = {condition, iterations, setAt, tokensAtStart, lastReason}`,
每一轮未达成就 `iterations + 1` 并记下 `lastReason`。

UI 侧三种终态:`"Goal could not be achieved"` / `"Goal achieved"` /
`"Goal not yet met… continuing"`。

## 判定它的是一次独立的机械模型调用

评判者的提示词原文:

> You are evaluating a hook condition in Claude Code. Judge whether the user-provided
> condition is met.

> Based on the conversation transcript above, has the following stopping condition been
> satisfied? **Answer based on transcript evidence only.**

它的输出契约是三态,不是两态:

```
- {"ok": true,  "reason": …}
- {"ok": false, "reason": "<reason the condition is not met>"}
- {"ok": false, "impossible": true, "reason": "<explain why the condition can never be satisfied>"}
```

以及两条我们该抄的措辞:

> Always include a "reason" field, **quoting specific text from the transcript** whenever
> possible. If the transcript does not contain clear evidence that the condition is
> satisfied, return {"ok": false, "reason": "insufficient evidence in transcript"}.

> **the assistant claiming the goal is impossible is evidence, not proof;** independently
> confirm the condition is genuinely unachievable rather than deferring to the assistant's
> self-assessment.

评判者跑在受控配置下:`thinkingConfig: {type:"disabled", mechanical:true}`、
`requiresStructuredOutput: true`、`isNonInteractiveSession: true`、独立 `agentId`、
`mode: "dontAsk"`、模型可覆写(`e.model ?? Em()`)。

未达成时回给主循环的是:

```js
{outcome:"blocking", blockingError:{blockingError:`[${e.prompt}]: ${reason}`},
 preventContinuation: !N && e.continueOnBlock !== true, stopReason: reason}
```

**整句条件每轮重贴,外加评判者的理由。**

还有一个 `ProposeGoal` 工具:"Propose a completion condition for this session's work — a goal
that keeps you working until a separate evaluator confirms it is met. Non-blocking."

## 这一挖判了我们设计的一个错,而且是删除形状的

**原生模式里不可变的是"那一句条件"——它在会话状态里,模型碰不到。文档是完全可变的,提示词
只是指着它。** 所以 GOAL.md 改 38 次没有违反任何东西:原生模式从没声称目标被冻结。

**我们把这两件事混成了一件:把条件写进了文档,于是只能去冻结文档。**

更难看的是:**我们的代码本来就是对的。** `frozen_spec_changed` 那一步走的是 `_allow`,
只观察不禁止,`frozen_digest` 的注释自己写着 "making it visible is the achievable property;
making it impossible is not"。**禁止只活在提示词里** —— SKILL.md 的门表、模板的
`## Boundary`、SessionStart 注入前言、Stop 的义务段,四处都在说 "frozen, do not edit,
challenge instead"。

所以待办不是"加解冻机制",是**把四处禁止措辞改成留痕要求**:

| | 现在 | 应该 |
|---|---|---|
| 条件 | 写在可编辑文件里,靠 digest 防 | 仍在文件里,digest **只报告** |
| 文档 | 冻结,只能挑战不能改 | **可以改**,每次改留痕(轨迹条目 + 裁定 ID) |
| digest 的措辞 | "这已经不是业主授权的目标,停下" | "第 N 轮 spec 动了,这是 diff,把裁定记下来" |
| 第四种结果 | green / red / unknown | 加 **impossible**:此会话内不可能达成 |

**该保留、而且比原生强的一条:**原生评判者读 transcript,失败措辞是
`"insufficient evidence in transcript"`;我们跑 anchor 拿退出码。
**退出码打败"从记录里没看出证据"。** 这条不换。

业主裁定:等 zCode 第 2 轮回来一起改,不现在动手。
