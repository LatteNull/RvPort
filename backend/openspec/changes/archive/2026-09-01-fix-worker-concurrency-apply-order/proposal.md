## Why

管理员通过 API 将 worker 并发从 1 调整到 4 后，数据库配置已更新，但 worker 心跳应用到 Spring AMQP listener 时持续报错，导致实际 consumer 数仍为 1。

## What Changes

- 修复 worker 动态应用并发限制时的 AMQP listener 设置顺序。
- 保证从低并发升高、从高并发降低以及恢复接收任务时都不会触发 `concurrentConsumers` 与 `maxConcurrentConsumers` 的校验错误。
- 补充单元测试，覆盖并发升高、降低和暂停场景。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `worker-observability`: 明确 worker 动态应用并发限制时必须同时支持升高和降低，并保持固定 `prefetch=1`。

## Impact

- 影响 `WorkerConcurrencyController` 的运行时并发应用逻辑。
- 影响 worker 心跳应用并发限制后的 RabbitMQ consumer 数。
- 不修改 API 结构、数据库 schema 或前端契约。
