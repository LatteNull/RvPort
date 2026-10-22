## Why

当前主 spec 全量严格校验中有 5 个能力因为 `Purpose` 过短产生 warning，导致 `openspec validate --specs --strict` 不能干净通过。需要补充这些能力的目的说明，避免后续全量校验时混入已知噪声。

## What Changes

- 扩展 `backend-database-design`、`kb-scan-runtime`、`migration-report-runtime`、`running-task-cancellation` 和 `test-support-api` 的 `Purpose` 描述。
- 保持现有 requirement 和 scenario 不变。
- 不修改后端运行时代码、数据库 schema、API 或测试逻辑。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `backend-database-design`: 补充数据库设计能力的边界、数据安全和查询支撑说明。
- `kb-scan-runtime`: 补充知识库扫描运行时的输入、执行、输出和代码上下文边界说明。
- `migration-report-runtime`: 补充迁移评估报告生成、制品存储和下载边界说明。
- `running-task-cancellation`: 补充运行中任务取消的状态、队列和资源清理边界说明。
- `test-support-api`: 补充测试辅助 API 的构建隔离、安全边界和 E2E 使用边界说明。

## Impact

- 仅影响 OpenSpec 文档。
- 预期结果是主 spec 严格校验不再因为 Purpose 过短失败。
