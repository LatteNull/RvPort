## Context

当前依赖分析在 `DependencyAnalysisHandler` 中通过 `findLatestSucceededSnapshotId(...)` 读取最近一次成功环境快照。该快照可能早于用户对远端环境的实际修改，导致目标环境已删除软件但依赖分析仍返回 `TARGET_INSTALLED`。依赖分析的判断目标是当前 source/x86 构建事实与当前 target/RISC-V 环境能力的匹配，因此使用过期快照会直接降低结果可信度。

现有环境采集能力已经由 `SshRuntimeService.collectEnvironment(...)` 完成，并能写入 `environment_snapshots` 和 `environment_components`。本变更应复用该采集能力，但不引入新的前端编排或通用任务 DAG。

## Goals / Non-Goals

**Goals:**

- 依赖分析 worker 开始分析前默认刷新 source/x86 和 target/RISC-V 环境采集。
- 依赖分析必须使用本次刷新产生的成功 snapshot。
- 任一刷新失败时，依赖分析任务失败，不再使用旧 snapshot 降级。
- 依赖分析 JSON/HTML artifact、任务日志和运行 summary 可审计本次使用的 snapshot。
- E2E 覆盖 stale snapshot 场景，验证环境变化后不会继续命中旧 snapshot。

**Non-Goals:**

- 不增加前端可选跳过刷新开关。
- 不引入通用任务 DAG 或前置任务依赖系统。
- 不改变 source-only 构建必须成功的前置要求。
- 不删除历史 environment snapshots。
- 不把旧 SBOM 流程迁移到该刷新模型。

## Decisions

### 1. 在 `DEPENDENCY_ANALYSIS` worker 内同步刷新环境

依赖分析任务创建仍保持轻量，只创建 `DEPENDENCY_ANALYSIS` 任务和运行记录。真正的远端 SSH 环境刷新在 `DependencyAnalysisHandler` 开始执行后完成。

理由：
- HTTP 创建接口不应因 SSH 采集长时间阻塞。
- 一个依赖分析任务即可对前端表达完整进度：刷新 source、刷新 target、提取事实、生成结果。
- 现阶段没有任务 DAG；用额外 `ENV_COLLECT` 任务编排会放大实现复杂度。

替代方案：
- 创建阶段同步刷新：阻塞 API，不采用。
- 先投递两个 `ENV_COLLECT` 再等待：需要任务 DAG 或轮询编排，不在本变更实现。

### 2. 复用环境采集 runtime，而不是复制采集脚本

实现时应抽取或注入可复用的环境采集服务，使 `DependencyAnalysisHandler` 能以内部调用方式执行采集并获得 `EnvironmentCollectionResult` 或等效结果。

采集输入：
- source 使用成功 source/x86 build run 的 `environmentId`。
- target 使用依赖分析运行记录中的 `targetEnvironmentId`。
- `collectScopes` 使用默认完整范围。
- target 采集需要包含 repository evidence，因为依赖匹配需要目标软件源和 provides/whatprovides 信息。

### 3. 刷新失败即失败

任一环境采集失败时，依赖分析任务应标记为 `FAILED`，并写入安全错误摘要。

理由：
- 依赖分析目标是当前环境判断，使用旧 snapshot 会产生错误结论。
- 目标环境采集失败时继续分析，会把“无法确认”伪装成可用或不可用。

### 4. 记录本次快照引用

依赖分析运行 summary 和 artifact JSON 应记录：
- `sourceSnapshotId`
- `targetSnapshotId`
- `sourceSnapshotCollectedAt`
- `targetSnapshotCollectedAt`
- `environmentRefresh=true`

如果后续数据库字段需要更强查询能力，可以新增显式字段；MVP 可先写入 artifact 和 run summary，避免扩大 schema。

### 5. E2E 用 stale snapshot 验证正确性

E2E 应准备一个目标环境旧 snapshot 中包含某工具、实时环境删除该工具但软件源仍可用的场景。重新运行依赖分析后，结果必须不再返回旧的 `TARGET_INSTALLED`，而应根据新采集结果返回 `REPO_AVAILABLE` 或其他实时证据状态。

## Risks / Trade-offs

- 依赖分析耗时增加 -> 在任务进度中明确展示环境刷新阶段，并复用已有采集超时配置。
- SSH 或包管理器短暂失败会导致依赖分析失败 -> 错误摘要中明确是 source 还是 target 刷新失败，用户可修复环境后重试。
- 内部调用环境采集可能增加模块耦合 -> 通过抽取小型 runtime/service 接口隔离，避免 controller/service 互相调用。
- 目标仓库刷新耗时较长 -> 默认优先正确性；后续可再设计高级缓存或显式跳过开关。
