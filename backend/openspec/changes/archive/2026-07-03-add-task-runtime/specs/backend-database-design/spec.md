## MODIFIED Requirements

### Requirement: 任务状态持久化存储在 PostgreSQL
系统 SHALL 将 PostgreSQL 作为异步任务状态、任务事件、任务日志元数据和任务关联业务结果的事实来源。

#### Scenario: 创建任务并投递队列
- **WHEN** API 请求创建长时间运行任务
- **THEN** 系统 MUST 先插入 `tasks` 记录，再将任务 ID 投递到队列
- **AND** 初始任务状态 SHALL 为 `PENDING`
- **AND** 队列投递成功后任务状态 SHALL 更新为 `QUEUED`

#### Scenario: 队列载荷最小化
- **WHEN** 任务被投递到 worker 队列
- **THEN** 队列载荷 MUST 只包含 `task_id` 等路由信息，并 MUST NOT 作为任务输入、状态、进度或结果的权威存储

#### Scenario: 修复待投递任务
- **WHEN** 任务已经持久化但长时间停留在 `PENDING`
- **THEN** 系统 SHALL 能基于 PostgreSQL 中的任务记录重新投递任务消息
- **AND** 修复流程 MUST NOT 从 RabbitMQ 或 Redis 推导任务事实

#### Scenario: Worker 更新任务生命周期
- **WHEN** worker 启动、推进、成功、失败、超时或取消任务
- **THEN** worker MUST 更新 PostgreSQL 中的任务状态并追加任务事件
- **AND** worker MUST 使用 PostgreSQL 原子状态变更避免重复消息导致重复执行

### Requirement: SSE 恢复使用持久化任务事件
系统 SHALL 将任务事件持久化到 PostgreSQL，使项目级 SSE 通道能在客户端重连后恢复。

#### Scenario: 客户端携带最后事件 ID 重连
- **WHEN** 前端携带最后消费的事件 ID 重连项目任务事件流
- **THEN** 后端 SHALL 将该 ID 作为 `task_events.id` 游标
- **AND** 后端 SHALL 从持久化的 `task_events` 数据中读取同一项目内后续事件
- **AND** 后续事件 SHALL 按 `task_events.id` 升序返回

#### Scenario: 事件流不包含完整日志
- **WHEN** 任务发出进度或日志更新
- **THEN** 持久化任务事件 SHALL 包含状态、进度、消息、日志级别和短摘要，但 MUST NOT 保存完整 stdout 或 stderr 日志

#### Scenario: 事件游标可索引查询
- **WHEN** 后端按项目和最后事件 ID 恢复 SSE 事件
- **THEN** 数据库 SHALL 支持按 `project_id` 和递增事件 ID 查询后续 `task_events`
