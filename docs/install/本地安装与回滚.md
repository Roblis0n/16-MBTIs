# 已实测的隔离 CLI 注册、安装与卸载

检查环境：Linux，Codex CLI `0.159.0-alpha.7`，Python `3.12.14`。这是项目临时验收流程，不是修改用户现有 Codex 配置的安装教程。当前发行等级仍是 `static_candidate`。

## 已知结果

- 在全新、仅用于本次测试的 `HOME` / `CODEX_HOME` / `CODEX_SQLITE_HOME` 中，`codex plugin marketplace add`、`plugin add`、`plugin list`、`plugin remove` 已真实成功
- 临时 marketplace 使用原仓库的 `.agents/plugins/marketplace.json` 和生成的 `plugins/16-minds`；引用路径相对于 marketplace 根，不能误指向 `.agents/plugins` 子目录
- 安装返回 `16-minds@16minds-local`，卸载后已安装列表为空，预置合成用户文件保持原字节
- 实际 `$minds-one` 会话在模型启动之前失败：沙箱辅助程序要求 app-server socket 目录属于当前用户且权限为 `0700`。新建私有临时 HOME、CODEX_HOME、TMPDIR、XDG_RUNTIME_DIR 后仍失败。没有绕过沙箱，也没有修改共享 socket 目录或全局权限
- 因此，注册成功不等于自然触发或八入口运行成功；其余七入口因同一启动前阻断而 `not_run`

完整命令、退出码、stdout/stderr、候选包构建哈希和版本见 `reports/one-shot/host-cli-*.json`。同为0.5.0的不同构建必须按包哈希分辨，旧回执不能证明后来构建。

## 隔离前提

只有用户明确授权临时安装验收时使用本流程。先选择**全新**临时目录，确认无同名插件、无用户资产；仅复制本插件和 repo marketplace。`CODEX_HOME` 目录必须先存在。测试进程以受控环境启动，只传必要的 PATH、LANG 和临时目录变量；不复制 auth.json、API key、账号令牌或用户配置。

以下是实际支持的命令形式。`<临时marketplace根>` 指包含 `.agents/plugins/marketplace.json` 与 `plugins/` 的同一个新目录；全部命令必须在同一个隔离环境中执行：

```text
codex --version
codex plugin list --json
codex plugin marketplace add <临时marketplace根> --json
codex plugin add 16-minds@16minds-local --json
codex plugin list --json
codex --no-daemon exec --ephemeral --sandbox read-only --skip-git-repo-check --json "$minds-one intj --mode light <合成任务>"
codex plugin remove 16-minds@16minds-local
codex plugin list --json
```

传递 `$minds-one` 时应使用参数数组，或在 shell 中使用不会展开 `$` 的正确引号；不能把上面的双引号文本直接当作通用 shell 脚本。项目实际工具以 Python `subprocess.run(argv, env=allowlisted_environment)` 传参。

若真实宿主可以启动，逐个测试 `minds-one`、`minds`、`minds-pair`、`minds-cast`、`minds-write`、`minds-decide`、`minds-vote`、`minds-ask`，分别核对技能识别、随包资源、真实委派回执与业务输出。通过 Python helper 的 JSON 检查不能替代这一步。遇到登录、权限或沙箱阻断时保留错误，不复制现有凭据、不新建账号、不关闭安全控制。

## 卸载与数据

本次测试只卸载明确的 `16-minds@16minds-local`，未删除其他插件或项目。日志默认不持久化；实际用户已有的 `.16minds/runs`、宿主会话、备份或 Git 历史不属于插件卸载范围。不要运行删除整个 HOME/CODEX_HOME 的命令。

Windows、macOS、桌面客户端和 Claude 的真实安装与文件系统安全尚未验收；Linux结果不外推。独立 skills / Claude 导出属于 experimental，保持同源但单独验收。

官方依据：[插件打包与路径](https://developers.openai.com/plugins/build/plugins)、[CODEX_HOME 等环境变量](https://learn.chatgpt.com/docs/config-file/environment-variables)。官方文档是接口依据，实际回执才是本环境测试证据。
