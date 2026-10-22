# running-task-cancellation Specification

## Purpose

定义运行中任务取消的业务状态、worker 定点取消、运行时句柄、协作式取消和底层资源清理要求。该能力覆盖取消请求如何进入数据库和取消队列、worker 如何定位本 JVM 内任务、如何终止本地或远程执行资源，以及如何保证用户可见状态和清理状态可追踪。

## Requirements

### Requirement: 运行中任务必须支持取消请求
任务运行时 SHALL 支持取消 `RUNNING` 任务，并 SHALL 将用户可见任务状态和底层资源清理状态分开管理。

#### Scenario: 取消运行中任务
- **WHEN** 已授权用户调用 `POST /api/tasks/{taskId}/cancel` 且任务状态为 `RUNNING`
- **THEN** 后端 SHALL 将任务状态更新为 `CANCELLED`
- **AND** SHALL 设置 `finished_at`
- **AND** SHALL 追加 `task.cancelled` 事件
- **AND** SHALL 投递取消清理消息

#### Scenario: 取消清理仍在进行
- **WHEN** 任务状态已经是 `CANCELLED` 但底层线程、进程或远程命令仍在清理
- **THEN** 任务详情 SHALL 继续返回业务状态 `CANCELLED`
- **AND** 后端 SHALL 在运行时句柄中记录清理状态
- **AND** 后端 MUST NOT 将任务状态回滚为 `RUNNING` 或 `FAILED`

#### Scenario: 重复取消运行中任务
- **WHEN** 用户重复取消同一个已经进入 `CANCELLED` 的任务
- **THEN** 后端 SHALL 幂等返回当前任务状态
- **AND** 后端 SHOULD NOT 重复投递相同运行时句柄的取消清理消息

### Requirement: Worker 必须登记运行时句柄
Worker SHALL 为每个已认领的运行中任务登记运行时句柄，用于定位任务所属 worker、线程、进程和远程命令。

#### Scenario: 任务开始执行时登记句柄
- **WHEN** worker 成功将任务认领为 `RUNNING`
- **THEN** worker SHALL 创建 active runtime handle
- **AND** runtime handle SHALL 记录 `taskId`、`projectId`、`workerInstanceId`、handle 类型、状态和开始时间

#### Scenario: 登记本地进程句柄
- **WHEN** handler 启动 Git、SBOM 分析器或其他本地外部进程
- **THEN** worker SHALL 将本地进程 PID 和必要进程树信息登记到当前 runtime handle
- **AND** 取消清理 SHALL 优先终止该进程及其子进程

#### Scenario: 登记远程进程句柄
- **WHEN** handler 通过 SSH 执行可取消远程命令
- **THEN** worker SHALL 将环境 ID、远程 PID、远程 PGID 和命令 marker 登记到当前 runtime handle
- **AND** 取消清理 SHALL 使用远程 PID 或 PGID 终止对应命令

#### Scenario: 任务自然结束
- **WHEN** 任务成功、失败、超时或被取消清理完成
- **THEN** worker SHALL 将 active runtime handle 更新为终态清理状态
- **AND** SHALL 从本 JVM 的运行中 registry 移除该任务句柄

### Requirement: 取消消息必须定点投递到任务所属 worker
取消清理消息 SHALL 根据 runtime handle 中的 `workerInstanceId` 定点投递到任务所属 worker 的专属取消队列。

#### Scenario: Worker 启动取消队列
- **WHEN** worker 应用启动
- **THEN** worker SHALL 生成或读取当前实例的 `workerInstanceId`
- **AND** SHALL 声明只服务当前实例的取消队列
- **AND** SHALL 将该队列绑定到取消 exchange 的 `worker.cancel.<workerInstanceId>` routing key

