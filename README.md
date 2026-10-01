# 16 Minds · 16-MBTIs

[English](README.en.md) · [MIT License](LICENSE) · [更新记录](CHANGELOG.md)

**让同一个问题接受不同思考视角的检验。** 16 Minds 是面向 Codex 的插件，用 16 种 MBTI 风格的角色设计组织分析、讨论、写作与决策。你可以指定一个角色、邀请多个角色讨论，也可以让插件按任务选择合适的角色。

当前版本为 **0.5.0**，发行状态为 **`static_candidate`（开发候选）**，业务协议为 **1.0.0**。角色用于设计思考视角和表达方式，不代表心理测评结果、真实受访者或独立外部证据。本项目由社区维护，与 OpenAI、Anthropic 或 MBTI 官方无隶属关系。

## 能做什么

插件包含八个技能入口，每个入口都带有独立的运行辅助程序和参考资料：

| 技能 | 用途 | 请求示例 |
| --- | --- | --- |
| `minds-one` | 使用一个指定视角分析问题 | 用 INTJ 视角检查这个方案的假设与风险。 |
| `minds` | 多个视角分析并综合结果 | 用 4 个视角分析以下方案，保留分歧和反例。 |
| `minds-pair` | 两种视角围绕同一材料讨论 | 让 INTJ 和 ENFP 讨论这个方案的可行性。 |
| `minds-cast` | 按任务选择准确数量的角色 | 为研究可行性问题配 4 个角色，先只预览名单。 |
| `minds-write` | 写作或保持事实的改写 | 改写以下原文，保留数字、否定、条件和义务。 |
| `minds-decide` | 在目标和硬约束下评估候选方案 | 比较 A、B 两个选项；缺关键条件时明确指出。 |
| `minds-vote` | 对冻结版本的提案做合成投票并计数 | 让 4 个角色评价同一版本的提案，列明弃权与无效票。 |
| `minds-ask` | 生成澄清问题或逐题访谈 | 先问最多 3 个关键问题；访谈模式每次只问一个。 |

完整角色集合为 `INTJ`、`INTP`、`ENTJ`、`ENTP`、`INFJ`、`INFP`、`ENFJ`、`ENFP`、`ISTJ`、`ISFJ`、`ESTJ`、`ESFJ`、`ISTP`、`ISFP`、`ESTP`、`ESFP`。角色资产分别描述关注点、表达方式与风险自检。

多角色入口默认选择 4 个角色，支持 1–16 个；配对入口固定为 2 个。`light`、`middle`、`heavy` 模式分别限制最多 1、2、3 轮，重试和格式修复共享原预算。

可显式选择 `code-review`、`premortem`、`decision-check`、`research-feasibility`、`journal`、`recheck` 等实验性任务资料，也包含 `course-paper`、`event-plan`、`technical-proposal`。默认不启用这些资料；选择资料不会自动授予联网、保存或执行权限。

## 安装到 Codex

需要支持插件的 Codex 客户端，以及运行辅助程序所需的 **Python 3.11+**。Python 辅助程序只依赖标准库，不需要安装额外的模型 SDK，也不需要单独的模型 API key；生成内容仍使用宿主已有的模型能力与账号。

仓库已包含 `plugins/16-minds/` 和 `.agents/plugins/marketplace.json`，无需先构建即可获得完整插件文件。

### 从 GitHub 添加 marketplace

如果你的 Codex CLI 支持插件 marketplace 命令，可以运行：

```text
codex plugin marketplace add Roblis0n/16-MBTIs --ref main
```

然后在桌面客户端的插件目录中选择 **16 Minds Local**，找到 **16 Minds** 并安装；在新聊天中明确选择对应技能。命令不可用时，先确认客户端支持的插件安装方式。

添加 marketplace 和实际安装是两个步骤。仓库的 marketplace 名称为 `16minds-local`，插件标识为 `16-minds@16minds-local`。如果已有同名安装或 marketplace，请先核对来源，避免把其他来源的插件当作本仓库版本。

