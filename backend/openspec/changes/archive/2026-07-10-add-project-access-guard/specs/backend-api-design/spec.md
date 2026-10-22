## ADDED Requirements

### Requirement: API 必须显式校验项目资源访问权限
所有项目级 API SHALL 在返回项目、源码、环境、任务、任务日志或 SSE 事件之前校验当前用户对所属项目的访问权限。

#### Scenario: 访问项目级资源
- **WHEN** 已登录用户调用带有 `projectId` 的项目、源码、环境、任务列表或 SSE API
- **THEN** 后端 SHALL 校验当前用户可以访问该 `projectId`
- **AND** 普通用户 SHALL 只能访问自己创建的项目
- **AND** 超级管理员 SHALL 能访问任意未软删除项目

#### Scenario: 访问任务和日志资源
- **WHEN** 已登录用户调用只包含 `taskId` 或 `taskId` + `logId` 的任务 API
- **THEN** 后端 SHALL 根据任务所属项目执行项目访问权限校验
- **AND** 日志下载 SHALL 同时校验日志属于该任务

#### Scenario: 拒绝越权访问
- **WHEN** 普通用户访问其他用户项目或其派生资源
- **THEN** API SHALL 返回与资源不存在一致的安全错误
- **AND** API MUST NOT 暴露目标资源是否存在、资源名称、任务状态、日志摘要、源码版本、环境配置或 SSE 事件

#### Scenario: 不引入权限模型字段
- **WHEN** API 返回当前用户、项目、源码、环境、任务或日志数据
- **THEN** API MUST NOT 返回 `roles`、`permissions`、`projectMembers` 或其他 RBAC 字段

### Requirement: 项目级 SSE API 必须在订阅前完成访问校验
项目级 SSE API SHALL 在创建 SSE emitter、注册订阅者或补发历史事件之前完成项目访问权限校验。

#### Scenario: 有权限用户建立 SSE
- **WHEN** 有项目访问权限的用户调用 `GET /api/projects/{projectId}/task-events`
- **THEN** 后端 SHALL 建立 `text/event-stream` 响应
- **AND** 后端 SHALL 只推送该项目的任务事件

#### Scenario: 无权限用户建立 SSE
- **WHEN** 无项目访问权限的用户调用 `GET /api/projects/{projectId}/task-events`
- **THEN** 后端 SHALL 拒绝请求
- **AND** 后端 MUST NOT 创建 SSE emitter
- **AND** 后端 MUST NOT 补发历史任务事件
