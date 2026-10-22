## ADDED Requirements

### Requirement: 任务 API 和 SSE 必须执行项目访问守卫
任务运行时 SHALL 对任务查询、取消、日志访问、日志下载和项目级 SSE 执行项目访问守卫，防止用户通过任务 ID、日志 ID 或 SSE 游标读取其他用户项目事件。

#### Scenario: 查询项目任务列表
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/tasks`
- **THEN** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 无权限时 SHALL 返回与项目不存在一致的安全错误

#### Scenario: 查询任务详情
- **WHEN** 已登录用户调用 `GET /api/tasks/{taskId}`
- **THEN** 后端 SHALL 根据 `tasks.project_id` 校验当前用户有权访问任务所属项目
- **AND** 无权限时 SHALL 返回与任务不存在一致的安全错误

#### Scenario: 取消任务
- **WHEN** 已登录用户调用 `POST /api/tasks/{taskId}/cancel`
- **THEN** 后端 SHALL 根据任务所属项目校验当前用户有权访问该任务
- **AND** 无权限时 SHALL 拒绝取消且 MUST NOT 改变任务状态

#### Scenario: 查询任务日志
- **WHEN** 已登录用户调用 `GET /api/tasks/{taskId}/logs`
- **THEN** 后端 SHALL 根据任务所属项目校验当前用户有权访问该任务
- **AND** 无权限时 SHALL 返回与任务不存在一致的安全错误
- **AND** 后端 MUST NOT 返回日志摘要、大小、类型或创建时间

#### Scenario: 下载任务日志
- **WHEN** 已登录用户调用 `GET /api/tasks/{taskId}/logs/{logId}/download`
- **THEN** 后端 SHALL 校验任务可访问且日志属于该任务
- **AND** 无权限、任务不存在、日志不存在或日志不属于该任务时 SHALL 返回安全错误
- **AND** 后端 MUST NOT 返回服务器真实路径

#### Scenario: 建立项目级 SSE
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/task-events`
- **THEN** 后端 SHALL 在创建 SSE emitter 前校验当前用户有权访问该项目
- **AND** 无权限时 SHALL 拒绝请求
- **AND** 无权限时 MUST NOT 创建 emitter、注册订阅或补发历史事件

#### Scenario: 使用 Last-Event-ID 恢复 SSE
- **WHEN** 有项目访问权限的用户携带 `Last-Event-ID` 重新连接
- **THEN** 后端 SHALL 只补发同一项目内 `id` 大于该值的事件
- **AND** 后端 MUST NOT 因全局自增事件 ID 补发其他项目事件
