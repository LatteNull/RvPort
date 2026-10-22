## Why

构建验证和自动化测试完成后，前端需要快速查看完整日志的末尾内容并按需向上翻页。当前日志 API 返回的是多条日志元数据或片段，适合 SSE 动态展示，但用于完成态日志查看会导致前端大量请求、拼接和渲染开销。

## What Changes

- 新增任务日志内容读取能力，按 `merged`、`stdout`、`stderr` 三类日志返回文本内容。
- 日志内容读取默认返回每类最后 100 行，并支持从日志底部向上按 offset 分段读取。
- 同一接口支持只请求单个日志类型，也支持一次请求多个日志类型且每种类型使用不同 offset 和 lines。
- 构建验证详情补齐 merged log 引用，使构建和测试日志查看能力一致。
- 保留现有日志元数据列表、日志下载和任务级日志 SSE，不把完成态日志查看和运行中 SSE 粒度混在一起。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `task-runtime`: 新增任务日志内容读取接口，支持按类型、offset、行数读取日志正文。
- `build-validation-runtime`: 构建验证运行结果需要保存并返回 merged log 引用。
- `automated-test-runtime`: 自动化测试日志查看需要明确使用任务日志内容读取接口展示 merged/stdout/stderr。
- `backend-api-design`: 补充日志内容读取 API 的参数、响应和权限边界。
- `api-e2e-test-suite`: 补充构建/测试日志内容读取的 E2E 覆盖。

## Impact

- 后端 API：新增或扩展 `GET /api/tasks/{taskId}/log-content`。
- 数据库：构建运行可能需要新增 `combined_log_id` 或等效字段，测试运行已具备 `combined_log_id`。
- 日志服务：需要支持受控日志文件按倒序 offset 读取最后 N 行。
- 构建验证和自动化测试响应：需要稳定暴露 `mergedLogId`、`stdoutLogId`、`stderrLogId`。
- E2E：需要验证单类日志、多类日志、不同 offset、权限和边界参数。
