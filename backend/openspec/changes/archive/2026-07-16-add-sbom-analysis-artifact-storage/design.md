## Context

SBOM 分析当前已经具备三类持久化数据：

- `sbom_runs.summary` 保存运行摘要、warnings 和工具信息。
- `sbom_components` 保存分析后的组件事实。
- `replacement_candidates` 保存替代候选和证据 metadata。

这些表适合保存组件事实和候选事实，但前端审计页面还需要一个稳定的“分析结果明细”查询模型：每一条 package、library、tool 或 native file 对比结果都应该能独立分页、排序和过滤。真实验证流程中生成的 JSON 可以作为输入输出摘要来源，但不能把完整结果数组整体塞进单个 `jsonb` 字段。

现有数据库 spec 同时明确“不引入通用 artifact 表”。因此本设计选择 SBOM 领域专用结果明细表和摘要 artifact 表，而不是全局 artifact 模型。

## Goals / Non-Goals

**Goals:**

- 在 SBOM 分析成功后按行持久化可查询的分析结果明细。
- 结果明细和 artifact 同时绑定 `project_id`、`task_id` 和 `sbom_run_id`。
- 提供 SBOM 分析维度的结果明细分页查询 API。
- 提供 SBOM 分析维度的轻量 artifact 查询 API。
- 将列表类 API 必须支持分页、排序和过滤沉淀为全局 API 约定。
- 复用现有项目访问权限校验。
- 保证 artifact 和结果 evidence 不包含明文凭据、私钥、token、passphrase、完整任务日志、完整 analyzer output 或服务器真实绝对路径。
- 保证 E2E 能验证结果明细、artifact 入库、副作用、脱敏和清理。

**Non-Goals:**

- 不实现通用 artifact 表或通用 `GET /api/tasks/{taskId}/artifacts`。
- 不把完整 HTML 报告入库。
- 不把完整 `environment_snapshots.raw_snapshot` 复制进 artifact 或 evidence。
- 不把分析器完整输入 JSON、完整输出 JSON 或完整结果数组原文无筛选入库。
- 不改变现有 `sbom_components` 和 `replacement_candidates` 的查询语义。

## Decisions

### 1. 使用 SBOM 专用结果明细表和摘要 artifact 表

新增两张 SBOM 专用表：

- `sbom_analysis_result_items`：每条分析结果一行，用于前端分页、排序、过滤和审计。
- `sbom_analysis_artifacts`：只保存运行级轻量摘要或 manifest，不保存完整结果明细数组。

这两张表只服务 SBOM 分析，不承载源码包、日志、报告、归档等其他领域产物。

原因：

- 符合现有 “MVP 不包含通用 artifact 持久化” 约束。
- 避免提前设计跨领域 artifact 生命周期、权限模型和存储策略。
- SBOM 结果和 artifact 的查询权限天然依赖 `sbom_run_id` 与项目访问权限。
- 结果明细独立成行后，列表查询可以使用普通列和索引，不依赖扫描巨大 JSON。

### 2. 同时保存 `project_id`、`task_id` 和 `sbom_run_id`

字段分工：

- `project_id`：用于权限校验、项目维度查询和清理。
- `task_id`：用于任务追踪、SSE/任务详情排查和运行链路审计。
- `sbom_run_id`：用于 SBOM 业务详情关联。

表约束：

- `sbom_analysis_result_items.project_id` 引用 `projects(id)`。
- `sbom_analysis_result_items.task_id` 引用 `tasks(id)`。
- `sbom_analysis_result_items.sbom_run_id` 引用 `sbom_runs(id)`。
- `sbom_analysis_artifacts.project_id` 引用 `projects(id)`。
- `sbom_analysis_artifacts.task_id` 引用 `tasks(id)`。
- `sbom_analysis_artifacts.sbom_run_id` 引用 `sbom_runs(id)`。
- `sbom_analysis_artifacts` 保持 `UNIQUE (sbom_run_id, artifact_type)`。
- `sbom_analysis_artifacts` 保持 `UNIQUE (task_id, artifact_type)`。
- `sbom_analysis_artifacts.size_bytes` 必须大于 0。

### 3. 结果明细按行保存，JSON 只保存有限 evidence

`sbom_analysis_result_items` 保存用于查询的稳定列：

- 身份和关联：`id`、`project_id`、`task_id`、`sbom_run_id`。
- 源侧信息：`component_type`、`source_name`、`source_version`、`source_arch`、`source_package_name`、`source_package_version`。
- 目标侧信息：`target_match_status`、`target_name`、`target_version`、`target_package_name`、`target_package_version`。
- 判断信息：`risk_level`、`match_strategy`、`recommendation`、`confidence`。
- 证据摘要：`evidence jsonb`，只保存匹配解释所需的有限证据。
- 时间：`created_at`。

索引优先覆盖常见查询：

- `sbom_run_id, created_at DESC`
- `project_id, task_id`
- `sbom_run_id, component_type`
- `sbom_run_id, source_name`
- `sbom_run_id, risk_level`
- `sbom_run_id, target_match_status`

### 4. artifact 类型从轻量摘要 JSON 开始

MVP 支持：

- `AUDIT_SUMMARY_JSON`：前端审计页面使用的轻量摘要。
- `ANALYZER_INPUT_SUMMARY_JSON`：分析器输入摘要，只保存 counts、快照摘要和选项，不保存完整组件数组。
- `ANALYZER_OUTPUT_SUMMARY_JSON`：分析器输出摘要，只保存 counts、warnings、tool 信息和有限候选样本。

