## Context

当前源码版本由 `source_revisions` 记录，后端内部持有 `working_copy_path`。环境由 `environments` 记录，其中 `working_directory` 已作为远端工作目录配置。后续构建验证应在远端环境中运行，因此需要先把某个源码版本部署到该环境的受控目录。

已有任务运行时已经提供 PostgreSQL 任务事实、RabbitMQ 投递、Worker handler、任务日志、项目级 SSE、任务级日志 SSE 和取消机制；已有 SSH runtime 支持短生命周期 SSH session、跳板机、命令执行和日志采集。源码部署应复用这些能力，不新增独立运行通道。

## Goals / Non-Goals

**Goals:**

- 支持把指定 `sourceRevision` 部署到一个或多个 SSH 环境，覆盖 x86 原始环境和 RISC-V 目标环境的双环境构建验证前置需求。
- 部署路径使用 `environment.working_directory` 作为根路径，并由后端生成。
- 记录源码部署运行事实，供查询、审计、SSE 展示和后续构建验证引用。
- 支持部署任务取消、失败落库、日志查看和重复部署复用。
- 不向 API 响应、任务事件或日志暴露后端本机源码路径。

**Non-Goals:**

- 本 change 不实现构建验证任务本身。
- 本 change 不实现前端页面。
- 本 change 不引入 rsync、agent 常驻进程或远端服务端组件。
- 本 change 不允许前端传入任意远端部署路径。

## Decisions

### 使用独立 `source_deploy_runs` 表记录部署事实

新增表记录每次部署运行：

| 字段 | 类型 | 属性 | 说明 |
| --- | --- | --- | --- |
| `id` | uuid | PK | 源码部署运行 ID |
| `project_id` | uuid | not null, FK, index | 所属项目 |
| `task_id` | uuid | not null, FK, unique | 关联 `SOURCE_DEPLOY` 任务 |
| `source_revision_id` | uuid | not null, FK, index | 被部署的源码版本 |
| `environment_id` | uuid | not null, FK, index | 目标环境 |
| `remote_path` | text | not null | 后端生成的远端部署目录 |
| `deploy_strategy` | varchar | not null | MVP 固定为 `TAR_OVER_SSH` |
| `force` | boolean | not null default false | 是否强制覆盖重新部署 |
| `status` | varchar | not null, index | 与任务终态保持一致 |
| `file_count` | integer | nullable | 部署文件数量 |
| `total_bytes` | bigint | nullable | 部署总字节数 |
| `exit_code` | integer | nullable | 远端命令退出码 |
| `summary` | jsonb | nullable | 脱敏摘要，例如耗时、压缩大小、远端 tar 版本 |
| `started_at` | timestamptz | nullable | 开始时间 |
| `finished_at` | timestamptz | nullable | 结束时间 |
| `created_at` | timestamptz | not null | 创建时间 |

索引：

- `idx_source_deploy_runs_project_created_at(project_id, created_at desc)`
- `idx_source_deploy_runs_source_env_created_at(source_revision_id, environment_id, created_at desc)`
- `idx_source_deploy_runs_status_created_at(status, created_at desc)`
- `uk_source_deploy_runs_task(task_id)`

不对 `source_revision_id + environment_id` 加唯一约束，因为 `force=true` 和失败重试都需要保留历史记录。

### API 使用项目作用域创建，详情按部署 ID 查询

新增 API：

- `POST /api/projects/{projectId}/source-deployments`
- `GET /api/projects/{projectId}/source-deployments`
- `GET /api/source-deployments/{sourceDeploymentId}`
- `POST /api/source-deployments/{sourceDeploymentId}/cancel`

创建请求：

```json
{
  "sourceRevisionId": "uuid",
  "environmentIds": ["uuid"],
  "force": false,
  "timeoutSeconds": 3600
}
```

