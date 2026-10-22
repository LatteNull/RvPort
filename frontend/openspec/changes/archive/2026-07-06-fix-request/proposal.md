## Why

后端已经实现通用 `ApiResponse`、`ApiErrorResponse` 和基础认证接口。当前前端 request client、auth store 和路由守卫仍按旧的 Bearer token 与 `success/data/error` 包络建模，和真实后端契约不一致。

已实现后端契约为：

- 成功响应：`data/traceId/timestamp`
- 错误响应：`code/message/details/traceId/timestamp`
- 登录态：`RVPORT_SESSION` HttpOnly Cookie
- CSRF：`GET /api/auth/csrf` 返回 header 名称和 token
- 当前用户：`GET /api/auth/me` 是 session 权威校验入口

## What Changes

- 将前端通用 API 响应类型调整为后端当前 `data/traceId/timestamp` 成功包络。
- 将前端错误类型调整为后端当前 `code/message/details/traceId/timestamp` 顶层错误包络。
- 调整 `src/api/request.ts` 的响应解包、错误处理、Cookie Session 和 CSRF 注入。
- 为 Axios 实例保留 typed request wrapper，让业务 API 写成 `request.get<T>(...)`、`request.post<T>(...)`。
- 将 auth 基础类型对齐后端 `LoginResponse`、`UserResponse` 和 `CsrfTokenResponse`。
- 将 auth store 从 token 状态改为 user/session 状态，并提供复用并发请求和短 TTL 的 session 校验能力。
- 将路由守卫改为通过 `/api/auth/me` 校验 Cookie Session，同时避免每次路由切换无条件请求 `/me`。
- 不新增业务 API 类型，不接入 admin users、tasks、SSE 或真实项目列表。

## Capabilities

### New Capabilities

- `request-client`: 覆盖前端 HTTP request client 的响应包络、错误处理、类型解包、Cookie Session 和 CSRF 行为。

### Modified Capabilities

- `frontend-application-foundation`: 登录、登出、获取当前用户和路由守卫对齐后端 Cookie Session 认证模型。

## Impact

- 影响 `src/api/request.ts`、`src/types/index.ts`、`src/api/auth.ts`、`src/store/authStore.ts`、`src/router/guards.ts` 和登录页的 auth 调用。
- 会让所有业务 API 方法使用更直接的返回类型，例如 `request.get<ProjectListItem[]>('/projects')`。
- 不修改后端代码。
- 不修改 `src/api/project.ts`、项目列表 mock、admin users、tasks 或 SSE。
- 不新增运行时依赖，不运行默认 build。
