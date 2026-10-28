## ADDED Requirements

### Requirement: 独立归约结果必须分别投影到 v2 Finding
每个 matched 归约候选 SHALL 输出独立 v2 Finding，并具有自己的 assessment、稳定 ID、fact、conclusion、occurrences、primaryOccurrenceId 和 evidenceChain。位置、来源与引用 SHALL 限于本候选及必要共享配置，主位置 SHALL 属于自身位置集合；不同候选 MUST NOT 仅因 finding code 或 TU 相同再次聚合。普通独立归约 Finding 的 `affectedCount` SHALL 为 1，不按证据条数膨胀。summary 和引用完整性 SHALL 反映拆分后的真实数量。

#### Scenario: 两个归约命中输出
- **WHEN** 同一 TU 有两个独立归约候选被判为 matched
- **THEN** v2 findings 包含两个不同 ID，各自关联自己的 assessment、主位置和证据链，计数为两个 Finding，所有引用可解析

#### Scenario: 多证据位置仍属于一条风险
- **WHEN** 一个归约候选包含多个可信来源位置和证据
- **THEN** 输出一个 Finding，保留本候选去重后的有界 occurrences 和必要证据，`affectedCount` 为 1

#### Scenario: 其他配置聚合保持不变
- **WHEN** 既有配置级规则按显式 semantic aggregation key 聚合同一危险配置
- **THEN** 仍按该规则的现有契约聚合，不受归约候选拆分影响

### Requirement: 归约候选的抑制与历史结果必须独立处理
扫描器 SHALL 在生成稳定候选身份后逐候选应用合法 suppression 并记录审计。仅匹配一个候选范围的抑制 MUST NOT 隐藏另一个候选；显式匹配多个候选的范围 SHALL 按现有匹配规则逐候选计数。公开结果 SHALL 保持 schema v2 与中英文字段完整，不要求前端、后端接口或历史数据迁移。

#### Scenario: 单点抑制
- **WHEN** 两个循环命中相同规则，但合法 suppression 的范围仅匹配其中一个更新
- **THEN** 只抑制该候选，另一个 Finding 保留；抑制审计指向被抑制候选，summary 与剩余结果一致

#### Scenario: 版本升级与历史记录
- **WHEN** 使用归约规则 1.1 对同一项目重新扫描
- **THEN** 新结果按独立候选生成且明确规则版本，旧扫描记录保持原样；新旧 ID 和数量可以不同，公共结果仍符合 schema v2

#### Scenario: 展示与诊断双语
- **WHEN** 发布候选相关的结论、说明、建议、诊断或 suppression 审计信息
- **THEN** 需要用户理解的内容具有语义一致的非空中文和英文字段，不将内部候选 ID 作为解释文本