列表必须支持分页、排序和过滤，至少支持 `sourceRevisionId`、`environmentId`、`status`、`createdAt` 时间范围，排序字段至少支持 `createdAt`、`startedAt`、`finishedAt`、`status`。

### 远端路径由后端生成

部署路径规则：

```text
<environment.working_directory>/rvport-sources/<sourceRevisionId>
```

创建部署任务时必须校验：

- 当前用户有项目权限。
- `sourceRevision` 属于 URL 中的项目。
- 每个 `environment` 都属于 URL 中的项目且已启用。
- 每个 `environment.working_directory` 非空，否则返回 `ENVIRONMENT_WORKING_DIRECTORY_REQUIRED`。
- `source_revisions.working_copy_path` 存在且后端可读，否则返回 `SOURCE_REVISION_WORKING_COPY_NOT_FOUND`。

前端不能提交 `remotePath`。这样后续构建验证可以稳定使用部署记录的 `remote_path`，同时避免用户通过 API 诱导后端写入任意远端路径。

### MVP 使用 tar over SSH

部署 handler 在后端本机从源码工作副本创建 tar 流，通过 SSH stdin 传给远端命令：

```sh
set -e
rm -rf "$DEPLOY_PATH.tmp"
mkdir -p "$DEPLOY_PATH.tmp"
tar -xzf - -C "$DEPLOY_PATH.tmp"
rm -rf "$DEPLOY_PATH"
mv "$DEPLOY_PATH.tmp" "$DEPLOY_PATH"
```

远端路径必须来自后端生成规则并进行 shell quote。远端缺少 `tar` 时任务失败，错误码使用 `SOURCE_DEPLOY_REMOTE_TAR_REQUIRED`。失败时尽力清理临时目录。

### 重复部署默认复用，强制部署显式覆盖

当 `force=false`：

- 若同一项目、源码版本、环境已有 `PENDING`、`QUEUED` 或 `RUNNING` 部署，返回该部署关联任务。
- 若已有最近一次 `SUCCEEDED` 部署，返回该成功部署关联任务或部署详情，不重复传输。
- 若最近一次为 `FAILED`、`CANCELLED` 或 `TIMEOUT`，创建新部署任务。

当 `force=true`，为请求中的每个环境始终创建新部署任务，并覆盖后端生成的远端目录。

### 构建验证后续引用部署结果

后续构建验证 API 应引用成功的 `source_deploy_runs`：

- 前端先触发源码部署。
- 部署成功后再创建构建验证任务。
- 构建验证运行目录使用 `source_deploy_runs.remote_path`。

不在构建验证创建时隐式部署源码，避免一个 API 同时承担传输、覆盖和构建两个副作用。

## Risks / Trade-offs

- 远端没有 `tar` 会导致部署失败 → 连接检查和失败摘要中明确提示缺失工具，后续可扩展为替代传输策略。
- 大源码部署时间较长 → 使用异步任务、SSE、任务级日志和取消机制承载。
- `tar over SSH` 不做增量同步 → MVP 优先保证可用性和可审计性，后续可新增 rsync strategy。
- 覆盖远端目录存在误删风险 → 远端路径只能由后端生成，且固定在 `working_directory/rvport-sources/<sourceRevisionId>` 下。
- 远端路径可能暴露环境目录结构 → API 不暴露后端本机路径；远端路径属于用户配置环境的一部分，响应中可返回用于构建引用和排查。

## Migration Plan

- 新增 Liquibase changeset 创建 `source_deploy_runs` 表和索引。
- 运行 jOOQ 生成脚本更新 generated sources。
- 新增 API、service、repository、handler 和测试。
- 回滚时可删除源码部署 API 和 handler；数据库表可保留历史记录或通过 Liquibase rollback 删除。

## Open Questions

- 后续是否需要增加 `RSYNC_OVER_SSH` 增量策略。
- 后续构建验证 API 是要求传 `sourceDeploymentId`，还是默认选择同环境下当前源码版本最近一次成功部署。
