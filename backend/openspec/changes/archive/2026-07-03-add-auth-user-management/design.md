# add-auth-user-management 设计

## 设计目标

本变更的目标是实现一个窄而稳定的 MVP 认证与本地用户管理层：

- 登录态对浏览器友好，使用服务端 Session 和 HttpOnly Cookie。
- 用户权限只区分普通登录用户和超级管理员，不引入角色系统。
- `users` 表是用户事实来源，Redis Session 只保存登录态。
- 密码只保存 Argon2id 哈希，任何响应、日志和审计都不暴露明文密码。
- 强制改密是后端硬约束，不只依赖前端页面跳转。

## 模块结构

建议包结构：

```text
cn.rvport.backend.auth
  AuthController
  AuthService
  CurrentUserService
  LoginRequest
  ChangePasswordRequest
  CurrentUserResponse

cn.rvport.backend.user
  AdminUserController
  UserService
  UserRepository
  UserStatus
  UserSummaryResponse
  CreateUserRequest
  UpdateUserRequest
  ResetPasswordRequest

cn.rvport.backend.security
  RvPortUserPrincipal
  RvPortAuthenticationFilter 或 CurrentUserStatusFilter
  PasswordChangeRequiredFilter
  SuperAdminAuthorization

cn.rvport.backend.audit
  AuditLogService
```

总体关系：

```text
浏览器
  │  RVPORT_SESSION + X-XSRF-TOKEN
  ▼
Spring Security
  │
  ├─ AuthController ── AuthService ── UserRepository(jOOQ) ── users
  │                         │
  │                         └─ AuditLogService ────────────── audit_logs
  │
  └─ AdminUserController ── UserService ── UserRepository(jOOQ)
```

## 登录态与 Session

MVP 不使用 JWT。登录成功后：

1. 后端校验用户名、用户状态和密码。
2. 创建 Spring Security `Authentication`。
3. 将安全上下文写入服务端 session。
4. Spring Session 将 session 保存到 Redis。
5. 响应设置 `RVPORT_SESSION` Cookie。

Session principal 建议只保存必要身份快照：

```text
userId
username
displayName
email
isSuperAdmin
mustChangePassword
status
```

不要保存：

```text
passwordHash
initialPassword
newPassword
currentPassword
roles
permissions
projectMembers
```

## 当前用户刷新与禁用处理

Session 中的 principal 可能变旧，例如超级管理员禁用了某个已登录用户。因此受保护请求不应完全信任 session 快照。

建议增加一个请求级检查：

```text
已认证请求
  -> 根据 principal.userId 从 users 表读取当前状态
  -> 用户不存在或 status != ACTIVE 时拒绝访问
  -> 必要时刷新当前请求上下文中的用户快照
```

这样可以保证：

- 被禁用用户不能继续使用旧 session。
- `must_change_password` 的最新状态能被后端约束。
- `GET /api/auth/me` 返回数据库中的当前用户信息。

## 强制改密

当 `users.must_change_password = true` 时，用户已经登录，但账号处于受限状态。

允许访问：

```text
GET  /api/auth/me
GET  /api/auth/csrf
POST /api/auth/change-password
POST /api/auth/logout
```

拒绝访问：

```text
/api/admin/**
/api/projects/**
/api/tasks/**
其他业务 API
```

拒绝时建议返回：

```text
HTTP 403
code = PASSWORD_CHANGE_REQUIRED
```

这样即使前端路由失误，后端也不会允许首次登录默认密码用户访问业务功能。

## CSRF 方案

因为 MVP 使用 Session Cookie，浏览器会自动携带登录 Cookie，所以需要保留 CSRF 防护。

建议方案：

- 使用 Cookie 型 CSRF token，例如 `XSRF-TOKEN`。
- CSRF token cookie 允许前端 JavaScript 读取。
- 前端在状态变更请求中提交 `X-XSRF-TOKEN` header。
- 新增 `GET /api/auth/csrf`，用于应用启动或登录页初始化时获取 token。
- `RVPORT_SESSION` 继续保持 HttpOnly，前端不能读取。

安全边界：

- `RVPORT_SESSION` 是登录凭证，必须 HttpOnly。
- `XSRF-TOKEN` 不是登录凭证，可以被前端读取后回传。
- 不应为了省事全局关闭 CSRF。

## 密码策略

密码保存：

- 使用现有 `PasswordEncoder` 的 Argon2id 配置。
- 只保存 `password_hash`。
- 不记录明文密码。

密码校验：

- 登录校验 `password` 与 `password_hash`。
- 当前用户修改密码时必须校验 `currentPassword`。
- 超级管理员重置密码不需要旧密码，但必须写审计日志。

密码策略在 MVP 中要求适度复杂，但暂不要求特殊符号：

```text
长度 >= 8
至少包含 1 个大写字母
至少包含 1 个小写字母
至少包含 1 个数字
不得与用户名完全相同
```

后续可以扩展特殊符号、历史密码和失败次数锁定。

## 认证 API

### `POST /api/auth/login`

行为：

- 根据 `username` 查找用户。
- 用户不存在、密码错误、用户禁用时返回统一认证失败或禁用错误。
- 用户状态为 `ACTIVE` 且密码正确时创建 session。
- 更新 `last_login_at`。
- 写入登录审计。
- 返回当前用户信息。

响应不得包含：

