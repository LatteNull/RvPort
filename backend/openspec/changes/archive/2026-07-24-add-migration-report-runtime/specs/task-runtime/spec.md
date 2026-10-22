## ADDED Requirements

### Requirement: 任务运行时必须支持迁移报告生成任务
任务运行时 SHALL 支持 `REPORT_GENERATE` 任务类型，用于异步生成迁移评估报告。

#### Scenario: 创建报告生成任务
- **WHEN** 报告 API 创建迁移评估报告
- **THEN** 后端 SHALL 创建类型为 `REPORT_GENERATE` 的任务
- **AND** `tasks.input_snapshot` SHALL 包含 `projectId`、`sourceRevisionId` 和 `reportId`
- **AND** 输入快照 MUST NOT 包含服务器真实报告路径或未脱敏的敏感信息

#### Scenario: 报告任务状态推送
- **WHEN** 报告生成任务进入 `QUEUED`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED` 或 `TIMEOUT`
- **THEN** 任务运行时 SHALL 追加对应任务事件
- **AND** 项目级 SSE SHALL 只向该报告所属项目推送事件

#### Scenario: 报告任务失败
- **WHEN** 报告生成 handler 因没有 confirmed 输入、报告制品保存失败或快照写入失败而失败
- **THEN** 任务运行时 SHALL 将任务标记为 `FAILED`
- **AND** 任务错误摘要 SHALL 使用脱敏后的业务错误信息

#### Scenario: 取消报告生成任务
- **WHEN** 用户取消尚未完成的 `REPORT_GENERATE` 任务
- **THEN** 任务运行时 SHALL 按现有取消机制更新任务状态
- **AND** 报告记录 SHALL 最终进入 `CANCELLED` 或与任务终态一致的状态
