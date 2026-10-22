## Context

`test` 项目生成迁移评估报告失败时，`tasks.status` 已进入 `FAILED`，但 `reports.status` 仍为 `PENDING`。数据库中该源码版本存在 1014 条 `CONFIRMED` 迁移输入，且 KB finding 和依赖分析结果引用都能回查，不是输入缺失或悬空引用问题。

当前报告生成流程在一个 `@Transactional` 方法中完成读取输入、写入 `report_inputs`、生成 HTML/JSON、保存对象存储制品、更新 `reports`、登记归档候选。后半段任意异常都会回滚前面所有数据库写入。实际触发点是某条依赖输入的 `locationLabel=include:../include` 被写入归档候选 summary 后，归档候选安全校验拒绝包含 `../` 的字符串，最终报告生成整体回滚。

## Goals / Non-Goals

**Goals:**

- 报告生成失败时，`reports.status` 必须可靠进入 `FAILED`、`CANCELLED` 或其他任务终态一致状态。
- 报告归档候选 summary 只保存安全聚合信息，不保存完整报告明细、路径、evidence、对象存储内部 key 或其他敏感/危险文本。
- `REPORT_GENERATE` 失败时保留足够的脱敏 root cause，能定位失败阶段和底层异常类型。
- 修复后 `include:../include` 这类报告明细仍可出现在报告 HTML/JSON 中，但不能阻断归档候选登记。

**Non-Goals:**

- 不改报告 HTML/JSON 的业务内容和展示结构。
- 不新增数据库表。
- 不放宽归档候选安全校验对 `../`、绝对路径、敏感字段的拒绝策略。
- 不清理历史失败报告记录；历史数据可后续按运维脚本处理。

## Decisions

### 报告正文和归档候选 summary 分离

报告正文仍通过 `report_inputs` 快照和对象存储 artifact 保存完整明细。归档候选 summary 改为专用轻量摘要，只包含：

- schema version
- report id
- risk level
- confirmed input count
- high risk issue count
- estimated workload
- source type counts
- detected level counts
- artifact count 或格式列表

归档候选 summary 不保存 `priorityIssues`、`dependencySubstitutionNotes`、`locationLabel`、`evidence`、`sourceDetail`、路径字段或完整问题明细。

选择该方案的原因是：归档候选是归档节点索引，不是报告内容载体。完整报告已经有 HTML/JSON artifact，候选只需要帮助前端展示“可归档什么”和帮助归档包找到 artifact。

### 报告状态写入从大事务中拆出

报告生成不应把所有步骤放在单个事务里。推荐方式：

- `reports.status=RUNNING` 使用独立事务写入。
- `report_inputs` 可按报告生成批次写入；如果后续失败，可保留失败快照或由失败清理策略删除，但报告终态不能被回滚。
- `reports.status=FAILED/CANCELLED/SUCCEEDED` 使用独立事务写入。
- 对象存储写入和数据库 artifact 元数据写入失败时，需要显式清理已上传对象。

这样即使归档候选登记、对象存储或序列化失败，报告记录仍能反映真实终态。

### 归档候选登记失败不应破坏已成功报告

报告内容、报告状态和 artifact 保存成功后，归档候选登记失败不应让报告本身失败。候选登记可以：

- 使用安全 summary 避免失败。
- 若仍因归档候选异常失败，应记录脱敏 warning，并保持报告 `SUCCEEDED`。

原因是归档候选是报告成功后的附加索引能力，不能反向破坏已经生成的报告。

### 任务失败必须保留 root cause

`TaskExecutionException` 如果包含 cause，worker 日志必须打印异常栈。任务错误摘要和报告 summary 可保存脱敏字段：

- `errorCode`
- `errorMessage`
- `failureStage`
- `causeClass`
- `causeMessage`

这些字段不得包含服务器真实路径、对象存储 key、凭据、token 或完整输入快照。

## Risks / Trade-offs

- [Risk] 拆事务后可能留下部分中间数据。
  Mitigation: 使用明确状态表达失败报告，并在同一 report id 下 upsert/删除旧 artifact；报告详情只展示成功报告的 artifact。

- [Risk] 归档候选 summary 变少，前端归档候选列表可展示信息减少。
  Mitigation: 候选列表展示聚合信息；用户需要明细时通过报告详情和 artifact 下载查看。

- [Risk] root cause message 可能包含敏感路径。
  Mitigation: 写入 API 响应、task event、report summary 前复用现有脱敏工具或增加统一脱敏方法。

- [Risk] 归档候选登记失败被降级后可能导致报告成功但不可归档。
  Mitigation: 写 warning 日志和安全摘要，后续可通过修复任务重新登记候选；本 change 优先保证报告生成主路径可靠。
