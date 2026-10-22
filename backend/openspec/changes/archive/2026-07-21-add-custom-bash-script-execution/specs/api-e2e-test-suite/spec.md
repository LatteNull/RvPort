## ADDED Requirements

### Requirement: E2E 必须覆盖 CUSTOM_BASH 脚本执行
API E2E 测试 SHALL 覆盖 `CUSTOM_BASH` 从创建、执行、日志输出、执行记录恢复到清理的端到端流程。

#### Scenario: CUSTOM_BASH 正常执行
- **WHEN** E2E 创建项目、SSH 环境并提交一个成功退出的 `CUSTOM_BASH` 脚本
- **THEN** 后端 SHALL 创建 `ENV_RUN_SCRIPT` 任务
- **AND** worker SHALL 执行脚本并将任务推进到 `SUCCEEDED`
- **AND** E2E SHALL 校验 `tasks`、`tool_runs`、`task_logs` 和 `task_log_events` 均产生对应记录
- **AND** E2E SHALL 校验 API 响应、任务输入、任务事件、审计日志和日志摘要不包含脚本正文中的敏感测试值

#### Scenario: CUSTOM_BASH 失败执行
- **WHEN** E2E 提交一个返回非 0 退出码的 `CUSTOM_BASH` 脚本
- **THEN** worker SHALL 将任务推进到 `FAILED`
- **AND** `tool_runs.exit_code` SHALL 保存非 0 退出码
- **AND** E2E SHALL 能从日志 API 和任务级日志 SSE 读取失败前产生的 stdout/stderr

#### Scenario: CUSTOM_BASH 参数校验
- **WHEN** E2E 提交空脚本、超大脚本或非法脚本类型
- **THEN** API SHALL 返回统一校验错误
- **AND** E2E SHALL 校验未创建任务、未保存脚本正文且未投递队列消息

### Requirement: E2E 必须覆盖任务级日志 SSE
API E2E 测试 SHALL 覆盖任务级日志 SSE 的历史补发、实时推送、断线恢复和权限边界。

#### Scenario: 首次连接补发历史日志
- **WHEN** 脚本任务已经产生若干日志事件
- **THEN** E2E 调用 `GET /api/tasks/{taskId}/log-events` 且不提交 `Last-Event-ID`
- **AND** SSE SHALL 先返回已有日志事件
- **AND** 返回事件 SHALL 按 `task_log_events.id` 升序排列

#### Scenario: 断线后继续恢复日志
- **WHEN** E2E 记录最后收到的任务级日志 SSE ID 后重新连接
- **THEN** 后端 SHALL 只补发同一任务中 ID 更大的日志事件
- **AND** E2E SHALL 校验不会收到其他任务或其他项目的日志事件

#### Scenario: 运行中继续推送日志
- **WHEN** 脚本任务仍在运行且持续输出日志
- **THEN** 任务级日志 SSE SHALL 在历史补发后继续推送新增日志事件
- **AND** 页面关闭或 SSE 断开 MUST NOT 取消后端任务

#### Scenario: 无权限订阅任务级日志 SSE
- **WHEN** 普通用户尝试订阅其他用户项目任务的日志 SSE
- **THEN** API SHALL 返回安全错误
- **AND** 后端 MUST NOT 补发任何日志事件

### Requirement: E2E 必须覆盖脚本执行记录恢复
API E2E 测试 SHALL 覆盖脚本执行记录列表、详情、状态映射和恢复查看。

#### Scenario: 查询脚本执行记录列表
- **WHEN** E2E 创建并执行脚本任务
- **THEN** `GET /api/projects/{projectId}/script-executions` SHALL 返回该执行记录
- **AND** 执行记录 SHALL 包含任务 ID、环境摘要、脚本 SHA256、脚本长度、状态、退出码和时间字段
- **AND** 响应 MUST NOT 包含脚本正文或服务器真实路径

#### Scenario: 查询运行中执行记录
- **WHEN** 脚本任务仍在 `PENDING`、`QUEUED` 或 `RUNNING`
- **THEN** 脚本执行记录状态 SHALL 展示为 `RUNNING`
- **AND** E2E SHALL 能通过任务级日志 SSE 恢复历史日志并继续接收新增日志

#### Scenario: 查询终态执行记录
- **WHEN** 脚本任务已经进入 `SUCCEEDED` 或 `FAILED`
- **THEN** 脚本执行记录 SHALL 展示为 `SUCCEEDED` 或 `ERROR`
- **AND** E2E SHALL 能通过执行记录详情和日志 API 查看完整结果摘要
