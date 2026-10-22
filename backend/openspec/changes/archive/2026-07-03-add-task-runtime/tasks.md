## 1. 任务运行时核心

- [x] 1.1 创建任务运行时包结构，包含任务服务、任务仓储、事件仓储、日志仓储和 worker 基础类型。
- [x] 1.2 定义任务状态、任务事件类型、任务日志类型和任务错误码常量，确保与数据库 CHECK 约束一致。
- [x] 1.3 实现任务创建服务：插入 `tasks(status=PENDING)`、保存 `input_snapshot`、追加 `task.created`。
- [x] 1.4 实现任务投递成功后的 `QUEUED` 状态更新、`queued_at` 写入和 `task.queued` 事件追加。
- [x] 1.5 实现任务详情和项目任务列表查询模型，响应中隐藏完整输入快照、明文凭据和服务器本地路径。
- [x] 1.6 实现任务取消服务，可靠取消 `PENDING` 和 `QUEUED` 任务，并对 `RUNNING` 返回明确限制。

## 2. 队列消费和投递修复

- [x] 2.1 实现 worker handler 接口和 handler 注册表，按任务类型查找处理器。
- [x] 2.2 实现 RabbitMQ worker listener，消费 `TaskQueueMessage` 并使用 manual ack。
- [x] 2.3 实现 worker 原子认领任务逻辑，仅将 `PENDING` 或 `QUEUED` 任务推进为 `RUNNING`。
- [x] 2.4 实现 worker 成功、失败、缺少 handler 和重复消息跳过处理，并在 PostgreSQL 写回后确认消息。
- [x] 2.5 实现 `PENDING` 任务投递修复流程，按宽限时间扫描并重新投递待投递任务。
- [x] 2.6 为 worker 启用条件配置，确保 API 模式和 worker 模式可以按环境变量控制。

## 3. 任务事件和 SSE

- [x] 3.1 实现任务事件追加服务，统一写入状态、进度、消息、日志级别和日志摘要。
- [x] 3.2 实现项目级 SSE broker，管理项目订阅连接、连接清理和心跳发送。
- [x] 3.3 实现 `GET /api/projects/{projectId}/task-events`，返回 `text/event-stream`。
- [x] 3.4 使用 `task_events.id` 作为 SSE `id`，使用 `task_events.event_type` 作为 SSE `event`。
- [x] 3.5 实现 `Last-Event-ID` 恢复，从 PostgreSQL 按 `project_id` 和 `id > lastEventId` 补发事件。
- [x] 3.6 确保 SSE data 不包含完整 stdout/stderr、明文凭据或服务器本地路径。

## 4. 任务日志 API

- [x] 4.1 实现任务日志元数据查询，支持按任务和日志类型分页读取 `task_logs`。
- [x] 4.2 实现 `GET /api/tasks/{taskId}/logs`，返回日志 ID、类型、大小、摘要和创建时间。
- [x] 4.3 实现 `GET /api/tasks/{taskId}/logs/{logId}/download`，校验日志归属并隐藏服务器真实路径。
- [x] 4.4 实现日志文件缺失、路径非法或下载失败时的统一错误响应。

## 5. API 控制器和安全边界

- [x] 5.1 实现 `GET /api/projects/{projectId}/tasks` 控制器。
- [x] 5.2 实现 `GET /api/tasks/{taskId}` 控制器。
- [x] 5.3 实现 `POST /api/tasks/{taskId}/cancel` 控制器。
- [x] 5.4 确保任务、SSE 和日志接口要求登录态，并遵守强制改密过滤规则。
- [x] 5.5 为任务运行时关键操作补充必要审计或请求日志，避免记录秘密信息。

## 6. 测试和验证

- [x] 6.1 为任务创建、投递、状态推进和取消逻辑编写单元测试。
- [x] 6.2 为 worker 原子认领、重复消息跳过、缺少 handler、成功和失败路径编写测试。
- [x] 6.3 为 SSE `Last-Event-ID` 恢复、事件排序和心跳行为编写测试。
- [x] 6.4 为任务日志元数据和受控下载编写测试，覆盖路径隐藏和归属校验。
- [x] 6.5 运行 `mvn test` 验证后端测试通过。
- [x] 6.6 在本地基础设施可用时进行一次实际联通验证：创建任务、投递 RabbitMQ、worker 消费、写入事件、SSE 或事件查询可观察。

## 7. 文档和收尾

- [x] 7.1 更新 `backend/docs/API_DESIGN.md` 中任务、SSE 和日志章节，使 `Last-Event-ID` 使用 `task_events.id` 的约定清晰可见。
- [x] 7.2 如实现新增 schema 字段或索引，补充 Liquibase changelog 并重新生成 jOOQ 代码。
- [x] 7.3 检查所有新增文档和注释使用中文，接口路径、字段名和枚举值保留英文。
- [x] 7.4 检查 OpenSpec 状态，确保 change 可以进入 archive 前同步。
