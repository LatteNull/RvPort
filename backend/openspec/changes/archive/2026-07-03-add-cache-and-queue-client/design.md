# add-cache-and-queue-client 设计

## 设计目标

建立应用侧 Redis 和 RabbitMQ 客户端边界，让后续业务模块使用稳定、窄口径的能力，而不是直接依赖底层模板和散落配置。

目标不是重新发明 Spring 的客户端，而是把 RvPort 的业务约束固定下来：

- Redis 是缓存和短期状态，不是事实来源。
- RabbitMQ 只做任务投递，不保存任务输入、状态、结果或日志。
- PostgreSQL 仍然是任务和业务数据的事实来源。

## 总体结构

```text
业务服务
  │
  ├─ RedisCacheClient
  │    ├─ key namespace
  │    ├─ TTL 必填
  │    └─ string/json/increment/delete
  │
  └─ TaskQueueClient
       ├─ TaskQueueMessage
       ├─ exchange / queue / routing key
       └─ RabbitTemplate
```

## Redis 客户端边界

建议新增包：

```text
cn.rvport.backend.cache
```

建议核心类型：

```text
RedisCacheClient
RedisKey
RedisCacheProperties
```

Redis 客户端只暴露短期缓存所需操作：

- `set(key, value, ttl)`
- `get(key, type)`
- `delete(key)`
- `increment(key, ttl)`
- `expire(key, ttl)`

所有写入必须显式提供 TTL，避免业务缓存永久残留。

### Redis 序列化

Redis 业务缓存必须避免使用 JDK 序列化作为 key 序列化方式。否则 Redis 原生命令看到的 key 会带有不可读二进制前缀，例如：

```text
\xac\xed\x00\x05t\x00...
```

约定如下：

```text
key serializer        -> StringRedisSerializer
hash key serializer   -> StringRedisSerializer
value serializer      -> JSON serializer
hash value serializer -> JSON serializer
```

也就是说：key 和 hash key 永远是字符串；JSON 只用于 value 和 hash value。

### Key namespace

业务缓存 key 建议统一形态：

```text
rvport:cache:<domain>:<purpose>:<id>
```

示例：

```text
rvport:cache:auth:nonce:<nonceId>
rvport:cache:rate-limit:login:<username-or-ip>
```

Spring Session namespace 继续由：

```text
spring.session.redis.namespace
```

或现有环境变量：

```text
RVPORT_SESSION_REDIS_NAMESPACE
```

控制。业务缓存 namespace 不得与 session namespace 混用。

## RabbitMQ 客户端边界

建议新增包：

```text
cn.rvport.backend.queue
```

建议核心类型：

```text
TaskQueueClient
TaskQueueMessage
TaskQueueProperties
```

队列消息建议保持最小化：

```json
{
  "taskId": "uuid",
  "taskType": "KB_SCAN",
  "projectId": "uuid",
  "createdAt": "2026-07-02T16:00:00+08:00"
}
```

其中：

- `taskId` 必须存在。
- `taskType` 用于 worker 路由。
- `projectId` 可用于 worker 日志、指标或后续路由，但不能替代数据库读取。
- 消息不得包含任务输入快照、任务结果、完整日志、状态事实或凭据明文。

## RabbitMQ 配置

建议配置前缀：

```yaml
rvport:
  queue:
    task:
      exchange: ${RVPORT_TASK_QUEUE_EXCHANGE:rvport.tasks}
      queue: ${RVPORT_TASK_QUEUE_NAME:rvport.tasks.default}
      routing-key: ${RVPORT_TASK_QUEUE_ROUTING_KEY:task.default}
```

后续如果区分 API 和 worker，可由 worker 绑定同一 queue 或不同 routing key。本变更只建立 publisher 和配置，不实现 consumer。

### 队列类型和可靠性

任务队列必须显式声明为 durable quorum queue：

```text
durable = true
exclusive = false
auto-delete = false
x-queue-type = quorum
```

原因：

- RabbitMQ 后续可能以集群方式部署。
- quorum queue 更适合需要副本一致性的任务投递场景。
- 避免先使用默认 classic queue，后续集群化时再迁移队列语义。

任务消息应使用持久化投递：

```text
delivery mode = persistent
content type = application/json
```

worker 侧消费必须使用 manual acknowledgment。虽然本变更不实现 consumer，但配置和文档需要提前约定：

```text
acknowledge-mode = manual
```

这样后续 worker 只有在成功读取 PostgreSQL、推进任务状态并完成必要处理后才确认消息。处理失败、进程退出或连接断开时，消息不应因为自动确认而静默丢失。

## 序列化约定

RabbitMQ 任务消息使用 JSON 序列化，并声明内容类型为 `application/json`。

理由：

- 本地调试时可以通过 RabbitMQ management UI 直接查看。
- 后续如果拆 worker 进程，跨语言兼容性更好。
- 消息结构简单，不需要 Java 序列化。

Redis 值序列化建议：

- 简单值使用 string。
- 结构化短期值使用 JSON。
- key 和 hash key 使用 string serializer，不使用 JSON 或 JDK serializer。
- 不存储明文秘密。

## 与后续任务 runtime 的关系

本变更只提供投递客户端，不定义完整任务状态机实现。后续 `add-task-runtime` 应负责：

```text
API 创建任务
  -> 写入 PostgreSQL tasks
  -> 写入 task_events
  -> 使用 TaskQueueClient 投递 taskId
  -> 返回 taskId
```

worker 消费后必须回到 PostgreSQL 读取任务输入快照并更新状态。

## 验证策略

apply 阶段建议验证：

- `RedisCacheProperties` 和 `TaskQueueProperties` 配置绑定测试通过。
- Redis key builder 能稳定生成带 namespace 的 key。
- Redis 原生命令看到的业务缓存 key 是可读字符串，不带 JDK 序列化前缀。
- Redis 写入 API 不允许缺省 TTL。
- `TaskQueueMessage` JSON 序列化字段符合 API/数据库边界。
- `TaskQueueClient` 使用配置的 exchange 和 routing key 调用 `RabbitTemplate`。
- 任务队列声明包含 `x-queue-type = quorum`。
- 任务消息使用 persistent delivery mode。
- RabbitMQ listener ack mode 配置为 manual，为后续 worker 消费预留可靠确认边界。
- `mvn test` 通过。
- `openspec validate add-cache-and-queue-client` 通过。

## 未解决问题

- 是否需要死信队列：建议在 worker 消费和重试策略确定后再设计。
- Redis 是否需要统一 metrics：可以在缓存使用场景增多后补充。
