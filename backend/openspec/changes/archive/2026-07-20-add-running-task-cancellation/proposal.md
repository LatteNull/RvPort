## Why

当前任务运行时只能取消 `PENDING` 和 `QUEUED` 任务，`RUNNING` 任务会返回暂不支持强制中止。后续环境采集、远程脚本、源码同步和 SBOM 分析都可能长时间运行，用户需要能主动取消运行中任务，并让 worker 尽快停止本地进程或远程进程。

## What Changes

- 支持 `POST /api/tasks/{taskId}/cancel` 取消 `RUNNING` 任务。
- 新增任务运行时句柄记录，用于保存任务所属 `workerInstanceId`、本地进程 PID、远程 PID/PGID、取消清理状态和错误摘要。
- 新增 worker 专属取消队列设计：每个 worker 启动时声明自己的取消队列，取消消息按 `workerInstanceId` 定点投递到持有任务执行上下文的 JVM。
- 取消消息投递必须启用 RabbitMQ mandatory publish，并处理 unroutable publisher return；当目标 worker 队列不存在时，必须显式写回 runtime handle 清理异常状态。
- 新增本地任务执行 registry，用于在单 JVM 内管理运行中的线程、虚拟线程、进程和 SSH 会话。
- 扩展任务执行上下文，使 handler 能检查取消状态并登记可取消资源。
- 本地进程、远程 SSH 命令、Git 同步、SBOM 分析器调用等运行时需要接入统一取消能力。
- 取消接口必须继续执行项目访问守卫，并通过任务事件/SSE 推送取消终态。
- 取消清理失败不得把用户已取消的任务回滚为运行中或失败，但必须记录清理失败状态以便审计。

## Capabilities

### New Capabilities

- `running-task-cancellation`: 定义运行中任务取消、worker 定点取消队列、运行时句柄和取消清理状态。

### Modified Capabilities

- `task-runtime`: 将运行中任务取消从“不支持”改为“可取消并异步清理运行资源”。
- `backend-api-design`: 更新任务取消 API 的运行中任务行为和响应约定。
- `backend-infrastructure`: 增加 RabbitMQ 取消 exchange、worker 专属取消队列和 DLQ 的基础设施约定。
- `api-e2e-test-suite`: 增加运行中任务取消的正常流程、异常流程和 edge case E2E 覆盖。

## Impact

- 数据库：新增任务运行时句柄表，必要时扩展 `tasks` 取消时间、取消人和取消原因字段。
- 后端 API：更新 `POST /api/tasks/{taskId}/cancel` 对 `RUNNING` 任务的行为。
- Worker：引入 `workerInstanceId`、本地执行 registry、取消消息 listener、定点取消队列声明和取消清理状态写回。
- RabbitMQ：新增取消 exchange、每 worker 取消队列、取消 DLQ、mandatory publish 和 publisher return 处理。
- Runtime adapters：Git 本地进程、SBOM 分析进程、SSH 远程命令执行需要登记可取消句柄。
- 测试：补充单元测试、轻量集成测试和 E2E 测试，覆盖正常流程、异常流程和 edge case。
