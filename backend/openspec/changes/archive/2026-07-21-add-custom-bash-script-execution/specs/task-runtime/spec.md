## ADDED Requirements

### Requirement: 任务运行时必须支持任务级日志 SSE
任务运行时 SHALL 提供任务级日志 SSE，用于单个任务的历史日志补发、实时日志推送和终态通知。

#### Scenario: 建立任务级日志 SSE
- **WHEN** 已登录用户调用 `GET /api/tasks/{taskId}/log-events`
- **THEN** 后端 SHALL 根据任务所属项目执行项目访问守卫
- **AND** 后端 SHALL 返回 `text/event-stream`
- **AND** SSE 通道 SHALL 只推送该任务的日志事件和终态事件
- **AND** 后端 SHALL 周期性发送 heartbeat 以保持连接

#### Scenario: 首次连接补发全部历史日志
- **WHEN** 用户建立任务级日志 SSE 且未提交 `Last-Event-ID`
- **THEN** 后端 SHALL 按日志事件 ID 升序补发该任务已有的全部日志事件
- **AND** 补发完成后 SHALL 保持连接继续推送新增日志事件

#### Scenario: 使用 Last-Event-ID 恢复日志流
- **WHEN** 用户携带 `Last-Event-ID` 重新连接任务级日志 SSE
- **THEN** 后端 SHALL 将该值解析为 `task_log_events.id`
- **AND** 后端 SHALL 只补发同一任务内 `id` 大于该值的日志事件
- **AND** 后端 MUST NOT 因全局自增 ID 补发其他任务或其他项目的日志事件

#### Scenario: 推送 stdout 和 stderr 日志事件
- **WHEN** worker 捕获到任务 stdout 或 stderr 输出
- **THEN** 任务运行时 SHALL 写入 `task_log_events`
- **AND** 任务级日志 SSE SHALL 推送对应事件
- **AND** SSE `id` SHALL 使用 `task_log_events.id`
- **AND** SSE `event` SHALL 使用 `task.log.stdout` 或 `task.log.stderr`
- **AND** SSE `data` SHALL 包含任务 ID、日志类型、内容片段、序号和时间

#### Scenario: 终态任务的日志 SSE
- **WHEN** 用户连接已经终态的任务日志 SSE
- **THEN** 后端 SHALL 先补发历史日志事件
- **AND** 后端 SHALL 发送任务终态事件
- **AND** 后端 MAY 在发送终态事件后关闭 SSE 连接

#### Scenario: 无权限订阅任务日志 SSE
- **WHEN** 无权限用户调用 `GET /api/tasks/{taskId}/log-events`
- **THEN** 后端 SHALL 拒绝请求
- **AND** 后端 MUST NOT 创建 SSE emitter
- **AND** 后端 MUST NOT 补发历史日志事件

### Requirement: 任务运行时必须持久化日志事件
任务运行时 SHALL 将用于实时展示和恢复的日志切片持久化为日志事件，同时继续使用 `task_logs` 保存完整日志文件元数据。

#### Scenario: 写入日志事件
- **WHEN** worker 捕获任务输出内容
- **THEN** 任务运行时 SHALL 将内容切分为有界日志事件
- **AND** 每条日志事件 SHALL 关联 `project_id`、`task_id`、日志类型、序号、内容和创建时间
- **AND** 日志事件 SHALL 按同一任务内写入顺序可排序

#### Scenario: 日志事件内容脱敏
- **WHEN** 任务运行时写入日志事件
- **THEN** 日志事件内容 MUST NOT 包含 SSH 密码、私钥、token、passphrase、加密密文或服务器真实绝对路径
- **AND** 超长内容 SHALL 被切分或截断到受控大小

#### Scenario: 完整日志文件仍可下载
- **WHEN** worker 写入日志事件
- **THEN** 任务运行时 SHALL 继续维护 `task_logs` 元数据和本地完整日志文件
- **AND** 任务日志下载 API SHALL 继续通过日志 ID 受控下载完整日志
- **AND** 任务日志下载 API MUST NOT 依赖客户端提交服务器文件路径

#### Scenario: 日志事件写入失败
- **WHEN** 任务运行时无法写入日志事件
- **THEN** worker SHALL 将任务标记为 `FAILED`
- **AND** 失败摘要 SHALL 使用安全错误信息
- **AND** 失败摘要 MUST NOT 暴露日志文件真实路径或未脱敏日志内容

### Requirement: 任务级日志 SSE 不替代项目级 SSE
任务运行时 SHALL 保留项目级 SSE 作为项目工作台任务状态通道，并 SHALL 使用任务级日志 SSE 承载单任务密集日志流。

#### Scenario: 项目级 SSE 推送任务状态
- **WHEN** 任务创建、入队、开始、进度变化或进入终态
- **THEN** 项目级 SSE SHALL 继续推送对应任务事件
- **AND** 项目级 SSE MAY 包含短日志摘要
- **AND** 项目级 SSE MUST NOT 承载完整或密集 stdout/stderr 日志流

#### Scenario: 脚本执行页订阅任务级日志 SSE
- **WHEN** 前端打开脚本执行页或执行记录详情页
- **THEN** 前端 SHALL 使用任务级日志 SSE 获取历史日志和新增日志
- **AND** 前端 MAY 同时通过任务详情 API 或项目级 SSE 获取任务状态摘要
