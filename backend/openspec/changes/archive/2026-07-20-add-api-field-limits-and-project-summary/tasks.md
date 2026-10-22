## 1. 数据库迁移和生成代码

- [x] 1.1 新增 Liquibase changeset，为 `users.username` 增加 `char_length(username) <= 64` check constraint。
- [x] 1.2 确认不为 `projects.name` 增加全局或创建人维度唯一约束。
- [x] 1.3 运行 Liquibase 验证当前数据库可完成迁移。
- [x] 1.4 运行 jOOQ codegen，确认生成代码与 schema 一致。

## 2. 认证输入长度限制

- [x] 2.1 为 `LoginRequest.username` 增加最大 64 字符校验。
- [x] 2.2 为 `LoginRequest.password` 增加最大 16 字符校验。
- [x] 2.3 为 `ChangePasswordRequest.currentPassword` 和 `newPassword` 增加最大 16 字符校验。
- [x] 2.4 为 `AcceptInvitationRequest.newPassword` 增加最大 16 字符校验。
- [x] 2.5 为 `PasswordResetConfirmRequest.newPassword` 增加最大 16 字符校验。
- [x] 2.6 为管理员重置密码请求中的 `newPassword` 增加最大 16 字符校验。
- [x] 2.7 为管理员创建用户请求中的 `username` 增加最大 64 字符校验。
- [x] 2.8 确认超长输入返回统一参数校验错误，且不会执行密码哈希校验、token 消费或密码更新。

## 3. 项目列表摘要字段

- [x] 3.1 设计项目列表项响应结构，增加 `highRiskCount`、`latestScanAt`、`latestBuildStatus` 和 `latestTestStatus`。
- [x] 3.2 实现当前页项目 ID 的批量摘要查询，避免列表项逐条查询。
- [x] 3.3 对尚未落地或暂无记录的领域返回稳定空值：高风险数为 `0`，扫描、构建、测试状态为 `null`。
- [x] 3.4 确认普通用户和超级管理员项目列表都返回相同摘要字段，并继续遵守项目访问守卫。
- [x] 3.5 确认同名项目可正常创建和列表展示，不返回冲突错误。

## 4. 单元测试

- [x] 4.1 为登录接口补充正常流程、超长 username、超长 password 和空白输入测试。
- [x] 4.2 为当前用户改密补充正常流程、当前密码超长、新密码超长、复杂度失败和当前密码错误测试。
- [x] 4.3 为邀请接受和忘记密码确认补充新密码超长时不消费 token、不更新密码的测试。
- [x] 4.4 为管理员创建用户和管理员重置密码补充 username/password 长度边界测试。
- [x] 4.5 为项目创建补充允许同名项目测试。
- [x] 4.6 为项目列表补充摘要字段正常流程、无领域记录空值、分页列表批量摘要和访问守卫测试。
- [x] 4.7 为 Liquibase 迁移补充 `users.username` 长度约束验证。

## 5. E2E 和真实验证

- [x] 5.1 更新模块化 E2E 的 auth 模块，覆盖 username 64、password 16 的边界和超长失败路径。
- [x] 5.2 更新模块化 E2E 的 project 模块，覆盖同名项目创建成功和项目列表摘要字段存在。
- [x] 5.3 启动真实后端和 Docker 基础设施，运行相关 E2E 模块。
- [x] 5.4 检查 E2E 清理脚本仍能清理同名项目和相关测试数据。

## 6. 文档和收尾

- [x] 6.1 更新 `backend/docs/API_DESIGN.md`，说明认证字段长度限制、项目列表摘要字段和项目允许重名策略。
- [x] 6.2 更新 `backend/docs/DATABASE_DESIGN.md`，说明 `users.username` 长度约束和 `projects.name` 非唯一策略。
- [x] 6.3 更新 E2E 覆盖文档，记录新增 auth/project 覆盖点。
- [x] 6.4 运行 `mvn test`，确认单元测试全部通过。
- [x] 6.5 运行 `openspec status --change add-api-field-limits-and-project-summary`，确认 artifacts 完成。