以上安装方式依据 [OpenAI 官方插件打包文档](https://developers.openai.com/plugins/build/plugins)。客户端版本和运行环境会影响可用能力，添加成功不代表八个技能的模型工作流都已验收通过。

### 克隆后作为本地来源

```text
git clone https://github.com/Roblis0n/16-MBTIs.git
cd 16-MBTIs
codex plugin marketplace add .
```

随后按上面的桌面安装步骤操作。源码开发者需要重新生成插件时，再运行：

```text
python -B tools/build.py
python -B tools/build.py --check
```

构建同时生成 `dist/16-minds-0.5.0-static_candidate.zip`，解压后得到 `16-minds/`。仓库根目录包含开发文件；实际插件目录是 `plugins/16-minds/`。

## 使用示例

安装后，在支持技能选择的聊天中明确选择 `minds`，并提供材料，例如：

```text
用 16 Minds 的 4 个视角分析下面的研究方案。
目标：找出关键假设、资源缺口和最可能失败的环节。
只使用我提供的材料，不联网，不保存记录。
最终保留不同意见，并区分事实、解释和待验证假设。

[在这里粘贴方案]
```

改写时选择 `minds-write`：

```text
用 16 Minds 改写以下文字，让意思更清楚。
保留原文的数字、否定、条件和义务，不添加未提供的事实。
按最终正文计数。

[在这里粘贴原文]
```

这些是给宿主的自然语言请求。旧 `/mind`、`/minds` 等名称只在请求解析中兼容，不承诺注册为客户端的 slash 命令。

## 工作原理与隐私

宿主模型负责生成内容和调用实际工具。Python helper 负责请求校验、角色选择、预算、状态、证据引用、投票统计和文本不变量检查。helper 不生成角色答案，不自行发起模型 API，也不把准备完成当作执行完成。

多角色独立执行依赖宿主真实提供的委派与隔离能力。能力缺失时会披露限制或拒绝该分支；同一上下文内模拟多个角色需要明确允许，并披露为模拟。角色观点仍需核查，合成投票不是现实人群的民意调查。

默认不保存记录、不联网、不调用额外模型，也没有遥测、云同步或后台任务。宿主自身仍会处理聊天上下文。持久化需要明确授权，**当前安全存储后端要求 POSIX 文件系统能力；Windows 上会明确拒绝持久化写入**。安装和会话内使用与持久化是不同能力。

## 验证状态与已知限制

- 保留 `static_candidate` 状态，未完成目标宿主八入口的完整模型调用验收。
- 原 0.5.0 在 Windows 上已有安装、启用和插件列表核对记录；这不能证明模型工作流或本仓库重新构建后的包已完成宿主验收。
- 历史 Linux 隔离环境中完成过注册、安装和卸载；模型入口在启动前受宿主沙箱条件阻断。
- 历史 Windows 全量回归存在失败和错误，不宣称全平台测试通过。具体平台限制见 [当前开发状态](docs/当前开发状态.md)。
- 角色选择尚未独立校准；公开合成题不构成独立留出评估，不保证优于单模型回答。
- Standalone skills 与 Claude 导出属于实验性导出，资源可由源码生成，目标宿主适配需单独验证。

本仓库收录可维护源码、测试、公开合成测试材料和可安装插件。原交接包中的工作计划、旧源码快照、机器安装记录及历史模型会话未作为插件发布内容上传；不要将这里的文件集合当作原交接归档的完整镜像。

## 开发与检查

只维护 `source/` 与 `runtime/` 等开发源，通过构建更新 `plugins/16-minds/`；不要手工修改生成文件。构建会核对已存在的清单并拒绝覆盖被手改的产物。

```text
python -B tools/minds_cli.py help
python -B tools/minds_cli.py version
python -B tools/build.py
python -B tools/build.py --check
python -B -m unittest tests.unit.test_build tests.unit.test_cli -v
```

按运行平台和所改功能选择测试。需要全量回归时，可运行 `python -B tools/check.py --label my-unique-run-001`；使用新标签，Windows 应启用 Python UTF-8 模式。全量检查包含依赖 POSIX 存储的用例，Windows 当前存在已知平台失败。

| 路径 | 内容 |
| --- | --- |
| `plugins/16-minds/` | 可安装插件、八个技能及各自的参考资料和 helper |
| `.agents/plugins/marketplace.json` | 指向插件目录的 marketplace 配置 |
| `source/` | 角色、技能、工作流、协议与插件身份源 |
| `runtime/minds/` | 仅使用 Python 标准库的运行辅助模块 |
| `tools/` | 构建、检查、导出与评估工具 |
| `tests/` | 单元、集成、导出测试与公开合成测试材料 |
| `docs/` | 安装、兼容性、隐私与评估说明 |
| `evaluation/`、`experiments/` | 公开开发评估及实验协议 |

进一步阅读：[调用协议](source/references/protocol.md)、[安装与回滚](docs/install/README.md)、[实验性导出](docs/compatibility/exports.md)、[安全边界](SECURITY.md)。

## 许可与来源

本项目采用 [MIT License](LICENSE)，保留原项目作者 **yukurash** 的版权及归属。本仓库维护 Codex 迁移版；角色来源记录见 [ATTRIBUTION.md](ATTRIBUTION.md) 和 [persona-provenance.json](source/plugin/persona-provenance.json)。
