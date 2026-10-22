## Context

当前部署将 API 服务和异步 worker 拆成两个独立 JVM 进程：

```text
backend         持有浏览器 SSE 连接
backend-worker  执行异步任务并写入任务事件
```

`TaskSseBroker` 和 `TaskLogSseBroker` 都使用进程内 `ConcurrentHashMap` 保存 `SseEmitter`。因此 API 进程产生的 `task.created` 可以推送到浏览器，但 worker 进程产生的后续生命周期事件和日志事件只能发布到 worker 自己的 broker。worker 进程没有浏览器 emitter，实时推送就会丢失。

数据库中 `task_events` 和 `task_log_events` 已经保留完整事件，说明事实写入链路正常。需要修复的是“事件落库后通知持有 SSE 连接的 API 进程”这一段。

## Goals / Non-Goals

**Goals:**

- 支持 `backend` 与 `backend-worker` 分进程部署下的项目级 SSE 实时推送。
- 支持分进程部署下的任务级日志 SSE 实时推送。
- 保持数据库事件表作为事实来源，Redis 只承担跨进程通知职责。
- 保持现有 SSE API、baseline、`afterEventId`、`Last-Event-ID` 和权限校验行为不变。
- 广播失败不能影响任务事件、日志事件或任务终态落库。
- E2E 必须覆盖 API 进程持有 SSE 连接、worker 进程产生事件的真实部署场景。

**Non-Goals:**

- 不将 Redis 变成事件事实来源。
- 不实现完整历史事件可靠投递队列。
- 不改变前端 SSE 使用方式。
- 不改变任务状态机、任务日志文件落库方式或 RabbitMQ 任务队列语义。

## Decisions

### 1. 使用 Redis Pub/Sub 作为跨进程实时通知通道

选择 Redis Pub/Sub，因为项目已经依赖 Redis，SSE 通知是轻量实时提示，不需要队列级可靠消费。`task_events` 和 `task_log_events` 仍然是事实来源，Redis 只发布“有新事件”的最小引用。

```text
Worker/API 事件写入
  │
  │ afterCommit
  ▼
Redis Pub/Sub: rvport:sse:task-events
  │
  ▼
API 进程订阅
  │
  │ 按 eventId 从 DB 重读
  ▼
TaskSseBroker.publish(event)
  │
  ▼
浏览器 SSE
```

备选方案：

- RabbitMQ fanout：可靠性强，但需要 API 实例临时队列或实例队列管理，复杂度高于当前需求。
- PostgreSQL LISTEN/NOTIFY：少一个组件，但 Spring 连接管理和重连处理更重，且当前 Redis 已存在。
- 定时轮询数据库：实现简单但实时性差，会增加数据库周期性负载。

### 2. 广播 payload 只携带最小引用

项目级事件广播 payload 建议只包含：

```json
{
  "eventId": 23606,
  "projectId": "da433b4a-daa2-4264-82bd-7af43f39906f"
}
```

任务级日志事件广播 payload 建议只包含：

```json
{
  "eventId": 99123,
  "taskId": "bedaa7e4-299b-4bb6-8efd-1c3ec96e37bc"
}
```

API 订阅端收到通知后从数据库读取完整事件，再走已有 broker 序列化逻辑。这能避免 Redis 消息携带完整业务结果、日志片段、路径或敏感信息，也避免事件结构变更时出现双写不一致。

### 3. 发布必须在事务提交后执行

现有 `TaskEventService` 和 `TaskLogEventService` 已经有 `afterCommit` 发布语义。新广播层应复用这个边界：

- 事务未提交时不广播。
- 提交后广播 Redis 通知。
- API 进程订阅到通知后重读数据库，避免读到未提交事件。
- 无事务上下文时保持立即广播。

### 4. 保留本进程直推，并用 publisherId 避免 Redis 回环重复

为了保持本地开发、combined mode 和 Redis 短时异常时的本进程体验，事件提交后同时：

- 调用本进程 broker 推送给当前 JVM 内 emitter。
- 发布 Redis 广播，让其他 API 进程也能收到。

Redis payload 增加本 JVM 的 `publisherId`。订阅端收到消息后，如果 `publisherId` 与当前进程一致则直接丢弃，避免同一 SSE 连接重复收到事件。跨进程场景下，API 进程的 `publisherId` 与 worker 进程不同，因此会从数据库重读并推送给浏览器。

### 5. 只在 API-capable 进程订阅并推送 SSE

worker 进程不需要持有浏览器 SSE 连接，也不需要订阅 Redis 后推送。订阅组件应根据运行模式启用：

- `api` 或 `combined` 模式：启用 Redis 订阅和 broker 推送。
- `worker` 模式：只发布 Redis 通知，不启用订阅推送。

这样可以避免 worker 实例无意义地订阅消息并读取数据库。

### 6. Redis 广播失败降级而不破坏任务执行

广播失败时：

- 事件和日志事件仍应保持已落库。
- 任务状态不应因为 SSE 广播失败被改成失败。
- 后端应记录脱敏 warning，包含 eventId、projectId/taskId、channel 和异常摘要。
- 前端仍可通过 overview/list/detail、SSE 重连游标或日志历史补发恢复。

这符合当前架构：实时 SSE 是体验优化，不是事实来源。

## Risks / Trade-offs

- [Risk] Redis Pub/Sub 不可靠，订阅端短暂断线时会丢广播。
  Mitigation: 数据库仍是事实来源；前端重连时通过 `afterEventId`/`Last-Event-ID` 补发项目事件，任务日志 SSE 首次连接和重连也从数据库补发。

- [Risk] 本进程直接推送和 Redis 订阅推送并存可能造成重复事件。
  Mitigation: MVP 采用统一 Redis 订阅端推送，或在订阅端按 eventId 做短 TTL 去重。

- [Risk] worker 模式错误启用订阅会造成无效 DB 查询。
  Mitigation: 订阅组件按应用运行模式启用，并补充配置测试。

- [Risk] Redis payload 如果携带完整事件会扩大敏感信息泄漏面。
  Mitigation: payload 只包含 eventId 和 projectId/taskId，API 端从数据库读取并沿用现有响应脱敏边界。

- [Risk] E2E 如果仍用 combined mode，会漏掉跨进程问题。
  Mitigation: 新增或扩展 E2E 时必须在 `backend` 与 `backend-worker` 分离部署下验证。

## Migration Plan

1. 新增 Redis Pub/Sub channel 配置，默认复用当前 Redis 连接。
2. 新增项目事件和任务日志事件的跨进程广播 publisher。
3. 新增 API 进程 Redis subscriber，从数据库重读事件并调用对应 broker。
4. 调整 `TaskEventService` 和 `TaskLogEventService` 的 after-commit 发布路径。
5. 增加单元测试覆盖 payload、after-commit、广播失败降级和运行模式启停。
6. 增加 E2E 覆盖 API/worker 分进程场景。

回滚策略：保留原有数据库事件和 SSE API，不涉及 schema 破坏性修改；如 Redis 广播出现问题，可通过配置临时关闭跨进程广播，前端仍依赖数据库重读和 SSE 重连恢复。

## Open Questions

- 是否需要为 Redis channel 增加环境前缀，避免同一 Redis 被多个 RvPort 环境共用时互相干扰？建议使用现有 namespace 前缀。
- 是否要对项目事件和任务日志事件使用两个独立 channel？建议拆分，便于订阅端按类型读取对应表。
