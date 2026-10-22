# add-auth-user-management 提案

## 背景

后端已经具备 Spring Boot 工程骨架、Liquibase schema、jOOQ 生成代码、Redis Session、统一响应格式、Redis 缓存客户端和 RabbitMQ 投递客户端。当前还缺少认证与本地用户管理的实际后端能力。

已有 API 设计和数据库设计已经确定：

- MVP 使用本地账号，不做 SSO。
- 浏览器登录态使用服务端 Session 和 Cookie，不使用 JWT。
- 用户表使用 `users`，包含 `is_super_admin` 和 `must_change_password`。
- MVP 不做用户角色、用户角色映射、权限模型或项目成员模型。
- `is_super_admin` 只能通过数据库或初始化流程授予，不能通过 API 创建或提升。
- 默认超级管理员为 `admin`，初始密码为 `admin123`，首次登录必须改密。

本变更用于把这些设计收敛为可实现的认证、当前用户和超级管理员用户管理模块。

## 范围

本变更将：

- 实现本地账号登录、退出、当前用户查询和当前用户修改密码 API。
- 使用 Spring Security、Spring Session Redis 和 `RVPORT_SESSION` HttpOnly Cookie 维护浏览器登录态。
- 保持 CSRF 防护，并为前端提供可获取 CSRF token 的接口或 cookie 方案。
- 使用 Argon2id 校验和保存用户密码哈希。
- 登录成功后更新 `users.last_login_at`。
- 禁止 `DISABLED` 用户登录和继续访问受保护 API。
- 对 `must_change_password=true` 用户限制访问范围，只允许读取当前用户、修改密码、退出登录和获取 CSRF token。
- 实现超级管理员用户管理 API：列表、创建普通用户、详情、更新、禁用、重置密码。
- 明确删除用户在 MVP 中等价为禁用用户，不做物理删除。
- 拒绝通过 API 创建或修改 `isSuperAdmin`。
- 对登录、退出、改密、创建用户、更新用户、禁用用户、重置密码写入脱敏审计日志。
- 增加认证、授权、强制改密、用户管理和密码策略相关测试。
- 更新中文开发计划和相关规格。

本变更不做：

- 不实现 JWT、OAuth、OIDC、LDAP 或企业 SSO。
- 不引入用户角色、权限、用户角色映射或项目成员模型。
- 不提供通过 API 创建、提升或撤销超级管理员的能力。
- 不实现邮箱验证、邮箱 action token 或找回密码邮件流程。
- 不实现用户物理删除。
- 不实现前端页面。
- 不实现项目级权限控制。

## 影响文件

预计影响：

- `src/main/java/cn/rvport/backend/security/**`
- `src/main/java/cn/rvport/backend/auth/**`
- `src/main/java/cn/rvport/backend/user/**`
- `src/main/java/cn/rvport/backend/audit/**`
- `src/main/resources/application.yml`
- `src/test/java/cn/rvport/backend/**`
- `docs/API_DESIGN.md`
- `docs/BACKEND_DEVELOPMENT_PLAN.md`
- `openspec/specs/backend-api-design/spec.md`
- `openspec/specs/backend-app-skeleton/spec.md`

## 验收标准

- `POST /api/auth/login` 能使用本地用户名和密码建立 Redis Session，并返回当前用户信息。
- 登录失败、用户不存在或用户被禁用时不泄漏账号存在性和密码细节。
- `POST /api/auth/logout` 能清理当前 session。
- `GET /api/auth/me` 能通过 HttpOnly Cookie 识别当前用户，并且不返回密码哈希、角色、权限或项目成员信息。
- `POST /api/auth/change-password` 能校验当前密码、保存新 Argon2id 哈希，并清除 `mustChangePassword`。
- 新密码策略要求至少 8 位，并同时包含大写字母、小写字母和数字；MVP 暂不要求特殊符号。
- `mustChangePassword=true` 用户除获取当前用户、修改密码、退出登录和获取 CSRF token 外，访问其他受保护 API 时返回明确错误。
- `GET /api/admin/users` 只有超级管理员可访问，并支持分页、状态和关键字筛选。
- `POST /api/admin/users` 只能创建普通用户，必须保存密码哈希，不能接受 `isSuperAdmin=true`。
- `GET /api/admin/users/{userId}` 和 `PATCH /api/admin/users/{userId}` 只有超级管理员可访问，且不能通过请求体修改 `isSuperAdmin`、`username` 或 `passwordHash`。
- `POST /api/admin/users/{userId}/reset-password` 能重置密码并支持设置 `mustChangePassword=true`。
- 用户删除操作在 MVP 中以禁用用户实现，不物理删除 `users` 记录。
- 状态为 `DISABLED` 的用户不能登录；已登录用户被禁用后继续访问受保护 API 时应被拒绝。
- 状态变更、改密、重置密码、登录和退出写入审计日志，审计详情不得包含明文密码。
- CSRF 防护与 Session Cookie 登录态兼容，前端可以获取并提交 CSRF token。
- 单元测试覆盖认证服务、用户管理服务、强制改密拦截、超级管理员授权和主要控制器行为。
- `mvn test` 通过。
- `openspec validate add-auth-user-management` 通过。
