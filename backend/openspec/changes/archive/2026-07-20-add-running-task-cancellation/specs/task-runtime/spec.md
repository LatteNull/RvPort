## MODIFIED Requirements

### Requirement: 任务 API 必须提供查询、取消和日志访问
任务运行时 SHALL 提供任务详情、项目任务列表、取消任务、日志列表和日志下载 API。

#### Scenario: 查询项目任务列表
- **WHEN** 前端调用 `GET /api/projects/{projectId}/tasks`
- **THEN** 后端 SHALL 返回该项目的分页任务列表
- **AND** 列表项 SHALL 包含任务 ID、类型、状态、进度、消息和关键时间字段

#### Scenario: 查询任务详情
- **WHEN** 前端调用 `GET /api/tasks/{taskId}`
- **THEN** 后端 SHALL 返回任务类型、状态、进度、消息、时间、错误摘要和关联业务资源引用
- **AND** 响应 MUST NOT 返回完整输入快照、明文凭据或服务器本地路径

#### Scenario: 取消未开始任务
- **WHEN** 前端调用 `POST /api/tasks/{taskId}/cancel` 且任务状态为 `PENDING` 或 `QUEUED`
- **THEN** 后端 SHALL 将任务状态更新为 `CANCELLED`
- **AND** SHALL 设置 `finished_at`
- **AND** SHALL 追加 `task.cancelled` 事件

#### Scenario: 取消运行中任务
- **WHEN** 前端调用 `POST /api/tasks/{taskId}/cancel` 且任务状态为 `RUNNING`
- **THEN** 后端 SHALL 将任务状态更新为 `CANCELLED`
- **AND** SHALL 设置 `finished_at`
- **AND** SHALL 追加 `task.cancelled` 事件
- **AND** SHALL 根据 active runtime handle 投递取消清理消息
- **AND** 后端 MUST NOT 等待底层线程、进程或远程命令完全退出后才返回 API 响应

#### Scenario: 查询任务日志元数据
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/logs`
- **THEN** 后端 SHALL 返回该任务的日志元数据、日志类型、大小、摘要和创建时间
- **AND** 响应 MUST NOT 暴露服务器真实文件路径

#### Scenario: 下载任务日志
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/logs/{logId}/download`
- **THEN** 后端 SHALL 校验日志属于该任务
- **AND** SHALL 通过受控下载返回日志文件
- **AND** 响应 MUST NOT 允许客户端指定服务器文件路径

### Requirement: Worker handler 必须通过执行上下文处理任务
任务运行时 SHALL 为 worker handler 提供统一任务执行上下文，使 handler 通过该上下文读取任务元数据、解析输入快照、更新进度、追加事件、写入任务日志、检查取消请求并登记可取消资源。

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

#### Scenario: Handler 检查取消请求
- **WHEN** handler 进入长时间运行步骤、循环、外部进程等待或远程命令等待
- **THEN** handler SHALL 能通过执行上下文检查任务是否已请求取消
- **AND** handler SHALL 在检测到取消请求后停止后续业务处理

#### Scenario: Handler 登记可取消资源
- **WHEN** handler 启动本地进程或远程命令
- **THEN** handler SHALL 通过执行上下文登记对应 runtime handle 信息
- **AND** handler MUST NOT 将明文凭据或完整命令输入写入 runtime handle 明文字段
