## MODIFIED Requirements

### Requirement: 版本化扫描请求
扫描器 SHALL 接受版本化 JSON 请求，必填字段为 `schema_version`、`request_id`、`project_root`、`source_profile`、`target_profile` 和源码输入选择器；源码输入选择器 SHALL 指向编译数据库或显式翻译单元列表。请求 MAY 增加 `bitcode_artifact_set`，其中包含显式 artifact root、manifest 相对路径、预期 manifest SHA-256、required profiles 和 source-mapping 要求。请求 MAY 包含 include/exclude、规则配置、资源预算和抑制项，但未知必填语义、不受支持的主版本、源码输入与 artifact-set 身份冲突 MUST 被拒绝。省略 `bitcode_artifact_set` 时 SHALL 保持 AST-only 行为，并在结果中明确 IR 分析未请求。

#### Scenario: 有效 AST-only 请求
- **WHEN** 请求字段、schema 主版本、profile 和所有源码路径均有效且未提供共享 BC
- **THEN** 扫描器创建一次具有同一 `request_id` 的 AST-only 扫描，在结果中回显规范化配置摘要并标记 `ir_analysis=not_requested`

#### Scenario: 有效 AST 加共享 BC 请求
- **WHEN** 源码输入有效且 `bitcode_artifact_set` 的 manifest、摘要、required profiles 和源码身份一致
- **THEN** 扫描器规划 source facts、LLVM facts 和 evidence 三个明确分母

#### Scenario: 不支持的主版本
- **WHEN** scan request 或其引用 manifest 的 schema 主版本不受支持
- **THEN** 扫描器拒绝请求，返回 `invalid_request`，并输出可机器识别的版本诊断

### Requirement: 稳定且双语的结果协议
扫描结果 SHALL 为版本化 JSON 文档，包含 `kind`、`schema_version`、`analysis_version`、`request_id`、`status`、`summary`、`findings`、`diagnostics` 和 `metadata`。提供共享 BC 时，summary/metadata MUST 分别公开 artifact、source facts、IR facts 和 evidence binding 的 planned/completed/failed/unknown 分母、artifact-set/profile/digest 摘要及 source-mapping 状态；AST-only 请求 MUST 明确 IR facts/evidence 未请求。所有用户可见的 finding 标题、说明和修复建议 MUST 同时提供中文与英文字段，例如 `title`/`title_en`、`message`/`message_en`、`suggestion`/`suggestion_en`。

#### Scenario: 完整 AST 加 IR facts 结果
- **WHEN** 所有计划 source/IR facts 和必需 evidence binding 均完成，且不存在阻断判断的 unresolved unknown
- **THEN** `status` 为 `complete`，各层分母与 diagnostics/unknown 计数一致，metadata 公开使用的 artifact-set 和 profile 摘要

#### Scenario: AST-only 完整结果
- **WHEN** 所有计划 AST facts 完成但请求未提供共享 BC
- **THEN** 结果可以为 `complete`，但 metadata 明确 `analysis_scope=facts_only`、`ir_analysis=not_requested`，且不得描述为完成 IR 风险检测

#### Scenario: 双语字段完整
- **WHEN** 任意 finding 被发布
- **THEN** 该 finding 同时包含非空中文和英文字段，且两种语言描述同一证据、影响与建议

### Requirement: 输出应确定、原子且可审计
扫描器 SHALL 规范化路径分隔符、按稳定键排序集合、避免时间戳参与语义摘要，并通过临时文件加原子替换发布文件结果。artifact-set 本地根、对象存储位置和临时 materialization 路径 MUST NOT 参与事实/evidence 身份或默认输出；默认输出 MUST NOT 暴露环境变量值、凭据或项目根/artifact root 外的绝对路径。结果 SHALL 通过稳定 artifact/bundle digest 引用共享输入，而不是引用可变文件路径。

#### Scenario: 写出过程被中断
- **WHEN** 进程在结果序列化或文件替换前异常终止
- **THEN** 既有有效结果不被截断，新结果不会以完整文件名呈现为可用产物

#### Scenario: 相同 artifact-set 位于不同根目录
- **WHEN** 相同 manifest 和 BC 字节从不同 artifact root materialize 后扫描
- **THEN** 语义结果、facts/evidence ID、摘要和排序相同，默认结果不包含两个绝对根路径
