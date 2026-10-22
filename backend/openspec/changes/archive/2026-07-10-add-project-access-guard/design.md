## Context

当前后端认证已经由 Spring Security、Redis Session 和 `RvPortUserPrincipal` 提供，`principal` 中包含用户 ID 和 `superAdmin` 标记。项目数据的所有权目前主要由 `projects.created_by` 表达，MVP 明确不引入角色、权限表或项目成员模型。

现有实现中，部分环境运行接口已经在 service 内校验 `project.created_by == principal.id()` 或 `principal.superAdmin()`，但项目详情、项目概览、源码列表、环境列表、任务详情、任务日志和项目级 SSE 等接口存在只校验登录或只校验资源存在的情况。随着 Git 同步、SSH runtime、任务日志和 SSE 被前端直接使用，项目级访问边界需要统一。

## Goals / Non-Goals

**Goals:**

- 为项目级资源提供统一访问守卫，避免跨用户读取或操作其他用户项目数据。
- 覆盖项目、源码、环境、任务、任务日志、日志下载和项目级 SSE。
- 保持 MVP 权限模型简单：普通用户只能访问自己创建的项目，超级管理员可以访问所有项目。
- 对无权限项目资源使用安全的“不存在”响应，减少资源枚举风险。
- 补充单元测试和 API E2E，覆盖正常流程、异常流程和 edge case。

**Non-Goals:**

- 不引入项目成员、组织、团队、角色、权限表或 RBAC。
- 不改变 session/cookie 认证方案。
- 不修改数据库 schema，除非实现过程中发现现有查询缺少必要索引。
- 不处理前端页面可见性和路由守卫；本 change 只定义后端 API 边界。

## Decisions

### 1. 使用统一 `ProjectAccessService`

新增共享服务集中封装项目访问判断，而不是让每个业务 service 自己复制判断逻辑。

核心方法建议：

- `requireProjectAccess(projectId, actorUserId, superAdmin)`
- `requireTaskAccess(taskId, actorUserId, superAdmin)`
- `requireEnvironmentAccess(environmentId, actorUserId, superAdmin)`
- `requireSourceRevisionAccess(projectId, sourceRevisionId, actorUserId, superAdmin)`
- `requireTaskLogAccess(taskId, logId, actorUserId, superAdmin)`

理由：当前权限判断已经开始分散，继续复制会导致后续新增 API 容易漏校验。统一服务可以同时规范错误码、返回码和审计口径。

替代方案：使用 Spring Method Security 注解。暂不采用，因为当前权限依赖数据库资源归属查询，且不同资源需要不同归属路径；直接注解会让表达式复杂且难测。

### 2. 普通用户按项目创建人授权，超级管理员全局旁路

MVP 规则：

```text
canAccess(project, user):
  user.isSuperAdmin == true
    OR project.createdBy == user.id
```

理由：与现有数据库字段和用户模型一致，不引入新的权限实体。

替代方案：创建项目成员表。暂不采用，因为用户已明确 MVP 不做用户角色和权限模型。

### 3. 无权限项目资源返回安全 404

普通用户访问其他用户项目、任务、环境、源码版本、任务日志或 SSE 时，后端返回与资源不存在一致的错误，例如 `PROJECT_NOT_FOUND`、`TASK_NOT_FOUND`、`ENVIRONMENT_NOT_FOUND`、`SOURCE_REVISION_NOT_FOUND` 或 `TASK_LOG_NOT_FOUND`。

理由：对项目级资源而言，403 会暴露资源存在性；当前环境运行接口已经采用类似策略。

替代方案：统一返回 403。实现简单，但会泄露 ID 是否有效，不适合项目隔离。

### 4. Controller 显式接收 principal，Service 执行访问校验

Controller 负责传入 `principal.id()` 和 `principal.superAdmin()`；业务 service 或访问守卫负责实际数据库校验。

理由：保持 controller 薄，同时不把安全逻辑藏在 repository 查询条件里。对 SSE 这种非 `ApiResponse` 返回也能先校验再创建 emitter。

替代方案：在 filter/interceptor 根据 URL 自动校验。暂不采用，因为 URL 与资源归属关系不完全一致，例如 `/api/tasks/{taskId}/logs/{logId}/download` 需要先根据 task 找 project。

### 5. SSE 先校验项目访问再订阅和补发

`GET /api/projects/{projectId}/task-events` 必须在调用 `taskSseBroker.subscribe(projectId)` 之前完成项目访问校验。未授权时不能创建 emitter，也不能补发历史事件。

理由：SSE 一旦建立就是长连接，如果先 subscribe 再失败，可能留下短暂的连接状态或错误处理不一致。

### 6. 任务和日志按任务所属项目授权

`GET /api/tasks/{taskId}`、`POST /api/tasks/{taskId}/cancel`、`GET /api/tasks/{taskId}/logs`、`GET /api/tasks/{taskId}/logs/{logId}/download` 必须先读取任务所属项目，再按项目访问守卫判断。日志下载还必须校验 `logId` 属于 `taskId`。

理由：这些接口没有显式 `projectId` 路径参数，只能通过 task 反查项目。

## Risks / Trade-offs

- [Risk] 权限守卫引入后，部分现有 E2E 或手工脚本可能因使用普通用户访问历史数据而失败。  
  Mitigation: 更新 E2E 登录用户和测试数据创建流程，确保测试资源由当前用户创建；超级管理员路径单独覆盖。

- [Risk] 项目列表如果继续返回全量项目，会与详情权限不一致。  
  Mitigation: 普通用户项目列表只返回自己创建的项目，超级管理员返回全部未删除项目。

- [Risk] 多个 service 同时修改签名，改动面较大。  
  Mitigation: 先落 `ProjectAccessService` 和 repository 辅助查询，再逐个入口替换；测试按 controller/service 分层补齐。

- [Risk] 404 防枚举策略可能让前端难以区分“资源不存在”和“无权限”。  
  Mitigation: MVP 接受该取舍；前端只展示通用“资源不存在或无权访问”语义。

- [Risk] SSE 的 Spring MVC 测试需要处理 `SseEmitter` 异步响应。  
  Mitigation: 继续使用现有 `TaskSseControllerTests` 的 standalone MockMvc 模式，并增加权限 service mock 验证。
