## MODIFIED Requirements

### Requirement: 长任务 API 以 PostgreSQL 任务模型为事实来源
所有长任务创建 API SHALL 先创建持久化任务记录，再返回 `taskId` 和初始任务状态。

#### Scenario: 创建长任务
- **WHEN** 前端发起 KB 扫描、SBOM 分析、环境采集、远程脚本、报告生成、复检、构建、测试或归档
- **THEN** API SHALL 返回 `taskId`、任务类型和初始状态
- **AND** API SHALL 先创建 `tasks` 记录并追加初始 `task_events`
- **AND** 队列载荷 SHALL 只使用 `task_id` 等路由信息
- **AND** API 响应 MUST NOT 返回完整任务输入快照、明文凭据或服务器本地路径

#### Scenario: 查询任务详情
- **WHEN** 前端调用 `GET /api/tasks/{taskId}`
- **THEN** API SHALL 从持久化任务状态返回任务类型、状态、进度、消息、时间、错误摘要和关联业务资源引用
- **AND** API 响应 MUST NOT 返回完整任务输入快照、明文凭据或服务器本地路径

#### Scenario: 查询项目任务列表
- **WHEN** 前端调用 `GET /api/projects/{projectId}/tasks`
- **THEN** API SHALL 返回该项目的分页任务列表
- **AND** 列表项 SHALL 包含任务 ID、任务类型、状态、进度、消息和关键时间字段

#### Scenario: 取消任务
- **WHEN** 前端调用 `POST /api/tasks/{taskId}/cancel`
- **THEN** API SHALL 可靠取消 `PENDING` 或 `QUEUED` 任务
- **AND** 对 `RUNNING` 任务 SHALL 返回明确错误或当前状态，说明 MVP 暂不支持强制中止运行中任务
- **AND** API MUST NOT 直接把仍在执行的任务伪造为已取消

#### Scenario: 枚举任务状态
- **WHEN** API 文档列出任务状态
- **THEN** 文档 SHALL 包含 `PENDING`、`QUEUED`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED` 和 `TIMEOUT`

### Requirement: API 使用项目级 SSE 作为实时任务通道
后端 API 设计 SHALL 使用项目级 SSE 作为 MVP 实时任务事件主通道。

#### Scenario: 建立 SSE 连接
- **WHEN** 前端进入项目工作台
- **THEN** 前端 SHALL 通过 `GET /api/projects/{projectId}/task-events` 建立项目级 SSE 连接
- **AND** SSE 响应内容类型 SHALL 为 `text/event-stream`

#### Scenario: SSE 事件 ID
- **WHEN** 后端发送任务 SSE 事件
- **THEN** SSE 协议层 `id` SHALL 使用递增的 `task_events.id`
- **AND** SSE 协议层 `event` SHALL 使用 `task_events.event_type`
- **AND** SSE data MAY 包含业务追踪字段 `eventId`

#### Scenario: SSE 断线恢复
- **WHEN** 前端携带 `Last-Event-ID` 重新连接
- **THEN** 后端 SHALL 将 `Last-Event-ID` 解析为 `task_events.id`
- **AND** 后端 SHALL 从持久化任务事件中补发同一项目内 `id` 大于该值的后续事件

#### Scenario: 断线补偿
- **WHEN** SSE 连接不可用或恢复失败
- **THEN** 前端 SHALL 通过 `GET /api/tasks/{taskId}` 和 `GET /api/tasks/{taskId}/logs` 补偿刷新

#### Scenario: 避免重复 SSE 通道
- **WHEN** 设计 MVP API
- **THEN** 文档 SHOULD NOT 将 `GET /api/tasks/{taskId}/events` 作为主实时通道

## ADDED Requirements

### Requirement: 任务日志 API 不暴露服务器路径
任务日志 API SHALL 通过任务日志资源提供分页和受控下载能力，并 SHALL 隐藏服务器真实文件路径。

#### Scenario: 查询日志元数据
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/logs`
- **THEN** API SHALL 返回日志 ID、日志类型、大小、摘要和创建时间
- **AND** 响应 MUST NOT 返回 `file_path` 或服务器真实路径

#### Scenario: 下载日志文件
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/logs/{logId}/download`
- **THEN** API SHALL 校验日志属于该任务
- **AND** API SHALL 通过受控下载返回日志内容
- **AND** API MUST NOT 接受客户端传入服务器文件路径作为下载参数
