## 1. 响应类型

- [x] 1.1 将 `src/types/index.ts` 中的 `ApiResponse<T>` 改为后端当前 `data/traceId/timestamp` 成功包络。
- [x] 1.2 将 `ApiErrorResponse` 改为后端当前顶层 `code/message/details/traceId/timestamp` 错误包络。
- [x] 1.3 将分页类型改为 `PageResponse<T>`，字段为 `items/page/pageSize/total/hasMore`。
- [x] 1.4 将 `User` 对齐后端 `UserResponse`，使用 UUID 字符串、`isSuperAdmin`、`mustChangePassword` 和 `status`，移除 `roles` 与 token 相关假设。

## 2. Request Client

- [x] 2.1 重构 `src/api/request.ts`，保留内部 Axios instance，并设置 Cookie Session 所需的 credentials 行为。
- [x] 2.2 移除 Bearer token 请求拦截逻辑。
- [x] 2.3 在 response interceptor 中按后端当前成功包络解包 `response.data.data`。
- [x] 2.4 在 response interceptor 中按后端当前错误包络展示顶层 `message` 并 reject。
- [x] 2.5 保留 HTTP 401 时清理 auth state 并跳转 `/login` 的行为。
- [x] 2.6 支持 `GET /api/auth/csrf` 并为 `POST/PUT/PATCH/DELETE` 注入 CSRF header。
- [x] 2.7 复用进行中的 CSRF token 请求，避免并发 unsafe 请求重复拉取 token。
- [x] 2.8 导出 typed request wrapper，使业务 API 可使用 `request.get<T>()`、`request.post<T>()` 等返回 `Promise<T>`。

## 3. Auth API 与状态

- [x] 3.1 将 `src/api/auth.ts` 对齐后端 `csrf/login/me/change-password/logout` 接口。
- [x] 3.2 将 `LoginResponse` 改为 `{ user }`，不再包含 token。
- [x] 3.3 将 `logout` 返回类型对齐 `{ loggedOut: boolean }`。
- [x] 3.4 更新 `src/store/authStore.ts`，移除 token 状态，保存 user 与 session 检查状态。
- [x] 3.5 在 auth store 中提供 `ensureSession()`，通过 `/api/auth/me` 校验 session。
- [x] 3.6 `ensureSession()` 复用进行中的 `/me` 请求，并使用短 TTL 避免 route 切换时无条件重复请求。

## 4. 路由与登录流程

- [x] 4.1 更新登录页，登录成功后保存返回的 user，不再保存 token。
- [x] 4.2 更新 `requireAuth`，通过 `ensureSession()` 校验 Cookie Session。
- [x] 4.3 更新 `requireGuest`，通过 `ensureSession()` 将已登录用户导向 `/home`。
- [x] 4.4 确认 session 校验失败时清理 user 并进入登录页。

## 5. 范围控制

- [x] 5.1 不修改 `src/api/project.ts`、项目列表 mock 或项目列表类型。
- [x] 5.2 不新增 admin users、tasks、SSE 等业务 API 类型。
- [x] 5.3 不修改后端代码。

## 6. 验证

- [x] 6.1 运行 `pnpm format:check`。
- [x] 6.2 运行 `pnpm lint`。
- [x] 6.3 运行 `pnpm typecheck`。
- [x] 6.4 运行 `openspec validate fix-request`。
- [x] 6.5 不运行 `pnpm build`，除非实现过程中触及构建配置或依赖。