`content` 使用 `jsonb`，但只允许保存运行级摘要、统计、warnings、工具信息、有限样本和结果查询入口。`summary` 保存 artifact 自身的摘要，便于列表接口不读取完整内容。

### 5. 在 SBOM_ANALYSIS 成功路径中先写明细，再写 artifact

`SbomAnalysisRuntimeService` 成功解析 analyzer result 后：

1. 将 package、library、tool 和 native file 对比结果逐条写入 `sbom_analysis_result_items`。
2. 使用 analyzer input 生成输入摘要。
3. 使用 analyzer result 生成输出摘要。
4. 使用 run、task、source/target snapshot、counts、warnings 和有限样本生成审计摘要。
5. 计算 artifact JSON canonical bytes 的 `sha256` 和 `size_bytes`。
6. 写入 `sbom_analysis_artifacts`。
7. 最后更新 `sbom_runs` 为 `SUCCEEDED`。

如果结果明细或 artifact 写入失败，本次 SBOM 任务 SHALL 失败并回滚到失败态，因为它们是本 change 后成功态结果的一部分。

### 6. API 只提供 SBOM 维度入口

新增：

- `GET /api/sbom-analyses/{analysisId}/results`
- `GET /api/sbom-analyses/{analysisId}/artifacts`
- `GET /api/sbom-analyses/{analysisId}/artifacts/{artifactType}`

结果明细列表接口返回分页响应，并支持过滤和排序：

- 分页：`page`、`pageSize`，沿用现有分页边界策略。
- 过滤：`componentType`、`sourceName`、`sourceVersion`、`sourcePackageName`、`targetMatchStatus`、`targetName`、`targetVersion`、`targetPackageName`、`riskLevel`、`matchStrategy`、`recommendation`。
- 排序：`componentType`、`sourceName`、`sourceVersion`、`targetMatchStatus`、`riskLevel`、`matchStrategy`、`createdAt`，默认 `riskLevel DESC, componentType ASC, sourceName ASC`。

artifact 列表接口返回分页响应，并支持过滤和排序：

- 分页：`page`、`pageSize`，沿用现有分页边界策略。
- 过滤：`artifactType`、`schemaVersion`、`taskId`、`sha256`、`createdFrom`、`createdTo`、`minSizeBytes`、`maxSizeBytes`。
- 排序：`artifactType`、`schemaVersion`、`createdAt`、`sizeBytes`、`sha256`，默认 `createdAt DESC, artifactType ASC`。
- 排序字段必须使用白名单，避免把任意字段拼接进 SQL。

不新增任务维度 API。表中保留 `task_id`，但等任务详情页需要展示 artifact 时再扩展。

### 7. 列表能力作为全局 API 约定

本 change 会同步修改 `backend-api-design` 的通用约定：后续所有返回集合或列表数据的接口，默认都必须支持分页、排序和过滤。

实现要求：

- 分页参数和响应格式统一使用现有 `PageResponse` 风格。
- 过滤字段按资源定义白名单，多个过滤条件默认 AND 语义。
- 排序字段按资源定义白名单，默认排序必须稳定。
- 不适合分页、排序或过滤的集合接口必须在对应 spec 中写明例外原因，并保证响应规模可控。

### 8. HTML 不入库

HTML 审计页应由前端或后端基于结果明细 API 和 `AUDIT_SUMMARY_JSON` 生成。数据库保存结构化结果行和轻量 JSON 摘要，避免 HTML 版本、样式和大文本膨胀进入数据模型。

## Risks / Trade-offs

- [Risk] 结果明细与现有 `sbom_components`、`replacement_candidates` 有重复 → 明细表定位为前端查询读模型，保留稳定列和有限 evidence，避免前端跨多张事实表拼装。
- [Risk] artifact JSON 过大导致数据库膨胀 → artifact 只保存摘要和样本；完整明细进入 `sbom_analysis_result_items`。
- [Risk] artifact 内容重复已有结构化表 → artifact 只承担运行级审计摘要用途，不作为组件查询主数据源。
- [Risk] 脱敏遗漏 → artifact builder 和 result item builder 必须只从白名单字段组装内容，不复制完整 raw payload。
- [Risk] 新增状态写入导致事务复杂 → 结果明细写入、artifact 写入与 SBOM 结果导入放在同一成功路径，失败时按 SBOM 分析失败处理。
- [Risk] 后续需要按 task 查询 artifact → 当前表已保留 `task_id` 和索引，后续只需增加 API，不需迁移表结构。
- [Risk] 多字段排序和过滤增加查询复杂度 → 使用显式白名单映射到 jOOQ 字段，分页接口不允许任意 SQL 字段名。

## Migration Plan

1. 新增 Liquibase changeset 创建 `sbom_analysis_result_items` 和 `sbom_analysis_artifacts`。
2. 运行 jOOQ 生成脚本，生成新表访问代码。
3. 增加 repository/service/runtime/controller 支持。
4. 增加单元测试和 E2E 验证。
5. 部署时新表为空；历史 SBOM 运行不回填结果明细或 artifact。

Rollback：

- 若未发布 API，可回滚代码并保留空表。
- 若需要数据库回滚，可删除 `sbom_analysis_result_items` 和 `sbom_analysis_artifacts`，不影响现有 SBOM 结构化结果表。

## Open Questions

- 是否需要 artifact 保留策略或清理策略。MVP 先随 SBOM run 生命周期保留，E2E 清理测试数据。
- 是否需要支持后端直接返回 HTML。MVP 不做，前端可基于 JSON 和结果明细 API 渲染。
