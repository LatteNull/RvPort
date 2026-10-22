# add-auth-user-management 任务

## 1. 认证基础

- [x] 定义当前用户 principal 和响应 DTO，不包含密码哈希、角色、权限或项目成员字段。
- [x] 实现基于 jOOQ 的用户读取、用户名查找、状态检查和登录时间更新。
- [x] 实现 `POST /api/auth/login`，使用 Argon2id 校验密码并创建 Redis Session。
- [x] 实现 `POST /api/auth/logout`，清理 session 并写入审计。
- [x] 实现 `GET /api/auth/me`，通过 session 识别当前用户并从数据库刷新用户状态。
- [x] 实现 `POST /api/auth/change-password`，校验当前密码、保存新哈希并清除 `mustChangePassword`。
- [x] 实现密码策略校验：至少 8 位，同时包含大写字母、小写字母和数字，暂不要求特殊符号。

## 2. 安全约束

- [x] 保留 Session Cookie 认证，不引入 JWT。
- [x] 配置 CSRF token 获取方式，使前端可以通过 `X-XSRF-TOKEN` 提交状态变更请求。
- [x] 增加受保护请求的用户状态检查，拒绝已禁用用户继续访问。
- [x] 增加强制改密访问限制，除改密、退出、当前用户和 CSRF token 外拒绝其他业务 API。
- [x] 增加超级管理员授权检查，只允许 `is_super_admin=true` 用户访问 `/api/admin/users/**`。
- [x] 确保错误响应使用统一错误包络和稳定错误码。

## 3. 超级管理员用户管理

- [x] 实现 `GET /api/admin/users`，支持分页、状态筛选和关键字搜索。
- [x] 实现 `POST /api/admin/users`，创建普通用户并保存初始密码哈希。
- [x] 拒绝创建用户请求中的 `isSuperAdmin`、`passwordHash`、`roles`、`permissions` 字段。
- [x] 实现 `GET /api/admin/users/{userId}`。
- [x] 实现 `PATCH /api/admin/users/{userId}`，仅允许更新展示名、邮箱和状态。
- [x] 禁止通过更新接口修改用户名、密码哈希、`isSuperAdmin` 或 `mustChangePassword`。
- [x] 实现 `POST /api/admin/users/{userId}/reset-password`，重置密码并支持设置 `mustChangePassword=true`。
- [x] 将删除用户语义收敛为禁用用户，不做物理删除。

## 4. 审计与脱敏

- [x] 为登录成功、登录失败、退出、当前用户改密写入审计日志。
- [x] 为创建用户、更新用户、禁用用户、重置密码写入审计日志。
- [x] 确保审计详情和应用日志不包含明文密码、初始密码、新密码、当前密码或密码哈希。

## 5. 测试与文档

- [x] 增加认证服务单元测试。
- [x] 增加密码策略单元测试，覆盖长度、大写、小写和数字要求。
- [x] 增加用户管理服务单元测试。
- [x] 增加安全过滤和授权行为测试。
- [x] 增加控制器 MockMvc 测试，覆盖状态码、错误码、响应脱敏和强制改密。
- [x] 更新 `docs/API_DESIGN.md`，将登录态固定为 Session Cookie 并补充 CSRF 约定。
- [x] 更新 `docs/BACKEND_DEVELOPMENT_PLAN.md`。
- [x] 运行 `mvn test`。
- [x] 运行 `openspec validate add-auth-user-management`。
