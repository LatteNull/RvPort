# add-database-migrations 提案

## 背景

当前后端已经有数据库设计文档、API 设计文档、Docker 基础设施和 Spring Boot 工程骨架，但 Liquibase 仍只有占位 changelog。PostgreSQL 空库还不能通过后端工程迁移出 MVP 所需 schema，也不能为后续 jOOQ codegen 提供真实数据库结构。

本变更用于把 `backend/docs/DATABASE_DESIGN.md` 中已确认的 MVP 数据库设计落成 Liquibase 初始迁移脚本。

## 范围

本变更将：

- 建立 Liquibase changelog 分层结构。
- 使用 PostgreSQL formatted SQL changelog 创建初始 schema。
- 启用 `pgcrypto` 扩展。
- 创建数据库设计文档中的 MVP 表、主键、外键、唯一约束、检查约束和必要索引。
- 创建幂等默认超级管理员初始化 seed：
  - `username = 'admin'`
  - 初始密码输入为 `admin123`
  - 只保存预计算后的 Argon2id `password_hash`
  - `is_super_admin = true`
  - `must_change_password = true`
- 保持 `.env` / 环境变量驱动的本地迁移方式。
- 验证空 PostgreSQL 数据库可以通过 Liquibase 迁移成功。
- 记录 jOOQ codegen 必须在 Liquibase 成功迁移 schema 后运行。

本变更不做：

- 不实现 Repository、Service、Controller 或业务 API。
- 不生成或提交 jOOQ 代码。
- 不实现登录、用户管理或默认管理员登录流程。
- 不引入 JPA。
- 不引入角色、用户角色映射、项目成员、通用 artifact、测试用例明细或邮箱验证相关表。
- 不实现外部 KMS/Vault。

## 影响文件

预计影响：

- `src/main/resources/db/changelog/db.changelog-master.yaml`
- `src/main/resources/db/changelog/changes/*.sql`
- `docs/BACKEND_DEVELOPMENT_PLAN.md`
- 可能新增数据库迁移验证测试或测试配置
- `openspec/specs/backend-database-design/spec.md`

## 验收标准

- 空 PostgreSQL 数据库可通过 Liquibase 迁移到可用 schema。
- 所有 MVP 表、关键字段、外键和索引与数据库设计文档一致。
- 默认 `admin` 用户初始化幂等。
- 数据库中不保存 `admin123` 明文。
- `users.must_change_password` 存在且默认值正确。
- 不创建 MVP 明确排除的表。
- Maven 测试和 OpenSpec 校验通过。
