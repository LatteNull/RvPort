## Why

当前人工修复后的 latest compare 只能查询复检状态和基础差异项列表，但缺少真正创建复检任务、基于已确认迁移输入生成差异、以及查看单条差异详情的完整 API 契约。代码行号会随修复变化，不能作为 issue 身份判断依据，因此需要补齐稳定匹配模型，保证前端能准确展示“上次确认的问题在本次是否修复、是否仍存在、是否新增或变化”。

## What Changes

- 新增项目级复检任务创建 API，支持显式指定 base/target source revision，也支持 latest 复检。
- 明确复检数据源为绑定源码版本的、已确认的迁移输入记录，而不是源码文本 diff 或未确认的原始扫描结果。
- 补齐 `diff_items` 的摘要字段和详情 API，使前端能分页展示差异列表并查看 old/new 两侧详情。
- 引入 issue identity / matching 模型：行号只用于展示，匹配优先使用 `sourceType + ruleId + relativePath + symbol + normalizedAnchor` 等稳定信息，并记录匹配置信度和原因。
- 明确 `RESOLVED`、`UNCHANGED`、`NEW`、`CHANGED` 的生成规则。
- latest compare API 继续保留为代码比较页入口，但语义明确为复检差异状态，不表示源码文本行级 diff。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `manual-fix-source-update-flow`: 补齐人工修复后复检任务创建、已确认迁移输入差异生成、差异列表/详情查询和 issue 匹配规则。

## Impact

- API：新增 `POST /api/projects/{projectId}/rechecks`、`POST /api/projects/{projectId}/rechecks/latest`、`GET /api/rechecks/{recheckRunId}/diff-items/{diffItemId}`，扩展现有 latest compare 和 diff-items 响应。
- 数据库：扩展 `recheck_runs`、`diff_items` 或相关迁移输入快照字段，用于保存匹配结果、列表摘要、old/new 快照和置信度。
- 后端运行时：新增复检任务 handler，读取 base/target source revision 对应的已确认迁移输入并生成 diff items。
- 权限：所有项目级和 recheck 级接口必须校验当前用户对项目的访问权限。
- 测试：补齐正常流程、异常流程、edge case 单元测试和模块化 E2E 覆盖。
