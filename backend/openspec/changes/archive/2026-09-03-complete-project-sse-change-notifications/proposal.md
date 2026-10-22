## Why

当前项目级 SSE 已经能推送任务生命周期事件，但事件内容不足以让前端可靠判断“哪个节点、哪个资源发生了变化”。同时，源码版本、运行环境配置这类项目上下文变化不是任务状态本身，当前没有统一事件通知，导致前端只能依赖轮询或隐式刷新。

本变更补齐项目事件通知能力：SSE 只负责发送轻量变更通知，前端收到事件后重新读取 overview、列表或详情接口获取权威数据，不做完整历史补发。

## What Changes

- 扩展任务事件的公开响应，增加节点与资源元数据，例如 `stageId`、`resourceType`、`resourceId`、`environmentRole`、`mode`。
- 增加项目上下文变更事件，用于通知 active source、运行环境选择、环境配置版本等项目级上下文变化。
- 保持 SSE 按 `projectId` 隔离，禁止不同项目之间串流事件。
- 明确 SSE 不承载完整业务数据，只承载变更提示、任务状态、进度、摘要消息和可用于前端局部刷新的元数据。
- 保留 `overview.latestTaskEventId` 作为首次连接 baseline；首次打开页面或更换浏览器时不补发旧事件，前端通过 overview 获取当前状态。
- 补齐单元测试和 E2E，覆盖生命周期事件、上下文变更事件、项目隔离和 cursor 行为。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `task-runtime`: 扩展项目级 SSE 事件契约，补齐节点状态变更通知和项目上下文变更通知。

## Impact

- 数据库：需要为任务事件或项目事件增加节点/资源元数据字段，并支持非任务绑定的项目上下文事件。
- 后端 API：影响 `GET /api/projects/{projectId}/task-events` 响应结构，但保持 SSE endpoint 不变。
- 业务服务：源码激活、源码导入完成、运行环境选择更新、环境配置版本变更等路径需要发布上下文变更事件。
- 前端协作：前端收到 SSE 后应重读 overview/readiness/list/detail，不应依赖 SSE 历史补发恢复完整页面状态。
- 测试：更新任务 SSE 单元测试和 E2E 模块，确保不同项目事件隔离且事件元数据完整。
