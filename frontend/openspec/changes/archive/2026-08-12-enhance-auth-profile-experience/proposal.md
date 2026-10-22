## Why

当前前端具备基础登录、会话恢复和强制修改密码能力，但登录页无法减少重复填写账号的成本，用户也缺少集中查看账户资料、更新显示名称和发起常规改密码的入口。后端已提供当前用户、更新显示名称和改密码接口，因此现在可以完善用户自助账户体验，而不改变 Cookie Session 安全边界。

## What Changes

- 登录页将账号输入字段标签和占位提示统一为“账号 / 请输入账号”，密码字段占位提示统一为“请输入密码”，并提供“记住账号”选项。
- “记住账号”仅在浏览器本地保存账号名，用于下次打开登录页时回填；不得保存密码、Cookie、token 或延长服务端会话。
- 新增受保护的 Settings 个人中心页面与 Header 用户菜单入口，集中展示当前用户账户资料。
- 个人中心允许用户编辑显示名称，并调用既有 `PATCH /api/auth/profile` 更新本地认证状态。
- 个人中心提供常规修改密码入口；强制修改密码的 `/settings/security/password` 路径与访问限制保持不变。
- 补齐相关 API 模块、Vite mock、路由、状态更新和测试覆盖。

## Capabilities

### New Capabilities

- `account-profile`: 已登录用户查看账户资料、编辑显示名称并在个人中心发起常规改密码。

### Modified Capabilities

- `incremental-api-integration`: 调整登录表单的账号记忆行为，并补充个人资料更新接口的前端消费契约。

## Impact

- 影响页面与路由：`src/pages/auth/login/`、新增 `src/pages/settings/profile/`、`src/router/routes.ts`、`src/layouts/MainLayout/`。
- 影响认证边界：`src/api/auth/`、`src/store/authStore.ts`、`mock/auth.ts` 及对应测试。
- 复用既有 Cookie Session、`GET /api/auth/me`、`PATCH /api/auth/profile` 和 `POST /api/auth/change-password`；不新增依赖，不修改后端 API 或会话时长。
