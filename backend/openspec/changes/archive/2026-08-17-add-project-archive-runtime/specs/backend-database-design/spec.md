## ADDED Requirements

### Requirement: 数据库必须保存待归档候选
数据库 SHALL 使用 `archive_candidates` 表保存当前源码版本下可归档内容的最新引用，使归档运行时可以按候选表生成快照。

#### Scenario: 创建待归档候选表
- **WHEN** 执行数据库迁移
- **THEN** Schema SHALL 创建 `archive_candidates` 表
- **AND** 表 SHALL 包含 `id`、`project_id`、`source_revision_id`、`node_type`、`candidate_type`、`candidate_key`、`resource_type`、`resource_id`、`title`、`summary`、`artifact_refs`、`status`、`created_at` 和 `updated_at`
- **AND** `project_id` SHALL 外键引用 `projects.id`
- **AND** `source_revision_id` SHALL 外键引用 `source_revisions.id`

#### Scenario: 候选唯一槽位
- **WHEN** 后端登记待归档候选
- **THEN** 数据库 SHALL 使用唯一约束保证 `(project_id, source_revision_id, node_type, candidate_type, candidate_key)` 不重复
- **AND** 后端 SHALL 通过 upsert 更新同一槽位的最新候选

#### Scenario: 候选状态约束
- **WHEN** 创建或更新待归档候选
- **THEN** `status` SHALL 只允许 `ACTIVE`、`SUPERSEDED` 或 `DELETED`
- **AND** 当前状态归档 SHALL 只读取 `ACTIVE` 候选

#### Scenario: 候选查询索引
- **WHEN** 后端创建归档或查询当前候选
- **THEN** 数据库 SHALL 支持按 `project_id, source_revision_id, status` 查询
- **AND** 数据库 SHALL 支持按 `project_id, source_revision_id, node_type, candidate_type` 查询

#### Scenario: 候选内容安全
- **WHEN** 后端保存 `summary` 或 `artifact_refs`
- **THEN** 数据库 MUST NOT 在候选表中保存完整日志、完整报告正文、完整 agent 输入、明文凭据、对象存储 object key 或服务器真实路径
- **AND** `artifact_refs` SHALL 通过 `storedArtifactId` 或受控业务资源 ID 引用内容

### Requirement: 归档记录必须绑定源码版本
数据库 SHALL 使每条归档记录明确绑定创建归档时使用的源码版本。

#### Scenario: 保存归档源码版本
- **WHEN** 后端创建归档记录
- **THEN** `archives` SHALL 保存 `source_revision_id`
- **AND** `source_revision_id` SHALL 外键引用 `source_revisions.id`
- **AND** 归档记录 SHALL 保存创建时的项目 active 源码版本 ID

#### Scenario: 查询源码版本归档
- **WHEN** 后端查询项目归档列表
- **THEN** 数据库 SHALL 支持按 `project_id, source_revision_id, created_at desc` 查询
- **AND** 数据库 SHALL 支持按 `project_id, status, created_at desc` 查询

### Requirement: 归档项必须固化候选快照
数据库 SHALL 使用 `archive_items` 保存归档创建时的候选快照，而不是在查询历史归档时读取当前候选状态。

#### Scenario: 保存归档项候选快照
- **WHEN** 后端创建归档项
- **THEN** `archive_items` SHALL 保存 `candidate_id`、`node_type`、`candidate_type`、`candidate_key`、`resource_type`、`resource_id`、`title`、`artifact_refs` 和 `metadata`
- **AND** `candidate_id` MAY 引用 `archive_candidates.id`
- **AND** `metadata` SHALL 保存创建归档时的安全摘要快照

#### Scenario: 归档项查询索引
- **WHEN** 后端查询归档详情
- **THEN** 数据库 SHALL 支持按 `archive_id` 查询归档项
- **AND** 数据库 SHALL 支持按 `archive_id, node_type, candidate_type` 查询归档项

#### Scenario: 归档项安全
- **WHEN** 后端保存归档项 metadata 或 artifact refs
- **THEN** 数据库 MUST NOT 保存明文凭据、对象存储 object key、服务器真实路径或完整任务输入快照
