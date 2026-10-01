# C03｜证据、主张、统计、输出与人格

## 1. 证据记录

Evidence包含evidence_id、kind、locator、content_hash、observed_at、access_status、trust_class、source_version、scope、excerpt_or_summary、derived_from。kind取provided_file/web_document/tool_observation/participant_statement/user_constraint。access_status为observed/not_accessed/unavailable/stale。

本地定位用安装/项目内相对路径+行号或结构锚点；网页定位用真实URL、标题、取得日期与段落；工具观察写命令/参数/exit_code/实际输出摘要。URL存在不代表已读；模型给了引用也不代表支持。participant_statement只能证明某角色这么说，不能转化成外部事实。

哈希来源必须是已获得内容；不允许为未读网页编造SHA-256。内容不可留存时记录哈希不可得及原因。敏感原文只留必要最小摘要/引用。真实公开引用与虚构fixture区分。

## 2. 主张记录

Claim包含claim_id、revision、actor_id、text、subject_id、scope、assumptions、evidence_ids、status、counter_claim_ids、supersedes、change_condition。status为supported/refuted/unverified/not_applicable。supported不代表确定正确，只是已列证据在限定范围内支持；用户价值偏好按kind=value_preference记录，不硬套事实真值。

语义校验必须检查引用ID存在、证据内容与主张相关、材料版本匹配、作用范围不扩大、角色发言的重复传播不伪计独立证据。涉及当前法律/医疗/价格等时变或高风险事实要按宿主规定核实；无权限则不做已核实陈述。

## 3. 子结果

AgentResult至少含run_id、actor_id、round、attempt_id、input_hash、persona_revision、claims、stance_change、summary、limitations。stance_change=initial/maintained/partially_revised/retracted。不要求隐藏思维链，只给可分享理由、证据和改变条件。

允许claims=[]且说明已检查范围、没有新增发现。不能强制每人贡献独特风险而制造幻觉。输出格式坏和业务判断不同分开处理；格式修复不得诱导不同结论。

## 4. 统计的共同对象

Score至少有actor_id、subject_id、subject_version、criterion_id、scale_id、value。只有全部身份一致的记录可聚合。序数优先给分布、min、所有众数、max。偶数median定义为两个中位观测的平均值并说明可能不是量表选项；不将均值当成功率。

同一角色同一对象只接受一个有效revision，显式supersedes旧项；重复归桶报错。没有可比对象的标题生成任务不出“集体支持分”。生成与共同候选评价是不同阶段、分别花预算。

## 5. 共同输出骨架

默认summary按：结论/当前状态 → 最关键依据 → 尚未解决的少数反例/不确定性 → 适用条件/翻转条件 → 最小下一步 → 执行披露（人数、实际轮数、模式、未完成项、校准/核查状态）。不要给所有任务机械塞六个大标题；骨架字段存在，展示可自然。

代码审查要位置、触发条件、复现状态、影响与测试建议；决策要用户目标/约束与牺牲；写作正文独立于差分报告；ask只问题时不能在正文夹why。原文可选full/raw，但不可信事实保留标记，敏感内容可按规则省略。

## 6. 16人格映射规范

persona文件字段：id、revision、lens(2—4具体关注点)、voice(表达节奏/结构/词汇)、self_check(避免的偏差)、common_competence_ref、source_map。不得存在permission_override、truth_standard_override或强制赞否字段。

区别要体现在关注的约束、提问路径与表达上，不体现在事实诚实程度。证据确认一个bug时16人都可承认；不为“差异性”让一半人否认。用户明确体裁/立场/语气优先于默认voice。

16行迁移设计见 `../06_design/02_persona_mapping.md`。这些是项目角色设计，不是现实人类心理学断言或诊断。


## 7. 补齐的内部输出契约

schemas下另有action_intent、roster、vote_summary、writing_result、interview_state、persona。它们与Request/AgentResult等共同构成协议，不是已实现产品。引用和各业务约束仍做语义校验：roster长度/唯一性与requested_n一致；vote_summary计数/集合/比率与票一致；writing_result actual_length以最终正文实际计数；interview当前问题ID必须在问题集合且只能一个；action已派发状态必须有实际receipt或显式dispatch_unknown。

示例中的null/hash缺失用于说明尚未运行；真实prepared/run派发必须具备实际input_hash。persona source_map的占位段落在WP05必须换成确切原行/标题。示例不是可直接假造一个已完成run的许可证。
