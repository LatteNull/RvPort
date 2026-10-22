## Why

当前 `/home` 仍是基础框架占位页，无法承载 MVP 中“项目列表页”的实际入口职责。根据 `public/首页@2x.png`、产品交互规格和 API 设计，首页需要展示用户可访问的迁移项目，并作为进入已有迁移流水线的入口。

## What Changes

- 将 `/home` 从基础占位页升级为项目列表页。
- 增加项目列表查询边界，使用 `GET /projects` 的开发期 mock 数据。
- 使用 TanStack Query 在首页加载项目列表，不使用 `useEffect + useState` 自行维护请求生命周期。
- 扩充开发期 mock 项目数据，用于验证多行卡片、页面滚动和最后一行布局。
- 增加项目卡片 UI，展示项目名称、源架构、目标架构、当前阶段、高风险数、最近扫描时间、最近构建状态和最近测试状态。
- 按 `public/首页@2x.png` 和 Figma 节点还原顶部标题区、新建按钮、卡片网格、风险角标、阶段条、状态字段和 hover/active 视觉。
- 在大屏宽度下控制首页内容最大宽度，保留 315px 固定卡片尺寸，降低右侧空白过多的问题。
- 新建项目弹窗、项目详情页、进入迁移流水线、查看报告跳转暂不实现，保留后续 change 扩展空间。
- 暂不引入 US18 多项目迁移状态看板、趋势、周报或全局指标。

## Capabilities

### New Capabilities

- `project-list-home`: 覆盖首页项目列表展示、项目卡片字段、项目列表 mock API、React Query 数据加载、设计图范围内的交互状态。

### Modified Capabilities

- `frontend-application-foundation`: 调整基础 Home 的范围约束；基础框架归档时要求 Home 不包含项目列表业务功能，本 change 开始由新的业务能力接管 `/home`。

## Impact

- 影响 `src/pages/home/` 首页实现和样式。
- 新增 `src/pages/home/components/ProjectCard/` 等首页局部组件。
- 新增或调整 `src/api/project.ts`、`src/types/project.ts` 和 `mock/project.ts`。
- 继续使用现有 Axios request client、React Query Provider、Vite mock、SCSS Modules 和 `@` 路径别名。
- 不新增运行时依赖，不改变登录、权限 loader、MainLayout 或路由结构。
