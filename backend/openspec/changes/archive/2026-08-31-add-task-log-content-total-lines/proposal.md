## 背景

`GET /api/tasks/{taskId}/log-content` 当前只返回日志分页内容，没有返回每类日志的总行数。前端需要这个总行数来计算行号范围、滚动位置，以及判断是否还有更多历史日志，而不是反复探测 offset。

由于任务运行中日志仍会持续增长，总行数不能只在任务完成后静态计算，需要在日志写入或落库时同步维护。

## 变更内容

- 在 `log-content` 响应中为 `merged`、`stdout`、`stderr` 每类日志增加 `totalLines`。
- 在任务日志内容追加或落库时维护总行数，使运行中任务也能返回接近实时的行数快照。
- 保持现有 offset 语义不变：`offset=0` 仍表示该日志类型的最新展示页，更大的 offset 继续向更旧日志翻页。
- 保留单类日志和多类日志同时请求的能力，并支持各自独立的 offset 和 lines。
- 补充正常流程、异常流程和 edge case 的测试覆盖。

## 能力范围

### 新增能力

- 无。

### 修改能力

- `task-runtime`：扩展任务日志内容 API，要求每类日志返回总行数。
- `backend-api-design`：补充 `GET /api/tasks/{taskId}/log-content` 的响应契约。
- `api-e2e-test-suite`：补充日志内容总行数相关的 E2E 覆盖。

## 影响范围

- 后端任务日志写入和读取逻辑。
- 任务日志数据库 schema 或等效持久化元数据。
- `GET /api/tasks/{taskId}/log-content` 响应 DTO。
- 任务日志内容分页相关的单元测试和 E2E 测试。
