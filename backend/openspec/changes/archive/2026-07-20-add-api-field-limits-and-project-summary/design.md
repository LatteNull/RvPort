## Context

当前后端已经实现邀请注册、忘记密码、个人资料更新和项目列表基础能力，但飞书联调文档暴露了三个未收敛点：认证输入缺少统一最大长度约束，项目列表卡片缺少风险、扫描、构建和测试摘要字段，项目名称重复策略未明确。

现有数据库中 `users.username` 是 `text` 且只有唯一索引；`projects.name` 是 `text` 且没有唯一约束。现有 API 请求对象中登录、改密、邀请设密和密码重置确认只做 `@NotBlank`，密码复杂度由 `PasswordPolicy` 校验但没有最大长度边界。

## Goals / Non-Goals

**Goals:**

- 统一认证入口字段边界：`username` 最大 64 字符，所有明文 `password` 输入最大 16 字符。
- 在数据库层限制 `users.username` 长度，避免绕过 API 写入超长用户名。
- 为 `GET /api/projects` 的列表项提供稳定项目卡片摘要字段。
- 明确项目名称允许重名，不新增项目名称唯一约束。
- 为上述正常流程、异常流程和 edge case 补充单元测试与 E2E 覆盖。

**Non-Goals:**

- 不修改普通 text 字段的现有长度配置，例如 `displayName`、`description`、`email`、配置值和各类摘要字段。
- 不改变密码哈希算法、密码复杂度规则或用户 action token 机制。
- 不新增项目编号、项目成员、项目共享或项目权限模型。
- 不实现完整构建、测试、issue 管理领域；未落地领域的项目摘要字段使用 `null` 或 `0` 表达暂无数据。
- 不改变当前用户资料修改路径；本 change 不新增 `/api/auth/me` alias。

## Decisions

### 认证字段长度在请求对象和服务层双重收敛

在请求 DTO 上使用 Bean Validation 表达最大长度，覆盖：

- `LoginRequest.username <= 64`
- `LoginRequest.password <= 16`
- `ChangePasswordRequest.currentPassword <= 16`
- `ChangePasswordRequest.newPassword <= 16`
- `AcceptInvitationRequest.newPassword <= 16`
- `PasswordResetConfirmRequest.newPassword <= 16`
- `ResetPasswordRequest.newPassword <= 16`
- `CreateUserRequest.username <= 64`

理由：请求对象校验可以统一返回 `VALIDATION_ERROR`，并在 Controller 层阻断超长输入进入密码哈希或认证流程。服务层仍保留现有密码复杂度、用户名重复、邮箱重复和 forbidden writable fields 校验。

备选方案是只在 service 中写手动校验；缺点是不同入口容易漏掉，并且 Controller validation 测试无法统一覆盖。

### 数据库只增加 username 长度约束

新增 Liquibase changeset，为 `users.username` 增加 `char_length(username) <= 64` check constraint。密码为明文输入，不持久化到独立字段，因此不做数据库层密码长度约束。

迁移前需要确认已有数据没有超过 64 字符的用户名。若存在，迁移应失败并暴露数据修复需求，而不是静默截断。

### 项目列表摘要字段使用轻量聚合对象

`ProjectResponse` 或专用列表响应项增加摘要字段：

- `highRiskCount`: `long`，当前没有 issue 领域事实时返回 `0`。
- `latestScanAt`: `OffsetDateTime`，优先来自已落地扫描或 SBOM 运行相关时间；没有扫描记录时返回 `null`。
- `latestBuildStatus`: `String` 或枚举字符串，没有构建记录时返回 `null`。
- `latestTestStatus`: `String` 或枚举字符串，没有测试记录时返回 `null`。

当前实现可以先在 `ProjectRepository.listAccessible` 的查询结果基础上追加批量摘要查询，避免对每个项目逐个查库。若项目列表页大小受控，按当前页项目 ID 做 `GROUP BY project_id` 聚合即可。

备选方案是新增批量摘要接口。当前前端需要项目卡片直接展示，优先把字段放入列表项，减少前端额外请求和状态拼装。

### 项目名称允许重名

本 change 明确不为 `projects.name` 增加唯一约束，也不在创建项目时拒绝同名。原因是后续可能引入多用户共享项目，提前定义同创建者唯一或全局唯一会限制后续产品设计。

现阶段项目唯一识别仍使用 `projectId`。前端列表可结合创建时间、架构、状态、摘要字段区分同名项目。

## Risks / Trade-offs

- [Risk] 密码最大 16 位会拒绝部分用户常用的更长密码。  
  Mitigation: 按当前产品决策执行，所有设密入口统一使用 16 位上限，避免前后端规则分裂。

- [Risk] 项目列表摘要聚合可能随领域表增多而变慢。  
  Mitigation: 只对当前页项目 ID 做批量聚合，并为后续构建、测试、issue 表按 `project_id, created_at/status` 增加必要索引。

- [Risk] 未落地领域摘要返回 `null` 或 `0` 可能被误解为真实执行结果。  
  Mitigation: API 文档明确 `null` 表示暂无运行记录，`0` 表示当前可聚合事实中的高风险数量为 0；前端展示为 `未开始` 或 `--`。

- [Risk] 项目允许重名会降低列表可识别性。  
  Mitigation: 本 change 不解决最终识别模型，但列表返回创建时间、架构、状态和摘要字段，短期满足区分需求；项目编号或共享模型留给后续 change。

## Migration Plan

1. 增加 Liquibase changeset，为 `users.username` 添加长度 check constraint。
2. 运行 Liquibase 验证当前数据库可迁移。
3. 运行 jOOQ codegen，确认生成代码与 schema 一致。
4. 更新 API 请求对象、项目列表响应和仓储查询。
5. 更新中文文档、单元测试和 E2E。

Rollback：如 username 约束需要回滚，可通过后续 Liquibase changeset 删除该 check constraint；API 长度限制和项目摘要字段为后端代码行为，可通过回滚版本恢复。

## Open Questions

- `latestScanAt` 首期是否只聚合 SBOM 运行，还是同时纳入 KB scan。实现时应优先检查当前已落地表结构，使用已有事实数据，不为未落地领域新增表。
