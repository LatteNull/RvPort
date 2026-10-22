## MODIFIED Requirements

### Requirement: 超级管理员可以管理本地用户
MVP API SHALL 为超级管理员提供配置页用户信息表和本地用户增删改查能力，但 SHALL NOT 通过 API 创建或提升超级管理员。管理员创建用户 SHALL 通过邮箱邀请用户自主设置密码；管理员重置密码 SHALL 继续支持直接设置新密码。

#### Scenario: 超级管理员查看用户列表
- **WHEN** 超级管理员打开配置页用户信息表
- **THEN** 前端 SHALL 能调用 `GET /api/admin/users` 获取分页用户列表
- **AND** 列表项 SHALL 包含用户 ID、用户名、展示名、邮箱、状态、`isSuperAdmin`、`mustChangePassword`、最近登录时间和创建时间
- **AND** 列表接口 SHOULD 支持状态筛选和关键字搜索

#### Scenario: 超级管理员创建普通用户
- **WHEN** 超级管理员调用 `POST /api/admin/users`
- **THEN** API SHALL 创建本地普通用户
- **AND** API SHALL 要求提交唯一 `username` 和唯一非空 `email`
- **AND** API SHALL 生成一次性邀请 token 并发送邀请邮件
- **AND** API MUST NOT 要求或接受 `initialPassword`
- **AND** API MUST NOT 接受 `isSuperAdmin`、`passwordHash`、`roles` 或 `permissions` 作为可写字段

#### Scenario: 超级管理员读取和更新用户
- **WHEN** 超级管理员调用 `GET /api/admin/users/{userId}` 或 `PATCH /api/admin/users/{userId}`
- **THEN** API SHALL 允许读取和更新用户的展示名、邮箱和状态
- **AND** API SHALL 对邮箱执行唯一性校验
- **AND** API MUST NOT 允许通过请求体修改 `username`、`passwordHash`、`isSuperAdmin` 或 `mustChangePassword`

#### Scenario: 超级管理员重置用户密码
- **WHEN** 超级管理员调用 `POST /api/admin/users/{userId}/reset-password`
- **THEN** API SHALL 保存新的密码哈希
- **AND** API SHALL 支持设置 `mustChangePassword=true`，使用户下次登录后必须修改密码
- **AND** API MUST NOT 发送重置密码邮件
- **AND** API MUST NOT 返回明文新密码或密码哈希

#### Scenario: 超级管理员重新发送邀请
- **WHEN** 超级管理员调用 `POST /api/admin/users/{userId}/send-invitation`
- **THEN** API SHALL 为该用户生成新的邀请 token
- **AND** API SHALL 使该用户未消费的旧邀请 token 失效
- **AND** API SHALL 向用户当前邮箱发送邀请邮件

#### Scenario: 超级管理员删除或禁用用户
- **WHEN** 超级管理员从配置页移除用户
- **THEN** API SHALL 将用户状态设置为 `DISABLED`
- **AND** API MUST NOT 物理删除 `users` 记录
- **AND** 历史创建人、审计记录和业务引用 SHALL 继续可追溯

#### Scenario: 普通用户访问用户管理接口
- **WHEN** 非超级管理员访问 `/api/admin/users` 或其子接口
- **THEN** API SHALL 返回 `FORBIDDEN` 错误

### Requirement: API 设计标注用户强制改密字段依赖
用户管理和重置密码 API SHALL 依赖数据库提供 `users.must_change_password` 字段。邀请注册和忘记密码流程 SHALL 使用独立 action token，不通过邮箱验证字段表达状态。

#### Scenario: 用户被邀请创建
- **WHEN** 超级管理员创建用户并发送邀请
- **THEN** 后端 SHALL 创建用户记录并生成邀请 token
- **AND** 后端 SHALL 在用户接受邀请并设置密码后允许其正常登录

#### Scenario: 用户被管理员重置密码
- **WHEN** 超级管理员重置用户密码并要求下次登录改密
- **THEN** 后端 SHALL 将该用户的 `must_change_password` 设置为 `true`

#### Scenario: 用户完成强制改密
- **WHEN** 用户成功修改自己的密码
- **THEN** 后端 SHALL 将 `users.must_change_password` 设置为 `false`

#### Scenario: 不新增邮箱验证字段
- **WHEN** 设计邀请注册和忘记密码流程
- **THEN** API 文档 MUST NOT 要求 `email_verified_at` 或等效邮箱验证字段
- **AND** 邮箱可达性 SHALL 由用户通过邮箱中的 token 完成设置密码动作体现

## ADDED Requirements

