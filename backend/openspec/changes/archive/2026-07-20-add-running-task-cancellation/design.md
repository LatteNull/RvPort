## Context

当前任务运行时已经具备 PostgreSQL 持久化任务、RabbitMQ 手动确认消费、任务事件、项目级 SSE、任务执行上下文和多种长任务 handler。现有取消能力只覆盖 `PENDING` 和 `QUEUED`，`RUNNING` 会返回暂不支持。这个限制在短任务阶段可接受，但对 SSH 远程脚本、环境采集、Git 同步和 SBOM 分析这类长任务不够。

本次设计需要同时解决三类资源：

- Java 内部执行：线程或虚拟线程只能协作式取消，不能安全强杀。
- 本地外部进程：Git、SBOM 分析器等可以通过 `Process` / PID / process tree 终止。
- 远程进程：SSH 命令需要在远端记录 PID/PGID，并通过远程 kill 终止。

同时需要考虑后续多 worker 实例。线程、虚拟线程和本地 `Process` 句柄只存在于创建它们的 JVM 内，不能依赖跨 JVM 共享内存。

## Goals / Non-Goals

**Goals:**

- 支持用户取消 `RUNNING` 任务。
- 取消请求返回后，任务业务状态立即进入 `CANCELLED`，前端可通过任务详情和 SSE 看到终态。
- worker 能定点收到自己持有任务的取消消息，并在本 JVM 内停止线程、虚拟线程、进程或 SSH 会话。
- 本地进程和远程进程都要有可审计的 runtime handle 记录。
- 取消清理失败要可观测、可重试或进入 DLQ，但不得把已经取消的任务回滚为运行中。
- 继续保持 RabbitMQ 不是任务事实来源，PostgreSQL 仍是任务状态事实来源。

**Non-Goals:**

- 不实现跨机器强杀另一个 worker 主机上的本地进程。
- 不引入分布式共享线程池。
- 不保证所有第三方命令都能优雅退出；只能提供 TERM/KILL 和会话关闭兜底。
- 不实现前端取消确认交互。
- 不实现任务暂停、恢复或优先级调度。

## Decisions

### 1. 任务业务状态和资源清理状态分离

取消接口对 `RUNNING` 任务成功校验权限后，立即把 `tasks.status` 更新为 `CANCELLED`，设置 `finished_at`，追加 `task.cancelled` 事件，并投递取消清理消息。实际线程、进程、远程命令的停止结果记录到 runtime handle。

原因：用户取消是业务终态，资源清理是后台补偿动作。如果等待远程 kill 完成再返回，长时间 SSH 卡顿会让取消 API 不可预测。

替代方案是取消接口阻塞等待清理完成。该方案语义更严格，但 API 延迟不可控，且会把 SSH/RabbitMQ/worker 故障暴露到用户取消操作上。

### 2. 每个 worker 使用专属取消队列

worker 启动时生成 `workerInstanceId`，声明自己的取消队列，并绑定：

```text
exchange: rvport.task.cancel
routing key: worker.cancel.<workerInstanceId>
queue: rvport.task.cancel.<workerInstanceId>
```

任务被认领时，worker 把 `taskId -> workerInstanceId -> runtimeHandleId` 写入 PostgreSQL。取消接口根据当前 active runtime handle 的 `workerInstanceId` 定点投递取消消息。

原因：本地线程和本地进程句柄只能由原 JVM 可靠处理。定点投递避免其他 worker 消费到无法处理的取消消息。

替代方案是所有 worker 共享一个取消队列。该方案简单，但取消消息可能被错误 JVM 消费，导致找不到本地 handle。

### 3. 取消消息必须使用 mandatory publish 并处理 unroutable return

RabbitMQ direct exchange 在 routing key 没有匹配队列时，默认会接受 publish 并直接丢弃消息。取消消息不能接受这种静默丢失，因此取消队列客户端必须启用 mandatory publish，并注册 publisher returns callback。

当返回 unroutable 时，后端必须把 runtime handle 更新为 `CANCEL_ROUTE_UNAVAILABLE`、`WORKER_LOST` 或等效状态。远程任务可以转入通用 cleanup repair 继续尝试远程 kill；本地任务不能跨 JVM 获取线程或 `Process` 句柄，只能记录无法确认清理。

worker 专属取消队列的生命周期建议使用以下策略之一：

- `exclusive + auto-delete`：worker 下线后队列立即删除，unroutable 能快速暴露 worker 不存在。
- `auto-delete 或 x-expires 短 TTL`：允许短时间内清理废弃队列，但仍避免长期堆积。

MVP 不要求 worker 重启后继续消费旧 `workerInstanceId` 的取消队列。原因是新 JVM 不持有旧 JVM 的线程和本地进程对象，稳定 worker id 反而可能让系统误以为可以完成本地清理。

