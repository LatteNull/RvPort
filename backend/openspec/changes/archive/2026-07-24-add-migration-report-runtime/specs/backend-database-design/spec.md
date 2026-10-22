## ADDED Requirements

### Requirement: 报告表必须绑定源码版本
数据库 SHALL 支持将迁移评估报告显式绑定到生成时使用的源码版本。

#### Scenario: 保存报告源码版本
- **WHEN** 后端创建新的迁移评估报告记录
- **THEN** `reports.source_revision_id` SHALL 保存生成报告使用的 `source_revisions.id`
- **AND** `reports.source_revision_id` SHALL 作为外键引用 `source_revisions(id)`
- **AND** 新报告记录的 `source_revision_id` MUST NOT 为空

#### Scenario: 查询源码版本报告
- **WHEN** 后端按项目和源码版本查询报告列表或最新报告
- **THEN** 数据库 SHALL 提供 `reports(project_id, source_revision_id, generated_at desc)` 或等效索引

### Requirement: 报告输入表必须保存迁移输入快照
数据库 SHALL 使用 `report_inputs` 保存报告生成时使用的迁移输入引用和快照。

#### Scenario: 保存迁移输入引用
- **WHEN** 报告生成使用一条迁移输入 reference
- **THEN** `report_inputs.input_type` SHALL 保存 `MIGRATION_INPUT_REF`
- **AND** `report_inputs.input_id` SHALL 保存 `migration_input_refs.id`
- **AND** `report_inputs.input_snapshot` SHALL 保存生成时的结构化快照

#### Scenario: 查询报告输入
- **WHEN** 后端查询某个报告的输入快照
- **THEN** 数据库 SHALL 能通过 `report_inputs.report_id` 高效查询
- **AND** 数据库 SHALL 能通过 `report_inputs(input_type, input_id)` 追溯输入来源

### Requirement: 报告输出制品必须使用对象存储元数据
数据库 SHALL 使用统一输出制品元数据记录迁移评估报告 HTML 和 JSON 输出位置，避免在报告业务表中保存大文件内容。

#### Scenario: 保存报告输出制品元数据
- **WHEN** 报告生成成功
- **THEN** 后端 SHALL 写入 `stored_artifacts` 元数据记录 HTML 报告制品
- **AND** 后端 SHALL 写入 `stored_artifacts` 元数据记录 JSON 报告制品
- **AND** `owner_type` SHALL 为 `MIGRATION_REPORT`
- **AND** `owner_id` SHALL 为 `reports.id`
- **AND** API MUST NOT 直接暴露 `bucket`、`object_key` 或服务器真实路径

#### Scenario: 历史路径字段兼容
- **WHEN** 数据库中存在历史 `reports.html_path` 或 `reports.json_path`
- **THEN** 这些字段 MAY 仅作为后端内部兼容读取字段
- **AND** 新生成报告 SHALL 优先使用 `stored_artifacts` 表达输出制品
