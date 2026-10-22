# add-database-migrations 设计

## 设计目标

将后端数据库设计从文档状态推进到可执行、可重复、可验证的 Liquibase 迁移状态。迁移脚本需要直接面向 PostgreSQL，作为后续 jOOQ codegen、认证用户管理、任务运行时和领域模块的 schema 基线。

## 迁移组织方式

采用 Liquibase master changelog + PostgreSQL formatted SQL changelog：

```text
src/main/resources/db/changelog/
├─ db.changelog-master.yaml
└─ changes/
   ├─ 0001-extensions.sql
   ├─ 0010-users.sql
   ├─ 0020-projects-sources.sql
   ├─ 0030-credentials-environments.sql
   ├─ 0040-tasks-events-logs.sql
   ├─ 0050-kb-sbom.sql
   ├─ 0060-issues.sql
   ├─ 0070-reports-rechecks.sql
   └─ 0080-validation-archives-audit.sql
```

选择 formatted SQL 的原因：

- PostgreSQL 的局部唯一索引、`CHECK` 约束、`jsonb`、`inet`、`bytea`、`gen_random_uuid()` 用 SQL 表达更直接。
- jOOQ codegen 看到的 schema 与实际 DDL 完全一致。
- 后续排查数据库问题时，SQL changelog 比 YAML DDL 更贴近 PostgreSQL 运维习惯。

## 依赖顺序

表之间存在较多外键依赖，迁移顺序应从根实体和共享实体向领域结果推进：

```text
pgcrypto
  ↓
users
  ↓
projects
  ↓
source_revisions / source_imports
  ↓
credentials / environments / environment_snapshots / environment_components
  ↓
tasks / task_events / task_logs / tool_runs
  ↓
kb_scan_runs / findings
  ↓
sbom_runs / sbom_components / replacement_candidates
  ↓
issues / issue_sources / issue_events
  ↓
reports / report_inputs / recheck_runs / diff_items
  ↓
build_runs / test_runs / archives / archive_items / audit_logs
```

其中 `source_imports.task_id`、`environment_snapshots.task_id` 等跨组引用需要在创建顺序上谨慎处理。优先策略是：先创建被依赖表，再创建引用表；如果循环依赖不可避免，使用后置 `ALTER TABLE ADD CONSTRAINT` 处理。

## 主键和默认值

大多数业务表使用：

```sql
id uuid primary key default gen_random_uuid()
```

`task_events` 使用：

```sql
id bigserial primary key
```

原因是 `task_events.id` 需要作为项目级 SSE 断线恢复的单调游标。

时间字段使用：

```sql
created_at timestamptz not null default now()
updated_at timestamptz
deleted_at timestamptz
```

不可变事实表不默认提供 `deleted_at`，用户可见生命周期对象按数据库设计提供软删除字段。

## 状态字段和约束

MVP 阶段使用 `text + CHECK`，不使用 PostgreSQL enum。这样后续扩展状态不需要先执行 enum alteration，也更适合早期迭代。

典型约束包括：

- `users.status in ('ACTIVE', 'DISABLED')`
- `projects.status in ('ACTIVE', 'ARCHIVED')`
- `projects.stage` 限定为数据库设计中的导航提示集合
- `tasks.status in ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT')`
- `tasks.progress between 0 and 100`
- `source_revisions.revision_type in ('ARCHIVE', 'GIT')`
- `environment.role in ('SOURCE_X86', 'TARGET_RISCV', 'GENERAL_EXECUTION')`

约束目标是保护核心数据边界，不追求把所有业务规则都塞进数据库。

## 默认超级管理员初始化

Liquibase seed 创建默认超级管理员，要求幂等：

```text
username = admin
password input = admin123
is_super_admin = true
must_change_password = true
status = ACTIVE
```

数据库只保存预计算后的 Argon2id `password_hash`，不得保存 `admin123` 明文。

该 seed 适合放在 `0010-users.sql` 中，并使用 `INSERT ... SELECT ... WHERE NOT EXISTS` 或 PostgreSQL `ON CONFLICT DO NOTHING` 保证重复执行不会创建重复管理员。

安全取舍：

- 优点：空库迁移后立即可用，适合本地和 MVP 自管部署。
- 风险：默认密码众所周知，因此必须设置 `must_change_password = true`，认证流程实现后必须强制首次改密。
- 后续生产部署可以通过环境变量覆盖默认管理员初始化策略，或迁移到专门初始化命令。

## 索引策略

本变更只创建数据库设计中明确要求的必需索引和少量低风险唯一索引：

- 外键常用查询列索引：`project_id`、`task_id`、`source_revision_id`、`environment_id` 等。
- 列表页常用排序索引：`(project_id, created_at desc)`、`(project_id, started_at desc)`。
- 状态恢复索引：`tasks(status)`、`tasks(type, status)`。
- SSE 恢复索引：`task_events(project_id, id)`、`task_events(task_id, id)`。
- 用户唯一约束：`users(username)`、`users(email) where email is not null`。

JSONB GIN 索引只在数据库设计明确为可选时暂不创建，除非 apply 阶段发现已有接口必须依赖该查询。

## jOOQ codegen 关系

本变更只创建真实 PostgreSQL schema，不生成 jOOQ 代码。正确顺序是：

```text
空 PostgreSQL
  -> Liquibase 迁移 schema
  -> jOOQ codegen 读取迁移后的 schema
  -> 后续 Repository/DAO 使用生成代码
```

jOOQ codegen 不得作为 schema 创建入口。

## 验证策略

建议 apply 阶段至少验证：

- `mvn test` 通过。
- `openspec validate add-database-migrations` 通过。
- 使用当前 Docker Compose PostgreSQL 或 Testcontainers PostgreSQL 启用 Liquibase 后，空库迁移成功。
- 查询确认核心表存在。
- 查询确认默认 `admin` 用户存在，`is_super_admin = true`，`must_change_password = true`，且 `password_hash` 不等于 `admin123`。
- 查询确认 MVP 排除表不存在，例如 `roles`、`user_roles`、`project_members`、`artifacts`、`test_cases`、用户 action token 表。

## 未解决问题

- Argon2id 默认管理员 hash 的具体参数需要与当前 Spring Security `Argon2PasswordEncoder` 对齐。
- 项目名称唯一性仍按数据库设计保持“不强制全局唯一”。
- 当前源码版本 `source_revisions(project_id) where is_active` 是否使用局部唯一索引，建议本变更使用该约束保护数据一致性。
- 是否将本地开发 `RVPORT_LIQUIBASE_ENABLED` 默认改为 `true`：建议保持默认 `false`，通过命令或环境变量显式开启迁移。
