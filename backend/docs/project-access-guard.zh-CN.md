# 项目访问边界

[English](project-access-guard.md) | 简体中文

## 权限模型

MVP 阶段不引入角色、项目成员表或 RBAC。项目级资源访问只依赖两个事实：

- 普通用户只能访问 `projects.created_by` 等于当前用户 ID 的项目。
- `is_super_admin=true` 的用户可以访问所有未软删除项目。

## 无权限响应策略

项目级资源使用防枚举策略。普通用户访问他人项目、任务、环境、源码版本、任务日志或项目级 SSE 时，后端返回与资源不存在一致的 `404` 错误。

常见错误码：

- `PROJECT_NOT_FOUND`：项目不存在或当前用户无权访问。
- `TASK_NOT_FOUND`：任务不存在或任务所属项目不可访问。
- `ENVIRONMENT_NOT_FOUND`：环境不存在或环境所属项目不可访问。
- `SOURCE_REVISION_NOT_FOUND`：源码版本不存在、不属于 URL 中项目或项目不可访问。
- `TASK_LOG_NOT_FOUND`：任务日志不存在、不属于该任务或任务所属项目不可访问。

## 已保护的 API 范围

项目 API：

- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{projectId}`
- `PATCH /api/projects/{projectId}`
- `GET /api/projects/{projectId}/overview`

源码 API：

- `GET /api/projects/{projectId}/sources`
- `POST /api/projects/{projectId}/sources/archive`
- `POST /api/projects/{projectId}/sources/git-sync`
- `POST /api/projects/{projectId}/sources/{sourceRevisionId}/activate`

环境 API：

- `GET /api/projects/{projectId}/environments`
- `POST /api/projects/{projectId}/environments`
- `GET /api/environments/{environmentId}`
- `PATCH /api/environments/{environmentId}`
- `GET /api/environments/{environmentId}/snapshots`
- `POST /api/projects/{projectId}/environments/{environmentId}/test-connection`
- `POST /api/projects/{projectId}/environments/{environmentId}/check`
- `POST /api/projects/{projectId}/environments/{environmentId}/collect`
- `POST /api/projects/{projectId}/environments/{environmentId}/scripts`

任务 API：

- `GET /api/projects/{projectId}/tasks`
- `GET /api/tasks/{taskId}`
- `POST /api/tasks/{taskId}/cancel`
- `GET /api/tasks/{taskId}/logs`
- `GET /api/tasks/{taskId}/logs/{logId}/download`
- `GET /api/projects/{projectId}/task-events`

## SSE 访问规则

项目级 SSE 必须先校验项目访问权限，再创建 `SseEmitter`，并且在权限校验失败时不能补发历史事件。

恢复逻辑仍使用：

```text
project_id = URL 中的 projectId
AND task_events.id > Last-Event-ID
ORDER BY id ASC
```

因此即使全局事件 ID 是递增的，补发查询也只会返回当前项目的事件。前端仍需要按 `taskId` 过滤同一项目内的并发任务事件。
