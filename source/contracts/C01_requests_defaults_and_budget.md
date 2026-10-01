# C01｜请求、入口、默认值与预算（规范性）

协议版本1.0.0。MUST=必须，MUST NOT=禁止，SHOULD=确有理由才偏离并记录。所有默认值是本包提出的产品决策，不是原项目事实或已验证最优值。S01签核后冻结。

## 1. 入口注册

| workflow | skill | 旧功能参照 | n约束 | 缺省mode |
|---|---|---|---|---|
| one | minds-one | /mind | 恰好1 | light |
| many | minds | /minds | 1—16，默认4 | middle |
| pair | minds-pair | /pair | 恰好2 | middle |
| cast | minds-cast | /cast | 1—16，默认4 | middle |
| write | minds-write | voice-write | 恰好1；多风格是多个显式variant，不偷扩N | light |
| decide | minds-decide | voice-decide | 恰好1；多人评审用many+decision profile | light |
| vote | minds-vote | voice-vote | 1—16，默认4 | middle |
| ask | minds-ask | voice-ask | 恰好1 | light |

这些是插件skill入口名，不保证宿主注册同名slash命令。实际调用方式按S00/S11文档验收。原别名仅在本插件自身解析层映射。

## 2. 规范化顺序

1. 分离raw_input、明确flags和`--`之后的正文。正文不得因含`--n`被再次当参数解析。禁止shell执行型解析。
2. persona ID去空格/小写并验证，只允许完整16ID。重复去重并给notice。
3. 固定n工作流先执行其约束。可变n工作流：显式n优先；没有n但有types，则n=types去重数；都缺省则n=4。
4. `--all`仅用于可变n，等价n=16；与显式n冲突报错。--types锁定，不得在cast时替换；锁定多于N报E_CONSTRAINT_CONFLICT。
5. pair可给首角色+第二角色；显式第二角色覆盖--rival并给ignored_rival。没有第二角色且请求rival由selector补一个不同ID；不能补成3人。n=1而显式要求双人挑战报错。
6. unknown flag报E_UNKNOWN_ARGUMENT。业务字段缺失时指出具体缺项；不通过改写用户意图猜测权限。
7. 显式结构化参数与同一请求正文要求冲突时，给出冲突事实并只问一个必要问题；不让实现者自行挑选更大的预算或权限。

请求保留workflow、task_kind、profile、question/source_text、locale、locked_personas、n、mode、presentation、budget、permissions、input_refs、provenance。来源类型为explicit/default/inferred；推断仅可用于任务路由，不可增加权限。

## 3. 人格与任务模式

合法角色：intj、intp、entj、entp、infj、infp、enfj、enfp、istj、isfj、estj、esfj、istp、isfp、estp、esfp。此顺序仅用于序列化，不能作为默认“取前N”的选择算法。

task_kind为creative/decision/factual/engineering/inquiry。profile为已注册一个主模板或null，检查项是受控名单；不接受任意执行DAG。voice=persona或neutral，neutral是对照模式，不伪装有人格。

presentation为summary（默认）、full、raw。raw不绕过隐私/不可信引用标记，也不把未核实原文当结论。locale默认当前用户语言；本项目中文zh-CN样例为主，英文/日文资产保真。

## 4. 统一资源默认表

| 字段 | light | middle | heavy |
|---|---:|---:|---:|
| max_rounds | 1 | 2 | 3 |
| max_agent_turns | N | 2N | 3N |
| max_verification_actions | 0 | 2 | 4 |
| max_repairs_per_result | 1，且仍占用上行turn总额 | 1，同左 | 1，同左 |
| agent_output_target_codepoints | 600 | 1000 | 1600 |
| final_summary_target_codepoints | 1800 | 2500 | 3200 |
| soft_deadline_seconds | 120 | 300 | 600 |

以上截止时间是调度停止策略，**不是完成时间保证**；控制只能在宿主返回/可管理检查点生效。超时不能凭空终止无法取消的后台工具。字数是目标而非截断证据的许可，用户指定文稿长度覆盖写作正文目标但仍受运行预算。

agent_turn是一次要求角色产出新结果的spawn或send：首轮、后续轮、结构修复都计数。纯wait、close不是turn；主线程摘要不是子turn，但其已观测token/耗时另外报告。重试不增加总额。N=4、middle上限8，首轮4+一次repair后仅剩3turn，不能再跑完整四人第二轮；选择有明确理由的3个跟进或直接结束并披露未再问的角色，不能假称全员两轮。

verification_action是调度器派发的一次新证据核查工具操作/明确核查子任务。用户已提供材料的读取、helper校验、控制工具调用另行记observed_tool_calls，**不冒充这个上限覆盖整个宿主的一切工具成本**。角色默认不额外查网/执行程序；需要验证由主控按本表分配。单次工具内部多请求或子代理自主调用不可见时写unknown。这是可审计软预算，不是账单硬封顶。

用户可降低各上限。显式增加上限需要展示会增加哪些动作，不能因“全量”自动提高至无上限。预算不足首轮N次则预检拒绝。max_rounds不可超过3，想做更长实验另走实验CR；max_agent_turns不得大于3N，结构修复与深挖共用总额。真正取消立即停止新派发。

并发上限取已验证open_thread_cap与用户concurrency_cap的较小者；二者任一unknown时保守逐个开关。N不是并发。逻辑actor可跨不同物理thread复建公开状态，严禁捏造未运行的角色。

## 5. 权限默认

read_supplied=true；write_project=false；run_untrusted_code=false；network=false；persist=false；external_models=false；publish=false；allow_simulation=false。这些是plugin内部权限意图，实际宿主可能更宽，必须按C05核验与限制。用户授权来源必须可追到当前明确指示，不能由自然语言分类器自动猜true。

无法完成的权限探针不执行，保留unknown。缺Python的定性降级和缺subagent的single_context降级分别需要披露，不得把“无helper”当允许模型心算正式票结果的后门。

## 6. 错误与退出约定

helper成功exit0；输入/schema/语义问题exit2；权限/能力问题exit3；资源上限exit4；意外内部错误exit5。stdout只输出带status/error的JSON，诊断到stderr并去敏。needs_information、no_feasible_option、abstain不是helper错误。结构纠错只允许一次且预算许可；不修理正常的拒绝、不确定性或不同意见。


## 7. 工作流专用字段（避免解析层自行发明参数）

Request.selection固定包含require_challenger、legacy_preview、preview_only。前者表示用户明确要求N内挑战者；legacy_preview只查看旧配役，不把历史表激活；preview_only仅cast允许，且不派发agent。旧别名语义在normalize保留来源并转这三个字段。

Request.workflow_options按workflow只允许以下之一：one/many/pair/cast为null；write为operation(write/rewrite)、length_metric、length_target、variant_id；ask为ask_mode、include_why、max_interview_turns（默认5、1—20、需要用户跨回合继续）；vote为proposal_id/version/text、policy、decisive_quorum、is_revision；decide为candidates(id/version/description)、user_goal、hard_constraints。必要字段从用户明示材料提取且留来源，未取得则返回缺失信息，不传伪完整Request给执行器。

多风格variants是用户显式请求的有界批量write运行，不是隐藏增加n：每variant独立run_id、同source_version，外层batch预算等于用户批准的总turn；初版最多4variant。未请求批量时只一版。没有独立批准的总预算不把四版当一次调用成本。many可以评多个文稿，评分必须同一对象集合。
