## ADDED Requirements

### Requirement: 后端 API 必须提供任务日志通知 SSE
后端 API SHALL 提供 `GET /api/tasks/{taskId}/log-notifications`，用于通知前端任务日志变化和任务结束。

#### Scenario: 建立带消费游标的通知连接
- **WHEN** 已登录用户调用 `GET /api/tasks/{taskId}/log-notifications?afterEventId=123`
- **THEN** 后端 SHALL 返回 `text/event-stream`
- **AND** `afterEventId` SHALL 表示前端已通过增量 API 成功消费的最后日志事件 ID
- **AND** 后端 SHALL 在当前最新事件 ID 大于该值时发送 `task.log.updated`

#### Scenario: 通知 SSE 的事件契约
- **WHEN** 后端发送 `task.log.updated`
- **THEN** JSON data SHALL 包含 `taskId`、`latestEventId` 和 `status`
- **AND** data MUST NOT 包含日志正文
- **WHEN** 后端发送 `task.log.completed`
- **THEN** JSON data SHALL 额外包含安全的终态消息

#### Scenario: 非法 SSE 游标
- **WHEN** 用户传入负数或非数字 `afterEventId`
- **THEN** 后端 SHALL 返回 HTTP 400 和稳定错误码
- **AND** 后端 MUST NOT 创建 SSE emitter

#### Scenario: 无任务访问权限
- **WHEN** 用户无权访问 taskId 所属项目或任务不存在
- **THEN** 后端 SHALL 使用现有任务访问守卫拒绝请求
- **AND** 后端 MUST NOT泄露任务状态、日志游标或日志内容

### Requirement: 后端 API 必须提供任务日志增量读取接口
后端 API SHALL 提供 `GET /api/tasks/{taskId}/log-increments`，以单一任务日志事件游标聚合读取 merged、stdout 和 stderr 新增内容。

#### Scenario: 正常增量响应
- **WHEN** 用户调用 `GET /api/tasks/{taskId}/log-increments?afterEventId=123&limit=500`
- **THEN** 响应 SHALL 包含 `taskId`、`fromEventId`、`latestEventId`、`hasMore` 和 `logs`
- **AND** `logs` SHALL 包含 merged、stdout、stderr 三类聚合内容及各自 `returnedEvents`
- **AND** 响应 MUST NOT 包含日志文件路径

#### Scenario: 默认增量参数
- **WHEN** 用户未提交 `afterEventId` 或 `limit`
- **THEN** 后端 SHALL 使用 `afterEventId=0` 和受控的默认事件条数
- **AND** 单次响应仍 SHALL 受最大事件数与最大 UTF-8 内容字节数限制

#### Scenario: 无效增量参数
- **WHEN** 用户提交负数游标、非正数 limit 或超过服务端上限的 limit
- **THEN** 后端 SHALL 返回 HTTP 400 和稳定错误码

#### Scenario: 游标大于当前最新事件
- **WHEN** `afterEventId` 大于当前任务最新日志事件 ID
- **THEN** 后端 SHALL 返回空增量和 `hasMore=false`
- **AND** 后端 MUST NOT 回退到历史日志或其他任务事件

### Requirement: 新日志 API 必须与现有日志内容 API 分工明确
API 文档 SHALL 将通知、运行中增量读取和完成态历史查看定义为三个不同职责。

#### Scenario: 前端查看运行中日志
- **WHEN** 前端打开运行中任务的日志页面
- **THEN** 前端 SHALL 使用 `/log-notifications` 获取变化通知
- **AND** 前端 SHALL 使用 `/log-increments` 获取新增正文

#### Scenario: 前端向上翻阅完成态历史日志
- **WHEN** 前端查看已经完成任务的历史日志并向上翻页
- **THEN** 前端 SHALL 继续使用 `/log-content`
- **AND** `/log-content` 的请求和响应字段 SHALL 保持兼容
