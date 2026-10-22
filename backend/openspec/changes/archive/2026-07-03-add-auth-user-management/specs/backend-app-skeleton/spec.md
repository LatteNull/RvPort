## MODIFIED Requirements

### Requirement: 浏览器登录态使用服务端 Session 和 Cookie
MVP 浏览器登录态 SHALL 使用 Spring Security Session、Spring Session Redis 和 HttpOnly Cookie，不 SHALL 使用 JWT 作为默认登录态。

#### Scenario: 用户登录
- **WHEN** 用户通过登录接口完成认证
- **THEN** 后端 SHALL 创建服务端 session
- **AND** session SHALL 存储到 Redis
- **AND** 响应 SHALL 设置 `RVPORT_SESSION` Cookie
- **AND** `RVPORT_SESSION` Cookie SHALL 使用 HttpOnly

#### Scenario: 前端获取当前用户
- **WHEN** 前端刷新页面或初始化应用状态
- **THEN** 前端 SHALL 调用 `GET /api/auth/me` 获取当前用户信息
- **AND** 未登录用户 SHALL 收到 `401` 响应

#### Scenario: 避免 JWT 作为 MVP 默认登录态
- **WHEN** 设计 MVP 浏览器认证
- **THEN** 系统 MUST NOT 要求前端保存 JWT
- **AND** 系统 MUST NOT 要求使用 JWT 完成浏览器登录态恢复

#### Scenario: 保留 CSRF 防护
- **WHEN** MVP 使用浏览器 Session Cookie 作为登录态
- **THEN** 后端 SHALL 保留 CSRF 防护
- **AND** 后端 SHALL 提供前端可获取 CSRF token 的方式
- **AND** 状态变更 API SHALL 校验约定的 CSRF token

#### Scenario: Session 中不保存秘密
- **WHEN** 后端创建认证 session
- **THEN** session principal MUST NOT 保存明文密码、密码哈希、业务凭据、角色、权限或项目成员列表

### Requirement: 密码和业务凭据必须使用不同安全策略
后端应用 SHALL 使用 Argon2id 保存用户密码哈希，并 SHALL 为 Git/SSH 等业务凭据提供应用层 AES-256-GCM 加密能力。

#### Scenario: 保存用户密码
- **WHEN** 后端保存或更新用户密码
- **THEN** 系统 SHALL 保存 Argon2id 哈希
- **AND** 系统 MUST NOT 保存明文密码
- **AND** 系统 MUST NOT 使用 SHA-256、MD5 等快哈希保存密码
- **AND** 响应、应用日志和审计详情 MUST NOT 包含明文密码或密码哈希

#### Scenario: 加密业务凭据
- **WHEN** 后续凭据管理能力保存 Git token、Git 密码、SSH 密码、SSH 私钥或 SSH passphrase
- **THEN** 秘密载荷 SHALL 使用应用层 AES-256-GCM 加密
- **AND** 加密主密钥 SHALL 来自环境变量或后续 KMS/Vault
- **AND** API、日志和审计 MUST NOT 输出明文秘密

#### Scenario: 区分平台级秘密和业务凭据
- **WHEN** 管理 PostgreSQL、Redis、RabbitMQ 密码或凭据加密主密钥
- **THEN** 这些平台级秘密 SHALL 来自 `.env` 或环境变量
- **AND** Git/SSH 等业务凭据 MAY 写入 `credentials` 表，但秘密字段 MUST 加密保存
