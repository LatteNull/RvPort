## Why

Worker 失联清理目前只结束 Task，关联的分析运行记录仍可能为 RUNNING，导致 latest 执行状态与 overview 不一致，旧活动记录还会遮住后续结果。旧 Worker 恢复后的完成、重试及业务写入也缺少统一终态保护，需要同时修复状态一致性和历史遗留记录。

## What Changes

- 在确认 Worker 失联时，事务内同步 Task、关联非终态业务运行记录和执行记录，保存 WORKER_LOST、结束时间及脱敏原因。
- 按任务类型注册领域收尾适配器，盘点并覆盖分析、构建、测试、报告等现有异步任务，不依赖失联进程中的 handler 回调。
- 对执行归属、尝试身份和终态实施数据库条件写入保护，防止迟到 Worker 发布结果、恢复重试或覆盖终态；保留正常重试语义。
- 增加有界、幂等的历史对账，修复已失败/取消/超时 Task 关联的非终态记录，不篡改已完成结果。
- 保持现有接口结构，通过真实落库状态统一 latest、overview 和提交后 SSE；不以展示层兜底替代修复。
- 补充正常、异常、边界及并发单测，Linux Docker 验证整体和受影响模块行/分支覆盖率至少 90%，并验证分离 API/Worker 链路。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `worker-observability`：确认失联时同步领域运行终态，并对历史失联残留提供有界对账。
- `task-runtime`：约束执行归属、迟到写入、正常重试及终态通知的一致性。

## Impact

- 仅修改 backend，涉及 WorkerCleanupItemService、TaskWorkerService、TaskRepository、runtime handle、各领域运行仓储和结果发布事务、测试与中文文档。
- 如需执行尝试关联字段或索引，使用 Liquibase 迁移并同步 jOOQ，不手工建表；复用 PostgreSQL 与现有事件广播，不新增基础设施。
- 不改前端、扫描工具、风险判断或业务 API 响应结构；不自动重新执行失联任务，不宣称远端进程已经停止。
- 不新增报告类型；沿用现有报告归档登记，阻止无效执行尝试发布新的当前结果和归档候选。
