## ADDED Requirements

### Requirement: CUSTOM_BASH 远程脚本必须真实执行
环境脚本运行时 SHALL 支持用户提交 `CUSTOM_BASH` 脚本，并 SHALL 在目标环境中以非交互方式真实执行。

#### Scenario: 创建 CUSTOM_BASH 脚本任务
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/environments/{environmentId}/scripts` 并提交 `scriptType=CUSTOM_BASH` 和非空脚本正文
- **THEN** 后端 SHALL 校验用户有权访问该项目和环境
- **AND** 后端 SHALL 创建 `ENV_RUN_SCRIPT` 任务
- **AND** 后端 SHALL 安全保存脚本正文
- **AND** 任务输入快照 SHALL 只保存脚本引用、脚本 SHA256、脚本长度、工作目录、超时和环境引用
- **AND** 任务输入快照 MUST NOT 保存脚本正文、明文凭据、私钥、token、passphrase 或服务器真实路径

#### Scenario: Worker 执行 CUSTOM_BASH
- **WHEN** worker 认领 `ENV_RUN_SCRIPT` 且任务输入 `scriptType=CUSTOM_BASH`
- **THEN** worker SHALL 读取并校验脚本引用对应的脚本正文
- **AND** worker SHALL 在目标环境创建临时脚本文件并执行该脚本
- **AND** worker SHALL 捕获 stdout、stderr、退出码和耗时
- **AND** worker SHALL 在执行完成或失败后尽力清理远端临时脚本文件
- **AND** worker MUST NOT 在日志摘要、任务事件、审计详情或 API 响应中暴露脚本正文

#### Scenario: CUSTOM_BASH 执行成功
- **WHEN** 远程脚本退出码为 0
- **THEN** worker SHALL 将任务标记为 `SUCCEEDED`
- **AND** SHALL 写入 `tool_runs` 执行记录
- **AND** `tool_runs.exit_code` SHALL 保存退出码
- **AND** `tool_runs.summary` SHALL 保存脚本类型、脚本 SHA256、脚本长度、工作目录配置状态、耗时和日志事件数量
- **AND** 任务级日志 SSE SHALL 能观察到 stdout/stderr 日志事件和成功终态

#### Scenario: CUSTOM_BASH 执行失败
- **WHEN** 远程脚本返回非 0 退出码、远程执行失败、脚本引用不存在或脚本 hash 校验失败
- **THEN** worker SHALL 将任务标记为 `FAILED`
- **AND** SHALL 写入失败态 `tool_runs`
- **AND** SHALL 保存 stdout/stderr 日志和安全错误摘要
- **AND** 任务级日志 SSE SHALL 能观察到已产生日志和失败终态

#### Scenario: 拒绝空脚本
- **WHEN** 用户提交 `scriptType=CUSTOM_BASH` 但脚本正文为空
- **THEN** API SHALL 返回参数校验错误
- **AND** 后端 MUST NOT 创建任务
- **AND** 后端 MUST NOT 保存脚本正文或投递队列消息

### Requirement: 脚本执行记录必须可恢复查看
后端 SHALL 提供脚本执行记录视图，使前端能在页面关闭后重新打开并恢复查看历史日志和当前执行状态。

#### Scenario: 查询项目脚本执行记录
- **WHEN** 已登录用户查询某个项目的脚本执行记录
- **THEN** 后端 SHALL 返回该项目下 `ENV_RUN_SCRIPT` 脚本任务的分页列表
- **AND** 列表项 SHALL 包含执行记录 ID、任务 ID、环境摘要、脚本类型、脚本 SHA256、脚本长度、执行状态、退出码、开始时间、结束时间和日志摘要
- **AND** 后端 SHALL 支持按状态、脚本类型、环境 ID、创建时间范围过滤
- **AND** 后端 SHALL 支持按创建时间、开始时间、结束时间和状态排序

#### Scenario: 执行记录状态映射
- **WHEN** 后端返回脚本执行记录
- **THEN** `PENDING`、`QUEUED` 和 `RUNNING` 任务状态 SHALL 映射为执行记录状态 `RUNNING`
- **AND** `SUCCEEDED` 任务状态 SHALL 映射为执行记录状态 `SUCCEEDED`
- **AND** `FAILED`、`TIMEOUT` 和 `CANCELLED` 任务状态 SHALL 映射为执行记录状态 `ERROR`
- **AND** 执行记录状态 MUST NOT 引入独立于 `tasks.status` 的第二套事实状态机

#### Scenario: 恢复运行中执行记录
- **WHEN** 用户重新打开仍在运行的脚本执行记录
- **THEN** 前端 SHALL 能读取执行记录详情
- **AND** 前端 SHALL 能通过任务级日志 SSE 获取全部历史日志并继续接收新增日志
- **AND** 后端 MUST NOT 因页面关闭或 SSE 断开而取消运行中的脚本任务

#### Scenario: 执行记录权限校验
- **WHEN** 用户查询脚本执行记录、执行记录详情或执行记录日志
- **THEN** 后端 SHALL 根据记录所属项目执行项目访问守卫
- **AND** 无权限时 SHALL 返回与资源不存在一致的安全错误
- **AND** 后端 MUST NOT 暴露目标项目、环境、任务、脚本摘要或日志是否存在
