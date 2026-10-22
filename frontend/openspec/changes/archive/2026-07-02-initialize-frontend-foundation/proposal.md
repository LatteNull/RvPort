## Why

RvPort-Frontend 需要先形成稳定、可持续演进的前端工程基础，后续业务页面才能在统一的路由、数据、状态、样式和质量工具约束下推进。

本变更聚焦前端基础架构，不承载项目列表、迁移流水线等业务功能实现，避免工程约束和业务需求混在同一条 change 中。

## What Changes

- 建立 React、TypeScript、Vite 和 pnpm 驱动的前端工程基础。
- 配置 Semi UI、React Router、TanStack Query、Zustand 和 Axios 的基础集成。
- 建立源码目录边界：应用入口、layout、router、pages、api、store、styles、types 和 mock。
- 建立最小 `/login` 与 `/home` 路由闭环，并使用 React Router loader 实现认证访问控制。
- 使用 TanStack Query 作为服务端状态边界，使用 Zustand 作为认证和本地状态边界。
- 使用 Axios 封装统一 request client，处理 `/api` 前缀、认证 token、响应包络和错误反馈。
- 使用 `vite-plugin-mock` 提供开发期 mock API。
- 使用 SCSS、CSS Modules 和 CSS Variables 管理样式；基础阶段不接入 Semi DSM 主题包，只通过 CSS Variables 覆盖必要的 Semi 语义色。
- 配置 `@` 指向 `src` 的路径别名。
- 配置 ESLint、Prettier、import sort、Husky 和编辑器保存时自动修复。
- 提供最小 Login 和 Home 页面，仅用于验证应用入口、路由、认证和 Provider 是否闭合。

非目标：

- 不实现项目列表卡片。
- 不实现新建项目弹窗。
- 不定义项目领域模型、项目 API 或项目 mock 数据。
- 不实现迁移流水线、扫描、构建、测试等业务页面。
- 不实现 SSE 或任务事件能力。
- 不接入 `@semi-bot/semi-theme-rvport` 或其他 Semi DSM 主题包。
- 不处理部署、CI 或后端服务。

## Capabilities

### New Capabilities

- `frontend-application-foundation`: 定义 RvPort-Frontend 的初始工程基础，包括工具链、应用入口、路由、认证守卫、数据请求、状态管理、样式策略、mock 边界和质量门禁。

### Modified Capabilities

- 无。

## Impact

- 影响范围：`frontend/`。
- 新增或确认依赖：React、TypeScript、Vite、Semi UI、React Router、TanStack Query、Zustand、Axios、Sass、vite-plugin-mock、ESLint、Prettier、Husky 和 import sort。
- 后续业务功能应在该基础上通过独立 change 增量推进。