### Requirement: 当前用户资料 API 不允许修改用户名和邮箱
个人中心 API SHALL 允许用户读取当前用户信息，并 MAY 允许修改展示类字段，但 MUST NOT 允许用户自行修改 `username` 或 `email`。

#### Scenario: 当前用户修改展示信息
- **WHEN** 已登录用户调用当前用户资料更新 API
- **THEN** API MAY 允许修改 `displayName`
- **AND** API MUST NOT 允许修改 `username`、`email`、`isSuperAdmin`、`status`、`mustChangePassword` 或 `passwordHash`

#### Scenario: 当前用户提交邮箱或用户名
- **WHEN** 当前用户资料更新请求包含 `username` 或 `email`
- **THEN** API SHALL 返回校验错误
- **AND** 后端 MUST NOT 修改 `users.username` 或 `users.email`

### Requirement: 用户邀请接受 API 必须设置密码并消费 token
认证 API SHALL 提供邀请接受接口，允许用户通过邮件 token 设置密码并完成账号注册。

#### Scenario: 接受有效邀请
- **WHEN** 用户调用 `POST /api/auth/invitations/accept` 并提交有效邀请 token 和新密码
- **THEN** 后端 SHALL 校验 token 类型、hash、过期时间、消费状态和用户状态
- **AND** 后端 SHALL 保存新密码哈希
- **AND** 后端 SHALL 消费该 token
- **AND** 后端 SHALL 允许用户随后使用账号密码登录

#### Scenario: 接受无效邀请
- **WHEN** 用户提交不存在、过期、已消费或类型不匹配的邀请 token
- **THEN** API SHALL 返回 token 无效或过期错误
- **AND** 后端 MUST NOT 修改用户密码

### Requirement: 忘记密码 API 必须防止账号枚举
认证 API SHALL 提供用户自行触发的忘记密码流程，并 SHALL 防止通过响应枚举账号是否存在。

#### Scenario: 请求密码重置
- **WHEN** 用户调用 `POST /api/auth/password-resets/request` 并提交用户名或邮箱
- **THEN** API SHALL 返回统一成功响应
- **AND** 若匹配到可用用户，后端 SHALL 生成密码重置 token 并发送邮件
- **AND** 若未匹配用户，后端 MUST NOT 暴露账号不存在

#### Scenario: 确认密码重置
- **WHEN** 用户调用 `POST /api/auth/password-resets/confirm` 并提交有效 token 和新密码
- **THEN** 后端 SHALL 校验 token 类型、hash、过期时间和消费状态
- **AND** 后端 SHALL 保存新密码哈希
- **AND** 后端 SHALL 消费该 token
- **AND** 后端 SHALL 将 `mustChangePassword` 设置为 `false`

#### Scenario: 密码重置 token 无效
- **WHEN** 用户提交不存在、过期、已消费或类型不匹配的密码重置 token
- **THEN** API SHALL 返回 token 无效或过期错误
- **AND** 后端 MUST NOT 修改用户密码

### Requirement: 管理员邮箱配置 API 必须受超级管理员保护
后端 API SHALL 为超级管理员提供邮箱服务器配置查询、保存和测试发送接口。

#### Scenario: 查询邮箱配置
- **WHEN** 超级管理员调用 `GET /api/admin/configs/mail`
- **THEN** API SHALL 返回邮箱配置摘要
- **AND** 响应 MUST NOT 返回 SMTP 密码明文

#### Scenario: 保存邮箱配置
- **WHEN** 超级管理员调用 `PATCH /api/admin/configs/mail`
- **THEN** API SHALL 校验并保存邮箱配置
- **AND** SMTP 密码等 secret SHALL 加密保存
- **AND** API MUST NOT 接受非邮箱配置白名单字段

#### Scenario: 测试邮箱配置
- **WHEN** 超级管理员调用 `POST /api/admin/configs/mail:test`
- **THEN** API SHALL 使用当前或请求中的临时邮箱配置发送测试邮件
- **AND** 响应 SHALL 返回脱敏后的成功或失败摘要

### Requirement: 任务完成邮件推送 API 配置必须受控
后端 SHALL 通过受控配置支持任务完成邮件推送开关和默认收件策略。

#### Scenario: 配置任务完成邮件推送
- **WHEN** 超级管理员更新任务邮件通知配置
- **THEN** API SHALL 保存通知开关和允许的通知策略
- **AND** API MUST NOT 允许提交任意未声明配置 key

#### Scenario: 任务完成触发邮件
- **WHEN** 任务进入终态且邮件通知开启
- **THEN** 后端 SHALL 向任务创建人邮箱发送任务完成通知
- **AND** 邮件内容 MUST NOT 包含明文凭据、完整日志或服务器真实敏感路径
