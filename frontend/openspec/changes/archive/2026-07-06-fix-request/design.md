## Context

后端已经实现基础 request/auth 契约，前端应以当前后端代码为准，而不是继续沿用旧 token 模型或未落地的 `success/data/error` 包络。

当前后端已实现：

- `ApiResponse<T>`：`data`、`traceId`、`timestamp`
- `ApiErrorResponse`：`code`、`message`、`details`、`traceId`、`timestamp`
- `PageResponse<T>`：`items`、`page`、`pageSize`、`total`、`hasMore`
- `GET /api/auth/csrf`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/change-password`
- `POST /api/auth/logout`

当前前端仍保存 `token`、注入 `Authorization: Bearer ...`，并按 `success/error` 响应包络解包。登录页也期望 `login()` 返回 `{ token, user }`。这些都和后端当前 Cookie Session + CSRF 模型不一致。

这造成两个问题：

- 真实后端响应会被 request interceptor 误判。
- 登录成功后前端仍寻找不存在的 token。
- 路由守卫依赖本地 token，不能校验真实 `RVPORT_SESSION`。
- 非 GET 请求缺少 CSRF token 注入。

## Goals / Non-Goals

**Goals:**

- 将前端通用响应类型对齐当前后端 `ApiResponse` 和 `ApiErrorResponse`。
- 保持 request interceptor 对业务调用方返回已解包 `data`。
- 让业务 API 方法使用 `request.get<T>()`、`request.post<T>()` 这类直接类型。
- 让 request client 使用 Cookie Session，并为需要 CSRF 的请求注入后端 CSRF token。
- 将 auth 类型对齐后端 `LoginResponse`、`UserResponse` 和 `CsrfTokenResponse`。
- 将 auth store 从 token 改为 user/session 状态。
- 通过 `/api/auth/me` 校验真实 session，并缓存短时间内的校验结果，复用并发校验请求。
- 保持 401 清理 auth state 并跳转登录页。

**Non-Goals:**

- 不新增后端 API 端点。
- 不调整页面 UI 或路由行为。
- 不接入 admin users、tasks、SSE 或真实项目列表。
- 不调整项目列表 API 或 project mock。
- 不实现 roles/permissions 权限系统。

## Decisions

### 1. 前端类型以后端当前响应包络为准

`src/types/index.ts` 中定义：

- `ApiResponse<T>`：包含 `data`、`traceId`、`timestamp`。
- `ApiErrorResponse`：包含 `code`、`message`、`details`、`traceId`、`timestamp`。
- `PageResponse<T>`：包含 `items`、`page`、`pageSize`、`total`、`hasMore`。

`User` 类型对齐后端 `UserResponse`：`id` 为 UUID 字符串，不包含 `roles`，包含 `isSuperAdmin`、`mustChangePassword`、`status`、登录和创建更新时间字段。

### 2. 使用 typed request wrapper 包装 Axios

Axios 原生泛型默认返回 `AxiosResponse<T>`，即使 response interceptor 在运行时返回 `data`，TypeScript 仍然不会自动理解这个解包行为。

因此保留内部 Axios instance，但导出一个项目自定义 request object：

- `request.get<T>(url, config?) => Promise<T>`
- `request.post<T>(url, data?, config?) => Promise<T>`
- `request.put<T>(url, data?, config?) => Promise<T>`
- `request.patch<T>(url, data?, config?) => Promise<T>`
- `request.delete<T>(url, config?) => Promise<T>`

这样业务 API 不需要再接触 Axios 的第二泛型参数。

### 3. 响应拦截器按后端当前包络解包和统一错误

response interceptor 判断：

- 成功响应：返回 `response.data.data`
- 后端错误响应：Toast 展示顶层 `message`，并 reject
- HTTP 401：清理 auth store，并跳转 `/login`
- HTTP 403：可重新拉取 `/api/auth/me` 刷新用户状态，再展示无权限消息
- 网络或非包络错误：使用 Axios error message

### 4. Cookie Session 和 CSRF

后端使用 `RVPORT_SESSION` HttpOnly Cookie，不返回 Bearer token。

request client 应：

- 设置 `withCredentials: true`，使浏览器携带后端 session cookie。
- 不再从 auth store 读取 token，也不再注入 `Authorization` header。
- 通过 `GET /api/auth/csrf` 获取 `CsrfTokenResponse`。
- 对 `POST`、`PUT`、`PATCH`、`DELETE` 等非安全方法注入 CSRF header。
- 复用进行中的 CSRF 获取请求，避免并发请求重复拉 token。
- 在 CSRF 失效导致请求失败时允许后续请求重新获取 token。

### 5. Auth store 负责 session 状态而不是 token

Zustand auth store 保存：

- `user`
- 最近一次 session 校验时间
- 可复用的进行中 session 校验 promise

它不保存 token。

`ensureSession()` 行为：

- 如果已有进行中 `/api/auth/me` 校验，复用该 promise。
- 如果最近一次校验仍在 TTL 内，直接返回当前 user。
- 否则调用 `GET /api/auth/me`。
- 成功时保存 user 和校验时间。
- 401 时清空 user 并让路由进入登录页。

TTL 只用于减少重复 `/me` 请求，不作为安全边界。后端 API 鉴权仍是权威；任何 401 都必须清理前端 auth state。

### 6. 路由守卫使用 `/me` 完成真实 session 校验

`requireAuth` 应通过 `ensureSession()` 校验 Cookie Session。认证失败时跳转 `/login`。

`requireGuest` 应通过 `ensureSession()` 判断当前会话是否已登录。已登录时跳转 `/home`；未登录时允许访问登录页。

这样刷新页面、多 tab 恢复、session 过期和用户状态变化都能被真实后端校验覆盖，而不是只依赖本地持久化状态。

## Risks / Trade-offs

- [Risk] `/api/auth/me` 在路由切换中被频繁调用。→ 使用短 TTL 与进行中 promise 复用，避免每次 route loader 无条件请求。
- [Risk] 前端本地 user 可能在 TTL 内短暂过期。→ 后端每个 API 仍权威鉴权，401/403 会触发清理或刷新。
- [Risk] CSRF token 获取与业务请求并发时可能重复。→ request client 复用进行中的 CSRF token promise。
- [Risk] Axios wrapper 只暴露常用 HTTP 方法，少数高级 Axios 能力不再直接暴露。→ 当前项目只需要常规 REST 方法；需要上传/下载时再扩展 wrapper。
- [Risk] 项目列表 mock 仍可能使用旧开发期契约。→ 本 change 不调整项目列表；真实项目 API 尚未由后端实现，留给后续业务 change。

## Migration Plan

1. 更新 `src/types/index.ts` 的 API、错误、分页和用户类型。
2. 重构 `src/api/request.ts`，保留 Axios instance，导出 typed request wrapper，并支持 Cookie Session 与 CSRF。
3. 更新 `src/api/auth.ts`，对齐 `csrf`、`login`、`logout`、`me` 和 `change-password`。
4. 更新 `src/store/authStore.ts`，移除 token，增加 `ensureSession()`、session 校验 TTL 和并发复用。
5. 更新 `src/router/guards.ts` 和登录页，使路由与登录流程使用 Cookie Session。
6. 运行 `pnpm format:check`、`pnpm lint`、`pnpm typecheck` 和 `openspec validate fix-request`。
