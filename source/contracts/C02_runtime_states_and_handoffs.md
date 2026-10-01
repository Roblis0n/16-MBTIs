# C02｜执行、轮次、恢复、错误与清理

## 1. 三个身份与四个版本

run_id为一次冻结输入下的运行；actor_id为该run内逻辑参与者；host_thread_id为宿主创建的短命线程，可为空或更换。所有结果有round、attempt_id、action_id与result_revision。protocol_version、persona_revision、input_hash和evidence_version在准备阶段冻结。任何影响任务/目标的输入变化产生新run并链接parent_run_id。

不得把thread_id当角色永久身份。不得把某角色重新生成的无历史回答冒充原角色改变了观点。恢复仅重建公开输出/依据，不承诺恢复模型内部隐藏状态。

## 2. 运行状态与合法转移

| from | 可到达 | 条件 |
|---|---|---|
| created | validated / blocked / failed / cancelled | 输入校验通过或失败原因明确 |
| validated | prepared / blocked / failed / cancelled | 角色、事实、预算、能力已预检 |
| prepared | running / blocked / cancelled | 本轮输入哈希固定，才可派发 |
| running | running / verifying / synthesizing / partial / failed / cancelled | 新轮次受max_rounds和turn预算约束 |
| verifying | running / synthesizing / partial / failed / cancelled | 真实核查可更新主张但不覆盖原证据 |
| synthesizing | completed / partial / failed / cancelled | 汇总字段和引用校验完成 |
| completed/partial/failed/cancelled/blocked | 无 | 终态只追加late事件，不隐式复活 |

partial是已发布但覆盖不完整的终态。工作中等待不叫partial终态，使用running加pending状态。续跑另建run，保留parent_run_id与已复用范围。

任务状态：queued/dispatched/running/succeeded/invalid_output/timed_out/failed/cancelled/dispatch_unknown/cleanup_unknown。wait超时只表示尚未收到，不能直接置timed_out；到run截止或获明确宿主结果才转换。无法确认spawn是否已成功则dispatch_unknown，不能无幂等机制重发造成双代理。

## 3. 首轮输入

每个角色只拿：用户问题、目标/硬约束、提供的材料快照、自己的persona、输出契约、范围/权限/预算、共同名词表。不包含主持人推荐、其他角色结果、某个“预期正确答案”。S00按真实schema检测是否意外继承父历史；未确认则isolation_status=unknown。

execution_mode为native_parallel/native_batched/native_sequential/single_context。isolation_status为verified_clean/unknown/unavailable/not_applicable。verified_clean只说明指定探针和设置验证通过，不代表统计独立、永不泄漏或不同底模。

## 4. 下一轮与屏障

准备下一轮之前冻结完整的上轮snapshot：成功结果、缺失角色、已核查证据、未解决主张。每位角色拿到自己的原主张+限定+修改历史，并拿统一的对方上轮切片；同轮早返回结果不得泄漏给其他正在生成者。

每次send必须带target_claim_id或明确的新证据任务；没有新关键材料或分歧纯属价值取舍则停。不能为了重试而强迫改态度。钢人化在当前turn内做，不强制新增额外对话回合。

## 5. 上下文压缩

优先保留原文中的数字、否定、量纲、硬约束、例外、适用版本和未解决反例。压缩必须带included_claims/omitted_claims/source_refs和context_complete标记。context_complete=false时不能强称讨论已覆盖全部。上下文过大可结束并提示范围，不偷偷删角色或把未读材料写成已读。

## 6. 幂等与事件

所有action先写pending intent，再调用实际工具，之后记录receipt。helper纯函数step(state,event)生成新state/actions。重复完全相同result哈希视为duplicate_ignore；同ID不同内容为conflicting_duplicate隔离并报告，不最后到达覆盖。生产事件log持久化仍需opt-in；无持久化时只能会话内恢复，宿主中断可能无法保证重建。

参考动作字段：kind(spawn/send/wait/close/verify)、action_id、actor_id、round、input_hash、payload_ref、budget_reservation。它们是本项目中介协议，不是原生工具参数。适配层逐项映射实际schema并写host_receipt；缺字段不得发明。

## 7. 清理与取消

取消：标stop_dispatch→阻止新spawn/send→对本run可管理句柄调用实际取消/关闭→记录确认状态。close工具不存在或调用失败时列residual_thread_ids，cleanup_status=unknown/partial；不得报全清理。不可kill未确认归属进程，不删其他run目录。

软deadline到达后允许一次不新增角色的主线程不完整总结；不可用“总结”名义派发额外代理。外部副作用动作本项目默认不执行；重试不得重放付款、发消息或写生产文件。

## 8. 错误码最小集

E_UNKNOWN_ARGUMENT、E_INVALID_PERSONA、E_CONSTRAINT_CONFLICT、E_MISSING_SOURCE、E_SCHEMA、E_SEMANTIC、E_UNKNOWN_EVIDENCE、E_SCORE_OBJECT_MISMATCH、E_STALE_BALLOT、E_BUDGET_TOO_SMALL、E_BUDGET_EXHAUSTED、E_CAPABILITY、E_PERMISSION、E_CONTEXT_INCOMPLETE、E_DISPATCH_UNKNOWN、E_PATH_ESCAPE、E_SYMLINK、E_EXISTS、E_PROFILE_CYCLE、E_CALIBRATION_MISMATCH、E_INTERNAL。

每个错误含public_message、machine_code、retryable、side_effect_status、safe_next_step；不得打印密钥、完整HOME或敏感原文。retryable=true也不绕过总预算。无可行方案不使用E_INTERNAL。
