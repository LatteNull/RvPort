## Context

项目级 SSE 当前通过 `GET /api/projects/{projectId}/task-events` 建立连接，并使用 `Last-Event-ID` 作为 `task_events.id` 游标恢复。该机制适合“同一页面短暂断线后恢复”，但不适合“新浏览器或新会话首次打开项目页”。如果新浏览器传入旧事件 ID 或不具备当前项目最新游标，就可能补发大量历史事件。

数据库中已经出现过历史异常事件：单个失败任务曾在数分钟内写入上万条重复 `task.started/task.progress/task.queued` 事件。即使当前 retry bug 已修复，只要首次连接补发历史事件，前端仍可能看到大量旧错误。

## Goals / Non-Goals

**Goals:**

- 项目 overview 返回当前项目最新任务事件 ID，作为前端首次打开项目页时的 SSE baseline。
- 项目级 SSE 支持 `afterEventId` 查询参数，显式表示“只订阅该游标之后的新事件”。
- 保留 `Last-Event-ID` 作为断线恢复机制。
- 未提交任何游标的首次连接默认从当前项目最新事件 ID 之后开始，不补发历史事件。
- SSE 补发和实时推送始终按项目隔离。

**Non-Goals:**

- 不修改任务级日志 SSE 的首次连接语义；日志详情页仍然需要补发历史日志。
- 不清理历史异常 `task_events` 数据。
- 不引入每个浏览器或每个用户的服务端 SSE cursor 存储。
- 不修改 frontend，本 change 只提供后端能力和契约。

## Decisions

### 1. `overview.latestTaskEventId` 作为项目 baseline

`GET /api/projects/{projectId}/overview` 增加：

```json
{
  "latestTaskEventId": 37150
}
```

该值来自当前项目下 `task_events.id` 的最大值；没有事件时返回 `0` 或 `null`，实现应选择一种稳定表达。推荐返回 `0`，便于前端直接作为 `afterEventId` 使用。

### 2. `afterEventId` 表达首次订阅 baseline

项目 SSE API 增加：

```text
GET /api/projects/{projectId}/task-events?afterEventId=37150
```

语义是只补发同一项目内 `id > afterEventId` 的事件，然后保持连接推送新事件。它不代表浏览器自动恢复，而是业务层 baseline。

### 3. 游标优先级

解析顺序：

```text
if afterEventId is present:
    cursor = afterEventId
else if Last-Event-ID is present:
    cursor = Last-Event-ID
else:
    cursor = latestTaskEventId(projectId)
```

这样新浏览器首次打开项目页时不会拉历史事件；同一 EventSource 断线时，浏览器自动带上的 `Last-Event-ID` 仍能恢复未消费事件；前端显式传 `afterEventId` 时，可以覆盖自动 header。

### 4. 项目隔离继续由查询条件保证

所有补发查询继续使用：

```sql
WHERE project_id = :projectId
  AND id > :cursor
ORDER BY id ASC
LIMIT :limit
```

实时推送仍按 `projectId` 管理 emitter 集合。多个浏览器同时打开不同项目时，每个项目只接收自己的任务事件。

### 5. Retry 不引入独立任务状态

Retry 属于任务执行过程，不新增 `RETRYING` 状态。重试期间任务可以处于 `QUEUED` 或 `RUNNING`，并通过 `retry_count`、message 和任务事件表达重试信息。

## Risks / Trade-offs

- [Risk] 前端仍可能只用 `Last-Event-ID` 且传入旧值。→ Mitigation: 后端提供无游标默认 baseline；前端接入时应优先使用 overview 返回的 `latestTaskEventId` 作为 `afterEventId`。
- [Risk] `afterEventId` 与 `Last-Event-ID` 同时存在且不一致。→ Mitigation: 明确 `afterEventId` 优先，避免浏览器自动恢复 header 干扰业务 baseline。
- [Risk] 首次连接默认不补发历史事件可能隐藏页面打开前刚完成的任务。→ Mitigation: 项目 overview、任务列表和任务详情仍作为当前事实来源；SSE 只承载实时增量。
- [Risk] 历史异常事件仍存在数据库中。→ Mitigation: 不在本 change 清理生产数据；如需清理，单独通过运维脚本或测试支持能力处理。

## Migration Plan

1. 增加 `TaskEventRepository.findLatestId(projectId)`。
2. 在项目 overview 聚合中返回 `latestTaskEventId`。
3. 更新 `TaskSseController` 支持 `afterEventId` 并调整游标优先级。
4. 补充非法游标校验，`afterEventId` 和 `Last-Event-ID` 均需非负数字。
5. 补充单元测试和 E2E 模块测试。

## Open Questions

- `latestTaskEventId` 没有事件时返回 `0` 还是 `null`。建议返回 `0`，减少前端分支。
