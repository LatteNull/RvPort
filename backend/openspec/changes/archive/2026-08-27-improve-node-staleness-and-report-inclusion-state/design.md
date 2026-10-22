## Context

后端已经通过 `source_revisions.is_active`、各节点运行表的 `source_revision_id`、以及 `project_runtime_environments.version` / `environment_config_version` 保存了源码版本和运行环境配置版本。当前问题不在于缺少历史数据，而在于节点列表默认视图没有统一收敛到“当前源码 + 当前运行环境”，前端容易把旧记录展示成当前节点结果。

评估报告已经使用 `migration_input_refs` 作为当前输入池，并在生成报告时写入 `report_inputs` 快照。缺口是 API 没有比较当前输入池和最新报告快照，因此前端不知道报告是否需要重新生成。节点内确认也已经落在 `migration_input_refs.status`，但 KB finding 和依赖分析结果列表没有直接返回该条与报告的关系。

## Goals / Non-Goals

**Goals:**

- 当前节点列表默认只展示 active source revision 下的当前结果。
- 依赖运行环境的节点默认只展示当前 `environment_config_version` 下的结果。
- 旧记录保留为历史，通过显式参数查看。
- 节点列表记录返回是否当前、是否陈旧、是否已纳入最新报告、是否会进入下一次报告。
- 报告 readiness/detail 返回最新报告是否已经覆盖当前 confirmed 输入，以及差异摘要。

**Non-Goals:**

- 不物理删除历史构建、依赖分析、KB 扫描、测试或报告记录。
- 不重新引入独立迁移输入合并节点。
- 不处理前端页面改造。
- 不改变报告生成时只读取 `CONFIRMED` 输入的规则。
- 不恢复 deprecated SBOM 新流程入口。

## Decisions

### 1. 使用软失效，不做级联删除

环境更新时继续递增项目运行环境版本；源码更新时继续创建新的 active source revision。节点查询通过版本字段判定记录是否 current/stale。

原因：历史记录仍然有审计价值，也会被报告比较、归档和历史查看使用。物理删除会破坏已有报告快照和历史任务追踪。

### 2. 当前节点默认过滤，历史查看显式开启

列表 API 默认使用：

- `sourceRevisionId` 未传时解析 active source revision；
- `currentOnly=true`；
- 对依赖运行环境的记录要求 `environmentConfigVersion == currentRuntimeEnvironment.version`；
- 需要查看旧记录时由前端显式传 `sourceRevisionId`、`environmentConfigVersion` 或 `includeStale=true`。

这种设计让当前节点页面默认收敛，同时保留审计查询能力。

### 3. 报告更新状态基于快照集合比较

报告 readiness/detail 对比两组集合：

- 当前将进入报告的输入：当前源码版本下 `migration_input_refs.status=CONFIRMED`；
- 最新成功报告的输入：该报告的 `report_inputs.input_type=MIGRATION_INPUT_REF` 和 `input_id`。

输出 `reportUpToDate` 和 `reportDiffSummary`。差异至少包含：

- `added`: 当前 confirmed 中存在、最新报告快照中不存在；
- `removed`: 最新报告快照中存在、当前 confirmed 中不存在；
- `changed`: 同一 input id 存在但当前 reference 的关键字段或状态与快照不同；
- `currentConfirmedInputCount`；
- `latestReportInputCount`。

### 4. 节点记录报告状态动态计算

KB finding 和依赖分析结果不直接保存“报告状态”。列表查询时按 `(sourceType, sourceRefId, sourceRevisionId)` 关联 `migration_input_refs`，再关联当前源码版本最新成功报告的 `report_inputs`。

建议 DTO 字段：

- `migrationInputRefId`
- `migrationInputStatus`
- `confirmedForNextReport`
- `includedInLatestReport`
- `latestReportId`

如果没有最新报告，`includedInLatestReport=false` 且 `latestReportId=null`。

### 5. 陈旧状态字段统一表达

依赖版本的节点记录返回：

- `currentSourceRevision`: 记录的 `sourceRevisionId` 是否等于 active source revision；
- `currentRuntimeEnvironment`: 已有字段继续保留；
- `staleReasons`: 字符串数组，例如 `SOURCE_REVISION_CHANGED`、`RUNTIME_ENVIRONMENT_CHANGED`。

不依赖运行环境的节点可以只返回 `currentSourceRevision`。

## Risks / Trade-offs

- [Risk] 默认过滤可能让用户误以为旧记录消失。→ 在 API 文档和响应字段中保留 `includeStale` / `currentOnly` 语义，并提供历史查询参数。
- [Risk] 每条记录动态联表计算报告状态可能增加查询复杂度。→ 只针对分页当前页计算，并为 `migration_input_refs(source_revision_id, source_type, source_ref_id)` 和 `report_inputs(report_id, input_id)` 使用现有或补充索引。
- [Risk] 报告快照 `changed` 判断过细会导致噪声。→ MVP 只比较状态、备注、detectedLevel、issueTitle、locationLabel、recommendationSummary 等报告可见字段；真实来源详情变化暂不作为强制 changed。
- [Risk] 历史报告和当前输入状态同时展示可能让前端理解复杂。→ 字段命名明确区分 `includedInLatestReport` 与 `confirmedForNextReport`。

## Migration Plan

1. 先补充查询 DTO 和 service 逻辑，不修改历史数据。
2. 如现有索引不足，通过 Liquibase 增加轻量索引。
3. 更新 E2E，验证源码更新和环境更新后当前列表默认不返回旧记录，但显式历史查询可返回。
4. 回滚时移除新增响应字段和过滤参数即可，历史数据无需迁移回滚。

## Open Questions

- “所有节点列表”是否包含归档、报告比较、优化轮次这类二级历史节点？建议第一轮只处理当前主流程节点和可进入报告的结果列表。
- `changed` 是否需要比较完整 `input_snapshot`？MVP 建议只比较报告可见字段，避免来源详情轻微变化导致过多更新提示。
