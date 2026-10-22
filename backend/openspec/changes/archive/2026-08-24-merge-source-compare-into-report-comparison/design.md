## Context

当前后端已经具备源码版本复检能力：`SourceController` 暴露 latest compare 和 recheck API，`RecheckDiffRuntimeService` 基于两个源码版本下已确认的迁移输入生成 `diff_items`，归档候选也能登记复检结果。该能力的底层模型可用，但产品流程上“源码对比”作为人工修复后的独立节点价值较弱。

评估报告已经绑定 `source_revision_id`，并通过 `report_inputs.input_snapshot` 保存生成时的不可变输入快照。用户在评估报告页查看当前报告和历史报告时，更自然的操作是对比两份报告，而不是跳转到单独的源码对比节点。

## Goals / Non-Goals

**Goals:**

- 在评估报告页提供历史报告列表能力，支持查看过往报告。
- 新增报告比较 API，允许当前报告与上一份可比较历史报告或指定历史报告进行比较。
- 报告比较基于 `report_inputs.input_snapshot`，保证历史报告比较稳定、可审计。
- 复用现有 recheck/diff 的差异语义：`RESOLVED`、`UNCHANGED`、`NEW`、`CHANGED`。
- 将源码对比 API 标记为兼容能力，不再作为主流程节点入口。

**Non-Goals:**

- 不实现前端页面。
- 不删除现有 `recheck_runs`、`diff_items` 表和 source compare API。
- 不实现源码文本 diff、文件级 diff 或 patch 展示。
- 不重新生成历史报告内容。

## Decisions

### 1. 报告比较入口以 report 为中心

新增报告侧入口，例如：

- `POST /api/reports/{reportId}/comparisons`
- `GET /api/report-comparisons/{comparisonId}`
- `GET /api/report-comparisons/{comparisonId}/diff-items`
- `GET /api/report-comparisons/{comparisonId}/diff-items/{diffItemId}`

创建比较时请求体可选传入 `baseReportId`。未传入时，后端自动选择同项目、同报告类型、早于当前报告且已成功生成的最近一份可比较报告。

理由：前端只需要理解“当前报告”和“历史报告”，不需要理解 source revision 对比策略。

### 2. 比较数据来源使用报告输入快照

比较算法读取两份报告的 `report_inputs.input_snapshot`，而不是读取当前 `migration_input_refs` 或原始扫描结果。

理由：报告是用户已查看和归档的事实，比较报告应保持历史一致性；如果动态读取当前输入，会导致同一份历史报告在不同时间比较结果不同。

### 3. 底层差异模型可复用但需要报告语义封装

实现可以复用现有 `diff_items` 字段和匹配算法，但对外响应应使用 report comparison 命名。可选方案有两种：

- 复用 `recheck_runs` 增加 `base_report_id`、`target_report_id` 或在 summary/evidence 中记录报告引用。
- 新建 `report_comparison_runs` 并复用 diff item 结构或新建 `report_comparison_diff_items`。

MVP 优先选择改动较小的方案：复用现有 diff item 结构，增加报告侧服务封装和必要索引/引用字段。如果现有表语义过窄，再通过 Liquibase 增补 report comparison 表。

### 4. 源码对比 API 保留兼容

`GET /api/projects/{projectId}/source/compare/latest`、`POST /api/projects/{projectId}/rechecks`、`POST /api/projects/{projectId}/rechecks/latest` 保留，不作为主流程推荐入口。

理由：避免破坏已有 E2E、调试脚本和已集成前端，同时让主流程从源码节点迁移到报告节点。

### 5. 报告历史列表继续使用现有分页接口

`GET /api/projects/{projectId}/reports/evaluation` 继续作为历史报告列表入口，需要确保支持分页、过滤和排序。报告详情和下载继续使用现有接口。

## Risks / Trade-offs

- [Risk] 报告输入快照字段在不同来源类型中结构不一致，比较算法可能需要兼容多种 snapshot schema。
  → Mitigation：抽取统一 comparable input adapter，缺字段时降级为低置信度匹配并保留 evidence。

- [Risk] 复用 recheck 表会让内部命名和外部 report comparison 命名不一致。
  → Mitigation：对外 API 和 response 使用 report comparison 命名，内部可在本次实现中保留 recheck 命名，后续有必要再迁移表名。

- [Risk] 自动选择上一份报告时可能出现同一源码版本多份报告。
  → Mitigation：按 `generated_at desc` 或完成时间选择最近成功报告，并在响应中明确返回 base/target report 摘要。

- [Risk] 历史报告没有输入快照或是早期不兼容格式。
  → Mitigation：返回 `REPORT_COMPARISON_UNSUPPORTED`，不创建比较任务。

## Migration Plan

1. 增加报告比较 API 和服务层。
2. 复用或扩展差异比较 runtime，使其能从两份 report input snapshot 构建 comparable inputs。
3. 在报告响应中增加可选比较入口摘要或 latest comparison 摘要。
4. 保留 source compare API 并更新文档为兼容入口。
5. 补充单元测试和 E2E，覆盖正常流程、异常流程和 edge case。

Rollback 策略：保留原 source compare API，若报告比较入口出现问题，可回退前端入口到原接口，数据库新增字段或表不影响已有报告生成。

## Open Questions

- 是否新建 `report_comparison_runs` 表，还是复用 `recheck_runs` 并增加报告引用字段，需要在实现阶段结合现有查询复杂度决定。
- 报告比较结果是否需要作为归档候选登记为独立 `COMPARISON_REPORT`，还是附属于迁移评估报告归档项，需要实现时确认归档页面展示方式。
