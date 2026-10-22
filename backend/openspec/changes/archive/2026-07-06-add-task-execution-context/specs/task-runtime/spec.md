## ADDED Requirements

### Requirement: Worker handler 必须通过执行上下文处理任务
任务运行时 SHALL 为 worker handler 提供统一任务执行上下文，使 handler 通过该上下文读取任务元数据、解析输入快照、更新进度、追加事件和写入任务日志。

#### Scenario: 创建执行上下文
- **WHEN** worker 成功认领任务并找到已注册 handler
- **THEN** 任务运行时 SHALL 为该任务创建执行上下文
- **AND** 执行上下文 SHALL 包含当前任务 ID、项目 ID、任务类型、当前状态和输入快照访问能力
- **AND** handler SHALL 通过执行上下文处理任务

#### Scenario: 安全解析输入快照
- **WHEN** handler 需要读取任务输入快照
- **THEN** handler SHALL 通过执行上下文解析输入快照
- **AND** 解析失败 SHALL 使任务进入 `FAILED`
- **AND** 失败摘要 MUST NOT 包含原始输入快照、明文凭据或服务器本地路径

#### Scenario: Handler 不直接写任务状态事实
- **WHEN** handler 需要更新任务进度、事件或日志
- **THEN** handler SHALL 使用执行上下文提供的任务运行时方法
- **AND** handler SHOULD NOT 直接写入 `tasks`、`task_events` 或 `task_logs` 表

### Requirement: 执行上下文必须统一写入任务进度事件
任务执行上下文 SHALL 提供进度更新能力，并 SHALL 保证任务进度、展示消息和持久化事件一致。

#### Scenario: 写入合法进度
- **WHEN** handler 通过执行上下文提交 0 到 100 之间的进度和展示消息
- **THEN** 任务运行时 SHALL 更新 `tasks.progress` 和 `tasks.message`
- **AND** SHALL 追加 `task.progress` 事件
- **AND** 项目级 SSE SHALL 能推送该进度事件

#### Scenario: 拒绝非法进度
- **WHEN** handler 通过执行上下文提交小于 0 或大于 100 的进度
- **THEN** 任务运行时 SHALL 拒绝该进度更新
- **AND** worker SHALL 将任务标记为 `FAILED`
- **AND** 失败摘要 SHALL 使用安全错误消息

#### Scenario: 多次进度更新
- **WHEN** handler 在一次任务执行过程中多次提交进度
- **THEN** 任务运行时 SHALL 按提交顺序持久化对应进度事件
- **AND** 最终任务详情 SHALL 展示最近一次进度和消息，直到进入终态

### Requirement: 执行上下文必须受控写入任务日志
任务执行上下文 SHALL 支持 handler 写入 stdout、stderr、combined 或 tool 日志，并 SHALL 将完整日志保存为受控本地文件，同时只向事件流暴露短摘要。

#### Scenario: 写入任务日志
- **WHEN** handler 通过执行上下文写入任务日志
- **THEN** 任务运行时 SHALL 在 `RVPORT_LOG_DIR` 管理的目录下创建或追加日志文件
- **AND** SHALL 在 `task_logs` 表登记日志类型、大小、摘要和受控文件路径
- **AND** 任务日志下载 API SHALL 能通过既有受控下载能力访问该日志

#### Scenario: 追加日志摘要事件
- **WHEN** handler 写入适合实时展示的日志内容
- **THEN** 任务运行时 SHALL 追加 `task.log` 事件
- **AND** 事件 SHALL 只包含短摘要
- **AND** 事件 MUST NOT 包含完整 stdout、完整 stderr、明文凭据或服务器真实文件路径

#### Scenario: 空日志内容
- **WHEN** handler 尝试写入空日志内容
- **THEN** 任务运行时 SHALL 使用明确策略处理该请求
- **AND** 该策略 SHALL 不产生无法下载的悬空 `task_logs` 记录

#### Scenario: 日志写入失败
- **WHEN** 日志文件无法创建或写入
- **THEN** 任务运行时 SHALL 将任务标记为 `FAILED`
- **AND** 失败摘要 SHALL 使用安全错误消息
- **AND** 失败摘要 MUST NOT 暴露服务器本地路径

### Requirement: 任务执行上下文必须保护敏感信息边界
任务执行上下文 SHALL 保证任务执行过程中的输入解析、进度消息、日志摘要和失败摘要不泄露明文秘密或服务器内部路径。

#### Scenario: 不泄露明文凭据
- **WHEN** handler 使用执行上下文写入进度、日志摘要或失败摘要
- **THEN** 任务运行时 MUST NOT 在 `task_events`、API 响应或队列消息中暴露密码、token、SSH 私钥、passphrase 或加密密文

#### Scenario: 不泄露服务器真实路径
- **WHEN** 执行上下文创建日志文件或处理任务本地文件
- **THEN** 任务事件和 API 响应 MUST NOT 暴露服务器真实绝对路径
- **AND** 日志下载 SHALL 继续通过受控日志 ID 访问

#### Scenario: 队列消息保持最小载荷
- **WHEN** 任务执行上下文能力被启用
- **THEN** RabbitMQ 任务消息 MUST 继续只包含任务 ID 等路由信息
- **AND** 消息 MUST NOT 包含任务输入快照、日志内容、任务结果或明文凭据

### Requirement: 任务执行上下文必须配套测试覆盖
任务执行上下文相关实现 SHALL 配套单元测试或轻量集成测试，并 SHALL 覆盖正常流程、异常流程和 edge case。

#### Scenario: 覆盖正常流程
- **WHEN** 为任务执行上下文编写测试
- **THEN** 测试 SHALL 覆盖 handler 成功解析输入、更新进度、写入日志和完成任务

#### Scenario: 覆盖异常流程
- **WHEN** 为任务执行上下文编写测试
- **THEN** 测试 SHALL 覆盖输入解析失败、日志写入失败、缺少 handler 和 handler 抛异常等错误路径

#### Scenario: 覆盖 edge case
- **WHEN** 为任务执行上下文编写测试
- **THEN** 测试 SHALL 覆盖空日志、超长日志摘要截断、非法进度、多次进度更新和敏感信息脱敏边界
