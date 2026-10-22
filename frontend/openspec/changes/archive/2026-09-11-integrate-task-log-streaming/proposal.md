## Why

当前构建、自动化测试和环境脚本日志只通过完成态 `log-content` 接口读取，运行期间依赖手动刷新，无法稳定消费持续增长的日志。后端已经提供轻量日志通知 SSE 与稳定游标增量接口，前端需要接入该链路，并保留完成态日志的历史分页能力。

## What Changes

- 为运行中任务接入 `GET /api/tasks/{taskId}/log-notifications`，使用 SSE 接收日志更新和任务终态通知，但不把通知当作正文已消费确认。
- 接入 `GET /api/tasks/{taskId}/log-increments`，按最后一次成功响应的事件游标串行补拉 `merged`、`stdout`、`stderr` 日志，支持断线恢复、失败重试和 `hasMore` 连续读取。
- 将共享任务日志面板扩展为运行态增量模式与完成态历史模式：运行时实时追加，终态补拉完成后切换至 `log-content` 权威日志，并继续支持向上加载和下载。
- 统一普通构建、x86 构建、自动化测试、结果对比和环境脚本执行记录的日志读取行为，减少页面各自维护的刷新与分页逻辑。
- 为长时间运行任务设置前端展示缓存边界，并在省略早期实时内容时提供明确提示；最终完整日志仍通过完成态接口访问。
- 补充 API 契约、流式状态机、重连、增量合并、终态收尾、错误恢复和资源清理测试。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `project-pipeline-workbench`: 将构建、测试和环境脚本任务的日志展示扩展为运行态实时增量读取、断线恢复与终态历史分页统一体验。

## Impact

- 前端 API 与领域类型：任务日志通知事件、增量日志请求和响应模型。
- 页面共享逻辑：新增任务日志流 Hook，调整日志 query key 和缓存生命周期。
- 页面组件：`TaskLogPanel` 以及环境脚本日志视图；普通构建、x86 构建、自动化测试和结果对比调用方。
- 后端：不修改接口，只消费现有 `/log-notifications`、`/log-increments`、`/log-content` 和受控下载契约。
- 依赖：不新增运行时依赖，复用原生 `EventSource`、TanStack Query 和现有 Monaco 日志查看器。
