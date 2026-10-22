## Purpose

定义 RvPort 后端 MVP 项目访问守卫的授权边界、派生资源归属校验、无权限错误策略和测试覆盖要求。

## Requirements

### Requirement: 项目访问守卫必须统一项目资源授权
后端 SHALL 提供统一项目访问守卫，用于所有项目级资源 API 的授权判断，并 SHALL 以 `projects.created_by` 和当前用户 `isSuperAdmin` 作为 MVP 授权依据。

#### Scenario: 普通用户访问自己创建的项目
- **WHEN** 已登录普通用户访问 `created_by` 等于当前用户 ID 的项目资源
- **THEN** 项目访问守卫 SHALL 允许访问

#### Scenario: 普通用户访问其他用户项目
- **WHEN** 已登录普通用户访问 `created_by` 不等于当前用户 ID 的项目资源
- **THEN** 项目访问守卫 SHALL 拒绝访问
- **AND** 后端 SHALL 返回与资源不存在一致的安全错误
- **AND** 后端 MUST NOT 暴露该项目是否存在、项目名称、环境、源码、任务或日志信息

#### Scenario: 超级管理员访问任意项目
- **WHEN** 已登录用户的 `isSuperAdmin` 为 `true`
- **THEN** 项目访问守卫 SHALL 允许其访问任意未软删除项目资源

#### Scenario: 项目不存在或已软删除
- **WHEN** 用户访问不存在或已软删除项目
- **THEN** 项目访问守卫 SHALL 返回 `PROJECT_NOT_FOUND`

### Requirement: 项目访问守卫必须覆盖派生资源归属
后端 SHALL 对任务、任务日志、环境、源码版本、源码导入、凭据和 SSE 等派生资源先解析所属项目，再执行统一项目访问守卫。

#### Scenario: 按任务 ID 校验访问权限
- **WHEN** 用户访问 `GET /api/tasks/{taskId}`、`POST /api/tasks/{taskId}/cancel`、`GET /api/tasks/{taskId}/logs` 或日志下载接口
- **THEN** 后端 SHALL 根据 `tasks.project_id` 解析所属项目
- **AND** 后端 SHALL 对该项目执行项目访问守卫
- **AND** 无权限或任务不存在时 SHALL 返回与任务不存在一致的安全错误

#### Scenario: 按任务日志 ID 校验访问权限
- **WHEN** 用户访问 `GET /api/tasks/{taskId}/logs/{logId}/download`
- **THEN** 后端 SHALL 验证日志存在且属于该任务
- **AND** 后端 SHALL 根据任务所属项目执行项目访问守卫
- **AND** 无权限、任务不存在、日志不存在或日志不属于该任务时 SHALL 返回安全错误

#### Scenario: 按环境 ID 校验访问权限
- **WHEN** 用户访问环境详情、更新、快照或环境运行 API
- **THEN** 后端 SHALL 根据 `environments.project_id` 执行项目访问守卫
- **AND** 无权限时 SHALL 返回与环境不存在一致的安全错误

#### Scenario: 按源码版本 ID 校验访问权限
- **WHEN** 用户访问源码版本切换或其他源码版本详情类 API
- **THEN** 后端 SHALL 验证源码版本属于 URL 中的项目
- **AND** 后端 SHALL 对 URL 中的项目执行项目访问守卫
- **AND** 无权限时 SHALL 返回与源码版本或项目不存在一致的安全错误

#### Scenario: 按项目 ID 校验 SSE 订阅
- **WHEN** 用户访问 `GET /api/projects/{projectId}/task-events`
- **THEN** 后端 SHALL 在创建 SSE emitter 和补发历史事件之前执行项目访问守卫
- **AND** 无权限时 MUST NOT 创建 SSE 订阅
- **AND** 无权限时 MUST NOT 补发任何 `task_events`

### Requirement: 项目访问守卫不得引入角色权限模型
项目访问守卫 SHALL 保持 MVP 权限边界，不 SHALL 引入角色、权限、项目成员、团队或组织模型。

#### Scenario: 设计访问判断
- **WHEN** 后端判断用户是否可访问项目资源
- **THEN** 判断 SHALL 只依赖当前用户 ID、`isSuperAdmin` 和项目归属字段
- **AND** 后端 MUST NOT 要求角色表、权限表、用户角色映射表或项目成员表

#### Scenario: API 响应不暴露权限模型
- **WHEN** API 返回项目、源码、环境、任务或用户信息
- **THEN** 响应 MUST NOT 返回 `roles`、`permissions` 或 `projectMembers`

### Requirement: 项目访问守卫必须配套测试覆盖
项目访问守卫 SHALL 配套单元测试和 API E2E 覆盖，并 SHALL 满足正常流程、异常流程和 edge case 测试策略。

#### Scenario: 覆盖正常流程
- **WHEN** 为项目访问守卫编写测试
- **THEN** 测试 SHALL 覆盖普通用户访问自己项目和超级管理员访问任意项目

#### Scenario: 覆盖异常流程
- **WHEN** 为项目访问守卫编写测试
- **THEN** 测试 SHALL 覆盖普通用户访问其他用户项目、任务、任务日志、源码、环境和 SSE 的拒绝路径

#### Scenario: 覆盖 edge case
- **WHEN** 为项目访问守卫编写测试
- **THEN** 测试 SHALL 覆盖项目不存在、任务不存在、日志不属于任务、源码版本不属于项目、环境不属于项目、软删除项目和 SSE 非法 `Last-Event-ID`
