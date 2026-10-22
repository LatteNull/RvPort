## ADDED Requirements

### Requirement: 后端必须封装 Redis 业务缓存客户端
后端应用 SHALL 提供 Redis 业务缓存客户端封装，使业务模块通过统一入口使用 Redis 短期缓存。

#### Scenario: 写入业务缓存
- **WHEN** 后端业务模块需要写入 Redis 短期业务缓存
- **THEN** 业务模块 SHALL 通过统一 Redis 缓存客户端写入
- **AND** 写入操作 MUST 显式指定 TTL
- **AND** 业务模块 SHOULD NOT 直接拼接 Redis key

#### Scenario: 区分业务缓存和 Session
- **WHEN** 后端同时使用 Spring Session Redis 和业务缓存
- **THEN** 业务缓存 key SHALL 使用独立 namespace
- **AND** 业务缓存 namespace MUST NOT 与 Spring Session namespace 混用

#### Scenario: Redis key 使用字符串序列化
- **WHEN** 后端业务缓存客户端写入 Redis key 或 hash key
- **THEN** key 和 hash key MUST 使用字符串序列化
- **AND** value 和 hash value MAY 使用 JSON 序列化
- **AND** Redis 原生命令看到的业务缓存 key MUST NOT 包含 JDK 序列化二进制前缀

#### Scenario: Redis 不承载权威业务状态
- **WHEN** Redis 缓存数据过期、丢失或被清理
- **THEN** 系统 MUST NOT 因此丢失 PostgreSQL 中的权威业务状态

### Requirement: 后端必须封装 RabbitMQ 任务投递客户端
后端应用 SHALL 提供 RabbitMQ 任务投递客户端封装，使长任务创建流程通过统一入口投递任务消息。

#### Scenario: 投递任务消息
- **WHEN** 后端需要将长任务投递到 RabbitMQ
- **THEN** 后端 SHALL 通过统一任务队列客户端投递
- **AND** 任务队列客户端 SHALL 使用可配置的 exchange、queue 和 routing key

#### Scenario: 最小化任务消息载荷
- **WHEN** 后端构造任务队列消息
- **THEN** 消息 MUST 包含 `taskId`
- **AND** 消息 MAY 包含任务类型、项目 ID 或必要路由字段
- **AND** 消息 MUST NOT 包含任务输入快照、任务结果、完整日志、任务状态事实或明文凭据

#### Scenario: 使用 JSON 消息格式
- **WHEN** 任务队列客户端发送 RabbitMQ 消息
- **THEN** 消息 SHOULD 使用 JSON 序列化
- **AND** 消息内容类型 SHOULD 标记为 `application/json`
- **AND** 消息 SHOULD 使用 persistent delivery mode

#### Scenario: 预留手动确认消费模式
- **WHEN** 后续 worker 消费 RabbitMQ 任务消息
- **THEN** RabbitMQ listener ack mode SHOULD 使用 manual
- **AND** worker SHOULD 在任务处理结果已可靠写回 PostgreSQL 后确认消息
- **AND** worker MUST NOT 依赖自动确认作为任务完成信号
