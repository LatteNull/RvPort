## Context

RvPort 后端已经具备 Spring Boot 工程骨架、Liquibase schema、jOOQ 生成代码、Redis Session、RabbitMQ 任务投递客户端和本地用户认证。数据库中已经存在 `tasks`、`task_events`、`task_logs` 和 `tool_runs`，RabbitMQ 任务队列已经声明为 durable quorum queue，listener ack mode 已配置为 manual。

当前缺口是所有长任务共享的运行时主干。后续 KB 扫描、SBOM 分析、环境采集、远程脚本、报告生成、复检、构建、测试和归档都需要复用同一套任务生命周期、队列消费、事件推送和日志访问模型。

约束：

- PostgreSQL 是任务状态、任务事件、日志元数据和业务结果的事实来源。
- RabbitMQ 只递送任务 ID 和必要路由信息，不能承载任务输入、状态、进度、结果或完整日志。
- Redis 不保存权威任务状态。
- 完整 stdout/stderr 日志保存在本地文件系统，数据库只保存元数据和摘要。
- MVP 使用项目级 SSE，不使用 WebSocket。

## Goals / Non-Goals

**Goals:**

- 提供统一任务创建服务，所有业务长任务通过同一入口创建 `tasks`、追加初始 `task_events` 并投递 RabbitMQ。
- 提供 worker 消费主干，支持按任务类型分发到 handler，并通过手动 ack 与 PostgreSQL 状态写回建立可靠边界。
- 提供任务状态机推进能力，覆盖 `PENDING`、`QUEUED`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED` 和 `TIMEOUT`。
- 提供项目级 SSE，支持实时推送、心跳和 `Last-Event-ID` 断线恢复。
- 提供任务详情、项目任务列表、取消任务、日志分页和日志下载基础 API。
- 提供投递失败修复机制，避免任务已入库但队列消息丢失后永久停滞。

**Non-Goals:**

- 不在本 change 中实现 KB 扫描、SBOM、构建、测试、报告或归档的具体业务 handler。
- 不实现运行中远程进程的强制终止；MVP 只可靠取消尚未开始执行的任务。
- 不引入通用 artifact API。
- 不把完整日志行落入 `task_events`。
- 不引入分布式 SSE fanout；多 API 实例实时广播可在后续通过 Redis Pub/Sub 或 RabbitMQ 扩展。

## Decisions

### 1. SSE 协议层 ID 使用 `task_events.id`

`task_events` 已经包含 `id bigserial primary key` 和 `event_id text unique`。SSE 的 `id:` SHALL 使用递增的 `task_events.id`，`event_id` 继续作为业务追踪字段返回在事件 data 中。

原因：

- `Last-Event-ID` 可以直接按 `project_id` 和 `id > lastEventId` 查询。
- 避免使用字符串业务 ID 做排序和游标比较。
- 与现有 `task_events_project_id_idx(project_id, id)` 索引匹配。

备选方案：

- 使用 `event_id text` 作为 SSE ID。该方案不适合作为恢复游标，需要额外解析或映射。
- 新增专用 `sse_sequence` 字段。当前 `id bigserial` 已满足需求，暂不新增。

### 2. 任务创建采用 PENDING 修复策略，而不是立刻引入 outbox

任务创建流程：

```text
事务内:
  ├─ insert tasks(status=PENDING)
  └─ insert task_events(task.created)

事务提交后:
  ├─ publish TaskQueueMessage(taskId, taskType, projectId)
  ├─ update tasks(status=QUEUED, queued_at=now())
  └─ insert task_events(task.queued)
```

如果事务提交后服务中断或 RabbitMQ 临时不可用，任务会停留在 `PENDING`。任务投递修复器定期扫描超过短暂宽限时间的 `PENDING` 任务并重新投递。

原因：

- 符合“先写 PostgreSQL，再投递队列”的既有边界。
- 不需要新增 outbox 表即可覆盖 MVP 最关键的一致性窗口。
- `tasks` 本身可以作为待投递任务的事实来源。

备选方案：

- 请求线程内 publish 失败后直接标记 `FAILED`。该方案简单，但会把临时队列故障暴露成业务任务失败。
- 新增 transactional outbox。该方案更完整，但当前 MVP 复杂度较高，后续需要多服务可靠投递时再升级。

### 3. Worker 使用原子认领保证幂等

RabbitMQ 消息可能重复投递，worker MUST 使用 PostgreSQL 原子更新认领任务：

```sql
update tasks
set status = 'RUNNING',
    started_at = now(),
    progress = coalesce(progress, 0),
    message = ?
where id = ?
  and status in ('PENDING', 'QUEUED')