#### Scenario: 投递运行中任务取消消息
- **WHEN** 后端取消一个存在 active runtime handle 的运行中任务
- **THEN** 后端 SHALL 读取 runtime handle 的 `workerInstanceId`
- **AND** SHALL 使用 `worker.cancel.<workerInstanceId>` routing key 投递取消消息
- **AND** SHALL 使用 mandatory publish 或等效机制检测无法路由的取消消息
- **AND** 取消消息 MUST NOT 包含任务输入快照、明文凭据、日志内容或服务器真实路径

#### Scenario: 取消消息无法路由
- **WHEN** RabbitMQ 返回取消消息 unroutable
- **THEN** 后端 SHALL 将 runtime handle 标记为 `CANCEL_ROUTE_UNAVAILABLE`、`WORKER_LOST` 或等效清理异常状态
- **AND** 后端 SHALL 记录安全错误摘要
- **AND** 本地进程任务 MUST NOT 假定其他 worker 可以继续清理原 JVM 中的线程或 `Process` 句柄
- **AND** 远程进程任务 MAY 转入通用清理修复流程继续尝试远程 kill

#### Scenario: 所属 worker 不可用
- **WHEN** 取消消息无法投递或无法被所属 worker 消费
- **THEN** 后端 SHALL 保留任务业务状态 `CANCELLED`
- **AND** SHALL 将 runtime handle 标记为 worker lost、cancel unknown 或等效清理异常状态
- **AND** 远程任务 MAY 由后续清理修复流程继续尝试终止

### Requirement: 任务执行上下文必须支持协作式取消
任务执行上下文 SHALL 为 handler 提供取消检查和可取消资源登记能力。

#### Scenario: Handler 检查取消状态
- **WHEN** handler 在长步骤前后、循环内或等待外部进程期间调用取消检查
- **THEN** 执行上下文 SHALL 能返回当前任务是否已请求取消
- **AND** 在已请求取消时 SHALL 抛出统一取消异常或返回明确取消信号

#### Scenario: 用户取消触发 handler 退出
- **WHEN** handler 检测到任务已请求取消
- **THEN** handler SHALL 停止后续业务处理
- **AND** worker SHALL 将该路径视为用户取消而不是可重试失败

#### Scenario: 取消异常不重试原任务
- **WHEN** handler 因用户取消抛出统一取消异常
- **THEN** worker SHALL 确认原 RabbitMQ 任务消息
- **AND** worker MUST NOT 将该任务重新投递为重试任务

### Requirement: 取消清理必须覆盖本地和远程执行资源
任务运行时 SHALL 为本地外部进程和远程 SSH 命令提供统一取消清理能力。

#### Scenario: 取消本地进程
- **WHEN** 取消清理处理本地进程 runtime handle
- **THEN** worker SHALL 先尝试正常终止进程
- **AND** 在 grace period 后仍未退出时 SHALL 强制终止进程及可发现的子进程
- **AND** SHALL 记录退出结果或清理失败摘要

#### Scenario: 取消远程进程
- **WHEN** 取消清理处理远程进程 runtime handle
- **THEN** worker SHALL 通过 SSH 在目标环境执行远程终止命令
- **AND** SHALL 优先按远程 PGID 终止进程组
- **AND** 在目标环境不支持进程组时 SHALL 降级按远程 PID 终止并记录降级信息

#### Scenario: 取消清理失败
- **WHEN** 本地或远程取消清理失败
- **THEN** 后端 SHALL 记录清理失败状态、错误码和安全错误摘要
- **AND** 错误摘要 MUST NOT 暴露明文凭据、服务器真实路径或完整命令输入
- **AND** 取消清理消息 SHALL 按配置进入重试或 DLQ

### Requirement: 运行中任务取消说明必须满足严格校验
`running-task-cancellation` 主 spec 的 Purpose SHALL 清晰描述取消请求、任务状态、worker 定点取消、运行时句柄和底层资源清理边界。

#### Scenario: 严格校验运行中任务取消说明
- **WHEN** 执行 `openspec validate running-task-cancellation --type spec --strict`
- **THEN** 该 spec SHALL 不再因为 `Purpose section is too brief` 失败
