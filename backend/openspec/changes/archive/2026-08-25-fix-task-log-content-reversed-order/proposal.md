## Why

当前任务日志内容接口默认使用 `TaskLogTailReader` 从物理日志文件尾部读取最后 N 行，但真实构建日志存在“最新日志位于文件头、较早日志位于文件尾”的倒序存储场景，导致 `offset=0&lines=100` 首屏返回最早日志，和前端查看完成态构建/测试日志时的预期相反。

需要将日志内容分页语义固定为“面向展示顺序”，避免前端必须理解后端日志文件的物理写入方向。

## What Changes

- 调整 `GET /api/tasks/{taskId}/log-content` 的语义：offset 表示按展示顺序跳过的行数，`offset=0` 必须返回最新展示页。
- 支持倒序存储日志：当日志文件头部代表最新内容时，从文件头开始分页，页内保持文件内自然顺序返回。
- 保持现有响应结构、日志类型参数、lines 上限、权限校验和脱敏逻辑不变。
- 补充单元测试和 E2E 覆盖倒序日志场景，防止再次退回到物理文件尾读取语义。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `task-runtime`: 明确完成态日志内容读取的 offset 语义面向展示顺序，并覆盖倒序日志存储。
- `backend-api-design`: 更新 `log-content` API 参数说明，避免将 offset 绑定到物理文件底部。
- `api-e2e-test-suite`: 增加倒序日志 fixture 的端到端验证。

## Impact

- 影响代码：
  - `src/main/java/cn/rvport/backend/task/TaskLogTailReader.java`
  - `src/main/java/cn/rvport/backend/task/TaskLogService.java`
  - 相关日志内容 API 单元测试和 E2E。
- 影响 API：
  - `GET /api/tasks/{taskId}/log-content` 的 offset 语义从“物理文件底部 offset”调整为“展示顺序 offset”。
- 不影响：
  - SSE 实时日志推送。
  - 日志文件下载接口。
  - 日志元数据分页接口。
