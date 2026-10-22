## Context

RvPort-Frontend 位于 monorepo 的 `frontend/` 目录下，前端 OpenSpec 也以该目录为边界。基础架构阶段需要先固定工程工具、运行入口、路由、数据请求、状态、样式和质量工具，避免后续业务页面各自引入不一致的模式。

当前讨论明确：本变更只初始化前端工程基础，不包含项目列表卡片、新建项目、项目模型或迁移流水线业务。

## Goals / Non-Goals

**Goals:**

- 使用 pnpm、React、TypeScript 和 Vite 建立可运行前端应用。
- 集成 Semi UI、React Router、TanStack Query、Zustand 和 Axios。
- 建立 `src/` 下清晰的工程边界：`layouts/`、`router/`、`pages/`、`api/`、`store/`、`styles/`、`types/`。
- 提供最小 `/login` 与 `/home` 路由，用于验证应用入口、认证守卫和路由布局。
- 建立开发期 mock API 边界。
- 建立 SCSS、CSS Modules 和 Semi CSS Variables 的样式策略。
- 建立格式化、lint、import sort、pre-commit 和保存自动修复能力。

**Non-Goals:**

- 不实现项目列表卡片、新建项目弹窗、项目 API、项目 mock 或项目领域模型。
- 不实现迁移流水线、扫描、构建、测试等业务页面。
- 不实现 SSE 或任务事件能力。
- 不接入 `@semi-bot/semi-theme-rvport` 或其他 Semi DSM 主题包。
- 不引入部署、CI 或后端服务约束。

## Decisions

### Decision: 前端 OpenSpec 以 `frontend/` 为边界

RvPort 是 monorepo，前端基础架构只影响 `frontend/`。OpenSpec change 应创建在 `frontend/openspec/changes/` 下，避免根目录 OpenSpec 同时承载其他包的决策。

替代方案是在 monorepo 根目录统一维护 OpenSpec；该方案更适合跨前后端协议或部署编排，不适合这条纯前端工程基础 change。

### Decision: React Query 管理服务端状态，Zustand 管理本地状态

接口数据、列表、详情和 mutation 由 TanStack Query 管理。认证 token、用户信息和其他前端本地状态由 Zustand 管理。页面不应使用 `useEffect + useState` 直接维护服务端数据缓存。

这样可以让请求生命周期、缓存、重试和刷新策略集中在 React Query，而不把异步状态分散到页面组件里。

### Decision: 路由独立成目录并使用 loader 做权限控制

`src/router/` 维护 router 实例、路由表和权限 loader。`/login` 使用静态引入，避免首屏登录额外等待 lazy chunk；`/home` 和后续业务页面可按页面大小使用 lazy。

认证访问控制通过 React Router loader 读取 `useAuthStore.getState()`，未登录访问受保护路由时重定向到 `/login`，已登录访问 `/login` 时重定向到 `/home`。

### Decision: API 边界由 Axios request client 统一处理

`src/api/request.ts` 负责 `baseURL`、timeout、认证 header、响应包络、错误提示和 401 退出登录。业务 API 文件只描述资源操作，不重复处理通用请求逻辑。

基础阶段只需要认证相关 API。项目、任务、流水线等业务 API 应在后续业务 change 中引入。

### Decision: 基础阶段只用 CSS Variables 覆盖 Semi 主题色

基础阶段不接入 Semi DSM 主题包，也不使用 `@semi-bot/semi-theme-rvport`。Semi 主色、链接色、focus 色等语义色通过全局 CSS Variables 覆盖。

若后续需要系统性修改 Semi 组件尺寸、间距、字体、圆角或组件级 SCSS token，再单独提出主题 change，评估是否使用 `@douyinfe/semi-vite-plugin` 的 theme/include 能力或 DSM 主题包。

### Decision: 页面样式使用 CSS Modules，全局样式保持少量且明确

全局样式只放 reset、基础字体、CSS variables 和通用工具类。页面和组件样式使用 `*.module.scss`，避免选择器泄漏。业务 CSS Modules 不应依赖 `!important` 覆盖组件库样式；优先使用主题变量、组件 props 或局部语义 class。

### Decision: Home 是最小验证页，不承载业务项目列表

基础架构需要一个 `/home` 证明路由、layout、认证和 Provider 闭合，但该页面只保留最小内容。项目列表卡片、新建项目弹窗、项目领域模型和项目 mock 都属于后续业务 change。

### Decision: import 顺序由 ESLint 自动修复

使用 `eslint-plugin-simple-import-sort` 管理 import/export 顺序，VS Code/Cursor 保存时执行 ESLint fix，并禁用编辑器内置 organize imports，避免排序规则冲突。

## Risks / Trade-offs

- 最新依赖版本行为变化 → 使用 `pnpm-lock.yaml` 固化实际安装结果，并通过 format/lint/typecheck 验证。
- 只用 CSS Variables 覆盖主题能力有限 → 后续复杂主题需求独立建 change，不在基础架构中提前引入 DSM 主题包复杂度。
- mock API 与真实 API 契约可能偏离 → 基础阶段只保留 mock 边界，真实业务接口在对应业务 change 中定义。
- 登录状态保存在本地 store → 仅作为前端权限闭环基础，真实认证策略后续可单独调整。

## Migration Plan

1. 建立前端 package、依赖、脚本和 Vite/TypeScript 配置。
2. 建立 `src/` 工程目录、应用入口、Provider、router、layout、login/home 最小页面。
3. 建立 Axios request client、认证 store、认证 mock API 和样式基础。
4. 配置 ESLint、Prettier、import sort、Husky 和编辑器保存修复。
5. 运行 `pnpm format:check`、`pnpm lint`、`pnpm typecheck`，必要时运行 `pnpm build`。

## Open Questions

- 真实认证接口是否沿用当前 `/api/auth/login`、`/api/auth/logout`、`/api/auth/me` 路径。
- 后续是否需要将 OpenSpec `project.md` 补充为前端工程长期约定。
