## MODIFIED Requirements

### Requirement: 版本化扫描请求
扫描器 SHALL 接受版本化 JSON 请求，必填字段为 `schema_version`、`request_id`、`project_root`、`source_profile`、`target_profile` 和源码输入选择器；源码输入选择器 SHALL 指向编译数据库或显式翻译单元列表。请求 MAY 增加 `bitcode_artifact_set`，其中包含显式 artifact root、manifest 相对路径、预期 manifest SHA-256、required profiles 和 source-mapping 要求。schema 1.3 请求 MAY 为 source/target 分别增加版本化 build context，并 MAY 增加带稳定 finding code、仓库相对路径 pattern、可选行范围和非空理由的 suppressions。请求 MAY 增加 `rules`，以稳定 code 列表选择已注册规则的全部或子集，并可使用显式空列表请求 facts-only；省略 `rules` 时 SHALL 使用该 schema/analysis version 锁定的默认规则集合。未知规则、重复冲突配置、不受支持的规则版本、无理由或越界 suppression、build context/profile 冲突、未知必填语义、不受支持的 schema 主版本、源码输入与 artifact-set 身份冲突 MUST 在分析前被拒绝。

#### Scenario: 有效 AST-only 表达式规则请求
- **WHEN** schema 1.3 请求字段、profiles 和源码路径均有效，未提供共享 BC且选择只依赖可用 AST/profile 证据的规则
- **THEN** 扫描器创建具有同一 `request_id` 的扫描，回显规范化规则、build-context 和 suppression 配置并按依赖生成 assessments

#### Scenario: 有效 AST 加共享 BC 请求
- **WHEN** 源码输入有效且 `bitcode_artifact_set` 的 manifest、摘要、required profiles 和源码身份一致
- **THEN** 扫描器规划 source facts、LLVM facts、evidence 和 enabled rule assessments 四类明确分母

#### Scenario: 显式 facts-only 请求
- **WHEN** 请求设置 `rules.enabled=[]`
- **THEN** 扫描器保留 AST-only 或 AST+IR facts 行为，并在规范化配置中明确未请求风险规则

#### Scenario: 旧请求保持旧默认集合
- **WHEN** 受支持的 schema 1.0-1.2 请求省略规则选择
- **THEN** 扫描器使用该版本锁定的四条核心规则，不静默启用 schema 1.3 新规则

#### Scenario: suppression 缺少理由
- **WHEN** 请求 suppression 使用未知 code、项目根外路径、全规则通配或空理由
- **THEN** 扫描器拒绝请求，返回 `invalid_request` 和可机器识别的 suppression 诊断

#### Scenario: 不支持的主版本或规则
- **WHEN** scan request、其引用 manifest/build context 的 schema 主版本或请求规则版本不受支持
- **THEN** 扫描器拒绝请求，返回 `invalid_request`，并输出可机器识别的版本或 `rules_not_available` 诊断

### Requirement: 稳定且双语的结果协议
扫描结果 SHALL 为版本化 JSON 文档，包含 `kind`、`schema_version`、`analysis_version`、`request_id`、`status`、`summary`、`assessments`、`findings`、`suppressions`、`diagnostics` 和 `metadata`。执行规则时，summary/metadata MUST 公开 registry digest、启用规则及版本/依赖、assessment 的 planned/completed/matched/not_matched/unknown/skipped/failed 分母、finding 与 suppressed 数量，并继续分别公开 artifact、source facts、IR facts 和 evidence binding 分母；facts-only 请求 MUST 明确风险规则未请求。metadata MUST 公开 source/target profile fingerprints 和提供时的 build-context fingerprints。所有用户可见的 finding 标题、说明、影响、修复建议和测试建议，以及需要动作的 suppression/diagnostic 信息，MUST 同时提供中文与英文字段。

#### Scenario: 完整十规则结果
- **WHEN** 所有计划 facts/evidence 和启用规则的必需 assessments 均完成，且不存在阻断判断的 unresolved unknown
- **THEN** `status` 为 `complete`，各层分母与 findings/suppressions/diagnostics/unknown 计数一致，metadata 公开使用的 artifacts、profiles、build contexts 和规则版本摘要

#### Scenario: 部分规则证据不可用
- **WHEN** 至少一个启用规则完成 assessment，但另一个规则因必需类型、控制流、循环、IR、binding、profile 或 build-context 字段缺失而 unknown/failed
- **THEN** 结果为 `partial`，保留已完成 findings，并明确未评估 rule/scope，不能把空缺计为 not_matched 或 suppressed

