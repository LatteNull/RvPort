## Why

当前项目级 SSE 仅使用 `Last-Event-ID` 作为恢复游标，新浏览器或旧游标重连时可能补发大量历史任务事件，尤其会放大历史异常重试事件。项目工作台需要区分“首次打开只看当前之后的新事件”和“同一页面断线后恢复未消费事件”。

## What Changes

- 项目 overview API 返回当前项目最新 `task_events.id`，作为前端首次建立项目 SSE 的 baseline 游标。
- 项目级 SSE API 支持显式 `afterEventId` 查询参数，用于从某个项目当前事件 ID 之后开始订阅。
- SSE 游标解析优先级调整为：`afterEventId` 优先，其次 `Last-Event-ID`，两者都不存在时以后端当前项目最新事件 ID 作为默认 baseline。
- `Last-Event-ID` 继续用于同一页面断线恢复；`afterEventId` 用于首次打开项目页或更换浏览器时避免补发历史事件。
- 所有补发和实时推送继续严格按 `projectId` 隔离，打开多个浏览器或多个项目页面时，不得跨项目推送或补发事件。
- 历史异常事件不作为生产 SSE 首次连接默认补发内容；需要审计历史任务时仍通过任务列表、任务详情和日志 API 查询。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `task-runtime`: 项目级 SSE 增加 baseline 游标语义、`afterEventId` 参数和默认不补发历史事件的首次连接行为。
- `backend-api-design`: 项目 overview 响应和项目级 SSE API 文档增加最新事件 ID、游标优先级和项目隔离要求。
- `backend-database-design`: 明确项目级最新事件 ID 查询路径和 SSE 恢复索引使用方式。

## Impact

- API：`GET /api/projects/{projectId}/overview` 增加 `latestTaskEventId`；`GET /api/projects/{projectId}/task-events` 增加 `afterEventId` 查询参数。
- 后端任务事件查询：增加按项目查询最新事件 ID 的 repository 能力，并复用现有 `task_events(project_id, id)` 索引。
- SSE controller：调整游标解析和默认 baseline 行为，保持项目访问守卫在创建 emitter 和补发事件之前执行。
- 测试：补充首次连接、断线恢复、非法游标、跨项目隔离、多个项目并行订阅和历史异常事件不默认补发的覆盖。
