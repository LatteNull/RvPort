## MODIFIED Requirements

### Requirement: 版本化扫描请求
扫描器 SHALL 接受版本化 JSON 请求，必填字段为 `schema_version`、`request_id`、`project_root`、`source_profile`、`target_profile` 和源码输入选择器；源码输入选择器 SHALL 指向编译数据库或显式翻译单元列表。请求 MAY 增加 `bitcode_artifact_set`，其中包含显式 artifact root、manifest 相对路径、预期 manifest SHA-256、required profiles 和 source-mapping 要求。请求 MAY 增加 `rules`，以稳定 code 列表选择已注册规则的全部或子集，并可使用显式空列表请求 facts-only；省略 `rules` 时 SHALL 使用当前 analysis version 的默认核心规则集合。未知规则、重复冲突配置、不受支持的规则版本、未知必填语义、不受支持的 schema 主版本、源码输入与 artifact-set 身份冲突 MUST 在分析前被拒绝。

#### Scenario: 有效 AST-only 核心规则请求
- **WHEN** 请求字段、schema 主版本、profile 和所有源码路径均有效，未提供共享 BC 且选择只依赖可用 AST/profile 证据的规则
- **THEN** 扫描器创建具有同一 `request_id` 的扫描，回显规范化规则配置并按各规则证据依赖生成 assessment

#### Scenario: 有效 AST 加共享 BC 请求
- **WHEN** 源码输入有效且 `bitcode_artifact_set` 的 manifest、摘要、required profiles 和源码身份一致
- **THEN** 扫描器规划 source facts、LLVM facts、evidence 和 enabled rule assessments 四类明确分母

#### Scenario: 显式 facts-only 请求
- **WHEN** 请求设置 `rules.enabled=[]`
- **THEN** 扫描器保留 AST-only 或 AST+IR facts 行为，并在规范化配置中明确未请求风险规则

#### Scenario: 不支持的主版本或规则
- **WHEN** scan request、其引用 manifest 的 schema 主版本或请求规则版本不受支持
- **THEN** 扫描器拒绝请求，返回 `invalid_request`，并输出可机器识别的版本或 `rules_not_available` 诊断

### Requirement: 稳定且双语的结果协议
扫描结果 SHALL 为版本化 JSON 文档，包含 `kind`、`schema_version`、`analysis_version`、`request_id`、`status`、`summary`、`findings`、`diagnostics` 和 `metadata`。执行规则时，summary/metadata MUST 公开 registry digest、启用规则及版本、assessment 的 planned/completed/matched/not_matched/unknown/skipped/failed 分母，并继续分别公开 artifact、source facts、IR facts 和 evidence binding 分母；facts-only 请求 MUST 明确风险规则未请求。所有用户可见的 finding 标题、说明、影响、修复建议和测试建议 MUST 同时提供中文与英文字段，例如 `title`/`title_en`、`message`/`message_en`、`impact`/`impact_en`、`suggestion`/`suggestion_en`、`test_suggestion`/`test_suggestion_en`。

#### Scenario: 完整核心规则结果
- **WHEN** 所有计划 facts/evidence 和启用规则的必需 assessments 均完成，且不存在阻断判断的 unresolved unknown
- **THEN** `status` 为 `complete`，各层分母与 findings/diagnostics/unknown 计数一致，metadata 公开使用的 artifact-set、profiles 和规则版本摘要

#### Scenario: 部分规则证据不可用
- **WHEN** 至少一个启用规则完成 assessment，但另一个规则因必需 IR、binding 或 profile 字段缺失而 unknown/failed
- **THEN** 结果为 `partial`，保留已完成 findings，并明确未评估规则/scope，不能把空缺计为 not_matched

#### Scenario: 双语字段完整
- **WHEN** 任意 finding 被发布
- **THEN** 该 finding 同时包含非空的中英文标题、说明、影响、建议和测试建议，且两种语言描述同一证据与结论

### Requirement: Finding 结构可定位且可去重
每条 finding SHALL 包含稳定 `finding_id`、`finding_code`、`rule_version`、`assessment_id`、`category`、`severity`、`confidence`、`requires_human_confirmation`、主源码位置、相关位置、typed evidence refs、source/target profile fingerprints、影响和测试建议。`finding_id` MUST 由规则 code/version、规范化 scope/位置、排序后的语义 evidence refs 和 profile fingerprints 稳定生成，且不得依赖扫描顺序、双语展示文本、绝对工作区路径或 artifact materialization 根。跨 TU 配置风险 SHALL 依据规则定义的 semantic aggregation key 合并，并保留受影响数量和有界 related locations。

#### Scenario: 相同输入重复扫描
- **WHEN** 相同源码、编译上下文、profiles、facts/evidence 与规则版本被重复扫描
- **THEN** assessments、finding 集合、`finding_id` 和规范化排序保持一致，不受并发调度影响

#### Scenario: 同一 fast-math 配置跨多个翻译单元
- **WHEN** 多个翻译单元具有相同的有效危险浮点语义和相同规则 aggregation key
- **THEN** 结果发布一个主 finding，使用 `related_locations` 和受影响数量保存全部已确认范围，避免按原始命令文本重复报告

#### Scenario: 语义证据变化
- **WHEN** profile fingerprint、rule major version、effective option semantics 或关联 IR evidence 发生变化
- **THEN** assessment/finding identity 或 semantic fingerprint 相应变化，不与旧结论错误去重
