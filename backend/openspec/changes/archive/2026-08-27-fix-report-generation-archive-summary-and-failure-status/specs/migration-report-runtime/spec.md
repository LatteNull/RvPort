## ADDED Requirements

### Requirement: 迁移评估报告失败必须可靠写入报告终态
迁移评估报告运行时 SHALL 保证报告生成任务失败、取消或成功时，`reports.status` 与任务终态保持一致或能表达同等终态，不得因报告生成内部事务回滚使报告长期停留在 `PENDING` 或 `RUNNING`。

#### Scenario: 报告生成过程中发生运行时异常
- **WHEN** `REPORT_GENERATE` handler 在读取输入、写入快照、生成内容、保存制品或登记附加索引阶段发生运行时异常
- **THEN** 后端 SHALL 将对应 `reports.status` 写为 `FAILED`
- **AND** `reports.summary` SHALL 包含脱敏后的错误码、错误阶段和错误摘要
- **AND** 任务 SHALL 进入 `FAILED`
- **AND** 报告状态写入 MUST NOT 被报告生成主事务回滚

#### Scenario: 报告生成任务被取消
- **WHEN** `REPORT_GENERATE` handler 检测到任务取消
- **THEN** 后端 SHALL 将对应 `reports.status` 写为 `CANCELLED`
- **AND** 任务 SHALL 进入 `CANCELLED`
- **AND** 报告状态写入 MUST NOT 被报告生成主事务回滚

#### Scenario: 没有确认输入导致失败
- **WHEN** 报告生成任务发现当前源码版本没有 `CONFIRMED` 迁移输入
- **THEN** 后端 SHALL 将对应 `reports.status` 写为 `FAILED`
- **AND** 错误码 SHALL 为 `REPORT_NO_CONFIRMED_INPUTS`
- **AND** 后端 MUST NOT 生成空报告 artifact

### Requirement: 迁移评估报告归档候选必须使用安全聚合摘要
迁移评估报告运行时 SHALL 在成功生成报告后登记归档候选，但候选 summary MUST 只包含安全聚合信息和报告引用，完整报告明细 SHALL 通过报告 artifact 和 `report_inputs` 快照保存。

#### Scenario: 报告明细包含路径逃逸文本
- **WHEN** confirmed migration input 中存在 `include:../include` 或其他包含 `../` 的报告明细文本
- **THEN** 报告 HTML 和 JSON artifact SHALL 能正常包含该报告明细
- **AND** 归档候选 summary MUST NOT 保存该明细文本
- **AND** 归档候选登记 MUST NOT 因该明细文本失败

#### Scenario: 报告成功后登记归档候选
- **WHEN** 迁移评估报告成功生成 HTML 和 JSON artifact
- **THEN** 后端 SHALL 登记当前项目和源码版本下的迁移报告归档候选
- **AND** 候选 summary SHALL 至少包含报告 ID、风险等级、confirmed 输入数量、高风险数量、工作量估算、来源统计和风险统计
- **AND** 候选 SHALL 包含 HTML 和 JSON artifact 引用

#### Scenario: 归档候选登记异常
- **WHEN** 报告 artifact 已保存且 `reports.status` 已写入 `SUCCEEDED`
- **AND** 归档候选登记发生异常
- **THEN** 后端 MUST NOT 将已成功生成的报告回滚为失败
- **AND** 后端 SHALL 写入脱敏 warning 日志或任务日志摘要，说明归档候选登记失败
