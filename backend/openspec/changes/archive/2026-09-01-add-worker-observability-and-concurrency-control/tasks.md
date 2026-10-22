## 1. Schema 与配置

- [x] 1.1 新增 `worker_instances` Liquibase migration，包含实例标识、主机信息、并发限制、实际并发、运行任务数、启动时间和心跳时间。
- [x] 1.2 重新生成 jOOQ 代码，并确认生成代码进入 `backend/src/generated/java`。
- [x] 1.3 扩展 `rvport.worker` 配置，增加运行模式、默认并发限制、最大并发上限、心跳间隔和离线阈值。
- [x] 1.4 固定 RabbitMQ task listener `prefetch=1`，不通过 `.env`、Compose 或 API 暴露编辑入口。

## 2. Worker 运行模式与心跳

- [x] 2.1 实现 API、worker、combined 运行模式，确保 API 模式不启动任务 listener，worker 模式不启动 HTTP 服务。
- [x] 2.2 实现 worker 实例注册和周期性心跳 upsert。
- [x] 2.3 在心跳中更新 `activeConcurrency`、`activeTaskCount` 和最近心跳时间。
- [x] 2.4 查询 worker 状态时按离线阈值计算 `ONLINE` / `OFFLINE`。

## 3. Worker 并发控制

- [x] 3.1 使用 Spring AMQP listener container 支持动态设置 `concurrencyLimit`。
- [x] 3.2 worker 周期性读取自身 `concurrencyLimit` 并应用变更。
- [x] 3.3 支持 `concurrencyLimit=0` 暂停接收新任务，恢复正数后继续消费。
- [x] 3.4 动态降低并发时不强制取消已经运行中的任务。

## 4. 管理员 API

- [x] 4.1 实现 `GET /api/admin/workers`，支持分页、排序、过滤并返回 worker 摘要。
- [x] 4.2 实现 `GET /api/admin/workers/{workerInstanceId}`，返回 worker 详情和当前运行任务列表。
- [x] 4.3 实现 `PUT /api/admin/workers/{workerInstanceId}/concurrency`，校验 `0 <= concurrencyLimit <= maxConcurrencyLimit`。
- [x] 4.4 确保 worker 管理 API 仅超级管理员可访问，并在无权限时不泄露 worker、主机或任务信息。

## 5. 部署与文档

- [x] 5.1 更新 Docker Compose，使同一后端镜像可分别以 API 节点和 worker 节点运行。
- [x] 5.2 确认 API 和 worker 服务共享 runtime volume。
- [x] 5.3 更新 README 或后端运行文档，说明 API/worker 模式、worker 并发配置、共享 volume 要求和不负责 Swarm/K8s scale。

## 6. 测试与验证

- [x] 6.1 增加 worker 实例注册、心跳、离线判定和并发限制校验的单元测试。
- [x] 6.2 增加 Rabbit listener 并发控制测试，覆盖并发大于一、并发为零和动态降低并发。
- [x] 6.3 增加 worker API 正常流程、异常流程和 edge case 测试。
- [x] 6.4 增加 E2E 模块，验证 worker 列表、详情、并发调整、暂停接新任务和权限边界。
- [x] 6.5 运行目标单元测试、E2E 模块和 OpenSpec 严格校验。
