## Context

当前后端已经把迁移流程拆成多个事实节点：源码版本、迁移输入、迁移报告、复检差异、源码部署、构建验证、自动化测试和测试结果比较。前端如果想展示“第几轮优化做到了什么程度”，只能分别查询多个资源并自行拼接。这个方式会让轮次边界不稳定，也会让历史多轮展示依赖前端推断。

本 change 将“优化闭环”定义为按源码版本落库的多轮聚合展示层。它只记录轮次边界和聚合摘要，不接管各节点的执行、不做自动决策、不替代各节点自己的状态。

## Goals / Non-Goals

**Goals:**

- 为每个项目的每个 active 源码版本建立稳定优化 cycle。
- 支持展示当前轮和历史多轮优化结果。
- 聚合展示迁移输入、报告、复检、源码部署、构建、测试和测试比较摘要。
- 保持后端为事实来源，前端不需要自己推断轮次号或跨节点拼装轮次边界。
- 所有优化 cycle API 遵循项目访问权限、分页、排序和过滤规则。

**Non-Goals:**

- 不自动触发扫描、SBOM、报告、复检、构建或测试。
- 不做“是否通过”“是否收敛”的业务决策。
- 不新增自动修复、一键修复或在线代码编辑。
- 不复制或迁移旧源码版本的迁移输入。
- 不把各节点的大 JSON、完整日志或报告正文保存到 cycle 表中。

## Decisions

### 使用 `optimization_cycles` 落库表达轮次边界

每个 cycle 绑定 `project_id` 和 `source_revision_id`，并使用 `cycle_number` 表达项目内第几轮优化。数据库使用唯一约束保证同一项目同一源码版本只存在一个 cycle，同时保证项目内轮次号唯一。

替代方案是完全动态聚合源码版本列表。这个方案实现更轻，但无法稳定保存轮次状态、创建时间和用户可见的历史边界，也不利于后续加审计、备注或归档。因此采用落库。

### cycle 状态只做展示，不做决策

cycle 状态建议只包含 `ACTIVE`、`SUPERSEDED` 以及必要的 `ARCHIVED` 或等效展示态。当前 active 源码版本对应 cycle 为 `ACTIVE`，旧 active cycle 在新源码版本激活后标记为 `SUPERSEDED`。

不引入 `PASSED`、`FAILED`、`CONVERGED` 这类判断性状态。构建失败、测试失败、比较 blocking 等结果都保留在各自节点摘要中展示。

### 聚合摘要按查询动态生成，cycle 表只存轻量 snapshot

`optimization_cycles` 表保存轮次元数据和可选 `summary` JSONB。API 查询时从事实表动态聚合最新摘要：

- `migration_input_refs`
- `reports`
- `recheck_runs` / `diff_items`
- `source_deploy_runs`
- `build_runs`
- `test_runs`
- `test_comparison_runs`

这样能避免 cycle 表成为第二事实来源。`summary` 只用于保存安全、可快速展示的缓存摘要；如果实现缓存，必须允许从事实表重建。

### 源码版本激活时创建或复用 cycle

源码包上传或 Git 同步成功并激活新源码版本时，后端创建或复用对应 cycle。首次源码导入创建第 1 轮；之后按项目内最大 `cycle_number + 1` 创建下一轮。并发激活场景依赖唯一约束和事务处理防止重复轮次。

### API 以项目为入口

优化闭环是项目工作台展示能力，因此 API 使用项目级路径：

- `GET /api/projects/{projectId}/optimization/overview`
- `GET /api/projects/{projectId}/optimization/cycles`
- `GET /api/projects/{projectId}/optimization/cycles/{cycleId}`

所有接口都必须先校验项目访问权限。列表接口支持分页、过滤和排序。

## Risks / Trade-offs

- [Risk] 源码版本激活和 cycle 创建并发导致轮次号冲突。  
  Mitigation: 使用数据库唯一约束，service 层在事务内计算轮次号并处理唯一冲突重试或复查。

- [Risk] 聚合查询跨多个大表，概览接口性能下降。  
  Mitigation: 默认只聚合当前 cycle 或分页 cycle；每个子摘要只取最新记录和计数，不读取完整日志、artifact 正文或 agent 输入。

- [Risk] cycle summary 与事实表不一致。  
  Mitigation: cycle 表不作为节点状态事实来源；API 优先从事实表动态聚合，summary 仅作为可重建缓存或展示摘要。

- [Risk] 前端把 cycle 状态误用为流程决策。  
  Mitigation: API 字段命名和文档明确 cycle 只做展示聚合，不提供 nextAction 或自动决策结论。

## Migration Plan

1. 新增 `optimization_cycles` 表、约束和索引。
2. Liquibase 对已有项目按 source revision 创建历史 cycle：每个项目按 source revision 创建时间递增分配 `cycle_number`，active source revision 对应 cycle 标记为 `ACTIVE`，其余为 `SUPERSEDED`。
3. 运行 jOOQ 生成脚本。
4. 接入源码版本激活流程，创建或复用 cycle。
5. 新增优化聚合查询 API 和 E2E。

回滚时可以停止调用 cycle 创建逻辑并保留表数据；由于 cycle 不是下游节点事实来源，回滚不影响已有扫描、报告、构建或测试记录。

## Open Questions

- cycle 是否需要用户备注或人工标记字段？当前不做，后续可扩展。
- 是否需要在项目 overview 中直接嵌入当前 cycle 摘要？当前建议先提供独立 optimization overview API，避免扩大现有 overview 响应。
