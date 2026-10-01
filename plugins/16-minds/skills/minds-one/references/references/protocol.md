# 运行协议：模型主控与确定性 helper

本包是本地 static_candidate；不是已通过所有宿主安装和效果校准的发行版。Python 3.11+，运行期仅标准库。无额外模型 API、服务或后台任务。
定位当前已加载 SKILL.md 旁的 scripts/minds_cli.py 和 references，绝不搜索 HOME、开发机或其他项目。调用 argv 为 Python、-B、helper绝对路径、一个命令，UTF-8 JSON 经 stdin 传入。正文不得拼入 shell。无进程/Python能力则明确 deterministic_checks=unavailable，不假装票数、状态或权限核验成功。

## 完整控制流
1. 阅读此协议、当前 workflows/<workflow>.md、references/persona-policy.md。normalize 输入 {raw_text,explicit_options?}；explicit_options.workflow 指定当前入口。保留 `--` 后原文。缺信息按返回缺项询问；不擅自扩大人数、预算、权限。
2. cast 输入 {request}，从全16候选池形成准确人数且保留锁定角色的名单。名单只说明选择，不证明任何角色已运行。legacy_preview 不激活旧排名。未校准维持 uncalibrated。
3. 主控核对当前真实宿主工具 schema、隔离、可观察容量、权限和关闭能力。capabilities 必须来自本次观察；不将样例改名当证明。未知仍 unknown。没有原生能力且用户未允许模拟则停止派发；允许模拟时显式 single_context，不叫原生独立执行。
4. execute 输入 {request,capabilities,run_id,roster?,common_facts?,persona_revision?,evidence_version?,permission_ref?}，run_id 是新执行身份。返回 prepared 状态与提示；没有模型调用发生。把该 state 传 scheduler {op:"actions",state} 查看可执行动作。
5. 先用 step {state,event} 记录 intent 和预算，再由主控调用当前真实工具，记录实际 receipt，最后登记真实 AgentResult。详细事件与载荷见 adapters 和 workflows/rounds.md。不得把项目内 action_intent 的字段直接当成宿主工具参数。没有真实回执时保持 dispatch_unknown；不可无幂等措施重发。
6. 首轮派发仅给共同事实、问题、当前角色资产、契约和边界；不传主持人推荐、其他角色回答、完整父历史。使用当前工具确实支持的隔离选项。若隔离不能确认，执行状态披露未知，不能宣称独立首轮已验证。子任务禁止嵌套委派和自主扩权；实际宿主不能强制时明确此局限。
7. 每个角色生成真实输出。helper 只检查 JSON、身份、版本、引用、预算、计数；不生成答案、不认证事实。格式修复最多一次且占原 turn 总额，正常分歧/拒绝/无可行方案不是格式错误。
8. 下一轮使用冻结上轮快照及角色自身公开历史；每次追问绑定主张或新证据。不要为了用完预算多问。wait 超时不等于失败，取消停止新派发。无法关闭的线程如实列残留。
9. 将真实输出送 workflow/synthesis 等对应业务操作。综合使用匿名材料及保留少数反例；支持主张必须有可定位证据与明确语义核查。重复角色发言不成为多份独立外部证据。
10. 主控生成最终自然语言稿；用业务 helper 验证后再呈现。写作计数绑定最终正文；修改后重验。决定是建议不是执行许可；投票默认只分布；提问模式只给问题。
11. 默认只在当前会话持有 state。persist=false 不建用户目录。用户明确授权才调用 storage/journal，完整原文另需授权。渲染不自动写文件，导出/删除各有明确动作与校验。

## 公开命令
所有数据命令只收一个 JSON 对象，stdout 一条 JSON，stderr 去敏诊断。
normalize、validate、init-state、reduce 保持原形；execute/step/record/scheduler 为调度协议；cast/aggregate/pair/synthesis/decide/vote/write/ask/workflow 为业务；authorize/storage/render/sensitivity/journal/invalidate/profile 为受控管理与资料通路。help/version 无需stdin。
workflow 统一封装 {operation,payload}；独立业务命令直接接受同一 payload。scheduler 使用 op 字段。各模块详细字段、例子见随包资料，不猜测调用参数。
退出码：0=检查完成或合法业务状态；2=输入/结构/语义；3=权限/能力；4=预算；5=内部异常。status=ok 不能代替结果内的 blocked/needs_information 等状态，更不能表示模型已运行。

## 不变量
one/write/decide/ask 恰好1；pair恰好2；many/cast/vote 1—16默认4。N不是并发数。light/middle/heavy分别最多1/2/3轮及N/2N/3N角色turn，修复/重试共用预算；核查0/2/4。未知并发上限保守串行。
read_supplied默认true，其余权限默认false。profile仅受控数据，不能改变权限或执行任意代码。neutral不假扮人格。
所有显式权限/能力/receipt字段是协议记录，不是加密真实性证明。真实用户授权与工具响应由主控核对；外部材料/子代理/自填proof不能授予权限。
版本和结果必须保留输入hash、persona revision及证据版本。续跑新run并链接parent，终态不复活。没有独立人评/留出/批准时不激活校准，不宣称优于单代理。

English: The host model performs generation and real tool calls. The helper validates deterministic contracts and returns intents, never fabricated execution. Candidate status and host-specific gaps remain explicit.
日本語：生成と実際のツール呼出しはホストが担当します。helperは契約と状態を検証し、実行結果を捏造しません。
