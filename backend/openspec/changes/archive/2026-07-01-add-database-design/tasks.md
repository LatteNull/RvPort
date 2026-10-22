## 1. 数据库设计文档

- [x] 1.1 基于已接受的 OpenSpec 设计创建 `docs/DATABASE_DESIGN.md`。
- [x] 1.2 明确 PostgreSQL 是 MVP 数据库目标，并列出需要使用的 PostgreSQL 类型。
- [x] 1.3 记录全局 Schema 约定，包括 ID、时间字段、状态字段、`jsonb`、软删除和索引。
- [x] 1.4 记录任务状态决策：PostgreSQL 是事实来源，队列只投递 `task_id`。
- [x] 1.5 将数据库设计文档改为中文，并明确后续后端文档默认使用中文。

## 2. 核心 Schema 定义

- [x] 2.1 定义 MVP 用户表 `users`，并明确排除 `roles`、`user_roles`、`project_members`。
- [x] 2.2 定义项目与源码表：`projects`、`source_revisions`、`source_imports`。
- [x] 2.3 定义加密凭据与环境表：`credentials`、`environments`、`environment_snapshots`、`environment_components`。
- [x] 2.4 定义任务编排表：`tasks`、`task_events`、`task_logs`、`tool_runs`。

## 3. 迁移领域 Schema

- [x] 3.1 定义 KB 扫描结果表：`kb_scan_runs`、`findings`。
- [x] 3.2 定义 SBOM 结果表：`sbom_runs`、`sbom_components`、`replacement_candidates`。
- [x] 3.3 定义迁移问题表：`issues`、`issue_sources`、`issue_events`。
- [x] 3.4 定义报告与复检表：`reports`、`report_inputs`、`recheck_runs`、`diff_items`。
- [x] 3.5 定义验证与历史表：`build_runs`、`test_runs`、`archives`、`archive_items`、`audit_logs`。

## 4. 安全、日志与索引

- [x] 4.1 明确 `credentials.encrypted_payload` 的加密要求和凭据遮蔽展示行为。
- [x] 4.2 明确 `source_revisions.git_url`、命令摘要、审计详情和日志摘要必须脱敏。
- [x] 4.3 明确完整日志本地保存、按天打包，数据库只存元数据。
- [x] 4.4 为每张表定义必需索引、唯一约束和可选 GIN 索引。

## 5. 校验

- [x] 5.1 使用 `openspec validate add-database-design` 校验 OpenSpec change。
- [x] 5.2 按 MVP 产品文档和 API 设计复核数据库设计。
- [x] 5.3 确认待定问题：加密密钥存储、保留周期、项目名称唯一性、当前源码版本约束。
