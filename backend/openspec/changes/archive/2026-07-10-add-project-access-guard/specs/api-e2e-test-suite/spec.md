## ADDED Requirements

### Requirement: API E2E 必须覆盖项目访问守卫
API E2E 测试套件 SHALL 覆盖项目访问守卫的正常流程、异常流程和 edge case，确保普通用户不能读取或操作其他用户项目资源。

#### Scenario: 覆盖普通用户访问自己资源
- **WHEN** E2E 使用普通用户创建项目、源码、环境和任务
- **THEN** 测试 SHALL 验证该用户可以读取项目详情、概览、源码列表、环境列表、任务详情、任务日志和项目级 SSE

#### Scenario: 覆盖超级管理员访问项目资源
- **WHEN** E2E 使用超级管理员访问普通用户创建的项目资源
- **THEN** 测试 SHALL 验证超级管理员可以读取项目详情、任务详情和必要的管理视图

#### Scenario: 覆盖跨用户越权读取
- **WHEN** E2E 使用用户 A 创建项目资源后切换到用户 B
- **THEN** 测试 SHALL 验证用户 B 访问用户 A 的项目详情、概览、源码列表、环境列表、任务列表、任务详情和任务日志时被拒绝
- **AND** 响应 MUST NOT 包含用户 A 项目的名称、任务状态、日志摘要、环境主机或源码版本信息

#### Scenario: 覆盖跨用户越权操作
- **WHEN** E2E 使用用户 B 操作用户 A 的项目资源
- **THEN** 测试 SHALL 验证源码激活、Git 同步、环境运行、任务取消和日志下载被拒绝
- **AND** 后端 MUST NOT 创建任务、投递队列消息或改变用户 A 的资源状态

#### Scenario: 覆盖 SSE 越权订阅
- **WHEN** E2E 使用用户 B 订阅用户 A 项目的 `GET /api/projects/{projectId}/task-events`
- **THEN** 后端 SHALL 拒绝请求
- **AND** 测试 SHALL 验证不会收到用户 A 的历史任务事件

#### Scenario: 覆盖访问守卫 edge case
- **WHEN** E2E 验证访问守卫边界
- **THEN** 测试 SHALL 覆盖不存在项目、软删除项目、任务不存在、日志不属于任务、源码版本不属于项目、环境不属于项目和非法 `Last-Event-ID`
