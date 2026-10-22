## Why

现有 SBOM 分析以 x86 与 RISC-V 两个操作系统环境的全量组件差异为核心，容易把发行版、默认包和基础运行时差异放大，导致分析目标从“软件迁移”发散为“操作系统迁移”。需要改为基于当前源码在 x86 源环境中的真实构建事实提取依赖，再检查 RISC-V 目标环境是否能满足这些依赖，使分析范围与代码强绑定并保持收敛。

## What Changes

- 将现有面向前端主流程的 SBOM 分析节点、`SBOM_ANALYSIS` 任务语义和 `/sbom-analyses` 主流程 API 标记为 deprecated；旧接口和旧数据保留兼容，不作为新流程默认入口。
- 新增构建事实驱动的依赖分析节点：依赖分析消费 x86 构建命令、构建日志、构建产物和可选测试事实，并查询 RISC-V 目标环境的已安装、仓库、provides/whatprovides、pkg-config、header 和工具能力。
- 构建验证保持默认双环境运行不变，但新增 `SOURCE_ONLY` 构建范围，用于依赖分析前置的 x86 构建；不传时仍默认 `BOTH`。
- 源码部署继续作为构建验证 runtime 的内部能力，不作为独立前端节点暴露；本次构建范围决定部署到 source、target 或双环境。
- 依赖分析不依赖 RISC-V 构建或测试失败证据；RISC-V 构建验证仍在后续正式构建验证节点双环境运行。
- 新流程中的迁移输入、报告、归档和 E2E 使用 `DEPENDENCY_RESULT` 或等效依赖分析结果来源；历史 `SBOM_RESULT` 保留兼容和历史查询能力。
- 保留可复用的底层能力：远端环境能力采集、包管理器探测、仓库元数据刷新、provides/whatprovides、ELF/SONAME、owner package、工具版本识别，但其输入来源改为 x86 构建事实而不是两个 OS 全量差异。

## Capabilities

### New Capabilities

- `dependency-analysis-runtime`: 定义构建事实驱动的依赖分析任务、输入来源、目标环境能力匹配、结果持久化、报告制品和查询 API。

### Modified Capabilities

- `sbom-analysis-runtime`: 将旧 SBOM 主流程标记为 deprecated；保留旧接口、旧任务和旧数据兼容，不再作为新流程默认节点。
- `build-validation-runtime`: 增加构建范围 `SOURCE_ONLY|BOTH`，默认 `BOTH`；`SOURCE_ONLY` 用于依赖分析前置 x86 构建。
- `backend-api-design`: 将 SBOM 分析 API 标记为 deprecated，新增依赖分析 API 和构建范围参数说明。
- `task-runtime`: 增加 `DEPENDENCY_ANALYSIS` 任务类型；`SBOM_ANALYSIS` 保留为 deprecated 历史任务类型。
- `migration-input-merge`: 新流程新增 `DEPENDENCY_RESULT` 来源并按源码版本绑定依赖分析结果；历史 `SBOM_RESULT` 保留兼容。
- `migration-report-runtime`: 新报告中的依赖替代性说明优先来自依赖分析结果；历史报告继续支持 SBOM 输入快照。
- `project-runtime-environment-selection`: 远程运行环境仍为 source/target 双环境，但依赖分析只要求 source 构建事实和 target 能力查询。
- `api-e2e-test-suite`: 新增依赖分析 E2E 覆盖，验证前置 x86 构建、依赖结果查询、迁移输入导入和清理；SBOM E2E 可保留为 deprecated 兼容覆盖。
- `project-archive-runtime`: 新流程归档候选增加依赖分析报告和明细制品；历史 SBOM 归档候选保留兼容。

## Impact

- API：新增 `/api/projects/{projectId}/dependency-analyses` 及详情、结果列表、制品下载等接口；构建创建接口增加可选 `buildScope`；SBOM API 标记 deprecated。
- 数据库：新增依赖分析运行表、结果明细表和 artifact 关联；旧 `sbom_*` 表保留历史兼容，不作为新依赖分析写入目标。
- Worker：新增 `DEPENDENCY_ANALYSIS` handler；构建 handler 支持 `SOURCE_ONLY`。
- 工具：`tools/sbom-analyzer` 需要重命名、替换或新建 `tools/dependency-analyzer`，输入契约改为构建事实 + RISC-V 目标能力。
- 文档/E2E：中文 API 文档、覆盖矩阵、真实环境验证脚本和 OpenSpec specs 需要同步更新。
