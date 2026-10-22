## Why

项目列表页已经提供“进入流水线”的视觉入口，但当前交互只停留在 hover 展示，无法进入项目上下文。根据 `node-id=10-98` 截图和 MVP 页面结构，用户从项目列表进入项目后应落到项目流水线工作台，由工作台展示迁移流程节点、状态总览和阶段入口。

## What Changes

- 新增项目流水线工作台能力，提供 `/projects/:projectId` 项目工作台默认页。
- 将项目卡片的“进入流水线”点击行为定义为进入对应项目流水线工作台。
- 在项目流水线工作台加载项目概览聚合数据，并展示项目基本信息、风险和关键运行状态。
- 画布采用 React Flow（`@xyflow/react`），支持画布平移、缩放、悬浮联动和当前阶段聚焦；流水线节点、分组、连线和布局由前端固定维护，不由后端概览接口返回。
- 新增开发 mock，支持项目流水线工作台在 Vite serve 模式下读取概览数据和轮询式 workflow 状态快照。
- 不在本 change 中实现键盘进入、项目级 SSE、节点自由拖拽编排、流水线子阶段页面、报告页面或任务执行。

## Capabilities

### New Capabilities

- `project-pipeline-workbench`: 定义项目工作台默认页、流水线画布和项目概览聚合数据展示。

### Modified Capabilities

- `project-list-home`: 将项目卡片从仅有 hover 视觉入口，扩展为鼠标点击进入项目流水线工作台。

## Impact

- 影响前端路由、项目列表卡片点击处理、项目 API 类型和 mock。
- 新增 `src/pages/project-pipeline-workbench/` 页面模块。
- 新增或扩展 `src/api/project.ts` 中的项目概览读取 API。
- 新增运行时依赖 `@xyflow/react`；自动布局若进入本 change 实现，优先评估轻量 dagre/elkjs 集成。
