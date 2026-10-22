## Why

当前项目级 SSE 事件只在产生事件的进程内推送。部署拆分为 `backend` API 进程和 `backend-worker` 进程后，浏览器 SSE 连接只存在于 API 进程，worker 产生的 `task.queued`、`task.started`、`task.progress`、`task.log`、终态事件和 `project.context.changed` 虽然已经正确落库，但无法实时推送到浏览器。

这个问题会导致前端在长任务执行期间只能收到 API 进程产生的 `task.created`，页面状态无法实时刷新；heartbeat 正常会进一步掩盖该问题，使用户误以为任务停滞。

## What Changes

- 增加基于 Redis 的跨进程 SSE 事件广播机制，使 worker 进程落库后的任务事件可以通知 API 进程推送给浏览器。
- 项目级任务事件广播只传递最小引用信息，API 进程收到后从数据库重读事件并通过本进程 `TaskSseBroker` 推送。
- 任务级日志 SSE 使用同样的跨进程广播思路，解决 worker 产生的实时日志无法到达 API 进程 emitter 的问题。
- 保持数据库 `task_events` 和 `task_log_events` 作为事实来源，Redis 广播只作为实时通知通道。
- 保持当前 SSE baseline、`afterEventId`、`Last-Event-ID` 和项目访问控制语义不变。
- 补充 API/worker 分进程部署下的 E2E 验证，覆盖 Git 同步或 test-support fixture 触发的跨进程事件推送。

## Capabilities

### New Capabilities

### Modified Capabilities

- `task-runtime`: 项目级 SSE 和任务级日志 SSE 必须支持 API/worker 分进程部署下的跨进程实时事件广播。
- `api-e2e-test-suite`: E2E 必须覆盖 API 进程持有 SSE 连接、worker 进程产生事件时浏览器能实时收到事件。

## Impact

- 后端任务事件发布链路：`TaskEventService`、`TaskSseBroker` 及新增 Redis 广播发布/订阅组件。
- 后端任务日志事件发布链路：`TaskLogEventService`、`TaskLogSseBroker` 及新增 Redis 广播发布/订阅组件。
- Redis 配置：复用现有 Redis 基础设施，新增专用 channel、payload DTO 和错误处理策略。
- E2E：新增或扩展 SSE case，使测试运行在 `backend` 与 `backend-worker` 分离的容器部署下。
- 运维：Redis 短时不可用时不影响任务状态落库，但实时 SSE 可能降级为前端重读或重连恢复。
