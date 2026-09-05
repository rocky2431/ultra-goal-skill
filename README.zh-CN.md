# UltraGoal

[English](README.md) · [简体中文](README.zh-CN.md)

UltraGoal 帮助编码 Agent 把一句开放式要求整理成有验收标准、权限边界和检查方法的目标。确认目标后，Agent 可以逐步完成任务，把进度保存在文件里，并在遇到约定范围之外的决定时向你提问。

它以 Skill、Python 脚本和 Hook 的形式运行在 Claude Code、Codex、Kimi Code 或 zCode 中。Hook 是宿主在特定事件发生时调用的脚本，例如一个回合结束时。宿主提供模型、工具和续跑能力，UltraGoal 提供目标定义和验收流程。

适合需要多轮调查、实施和评审的任务。小型的一次性工作可以直接交给 Agent 处理。

版本：2.15.4。核心脚本需要 Python 3.10 或更新版本。

- [安装与开始使用](#安装与开始使用)
- [第一个目标](#第一个目标)
- [目标如何运行](#目标如何运行)
- [文件与进度](#文件与进度)
- [当前限制](#当前限制)
- [文档](#文档)
- [开发](#开发)

## 安装与开始使用

你需要一个能加载 Skill、运行 Python 的编码 Agent。要在回合结束时自动触发验收，宿主还需要加载插件的 Hook。

### Claude Code

```bash
claude plugin marketplace add rocky2431/ultra-goal-skill
claude plugin install ultra-goal@ultra-goal
```

### Codex

```bash
codex plugin marketplace add rocky2431/ultra-goal-skill
codex plugin add ultra-goal@rocky-ultra-goal
```

插件包含主 Skill、`goal-run` 启动命令、评审角色和对应宿主的 Hook 配置。安装后重新加载插件或开启新会话，检查宿主是否发现这些组件。同一套 Hook 启用一份即可，以免重复触发。

### Kimi Code 与 zCode

适配配置位于 `plugins/ultra-goal`：Kimi Code 使用 `kimi.plugin.json`，zCode 使用 `.zcode-plugin/plugin.json`。通过所用版本的原生插件功能加载这个目录。安装界面随版本变化，部分 Kimi 发行版本没有 `kimi plugin` 命令。

宿主需要同时加载清单和 Hook，验收 Hook 才能运行。各适配器注册的事件见 [Hook 覆盖表](docs/usage.zh-CN.md#hook-与宿主覆盖)。如果宿主只能加载 Skill，可以使用功能较少的[单独安装方式](docs/usage.zh-CN.md#单独安装-skill)。

### 本地副本

Kimi Code、zCode 的插件加载器和可选快捷入口需要一份本地副本。克隆仓库并进入目录：

```bash
git clone https://github.com/rocky2431/ultra-goal-skill.git
cd ultra-goal-skill
```

### 可选快捷入口

要为主 Skill 添加较短的调用名称，请在克隆的仓库根目录中，只运行与你使用的宿主对应的一行：

```bash
python3 scripts/install_shortcuts.py --host claude
python3 scripts/install_shortcuts.py --host codex
```

Kimi 和 zCode 分别使用 `--host kimi`、`--host zcode`。安装后重新加载 Skill 或开启新会话。

| 宿主 | 短入口 | 长入口 |
|---|---|---|
| Claude Code | `/UG` | `/ultragoal` |
| Codex | `$ug` | `$ultragoal` |
| Kimi Code | `/skill:ug` | `/skill:ultragoal` |
| zCode | 在 Skill 选择器中选 `ug` | 在 Skill 选择器中选 `ultragoal` |

快捷入口会读取这个克隆目录中的 Skill，因此需要保留该目录。它不安装 Hook；需要 Hook 和评审角色时，请另外安装插件。更换源文件位置、删除入口或使用自定义 Kimi 数据目录的方法见[快捷入口维护](docs/usage.zh-CN.md#快捷入口维护)。zCode 的实际发现情况仍需在安装版本中测试。

## 第一个目标

在你要开展工作的项目目录中打开编码 Agent，用自然语言或已安装的快捷入口调用 UltraGoal：

> 使用 UltraGoal，把“让运营团队能够使用 CSV 导出功能”整理成可执行目标。先检查现有实现，只问我必须决定的问题，最后向我展示完整的验收与授权契约。

Agent 会检查项目和已有目标，一次询问一个尚未确定的选择，然后整理目标供你确认。需要确定的内容包括：

- 最终结果应做到什么，以及如何检查。
- Agent 可以修改哪些文件、操作哪些外部系统。
- 哪些要求必须保持，哪些方法可以替换。
- 什么时候停止，包括尝试次数限制和必要的独立评审。

假设目标名为 `export-ready`，Agent 会把约定写入 `.goals/export-ready.goal.md`，把决定记录在 `.goals/export-ready.decisions.md`。确认条款后，它会询问是否开始；如果你已经授权启动，就直接进入执行。

以后要启动已经确认的目标，如果宿主提供了插件的斜杠命令，可以使用：

```text
/ultra-goal:goal-run export-ready
```

如果宿主没有这个命令，让 Agent 按照[启动流程](plugins/ultra-goal/commands/goal-run.md)运行已有目标。开始前，两份目标文件都需要已经存在。

## 目标如何运行

1. Agent 读取已确认的目标，选择下一步。在已有权限内，它可以调整实施方法。
2. 它自己完成工作，或通过宿主的委派工具分配一项范围明确的任务。使用工作者的结果前，先检查实际产物。
3. 它把当前事实、经验和下一步写回目标文件，再继续推进。
4. 宣布完成前，它请求验收。验收器运行约定的检查命令，称为 **Anchor**，并检查必需的评审证据。通过结果必须对应当前产物。

你决定要达成什么结果，Agent 在约定范围内选择实现方法。修改验收标准、必需手段、权限或预算，需要你的批准。可查明的仓库事实和普通实施选择，由它自行处理。

同一个目标可以用 Loop 执行，由 Agent 在运行时选择下一步；也可以用 Graph 执行，提前写出路由。两者共用验收和授权契约。执行能力来自宿主，UltraGoal 不附带独立的 Agent Runtime 或工作流引擎。

## 文件与进度

每个项目把目标保存在 `.goals/` 中。以 `export-ready` 为例，主要文件是：

| 文件 | 内容 |
|---|---|
| `export-ready.goal.md` | 已确认的要求、验收规则和当前进度 |
| `export-ready.decisions.md` | 做出的决定、放弃的选项及决定者 |
| `export-ready.events.jsonl` | 验收器和 Hook 脚本记录的观测 |
| `active` | 当前绑定到 Hook 的目标及原生会话 |

Agent 维护目标文件中的进度部分：`State` 记录当前事实，`Lessons` 记录应影响后续决定的经验，`Next` 说明从哪里继续。脚本维护验收记录、基线和评审归档。完整文件清单见[文件维护](docs/usage.zh-CN.md#文件及其维护)。

你可以直接请 Agent 查看进度或解释停止原因。手动检查状态、恢复会话和取消任务的方法见[使用指南](docs/usage.zh-CN.md)。取消运行时，需要同时停止宿主的原生目标和 UltraGoal 的活动绑定。

## 当前限制

持续执行依赖宿主的原生 Goal 机制及其预算。Stop Hook 在回合结束时运行，不能唤醒已经关闭的 Agent。没有完成声明的普通 Stop 不执行 Anchor。Agent 应在最终回答前调用 `verify`，这样就能在回答中报告验收结果。

提问、方法选择、状态保存和调用验收流程，仍由模型负责。脚本检查显式声明，无法捕获每一句缺少依据的话，也不能鉴别共享文件里填写的身份是否真实。检查超时、不可用或预算耗尽时，目标保持未验证状态。

包内包含四家适配器，但四家完整的无人值守运行及 Windows 生命周期行为仍未完成验证。依赖某个宿主长期运行前，请查看[剩余验证范围](docs/wip/outstanding.md)。

## 文档

- [使用指南](docs/usage.zh-CN.md)：任务分配、反馈、Hook、验收、恢复和故障排查。[English](docs/usage.md)。
- [目标契约](plugins/ultra-goal/skills/ultra-goal/references/goal-contract.md)：字段、验收覆盖关系和评审凭据。
- [Skill 指令](plugins/ultra-goal/skills/ultra-goal/SKILL.md)：Agent 实际加载的流程。
- [研究依据](plugins/ultra-goal/skills/ultra-goal/references/research-basis.md)：参考工作及其对设计的影响。

## 开发

脚本和测试使用 Python 标准库。在仓库根目录运行：

```bash
python3 -m unittest discover -s tests -v
```

测试覆盖目标校验、会话绑定、验收、中断恢复、证据留存和包结构。宿主生命周期需要另外测试，详见[使用指南](docs/usage.zh-CN.md#验证方式与能力边界)。

## 许可证

[MIT](LICENSE)。

Kimi Code 的用户安装目录遵循 `KIMI_CODE_HOME`，默认是 `~/.kimi-code`；Skill 和 `/ug` 快捷入口都写入该目录下的 `skills`。安装器不会迁移或删除旧 Python CLI 的 `~/.kimi` 目录。参见 [Kimi Skill 目录](https://www.kimi.com/code/docs/kimi-code-cli/customization/skills.html)。
