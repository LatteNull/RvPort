## ADDED Requirements

### Requirement: 任务运行时必须提供轻量日志变化通知 SSE
任务运行时 SHALL 提供按任务订阅的日志通知 SSE，并 MUST 只发送日志变化、heartbeat 和任务终态通知，不得通过该 SSE 发送日志正文。

#### Scenario: 运行中任务出现新增日志
- **WHEN** 已授权用户订阅任务日志通知，且该任务产生了游标之后的新日志事件
- **THEN** 后端 SHALL 在最多一个 5 秒检查周期内发送 `task.log.updated`
- **AND** 事件 SHALL 包含任务 ID、最新日志事件 ID 和当前任务状态
- **AND** 事件 MUST NOT 包含 stdout、stderr、完整日志文件内容或服务器路径

#### Scenario: 没有新增日志
- **WHEN** 任务日志最大事件 ID 和任务状态在检查周期内均未变化
- **THEN** 后端 MUST NOT 发送 `task.log.updated`
- **AND** 后端 SHALL 继续发送 heartbeat 保持连接

#### Scenario: 同一任务存在多个连接
- **WHEN** 同一 API 进程持有同一任务的多个日志通知 SSE 连接
- **THEN** 后端 SHALL 按 taskId 复用一次周期检查结果
- **AND** 后端 SHALL 将变化通知广播给该任务的全部有效连接

### Requirement: 日志通知 SSE 必须正确处理任务终态
任务运行时 SHALL 从共享数据库读取任务终态，并 SHALL 在终态通知中提供最终日志游标后关闭连接。

#### Scenario: 运行中任务进入终态且存在最终日志
- **WHEN** 周期检查同时发现任务产生了新增日志并进入 `SUCCEEDED`、`FAILED`、`CANCELLED` 或 `TIMEOUT`
- **THEN** 后端 SHALL 先发送 `task.log.updated`
- **AND** 后端 SHALL 再发送 `task.log.completed`
- **AND** 终态事件 SHALL 包含任务状态和最新日志事件 ID
- **AND** 后端 SHALL 在发送终态事件后完成 SSE 连接

#### Scenario: 订阅已经终态的任务
- **WHEN** 已授权用户订阅已经进入终态的任务
- **THEN** 后端 SHALL 立即发送 `task.log.completed`
- **AND** 后端 MUST NOT 等待下一个 5 秒检查周期
- **AND** 后端 SHALL 随后完成 SSE 连接

#### Scenario: 任务重试时保持连接
- **WHEN** 任务执行失败后重新进入 `QUEUED` 并等待下一次尝试
- **THEN** 日志通知 SSE SHALL 保持连接
- **AND** 后端 MUST NOT 将重试状态当作终态发送 completed 事件

### Requirement: 任务运行时必须提供稳定游标的日志增量读取
任务运行时 SHALL 使用 `task_log_events.id` 作为任务日志的前向增量游标，并 SHALL 将一批事件聚合为 merged、stdout 和 stderr 内容。

#### Scenario: 按游标读取新增日志
- **WHEN** 用户请求某任务 `id > afterEventId` 的日志增量
- **THEN** 后端 SHALL 只查询该任务的日志事件并按 ID 升序处理
- **AND** stdout 和 stderr SHALL 分别包含对应类型内容
- **AND** merged SHALL 按事件 ID 顺序包含两类内容
- **AND** 响应 SHALL 返回本批实际消费到的 `latestEventId`

#### Scenario: 增量超过单批上限
- **WHEN** 游标之后的日志超过事件条数或响应内容字节数上限
- **THEN** 后端 SHALL 只返回不超过上限的完整事件
- **AND** 响应 SHALL 返回 `hasMore=true`
- **AND** 客户端 SHALL 能使用本批 `latestEventId` 继续读取而不重复或遗漏事件

#### Scenario: 游标之后没有日志
- **WHEN** 当前任务不存在 ID 大于 `afterEventId` 的日志事件
- **THEN** 后端 SHALL 返回空的 merged、stdout 和 stderr 内容
- **AND** 响应 SHALL 返回 `hasMore=false`

#### Scenario: 全局事件 ID 中夹有其他任务事件
- **WHEN** 其他任务在当前任务两个日志事件之间写入了全局自增日志事件 ID
- **THEN** 当前任务的增量读取 MUST NOT 返回其他任务的事件或内容
- **AND** 当前任务 SHALL 仍能继续使用其最后实际返回的事件 ID 读取后续内容

### Requirement: 日志恢复必须以增量读取成功游标为准
任务运行时 MUST NOT 将 SSE 通知送达视为日志正文已消费，前端恢复 SHALL 以最后一次成功增量响应的事件游标为准。

#### Scenario: 收到更新通知后增量请求失败
- **WHEN** 前端收到 `task.log.updated` 但增量日志请求失败或连接中断
- **THEN** 前端 SHALL 保留此前成功消费的游标
- **AND** 重新建立日志页连接后 SHALL 再次从该游标拉取增量

#### Scenario: 收到终态通知后仍有未读取日志
- **WHEN** `task.log.completed.latestEventId` 大于前端最后成功消费的事件 ID
- **THEN** 前端 SHALL 在结束动态日志展示前继续读取剩余增量

### Requirement: 旧日志正文 SSE 必须提供迁移期兼容
任务运行时 SHALL 在迁移期保留 `GET /api/tasks/{taskId}/log-events`，并 SHALL 将其标记为废弃，新的调用方必须使用日志通知 SSE 与增量读取 API。

#### Scenario: 旧调用方仍订阅日志正文 SSE
- **WHEN** 已有调用方请求旧 `/log-events` 路由
- **THEN** 后端 SHALL 在本 change 中保持旧接口可用
- **AND** API 文档 SHALL 指示新调用方改用新接口

#### Scenario: 完成态历史日志翻页
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/log-content`
- **THEN** 后端 SHALL 保持现有完成态日志历史分页契约
- **AND** 新增量接口 MUST NOT 改变该接口的 offset 语义
