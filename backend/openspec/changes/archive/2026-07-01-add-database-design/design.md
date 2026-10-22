## 背景

RvPort 是一个面向 x86 到 RISC-V 的迁移评估与验证平台。MVP 工作流覆盖项目创建、源码导入、SSH 环境管理、KB 扫描、SBOM 替代分析、迁移问题汇总、报告生成、修复后复检差异、RISC-V 构建、自动化测试、归档快照和审计。

`backend` 目录此前没有后端实现和数据库 Schema。父项目文档曾提到 PostgreSQL/MySQL 都可能作为存储，但当前 MVP 已确认使用 PostgreSQL。数据库需要支持长时间异步任务、本地日志、平台自管加密凭据、可复现工具结果和报告追溯。

详细字段定义以 `docs/DATABASE_DESIGN.md` 为准；本文件记录 OpenSpec change 的关键设计判断。

## 目标 / 非目标

**目标：**

- 定义后端 MVP 的 PostgreSQL 数据模型。
- 让 PostgreSQL 成为任务状态、任务事件和业务结果的事实来源。
- 保持队列载荷最小化，队列只投递 `task_id`。
- 将平台自管凭据保存为加密载荷。
- 完整日志留在文件系统，数据库只保存本地日志元数据，日志按天打包。
- 区分工具事实和用户管理的迁移问题。
- 对源码版本和环境快照做版本化，保证报告和复检可追溯。
- MVP 测试结果只保存摘要字段。
- MVP 只保留本地用户，不设计用户角色、用户角色映射和项目成员。
- 增加 `users.is_super_admin`，并由环境初始化脚本首次运行时创建默认超级管理员。

**非目标：**

- MVP 不引入通用 artifact 表。
- MVP 不解析或持久化 JUnit、CTest、pytest 等详细测试用例报告。
- MVP 不设计 AI Agent 补丁生成、benchmark/profiling、RVV 优化或浮点分析的专用表，只保留扩展模式。
- MVP 不接入外部 Secret Manager。
- MVP 不提供 MySQL 兼容层。
- MVP 不包含用户角色或项目成员 Schema。

## 关键决策

### PostgreSQL 是 MVP 数据库

使用 PostgreSQL 特有或适配良好的类型：

- `uuid`：实体 ID。
- `timestamptz`：时间字段。
- `jsonb`：任务输入快照、工具摘要、环境快照、报告摘要和元数据。
- `inet`：审计 IP 地址。
- `bytea`：加密凭据载荷。

考虑过 MySQL，但任务输入、扫描输出、环境快照和报告摘要更适合使用 `jsonb` 和可选 GIN 索引，因此 MVP 选择 PostgreSQL。

### PostgreSQL 是任务状态事实来源

队列只投递 `task_id`。API、worker、SSE 恢复、项目概览聚合和报告生成都从 PostgreSQL 读取权威状态。

核心任务表：

```text
tasks
task_events
task_logs
tool_runs
```

`tasks` 保存当前状态；`task_events` 保存只追加的状态、进度和日志摘要事件，用于 SSE 恢复；`task_logs` 保存本地日志文件元数据；`tool_runs` 保存任务内部工具调用元数据。

不把任务状态放在 Redis/RabbitMQ 中，因为服务重启、worker 崩溃和 SSE 重连都需要持久状态和可回放事件。

### 凭据隔离并加密

凭据使用独立 `credentials` 表。环境和源码导入通过 ID 引用凭据。API 只能返回遮蔽摘要，不能返回解密载荷。

需要加密的字段：

- `credentials.encrypted_payload bytea`：保存 SSH 密码、SSH 私钥、Git 密码或未来其他凭据载荷。

默认不加密但必须注意安全的字段：

- `environments.host`：MVP 视为普通元数据，部署策略可要求加密。
- `environments.username`：MVP 视为普通元数据。
- `source_revisions.git_url`：必须脱敏，禁止内嵌 token；凭据必须移入 `credentials`。

### 日志本地保存，PostgreSQL 只存元数据

完整 stdout/stderr/task 日志写入本地文件。PostgreSQL 保存路径、日志日期、归档路径、哈希、大小和短摘要。每日打包流程可更新 `archive_path`。

MVP 不引入通用 `artifacts` 表。报告和归档可以在自己的业务表上直接保存本地路径。

### 工具事实与用户问题分离

`findings`、`sbom_components`、`replacement_candidates` 表示工具事实。`issues` 表示用户管理的迁移问题。`issue_sources` 负责把一个问题映射到一个或多个 finding、SBOM component 或未来分析器输出。

这样可以保留来源追溯，也允许用户忽略或解决问题，而不修改原始工具输出。

### 项目阶段只是导航提示

