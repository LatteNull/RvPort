## 1. 任务事件查询能力

- [x] 1.1 在 `TaskEventRepository` 中增加按 `projectId` 查询最新 `task_events.id` 的方法。
- [x] 1.2 确认最新事件查询和补发查询都使用 `project_id, id` 索引路径。
- [x] 1.3 为无事件项目定义稳定返回值 `0`。

## 2. Project overview baseline

- [x] 2.1 更新项目 overview DTO，增加 `latestTaskEventId`。
- [x] 2.2 在 `ProjectService.overview` 中聚合当前项目最新任务事件 ID。
- [x] 2.3 确保 overview 仍在项目访问守卫后返回，越权时不暴露事件游标。

## 3. 项目级 SSE 游标语义

- [x] 3.1 更新 `TaskSseController`，支持 `afterEventId` 查询参数。
- [x] 3.2 实现游标优先级：`afterEventId` 优先，其次 `Last-Event-ID`，否则使用当前项目最新事件 ID。
- [x] 3.3 对 `afterEventId` 和被使用的 `Last-Event-ID` 执行非负数字校验。
- [x] 3.4 保持项目访问守卫在创建 emitter 和补发事件之前执行。
- [x] 3.5 确认实时 publish 仍按 `projectId` emitter 集合隔离。

## 4. Retry 表达检查

- [x] 4.1 确认任务状态枚举不新增 `RETRYING`。
- [x] 4.2 确认重试事件通过 `QUEUED`/`RUNNING`、`retry_count` 和 message 表达。
- [x] 4.3 针对 retry attempt 递增补充回归测试，防止再次出现无限重试事件。

## 5. API 文档与 E2E

- [x] 5.1 更新 `backend/docs/API_DESIGN.md`，说明 `latestTaskEventId`、`afterEventId` 和 `Last-Event-ID` 的语义。
- [x] 5.2 更新 E2E 文档和模块，加入项目级 SSE baseline 用例。
- [x] 5.3 补充首次连接无游标不补发历史事件的 E2E。
- [x] 5.4 补充 `afterEventId` 补发、`Last-Event-ID` 断线恢复和两者同时存在时优先级的 E2E。
- [x] 5.5 补充跨项目隔离 E2E，确认项目 A 不接收项目 B 事件。

## 6. 测试与验证

- [x] 6.1 补充正常流程单元测试：overview 返回最新事件 ID，SSE 从 baseline 后补发。
- [x] 6.2 补充异常流程测试：非法 `afterEventId` 和非法 `Last-Event-ID` 拒绝且不创建 emitter。
- [x] 6.3 补充 edge case 测试：无事件项目、多项目事件 ID 空洞、同时提交两个游标、旧历史异常事件存在。
- [x] 6.4 运行 `mvn test`。
- [x] 6.5 启动后端后运行 task/SSE 相关 E2E 模块，确认行为符合设计。
