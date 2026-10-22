## MODIFIED Requirements

### Requirement: 项目级 SSE 必须使用持久化事件恢复
任务运行时 SHALL 提供项目级 SSE 通道，并 SHALL 使用持久化 `task_events` 支持断线恢复，同时 SHALL 区分首次订阅 baseline 和同一连接的断线恢复游标。

#### Scenario: 建立项目级 SSE
- **WHEN** 已登录用户请求 `GET /api/projects/{projectId}/task-events`
- **THEN** 后端 SHALL 返回 `text/event-stream`
- **AND** SSE 通道 SHALL 只推送该项目的任务事件
- **AND** 后端 SHALL 周期性发送心跳以保持连接

#### Scenario: 使用 afterEventId 作为首次订阅 baseline
- **WHEN** 前端请求 `GET /api/projects/{projectId}/task-events?afterEventId={eventId}`
- **THEN** 后端 SHALL 将 `afterEventId` 解析为 `task_events.id` 游标
- **AND** 后端 SHALL 按 `project_id` 和 `id > afterEventId` 从 PostgreSQL 补发后续事件
- **AND** 补发顺序 SHALL 按 `task_events.id` 升序

#### Scenario: 使用 Last-Event-ID 恢复
- **WHEN** 前端未提交 `afterEventId` 且携带 `Last-Event-ID` 重新连接
- **THEN** 后端 SHALL 将该值解析为 `task_events.id`
- **AND** 后端 SHALL 按 `project_id` 和 `id > Last-Event-ID` 从 PostgreSQL 补发后续事件
- **AND** 补发顺序 SHALL 按 `task_events.id` 升序

#### Scenario: 无游标首次连接使用当前项目最新事件作为 baseline
- **WHEN** 前端请求项目级 SSE 且未提交 `afterEventId` 或 `Last-Event-ID`
- **THEN** 后端 SHALL 查询当前项目最新 `task_events.id` 作为 baseline
- **AND** 后端 SHALL 只推送该 baseline 之后的新事件
- **AND** 后端 MUST NOT 默认补发该项目全部历史事件

#### Scenario: afterEventId 优先于 Last-Event-ID
- **WHEN** 前端同时提交 `afterEventId` 和 `Last-Event-ID`
- **THEN** 后端 SHALL 使用 `afterEventId` 作为游标
- **AND** 后端 SHALL 忽略本次请求中的 `Last-Event-ID`

#### Scenario: 拒绝非法 SSE 游标
- **WHEN** `afterEventId` 或被使用的 `Last-Event-ID` 不是非负数字
- **THEN** 后端 SHALL 返回 `SSE_LAST_EVENT_ID_INVALID` 或等效统一错误
- **AND** 后端 MUST NOT 创建 SSE emitter
- **AND** 后端 MUST NOT 补发历史事件

#### Scenario: 发送 SSE 事件
- **WHEN** 后端向 SSE 连接发送任务事件
- **THEN** SSE `id` SHALL 使用 `task_events.id`
- **AND** SSE `event` SHALL 使用 `task_events.event_type`
- **AND** SSE `data` SHALL 包含事件业务载荷

#### Scenario: 多项目 SSE 隔离
- **WHEN** 同一用户或不同用户同时打开多个项目的 SSE 连接
- **THEN** 每个 SSE 连接 SHALL 只收到对应 `projectId` 的任务事件
- **AND** 后端 MUST NOT 因全局递增 `task_events.id` 将其他项目事件补发或推送到当前项目连接

### Requirement: 项目 overview 必须提供项目级 SSE baseline
任务运行时 SHALL 提供当前项目最新任务事件 ID，使项目 overview 能作为首次建立 SSE 的事实 baseline。

#### Scenario: 查询最新项目事件 ID
- **WHEN** 后端生成项目 overview
- **THEN** 任务运行时 SHALL 能按 `projectId` 查询当前项目最新 `task_events.id`
- **AND** 没有任务事件时 SHALL 返回 `0`

#### Scenario: 历史异常事件不默认补发
- **WHEN** 项目存在大量历史任务事件
- **AND** 前端首次打开项目且未提交游标
- **THEN** 后端 SHALL 从当前项目最新事件 ID 之后开始推送
- **AND** 后端 MUST NOT 默认补发历史异常事件

### Requirement: 重试必须作为运行过程事件表达
任务重试 SHALL 保持在既有任务状态模型内表达，不得新增独立的 `RETRYING` 任务状态。

#### Scenario: 重试期间状态表达
- **WHEN** worker 判断任务失败可重试
- **THEN** 后端 SHALL 使用 `QUEUED` 或 `RUNNING` 表达任务仍在执行流程中
- **AND** 后端 SHALL 使用 `retry_count`、message 和任务事件表达重试次数
- **AND** 后端 MUST NOT 新增 `RETRYING` 状态

#### Scenario: 达到最大重试次数
- **WHEN** 任务达到最大重试次数仍失败
- **THEN** worker SHALL 将任务标记为 `FAILED`
- **AND** worker SHALL 追加单个终态 `task.failed` 事件