### 4. 使用本地 TaskExecutionRegistry 管理运行中句柄

每个 JVM 维护一个内存 registry：

```text
taskId -> RunningTaskHandle
```

`RunningTaskHandle` 包含任务执行 `Future`、取消 token、登记过的本地 process handle、远程 process handle 和执行上下文。取消 listener 收到定点消息后，从 registry 找到 handle 并调用 `cancel()`。

原因：数据库适合记录归属和审计，不适合保存 Java 对象、线程和 `Process` 引用。

### 5. handler 使用协作式取消

任务执行上下文增加取消能力：

- `isCancellationRequested()`
- `throwIfCancellationRequested()`
- `registerRuntimeHandle(...)`
- `registerLocalProcess(...)`
- `registerRemoteProcess(...)`

handler 在长步骤前后、循环内、外部命令等待期间检查取消状态。Java 线程只通过 interrupt 和取消 token 通知，不做不安全强杀。

### 6. 本地进程按进程树清理

本地 `ProcessBuilder` 启动的 Git 和 SBOM 分析器必须登记 `ProcessHandle`。取消时先尝试正常终止，再在 grace period 后强制终止自身和 descendants。

Windows 和 Linux 的进程树行为不同，MVP 以 Java `ProcessHandle.descendants()` 为统一抽象，并在测试中覆盖至少当前开发平台。

### 7. 远程命令使用包装脚本记录 PID/PGID

SSH runtime 执行长命令时不直接裸跑命令，而是通过包装脚本启动命令、记录 remote PID/PGID、stdout/stderr 路径和 exit code。取消时执行：

```text
kill -TERM -<pgid>
sleep <grace>
kill -KILL -<pgid>
```

如果目标系统不支持进程组，降级为按 PID 终止，并记录能力降级。

### 8. 原任务消息确认和取消清理解耦

任务 worker 仍然只在任务处理完成、取消完成进入业务终态或失败状态可靠写回后 ack 原任务消息。取消清理消息有独立 retry 和 DLQ。用户取消导致的 `TaskCancelledException` 不应触发原任务重试。

### 9. worker 崩溃兜底

如果取消时 active handle 指向的 worker 已下线，定点取消队列可能不存在或无人消费。API 仍保留 `CANCELLED` 业务状态，并把 runtime handle 标记为 `WORKER_LOST`、`CANCEL_UNKNOWN` 或等效状态。

远程任务可以由后续 cleanup repair 根据 `environmentId`、remote PID/PGID 尝试清理。本地进程跨主机强杀不在本次范围内。

## Risks / Trade-offs

- [Risk] 任务状态先变为 `CANCELLED`，但底层进程短时间内仍在退出。→ Mitigation：通过 runtime handle 暴露清理状态，并对取消清理失败写入审计日志和 DLQ。
- [Risk] worker 崩溃后专属取消队列不可用。→ Mitigation：runtime handle 持久化 worker 归属，后续 repair 标记 worker lost；远程进程可尝试通用清理。
- [Risk] RabbitMQ direct exchange 对不存在 routing key 的消息默认静默丢弃。→ Mitigation：取消消息必须 mandatory publish，并通过 publisher return 将 runtime handle 标记为路由不可达。
- [Risk] Java 线程无法安全强杀。→ Mitigation：执行上下文提供取消检查，handler 必须在长步骤前后检查。
- [Risk] 远程 PID 被复用导致误杀。→ Mitigation：包装脚本记录 marker、启动时间和工作目录，取消前尽量验证 marker；无法验证时记录风险并保守处理。
- [Risk] Windows/Linux 进程树行为不一致。→ Mitigation：本地进程取消实现抽象化，并为当前平台补测试。

## Migration Plan

1. 通过 Liquibase 新增 runtime handle 表和必要任务取消字段。
2. 增加 RabbitMQ 取消 exchange、专属取消队列声明、mandatory publish、publisher return 和配置。
3. 增加 worker instance 注册、任务运行 registry 和取消 listener。
4. 扩展任务执行上下文和 worker 主流程。
5. 逐步改造 Git、SSH、SBOM 等可取消 runtime。
6. 补齐单元测试、集成测试和 E2E。

回滚时可以保留新增表和字段，关闭取消 listener 后恢复 `RUNNING` 取消返回不支持；但已经进入 `CANCELLED` 的任务不做状态回滚。

## Open Questions

- worker 专属取消队列名称是否需要包含应用实例启动时间，避免同一 host/pid 复用冲突？
- 远程命令包装脚本是否需要长期保存在目标机器，还是每次以内联脚本创建临时目录？
- runtime cleanup 状态是否需要暴露给普通用户，还是只在管理/审计接口中展示？
