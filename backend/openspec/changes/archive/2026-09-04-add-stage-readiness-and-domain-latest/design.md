## Context

当前项目工作台已经有项目 overview、各领域 list/detail/create 接口，以及评估报告页专用 readiness。随着节点增加，前端需要判断“当前阶段能否执行”“当前阶段最新结果是什么”“结果是否属于当前源码和运行环境”，这些判断如果散落在前端和领域接口中，会导致旧 Context 结果误用、按钮状态不一致、写接口缺少服务端二次校验。

文档中的 Feature-v0.0.2 已明确两个方向：readiness 是项目级阶段事实接口，latest 是领域接口加统一响应外壳。后端只返回事实，不返回按钮、动作和 UI 文案。

## Goals / Non-Goals

**Goals:**

- 提供 `GET /api/projects/{projectId}/readiness?stageId=...`，按当前 Context 返回阶段前置条件事实。
- 为主要异步领域提供 latest 接口或 latest 外壳，统一返回 context、freshness、execution 和 result。
- 明确 `sourceRevisionId` 与 `runtimeEnvironmentVersion` 对 CURRENT/STALE 的影响。
- 写接口在创建任务前复用 readiness 的核心校验逻辑，但必须重新读取数据库当前状态。
- 保持领域 result 结构不被统一外壳抹平，前端可以继续按领域展示。

**Non-Goals:**

- 不在后端返回按钮配置、推荐动作、按钮文案或页面跳转。
- 不重构已有列表和详情接口的分页、排序、过滤机制。
- 不删除已有历史接口，历史查询继续通过 list/detail。
- 不恢复已经废弃的 SBOM 节点作为新流程前置条件。

## Decisions

### 1. readiness 使用项目级统一接口

新增 `StageReadinessController`，路径为 `GET /api/projects/{projectId}/readiness?stageId={stageId}`。service 内部根据 stageId 分派到阶段 readiness provider。

这样做的原因是 readiness 返回的是跨领域的前置事实，例如依赖分析依赖 x86 构建和目标环境，评估报告依赖已确认输入和可比较报告。把它放到单一项目级接口可以避免每个领域重复定义不同形态的 readiness。

### 2. latest 保留领域接口，但使用统一外壳

每个领域 latest 返回 `DomainLatestResponse<T>`：

- `context`: 当前 active source revision 与当前 runtime environment version。
- `freshness`: `CURRENT`、`STALE` 或 `EMPTY`。
- `execution`: 最新执行记录摘要，可以表达 `PENDING`、`RUNNING`、`FAILED`、`SUCCEEDED`、`CANCELED`。
- `result`: 领域结果结构，保持各领域已有 DTO 或摘要 DTO。

latest 查询不得跳过最新失败记录。如果当前 Context 最新一次执行失败，latest 必须返回失败 execution，而不是回退到更早成功结果。

### 3. Context 计算集中化

新增轻量 `ProjectContextSnapshot`，由当前 active source revision 和 `ProjectRuntimeEnvironmentService.currentVersion(projectId)` 组成。需要源码的阶段必须比较 `sourceRevisionId`；需要环境的阶段必须比较 `environmentConfigVersion`。

对于只受源码影响的阶段，例如知识库扫描，只比较 source revision。对于构建、依赖分析、自动化测试、归档等阶段，需要同时考虑源码版本和环境配置版本。

### 4. readiness provider 返回事实，不返回操作建议

provider 只返回：

- `key`
- `status`
- `referenceId`
- `reasonCode`
- 可选 `details`

`ready`、`actions`、`buttonLabel`、`recommendedAction` 不进入 readiness 响应。前端可以基于稳定 key/status 组合决定 UI 行为。

### 5. 写接口复用校验，但不能复用旧查询结果

构建、依赖分析、自动化测试、报告生成、归档等写接口必须在事务中重新读取当前 Context 和前置执行记录。如果不满足条件，返回 `PREREQUISITE_NOT_SATISFIED`，并包含 `stageId`、`prerequisite`、`status` 和 `reasonCode`。

### 6. 阶段映射先覆盖当前流程

首批 stageId：

- `kb`
- `x86-build`
- `rv-dependency-analysis`
- `report`
- `build`
- `test`
- `optimize`
- `archive`

`project`、`env`、`assets`、`manual` 暂不提供 readiness，因为它们不是独立异步执行条件查询的主要目标。

## Risks / Trade-offs

- [Risk] 各领域最新记录的定义不一致，可能出现 latest 结果和列表第一条不一致。→ Mitigation：为每个领域 repository 明确 `findLatestForCurrentContext` 或等效查询，列表接口继续保持历史查询语义。
- [Risk] readiness 和写接口校验逻辑重复后产生漂移。→ Mitigation：抽出 provider/checker，被查询接口和写接口共同调用，但写接口必须实时读取。
- [Risk] 统一 latest 外壳会改变已有 latest 响应结构。→ Mitigation：这是面向 Feature-v0.0.2 的 API 调整，需要 E2E 固化；历史 list/detail 不改。
- [Risk] 运行中任务和最新失败任务同时存在时状态判断模糊。→ Mitigation：readiness 优先返回 RUNNING；latest execution 返回最新任务的真实状态，必要时 result 为 null。
- [Risk] 旧 SBOM 相关代码仍存在导致 stage 混淆。→ Mitigation：本 change 不新增 SBOM readiness/latest，后续看到旧 SBOM 只作为历史兼容或废弃内容处理。
