## Why

当前 worker 已经能认领任务并分发 handler，但 handler 只能读取原始输入快照并返回完成消息，缺少统一的进度、事件、日志和输入解析能力。接下来要接入真实 SSH、Git 同步和远程脚本任务，先补齐任务执行上下文可以避免每个业务 handler 重复实现日志、脱敏、状态推进和错误处理。

## What Changes

- 为任务 handler 引入统一执行上下文，使 handler 通过上下文读取任务、解析输入、更新进度、追加事件和写入任务日志。
- 扩展 worker 调用模型，让 `TaskWorkerService` 在认领任务后创建执行上下文并传给 handler。
- 增加任务日志写入能力，支持 stdout、stderr、combined 或 tool 日志落本地文件并登记 `task_logs` 元数据。
- 规范日志摘要事件：上下文可以追加短摘要到 `task_events`，但不得把完整日志、明文凭据或服务器真实路径放入 SSE 事件。
- 规范进度更新：上下文统一校验 0 到 100 的进度边界，并同步更新 `tasks.progress`、`tasks.message` 和 `task.progress` 事件。
- 保持任务队列消息和 API 响应安全边界不变：队列仍只投递任务 ID 等路由信息，API 仍不暴露输入快照和本地路径。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `task-runtime`: 增强 worker handler 执行模型，补充任务执行上下文、进度更新、日志写入和安全输入解析要求。

## Impact

- 影响后端 worker 主干：`TaskHandler`、`TaskWorkerService`、handler 注册和相关单元测试。
- 影响任务日志能力：需要为 worker 侧新增受控日志文件创建和 `task_logs` 元数据写入入口。
- 影响后续 SSH、Git、环境采集、远程脚本等任务 handler 的接入方式。
- 不新增 HTTP API，不修改数据库 schema；复用既有 `tasks`、`task_events` 和 `task_logs` 表。