returning *
```

如果没有返回记录，说明任务已经终态、已被取消或已被其他 worker 认领，当前消息应直接 ack 并跳过。

原因：

- 重复消息不会重复执行业务 handler。
- worker 崩溃后可以通过任务状态和消息重投恢复。
- ack 发生在必要状态和事件已写回 PostgreSQL 后。

### 4. Worker handler 使用注册表分发

任务主干提供 `TaskHandler` 和 `TaskHandlerRegistry` 概念，handler 按 `tasks.type` 注册。worker 消费到任务后从数据库读取完整任务输入快照，再选择 handler 执行。

未注册 handler 的任务 SHALL 标记为 `FAILED`，错误码为 `TASK_HANDLER_NOT_FOUND`，并追加 `task.failed` 事件。

原因：

- 任务运行时不耦合具体业务模块。
- 后续 KB_SCAN、SBOM_ANALYSIS、BUILD、TEST 等可以独立接入。
- 可以在测试中使用轻量 handler 验证状态推进、事件追加和 ack 边界。

### 5. MVP 只可靠取消未开始任务

`POST /api/tasks/{taskId}/cancel` 对 `PENDING` 和 `QUEUED` 任务执行状态更新：

```text
PENDING/QUEUED -> CANCELLED
```

如果任务已 `RUNNING`，MVP 返回明确错误或当前状态，表示运行中强制中止暂不支持。后续远程执行能力可以补充 `cancel_requested` 或 worker 进程终止机制。

原因：

- 当前 schema 没有取消请求字段。
- 对运行中任务直接改终态会与 worker 后续写成功/失败结果冲突。
- 不把“取消按钮”做成虚假承诺。

### 6. SSE 使用单实例内存 fanout，PostgreSQL 负责补偿恢复

每次追加 `task_events` 后，当前进程内的 SSE broker 将事件推送给订阅同一项目的连接。连接建立时：

1. 校验用户登录态。
2. 校验项目存在。
3. 读取 `Last-Event-ID`。
4. 从 PostgreSQL 补发该 ID 之后的事件。
5. 注册到项目级内存订阅表并持续发送新事件和心跳。

原因：

- MVP 默认单 API 实例，本地 fanout 简单可靠。
- 即使连接丢事件或服务重启，前端也能用 `Last-Event-ID` 从 PostgreSQL 恢复。
- 后续多实例只需要替换实时 fanout，不改变 PostgreSQL 事实来源和 SSE API 契约。

### 7. 日志 API 先基于 `task_logs` 元数据提供分页和受控下载

`task_logs` 当前保存本地文件路径、大小、哈希和摘要，不保存逐行日志。MVP 的 `GET /api/tasks/{taskId}/logs` SHALL 返回日志文件元数据和摘要列表，而不是逐行日志内容。下载接口通过 `logId` 读取受控文件并隐藏服务器真实路径。

原因：

- 对齐数据库设计：完整日志在本地文件系统，数据库只保存元数据和摘要。
- 避免将大日志写入 PostgreSQL。
- 后续如需要日志 tail 或逐行分页，可以在日志文件读取层扩展，不改变 `task_logs` 元数据模型。

## Risks / Trade-offs

- [风险] PENDING 修复器不是完整 outbox，极端情况下可能重复投递。→ 通过 worker 原子认领和终态跳过保证重复消息不会重复执行业务。
- [风险] 单实例 SSE fanout 在多 API 实例部署时只能保证恢复，不保证跨实例实时推送。→ MVP 接受该限制；后续可加 Redis Pub/Sub。
- [风险] 运行中任务取消暂不支持强中止，前端取消体验有限。→ API 明确返回当前限制，后续远程执行模块再设计取消请求和进程终止。
- [风险] 日志分页如果按文件读取实现，超大文件随机分页成本较高。→ 本阶段先返回日志元数据和摘要，完整查看以下载为主；tail/行索引后续扩展。
- [风险] task handler 抛出异常可能导致消息重投和任务失败状态冲突。→ handler 异常由 worker 捕获，优先写 `FAILED` 和 `task.failed` 后 ack；只有 PostgreSQL 写回失败才 nack/requeue。

## Migration Plan

1. 先实现任务运行时服务、仓储和事件追加，不改变现有业务表。
2. 实现任务 API、SSE API 和日志 API。
3. 实现 worker listener、handler registry 和 PENDING 修复器。
4. 使用测试 handler 或测试夹具验证创建、投递、消费、状态推进、事件恢复和取消语义。
5. 如实现过程中发现现有 schema 不能表达必要字段，再通过单独 Liquibase changeset 补充，并重新生成 jOOQ 代码。

回滚策略：

- 该 change 不改变已有认证和用户管理 API。
- 如果 worker 或 SSE 有问题，可以通过配置关闭 worker 消费，任务仍可保留在 PostgreSQL 中等待修复。
- 如新增 migration，应保证向后兼容，避免破坏已存在的任务记录。

## Open Questions

- 是否需要在本阶段提供仅测试环境启用的示例 task handler，用于端到端验证 worker 成功路径。
- `GET /api/projects/{projectId}/tasks` 是否需要第一版支持 `type`、`status` 和关键字筛选，还是只做分页和状态筛选。
- 日志详情接口第一版是否需要支持从本地日志文件读取 tail 片段，还是仅返回 `task_logs` 元数据和摘要。
