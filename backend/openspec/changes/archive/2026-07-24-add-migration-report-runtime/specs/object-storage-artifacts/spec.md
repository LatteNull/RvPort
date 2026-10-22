## MODIFIED Requirements

### Requirement: 后端生成制品必须保存统一元数据
#### Scenario: 保存迁移评估报告输出制品
- **WHEN** 迁移评估报告生成 HTML 或 JSON 输出
- **THEN** 后端 SHALL 使用 `stored_artifacts` 或等效元数据记录保存报告输出制品元数据
- **AND** `owner_type` SHALL 为 `MIGRATION_REPORT`
- **AND** `owner_id` SHALL 为 `reports.id`
- **AND** `artifact_type` SHALL 区分 HTML 报告和 JSON 报告
- **AND** API 响应 MUST NOT 返回 `bucket`、`object_key` 或服务器真实路径

### Requirement: 对象存储写入必须保持元数据一致性
#### Scenario: 迁移评估报告制品保存失败
- **WHEN** 迁移评估报告 HTML 或 JSON 对象上传、元数据写入或报告状态更新失败
- **THEN** 后端 SHALL 将报告生成视为失败
- **AND** 后端 SHALL 尽力删除本次已经上传的报告对象
- **AND** 后端 MUST NOT 留下指向不存在对象的成功报告元数据
