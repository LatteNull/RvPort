## Why

当前远程脚本 API 已允许创建 `CUSTOM_BASH` 任务，但 worker 不会执行脚本正文，脚本执行页也缺少任务级日志流和可恢复的执行记录视图。需要补齐用户确认执行后保持页面、实时输出日志、关闭页面后通过执行记录恢复查看的完整链路。

## What Changes

- 支持 `CUSTOM_BASH` 脚本从前端提交、后端安全保存、worker 远程执行。
- 新增脚本执行记录查询能力，执行记录由任务和工具运行记录驱动，前端状态仅展示进行中、已完成、错误。
- 新增任务级日志 SSE，连接时先补发已有日志事件，再持续推送后续 stdout/stderr 和终态事件。
- 新增可恢复的日志事件持久化模型，供任务级 SSE 使用 `Last-Event-ID` 断线恢复。
- 保留项目级 SSE 作为项目工作台任务状态通道，不用它承载密集脚本日志流。
- 补充单元测试和 E2E，覆盖正常流程、异常流程和 edge case。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `project-source-environment`: 补齐 `CUSTOM_BASH` 远程脚本执行、脚本执行记录、脚本正文安全处理和执行结果查询语义。
- `task-runtime`: 增加任务级日志 SSE、日志事件持久化、历史日志补发和日志流恢复语义。
- `backend-api-design`: 增加脚本执行记录 API 和任务级日志 SSE API。
- `backend-database-design`: 增加日志事件表和脚本正文安全存储字段/表约束。
- `api-e2e-test-suite`: 增加 CUSTOM_BASH 执行、日志流、断线恢复、执行记录恢复和权限边界的 E2E 覆盖。

## Impact

- 后端 API：环境脚本创建接口、脚本执行记录查询接口、任务级日志 SSE 接口。
- 数据库：新增或扩展脚本正文安全存储、日志事件持久化和查询索引。
- Worker/SSH runtime：执行 `CUSTOM_BASH`，写入执行记录、日志文件、日志事件和任务事件。
- 前端交互：脚本执行页通过任务级日志 SSE 展示实时日志，执行记录页可恢复历史和继续追踪运行中任务。
- 测试：补充 Java 单元测试、轻量集成测试和 E2E 模块测试。
