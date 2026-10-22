## Why

当前后端已经支持 KB 扫描、SBOM 分析和按源码版本隔离的迁移输入合并，但还缺少把人工确认后的迁移输入生成迁移评估报告的闭环能力。前端报告页、归档流程和后续复检对比都需要一个可追溯、可下载、不可变的报告结果。

## What Changes

- 新增迁移评估报告运行时能力：基于指定源码版本下 `CONFIRMED` 的迁移输入生成报告。
- 新增报告生成任务类型，沿用现有 task/worker/SSE 机制异步执行。
- 新增报告 API：创建评估报告、查询报告列表、查询最新报告、查询报告详情、查询报告输入快照、按 HTML/JSON 下载报告。
- 补齐 `reports` 与源码版本的显式绑定，保证同项目多源码版本报告可追溯。
- 报告生成时写入 `report_inputs`，保存迁移输入引用和生成时快照，避免后续迁移输入变更影响历史报告。
- 报告只消费 `status=CONFIRMED` 的迁移输入；没有确认输入时返回明确业务错误，不生成空报告。
- 增加单元测试与 E2E 测试，覆盖正常流程、异常流程和 edge case。

## Capabilities

### New Capabilities

- `migration-report-runtime`: 迁移评估报告的生成、快照、下载和运行时行为。

### Modified Capabilities

- `backend-api-design`: 增加报告生成、列表、详情、输入快照和下载接口的契约。
- `backend-database-design`: 补充报告与源码版本绑定、报告输入快照和索引要求。
- `task-runtime`: 增加报告生成任务类型及其状态/SSE 行为。
- `api-e2e-test-suite`: 增加迁移报告端到端测试模块。

## Impact

- 后端代码：新增 `report` 领域模块、报告 runtime handler、报告文件生成器、repository/service/controller。
- 数据库：新增 Liquibase 迁移，为 `reports` 补充 `source_revision_id` 和必要索引；视情况补充 `report_inputs` 输入类型约束。
- API：新增 `/api/projects/{projectId}/reports/evaluation`、`/api/reports/{reportId}` 等报告接口。
- 任务系统：新增 `REPORT_GENERATE` 任务类型，复用 RabbitMQ worker、任务日志和项目/任务 SSE。
- 对象存储：报告 HTML/JSON 保存到已完成的对象存储制品能力中，通过 `stored_artifacts` 记录元数据，API 不返回服务器真实路径、bucket 或 object key。
- 测试：新增 report 单元测试和 E2E 模块，验证权限、空输入、快照不可变、下载格式和清理行为。
