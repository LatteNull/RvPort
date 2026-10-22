## Why

评估报告运行时已经支持在没有确认迁移输入时生成成功的全零报告，但项目级阶段 readiness 仍将该情况判定为缺失前置条件，导致前端无法发起本应合法的报告任务。同时，完成态日志文件实际按时间正序追加，现有日志分页却按“最新内容位于文件头”读取，导致自动化测试等任务的日志展示顺序颠倒。

## What Changes

- 调整评估报告阶段 readiness：存在有效源码版本时，即使确认迁移输入数量为 0，`INCLUDED_FINDINGS` 前置条件也返回 `SATISFIED`，并保留真实的输入数量统计。
- 保留“缺少有效源码版本”作为报告生成阻塞条件，不放宽项目、源码版本或权限校验。
- 修正 `GET /api/tasks/{taskId}/log-content` 的完成态日志分页语义：`offset=0` 从物理文件尾部读取最新一页，offset 增大时向更早内容翻页；每一页内部按日志产生时间正序返回。
- 明确前端历史日志拼接只调整分页先后，不再反转单页中的日志行；运行中的 SSE 通知与 `/log-increments` 增量读取保持现有正序契约。
- 修正文档中“最新日志位于文件头”和“没有确认输入会阻塞报告”的过期描述。
- 补充正常流程、异常流程和边界条件单元测试，并执行受影响模块及项目整体覆盖率检查，行覆盖率和可用时的分支覆盖率均达到至少 90%。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `migration-report-runtime`: 统一报告 readiness 与空输入报告运行时语义，零确认输入不再阻塞报告生成。
- `task-runtime`: 修正完成态任务日志的尾部分页和页内时间顺序契约。
- `backend-api-design`: 修正报告 readiness 与 `log-content` API 的外部行为说明，消除既有规格冲突。
- `api-e2e-test-suite`: 修正报告空输入和完成态日志顺序的 E2E 验收契约。

## Impact

- 后端报告阶段 readiness 计算和报告创建前置条件校验。
- 后端日志文件分页读取器、日志内容服务及其单元测试。
- 前端完成态日志分页拼接契约；本 change 只修改后端与后端文档，不影响请求和响应字段。
- `migration-report-runtime`、`task-runtime`、`backend-api-design` 主规格及相关 API 文档。
- 不涉及数据库 schema、消息队列、SSE 协议、任务日志文件格式或已有 API 路径变更。
