## ADDED Requirements

### Requirement: Worker 必须支持单实例可配置并发消费
任务运行时 SHALL 允许同一个 worker 实例按配置的并发限制启动多个 RabbitMQ consumer，并 SHALL 保持任务认领、ack/nack、重试和取消语义不变。

#### Scenario: 单 worker 并发消费多个任务
- **WHEN** worker 的 `concurrencyLimit` 大于 `1`
- **AND** 任务队列中存在多个可认领任务
- **THEN** worker SHALL 允许多个 consumer 并发认领不同任务
- **AND** 每个任务 SHALL 继续通过 PostgreSQL 原子状态变更从 `PENDING` 或 `QUEUED` 进入 `RUNNING`

#### Scenario: 并发任务独立 ack
- **WHEN** 同一个 worker 内多个任务并发执行
- **THEN** 每条 RabbitMQ 消息 SHALL 在对应任务完成、失败、取消或重试状态可靠写回后独立 ack 或 nack
- **AND** 一个任务失败或重试 MUST NOT 导致其他正在运行任务被 ack、nack 或取消

#### Scenario: 并发任务取消隔离
- **WHEN** 同一个 worker 内多个任务并发运行
- **AND** 用户取消其中一个任务
- **THEN** 取消消息 SHALL 定位到目标 worker
- **AND** worker SHALL 只取消对应 `taskId` 的运行句柄
- **AND** 同 worker 内其他任务 SHALL 继续运行

#### Scenario: 并发限制为零时暂停消费
- **WHEN** worker 读取到 `concurrencyLimit=0`
- **THEN** 任务 listener SHALL 暂停接收新任务消息
- **AND** 已经被 consumer 认领并执行中的任务 SHALL 继续按原生命周期完成

#### Scenario: 动态降低并发不强杀运行任务
- **WHEN** worker 当前运行任务数大于新的 `concurrencyLimit`
- **THEN** worker SHALL 停止或减少后续新任务消费
- **AND** worker MUST NOT 因并发限制降低而强制终止已经运行的任务

### Requirement: Worker 运行模式必须控制任务 listener 启停
任务运行时 SHALL 根据应用运行模式决定是否启动任务队列 listener，避免 API-only 节点消费任务。

#### Scenario: API 模式不消费任务
- **WHEN** 后端以 API 模式启动
- **THEN** 任务队列 listener MUST NOT 启动
- **AND** 该节点 MUST NOT 注册为可执行任务的 worker

#### Scenario: Worker 模式消费任务
- **WHEN** 后端以 worker 模式启动
- **THEN** 任务队列 listener SHALL 启动
- **AND** 该节点 SHALL 注册 worker 实例并上报心跳

#### Scenario: Combined 模式兼容本地开发
- **WHEN** 后端以 combined 模式启动
- **THEN** 后端 MAY 同时启动 HTTP API 和任务队列 listener
- **AND** 该模式 SHALL 保持本地开发可用
