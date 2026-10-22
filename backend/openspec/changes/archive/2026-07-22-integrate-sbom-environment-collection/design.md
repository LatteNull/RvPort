## Context

当前 SBOM 分析链路由前端先触发环境采集，再把 `sourceSnapshotId` 和 `targetSnapshotId` 提交给 `POST /api/projects/{projectId}/sbom-analyses`。后端 `SbomService` 会校验快照归属并创建 `SBOM_ANALYSIS` 任务，`SbomAnalysisRuntimeService` 直接读取已有快照构造 analyzer 输入。

这个设计的问题是快照选择暴露给了前端，前端需要理解“采集”和“分析”的内部依赖，并且可能选择旧快照或漏掉采集。更合理的边界是：前端只选择源环境和目标环境，后端把“采集源环境、采集目标环境、执行分析器、导入结果”作为一个完整长任务处理。

## Goals / Non-Goals

**Goals:**

- SBOM 创建 API 不再要求前端传入源/目标快照 ID。
- `SBOM_ANALYSIS` worker 内部生成本轮源/目标环境快照，并回填到 `sbom_runs`。
- SBOM analyzer 仍然保持独立 CLI，只消费 Java 后端导出的 JSON，不直接访问远端环境或数据库。
- 采集、分析、导入、失败和取消都通过同一个任务状态、任务日志和 SSE 事件表达。
- 采集中或失败时，SBOM 查询接口能够返回可解释的中间状态。

**Non-Goals:**

- 不移除独立环境采集 API；该 API 仍用于调试、兼容和非 SBOM 场景。
- 不让 `tools/sbom-analyzer` 直接 SSH 到远端环境。
- 不实现前端页面调整。
- 不引入并行采集；本 change 优先保证流程一致性和可恢复性。

## Decisions

### 1. SBOM 创建只接收环境 ID

`SbomAnalysisRequest` 只保留 `sourceEnvironmentId` 和 `targetEnvironmentId`，移除或不再接受 `sourceSnapshotId`、`targetSnapshotId`、`repositoryPolicy` 和 `collectScopes`。

理由：

- 快照是本轮分析的执行产物，不应该由前端选择。
- 分析选项目前没有业务选择空间，默认全量分析可以降低前端复杂度和 API 分支。
- 可以避免旧快照、跨环境快照和漏采集导致的结果不一致。
- 权限校验只需要围绕项目和环境进行，API 契约更清晰。

后端创建任务时固定使用默认选项：

- `repositoryPolicy=TARGET_ENV_REPOS`
- `collectScopes=OS, PACKAGE_MANAGER, REPOSITORIES, INSTALLED_PACKAGES, TOOL_VERSIONS, NATIVE_FILES`

可选兼容方案是暂时保留旧字段但忽略或拒绝。建议明确拒绝请求中的 snapshot 和分析选项字段，避免前端误以为可以指定历史快照或局部分析范围。

### 2. `sbom_runs` 支持采集前无快照

数据库需要新增 Liquibase 迁移，将 `sbom_runs.source_snapshot_id` 和 `sbom_runs.target_snapshot_id` 改为可空，并保留外键和索引。worker 采集成功后通过新的 repository 方法回填快照 ID。

理由：

- API 创建后需要立即返回 `taskId`，同时 SBOM 运行记录需要可查询。
- 快照只能在 worker 真实采集成功后生成。
- 允许可空比“先不创建 sbom_run”更利于列表、详情和审计。

查询接口需要对空 snapshot 友好：

- 列表和详情返回 `null` 快照摘要或阶段状态。
- `collection-detail` 在快照未生成时返回“未可用”状态，而不是 `SNAPSHOT_NOT_FOUND`。

### 3. 抽取可返回快照 ID 的环境采集内部接口

当前 `SshRuntimeService.collectEnvironment(...)` 直接执行采集并返回 `void`。需要抽出一个内部方法，例如：

```text
collectEnvironmentSnapshot(input, context, options) -> EnvironmentCollectionResult
```

返回值至少包含：

- `snapshotId`
- `summary`
- `exitCode`
- `toolRunId`

独立 `ENV_COLLECT` handler 继续调用该内部方法并保持原有 API 行为；SBOM runtime 也调用同一内部方法，确保组件写入、provider 证据、ELF metadata、unmanaged 工具证据和脱敏规则一致。

