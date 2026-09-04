# 四宿主适配：任务信封与四轮对抗审查

这一路的完整记录。实现由 zCode 落地，Claude Code 与 Codex 对抗审查，四轮加一轮修正。

- `mission.md` —— 任务信封。§8.1 是 zCode 的实现报告，§8.2/8.3 是两个审查方逐轮，
  §8.4 说明为什么没有联合结论，§9 是三项宿主验收（Kimi、zCode、Windows 模拟器）。
- `reviews/` —— 两方各四轮的独立报告、预注册读数，以及三个可再跑的探针驱动。
  探针从自身位置解析仓库根，所以搬家之后仍然能跑：
  `python3 docs/research/2026-09-04-ultra-goal-review/host-adaptation/reviews/probes-round-5.py`
- 结论与去向：`../最终方案.md`；还没做完的：`../../../wip/outstanding.md`。

## 这些报告里的路径是搬家之前的

四轮报告写在这些文件还在 `docs/wip/` 的时候，里面的引用（含行号）指的是那个布局。
**报告本身不改** —— 改掉引用等于改掉当时的记录。对照表：

| 报告里写的 | 现在在哪 |
|---|---|
| `docs/wip/mission-host-adaptation.md` | `docs/research/2026-09-04-ultra-goal-review/host-adaptation/mission.md` |
| `docs/wip/reviews/` | `docs/research/2026-09-04-ultra-goal-review/host-adaptation/reviews/` |
| `docs/wip/theory-sweep.md` | `docs/design/theory-sweep.md` |
| `docs/wip/protoss-comparison.md` | `docs/design/protoss-comparison.md` |
