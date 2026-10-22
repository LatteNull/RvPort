## MODIFIED Requirements

### Requirement: 认证 API 不暴露角色权限模型
MVP 认证 API SHALL 只返回本地用户信息和超级管理员标记，不 SHALL 暴露角色、权限或项目成员模型。

#### Scenario: 获取当前用户
- **WHEN** 前端调用 `GET /api/auth/me`
- **THEN** 响应 SHALL 包含用户 ID、用户名、展示名、邮箱、状态、`isSuperAdmin` 和 `mustChangePassword`
- **AND** 响应 MUST NOT 包含 `roles`、`permissions`、`projectMembers` 或 `passwordHash`

#### Scenario: 用户登录成功
- **WHEN** 用户通过本地账号登录
- **THEN** API SHALL 建立基于服务端 Session 和 Cookie 的登录态
- **AND** 响应 SHALL 返回当前用户信息
- **AND** 响应和日志 MUST NOT 返回明文密码、密码哈希、角色、权限或项目成员信息

#### Scenario: 用户登录失败
- **WHEN** 用户名不存在、密码错误或用户状态不允许登录
- **THEN** API SHALL 返回认证失败或用户禁用错误
- **AND** 响应和日志 MUST NOT 暴露明文密码
- **AND** 响应 SHOULD NOT 泄漏可被枚举利用的账号存在性细节

#### Scenario: 当前用户修改密码
- **WHEN** 已登录用户调用 `POST /api/auth/change-password`
- **THEN** API SHALL 校验当前密码并保存新密码哈希
- **AND** 成功后 SHALL 将用户的 `mustChangePassword` 标记清除
- **AND** API MUST NOT 在响应、日志或审计详情中记录当前密码或新密码

#### Scenario: 强制改密用户访问受限
- **WHEN** 已登录用户的 `mustChangePassword` 为 `true`
- **THEN** API SHALL 只允许其访问当前用户查询、修改密码、退出登录和 CSRF token 获取接口
- **AND** 访问其他受保护业务接口时 SHALL 返回 `PASSWORD_CHANGE_REQUIRED` 错误

#### Scenario: 用户退出登录
- **WHEN** 已登录用户调用 `POST /api/auth/logout`
- **THEN** API SHALL 清理当前服务端 Session
- **AND** 后续使用同一登录态访问受保护接口 SHALL 失败

### Requirement: 超级管理员可以管理本地用户
MVP API SHALL 为超级管理员提供配置页用户信息表和本地用户增删改查能力，但 SHALL NOT 通过 API 创建或提升超级管理员。

#### Scenario: 超级管理员查看用户列表
- **WHEN** 超级管理员打开配置页用户信息表
- **THEN** 前端 SHALL 能调用 `GET /api/admin/users` 获取分页用户列表
- **AND** 列表项 SHALL 包含用户 ID、用户名、展示名、邮箱、状态、`isSuperAdmin`、`mustChangePassword`、最近登录时间和创建时间
- **AND** 列表接口 SHOULD 支持状态筛选和关键字搜索

#### Scenario: 超级管理员创建普通用户
- **WHEN** 超级管理员调用 `POST /api/admin/users`
- **THEN** API SHALL 创建本地普通用户并保存初始密码哈希
- **AND** API SHALL 支持设置 `mustChangePassword`
- **AND** API MUST NOT 接受 `isSuperAdmin`、`passwordHash`、`roles` 或 `permissions` 作为可写字段

#### Scenario: 超级管理员读取和更新用户
- **WHEN** 超级管理员调用 `GET /api/admin/users/{userId}` 或 `PATCH /api/admin/users/{userId}`
- **THEN** API SHALL 允许读取和更新用户的展示名、邮箱和状态
- **AND** API MUST NOT 允许通过请求体修改 `username`、`passwordHash`、`isSuperAdmin` 或 `mustChangePassword`

#### Scenario: 超级管理员重置用户密码
- **WHEN** 超级管理员调用 `POST /api/admin/users/{userId}/reset-password`
- **THEN** API SHALL 保存新的密码哈希
- **AND** API SHALL 支持设置 `mustChangePassword=true`，使用户下次登录后必须修改密码
- **AND** API MUST NOT 返回明文新密码或密码哈希

#### Scenario: 超级管理员删除或禁用用户
- **WHEN** 超级管理员从配置页移除用户
- **THEN** API SHALL 将用户状态设置为 `DISABLED`
- **AND** API MUST NOT 物理删除 `users` 记录
- **AND** 历史创建人、审计记录和业务引用 SHALL 继续可追溯

#### Scenario: 普通用户访问用户管理接口
- **WHEN** 非超级管理员访问 `/api/admin/users` 或其子接口
- **THEN** API SHALL 返回 `FORBIDDEN` 错误

### Requirement: API 通用约定必须统一
后端 API 设计 SHALL 定义统一的 base path、响应包络、错误格式、分页格式、时间格式和浏览器 Session 安全约定。

#### Scenario: 返回成功响应
- **WHEN** API 请求成功
- **THEN** 响应 SHALL 使用统一响应包络，包含业务数据、请求追踪 ID 和时间戳

#### Scenario: 返回错误响应
- **WHEN** API 请求失败
- **THEN** 响应 SHALL 使用统一错误格式，包含错误码、错误消息、可选字段级详情、请求追踪 ID 和时间戳

#### Scenario: 返回分页列表
- **WHEN** API 返回列表数据
- **THEN** 响应 SHALL 支持 `page`、`pageSize`、`total`、`hasMore` 和 `items`

#### Scenario: 使用 Session Cookie 进行浏览器认证
- **WHEN** 前端调用需要登录态的 API
- **THEN** 前端 SHALL 依赖浏览器自动携带 HttpOnly Session Cookie
- **AND** 前端 MUST NOT 通过读取 JWT 恢复 MVP 登录态

#### Scenario: 状态变更请求提交 CSRF token
- **WHEN** 前端使用 Session Cookie 调用状态变更 API
- **THEN** 前端 SHALL 能先获取 CSRF token
- **AND** 状态变更请求 SHALL 通过约定 header 提交 CSRF token
