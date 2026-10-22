## 1. 报告生成状态可靠性

- [x] 1.1 拆分 `ReportRuntimeService.generate` 的事务边界，避免完整报告生成流程处于单个大事务中
- [x] 1.2 增加报告状态独立写入能力，确保 `RUNNING`、`FAILED`、`CANCELLED`、`SUCCEEDED` 不被后续异常回滚
- [x] 1.3 在报告生成失败时写入脱敏 summary，包含 `errorCode`、`failureStage`、`causeClass` 和安全错误摘要
- [x] 1.4 确认没有 confirmed 输入时报告状态进入 `FAILED`，且不生成空报告 artifact

## 2. 归档候选摘要安全化

- [x] 2.1 为迁移评估报告创建专用归档候选 summary 构造逻辑，只包含聚合统计和报告引用
- [x] 2.2 从迁移报告归档候选 summary 中移除 `priorityIssues`、`dependencySubstitutionNotes`、`locationLabel`、`evidence`、`sourceDetail` 等明细字段
- [x] 2.3 确保报告 HTML/JSON artifact 和 `report_inputs` 仍保留完整报告明细
- [x] 2.4 调整归档候选登记失败处理，避免候选登记异常反向破坏已成功生成的报告

## 3. 任务失败可观测性

- [x] 3.1 修改 worker 对包含 cause 的 `TaskExecutionException` 日志输出，保留脱敏后的 cause stack
- [x] 3.2 为 `REPORT_GENERATE` 增加阶段标记，区分输入读取、快照写入、报告渲染、artifact 保存和归档候选登记失败
- [x] 3.3 确保任务错误摘要、任务事件和报告失败 summary 不暴露明文凭据、对象存储 key、完整输入快照或服务器敏感路径

## 4. 测试与验证

- [x] 4.1 增加报告生成成功路径测试，验证 `reports`、`report_inputs`、`stored_artifacts` 和归档候选均正确写入
- [x] 4.2 增加包含 `include:../include` 迁移输入的测试，验证报告生成成功且归档候选 summary 不包含该明细文本
- [x] 4.3 增加报告生成失败路径测试，验证报告状态进入 `FAILED` 且任务状态一致
- [x] 4.4 增加 worker 日志或错误处理测试，验证包含 cause 的 `TaskExecutionException` 可观测性
- [x] 4.5 运行 Maven 单元测试和相关 E2E 模块
- [x] 4.6 使用 `test` 项目真实数据重新生成迁移评估报告，确认报告成功、artifact 可下载、归档候选可查询
