## ADDED Requirements

### Requirement: 任务失败必须保留脱敏 root cause
任务运行时 SHALL 在 handler 抛出包含 cause 的业务异常时记录脱敏后的 root cause 信息，使后端日志和任务错误摘要能定位实际失败阶段，同时不泄露敏感信息。

#### Scenario: TaskExecutionException 包含 cause
- **WHEN** worker 捕获到包含 cause 的 `TaskExecutionException`
- **THEN** 后端日志 SHALL 记录任务 ID、任务类型、业务错误码、脱敏业务消息和 cause stack
- **AND** 日志 MUST NOT 包含明文凭据、私钥、token、完整任务输入快照或服务器敏感路径

#### Scenario: 任务失败摘要包含诊断字段
- **WHEN** 任务因 handler 异常进入 `FAILED`
- **THEN** `tasks.error_code` SHALL 保存稳定业务错误码
- **AND** `tasks.error_message` SHALL 保存脱敏后的用户可展示摘要
- **AND** 任务事件或关联业务记录 MAY 保存脱敏后的 `failureStage`、`causeClass` 和 `causeMessage`
- **AND** 这些诊断字段 MUST NOT 暴露明文凭据、私钥、token、完整命令、完整日志或服务器真实路径

#### Scenario: REPORT_GENERATE 失败可定位阶段
- **WHEN** `REPORT_GENERATE` 任务在输入读取、快照写入、报告渲染、artifact 保存或归档候选登记阶段失败
- **THEN** 任务失败摘要或后端日志 SHALL 能区分失败阶段
- **AND** 任务运行时 SHALL 保持任务和报告记录的终态一致
