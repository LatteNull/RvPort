## ADDED Requirements

### Requirement: 任务运行时必须统一创建长任务
任务运行时 SHALL 提供统一任务创建入口，用于创建所有需要异步执行的长任务。

#### Scenario: 创建长任务记录
- **WHEN** 后端业务模块请求创建长任务
- **THEN** 任务运行时 SHALL 在 PostgreSQL 中创建 `tasks` 记录
- **AND** 初始状态 SHALL 为 `PENDING`
- **AND** 任务输入快照 SHALL 保存到 `tasks.input_snapshot`
- **AND** 任务创建人 SHALL 来自当前登录用户或明确的系统执行上下文

#### Scenario: 追加初始任务事件
- **WHEN** 任务运行时成功创建任务记录
- **THEN** 任务运行时 SHALL 追加 `task.created` 事件到 `task_events`
- **AND** 事件 SHALL 关联同一 `project_id` 和 `task_id`

#### Scenario: 返回任务创建结果
- **WHEN** API 成功创建异步任务
- **THEN** 响应 SHALL 返回 `taskId`、任务类型和当前状态
- **AND** 响应 MUST NOT 返回完整输入快照、明文凭据或服务器本地路径

### Requirement: 任务运行时必须先持久化再投递队列
任务运行时 SHALL 以 PostgreSQL 任务记录作为事实来源，并在任务持久化后投递 RabbitMQ。

#### Scenario: 投递任务消息
- **WHEN** 任务记录和初始事件已经提交
- **THEN** 任务运行时 SHALL 通过统一 `TaskQueueClient` 投递 RabbitMQ 消息
- **AND** 消息 SHALL 包含 `taskId`
- **AND** 消息 MAY 包含任务类型、项目 ID 和创建时间
- **AND** 消息 MUST NOT 包含任务输入快照、任务结果、完整日志、任务状态事实或明文凭据

#### Scenario: 标记任务已入队
- **WHEN** RabbitMQ 投递成功
- **THEN** 任务运行时 SHALL 将任务状态更新为 `QUEUED`
- **AND** SHALL 设置 `queued_at`
- **AND** SHALL 追加 `task.queued` 事件

#### Scenario: 修复未投递任务
- **WHEN** 任务长时间停留在 `PENDING`
- **THEN** 任务运行时 SHALL 能通过修复流程重新投递该任务
- **AND** 修复流程 MUST 继续只以 PostgreSQL 中的任务记录为事实来源

### Requirement: Worker 必须幂等消费任务消息
Worker SHALL 使用 PostgreSQL 原子状态变更认领任务，并 SHALL 在处理结果可靠写回后手动确认 RabbitMQ 消息。

#### Scenario: 成功认领任务
- **WHEN** worker 收到任务队列消息
- **THEN** worker SHALL 根据 `taskId` 从 PostgreSQL 读取任务记录和输入快照
- **AND** worker SHALL 仅在任务状态为 `PENDING` 或 `QUEUED` 时将其原子更新为 `RUNNING`
- **AND** worker SHALL 设置 `started_at`
- **AND** worker SHALL 追加 `task.started` 事件

#### Scenario: 重复消息跳过
- **WHEN** worker 收到的任务已经处于 `RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED` 或 `TIMEOUT`
- **THEN** worker SHALL 不重复执行业务 handler
- **AND** worker SHALL 确认该 RabbitMQ 消息

#### Scenario: 处理成功
- **WHEN** 任务 handler 成功完成
- **THEN** worker SHALL 将任务状态更新为 `SUCCEEDED`
- **AND** SHALL 设置 `finished_at`
- **AND** SHALL 追加 `task.succeeded` 事件
- **AND** SHALL 在数据库写回完成后确认 RabbitMQ 消息

#### Scenario: 处理失败
- **WHEN** 任务 handler 抛出业务异常或返回失败结果
- **THEN** worker SHALL 将任务状态更新为 `FAILED`
- **AND** SHALL 写入错误码和错误摘要
- **AND** SHALL 追加 `task.failed` 事件
- **AND** SHALL 在失败状态可靠写回后确认 RabbitMQ 消息

### Requirement: Worker 必须通过任务类型分发 handler
任务运行时 SHALL 提供任务 handler 注册和分发机制，使业务模块按任务类型接入 worker 主干。

#### Scenario: 分发到已注册 handler
- **WHEN** worker 认领任务后发现任务类型存在已注册 handler
- **THEN** worker SHALL 调用该 handler 处理任务
- **AND** handler SHALL 从 PostgreSQL 中读取任务输入快照和所需业务数据

