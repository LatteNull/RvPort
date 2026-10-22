## Context

当前环境脚本 API 已能创建 `ENV_RUN_SCRIPT` 任务，任务运行时也已有 `tasks`、`task_events`、`task_logs`、`tool_runs`、RabbitMQ worker、项目级 SSE 和任务取消能力。但 `CUSTOM_BASH` 只保存脚本哈希和长度，worker 执行时会拒绝执行，因为脚本正文没有可读取的安全来源。

脚本执行页的交互也比普通任务列表更细：用户确认执行后页面不跳转，需要实时显示 stdout/stderr；如果页面关闭，任务不能中止；再次打开执行记录时，需要先看到全部历史日志，再继续接收运行中的新增日志。因此项目级 SSE 不适合作为密集日志流主通道，它只应保留给工作台任务状态广播。

## Goals / Non-Goals

**Goals:**

- 支持前端提交 `CUSTOM_BASH`，后端安全保存脚本正文，worker 读取并在目标环境执行。
- 提供脚本执行记录查询，执行记录可从任务、工具运行和日志事件恢复。
- 提供任务级日志 SSE：连接后先补发已有日志事件，再保持连接推送新增日志和终态。
- 保证页面关闭不影响任务执行，重新打开执行记录可恢复历史日志并继续追踪进行中任务。
- 保证脚本正文、SSH 凭据、服务器路径不出现在队列消息、任务事件、日志摘要、审计详情和 API 响应中。
- 补充正常流程、异常流程和 edge case 测试。

**Non-Goals:**

- 不实现 WebSocket。
- 不实现交互式 shell、TTY、stdin 持续输入或 sudo 密码输入。
- 不允许前端通过任意服务器路径引用脚本。
- 不把完整日志写入 `task_events`。
- 不把脚本执行记录设计成独立于 `tasks` 的第二套任务状态机。

## Decisions

### 1. 新增脚本正文安全存储，而不是放入 `tasks.input_snapshot`

`tasks.input_snapshot` 继续只保存 `scriptRef`、`scriptSha256`、`scriptLength`、`scriptType`、环境 ID、超时和工作目录等安全摘要。脚本正文保存到专用表，例如 `task_script_payloads`，并使用现有凭据加密能力或同等级应用层加密保存。

原因：

- 队列消息和任务输入快照经常用于排障、审计和测试断言，不能包含用户提交的完整脚本。
- 未来 API 容器和 worker 容器可能不是同一节点，单纯保存到 API 本机临时文件会导致 worker 无法读取。
- 表内加密可以支持任务重试、worker 重启和执行记录恢复。

备选方案：

- 本地共享 runtime volume：实现简单，但对多 worker、多节点和容器重建更脆弱。
- 明文数据库字段：查询方便，但安全边界不可接受。

### 2. 脚本执行记录复用任务事实，不引入独立状态机

脚本执行记录以 `tasks` 为事实来源，结合 `tool_runs`、`task_logs`、`task_log_events` 返回面向前端的记录视图。前端状态映射为：

| 任务状态 | 执行记录状态 |
| --- | --- |
| `PENDING` / `QUEUED` / `RUNNING` | `RUNNING` |
| `SUCCEEDED` | `SUCCEEDED` |
| `FAILED` / `TIMEOUT` / `CANCELLED` | `ERROR` |

原因：

- 用户点击确认后即创建任务，不需要“未开始”展示状态。
- 避免 `script_executions.status` 和 `tasks.status` 两套状态不一致。
- 当前任务访问守卫、取消、日志和 SSE 可以复用。

### 3. 新增任务级日志 SSE，项目级 SSE 继续保留

项目级 SSE 继续用于工作台状态广播：`task.created`、`task.started`、`task.progress`、`task.succeeded`、`task.failed`。任务级日志 SSE 专门用于脚本执行页：

```http
GET /api/tasks/{taskId}/log-events
Accept: text/event-stream
Last-Event-ID: 123
```

连接行为：

- 无 `Last-Event-ID`：从该任务第一条日志事件开始补发。
- 有 `Last-Event-ID`：补发 `id` 大于该值的日志事件。
- 历史补发完成后连接保持，继续推送新增 stdout/stderr。
- 任务已终态时，补发日志后发送终态事件并关闭连接。

原因：

- 脚本日志可能高频，项目级 SSE 会污染项目工作台通道。
- 任务级 SSE 可以按 `taskId` 和日志事件 ID 精确恢复。
- 前端打开执行记录时只需连接一个流即可获得历史和实时日志。

### 4. 新增 `task_log_events`，完整日志仍保留在 `task_logs`

`task_logs` 仍用于完整日志文件下载和归档。`task_log_events` 用于实时展示和恢复，保存切片后的 stdout/stderr 片段或行级内容。

建议字段：

- `id bigserial primary key`
- `project_id uuid not null`
- `task_id uuid not null`
- `log_type text not null`
- `sequence bigint not null`
- `content text not null`
- `created_at timestamptz not null`

索引：

- `task_id, id`
- `project_id, task_id, id`
- `task_id, sequence`

内容策略：

- 单条内容必须有最大长度限制，超长输出按 chunk 切分。
- 内容必须经过敏感信息脱敏。
- 可以保存日志正文片段，但不得保存 SSH 密码、私钥、token、passphrase 或服务器真实绝对路径。

### 5. 远程执行采用临时脚本文件和短生命周期 SSH 命令

worker 解密脚本正文后，通过 SSH 在远端创建临时脚本文件，设置安全权限，执行 `bash` 或 `sh`，捕获 stdout/stderr，最后清理临时文件。每次执行仍使用短生命周期 SSH session，不跨任务复用空闲连接。

执行摘要写入 `tool_runs.summary`：

- `scriptType`
- `scriptSha256`
- `scriptLength`
- `workingDirectoryConfigured`
- `exitCode`
- `durationMs`
- `logEventCount`

不得写入脚本正文。

### 6. 流式日志需要支持增量写入

当前执行上下文按一次 `context.log(STDOUT, fullStdout)` 写入，适合短输出，不适合动态日志。实现时应增加日志 sink 能力，使 SSH adapter 或 runtime 能在进程输出产生时写入：

- 本地日志文件追加。
- `task_log_events` 追加。
- 任务级日志 SSE 发布。
- 可选地低频写 `task_events` 摘要，用于项目级工作台。

### 7. 权限边界沿用项目访问守卫

所有脚本执行记录、任务级日志 SSE、日志补发和日志下载都必须先根据 `taskId` 找到项目，再执行项目访问守卫。无权限时返回与资源不存在一致的安全错误，并且不能创建 SSE emitter 或补发任何历史日志。

## Risks / Trade-offs

- [Risk] 日志事件表增长快。  
  Mitigation: 对 chunk 大小设上限，按任务和时间索引；后续可增加保留期或归档策略。完整日志仍由文件系统管理。

- [Risk] 脚本可能包含敏感内容。  
  Mitigation: 脚本正文加密保存；API 响应、任务输入、审计和事件只返回 hash、长度和摘要。

- [Risk] 高频日志直接写数据库和 SSE 可能造成压力。  
  Mitigation: 按 chunk 批量/限速写入，SSE 发送失败时移除 emitter，不影响任务执行。

- [Risk] 远端脚本执行后临时文件残留。  
  Mitigation: 使用唯一临时路径、`trap` 清理和 worker finally 清理；失败摘要只记录安全信息。

- [Risk] 任务级 SSE 与项目级 SSE 语义混淆。  
  Mitigation: 项目级 SSE 只承载任务状态和低频摘要；任务级 SSE 承载日志正文切片和终态。
