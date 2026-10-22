## Context

当前 worker 由 `@RabbitListener` 消费统一任务队列，`TaskWorkerService.process()` 在 listener 线程中同步执行任务，完成后再 ack/nack RabbitMQ 消息。Rabbit listener container 未显式设置并发参数，因此单个后端实例默认只能低并发消费长任务。

现有运行中任务取消机制已经记录 `workerInstanceId`，并通过 worker 专属取消队列定点投递取消消息。`TaskExecutionRegistry` 以 `taskId -> RunningTaskHandle` 管理当前 JVM 内运行任务，可以支持同一 worker 实例内多个任务并发，只要每个任务仍由独立 consumer 线程同步执行即可。

部署层面，项目会使用 Docker Swarm 或未来 Kubernetes 管理 worker 容器副本数量。RvPort 不负责 scale 编排，只需要自动感知接入的 worker，并允许管理员控制单个 worker 的最大任务消费并发。多 API/worker 容器部署时，runtime 日志、源码、报告和临时制品需要共享 volume 或等效共享存储。

## Goals / Non-Goals

**Goals:**

- 同一后端镜像支持 API 节点和 worker 节点两种运行模式。
- worker 节点自动注册实例信息并持续心跳。
- 管理员可以查看 worker 列表、在线状态、当前并发和正在执行的任务。
- 管理员可以调整单个 worker 的 `concurrencyLimit`，worker 周期性拉取并动态应用。
- RabbitMQ 任务消费者支持单 worker 内多 consumer 并发。
- `prefetch` 固定为 `1`，避免长任务被某个 worker 预取囤积。
- `concurrencyLimit=0` 表示暂停接收新任务，已有运行任务继续执行。
- 保持现有任务认领、重试、DLQ、日志、SSE 和取消机制语义。

**Non-Goals:**

- 不实现 Docker Swarm scale API。
- 不实现 Kubernetes scale API。
- 不提供页面控制 worker 容器副本数量。
- 不开放 `prefetch` 配置、展示或编辑。
- 不把任务执行改为 listener ack 后后台线程异步执行。
- 不改变业务任务 handler 的输入输出协议。

## Decisions

### 运行模式拆分

新增应用运行模式配置，建议使用 `RVPORT_APP_MODE=api|worker|combined` 或等效配置。生产部署推荐：

- `api`：启动 HTTP API、SSE、管理接口，不启动任务队列 listener。
- `worker`：启动任务队列 listener 和 worker 心跳，不启动 HTTP server。
- `combined`：保留本地开发兼容模式，可同时启动 HTTP API 和 worker。

worker-only 模式应使用 `spring.main.web-application-type=none` 或等效配置禁用 Tomcat，降低无意义暴露面。Compose 中应拆分 `backend` 和 `backend-worker` 服务，两者使用同一镜像和同一套共享 runtime volume。

### worker 实例表作为观测事实来源

新增 `worker_instances` 表，记录自动接入 worker 的状态：

```text
worker_instances
  id
  instance_id unique
  hostname
  process_id
  app_version
  status
  concurrency_limit
  active_concurrency
  active_task_count
  started_at
  last_heartbeat_at
  metadata
  created_at
  updated_at
```

`OFFLINE` 不要求 worker 主动写入。查询时可按 `now - last_heartbeat_at > offlineTimeout` 计算离线状态，也可以由定时维护任务落库更新。

`active_task_count` 可由 worker 心跳写入当前 JVM 内 registry 数量，也可在查询时通过 `task_runtime_handles` 和 `tasks` 计算。为了管理员列表查询效率，心跳中写入当前值，详情接口再关联任务明细。

### 单 worker 并发由数据库控制

worker 启动时以环境变量默认值注册 `concurrencyLimit`。管理员通过 API 修改某个 `workerInstanceId` 的并发限制后，目标 worker 在下一次心跳周期读取到变更并应用到 listener container。

推荐配置：

```yaml
rvport:
  worker:
    concurrency-limit: ${RVPORT_WORKER_CONCURRENCY_LIMIT:1}
    max-concurrency-limit: ${RVPORT_WORKER_MAX_CONCURRENCY_LIMIT:8}
    heartbeat-interval-seconds: ${RVPORT_WORKER_HEARTBEAT_INTERVAL_SECONDS:10}
    offline-timeout-seconds: ${RVPORT_WORKER_OFFLINE_TIMEOUT_SECONDS:60}
```

管理员写入值必须满足：

```text
0 <= concurrencyLimit <= maxConcurrencyLimit
```

### 使用 Spring AMQP listener container 并发

并发控制应使用 Spring AMQP 自带 listener container 能力，而不是在 `onMessage()` 中自行开启后台线程后提前 ack。

目标模型：

```text
worker JVM
  Rabbit listener container
    consumer-1 -> Task A -> ack/nack
    consumer-2 -> Task B -> ack/nack
    consumer-N -> Task N -> ack/nack
```

每个 consumer 线程同步执行任务，任务完成或失败后再确认 RabbitMQ 消息。这样可以保留现有可靠性模型：JVM 崩溃时未 ack 消息仍由 RabbitMQ 重新投递。

### prefetch 固定为 1

`prefetch` 固定为 `1`，不落库、不展示、不开放编辑。原因是 RvPort 任务通常是长任务，如果 prefetch 大于 1，某个 worker 会提前拿走但暂不执行多条任务，导致其他 worker 空闲时无法获得任务。

### 暂停 worker 接新任务

`concurrencyLimit=0` 表示暂停接收新任务。实现上可以停止任务 listener container，已有 consumer 正在执行的任务不应被强制取消。恢复为正数后重新启动 container 并应用对应并发。

取消已有任务仍走现有任务取消 API 和 worker 定点取消队列，不通过并发控制 API 隐式取消。

### 管理员观测 API

新增超级管理员 API：

```http
GET /api/admin/workers
GET /api/admin/workers/{workerInstanceId}
PUT /api/admin/workers/{workerInstanceId}/concurrency
```

列表接口返回分页、排序、过滤，符合后续所有类似接口都支持分页排序过滤的全局约定。详情接口返回 worker 当前运行任务明细，任务来源通过 `task_runtime_handles.worker_instance_id` 关联。

## Risks / Trade-offs

- [Risk] 单 worker 并发增加后可能放大 CPU、磁盘、SSH 和远端资源压力。-> 使用低默认并发、管理员上限和 `prefetch=1` 控制风险。
- [Risk] API 与 worker 拆分后如果没有共享 runtime volume，API 可能读不到 worker 写入的日志或制品。-> Compose 和文档明确共享 volume 为部署前提，长期制品优先进入对象存储。
- [Risk] 动态降低并发不会立即减少已经运行的任务数量。-> 将语义定义为“影响后续消费”，已有任务自然完成；需要停止任务时使用取消 API。
- [Risk] worker 容器异常退出时无法主动注销。-> 使用心跳超时计算 `OFFLINE`。
- [Risk] 多 consumer 并发可能暴露 handler 中隐含的共享状态问题。-> 增加并发单元测试和 E2E，验证多个任务同时运行、单任务取消不影响其他任务。
- [Risk] worker-only 模式禁用 HTTP 后健康检查方式变化。-> worker 健康以心跳和 RabbitMQ 连接为准，容器级健康检查可使用进程存活或轻量命令。
