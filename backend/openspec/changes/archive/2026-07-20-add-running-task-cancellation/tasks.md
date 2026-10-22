## 1. 数据库和 jOOQ

- [x] 1.1 新增 Liquibase changeset，创建任务运行时句柄表，包含 `task_id`、`project_id`、`worker_instance_id`、handle 类型、local PID、remote PID/PGID、environment ID、状态、取消时间、结束时间、错误码、错误摘要和 metadata。
- [x] 1.2 为 runtime handle 表增加必要索引：`task_id`、`project_id`、`worker_instance_id`、`status`、`updated_at`。
- [x] 1.3 扩展 `tasks` 表取消字段，记录取消请求时间、取消人和取消原因。
- [x] 1.4 运行 Liquibase，并使用数据库查询确认 schema、索引和约束符合设计。
- [x] 1.5 运行 jOOQ 生成脚本，更新生成代码并确认 Maven 编译通过。

## 2. RabbitMQ 取消基础设施

- [x] 2.1 新增取消队列配置属性，支持取消 exchange、routing key 前缀、队列名前缀、DLX、DLQ、mandatory publish、publisher return、重试和 grace period。
- [x] 2.2 在 RabbitMQ 配置中声明取消 exchange、取消 DLX 和 worker 专属取消队列绑定。
- [x] 2.3 实现取消消息模型和取消队列客户端，消息只包含 `taskId`、`runtimeHandleId`、`workerInstanceId`、请求时间和安全原因，并启用 mandatory publish。
- [x] 2.4 实现 publisher return callback，将 unroutable 取消消息写回 runtime handle 的路由不可达或 worker 不存在状态。
- [x] 2.5 实现取消 listener，使用 manual ack，并在清理状态可靠写回后确认消息。
- [x] 2.6 为取消消息失败路径配置 retry/DLQ，并写入 runtime handle 清理失败状态。

## 3. Worker 实例和运行 registry

- [x] 3.1 实现 `workerInstanceId` 生成和配置读取，确保每个 worker 实例具备稳定唯一标识。
- [x] 3.2 实现本 JVM `TaskExecutionRegistry`，支持注册、查询、取消和移除运行中任务句柄。
- [x] 3.3 改造任务认领流程，任务进入 `RUNNING` 后创建 active runtime handle 并写入数据库。
- [x] 3.4 改造任务完成、失败、超时和取消路径，确保 runtime handle 从 active 更新为终态并从 registry 移除。
- [x] 3.5 确保 worker 收到已取消任务或 handler 抛出取消异常时 ack 原任务消息且不重试。

## 4. 任务取消 API 和事件

- [x] 4.1 改造 `POST /api/tasks/{taskId}/cancel`，支持 `RUNNING` 任务进入 `CANCELLED` 并追加 `task.cancelled` 事件。
- [x] 4.2 保留 `PENDING` 和 `QUEUED` 取消逻辑，并确保旧队列消息被 worker 幂等跳过。
- [x] 4.3 对 `RUNNING` 任务读取 active runtime handle，并按 `workerInstanceId` 定点投递取消消息。
- [x] 4.4 对无 active runtime handle、worker lost、重复取消和终态任务实现明确幂等行为。
- [x] 4.5 确保取消 API 继续执行项目访问守卫，并避免暴露资源是否存在之外的敏感信息。

## 5. 执行上下文和 runtime adapter

- [x] 5.1 扩展任务执行上下文，增加取消检查、取消异常和可取消资源登记能力。
- [x] 5.2 改造长时间 handler，在关键步骤前后检查取消请求。
- [x] 5.3 改造 Git 本地进程执行，登记 local process handle，并支持取消时终止进程树。
- [x] 5.4 改造 SBOM 分析器进程执行，登记 local process handle，并支持取消时终止进程树。
- [x] 5.5 改造 SSH runtime，远程命令通过包装脚本记录 PID/PGID，并支持远程 TERM/KILL 清理。
- [x] 5.6 确保取消、失败和超时路径都不会泄露明文凭据、服务器真实路径或完整命令输入。

## 6. 单元测试和集成测试

- [x] 6.1 为 runtime handle repository 覆盖正常创建/更新、异常输入和重复 active handle edge case。
- [x] 6.2 为取消队列客户端和 listener 覆盖定点 routing key、mandatory publish、publisher return、manual ack、失败重试和 DLQ 路径。
- [x] 6.3 为 `TaskExecutionRegistry` 覆盖注册/取消/移除、重复取消和任务不存在。
- [x] 6.4 为取消 API 覆盖 `PENDING`、`QUEUED`、`RUNNING`、终态、无权限和重复取消。
- [x] 6.5 为本地 process 取消覆盖正常退出、grace period 后强杀和 process 已退出 edge case。
- [x] 6.6 为 SSH 远程取消覆盖 PID/PGID 记录、远程 kill 命令构造、连接失败和清理失败。

## 7. E2E 和真实联通验证

- [x] 7.1 增加 E2E task 模块 case，验证运行中任务取消后任务详情、任务列表和 SSE 都返回 `CANCELLED`。
- [x] 7.2 增加无权限取消运行中任务 E2E，验证状态、事件和取消消息不发生变化。
- [x] 7.3 增加重复取消 E2E，验证幂等行为和无重复清理副作用。
- [x] 7.4 增加 test-support 能力，用于创建可控运行中任务、触发取消清理失败和查询 runtime handle。
- [x] 7.5 增加目标 worker 取消队列不存在的 E2E，验证 unroutable publisher return 会写回 runtime handle。
- [x] 7.6 启动真实后端、RabbitMQ、PostgreSQL 和 Redis，运行相关模块 E2E 并记录结果。

## 8. 文档和收尾

- [x] 8.1 更新 README 或后端文档，说明 worker 模式、取消队列配置和运行中取消语义。
- [x] 8.2 更新 API 文档，说明运行中取消会立即返回 `CANCELLED`，底层清理由 runtime handle 记录。
- [x] 8.3 运行 `mvn test`，确保单元测试全部通过。
- [x] 8.4 运行相关 E2E 模块，确保正常流程、异常流程和 edge case 覆盖通过。
- [x] 8.5 检查 OpenSpec 状态，确认 change 可进入 apply。
