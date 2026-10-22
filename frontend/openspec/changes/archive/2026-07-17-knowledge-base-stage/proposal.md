## Why

知识库扫描是源码制品导入后的核心分析入口，但当前工作台仅展示 `kb` 流程节点，尚未提供扫描配置、任务状态、Finding 结果、详情与迁移问题清单衔接能力。需要以与已有阶段 Drawer 一致的交互承载扫描全流程，并明确扫描结果的选择状态与持久业务状态。

## What Changes

- 新增知识库扫描阶段 Drawer：展示扫描任务状态、三项扫描概览和 Finding 结果表格。
- 在同一个 Drawer 内提供“新建扫描”配置视图和 Finding 详情视图，不在 Drawer 上叠加 Modal。
- 支持按全局扫描配置启动任务、查看运行/失败/空态、导出当前扫描报告。
- 支持全选或逐行选择 Finding，并将已选 Finding 加入迁移问题清单；结果状态仅展示“未加入”或“已加入”。
- 为工作台 `kb` 节点补充阶段详情入口与服务端状态映射。
- 统一阶段 Drawer 宽度：含主结果表格的阶段使用 `1100px`，信息或表单型阶段使用 `800px`。

## Capabilities

### New Capabilities

- `knowledge-base-scanning`: 知识库扫描任务、扫描配置、Finding 结果、详情、报告导出和迁移问题清单加入交互。

### Modified Capabilities

- `project-pipeline-workbench`: 工作台支持从 `kb` 节点打开知识库扫描阶段 Drawer，并将知识库扫描任务状态映射到固定 Workflow 节点。

## Impact

- 受影响页面：`src/pages/project-detail/StageDrawer/`、项目工作台 Workflow 节点点击逻辑。
- 受影响领域边界：`src/types/project.ts`、`src/api/project.ts`、`mock/project.ts` 及其测试 fixture。
- 复用现有 BaseDrawer、TanStack Query、Ant Design Table/Form/Empty/Popconfirm 和本地 Monaco 只读代码视图，不新增运行时依赖。
