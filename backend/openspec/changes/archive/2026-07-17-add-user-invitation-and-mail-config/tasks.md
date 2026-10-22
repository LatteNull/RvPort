## 1. 数据库和生成代码

- [x] 1.1 新增 Liquibase 迁移，创建 `system_configs` 表及 `namespace, config_key` 唯一约束和必要索引。
- [x] 1.2 新增 Liquibase 迁移，创建 `user_action_tokens` 表、token 类型约束、token hash 唯一索引、用户和过期时间索引。
- [x] 1.3 确认 `users.username` 和非空 `users.email` 唯一索引仍存在，并补充迁移测试覆盖。
- [x] 1.4 运行 Liquibase 更新本地数据库并重新执行 jOOQ 生成脚本。

## 2. 统一配置和邮箱配置

- [x] 2.1 实现 `SystemConfigRepository`，支持按 namespace/key 读写、批量读取、secret 加密写入和脱敏读取。
- [x] 2.2 实现邮箱配置 DTO、字段白名单、类型校验、端口/TLS/超时校验和 secret 脱敏响应。
- [x] 2.3 新增超级管理员邮箱配置 API：`GET /api/admin/configs/mail`、`PATCH /api/admin/configs/mail`、`POST /api/admin/configs/mail:test`。
- [x] 2.4 确保普通用户访问邮箱配置 API 返回权限错误。

## 3. 邮件发送服务

- [x] 3.1 添加邮件发送依赖和配置加载逻辑，支持从 `system_configs` 获取 SMTP 配置。
- [x] 3.2 实现邮件发送服务，支持邀请邮件、忘记密码邮件、任务完成邮件和测试邮件。
- [x] 3.3 实现邮件发送失败的脱敏错误摘要，避免泄漏 SMTP 密码、token、完整服务器响应或业务凭据。
- [x] 3.4 支持本地开发或 E2E 使用测试邮件模式，避免必须连接真实外部邮箱服务。

## 4. 用户邀请注册

- [x] 4.1 调整 `POST /api/admin/users`，移除 `initialPassword` 要求，要求唯一 username 和非空唯一 email。
- [x] 4.2 创建用户时生成邀请 token，数据库仅保存 token hash，并在事务提交后发送邀请邮件。
- [x] 4.3 新增 `POST /api/admin/users/{userId}/send-invitation`，重新生成邀请 token 并使旧未消费邀请 token 失效。
- [x] 4.4 新增 `POST /api/auth/invitations/accept`，校验 token 后设置密码、消费 token 并允许后续登录。
- [x] 4.5 确保邀请 token 过期、已消费、类型错误或用户禁用时不能修改密码。

## 5. 忘记密码和个人中心边界

- [x] 5.1 新增 `POST /api/auth/password-resets/request`，统一响应并防止账号枚举。
- [x] 5.2 新增 `POST /api/auth/password-resets/confirm`，校验密码重置 token 后设置新密码并消费 token。
- [x] 5.3 保留管理员 `POST /api/admin/users/{userId}/reset-password` 直接重置密码能力，并确认该流程不发送邮件。
- [x] 5.4 如实现个人中心更新 API，仅允许修改 `displayName`，并拒绝 `username`、`email`、`isSuperAdmin`、`status`、`mustChangePassword` 和 `passwordHash`。

## 6. 任务完成邮件推送

- [x] 6.1 增加任务完成邮件通知配置读取逻辑，默认策略明确且可测试。
- [x] 6.2 在任务进入终态并完成状态、事件落库后触发邮件通知。
- [x] 6.3 确保任务完成邮件发送失败不会回滚任务终态、不会重新投递任务，并记录脱敏失败摘要。
- [x] 6.4 确保任务邮件内容不包含完整日志、明文凭据、token 或服务器真实敏感路径。

## 7. 单元测试和集成测试

- [x] 7.1 为系统配置读写、secret 加密脱敏、字段白名单和类型校验补充正常流程、异常流程、edge case 测试。
- [x] 7.2 为邀请 token 生成、hash 校验、过期、消费、重放和类型不匹配补充测试。
- [x] 7.3 为管理员创建用户、重新发送邀请、接受邀请、管理员直接重置密码和忘记密码流程补充测试。
- [x] 7.4 为邮件发送服务和任务完成邮件推送补充成功、失败和脱敏边界测试。
- [x] 7.5 运行 `mvn test` 并确认通过。

## 8. API E2E 和文档

- [x] 8.1 更新独立 E2E 测试，覆盖管理员邀请创建用户、接受邀请、管理员直接重置密码、忘记密码、邮箱配置和任务完成邮件推送。
- [x] 8.2 E2E 清理脚本覆盖 `system_configs` 测试项、`user_action_tokens`、测试用户和测试邮件记录。
- [x] 8.3 更新 `docs/API_DESIGN.md`、数据库设计文档和 README 中涉及用户创建、邮箱配置、忘记密码和任务邮件通知的说明。
- [x] 8.4 运行 OpenSpec 状态检查，确认 proposal、design、specs、tasks 均完整。
