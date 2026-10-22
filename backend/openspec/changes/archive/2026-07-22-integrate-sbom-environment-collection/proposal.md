## Why

当前 SBOM 分析要求前端先调用环境采集接口并传入源/目标快照 ID，这把后端内部运行顺序暴露给了前端，也容易出现用户选择旧快照或漏采集导致分析结果不可信的问题。SBOM 分析应作为一个完整的后端长任务：任务创建后由 worker 先采集环境，再基于本轮快照执行分析。

## What Changes

- **BREAKING**：`POST /api/projects/{projectId}/sbom-analyses` 不再要求 `sourceSnapshotId` 和 `targetSnapshotId`，前端只提交源环境和目标环境。
- SBOM 分析选项由后端固定为默认全量分析，不向前端暴露采集范围或仓库策略参数。
- SBOM worker 在同一个 `SBOM_ANALYSIS` 任务中依次执行源环境采集、目标环境采集和 SBOM analyzer 调用。
- `sbom_runs` 创建时允许暂未绑定快照，worker 采集成功后回填 `sourceSnapshotId` 和 `targetSnapshotId`。
- SBOM 任务事件和运行摘要需要表达当前阶段，包括源环境采集、目标环境采集、分析器执行和结果导入。
- `collection-detail` 需要支持采集中、采集失败或快照尚未生成时的响应语义。
- 保留独立环境采集 API 用于调试、兼容和非 SBOM 场景，但 SBOM 页面不再依赖前端主动调用该接口。
- 补充测试覆盖正常流程、采集失败、分析失败、取消、权限和空快照边界场景。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `backend-api-design`：调整 SBOM 分析创建 API，不再要求前端传入快照 ID，并明确采集详情在快照未生成时的返回语义。
- `sbom-analysis-runtime`：调整 SBOM worker 运行流程，由 worker 内部完成环境采集并回填快照后再调用 analyzer。
- `project-source-environment`：明确环境采集能力可作为 SBOM runtime 的内部步骤复用，且仍需保持脱敏、组件清单和仓库证据语义。

## Impact

- 后端 API DTO、校验逻辑和 API 文档。
- `sbom_runs` 数据库结构、jOOQ 生成代码和 Liquibase 迁移。
- SBOM worker、环境采集 runtime 复用接口、任务进度事件和失败摘要。
- SBOM 查询接口对未生成快照状态的兼容处理。
- Java 单元测试、API E2E 测试和真实联通验证脚本。
