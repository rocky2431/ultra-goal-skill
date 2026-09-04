# Ultra Goal 四宿主审查交付

完成三家各三轮的实际对抗讨论。实施代码未改、未提交、未安装或修改全局配置。

- [最终方案与论证](方案与论证.md)：当前应采用的结论、完整循环、hook 分工和置信度边界。
- [主审裁决与验证](裁决与验证.md)：Codex 初审、逐项反驳、源码位置、真实探针与最终限定。
- [结构化证据与九次回执](evidence.json)：固定代码基线、原生版本相关证据、报告摘要哈希、执行结果和协议告警。

## 原始讨论记录

这些是每轮交付的原文，包含当时尚未纠正的主张。不要把第一轮的假设当作最终方案；撤回与裁决见第三轮及主审报告。原文中的临时路径保留为当时来源，核心证据已经归档到本目录。

| 真实代理 | 独立审查 | 交叉质询 | 最终攻击 |
|---|---|---|---|
| Claude Code | [第 1 轮](discussions/claude-round1.md) | [第 2 轮](discussions/claude-round2.md) | [第 3 轮](discussions/claude-round3.md) |
| zCode | [第 1 轮](discussions/zcode-round1.md) | [第 2 轮](discussions/zcode-round2.md) | [第 3 轮](discussions/zcode-round3.md) |
| Kimi | [第 1 轮](discussions/kimi-round1.md) | [第 2 轮](discussions/kimi-round2.md) | [第 3 轮](discussions/kimi-round3.md) |

## 验证范围

- main 固定 b07e2a8；适配候选固定 f15a003。适配活工作树在讨论期间继续变化，未被本任务修改。
- 本次执行的 hook 定向测试：main 69 项通过，adapt 93 项通过。它们不是宿主生命周期测试。
- Codex/CC：有意 exit 2 纠正、真正静默放行已在已安装 CLI 上实跑。另复现 CC allow-context 仍续跑，以及 Codex 混合 Stop JSON 未产生纠正。
- Kimi/zCode：没有成功的真实 hook 注册和消费验证；zCode 的临时设置探针被 root CLI 的 Unknown option --settings 拒绝。
- CC 的 native goal 共存探针没有给出足以判定优先级的记录，未算完整 goal 验证。
- Kimi 三轮回执虽均成功交付报告，但包含 185/67/31 条协议告警；不据此证明 ACP 链路健康。
- 四家完整无人值守链、取消、恢复和原生完成时序仍须在实施期验收；没有用投票数推导 95% 成功率。
