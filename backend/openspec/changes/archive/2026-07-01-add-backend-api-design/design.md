## 背景

API 设计覆盖页面触发、REST API、Task API、SSE、工具契约和前端字段映射。

数据库结构见 [数据库说明](../../../../docs/DATABASE_DESIGN.md)。设计明确了以下边界：

- PostgreSQL 是任务状态事实来源。
- 队列只投递 `task_id`。
- 不引入通用 `artifacts` 表。
- MVP 不做用户角色、用户角色映射和项目成员。
- 用户通过 `users.is_super_admin` 标记超级管理员。
- 完整日志保存在本地文件系统，数据库只保存元数据和摘要。
- MVP 测试只保存退出码和汇总计数。
- `projects.stage` 只是导航提示，不是权威状态机。

因此 API 文档不能简单复制根目录版本，而应先复制其结构和领域划分，再按数据库设计修正冲突点。

## 设计方向

### 1. API 文档落点

建议后续正式文档写入：

```text
backend/docs/API_DESIGN.md
```

文档保持中文，接口路径、字段名、枚举值、HTTP 方法、SSE 事件名保留英文。

### 2. 推荐文档结构

```text
1. 文档目的与边界
2. 通用 API 约定
3. 认证与当前用户 API
4. 项目与概览 API
5. 源码版本 API
6. 环境与凭据 API
7. 异步任务、SSE 与日志 API
8. KB 扫描 API
9. SBOM 替代分析 API
10. 迁移问题 API
11. 报告与复检 API
12. 构建与测试 API
13. 归档与审计 API
14. 错误码、脱敏与安全规则
15. MVP 不包含内容
```

### 3. URL 与响应约定

保留根目录设计中的基础约定：

- Base URL：`/api`
- JSON 请求：`Content-Type: application/json`
- 文件上传：`multipart/form-data`
- 时间格式：ISO 8601
- 分页字段：`page`、`pageSize`、`total`、`hasMore`

需要补充：

- 请求 ID 和错误响应必须能对应 `audit_logs.request_id`。
- 所有下载接口不能接受任意服务器路径作为参数。
- 响应中的本地文件路径默认不暴露给前端。

### 4. 认证与用户模型

根目录底稿里的 `GET /auth/me` 写着“读取当前用户、角色和权限”，需要改为读取当前本地用户。

建议响应只包含：

```json
{
  "id": "user_001",
  "username": "admin",
  "displayName": "Admin",
  "email": null,
  "isSuperAdmin": true,
  "mustChangePassword": false,
  "status": "ACTIVE"
}
```

MVP 不返回：

- `roles`
- `permissions`
- `projectMembers`

### 4.1 超级管理员用户管理

配置页需要提供用户信息表。超级管理员可以查看所有本地用户，并对普通用户执行增删改查和重置密码。

推荐接口：

```http
GET    /api/admin/users
POST   /api/admin/users
GET    /api/admin/users/{userId}
PATCH  /api/admin/users/{userId}
DELETE /api/admin/users/{userId}
POST   /api/admin/users/{userId}/reset-password
```

`GET /api/admin/users` 用于配置页用户信息表，支持分页、状态筛选和关键词搜索。

创建用户请求：

```json
{
  "username": "developer",
  "displayName": "Developer",
  "email": "dev@example.com",
  "initialPassword": "Temp123456",
  "mustChangePassword": true,
  "status": "ACTIVE"
}
```

重置密码请求：

```json
{
  "newPassword": "Temp123456",
  "mustChangePassword": true
}
```

普通用户修改自己的密码：

```http
POST /api/auth/change-password
```

```json
{
  "currentPassword": "old-password",
  "newPassword": "new-password"
}
```

约束：

- `isSuperAdmin` 不允许通过 API 创建、更新或提升，只能通过初始化脚本或数据库维护方式设置。
- 超级管理员可以创建普通用户、更新普通用户资料、禁用用户、删除用户或重置用户密码。
- MVP 不引入 `roles`、`permissions` 或 `projectMembers`。
- 删除用户建议优先设计为禁用或软删除语义，避免破坏 `created_by`、`audit_logs.user_id` 等历史引用。
- 用户被创建或被重置密码后，如果 `mustChangePassword=true`，登录后只能访问修改密码和退出登录相关接口，直到完成改密。

需要配套数据库补充：

```text
users.must_change_password boolean not null default false
```

邮箱验证暂不进入 MVP，因此不增加 `email_verified_at` 或用户 action token 表。

### 5. 项目 stage 与 overview

`projects.stage` 在 API 中可以返回，但必须标记为 `stageHint` 或说明其只是导航提示。

项目真实状态应由 `GET /projects/{projectId}/overview` 聚合：

