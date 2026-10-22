# add-cache-and-queue-client 提案

## 背景

后端工程已经引入 Redis、RabbitMQ 相关 Spring Boot starter，并通过 `application.yml` 从环境变量读取连接配置。当前仍缺少应用侧统一客户端封装：业务模块如果直接使用底层 `RedisTemplate`、`RabbitTemplate` 或散落的 key / exchange / routing key 字符串，后续会难以保证 Redis 只作为缓存、RabbitMQ 只作为任务投递通道。

本变更用于补齐 Redis 客户端和 RabbitMQ 客户端封装，为后续认证、限流、任务投递和 worker 主干提供稳定基础。

## 范围

本变更将：

- 新增 Redis 缓存客户端封装。
- 建立 Redis key namespace 约定。
- 明确 Redis key/hash key 使用字符串序列化，避免 JDK 或 JSON 序列化导致 Redis key 出现不可读前缀。
- 要求业务 Redis 写入必须显式设置 TTL。
- 保持 Spring Session Redis 独立使用，不与业务缓存 key 混用。
- 新增 RabbitMQ 任务投递客户端封装。
- 定义任务队列消息模型，只允许携带 `task_id` 和必要路由信息。
- 定义 RabbitMQ exchange、queue、routing key 配置项。
- 将任务队列声明为 durable quorum queue，以适配后续 RabbitMQ 集群部署。
- 要求任务消息持久化投递，并为后续 worker 消费使用手动确认模式预留配置。
- 建立 RabbitMQ JSON 消息序列化约定。
- 增加配置绑定和基础单元测试。
- 更新中文后端开发计划，说明 Redis/RabbitMQ 客户端边界。

本变更不做：

- 不实现完整任务创建服务。
- 不实现 worker 消费和任务状态推进。
- 不实现 SSE。
- 不把 Redis 作为任务状态事实来源。
- 不把 RabbitMQ 消息设计成任务输入、任务结果或日志载体。
- 不修改现有数据库 schema。

## 影响文件

预计影响：

- `pom.xml`
- `src/main/resources/application.yml`
- `src/main/java/cn/rvport/backend/config/**`
- `src/main/java/cn/rvport/backend/cache/**`
- `src/main/java/cn/rvport/backend/queue/**`
- `src/test/java/cn/rvport/backend/**`
- `docs/BACKEND_DEVELOPMENT_PLAN.md`
- `openspec/specs/backend-app-skeleton/spec.md`
- `openspec/specs/backend-infrastructure/spec.md`

## 验收标准

- 后端提供统一 Redis 缓存客户端，业务代码不需要直接拼接 Redis key。
- Redis 业务缓存 key 使用统一前缀，并与 Spring Session namespace 分离。
- Redis 业务缓存 key 在 Redis 原生命令下必须是可读字符串，不得出现 JDK 序列化二进制前缀。
- Redis 写入短期业务数据时必须显式提供 TTL。
- 后端提供 RabbitMQ 任务投递客户端。
- RabbitMQ 任务消息只包含 `taskId`、任务类型或路由所需字段，不包含任务输入、结果、日志或状态事实。
- RabbitMQ exchange、queue、routing key 可通过环境变量配置。
- RabbitMQ 任务队列声明为 durable quorum queue。
- RabbitMQ 消息以 persistent delivery mode 投递。
- RabbitMQ listener ack mode 预留为 manual，后续 worker 消费成功后才能确认消息。
- 配置绑定测试通过。
- 消息序列化测试通过。
- `mvn test` 通过。
- `openspec validate add-cache-and-queue-client` 通过。
