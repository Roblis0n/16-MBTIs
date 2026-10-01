# C07｜打包、兼容与发行

## 1. Manifest主方案

官方当前推荐portable根manifest[R01]，本包选择如下候选；不是已安装结果：

```json
{"$schema":"https://agent-plugins.org/schemas/1.0.0/plugin.schema.json","name":"16-minds","version":"0.4.0","description":"Distinct perspectives for grounded review, decisions, and writing"}
```

0.4.0是拟议目标版本，S00/S11与真实仓库发行历史核对后才能确定。legacy `.codex-plugin/plugin.json`仅在目标宿主确需时从同源生成；不要同时手写两份身份。OpenAI扩展覆盖语义按实际schema核对，不猜merge。[R01]

repo marketplace候选：

```json
{"name":"16minds-local","interface":{"displayName":"16 Minds Local"},"plugins":[{"name":"16-minds","source":{"source":"local","path":"./plugins/16-minds"},"policy":{"installation":"AVAILABLE","authentication":"ON_INSTALL"},"category":"Productivity"}]}
```

字段按S00实时官方schema验证；authentication字段是marketplace约定，不代表本插件需要建立登录账号。source.path基于marketplace根仓库，不是`.agents/plugins`子目录。此例不能代替实际注册安装；不在用户HOME自动创建marketplace。

## 2. 构建步骤

读取固定源清单→校验8入口/16人格/协议版本→确定共享资源策略→拷贝必要资料和helper→校验所有引用可达→补原LICENSE/署名→计算内容manifest→确定性ZIP。路径排序固定、UTF-8 LF、ZIP timestamps固定（例如1980-01-01）、权限元数据固定。构建过程不联网、不写源目录、不装依赖。

禁止发布：baseline原包、.git、真实runs、测试答案、API key、宿主config、开发机绝对路径、pycache和未启用profile。public例子必须synthetic标注。manifest/generation清单哈希与发布ZIP一致，不能生成后手改。

## 3. 支持矩阵

字段host_surface、version、os、plugin_manifest_mode、native_delegation、isolation、open_thread_cap、python、resource_paths、install/smoke/uninstall、tested_at、evidence_ref。状态documented/observed/unsupported/unknown。官方文档当前描述桌面/CLI支持而IDE不支持plugin[R03]，但用户实机版本独立确认。

Windows是关键目标（中文/空格/驱动器/junction），Linux为第二环境；macOS无实机则not_run。CLI和桌面的插件安装、刷新/新会话规则分别测试。仅在容器模拟Windows路径解析不算Windows安装成功。

## 4. 发行等级

static_candidate：仅静态构建/协议测试；host_candidate：真实8入口smoke和安全关键项通过；uncalibrated_release：用户批准，文案无效果优越声明，校准明确为空；calibrated_release：另需C06独立数据与激活签核。

S10的评估协议必须完成，但真实费用实验可not_run并限制发行等级。不得把“无有效校准也可发行”理解为“无安装测试也可声称可用”。未通过的可选profile不列默认功能。

## 5. 安装/卸载和维护

新用户教程写当前实际工具界面的步骤、最短用例和排错；代码块内命令在真实环境核验后发布。原Claude命令不再默认注册，给明确迁移表。IDE需要独立skills导出属WP31，不混宣传。

卸载只关闭/移除本plugin与其marketplace注册，不删整个`~/.codex`、其他skills或用户日志。日志默认保留，删除另确认。升级保留旧ZIP和build-manifest；若schema变更给只读旧版渲染或显式migration，历史记录不原地覆盖。

公开push/tag/release/upload必须单独授权。没有授权最多产本地candidate/草拟发行说明。依赖/官方接口变化用S00探针重跑，不后台自动升级。bug回归必须链接原F编号与新增测试，不能只是“优化prompt”。
