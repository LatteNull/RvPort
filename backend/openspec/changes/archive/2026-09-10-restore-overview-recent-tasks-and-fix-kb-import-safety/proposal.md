## Why

项目 overview 在近期重构后移除了前端仍然依赖的 `recentTasks`，导致项目首页无法直接展示最近任务。与此同时，KB Scanner 已成功生成结果后，归档候选安全校验会把合法的 `paths` 字段误判为敏感内容，且当前对 JSON 制品执行无结构的文本路径替换，存在破坏源码证据乃至 JSON 有效性的风险。

## What Changes

- 在项目 overview 响应中恢复 `recentTasks`，返回当前项目按创建时间倒序排列的最近 5 条任务，同时保留现有 `currentContext`、`workflow` 和 `latestTaskEventId`。
- 调整归档候选安全校验：允许 `path`、`paths` 等业务字段名和安全相对路径值，继续拒绝密钥字段、绝对服务器路径和目录穿越内容。
- 将 KB JSON 结果的路径脱敏改为结构化处理，保证脱敏后仍是合法 JSON，并保留 `#include "../..."` 等源码文本的原始语义。
- 明确 KB 扫描成功与归档候选登记的状态边界：归档登记异常不得将已经成功完成并导入的 Scanner 结果误报为“KB 扫描失败”，同时记录可诊断的安全日志。
- 补充 overview、归档安全校验和 KB 导入链路的正常流程、异常流程及 edge case 测试。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `backend-api-design`: 恢复项目 overview 的最近任务列表响应契约。
- `kb-scan-runtime`: 修正 KB 结果结构化脱敏、源码证据保真以及扫描成功后的归档登记失败语义。
- `project-archive-runtime`: 收敛归档候选敏感字段和路径值校验规则，允许合法的路径摘要结构。

## Impact

- 影响项目 overview DTO、项目服务聚合查询及相关 API 文档和测试。
- 影响归档候选安全校验、KB 扫描结果脱敏与归档登记流程。
- 不修改 KB Scanner schema v2，不修改数据库 schema，不兼容或修复既有失败扫描制品；既有失败任务可在修复部署后重新运行。
