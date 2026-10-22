# Project access boundaries

English | [简体中文](project-access-guard.zh-CN.md)

## Authorization model

The MVP does not introduce roles, a project-membership table, or RBAC. Project resource access depends on two facts:

- Ordinary users can access only projects whose `projects.created_by` equals their user ID.
- Users with `is_super_admin=true` can access every project that has not been soft-deleted.

## Responses for unauthorized access

Project resources use an anti-enumeration policy. When an ordinary user accesses another user's project, task, environment, source revision, task log, or project SSE stream, the backend returns the same `404` response used for a nonexistent resource.

Common error codes:

- `PROJECT_NOT_FOUND`: the project does not exist or the current user cannot access it.
- `TASK_NOT_FOUND`: the task does not exist or its project is inaccessible.
- `ENVIRONMENT_NOT_FOUND`: the environment does not exist or its project is inaccessible.
- `SOURCE_REVISION_NOT_FOUND`: the revision does not exist, does not belong to the project in the URL, or the project is inaccessible.
- `TASK_LOG_NOT_FOUND`: the log does not exist, does not belong to the task, or the task's project is inaccessible.

## Protected API scope

Project APIs:

- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{projectId}`
- `PATCH /api/projects/{projectId}`
- `GET /api/projects/{projectId}/overview`

Source APIs:

- `GET /api/projects/{projectId}/sources`
- `POST /api/projects/{projectId}/sources/archive`
- `POST /api/projects/{projectId}/sources/git-sync`
- `POST /api/projects/{projectId}/sources/{sourceRevisionId}/activate`

Environment APIs:

- `GET /api/projects/{projectId}/environments`
- `POST /api/projects/{projectId}/environments`
- `GET /api/environments/{environmentId}`
- `PATCH /api/environments/{environmentId}`
- `GET /api/environments/{environmentId}/snapshots`
- `POST /api/projects/{projectId}/environments/{environmentId}/test-connection`
- `POST /api/projects/{projectId}/environments/{environmentId}/check`
- `POST /api/projects/{projectId}/environments/{environmentId}/collect`
- `POST /api/projects/{projectId}/environments/{environmentId}/scripts`

Task APIs:

- `GET /api/projects/{projectId}/tasks`
- `GET /api/tasks/{taskId}`
- `POST /api/tasks/{taskId}/cancel`
- `GET /api/tasks/{taskId}/logs`
- `GET /api/tasks/{taskId}/logs/{logId}/download`
- `GET /api/projects/{projectId}/task-events`

## SSE access rules

Project SSE must check access before creating `SseEmitter`. An authorization failure must not replay historical events.

Recovery continues to use:

```text
project_id = projectId in the URL
AND task_events.id > Last-Event-ID
ORDER BY id ASC
```

Even though global event IDs increase monotonically, replay queries return events only for the current project. The frontend must still filter concurrent task events within that project by `taskId`.
