# C04｜四种特色业务的精确定义

## A. 决策

候选至少2个、有唯一ID和版本。先验证用户硬约束；unknown可行性不能当通过。结果三种：decided(selected非空、条件明确)、needs_information(selected=null、阻断信息及如何取得)、no_feasible_option(selected=null、各候选违反的约束)。推荐不是执行许可。

decided可以是条件性建议；不能用“条件是未知的关键许可”掩盖needs_information。区别：合理明确的适用条件可以附建议；当前连候选可行性都无法判断且会改变选择的关键事实属于信息缺口。用户要求明确推荐时可以给条件性方向，但必须标注未满足条件，不当已定案。

字段strongest_case/weakest_case/risk/revisit_when保留。新trigger必须是可观察条件，不编概率或精确阈值。有用户提供的量纲与公式才计算交点；无量化依据给定性条件。

## B. 投票输入与计数

每票绑定run_id、proposal_id、proposal_version、voter_id、ballot_revision、choice(yes/no/abstain)、reason、conditions。缺失和failed不是choice。eligible取最初锁定的唯一voter集合；responded取同版本有效票数；decisive=yes+no。valid_ballots=responded。保留missing_ids、invalid_ids、failed_ids。

任何重复/过期/未知票先隔离并报告；不能因为聚合时忽略了坏票就宣称全员覆盖。v2提案另起票集，v1 yes从不继承。默认revision=1，修改票必须显式supersedes，不能last-write-wins。

默认policy=distribution、verdict=not_requested，只展合成分布和条件；不把结果当用户/组织应该做什么。非政治示例可展示算法；真实政治/选举选择只给中立事实信息，不作人格推荐、得票预测或整体排名。

## C. 可决模式规则及判断顺序

用户明确请求算法判定后，默认absolute_majority。配置提前冻结eligible/policy/quorum，不见结果后换票制。

1. 提案被修改且未完成新版本请求集合时：pending_revote（另附有效新票统计）。
2. 首次表决存在未完成/无效参与者：partial；保留provisional_verdict，但不冒充全员结果。缺失者恰好导致肯定结果的情况也保持partial。
3. 完整票集但decisive小于quorum：no_quorum。
4. decisive>0且yes=no：tie。
5. 按规则计算pass/fail；全部弃权在第3步得到no_quorum。

absolute_majority：quorum=ceil(eligible/2)，pass条件yes>eligible/2。valid_majority：用户先定decisive_quorum（1—eligible），pass条件yes>no；不能零参与通过。strict_unanimity：quorum=eligible、需全部yes；任意no或abstain则fail，缺失按partial处理，不能把弃权报no_quorum掩盖“一致同意未获得”。**strict_unanimity专用次序：覆盖完整后直接全yes判断，不复用第3/4步。**

例：16人1yes/0no/15abstain在absolute_majority下no_quorum，yes/eligible=6.25%。8yes/8no为tie。9yes/0no/7abstain为pass（仅指所选算法）。4人3yes/1missing为partial而非正式pass，provisional可说明现有3票满足数学门槛但覆盖未完成。

## D. 改案

条件类型hard_constraint/preference/misunderstanding/unknown。只有preference承认可能交易，hard_constraint不强迫让步。存在互斥硬约束输出no_feasible_compromise并指出具体冲突；不编“既全部本地又全部上传”的万能方案。

修案需新proposal_version和差分，触发重新读取相关证据及重投。剩余turn预算不足全体重投时输出pending_revote，并说明需要另一次授权运行；不能借重投绕过预算。

## E. 写作/改写

rewrite必须有源文本及版本；提取实体/数字/日期/单位/否定/条件/义务强度/因果强度/立场。变化分preserved/authorized_change/review_needed/violation。列表编号、标题页码等结构性数字可白名单，但要有规则，不一律删掉新增数字。

纯改写不默认联网。源材料可能有事实错时指出问题，忠实改写稿不静默改立场。新写作可用明确标注虚构/假设的场景，但不能冒充用户真实经历。缺关键事实留占位说明“需补X”，不造比例。

length_metric=codepoints默认；统计Unicode码位，不把字节或token当字数。英文用户要求words时使用独立word_count并披露规则。文本可包含组合字符/emoji导致视觉字形与codepoint不同；不声称视觉字数完全一致。所有计数发生在最终正文，不计差分注释。

## F. 提问/访谈

questions模式light/middle/heavy最多3/5/7个问题，不要求凑满；include_why默认为false，用户明确需要才展示。interview模式需显式选择，任何时点只问一个关键问题；已答/不愿答/不知道分别记录，不重复追问已解决信息。

停止条件：用户要求结论/退出、关键不确定性消除、达到显式会话turn预算。跨用户回合无后台运行承诺。只问题模式的建议放在用户切换后，不夹带“你应该”。避免问题中预设用户失败、病理或动机。无人格提问模式同样可用，不夸大persona心理诊断。