### 4. SBOM worker 使用阶段化执行

`SbomAnalysisRuntimeService.analyze()` 调整为以下顺序：

```text
mark sbom_run RUNNING
progress 5  : 准备 SBOM 采集
progress 10 : 采集源环境
sourceSnapshotId = collect(sourceEnvironment)
update sbom_run.source_snapshot_id
progress 35 : 采集目标环境
targetSnapshotId = collect(targetEnvironment)
update sbom_run.target_snapshot_id
progress 60 : 准备分析输入
run analyzer
progress 80 : 导入结果
mark sbom_run SUCCEEDED
progress 95 : 完成
```

阶段失败语义：

- 源环境采集失败：`phase=SOURCE_COLLECT`，不执行目标采集和 analyzer。
- 目标环境采集失败：`phase=TARGET_COLLECT`，源快照可保留，不能执行 analyzer。
- analyzer 失败：`phase=ANALYZE`，保留两侧快照和 analyzer stdout/stderr 摘要。
- 结果导入失败：`phase=IMPORT_RESULT`，任务失败，不写成功态 summary。

### 5. 目标仓库证据仍由环境角色决定

环境采集已有逻辑会对 `TARGET_RISCV` 采集仓库可用包和 provides 证据。SBOM 内部采集应复用该角色规则：

- 源环境：重点采集已安装包、库、工具、native 文件和 owner/provider 证据。
- 目标环境：采集已安装事实，同时尽量采集仓库包和 repository provides。

如果仓库 metadata 或 provides 失败，但基础快照和已安装组件可用，目标采集可以成功并把警告写入 `raw_snapshot.parseWarnings`，由 analyzer 和 API 继续表达证据不足。

### 6. 取消行为复用任务执行上下文

SBOM 任务现在包含 SSH 采集和本地 analyzer 进程。每个阶段都需要调用 `context.throwIfCancellationRequested()`，远端 SSH 命令和本地 analyzer 进程都应通过已有执行上下文注册取消资源。

取消后的状态：

- `tasks.status=CANCELLED`
- `sbom_runs.status=CANCELLED`
- 已生成快照可保留用于审计
- 不写入成功态 SBOM 结果

## Risks / Trade-offs

- [Risk] SBOM 单个任务耗时变长，因为包含两次环境采集。  
  Mitigation：先保证流程一致性；后续可单独做并行采集优化。

- [Risk] `sbom_runs` 快照字段改为可空后，旧查询代码可能出现 NPE 或 `SNAPSHOT_NOT_FOUND`。  
  Mitigation：所有运行详情、列表和 collection-detail 显式处理空快照。

- [Risk] 环境采集原本作为独立 task 设计，直接复用可能造成 tool run 名称、日志和进度语义混乱。  
  Mitigation：抽取内部采集方法，handler 和 SBOM runtime 分别传入用途上下文，日志仍挂到当前任务。

- [Risk] 源环境采集成功、目标环境失败时会留下部分快照。  
  Mitigation：保留用于审计，并在 `sbom_runs.summary` 中标记失败阶段和已生成快照。

- [Risk] API breaking change 影响当前前端。  
  Mitigation：本 change 只处理后端；API 文档明确新契约，前端另行适配。

## Migration Plan

1. 新增 Liquibase changeset，将 `sbom_runs.source_snapshot_id` 和 `target_snapshot_id` 改为可空。
2. 运行 Liquibase 后重新执行 jOOQ 生成脚本。
3. 更新 SBOM 创建 API DTO、Service 校验和 API 文档，创建请求只接收源环境和目标环境。
4. 抽取环境采集内部方法并保持独立 `ENV_COLLECT` 行为不变。
5. 改造 `SbomAnalysisRuntimeService` 阶段化采集和分析流程。
6. 更新 SBOM 查询接口空快照语义。
7. 补齐单元测试和 E2E 测试。

Rollback：

- 代码回滚后，如果存在快照为空的 `sbom_runs`，旧代码无法处理。回滚前需要删除或标记失败这些未完成运行，再恢复 `NOT NULL` 约束。

## Open Questions

- 是否允许内部/debug API 指定历史 snapshot 复跑分析？本 change 建议不开放，避免扩大 API 语义。
- 目标环境不是 `TARGET_RISCV` 时是否采集 repository provides？当前建议保持既有角色规则，后续如果支持更多目标架构再扩展。