`projects.stage` 只作为项目列表和概览页的缓存式导航提示，不作为权威线性状态机。

迁移工作流是迭代式的。报告、构建或测试之后，开发者可能重新导入修复后的代码，使项目回到源码导入、扫描、报告或等待修复等阶段提示。

项目真实状态必须从以下数据推导：

- 当前启用的 `source_revisions`。
- 最新的 `tasks`。
- 最新领域运行表：`kb_scan_runs`、`sbom_runs`、`reports`、`recheck_runs`、`build_runs`、`test_runs`。
- 当前 `issues` 和 `diff_items`。

### 用户模型保持 MVP 简化

MVP 只保留 `users` 表，不引入 `roles`、`user_roles`、`project_members`。

`users.is_super_admin` 用于标记超级管理员。环境初始化脚本第一次成功运行时，如果不存在 `username = 'admin'`，应创建默认超级管理员，初始密码输入为 `admin123`。数据库只能保存派生的 `password_hash`，不得保存明文密码。初始化脚本必须幂等。

## 表分组

```text
用户
  users

项目与源码
  projects
  source_revisions
  source_imports

环境与凭据
  credentials
  environments
  environment_snapshots
  environment_components

任务编排
  tasks
  task_events
  task_logs
  tool_runs

KB 扫描
  kb_scan_runs
  findings

SBOM 分析
  sbom_runs
  sbom_components
  replacement_candidates

迁移问题
  issues
  issue_sources
  issue_events

报告与复检
  reports
  report_inputs
  recheck_runs
  diff_items

验证与历史
  build_runs
  test_runs
  archives
  archive_items
  audit_logs
```

## 常见字段约定

多数实体表使用：

```text
id uuid primary key
created_at timestamptz not null default now()
updated_at timestamptz
deleted_at timestamptz -- 仅用户可见生命周期记录使用
```

MVP 状态和类型字段优先使用 `text + CHECK`。如果实现阶段确认取值稳定，可以从一开始使用 PostgreSQL enum。

常见状态：

- 任务状态：`PENDING`、`QUEUED`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED`、`TIMEOUT`。
- 项目阶段提示：`PROJECT_CREATED`、`SOURCE_IMPORTED`、`ENV_CONFIGURED`、`SCANNING`、`REPORT_GENERATED`、`WAITING_FIX`、`BUILD_PASSED`、`BUILD_FAILED`、`TEST_PASSED`、`TEST_FAILED`、`ARCHIVED`。
- 问题状态：`CANDIDATE`、`CONFIRMED`、`IGNORED`、`RESOLVED`。
- 替代结论：`TARGET_PRESENT`、`DIRECT_AVAILABLE`、`UPGRADE_AVAILABLE`、`SOURCE_BUILD_REQUIRED`、`NO_ALTERNATIVE`、`MANUAL_CONFIRM_REQUIRED`。

## 风险 / 权衡

- [风险] 大量 `jsonb` 字段可能隐藏后续需要索引的字段。缓解方式：用于过滤、排序、关联和报表聚合的字段必须拆成普通列，`jsonb` 只保留追溯和原始摘要。
- [风险] 数据库里的本地路径在文件被手工移动后可能失效。缓解方式：统一由后端管理路径生成和每日打包目录。
- [风险] 任务事件增长较快。缓解方式：保留足够支持 UI 恢复的事件，并根据项目保留策略归档或清理历史事件。
- [风险] 平台自管加密带来密钥管理责任。缓解方式：保存 `kms_key_version`，定义轮换流程，日志和审计中永不暴露解密载荷。
- [风险] MVP 不引入通用 artifact 表，未来 artifact 生命周期扩展时可能需要迁移。缓解方式：MVP 保持报告、归档、日志路径显式建模，只有在产品需要跨领域 artifact 管理时再引入 artifact 模型。

## 迁移计划

1. 创建基础用户和项目表迁移脚本。
2. 添加凭据和环境表。
3. 在实现 worker 前添加任务、事件、日志和工具运行表。
4. 添加 KB 扫描和 SBOM 结果表。
5. 添加问题、报告、复检、构建、测试、归档和审计表。
6. 使用代表性 MVP 查询验证索引和外键。

早期 MVP 尚无生产数据时，可以通过删除新增 Schema 对象回滚。一旦存在生产数据，回滚必须先保留导出备份和加密凭据材料。

## 待确认问题

- `credentials.encrypted_payload` 使用哪种加密库和密钥存储机制？
- 任务事件、未打包日志、每日日志归档、报告和项目归档的保留周期是什么？
- 项目名称应该全局唯一、按创建人唯一，还是允许重复？
- 当前启用源码版本是否用局部唯一索引强约束，还是只在服务层管理？
