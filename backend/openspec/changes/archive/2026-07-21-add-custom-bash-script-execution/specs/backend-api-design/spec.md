## ADDED Requirements

### Requirement: API 必须提供脚本执行记录查询
后端 API SHALL 提供脚本执行记录列表和详情接口，用于前端展示脚本执行历史、当前状态和恢复入口。

#### Scenario: 查询项目脚本执行记录列表
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/script-executions`
- **THEN** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 响应 SHALL 返回分页执行记录列表
- **AND** 列表项 SHALL 包含执行记录 ID、任务 ID、环境摘要、脚本类型、脚本 SHA256、脚本长度、状态、退出码、创建时间、开始时间、结束时间和最近日志摘要
- **AND** 响应 MUST NOT 返回脚本正文、明文凭据、服务器真实路径或日志文件路径

#### Scenario: 过滤排序脚本执行记录
- **WHEN** 前端查询脚本执行记录列表
- **THEN** API SHALL 支持 `page` 和 `pageSize`
- **AND** API SHALL 支持按执行状态、脚本类型、环境 ID、创建时间范围过滤
- **AND** API SHALL 支持按创建时间、开始时间、结束时间和状态排序
- **AND** 后端 MUST 拒绝不在白名单内的过滤或排序字段

#### Scenario: 查询脚本执行记录详情
- **WHEN** 已登录用户调用 `GET /api/script-executions/{executionId}`
- **THEN** 后端 SHALL 根据执行记录所属项目校验访问权限
- **AND** 响应 SHALL 返回执行记录摘要、任务摘要、环境摘要、工具执行摘要和日志统计
- **AND** 响应 MUST NOT 返回脚本正文、明文凭据、服务器真实路径或日志文件路径

#### Scenario: 无权限查询脚本执行记录
- **WHEN** 用户查询无权访问项目下的脚本执行记录
- **THEN** API SHALL 返回与资源不存在一致的安全错误
- **AND** 后端 MUST NOT 暴露执行记录、任务、环境或日志是否存在

### Requirement: API 必须提供任务级日志 SSE
后端 API SHALL 提供单任务日志 SSE，用于脚本执行页和执行记录详情页恢复历史日志并接收新增日志。

#### Scenario: 建立任务级日志 SSE
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/log-events`
- **THEN** 后端 SHALL 根据任务所属项目校验访问权限
- **AND** 响应内容类型 SHALL 为 `text/event-stream`
- **AND** 后端 SHALL 先补发历史日志事件，再保持连接推送新增日志事件

#### Scenario: 日志 SSE 事件格式
- **WHEN** 后端发送任务级日志 SSE 事件
- **THEN** SSE 协议层 `id` SHALL 使用递增的 `task_log_events.id`
- **AND** stdout 事件类型 SHALL 为 `task.log.stdout`
- **AND** stderr 事件类型 SHALL 为 `task.log.stderr`
- **AND** 终态事件类型 SHALL 为 `task.succeeded`、`task.failed`、`task.cancelled` 或 `task.timeout`
- **AND** SSE data SHALL 是 JSON

#### Scenario: 日志 SSE 断线恢复
- **WHEN** 前端携带 `Last-Event-ID` 重新连接 `GET /api/tasks/{taskId}/log-events`
- **THEN** 后端 SHALL 将 `Last-Event-ID` 解析为 `task_log_events.id`
- **AND** 后端 SHALL 从持久化日志事件中补发同一任务内 `id` 大于该值的后续日志事件
- **AND** 后端 MUST NOT 补发其他项目或其他任务的日志事件

#### Scenario: 任务级日志 SSE 权限失败
- **WHEN** 无权限用户订阅任务级日志 SSE
- **THEN** 后端 SHALL 拒绝请求
- **AND** 后端 MUST NOT 创建 SSE emitter
- **AND** 后端 MUST NOT 补发历史日志事件

### Requirement: CUSTOM_BASH API 必须保护脚本正文
远程脚本 API SHALL 接收用户提交的 `CUSTOM_BASH` 脚本正文，但 MUST 只在受控存储和 worker 执行期间使用脚本正文。

#### Scenario: 提交 CUSTOM_BASH
- **WHEN** 用户调用 `POST /api/projects/{projectId}/environments/{environmentId}/scripts` 且 `scriptType=CUSTOM_BASH`
- **THEN** 请求 SHALL 包含非空 `script`
- **AND** 后端 SHALL 返回任务和执行记录摘要
- **AND** 响应 MUST NOT 返回脚本正文

#### Scenario: 返回执行记录状态
- **WHEN** API 返回脚本执行记录
- **THEN** API SHALL 只返回 `RUNNING`、`SUCCEEDED` 或 `ERROR` 三类执行记录状态
- **AND** `PENDING` 和 `QUEUED` 任务 SHALL 在执行记录中展示为 `RUNNING`

#### Scenario: 拒绝不安全脚本请求
- **WHEN** `CUSTOM_BASH` 请求缺少脚本正文、脚本过大、脚本类型不合法或环境不可运行
- **THEN** API SHALL 返回统一错误响应
- **AND** 后端 MUST NOT 创建可执行任务或投递队列消息