#### Scenario: 双语字段完整
- **WHEN** 任意 finding、可审计 suppression 或需要用户动作的 diagnostic 被发布
- **THEN** 其用户可见内容同时包含非空中英文字段，且两种语言描述同一证据与结论

### Requirement: Finding 结构可定位且可去重
每条 finding SHALL 包含稳定 `finding_id`、`finding_code`、`rule_version`、`assessment_id`、`category`、`severity`、`confidence`、`evidence_origin`、`requires_human_confirmation`、主源码位置、相关位置、typed evidence refs、source/target profile fingerprints、可选 source/target build-context fingerprints、影响、测试建议和结构化 `validation_plan`。`validation_plan` MUST 表达适用 input classes、absolute/relative/ULP/classification/errno/exceptions error metrics、`standard|profile|project-policy|user-provided|unknown` threshold source 及平台/选项/舍入/顺序/repeat strategy；扫描器 MUST NOT 为 `unknown` 或业务阈值臆造数值。`finding_id` MUST 在 suppression 前由规则 code/version、规范化 scope/位置、排序后的语义 evidence refs、evidence origin 和适用 fingerprints 稳定生成，且不得依赖扫描顺序、双语展示文本、suppression 理由、绝对工作区路径或 artifact materialization 根。跨 TU 配置风险 SHALL 依据规则定义的 semantic aggregation key 合并，并保留受影响数量和有界 related locations。

#### Scenario: 相同输入重复扫描
- **WHEN** 相同源码、编译上下文、profiles/build contexts、facts/evidence 与规则版本被重复扫描
- **THEN** assessments、finding 候选、`finding_id` 和规范化排序保持一致，不受并发调度或 suppression 是否展示该候选影响

#### Scenario: 启发式 finding
- **WHEN** 规则只能根据比较、归约或输入域线索推断风险
- **THEN** finding 包含 `evidence_origin=heuristic`、`confidence=medium|low`、固定 rationale、`requires_human_confirmation=true`，且 validation plan 的业务阈值来源为 `project-policy`、`user-provided` 或 `unknown` 而非扫描器生成值

#### Scenario: 特殊值验证计划
- **WHEN** finding 涉及 libm、fenv 或 NaN/Inf 语义
- **THEN** validation plan 包含适用特殊值/边界 input classes、classification/errno/exceptions metrics 和明确的平台、rounding 或重复策略

#### Scenario: 同一配置跨多个翻译单元
- **WHEN** 多个翻译单元具有相同的有效危险语义和相同规则 aggregation key
- **THEN** 结果发布一个主 finding，使用 `related_locations` 和受影响数量保存全部已确认范围，避免按原始命令文本重复报告

#### Scenario: 语义证据变化
- **WHEN** profile/build-context fingerprint、rule major version、effective semantics 或关联 IR evidence 发生变化
- **THEN** assessment/finding identity 或 semantic fingerprint 相应变化，不与旧结论错误去重

## ADDED Requirements

### Requirement: Suppression 必须有理由且可审计
扫描器 SHALL 在 finding candidate 和稳定 `finding_id` 生成后应用 request 或源码 suppression。每条有效 suppression MUST 精确记录 rule code、规范化路径/范围、理由、来源、candidate finding ID 和匹配结果；被抑制候选不得出现在 `findings`，但 MUST 出现在有界 `suppressions` 记录并计入 `summary.suppressed`。无理由、未知 code、范围歧义、越界路径或全规则通配 MUST NOT 隐藏结果。

#### Scenario: 请求抑制匹配单个 finding
- **WHEN** 有效 request suppression 的 code、路径和行范围唯一匹配 finding candidate
- **THEN** candidate ID 保持稳定、finding 不发布、suppression audit record 和 suppressed 计数增加

#### Scenario: 带理由的源码抑制
- **WHEN** 严格格式的 `fp-precision-scanner: ignore <code> -- <reason>` 注释可唯一绑定相邻声明或表达式
- **THEN** 只抑制该范围对应 code，并记录 spelling/expansion provenance 和理由

#### Scenario: 源码抑制范围歧义
- **WHEN** 宏、模板或同位置多个表达式导致注释无法唯一绑定
- **THEN** suppression 不生效，输出双语诊断且候选 finding 仍发布
