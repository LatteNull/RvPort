## Why

`assets` 启动的六项并行分析中，SBOM 分析尚无专属阶段 Drawer，用户无法查看依赖替代结论、选择需要纳入迁移输入的组件或重新执行分析。

## What Changes

- 新增 SBOM 分析专属 Drawer，展示状态、替代性统计和组件替代结果表。
- 将结果选择、全选与“加入迁移输入”作为表格级操作；将“重新分析”保留为阶段级 Footer 操作。
- 提供执行/重新分析配置，包含 x86 源环境、RISC-V 目标环境、软件源策略、采集范围和分析选项。
- 增加 SBOM 任务、组件结果和加入迁移输入的 API 类型、领域边界和开发 mock；使用服务端任务状态刷新 workflow。

## Capabilities

### New Capabilities

- `sbom-analysis`: SBOM 替代性分析的执行、结果查看、结果选择与迁移输入提交。

### Modified Capabilities

- `project-pipeline-workbench`: 将 SBOM 阶段状态、任务结果和已确认的迁移输入操作映射到固定工作流。

## Impact

- 影响 `StageDrawer` 注册、SBOM 专属组件、项目领域类型、`src/api/project.ts` 和开发 mock。
- 影响 workflow 状态和迁移输入的缓存刷新，不改变 React Flow 拓扑或节点布局。
- 不新增运行时依赖；使用现有 Ant Design、TanStack Query、SCSS Modules 与 Vite mock。
