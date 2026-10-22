## MODIFIED Requirements

### Requirement: API 使用项目级 SSE 作为实时任务通道
后端 API 设计 SHALL 使用项目级 SSE 作为 MVP 实时任务事件主通道，并 SHALL 区分首次订阅 baseline 与同一页面断线恢复游标，避免新浏览器或旧游标默认补发大量历史事件。

#### Scenario: 建立 SSE 连接
- **WHEN** 前端进入项目工作台
- **THEN** 前端 SHALL 能通过 `GET /api/projects/{projectId}/task-events` 建立项目级 SSE 连接
- **AND** SSE 响应内容类型 SHALL 为 `text/event-stream`
- **AND** 未提交任何游标时，后端 SHALL 从当前项目最新事件 ID 之后开始推送新事件

#### Scenario: 使用 overview baseline 建立 SSE
- **WHEN** 前端调用 `GET /api/projects/{projectId}/overview` 获得 `latestTaskEventId`
- **THEN** 前端 SHALL 能调用 `GET /api/projects/{projectId}/task-events?afterEventId={latestTaskEventId}` 只订阅该事件之后的新事件
- **AND** 后端 SHALL 只补发同一项目内 `id > afterEventId` 的事件

#### Scenario: SSE 事件 ID
- **WHEN** 后端发送任务 SSE 事件
- **THEN** SSE 协议层 `id` SHALL 使用递增的 `task_events.id`
- **AND** SSE 协议层 `event` SHALL 使用 `task_events.event_type`
- **AND** SSE data MAY 包含业务追踪字段 `eventId`

#### Scenario: SSE 断线恢复
- **WHEN** 前端未提交 `afterEventId` 且携带 `Last-Event-ID` 重新连接
- **THEN** 后端 SHALL 将 `Last-Event-ID` 解析为 `task_events.id`
- **AND** 后端 SHALL 从持久化任务事件中补发同一项目内 `id` 大于该值的后续事件

#### Scenario: afterEventId 覆盖 Last-Event-ID
- **WHEN** 前端同时提交 `afterEventId` 和 `Last-Event-ID`
- **THEN** 后端 SHALL 以 `afterEventId` 作为本次连接游标
- **AND** 后端 SHALL 忽略本次请求中的 `Last-Event-ID`

#### Scenario: 断线补偿
- **WHEN** SSE 连接不可用或恢复失败
- **THEN** 前端 SHALL 通过 `GET /api/tasks/{taskId}` 和 `GET /api/tasks/{taskId}/logs` 补偿刷新

#### Scenario: 避免重复 SSE 通道
- **WHEN** 设计 MVP API
- **THEN** 文档 SHOULD NOT 将 `GET /api/tasks/{taskId}/events` 作为主实时通道

#### Scenario: 项目级 SSE 隔离
- **WHEN** 用户在两个浏览器或两个页面分别打开不同项目
- **THEN** 每个项目级 SSE 连接 SHALL 只接收对应项目的任务事件
- **AND** 后端 MUST NOT 补发或推送其他项目的任务事件

### Requirement: 项目 overview 必须返回最新任务事件 ID
项目 overview API SHALL 返回当前项目最新任务事件 ID，供前端首次建立项目级 SSE 时作为 baseline。

#### Scenario: 读取项目概览包含 latestTaskEventId
- **WHEN** 前端调用 `GET /api/projects/{projectId}/overview`
- **THEN** 后端 SHALL 根据项目访问权限返回项目概览
- **AND** 响应 SHALL 包含 `latestTaskEventId`
- **AND** `latestTaskEventId` SHALL 为当前项目最新 `task_events.id`
- **AND** 当前项目没有任务事件时 SHALL 返回 `0`

#### Scenario: 无权限读取 overview
- **WHEN** 用户无权访问目标项目
- **THEN** 后端 SHALL 拒绝返回 overview
- **AND** 后端 MUST NOT 暴露该项目的 `latestTaskEventId`

### Requirement: 项目级 SSE 必须校验游标参数
项目级 SSE API SHALL 对 `afterEventId` 和 `Last-Event-ID` 执行统一游标校验。

#### Scenario: afterEventId 非法
- **WHEN** 前端调用项目级 SSE 且 `afterEventId` 不是非负数字
- **THEN** 后端 SHALL 返回统一参数错误
- **AND** 后端 MUST NOT 创建 SSE emitter

#### Scenario: Last-Event-ID 非法
- **WHEN** 前端调用项目级 SSE 且未提交 `afterEventId`，但 `Last-Event-ID` 不是非负数字
- **THEN** 后端 SHALL 返回统一参数错误
- **AND** 后端 MUST NOT 创建 SSE emitter
