## MODIFIED Requirements

### Requirement: RabbitMQ 作为异步任务投递队列
基础设施 SHALL 使用 RabbitMQ 作为异步任务投递队列，并 SHALL 保持队列载荷最小化。

#### Scenario: 启动 RabbitMQ
- **WHEN** Compose 启动 RabbitMQ 服务
- **THEN** 服务 SHALL 使用 `rabbitmq:4.3.2-management`
- **AND** SHALL 暴露 AMQP 端口和本地管理界面端口
- **AND** RabbitMQ 用户、密码和 vhost SHALL 从环境变量读取

#### Scenario: 投递任务消息
- **WHEN** 后端 API 创建长任务并投递队列
- **THEN** RabbitMQ 消息载荷 SHALL 只包含 `task_id` 和必要路由信息
- **AND** RabbitMQ MUST NOT 作为任务输入、任务状态、任务进度、任务结果或日志的事实来源
- **AND** 后端 SHALL 通过统一任务队列客户端投递 RabbitMQ 消息

#### Scenario: 配置任务队列路由
- **WHEN** 后端应用启动
- **THEN** 任务队列 exchange、queue 和 routing key SHALL 可通过环境变量配置

#### Scenario: 使用集群友好的任务队列类型
- **WHEN** 后端声明 RabbitMQ 任务队列
- **THEN** 任务队列 SHALL 声明为 durable queue
- **AND** 任务队列 SHOULD 使用 `x-queue-type = quorum`
- **AND** 任务消息 SHOULD 使用 persistent delivery mode

#### Scenario: 使用手动确认消费模式
- **WHEN** 后续 worker 消费 RabbitMQ 任务队列消息
- **THEN** RabbitMQ listener ack mode SHOULD 配置为 manual
- **AND** 消息确认 SHOULD 发生在 worker 已完成必要处理并写回 PostgreSQL 之后

### Requirement: Redis 作为缓存而不是事实来源
基础设施 SHALL 使用 Redis 作为缓存和短期状态存储，但 SHALL NOT 作为业务事实来源。

#### Scenario: 启动 Redis
- **WHEN** Compose 启动 Redis 服务
- **THEN** 服务 SHALL 使用 `redis:8.8.0`
- **AND** Redis 端口和密码 SHALL 从环境变量读取

#### Scenario: 使用 Redis 缓存
- **WHEN** 后端需要缓存登录态、token、短期 nonce 或限流计数
- **THEN** 后端 MAY 使用 Redis 保存这些短期数据
- **AND** Redis 数据失效或丢失 MUST NOT 破坏 PostgreSQL 中的权威业务状态
- **AND** 后端业务缓存 SHOULD 通过统一 Redis 缓存客户端访问

#### Scenario: 避免 Redis 承载任务事实
- **WHEN** 任务状态、任务事件、任务结果或审计记录需要保存
- **THEN** 系统 MUST 使用 PostgreSQL 作为事实来源
- **AND** 系统 MUST NOT 依赖 Redis 作为任务队列

#### Scenario: 配置业务缓存命名空间
- **WHEN** 后端应用启动
- **THEN** Redis 业务缓存 namespace SHALL 可通过环境变量配置
- **AND** Redis 业务缓存 namespace SHALL 与 Spring Session namespace 分离

#### Scenario: 使用可读 Redis key
- **WHEN** 后端业务缓存客户端写入 Redis key
- **THEN** Redis key SHALL 使用字符串序列化
- **AND** Redis key MUST NOT 因 JDK 或 JSON key 序列化产生不可读二进制前缀
