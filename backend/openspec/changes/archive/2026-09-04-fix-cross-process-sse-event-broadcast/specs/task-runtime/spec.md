## ADDED Requirements

### Requirement: 项目级 SSE 必须支持跨进程事件广播
任务运行时 SHALL 在 API 进程和 worker 进程分离部署时，通过跨进程事件广播将已持久化的项目事件通知到持有浏览器 SSE 连接的 API 进程。

#### Scenario: worker 事件跨进程推送到浏览器
- **WHEN** worker 进程写入 `task.queued`、`task.started`、`task.progress`、`task.log`、`task.succeeded` 或 `task.failed` 项目事件
- **AND** 浏览器 SSE 连接存在于 API 进程
- **THEN** worker 进程 SHALL 在事务提交后发布跨进程事件通知
- **AND** API 进程 SHALL 接收该通知并从数据库读取对应 `task_events` 记录
- **AND** API 进程 SHALL 通过本进程 `TaskSseBroker` 将事件推送给该项目的 SSE 连接

#### Scenario: 项目上下文事件跨进程推送
- **WHEN** worker 进程因 Git 同步、源码激活、环境变更或其他异步流程写入 `project.context.changed`
- **THEN** 后端 SHALL 在事务提交后发布跨进程事件通知
- **AND** API 进程 SHALL 将该上下文变更事件推送给对应项目的 SSE 连接
- **AND** 推送内容 SHALL 继续遵守项目事件轻量载荷和敏感信息边界

#### Scenario: Redis 广播只携带最小引用
- **WHEN** 后端发布项目事件跨进程通知
- **THEN** 通知 payload SHALL 只包含定位事件所需的最小引用信息
- **AND** payload SHALL 至少包含 `eventId` 和 `projectId`
- **AND** payload MUST NOT 包含完整业务结果、完整日志、服务器真实路径、明文凭据、token 或私钥

#### Scenario: 数据库仍为项目事件事实来源
- **WHEN** API 进程收到项目事件跨进程通知
- **THEN** API 进程 SHALL 根据 `eventId` 和 `projectId` 从数据库重读事件
- **AND** API 进程 MUST NOT 直接信任 Redis payload 作为 SSE 业务数据
- **AND** 事件不存在、项目不匹配或读取失败时 SHALL 记录脱敏 warning 并丢弃该通知

#### Scenario: Redis 广播失败不改变任务终态
- **WHEN** 任务事件已经成功写入数据库
- **AND** Redis 跨进程通知发布失败
- **THEN** 任务状态和事件事实 SHALL 保持已写入结果
- **AND** 后端 MUST NOT 因 SSE 广播失败将任务标记为失败
- **AND** 后端 SHALL 记录脱敏 warning 供运维排查

#### Scenario: SSE 游标语义保持不变
- **WHEN** 跨进程广播启用
- **THEN** 项目级 SSE SHALL 继续支持既有 `afterEventId`、`Last-Event-ID` 和无游标 baseline 语义
- **AND** 断线恢复 SHALL 继续从数据库按当前 `projectId` 查询游标之后的事件
- **AND** 后端 MUST NOT 将 Redis Pub/Sub 作为历史事件补发来源

### Requirement: 任务级日志 SSE 必须支持跨进程日志广播
任务运行时 SHALL 在 API 进程和 worker 进程分离部署时，通过跨进程日志事件广播将已持久化的任务日志事件通知到持有任务日志 SSE 连接的 API 进程。

#### Scenario: worker 日志事件跨进程推送到浏览器
- **WHEN** worker 进程写入 `task_log_events`
- **AND** 浏览器任务级日志 SSE 连接存在于 API 进程
- **THEN** worker 进程 SHALL 在事务提交后发布跨进程日志事件通知
- **AND** API 进程 SHALL 接收该通知并从数据库读取对应日志事件
- **AND** API 进程 SHALL 通过本进程 `TaskLogSseBroker` 将日志事件推送给该任务的日志 SSE 连接

#### Scenario: 日志广播只携带最小引用
- **WHEN** 后端发布任务日志事件跨进程通知
- **THEN** 通知 payload SHALL 至少包含 `eventId` 和 `taskId`
- **AND** payload MUST NOT 包含日志内容片段、完整 stdout、完整 stderr、服务器真实路径、明文凭据、token 或私钥

#### Scenario: 数据库仍为日志事件事实来源
- **WHEN** API 进程收到任务日志事件跨进程通知
- **THEN** API 进程 SHALL 根据 `eventId` 和 `taskId` 从数据库重读日志事件
- **AND** API 进程 MUST NOT 直接信任 Redis payload 作为日志 SSE 数据
- **AND** 日志事件不存在、任务不匹配或读取失败时 SHALL 记录脱敏 warning 并丢弃该通知

#### Scenario: 日志广播失败不改变任务状态
- **WHEN** 日志事件已经成功写入数据库
- **AND** Redis 跨进程通知发布失败
- **THEN** 日志事件事实 SHALL 保持已写入结果
- **AND** 后端 MUST NOT 因日志 SSE 广播失败将任务标记为失败
- **AND** 用户重新订阅任务级日志 SSE 时 SHALL 能从数据库补发已有日志事件

### Requirement: SSE 跨进程订阅必须按运行模式启用
任务运行时 SHALL 只在能够持有 HTTP SSE 连接的进程中启用 Redis SSE 事件订阅，并允许 worker-only 进程仅发布跨进程通知。

#### Scenario: API 模式启用订阅
- **WHEN** 后端以 API 模式或 combined 模式启动
- **THEN** 后端 SHALL 启用项目事件和任务日志事件的 Redis 订阅
- **AND** 收到通知后 SHALL 通过本进程 SSE broker 推送给本地 emitter

#### Scenario: worker 模式不启用订阅
- **WHEN** 后端以 worker 模式启动
- **THEN** 后端 MUST NOT 启用项目事件或任务日志事件的 Redis 订阅推送
- **AND** worker 进程 SHALL 仍能在事件落库后发布跨进程通知

#### Scenario: 无本地订阅者时丢弃通知
- **WHEN** API 进程收到跨进程事件通知
- **AND** 本进程没有对应项目或任务的 SSE emitter
- **THEN** 后端 SHALL 安静丢弃该通知或仅记录 debug 日志
- **AND** 后端 MUST NOT 因无本地 emitter 读取完整历史事件或创建补偿任务
