## Context

当前 `/home` 已是项目列表页，项目卡片显示“进入流水线”hover 入口，但 `project-list-home` 规格明确把 pipeline navigation 留到后续 change。用户提供的 `node-id=10-98` 截图展示的是“项目流水线工作台”：顶部项目状态卡片、灰底流程画布、11 个迁移流程节点和底部操作区。产品文档中“项目概览页”的状态聚合语义仍然适用，但视觉和交互形态应按流水线工作台实现。

后端 API 设计已声明 `GET /api/projects/{projectId}/overview` 作为项目概览聚合数据接口，但当前前端只封装了 `/projects` 列表和创建接口。因此本 change 应先建立前端路由、React Flow 画布、API 边界和 mock 数据，避免把后续阶段详情页面、任务实时通道和真实任务执行混入首个入口 change。

## Goals / Non-Goals

**Goals:**

- 鼠标点击项目卡片后进入 `/projects/:projectId`。
- `/projects/:projectId` 作为项目工作台默认页，展示项目流水线工作台。
- 页面通过 TanStack Query 调用项目概览 API 边界，并提供加载、错误和空态。
- 使用 React Flow 渲染迁移流程画布，支持画布平移、缩放、悬浮联动和当前阶段聚焦。
- 按截图和 Figma workflow 原型展示顶部返回、标题、项目/风险/阶段/构建状态卡片、流程节点、分组框、连接边和底部操作按钮。
- 开发 mock 返回正式响应包络下的项目概览数据。
- 保留现有项目卡片 hover 视觉表现和 Ant Design/SCSS Modules 约定。

**Non-Goals:**

- 不支持键盘 Enter/Space 触发进入。
- 不建立或消费项目级 SSE。
- 不实现环境、源码、扫描、SBOM、问题清单、报告、构建、测试等子页面。
- 不触发任何长任务，不实现报告生成或“继续下一步”的真实跳转决策。
- 不要求后端在本 change 中实现项目概览 controller。
- 不把本页做成低代码流程编排器，不提供节点拖拽编排、新增、删除、重连、端口配置、复制粘贴或撤销重做。

## Decisions

### 路由使用 `/projects/:projectId`

项目流水线工作台需要项目上下文，且后续所有工作台页面都应共享 `projectId`。因此入口路由采用 `/projects/:projectId`，而不是无上下文的 `/pipeline`。

备选方案是 `/projects/:projectId/overview`。当前选择较短路径，是因为流水线工作台是项目默认页；后续子页面可扩展为 `/projects/:projectId/environments`、`/projects/:projectId/source` 等。

### 点击入口由 HomePage 负责导航

`ProjectCard` 保持展示组件定位，通过 `onOpen(project.id)` 之类的回调暴露点击事件；`HomePage` 使用 `useNavigate` 执行路由跳转。这样卡片不直接依赖 router，仍可在列表、搜索结果或其他项目集合视图中复用。

备选方案是在 `ProjectCard` 内直接调用 `useNavigate`。这会让展示组件和路由耦合更强，后续如果卡片需要出现在非路由上下文中，复用成本更高。

### 画布采用 React Flow

本页选择 React Flow（`@xyflow/react`）渲染流程画布。它适合 React 业务应用中的节点型 UI，能直接使用 React 自定义节点、React state、TanStack Query 数据和 Ant Design 周边控件，同时内置画布平移缩放、自定义节点、自定义边和节点事件。

备选方案是 AntV X6。X6 更适合低代码编排器或专业图编辑器，优势在复杂端口、连接桩、图元工具、复制粘贴、撤销重做、Stencil 和复杂连线路由。本 change 的目标是固定迁移流程的工作台，不是让用户自由建模流程，因此 React Flow 的模型更轻，和当前 React 技术栈集成成本更低。

### Workflow 拓扑由前端固定维护

后端不返回 workflow 节点、分组、连线和布局坐标。前端将 Figma workflow 原型中的阶段、分组、连线和坐标作为固定业务拓扑维护，并将后端 workflow 状态快照映射到这些固定节点和边上。

拓扑配置应和状态映射保持清晰边界：阶段、分组、边、坐标属于静态配置；阶段状态、当前阶段和运行中边属于后端状态。若后续需要自动布局，应作为可替换布局层接入，而不是要求后端返回 React Flow 节点结构。

### 项目概览先使用聚合 API 边界

页面新增 `getProjectOverview(projectId)`，目标路径对齐设计文档中的 `GET /api/projects/{projectId}/overview`。即使开发阶段由 mock 提供数据，也应保持 API 形状接近正式接口。

备选方案是复用 `ProjectListItem` 直接从列表传递数据。这样刷新详情页或直接打开 URL 时缺少数据来源，也无法承接后续 overview 聚合字段。

### Workflow 状态先使用轮询快照

项目级 SSE 是工作台实时任务状态的正确方向，但这次用户明确要求“sse 等会弄”。项目流水线工作台先通过 `GET /api/projects/{projectId}/workflow/status` 读取 workflow 状态快照，并以 30 秒轮询作为开发阶段替代方案。

状态接口只表达运行态，不表达拓扑：`currentStageId` 用于画布聚焦，`stages` 用于阶段状态渲染，`activeEdgeIds` 用于运行中边动画。若后端返回全量快照，前端在赋值前应做语义 diff；没有变化时不更新 state，避免轮询导致 React Flow 重绘。

### 画布交互以固定流程浏览为主

节点卡片不支持拖拽，避免用户误以为可以改变服务端流水线结构。画布仍支持平移和缩放，初始化不要求展示完整画布，而应以当前进行中阶段作为视觉中心，并使用明确的初始缩放比例。

节点悬浮时，应高亮或动画展示与该节点直接相连的 source/target edges。该效果不应通过 hover 时修改 `edges` 数组实现，而应通过稳定的 edge className 和画布上的 hover 状态属性交给 CSS 控制，减少 hover 触发的 React Flow 重绘。

## Risks / Trade-offs

- [Risk] 引入 React Flow 增加运行时依赖和 CSS 引入要求。 → Mitigation: 只引入 `@xyflow/react`，在页面或全局样式入口按官方要求加载 React Flow CSS，并把画布封装在项目工作台模块内。
- [Risk] 项目流水线工作台先用 mock，可能与后端最终字段不完全一致。 → Mitigation: 类型和 mock 字段以 `docs/design/01_API_DESIGN.md`、产品 OV 字段和截图中的流水线节点为准，保持快照聚合语义。
- [Risk] 不支持键盘进入会降低可访问性。 → Mitigation: 本 change 明确按用户要求排除键盘支持，后续可单独补交互增强。
- [Risk] 不接 SSE 时运行中状态不会实时刷新。 → Mitigation: 页面只声明快照读取能力，实时状态由后续 SSE change 补齐。

## Open Questions

- React Flow 的自动布局本 change 是否需要真实启用 dagre/elkjs，还是先使用截图坐标并保留布局函数边界？
- 节点点击后第一版是只选中节点，还是打开轻量详情抽屉？
