## 1. 路由与 API 边界

- [x] 1.1 在主布局下新增受认证保护的 `/projects/:projectId` 路由。
- [x] 1.2 将 `@xyflow/react` 作为 React Flow 运行时依赖加入前端，并在前端样式边界加载其样式表。
- [x] 1.3 定义项目流水线工作台 TypeScript 类型，覆盖项目标识、阶段、风险、状态摘要、流水线节点和流水线边。
- [x] 1.4 在项目 API 模块中基于共享 request client 新增 `getProjectOverview(projectId)`。

## 2. 项目列表入口

- [x] 2.1 为 `ProjectCard` 增加传给父组件的鼠标点击回调，不增加键盘激活。
- [x] 2.2 从 `/home` 的项目卡片导航到 `/projects/:projectId`。
- [x] 2.3 保留现有 hover 时的“进入流水线”视觉提示和报告文本行为。

## 3. 项目流水线工作台页面

- [x] 3.1 创建项目流水线工作台页面模块和 SCSS Module。
- [x] 3.2 使用 TanStack Query 加载概览数据，并渲染局部加载、错误和重试状态。
- [x] 3.3 按截图渲染顶部标题、返回操作、摘要卡片和底部操作区。
- [x] 3.4 使用自定义流水线阶段节点和连接边渲染 React Flow 画布。
- [x] 3.5 支持 React Flow 拖拽、平移、缩放、fitView 和鼠标选择节点，不增加键盘激活。
- [x] 3.6 将布局生成封装在小函数后面，使手动截图坐标后续可替换为 dagre/elkjs 自动布局。
- [x] 3.7 确保页面不创建 SSE 连接，也不启动长任务。

## 4. 开发 Mock

- [x] 4.1 为 `GET /api/projects/:projectId/overview` 增加 Vite mock handler。
- [x] 4.2 为已有 mock 项目返回成功的概览数据。
- [x] 4.3 为未知项目 ID 返回当前错误响应包络。
- [x] 4.4 为 `GET /api/projects/:projectId/workflow/status` 增加轮询式 workflow 状态 mock，返回阶段状态和动态边 ID。
- [x] 4.5 将 React Flow 画布改为由 overview 结构和 workflow 状态快照驱动，进行中边展示动画。

## 5. 验证

- [x] 5.1 运行 `openspec validate project-pipeline-workbench`。
- [x] 5.2 运行 `pnpm format:check`。
- [x] 5.3 运行 `pnpm lint`。
- [x] 5.4 运行 `pnpm typecheck`。

## 6. Workflow 画布优化收敛

- [x] 6.1 将 workflow 静态拓扑与运行态状态映射保持清晰边界，确保 overview 类型、API 和 mock 不返回节点、分组、边或布局坐标。
- [x] 6.2 确保 workflow 状态轮询只消费当前阶段、阶段状态和运行中边 ID；后端返回全量快照时，前端先做语义 diff，无变化不触发状态更新。
- [x] 6.3 将 React Flow 画布定位为固定流程浏览器：节点不可拖拽或重连，画布保留平移和缩放。
- [x] 6.4 初始化和状态切换时以当前进行中阶段为视觉中心，并使用明确的初始缩放比例，不以完整展示全量 workflow 为目标。
- [x] 6.5 使用稳定 edge className 和 SCSS hover 规则实现节点悬浮时相邻 source/target edges 动画，不在 hover 时改写 edges 数组。
- [x] 6.6 收敛节点、分组和连线的配置边界；必要时将阶段、分组、边和布局常量整理为独立拓扑配置，避免与渲染状态缓存混杂。
- [x] 6.7 复核源码扫描、源码修复和优化测试分组框边界，使其按 Figma workflow 原型包含正确节点且不遮挡关键连线或箭头。
