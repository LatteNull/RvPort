## MODIFIED Requirements

### Requirement: 管理员必须能控制单个 worker 的最大并发
后端 SHALL 允许超级管理员为单个 worker 设置任务消费并发限制，并 SHALL 由目标 worker 周期性拉取后动态应用。

#### Scenario: 设置 worker 并发限制
- **WHEN** 超级管理员调用 worker 并发设置 API 并提交合法 `concurrencyLimit`
- **THEN** 后端 SHALL 更新该 worker 的并发限制
- **AND** 目标 worker SHALL 在后续心跳周期内读取并应用新的并发限制
- **AND** API SHALL 返回更新后的期望并发限制

#### Scenario: 升高 worker 并发限制
- **GIVEN** 目标 worker 当前实际并发为 `1`
- **WHEN** 超级管理员将该 worker 的 `concurrencyLimit` 设置为 `4`
- **THEN** 目标 worker MUST 在应用 Spring AMQP listener 配置时避免 `concurrentConsumers` 大于 `maxConcurrentConsumers`
- **AND** 目标 worker SHALL 将实际任务 consumer 并发调整为 `4`
- **AND** listener 的 `prefetch` MUST 仍为 `1`

#### Scenario: 降低 worker 并发限制
- **GIVEN** 目标 worker 当前实际并发为 `4`
- **WHEN** 超级管理员将该 worker 的 `concurrencyLimit` 设置为 `1`
- **THEN** 目标 worker MUST 在应用 Spring AMQP listener 配置时避免 `concurrentConsumers` 与 `maxConcurrentConsumers` 的校验错误
- **AND** 目标 worker SHALL 将实际任务 consumer 并发调整为 `1`
- **AND** listener 的 `prefetch` MUST 仍为 `1`

#### Scenario: 并发限制为零
- **WHEN** 超级管理员将某个 worker 的 `concurrencyLimit` 设置为 `0`
- **THEN** 目标 worker SHALL 暂停接收新的任务队列消息
- **AND** 已经运行中的任务 SHALL 继续执行，除非用户通过任务取消 API 显式取消

#### Scenario: 并发限制恢复为正数
- **WHEN** 超级管理员将某个 worker 的 `concurrencyLimit` 从 `0` 设置为正数
- **THEN** 目标 worker SHALL 恢复接收任务队列消息
- **AND** 实际并发 SHALL 不超过新的 `concurrencyLimit`
