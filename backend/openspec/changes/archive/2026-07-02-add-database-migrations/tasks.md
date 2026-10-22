# 任务清单

- [x] 梳理 `backend/docs/DATABASE_DESIGN.md` 中所有 MVP 表、字段、约束和索引，形成迁移实现清单。
- [x] 将 `db.changelog-master.yaml` 改为 include 分层 changelog。
- [x] 创建 `0001-extensions.sql`，启用 `pgcrypto`。
- [x] 创建 `0010-users.sql`，包含 `users` 表、约束、索引和默认超级管理员 seed。
- [x] 创建 `0020-projects-sources.sql`，包含 `projects`、`source_revisions`、`source_imports`。
- [x] 创建 `0030-credentials-environments.sql`，包含 `credentials`、`environments`、`environment_snapshots`、`environment_components`。
- [x] 创建 `0040-tasks-events-logs.sql`，包含 `tasks`、`task_events`、`task_logs`、`tool_runs`。
- [x] 创建 `0050-kb-sbom.sql`，包含 `kb_scan_runs`、`findings`、`sbom_runs`、`sbom_components`、`replacement_candidates`。
- [x] 创建 `0060-issues.sql`，包含 `issues`、`issue_sources`、`issue_events`。
- [x] 创建 `0070-reports-rechecks.sql`，包含 `reports`、`report_inputs`、`recheck_runs`、`diff_items`。
- [x] 创建 `0080-validation-archives-audit.sql`，包含 `build_runs`、`test_runs`、`archives`、`archive_items`、`audit_logs`。
- [x] 为外键、状态查询、列表排序、SSE 恢复和唯一性创建必要索引。
- [x] 确认 MVP 排除表未被创建：`roles`、`user_roles`、`project_members`、`artifacts`、`test_cases`、邮箱验证或 action token 表。
- [x] 增加或更新迁移验证测试，确认空库可执行 Liquibase 迁移。
- [x] 验证默认 `admin` 用户初始化幂等，且数据库不保存明文 `admin123`。
- [x] 更新中文后端开发计划，记录 Liquibase 迁移执行方式和 jOOQ codegen 前置条件。
- [x] 执行 `mvn test`。
- [x] 执行 `openspec validate add-database-migrations`。
