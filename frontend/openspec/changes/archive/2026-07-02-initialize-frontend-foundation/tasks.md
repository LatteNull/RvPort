## 1. 工具链与项目配置

- [x] 1.1 确认 `frontend/` 使用 pnpm package，并提供 dev、build、preview、lint、format、format check、typecheck 和 prepare 脚本。
- [x] 1.2 添加并锁定 React、TypeScript、Vite、Semi UI、React Router、TanStack Query、Zustand 和 Axios 依赖。
- [x] 1.3 添加并配置 ESLint、Prettier、Husky、Sass、vite-plugin-mock 和 import sort 相关开发依赖。
- [x] 1.4 配置 Vite、TypeScript 和 `@` 到 `src` 的路径别名。
- [x] 1.5 配置编辑器保存时执行 ESLint auto-fix，并避免内置 organize imports 与项目 import sort 规则冲突。

## 2. 应用入口与路由基础

- [x] 2.1 建立 React 应用入口，并在 Vite HTML root 上渲染应用。
- [x] 2.2 在 App 中接入 TanStack Query Provider 和 React Router Provider。
- [x] 2.3 建立 `src/router/` 目录，维护 router 实例、路由表和权限 loader。
- [x] 2.4 建立最小 `/login` 和 `/home` 路由，根路径 `/` 重定向到 `/home`。
- [x] 2.5 使用 loader 实现未登录访问受保护路由时跳转 `/login`、已登录访问 `/login` 时跳转 `/home`。
- [x] 2.6 保持 `/login` 静态引入，允许 `/home` 和后续较大业务页面使用 lazy。
- [x] 2.7 建立最小 layout，并通过 `Outlet` 渲染子路由。

## 3. 状态、请求与 mock 边界

- [x] 3.1 建立 Zustand auth store，保存 token、user 和 logout 行为。
- [x] 3.2 建立 Axios request client，统一处理 baseURL、timeout、认证 header、响应包络、错误提示和 401 处理。
- [x] 3.3 建立认证 API 边界，覆盖 login、logout 和获取当前用户。
- [x] 3.4 配置 `vite-plugin-mock`，仅在 Vite serve 模式启用开发期 mock API。
- [x] 3.5 使用 TanStack Query 作为服务端状态标准，不在页面中用 `useEffect + useState` 维护接口数据生命周期。

## 4. 样式与 UI 基础

- [x] 4.1 接入 Semi UI 和 React 19 adapter。
- [x] 4.2 建立 `src/styles/`，包含 reset、global、variables、mixins、animation 和 Semi CSS Variables 覆盖文件。
- [x] 4.3 使用 CSS Variables 覆盖 Semi 基础语义色；不接入 `@semi-bot/semi-theme-rvport` 或其他 Semi DSM 主题包。
- [x] 4.4 页面和组件样式使用 `*.module.scss`，全局样式只承载 reset、字体、变量和通用工具类。
- [x] 4.5 确认全局 reset 不会覆盖 Semi 组件内部 padding、margin 等基础样式。

## 5. 最小页面与范围控制

- [x] 5.1 建立最小 Login 页面，用于验证登录接口、认证状态写入和跳转 `/home`。
- [x] 5.2 建立最小 Home 页面，用于验证受保护路由和 layout 渲染。
- [x] 5.3 移除或避免纳入项目列表卡片、新建项目弹窗、项目领域模型、项目 API 和项目 mock 数据。
- [x] 5.4 将项目列表、迁移流水线、扫描、构建、测试等业务功能留给后续独立 change。

## 6. 验证

- [x] 6.1 运行 `pnpm format:check`。
- [x] 6.2 运行 `pnpm lint`。
- [x] 6.3 运行 `pnpm typecheck`。
- [x] 6.4 视需要运行 `pnpm build`，确认 Vite 生产构建可用。

## 7. 基础质量收尾

- [x] 7.1 合并重复 API 响应类型，只保留当前 request client 使用的 `code/data/message` 包络。
- [x] 7.2 移除基础页面样式中的 `!important`，避免给后续组件样式留下不良先例。
- [x] 7.3 将全局 reset 收敛为 minimal reset，降低覆盖 Semi 组件内部样式的风险。
- [x] 7.4 重新运行格式、lint、类型检查和构建验证。
