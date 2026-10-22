## Why

当前后端已经具备认证、数据库迁移、Redis 和 RabbitMQ 基础封装，但所有 KB 扫描、SBOM、构建、测试、报告和归档等长任务还缺少统一运行时主干。现在需要先建立可复用的任务创建、队列消费、状态推进、事件持久化、SSE 推送和日志访问能力，避免后续每个业务模块重复实现任务生命周期。

## What Changes

- 新增任务运行时主干，统一封装任务创建、任务状态推进、任务事件追加、任务队列投递和 worker 消费入口。
- 新增项目级 SSE 运行能力，使用 `task_events.id` 作为 SSE `Last-Event-ID` 恢复游标，并从 PostgreSQL 补发断线期间事件。
- 新增任务查询、项目任务列表、取消任务、日志分页和日志下载基础 API。
- 新增 worker handler 注册与分发约定，RabbitMQ 消息继续只携带 `taskId` 和必要路由信息。
- 明确 MVP 取消语义：只可靠取消 `PENDING` 和 `QUEUED` 任务；运行中任务的进程级中止留给后续远程执行能力。
- 明确投递一致性策略：任务先以 PostgreSQL 为事实来源创建，投递失败或服务中断由 `PENDING` 任务修复机制重新投递。

## Capabilities

### New Capabilities
- `task-runtime`: 覆盖任务创建、状态机、事件追加、RabbitMQ 消费、worker handler 分发、项目级 SSE、日志访问和投递修复能力。

### Modified Capabilities
- `backend-api-design`: 细化任务 API、SSE `Last-Event-ID`、取消语义和日志访问契约。
- `backend-database-design`: 细化 PostgreSQL 作为任务事实来源、任务事件恢复游标、投递修复和 worker 幂等处理要求。

## Impact

- 影响后端任务相关包：`tasks`、`worker`、`logs`、`queue` 和 SSE Web 层。
- 复用现有 `TaskQueueClient`、quorum queue、manual ack RabbitMQ 配置和 jOOQ 数据访问。
- 复用现有 `tasks`、`task_events`、`task_logs`、`tool_runs` 表；如实现发现 schema 不足，可通过后续 Liquibase migration 补充小范围字段或索引。
- 后续 KB 扫描、SBOM、构建、测试、报告和归档模块都应通过该任务运行时创建和推进长任务。
