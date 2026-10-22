## Context

后端当前已经实现本地用户、Session 登录、强制改密、超级管理员用户管理和管理员直接重置密码。现有用户创建 API 要求管理员提交初始密码，这会把密码分发责任放到管理员侧，也无法验证用户邮箱可达性。项目后续还需要任务完成邮件推送，因此需要先补齐统一邮件配置和邮件发送基础能力。

当前数据库中 `users.username` 已有唯一索引，`users.email` 已有非空唯一索引。个人中心不允许用户修改自己的用户名和邮箱，邮箱只能由超级管理员维护。

## Goals / Non-Goals

**Goals:**

- 使用统一 `system_configs` 表承载邮箱服务器配置，并为后续 AI、知识库、通知等配置留出同一模型。
- 管理员创建用户后生成邀请 token，通过邮件发送设置密码链接，由用户自主设置密码完成注册。
- 支持用户忘记密码：用户提交邮箱或用户名后，后端发送密码重置邮件，用户通过 token 设置新密码。
- 保留管理员直接重置密码能力，并允许管理员选择是否要求用户下次登录后主动修改密码。
- 邮件发送能力可用于邀请、忘记密码和任务完成通知。
- 所有新增测试继续满足正常流程、异常流程、edge case 三类覆盖。

**Non-Goals:**

- 不允许用户在个人中心修改 `username` 或 `email`。
- 不新增角色、权限、项目成员模型。
- 不新增 `email_verified_at` 等邮箱验证字段；邀请 token 被发送到该邮箱，接受邀请即证明邮箱可达。
- 不在本 change 实现 AI 服务配置或知识库版本配置。

## Decisions

### 使用统一 system_configs 表

使用 `system_configs(namespace, config_key, config_value, value_type, encrypted, updated_by, timestamps)` 保存配置。邮箱配置使用 `namespace = 'mail'`，任务邮件通知使用 `namespace = 'notification'` 或邮件配置中的受控 key。

备选方案是每类配置独立建表。该方案查询更直观，但后续 AI、知识库、通知等配置会产生大量小表，迁移和 API 维护成本更高。统一表可以减少 schema 膨胀，但 API 层必须通过白名单字段和业务 DTO 控制读写，不能开放任意 key-value 写接口。

### token 只保存 hash

邀请和忘记密码使用 `user_action_tokens` 表保存 `token_hash`，明文 token 只出现在邮件 URL 和用户提交请求中。token 需要包含类型、用户、过期时间、消费时间、创建人和必要 metadata。

备选方案是直接保存明文 token，调试更简单，但泄漏风险不可接受。

### 管理员创建用户不再提交初始密码

管理员创建用户时提交 `username`、`email`、`displayName`、`status`。后端创建用户并发送邀请邮件，用户通过邀请链接设置密码。为了满足 `users.password_hash not null` 约束，创建时可以写入不可登录的随机密码哈希或调整 schema 支持注册前密码为空；本 change 推荐保留 not null，通过随机不可知密码哈希避免扩大登录判断复杂度。

### 管理员重置密码继续直接设置

管理员重置密码 API 继续接受新密码，并可设置 `mustChangePassword`。这用于管理员人工处理账号问题。忘记密码邮件由用户主动触发，不复用管理员重置路径。

### 邮件发送失败与用户创建事务

用户创建和 token 创建应在数据库事务中完成。邮件发送可以在事务提交后执行；如果邮件发送失败，应保留用户和 token，并返回可识别错误或允许管理员重新发送邀请。这样避免邮件服务临时故障导致用户记录反复创建失败。

### 任务完成邮件推送

任务进入成功、失败、取消等终态后，worker 在完成任务状态落库和事件写入后触发通知发送。邮件发送失败不得回滚任务终态；失败需要记录日志或审计摘要，并允许后续重试策略扩展。

## Risks / Trade-offs

- [配置表过于自由] → API 层必须按 namespace 定义 DTO、字段白名单、类型校验和 secret 加密策略，不提供任意配置写入接口。
- [邀请邮件发送失败] → 保留 token，提供 `POST /api/admin/users/{userId}/send-invitation` 重新发送。
- [忘记密码被用于枚举用户] → request 接口无论用户是否存在都返回统一成功响应，并限制频率。
- [token 泄漏] → token 只保存 hash，设置短期过期时间，消费后立即标记 `consumed_at`，日志和审计不得记录明文 token。
- [邮件发送阻塞 worker] → 任务完成通知应设置超时，失败只记录通知失败，不影响任务状态。

## Migration Plan

1. 新增 `system_configs` 表和 `user_action_tokens` 表。
2. 保持 `users.username` 和非空 `users.email` 唯一索引。
3. 调整管理员创建用户 API 请求字段，移除 `initialPassword` 要求。
4. 新增邀请接受、重新发送邀请、忘记密码、邮箱配置和测试发送 API。
5. 增加邮件发送服务和任务完成通知路径。
6. 补充单元测试和 E2E 测试。

回滚时可以停止调用新增邮件和 token API，保留表结构不影响现有登录、管理员重置密码和强制改密流程。

## Open Questions

- 邮件 URL 的前端 base URL 使用系统配置还是环境变量提供。
- 邀请 token 和忘记密码 token 的默认有效期分别设置为多久。
- 任务完成邮件推送默认是否开启，是否需要用户级偏好配置。
