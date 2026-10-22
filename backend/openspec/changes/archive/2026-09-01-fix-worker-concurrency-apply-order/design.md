## Context

当前 worker 并发限制存储在 `worker_instances.concurrency_limit`，管理员 API 更新该值后，worker 心跳通过 `WorkerConcurrencyController` 将其应用到 Spring AMQP `SimpleMessageListenerContainer`。

现有实现直接执行：

```java
setConcurrentConsumers(limit);
setMaxConcurrentConsumers(limit);
```

当当前 max 仍为 1 且目标 limit 为 4 时，Spring AMQP 会在第一步抛出：

```text
'concurrentConsumers' cannot be more than 'maxConcurrentConsumers'
```

## Decision

`WorkerConcurrencyController` 应根据当前并发值和目标并发值选择安全顺序：

- 升高并发：先设置 `maxConcurrentConsumers`，再设置 `concurrentConsumers`。
- 降低并发：先设置 `concurrentConsumers`，再设置 `maxConcurrentConsumers`。
- 目标并发为 0：停止 listener，不再消费新消息。
- 目标并发为正数且 listener 未运行：应用目标并发后启动 listener。
- 始终保持 `prefetchCount=1`。

## Risks

- 调整运行中 listener 的并发属于运行时行为，单元测试需要用 mock 覆盖 setter 调用顺序。
- 实际 consumer 数由 Spring AMQP 异步调整，E2E 验证需要等待一个心跳周期后观察 RabbitMQ。

## Validation

- 增加 `WorkerConcurrencyController` 单元测试，覆盖 `1 -> 4`、`4 -> 1`、`0` 暂停和正数恢复。
- 本地运行目标测试。
- 重建并重启后端 worker 容器后，通过 admin worker API 设置并发为 4，观察 `worker_instances.active_concurrency` 与 RabbitMQ queue consumers。
