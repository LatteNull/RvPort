## 1. 增量日志查询模型

- [x] 1.1 为 `TaskLogEventRepository` 增加按 `taskId + afterEventId` 升序限量查询、任务最新事件 ID 和批量任务最新事件 ID 查询能力。
- [x] 1.2 检查 `task_log_events (task_id, id)` 现有索引的查询计划；仅在现有索引不能支撑游标读取和批量最大 ID 查询时增加 Liquibase 变更，并同步生成 jOOQ 元数据。
- [x] 1.3 定义增量日志请求与响应 DTO，包含 `fromEventId`、`latestEventId`、`hasMore` 以及 merged/stdout/stderr 聚合内容和事件计数。
- [x] 1.4 实现增量聚合服务，按事件 ID 顺序构造三类内容，并同时执行事件条数和 UTF-8 响应字节数上限。
- [x] 1.5 处理无日志、游标超过最新值、事件内容刚好达到边界和全局 ID 中夹有其他任务事件等 edge case。

## 2. 日志增量读取 API

- [x] 2.1 新增 `GET /api/tasks/{taskId}/log-increments` controller，并复用 `ProjectAccessService.requireTaskAccess` 在读取前校验权限。
- [x] 2.2 实现 `afterEventId` 和 `limit` 默认值、范围校验及稳定错误码，确保响应不暴露日志文件路径或其他任务信息。
- [x] 2.3 保持 `GET /api/tasks/{taskId}/log-content` 的请求、响应及完成态历史分页行为不变。

## 3. 任务日志通知 SSE

- [x] 3.1 新增独立日志通知 broker，按 taskId 管理 emitter 集合和任务级观察状态，并在 completion、timeout、error 时清理连接。
- [x] 3.2 实现 5 秒固定周期检查，只处理存在本地订阅的任务，并按 taskId 去重、批量读取任务状态与最新日志事件 ID。
- [x] 3.3 实现 `task.log.updated`、`task.log.completed` 和 heartbeat 事件，确保通知 payload 不携带日志正文且 SSE 通知不被当作消费确认。
- [x] 3.4 新增 `GET /api/tasks/{taskId}/log-notifications`，在创建 emitter 前完成任务权限和游标校验，并在注册后立即读取当前快照。
- [x] 3.5 对新增日志与终态同时发生的情况固定按 updated、completed、关闭连接的顺序处理；已终态任务连接时立即发送 completed 并关闭。
- [x] 3.6 确保 `QUEUED` 重试不是终态，并确保多浏览器连接共享任务查询结果但分别维护和清理 emitter。

## 4. 兼容与迁移

- [x] 4.1 保留现有 `/api/tasks/{taskId}/log-events` 行为，在 API 文档和代码元数据中标记为废弃。
- [x] 4.2 确认新通知 SSE 的正确性不依赖 Worker 本地 broker 或 Redis 日志广播，并避免新旧 broker 之间产生重复通知。
- [x] 4.3 补充前端接入契约：连接或重连后先拉增量、收到 updated 后拉到 `hasMore=false`、收到 completed 后补拉到终态游标。

## 5. 单元与集成测试

- [x] 5.1 增加增量仓储与聚合服务正常流程测试，验证事件顺序、三类内容、游标推进和分页续读。
- [x] 5.2 增加异常流程测试，覆盖非法游标、非法 limit、越权访问、响应上限和仓储读取失败。
- [x] 5.3 增加 edge case 测试，覆盖空日志、终态空日志、跨任务交错 ID、最后一批日志与终态同周期、重试状态、多连接和 emitter 清理。
- [x] 5.4 增加轮询批量查询测试，验证同一任务多个连接不会按连接数重复查询，并验证无订阅任务时不查询数据库。
- [x] 5.5 运行后端完整 Maven 测试，确认旧 `/log-events` 与 `/log-content` 回归测试继续通过。

## 6. API E2E 与文档

- [x] 6.1 扩展 test-support fixture，使 E2E 能创建运行中/终态任务、追加交错 stdout/stderr 日志并触发轮询，而不依赖长时间真实任务。
- [x] 6.2 扩展 task-sse E2E 模块，验证通知后按游标增量读取、最终日志收尾、空日志终态和 SSE 正常关闭。
- [x] 6.3 增加非法参数、普通用户越权、跨任务隔离、多连接和响应分页上限的 E2E 场景，并在结束后清理所有 fixture 数据。
- [x] 6.4 在容器化 API/Worker 部署下运行相关 E2E，确认通知与终态不依赖进程内共享内存。
- [x] 6.5 更新 `docs/API_DESIGN.md` 和 E2E 覆盖清单，记录新旧接口职责、事件示例、增量响应示例及前端恢复流程。
