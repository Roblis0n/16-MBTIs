# 安装、升级、卸载与回滚

本仓库已经包含可安装的 `plugins/16-minds/` 和 `.agents/plugins/marketplace.json`。从 GitHub 添加 marketplace、从克隆目录添加本地来源的步骤见 [README](../../README.md#安装到-codex)，依据 [OpenAI 官方插件打包文档](https://developers.openai.com/plugins/build/plugins)。

需要支持插件的 Codex 客户端和 Python 3.11+。Python helper 只依赖标准库；插件安装成功不代表当前宿主完成了八入口模型运行验收。现有同名插件或 marketplace 应先核对来源。

需要 ZIP 时，在仓库根目录运行 `python -B tools/build.py`，生成 `dist/16-minds-0.5.0-static_candidate.zip`。解压后得到独立的 `16-minds/` 插件目录；源码仓库根目录不是插件根目录。

升级前保留旧包、构建清单与版本。使用当前宿主支持的移除和安装流程，仅操作 `16-minds@16minds-local`。卸载不删除项目、用户运行记录、其他插件或整个 Codex 配置。回滚使用原包和原安装记录，不改写历史运行数据。

完整验收应逐个核对八个技能的识别、随包资源、真实委派回执和业务输出。Python helper 校验不能替代模型调用。遇到登录、能力或沙箱阻断时保留真实错误，不复制凭据或关闭安全控制。

当前安全持久化不支持 Windows，默认不保存记录。Standalone/Claude 导出属于 experimental；见 [导出说明](../compatibility/exports.md)。历史隔离安装说明见 [已观察安装流程](../compatibility/host-install-isolated.md)，历史机器回执留在本地原交接归档。