```text
passwordHash
roles
permissions
projectMembers
```

### `POST /api/auth/logout`

行为：

- 清理当前 session。
- 写入退出审计。
- 返回空成功响应。

### `GET /api/auth/me`

行为：

- 未登录返回 `401`。
- 已登录时从数据库读取当前用户。
- 用户不存在或禁用时返回 `401` 或 `403`，并使当前 session 失效。
- 返回当前用户信息。

### `POST /api/auth/change-password`

行为：

- 校验当前用户仍为 `ACTIVE`。
- 校验 `currentPassword`。
- 校验 `newPassword` 策略。
- 保存新 Argon2id 哈希。
- 将 `must_change_password` 设置为 `false`。
- 写入改密审计。

## 超级管理员用户管理

超级管理员判断只来自 `users.is_super_admin = true`。

普通用户访问 `/api/admin/users/**` 时返回：

```text
HTTP 403
code = FORBIDDEN
```

### 用户列表

`GET /api/admin/users`

支持：

```text
page
pageSize
status
keyword
```

`keyword` 可匹配：

```text
username
display_name
email
```

建议默认排序：

```text
created_at desc
```

### 创建普通用户

`POST /api/admin/users`

允许字段：

```text
username
displayName
email
initialPassword
mustChangePassword
status
```

禁止字段：

```text
isSuperAdmin
passwordHash
roles
permissions
```

如果请求体显式传入 `isSuperAdmin`，即使值为 `false`，也建议返回 `VALIDATION_ERROR`。这样可以让 API 契约更清楚：超级管理员标记不是接口字段。

创建时：

- username 必须唯一。
- email 非空时必须唯一。
- initialPassword 必须哈希后保存。
- `mustChangePassword` 默认建议为 `true`。
- 写入创建用户审计，审计详情不得包含初始密码。

### 更新用户

`PATCH /api/admin/users/{userId}`

允许更新：

```text
displayName
email
status
```

不允许更新：

```text
username
passwordHash
isSuperAdmin
mustChangePassword
```

`mustChangePassword` 只能通过创建用户和重置密码设置，通过用户自己成功改密清除。

禁用用户时：

- 将 `status` 设置为 `DISABLED`。
- 不删除历史创建人、审计操作人或业务引用。
- 旧 session 在下一次受保护请求中被拒绝。

### 重置密码

`POST /api/admin/users/{userId}/reset-password`

行为：

- 校验目标用户存在。
- 保存新密码 Argon2id 哈希。
- 根据请求设置 `mustChangePassword`，默认建议为 `true`。
- 写入重置密码审计。
- 响应不返回明文密码。

### 删除用户

MVP 不做物理删除。配置页“删除”动作应映射为禁用用户：

```text
PATCH /api/admin/users/{userId}
{ "status": "DISABLED" }
```

这样历史任务、项目创建人、审计日志和运行记录仍可追溯。

## 审计

以下动作必须写审计：

```text
auth.login.success
auth.login.failed
auth.logout
auth.change_password
admin.user.create
admin.user.update
admin.user.disable
admin.user.reset_password
```

审计详情只记录脱敏信息，例如：

```json
{
  "targetUserId": "uuid",
  "username": "developer",
  "changedFields": ["displayName", "status"]
}
```

不得记录：

```text
password
initialPassword
newPassword
currentPassword
passwordHash
```

## 错误码

建议补齐或复用以下错误码：

| 错误码 | 场景 |
| --- | --- |
| `AUTH_REQUIRED` | 未登录或登录态失效 |
| `INVALID_CREDENTIALS` | 用户名或密码错误 |
| `USER_DISABLED` | 用户已禁用 |
| `PASSWORD_CHANGE_REQUIRED` | 用户必须先修改密码 |
| `CURRENT_PASSWORD_INVALID` | 当前密码不正确 |
| `PASSWORD_POLICY_FAILED` | 新密码不满足策略 |
| `FORBIDDEN` | 非超级管理员访问管理接口 |
| `USER_NOT_FOUND` | 用户不存在 |
| `USERNAME_EXISTS` | 用户名已存在 |
| `EMAIL_EXISTS` | 邮箱已存在 |
| `VALIDATION_ERROR` | 请求字段不合法 |

## 测试策略

普通 `mvn test` 不应要求开发者必须有正在运行的真实数据库、Redis 或 RabbitMQ。

建议测试分层：

- AuthService 单元测试：密码正确、密码错误、禁用用户、强制改密清除。
- UserService 单元测试：创建用户、拒绝 `isSuperAdmin`、更新字段限制、重置密码、禁用用户。
- Security/Filter 测试：未登录、普通用户访问管理接口、强制改密访问限制。
- Controller MockMvc 测试：响应包络、错误码、状态码和字段脱敏。
- Repository 可用集成测试或后续 Testcontainers 覆盖，但不作为本变更必须进入默认单元测试的前提。

apply 阶段可以临时执行真实连通性测试或手工 curl，但不应把依赖真实基础设施的测试永久放入默认单元测试。

## 未解决问题

- 是否需要登录失败次数限制：建议后续结合 Redis 缓存客户端增加限流或临时锁定。
- 是否需要 session 主动下线接口：MVP 可以先依赖状态检查，后续再做 session 管理。
- 是否允许超级管理员修改自己的状态：建议 apply 阶段明确保护，避免最后一个超级管理员禁用自己。
