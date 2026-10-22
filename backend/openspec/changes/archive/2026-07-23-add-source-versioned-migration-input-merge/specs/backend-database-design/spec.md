## ADDED Requirements

### Requirement: 数据库必须持久化源码版本迁移输入集合
数据库 SHALL 提供迁移输入集合表，用于表达一个源码版本下的一组迁移输入 reference。

#### Scenario: 创建迁移输入集合表
- **WHEN** 执行数据库迁移
- **THEN** Schema SHALL 创建 `migration_input_sets` 表
- **AND** 表 SHALL 包含 `id`、`project_id`、`source_revision_id`、`status`、`created_at` 和 `updated_at`
- **AND** `project_id` SHALL 引用 `projects.id`
- **AND** `source_revision_id` SHALL 引用 `source_revisions.id`
- **AND** `status` SHALL 至少支持 `ACTIVE` 和 `ARCHIVED`

#### Scenario: 限制源码版本唯一集合
- **WHEN** 创建或维护 `migration_input_sets`
- **THEN** 数据库 SHALL 防止同一 `source_revision_id` 出现多个 active 迁移输入集合
- **AND** 数据库 SHALL 支持按 `project_id, source_revision_id` 查询集合

### Requirement: 数据库必须持久化迁移输入 reference 列表
数据库 SHALL 提供迁移输入 reference 表，用于统一展示候选问题并引用真实来源记录。

#### Scenario: 创建迁移输入 reference 表
- **WHEN** 执行数据库迁移
- **THEN** Schema SHALL 创建 `migration_input_refs` 表
- **AND** 表 SHALL 包含 `id`、`input_set_id`、`project_id`、`source_revision_id`、`issue_title`、`source_type`、`source_ref_id`、`detected_level`、`location_label`、`recommendation_summary`、`status`、`note`、`created_at` 和 `updated_at`
- **AND** `input_set_id` SHALL 引用 `migration_input_sets.id`
- **AND** `project_id` SHALL 引用 `projects.id`
- **AND** `source_revision_id` SHALL 引用 `source_revisions.id`

#### Scenario: 限制 reference 状态
- **WHEN** 创建或更新 `migration_input_refs`
- **THEN** `status` SHALL 只允许 `CANDIDATE`、`CONFIRMED` 或 `EXCLUDED`

#### Scenario: 防止重复导入
- **WHEN** 同一迁移输入集合中导入相同 `source_type` 和 `source_ref_id`
- **THEN** 数据库 SHALL 通过唯一约束或等效机制防止重复 reference

#### Scenario: 索引迁移输入列表查询路径
- **WHEN** 创建 `migration_input_refs`
- **THEN** 数据库 SHALL 为 `project_id, source_revision_id, created_at desc` 建立索引
- **AND** 数据库 SHALL 为 `project_id, source_revision_id, source_type` 建立索引
- **AND** 数据库 SHALL 为 `project_id, source_revision_id, status` 建立索引
- **AND** 数据库 SHALL 为 `project_id, source_revision_id, detected_level` 建立索引

#### Scenario: 多来源引用由服务层校验
- **WHEN** `migration_input_refs.source_ref_id` 指向不同来源表
- **THEN** 数据库 MAY 不为 `source_ref_id` 创建单一外键
- **AND** 服务层 MUST 按 `source_type` 校验真实来源记录存在、项目归属和源码版本约束
