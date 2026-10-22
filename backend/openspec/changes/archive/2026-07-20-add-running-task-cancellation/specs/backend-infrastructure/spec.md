## ADDED Requirements

### Requirement: RabbitMQ 必须支持 worker 定点取消队列
基础设施 SHALL 为运行中任务取消提供独立 RabbitMQ exchange、worker 专属取消队列和取消 DLQ。

#### Scenario: 配置取消队列路由
- **WHEN** 后端应用启动
- **THEN** 取消 exchange、routing key 前缀、队列名前缀、DLQ、mandatory publish 和 publisher return SHALL 可通过环境变量配置
- **AND** 默认配置 SHALL 与既有任务队列配置互相独立

#### Scenario: Worker 声明专属取消队列
- **WHEN** worker 实例启动并生成 `workerInstanceId`
- **THEN** worker SHALL 声明只服务当前实例的取消队列
- **AND** SHALL 绑定到取消 exchange 的 `worker.cancel.<workerInstanceId>` routing key
- **AND** 取消队列 SHALL 具备明确生命周期控制，避免 worker 下线后废弃队列长期堆积

#### Scenario: 取消消息无法路由
- **WHEN** 后端向取消 exchange 投递取消消息但没有队列匹配 routing key
- **THEN** RabbitMQ publisher return SHALL 被后端捕获
- **AND** 后端 SHALL 将对应 runtime handle 标记为路由不可达或 worker 不存在
- **AND** 后端 MUST NOT 把 publish 成功等同于取消消息已被目标 worker 接收

#### Scenario: 使用集群友好的取消队列配置
- **WHEN** 后端声明取消队列
- **THEN** 取消队列 SHALL 使用 durable 或具备明确生命周期控制的队列配置
- **AND** 取消消息 SHOULD 使用 persistent delivery mode
- **AND** 取消队列 SHOULD 配置 dead-letter exchange

#### Scenario: 使用手动确认取消消息
- **WHEN** worker 消费取消队列消息
- **THEN** RabbitMQ listener ack mode SHALL 配置为 manual
- **AND** 消息确认 SHALL 发生在取消清理状态已经可靠写回 PostgreSQL 之后

#### Scenario: 取消消息进入 DLQ
- **WHEN** 取消清理超过最大重试次数或出现不可恢复错误
- **THEN** 取消消息 SHALL 进入取消 DLQ
- **AND** 后端 SHALL 在 runtime handle 中记录清理失败状态