#### Scenario: 缺少 handler
- **WHEN** worker 认领任务后发现任务类型没有已注册 handler
- **THEN** worker SHALL 将任务标记为 `FAILED`
- **AND** 错误码 SHALL 为 `TASK_HANDLER_NOT_FOUND`
- **AND** worker SHALL 追加 `task.failed` 事件

### Requirement: 任务运行时必须持久化任务事件
任务运行时 SHALL 将所有任务状态变化、进度变化和日志摘要写入 `task_events`。

#### Scenario: 写入进度事件
- **WHEN** 任务进度发生变化
- **THEN** 任务运行时 SHALL 更新 `tasks.progress` 和可展示消息
- **AND** SHALL 追加 `task.progress` 事件
- **AND** 进度值 SHALL 在 0 到 100 之间

#### Scenario: 写入日志摘要事件
- **WHEN** worker 捕获到适合展示的日志摘要
- **THEN** 任务运行时 SHALL 追加 `task.log` 事件
- **AND** 事件 MAY 包含日志级别和短摘要
- **AND** 事件 MUST NOT 包含完整 stdout 或 stderr 日志

#### Scenario: 写入终态事件
- **WHEN** 任务进入 `SUCCEEDED`、`FAILED`、`CANCELLED` 或 `TIMEOUT`
- **THEN** 任务运行时 SHALL 设置 `finished_at`
- **AND** SHALL 追加对应终态事件

### Requirement: 项目级 SSE 必须使用持久化事件恢复
任务运行时 SHALL 提供项目级 SSE 通道，并 SHALL 使用持久化 `task_events` 支持断线恢复。

#### Scenario: 建立项目级 SSE
- **WHEN** 已登录用户请求 `GET /api/projects/{projectId}/task-events`
- **THEN** 后端 SHALL 返回 `text/event-stream`
- **AND** SSE 通道 SHALL 只推送该项目的任务事件
- **AND** 后端 SHALL 周期性发送心跳以保持连接

#### Scenario: 使用 Last-Event-ID 恢复
- **WHEN** 前端携带 `Last-Event-ID` 重新连接
- **THEN** 后端 SHALL 将该值解析为 `task_events.id`
- **AND** 后端 SHALL 按 `project_id` 和 `id > Last-Event-ID` 从 PostgreSQL 补发后续事件
- **AND** 补发顺序 SHALL 按 `task_events.id` 升序

#### Scenario: 发送 SSE 事件
- **WHEN** 后端向 SSE 连接发送任务事件
- **THEN** SSE `id` SHALL 使用 `task_events.id`
- **AND** SSE `event` SHALL 使用 `task_events.event_type`
- **AND** SSE `data` SHALL 包含事件业务载荷

### Requirement: 任务 API 必须提供查询、取消和日志访问
任务运行时 SHALL 提供任务详情、项目任务列表、取消任务、日志列表和日志下载 API。

#### Scenario: 查询项目任务列表
- **WHEN** 前端调用 `GET /api/projects/{projectId}/tasks`
- **THEN** 后端 SHALL 返回该项目的分页任务列表
- **AND** 列表项 SHALL 包含任务 ID、类型、状态、进度、消息和关键时间字段

#### Scenario: 查询任务详情
- **WHEN** 前端调用 `GET /api/tasks/{taskId}`
- **THEN** 后端 SHALL 返回任务类型、状态、进度、消息、时间、错误摘要和关联业务资源引用
- **AND** 响应 MUST NOT 返回完整输入快照、明文凭据或服务器本地路径

#### Scenario: 取消未开始任务
- **WHEN** 前端调用 `POST /api/tasks/{taskId}/cancel` 且任务状态为 `PENDING` 或 `QUEUED`
- **THEN** 后端 SHALL 将任务状态更新为 `CANCELLED`
- **AND** SHALL 设置 `finished_at`
- **AND** SHALL 追加 `task.cancelled` 事件

#### Scenario: 拒绝强制取消运行中任务
- **WHEN** 前端调用 `POST /api/tasks/{taskId}/cancel` 且任务状态为 `RUNNING`
- **THEN** 后端 SHALL 返回明确错误或当前任务状态，说明 MVP 暂不支持强制中止运行中任务
- **AND** 后端 MUST NOT 直接把运行中任务伪造为已取消

#### Scenario: 查询任务日志元数据
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/logs`
- **THEN** 后端 SHALL 返回该任务的日志元数据、日志类型、大小、摘要和创建时间
- **AND** 响应 MUST NOT 暴露服务器真实文件路径

#### Scenario: 下载任务日志
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/logs/{logId}/download`
- **THEN** 后端 SHALL 校验日志属于该任务
- **AND** SHALL 通过受控下载返回日志文件
- **AND** 响应 MUST NOT 允许客户端指定服务器文件路径
