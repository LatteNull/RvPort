## Why

`test` 项目生成迁移评估报告时失败，数据库中任务进入 `FAILED`，但报告记录仍停留在 `PENDING`，且后端日志只显示 `TASK_HANDLER_FAILED`，没有真实异常原因。排查发现报告成功生成内容后登记归档候选时，候选 summary 混入 `include:../include` 这类明细路径，被归档安全校验拒绝，并因报告生成整体事务回滚导致状态、输入快照和制品记录都没有保留下来。

## What Changes

- 修改迁移评估报告生成流程，使报告状态、失败摘要和关键进度在异常时可靠落库，不再因为同一事务回滚而长期停留在 `PENDING`。
- 调整迁移评估报告登记归档候选的 summary，只保存安全聚合信息和报告/制品引用，不保存完整问题明细、路径文本、evidence 或其他可能触发归档安全策略的字段。
- 增强 `REPORT_GENERATE` 任务失败可观测性，在任务错误摘要和后端日志中保留脱敏后的 root cause 类型、阶段和业务错误码。
- 增加测试覆盖：正常报告生成、归档候选包含安全摘要、带 `../` 的迁移输入仍能生成报告、报告失败时状态一致、worker 日志保留 cause。
- 不改变报告 HTML/JSON 下载内容；报告明细仍保存在对象存储制品和 `report_inputs` 快照中。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `migration-report-runtime`: 迁移评估报告生成失败时必须可靠写入报告终态，并且归档候选登记必须使用安全聚合摘要。
- `project-archive-runtime`: 归档候选 summary 必须保持轻量、安全，不承载完整报告明细或路径逃逸文本；完整报告内容通过 artifact 引用下载。
- `task-runtime`: `REPORT_GENERATE` 失败时任务运行时必须保留脱敏 root cause，便于定位实际失败阶段。

## Impact

- 影响后端报告生成运行时、报告仓储事务边界、归档候选登记、任务 worker 失败日志。
- 影响 `reports`、`report_inputs`、`stored_artifacts`、`archive_candidates` 的写入时序，不需要新增数据库表。
- 影响测试：需要补充报告生成单元测试和必要的集成/E2E 验证。
