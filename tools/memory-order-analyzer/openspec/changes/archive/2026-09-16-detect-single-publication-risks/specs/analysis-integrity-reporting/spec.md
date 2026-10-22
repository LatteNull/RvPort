## ADDED Requirements

### Requirement: Validate P4 cross-layer evidence integrity
系统 SHALL 在 worker、磁盘、缓存和报告消费入口验证 PublicationLocalFacts、SinglePublicationProtocolGraph、PublicationRiskReport 与 BC/P1/P2/P3 之间的 schema/policy/model、digest、scope/profile/boundary、语言配置、预算、原始/分析引用、函数/invocation/ThreadInstance、对象范围、guard 和证明闭包。P4 解释 MUST NOT 覆盖或抬高 P1/P2/P3 原始 unknown；结构错误 MUST 被拒绝而非作为正常零候选。

#### Scenario: A successful observation references a stale load
- **WHEN** 成功观察的原始 load、invocation 或 thread effect 与当前 P3/P2 generation 不一致
- **THEN** 拒绝相关产物，不让陈旧节点参与 reads-from 唯一化或 finding

#### Scenario: A valid local interpretation explains a raw unknown narrowly
- **WHEN** P4 局部证明在一个具体候选内解释初值或 gate，但原 P1/P2 仍有更宽 unknown
- **THEN** P4 保存原始诊断、适用上下文和证明，不修改原文件或把该解释推广到其他候选

### Requirement: Preserve P4 plans, findings and unknown denominators
风险分析 SHALL 在执行前登记 scope 成员、根、局部事实和协议候选计划，并在报告中保留 complete、partial、failed、not_run、finding、discharged、unknown、unsupported、excluded 和未展开项。不得通过过滤开放边界、未知同步、超限候选或失败 TU 提高完整率；finding 数与完整率 SHALL 独立统计。

#### Scenario: A partial run already contains a finding
- **WHEN** 一个候选有可报告风险而另一个相关计划项 unknown 或超限
- **THEN** 保留 finding 和 unknown 分母，整体退出 2且 verdict 不伪装为完整

#### Scenario: No findings remain after filtering unsupported inputs
- **WHEN** 所有计划候选都因未支持同步被标记 unsupported
- **THEN** unsupported 仍计入原计划，结果 inconclusive 而不是零风险通过

### Requirement: Isolate P4 risk exit semantics from existing commands
`detect-publication-risks` SHALL 使用 0 表示完整且无 finding、3 表示完整且有 finding、2 表示有可用结果但 partial/unknown/unsupported、1 表示非法或不可继续；partial SHALL 优先于 finding 返回 2。collect/index/link/summarize/model-threads 的既有 0/2/1 语义 MUST 保持不变。

#### Scenario: Existing P3 analysis completes after P4 is installed
- **WHEN** 用户只运行 `model-threads`
- **THEN** P3 仍按原 0/2/1 规则退出并保持 findings=null，不因 P4 可用而运行风险规则
