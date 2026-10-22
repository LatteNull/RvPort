## Context

当前任务运行时已经具备任务创建、队列投递、worker 认领、handler 分发、任务事件和 SSE 推送能力。但现有 `TaskHandler` 接口只接收 `TaskView` 与原始 `JSONB inputSnapshot`，并只能返回 `TaskHandlerResult.message`。这对后续真实任务不够用：SSH 连通性测试、Git 同步、远程脚本执行和环境采集都需要统一解析输入、更新进度、追加事件、写本地日志并登记 `task_logs`。

本 change 聚焦任务执行器能力，不实现真实 SSH 连接、Git clone、环境采集或远程脚本执行。

## Goals / Non-Goals

**Goals:**

- 为业务 handler 提供统一 `TaskExecutionContext`，封装任务元数据、输入解析、进度更新、事件追加和日志写入。
- 让 worker 在认领任务后创建执行上下文，并通过上下文调用 handler。
- 新增受控任务日志写入能力，日志文件落在 `RVPORT_LOG_DIR` 下，数据库只保存相对路径或受控路径信息。
- 保证日志摘要、事件、API 响应和队列消息不泄露明文凭据、完整日志或服务器真实路径。
- 为后续 SSH/Git handler 提供可复用基础，不在每个 handler 中重复写进度和日志样板代码。

**Non-Goals:**

- 不实现 SSH 客户端、跳板机连接、Git clone/fetch 或远程命令执行。
- 不新增 HTTP API。
- 不修改数据库 schema，复用已有 `tasks`、`task_events` 和 `task_logs`。
- 不改变 RabbitMQ 消息格式，队列仍只承载任务 ID 等路由信息。
- 不实现运行中任务强制中止。

## Decisions

### 1. 使用 `TaskExecutionContext` 作为 handler 的唯一入口

将 handler 从直接接收 `TaskView` 和 `JSONB` 调整为接收执行上下文。上下文提供：

- `task()`：当前任务只读视图。
- `input(Class<T>)` 或等价方法：安全解析输入快照。
- `progress(int, String)`：更新 `tasks.progress/message` 并追加 `task.progress` 事件。
- `log(TaskLogType, String)` 或等价方法：写入日志文件、登记 `task_logs`，并追加可展示短摘要事件。
- `event(...)`：追加非状态型事件或工具摘要。

选择该方案，是因为后续 SSH/Git/脚本 handler 都需要同一组能力。相比继续扩展 `TaskHandlerResult`，上下文可以支持处理过程中的多次进度和日志写入，而不是等 handler 结束后一次性返回。

### 2. worker 负责创建上下文，handler 不直接依赖底层仓储

`TaskWorkerService` 在任务认领成功后创建上下文，并传给 handler。上下文内部组合 `TaskRepository`、`TaskEventService`、`TaskLogRepository`、日志根目录配置和 JSON 解析能力。

handler 可以依赖业务服务，但不应直接操作任务状态表。这样任务状态流转仍集中在任务运行时，避免不同 handler 对 `tasks`、`task_events` 和 `task_logs` 使用不一致。

### 3. 日志落本地文件，事件只放短摘要

完整 stdout/stderr/tool 输出写入 `RVPORT_LOG_DIR` 下的任务专属目录，例如按项目、任务 ID 和日期组织。`task_logs.file_path` 保存受控相对路径或可由 `TaskLogService` 安全解析的路径。`task_events.log_excerpt` 只保存短摘要，必须截断并做基础脱敏。

这样既满足前端实时查看进展，又避免 SSE 事件、API 响应或数据库事件表承载大量日志内容。

### 4. 输入解析失败作为任务失败处理

如果 handler 通过上下文解析 input snapshot 失败，worker 应将任务标记为 `FAILED`，错误码使用明确的任务输入错误码，并追加失败事件。失败消息必须是安全摘要，不包含原始 input snapshot。

### 5. 进度边界由上下文统一校验

上下文 SHALL 限制进度值在 0 到 100 之间。非法进度由上下文拒绝并使任务失败，避免 handler 把任务推进到不可展示状态。终态成功仍由 worker 统一设置为 100。

## Risks / Trade-offs

- [Risk] 修改 `TaskHandler` 接口会影响现有测试和后续 handler 接入方式。  
  Mitigation: 当前尚无真实业务 handler，迁移成本低；同步更新 worker 单元测试和注册测试。

- [Risk] 日志写入失败可能让业务任务本身失败。  
  Mitigation: MVP 中日志是任务可观测性的关键部分，日志无法可靠写入时应失败并给出安全错误摘要；后续可引入降级策略。

- [Risk] 日志摘要脱敏无法覆盖所有业务秘密格式。  
  Mitigation: 默认禁止 handler 把明文凭据写入日志；上下文做基础关键词脱敏和长度截断，SSH/Git change 再针对具体凭据增加测试。

- [Risk] 上下文能力过大可能变成通用杂物入口。  
  Mitigation: 本 change 只纳入任务元数据、输入解析、进度、事件和日志，不把 SSH/Git/文件传输等业务能力放入上下文本身。

## Migration Plan

1. 新增 `TaskExecutionContext` 及默认实现。
2. 新增任务日志写入入口，复用现有 `TaskLogService` 下载安全边界。
3. 调整 `TaskHandler` 接口和 `TaskWorkerService` 调用路径。
4. 更新现有 worker 测试，补充正常流程、异常流程和 edge case。
5. 运行受影响测试和完整 `mvn test`。

回滚时可恢复旧 `TaskHandler` 接口和 worker 调用路径；由于不修改数据库 schema，回滚不需要数据迁移。

## Open Questions

- 日志文件目录最终是否按 `projectId/taskId` 还是按日期优先组织？实现时应选择便于清理和下载校验的结构。
- 日志摘要截断长度采用多少字符合适？MVP 可先使用固定上限，后续根据前端展示再调整。
