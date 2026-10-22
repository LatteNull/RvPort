## ADDED Requirements

### Requirement: 数据库必须保存优化轮次记录
数据库 SHALL 使用 `optimization_cycles` 表保存项目优化轮次边界，并 SHALL 通过约束保证同一项目同一源码版本只有一个优化轮次。

#### Scenario: 保存优化轮次基础字段
- **WHEN** 后端创建优化轮次
- **THEN** `optimization_cycles` SHALL 保存 `id`、`project_id`、`source_revision_id`、`cycle_number`、`status`、`summary`、`started_at`、`completed_at`、`created_at` 和 `updated_at`
- **AND** `project_id` SHALL 外键引用 `projects.id`
- **AND** `source_revision_id` SHALL 外键引用 `source_revisions.id`

#### Scenario: 约束优化轮次唯一性
- **WHEN** 后端保存优化轮次
- **THEN** 数据库 SHALL 使用唯一约束保证 `(project_id, source_revision_id)` 不重复
- **AND** 数据库 SHALL 使用唯一约束保证 `(project_id, cycle_number)` 不重复

#### Scenario: 优化轮次索引
- **WHEN** 查询项目优化轮次列表或当前轮次
- **THEN** 数据库 SHALL 提供 `project_id, cycle_number desc` 索引
- **AND** 数据库 SHALL 提供 `project_id, status` 索引
- **AND** 数据库 SHALL 提供 `source_revision_id` 索引

#### Scenario: 优化轮次摘要不保存大内容
- **WHEN** 后端写入 `optimization_cycles.summary`
- **THEN** 摘要 SHALL 只保存安全聚合信息和资源 ID
- **AND** 数据库 MUST NOT 在该字段保存完整日志、完整报告正文、完整 agent 输入、明文凭据或对象存储内部 key
