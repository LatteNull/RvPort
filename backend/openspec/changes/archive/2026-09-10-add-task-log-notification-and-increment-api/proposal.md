## Why

现有任务级日志 SSE 直接传输并补发日志正文，既增加长连接的数据压力，也要求前端逐事件拼接内容；现有 `log-content` 又面向完成态倒序翻页，其 offset 在运行中日志持续增长时不能作为稳定的增量游标。需要将“日志变化通知”和“日志正文读取”解耦，为运行中日志提供轻量、可恢复且不会遗漏终态前最后一批内容的通用链路。

## What Changes

- 新增任务级日志通知 SSE：按 `taskId` 建立连接，只发送“日志有更新”、heartbeat 和“任务已结束”事件，不在 SSE 中携带日志正文。
- API 进程按固定 5 秒周期检查存在本地订阅的任务，以数据库中的任务状态和最新 `task_log_events.id` 为事实来源；同一任务的多个 SSE 连接共享一次检查结果。
- 新增任务日志增量读取 API，使用任务内稳定的 `task_log_events.id` 作为前向游标，一次聚合返回 `merged`、`stdout`、`stderr` 的新增内容。
- 增量读取支持条数和响应体大小上限、`hasMore` 续读，并确保游标只读取当前任务的数据。
- 日志通知 SSE 接受前端已读取的日志事件游标；连接时若存在更新立即通知，断线重连后不依赖 SSE 历史补发恢复日志。
- 任务进入 `SUCCEEDED`、`FAILED`、`CANCELLED` 或 `TIMEOUT` 时，先通知尚未读取的最后一批日志，再发送携带最新日志游标的终态事件并关闭连接；连接已终态任务时直接发送终态事件。
- 保留 `GET /api/tasks/{taskId}/log-content` 作为完成态日志历史分页接口，不修改其现有契约。
- 现有直接传输日志正文的 `GET /api/tasks/{taskId}/log-events` 标记为废弃，避免新旧语义混用；本 change 不立即删除旧接口。
- 补充正常流程、异常流程和 edge case 的单元测试及 API E2E 覆盖。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `task-runtime`: 增加任务日志变化通知、稳定游标增量读取、终态收尾与任务级订阅轮询要求，并废弃直接通过 SSE 传输正文的旧模式。
- `backend-api-design`: 定义任务日志通知 SSE 和日志增量读取 API 的请求、响应、游标、权限及终态契约。
- `api-e2e-test-suite`: 增加任务日志通知与增量拉取的正常、异常和 edge case E2E 场景。

## Impact

- API：新增任务日志通知 SSE 与日志增量读取接口；旧 `/api/tasks/{taskId}/log-events` 保留但废弃；现有 `/api/tasks/{taskId}/log-content` 不变。
- 后端：涉及任务访问守卫、任务与日志事件查询、SSE emitter 管理、定时检查和响应 DTO。
- 数据：复用 `tasks`、`task_log_events` 及现有 `(task_id, id)` 索引，不引入新的日志正文存储。
- 部署：通知正确性以共享数据库为基础，不要求 Worker 将终态直接推送到 API 进程；项目级 SSE 的 Redis 跨进程机制保持不变。
- 测试：更新任务日志 SSE 单元测试，并扩展 task-sse API E2E 模块。