```text
active source revision
latest tasks
latest kb_scan_runs / sbom_runs / reports / recheck_runs
latest build_runs / test_runs
current issues / diff_items
```

这能支持修复后代码重新入库，不会被线性 stage 卡死。

### 6. 异步任务与 SSE

API 设计应统一成：

```text
POST 业务动作接口
  -> 创建 tasks 记录
  -> 返回 taskId 和初始 task 状态
  -> API 投递 task_id 到队列

GET /api/tasks/{taskId}
  -> 读取任务当前状态

GET /api/projects/{projectId}/task-events
  -> 项目级 SSE，支持 Last-Event-ID 恢复

GET /api/tasks/{taskId}/logs
  -> 分页读取完整日志或日志片段
```

根目录底稿中的 `GET /tasks/{taskId}/events` 建议不作为 MVP 主路径，避免和项目级 SSE 重复。

任务状态必须补齐：

```text
PENDING
QUEUED
RUNNING
SUCCEEDED
FAILED
CANCELLED
TIMEOUT
```

### 7. 去掉通用 Artifact API

根目录底稿中有 `Artifact` 对象、`/api/artifacts/{id}/download` 和 `artifact.created` 事件。根据数据库设计，MVP 不做通用 artifact 表。

建议改为业务资源下载：

```text
GET /api/reports/{reportId}/download?format=HTML|JSON
GET /api/archives/{archiveId}/download
GET /api/tasks/{taskId}/logs/{logId}/download
```

SSE 事件如果要表达“输出已生成”，建议使用领域事件：

```text
report.generated
archive.created
task.log_archived
```

或者先只使用 `task.succeeded`，由前端通过业务详情接口刷新结果。

### 8. 凭据与环境 API

创建或更新环境时可以提交秘密字段，但响应不能返回明文。

写入请求可以包含：

```json
{
  "loginType": "PASSWORD",
  "username": "root",
  "password": "******"
}
```

读取响应必须变成：

```json
{
  "credential": {
    "configured": true,
    "kind": "SSH_PASSWORD",
    "name": "rv-dev-01",
    "maskedSummary": "root@192.0.2.10"
  }
}
```

### 9. 测试 API 的 MVP 边界

根目录底稿有：

```text
POST /tests/{testRunId}/rerun-failed
POST /tests/compare
```

这两个接口依赖详细测试用例解析或跨环境结构化对比。MVP 数据库只保存：

```text
exit_code
passed_count
failed_count
skipped_count
status
log references
```

因此建议 MVP 暂不提供 `rerun-failed`。`tests/compare` 如保留，只能比较摘要字段，不能承诺用例级对比。

### 10. 对外命名策略

API 可以使用业务友好的名词，不必完全等同数据库表名，但必须容易映射。

推荐保留：

```text
POST /projects/{projectId}/sbom-analyses
GET  /sbom-analyses/{analysisId}
```

内部映射：

```text
sbom_runs.id = analysisId
```

同理：

```text
/builds      -> build_runs
/tests       -> test_runs
/rechecks    -> recheck_runs
/sources     -> source_revisions + source_imports
```

## 风险与待确认

- [风险] 如果 API 文档继续暴露 Artifact 概念，会和数据库设计冲突。建议在 API 文档中明确 MVP 没有通用 Artifact API。
- [风险] 如果 `GET /auth/me` 暴露权限列表，前端可能提前绑定 RBAC。建议只暴露 `isSuperAdmin`。
- [风险] 如果通过 API 允许设置 `isSuperAdmin`，会把超级管理员变成变相角色系统且增加误操作风险。建议 API 永不接受该字段。
- [风险] 如果用户删除做物理删除，历史项目创建人和审计操作人引用会受影响。建议 API 文档优先使用禁用或软删除语义。
- [风险] 如果同时保留任务级 SSE 和项目级 SSE，会增加前端订阅复杂度和后端事件回放复杂度。建议 MVP 只保留项目级 SSE。
- [风险] 如果测试 API 承诺失败用例重跑，会倒逼测试用例解析。建议从 MVP 中移除。
- [待确认] 登录态采用 Session Cookie 还是 Bearer Token。
- [待确认] 报告下载是否使用 `GET /reports/{id}/download?format=...`，还是继续使用 `POST /reports/{id}/export` 创建异步导出任务。
- [待确认] 是否需要单独的凭据管理 API，还是凭据只通过环境和源码配置写入。
- [待确认] API 文档是否需要同时输出 OpenAPI YAML。
- [待确认] `DELETE /api/admin/users/{userId}` 在 MVP 中是禁用用户、软删除用户，还是只提供 `PATCH status=DISABLED` 而不提供删除接口。
