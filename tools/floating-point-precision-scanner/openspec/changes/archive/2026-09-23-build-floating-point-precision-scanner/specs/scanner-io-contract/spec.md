## ADDED Requirements

### Requirement: 版本化扫描请求
扫描器 SHALL 接受版本化 JSON 请求，必填字段为 `schema_version`、`request_id`、`project_root`、`source_profile`、`target_profile` 和输入选择器；输入选择器 SHALL 指向编译数据库或显式翻译单元列表。请求 MAY 包含 include/exclude、规则配置、资源预算和抑制项，但未知必填语义或不受支持的主版本 MUST 被拒绝。

#### Scenario: 有效请求
- **WHEN** 请求字段、schema 主版本、profile 和所有路径均有效
- **THEN** 扫描器创建一次具有同一 `request_id` 的扫描，并在结果中回显规范化配置摘要

#### Scenario: 不支持的主版本
- **WHEN** `schema_version` 的主版本不受支持
- **THEN** 扫描器拒绝请求，返回 `invalid_request`，并输出可机器识别的版本诊断

### Requirement: 稳定且双语的结果协议
扫描结果 SHALL 为版本化 JSON 文档，包含 `kind`、`schema_version`、`analysis_version`、`request_id`、`status`、`summary`、`findings`、`diagnostics` 和 `metadata`。所有用户可见的 finding 标题、说明和修复建议 MUST 同时提供中文与英文字段，例如 `title`/`title_en`、`message`/`message_en`、`suggestion`/`suggestion_en`。

#### Scenario: 完整扫描结果
- **WHEN** 所有计划翻译单元和启用规则的必需 assessment 均完成，且不存在阻断规则判断的 unresolved unknown
- **THEN** `status` 为 `complete`，摘要分母与 finding、diagnostic、suppressed、unknown 计数一致；非阻断且未被规则消费的 profile 可选字段可以保持 unknown

#### Scenario: 双语字段完整
- **WHEN** 任意 finding 被发布
- **THEN** 该 finding 同时包含非空中文和英文字段，且两种语言描述同一证据、影响与建议

### Requirement: Finding 结构可定位且可去重
每条 finding SHALL 包含稳定 `finding_id`、`finding_code`、`rule_version`、`category`、`severity`、`confidence`、`requires_human_confirmation`、主源码位置、相关位置、证据、影响和测试建议。`finding_id` MUST 由规则、规范化位置和语义指纹稳定生成，且不得依赖扫描顺序或绝对工作区路径。

#### Scenario: 相同输入重复扫描
- **WHEN** 相同源码、编译上下文、profiles 与规则版本被重复扫描
- **THEN** finding 集合、`finding_id` 和规范化排序保持一致，不受并发调度影响

#### Scenario: 同一风险跨多个位置
- **WHEN** 一个 ABI 或配置风险关联多个声明或翻译单元
- **THEN** 结果发布一个主 finding，并使用 `related_locations` 保留所有已确认关联位置，避免仅按文本重复报告

### Requirement: 明确状态与退出码映射
CLI SHALL 使用固定退出码：`0` 表示 `complete`，`2` 表示 `invalid_request`，`3` 表示无可用结果的 `failed`，`4` 表示 `partial`，`5` 表示 `internal_error`。发现任意数量的浮点风险本身 MUST NOT 改变退出码；CI 是否因风险失败由独立策略层决定。

#### Scenario: 扫描发现高风险项
- **WHEN** 扫描完整结束且存在 `critical` 或 `high` finding
- **THEN** 结果 `status` 仍为 `complete` 且退出码为 `0`，风险数量通过摘要和 finding 表达

#### Scenario: 部分扫描
- **WHEN** 至少一个翻译单元或必需 assessment 完成，且至少一个计划翻译单元或启用规则的必需 assessment 未完成
- **THEN** 结果 `status` 为 `partial`、退出码为 `4`，并公开 planned/completed/failed 分母

### Requirement: 输出应确定、原子且可审计
扫描器 SHALL 规范化路径分隔符、按稳定键排序集合、避免时间戳参与语义摘要，并通过临时文件加原子替换发布文件结果。默认输出 MUST NOT 暴露环境变量值、凭据或项目根外的绝对路径。

#### Scenario: 写出过程被中断
- **WHEN** 进程在结果序列化或文件替换前异常终止
- **THEN** 既有有效结果不被截断，新结果不会以完整文件名呈现为可用产物
