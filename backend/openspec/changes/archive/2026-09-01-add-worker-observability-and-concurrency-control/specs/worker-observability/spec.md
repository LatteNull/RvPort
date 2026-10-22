## ADDED Requirements

### Requirement: Worker 实例必须自动注册并上报心跳
后端 worker 节点 SHALL 在启动后自动注册 worker 实例，并 SHALL 周期性上报心跳、并发状态和当前运行任务数量。

#### Scenario: Worker 启动注册实例
- **WHEN** worker 节点以 worker 或 combined 模式启动
- **THEN** 后端 SHALL 生成或读取稳定的 `workerInstanceId`
- **AND** 后端 SHALL 在 `worker_instances` 中 upsert 对应实例记录
- **AND** 实例记录 SHALL 包含主机名、进程 ID、应用版本、启动时间、并发限制、实际并发和最近心跳时间

#### Scenario: Worker 周期性心跳
- **WHEN** worker 节点处于运行状态
- **THEN** 后端 SHALL 按配置的心跳间隔更新该 worker 的 `lastHeartbeatAt`
- **AND** 后端 SHALL 更新 `activeConcurrency` 和 `activeTaskCount`
- **AND** 心跳写入失败 MUST NOT 直接中断当前正在执行的任务

#### Scenario: Worker 离线判定
- **WHEN** 管理员查询 worker 列表或详情
- **AND** 某 worker 的最近心跳时间超过配置的离线阈值
- **THEN** API SHALL 将该 worker 展示为 `OFFLINE`
- **AND** API MUST NOT 将没有心跳的 worker 继续展示为可接收新任务

### Requirement: Worker 当前任务必须可观测
后端 SHALL 允许超级管理员查看每个 worker 当前正在执行的任务，并 SHALL 通过任务运行句柄和任务记录提供可审计摘要。

#### Scenario: 查询 worker 运行任务
- **WHEN** 超级管理员查询某个 worker 详情
- **THEN** API SHALL 返回该 worker 当前关联的运行中任务列表
- **AND** 每个任务摘要 SHALL 包含任务 ID、项目 ID、项目名称、任务类型、任务状态、进度、消息、开始时间和 runtime handle ID

#### Scenario: Worker 无运行任务
- **WHEN** 超级管理员查询在线但没有运行任务的 worker
- **THEN** API SHALL 返回空运行任务列表
- **AND** `activeTaskCount` SHALL 为 `0`

#### Scenario: 已离线 worker 的历史运行句柄
- **WHEN** 超级管理员查询离线 worker
- **THEN** API MAY 返回仍未完成清理的历史 runtime handle 摘要
- **AND** API SHALL 明确标记 worker 为 `OFFLINE`

### Requirement: 管理员必须能控制单个 worker 的最大并发
后端 SHALL 允许超级管理员为单个 worker 设置任务消费并发限制，并 SHALL 由目标 worker 周期性拉取后动态应用。

#### Scenario: 设置 worker 并发限制
- **WHEN** 超级管理员调用 worker 并发设置 API 并提交合法 `concurrencyLimit`
- **THEN** 后端 SHALL 更新该 worker 的并发限制
- **AND** 目标 worker SHALL 在后续心跳周期内读取并应用新的并发限制
- **AND** API SHALL 返回更新后的期望并发限制

#### Scenario: 并发限制为零
- **WHEN** 超级管理员将某个 worker 的 `concurrencyLimit` 设置为 `0`
- **THEN** 目标 worker SHALL 暂停接收新的任务队列消息
- **AND** 已经运行中的任务 SHALL 继续执行，除非用户通过任务取消 API 显式取消

#### Scenario: 并发限制恢复为正数
- **WHEN** 超级管理员将某个 worker 的 `concurrencyLimit` 从 `0` 设置为正数
- **THEN** 目标 worker SHALL 恢复接收任务队列消息
- **AND** 实际并发 SHALL 不超过新的 `concurrencyLimit`

#### Scenario: 并发限制超过上限
- **WHEN** 超级管理员提交超过系统 `maxConcurrencyLimit` 的并发限制
- **THEN** 后端 SHALL 返回统一业务错误
- **AND** 后端 MUST NOT 更新该 worker 的并发限制

#### Scenario: 普通用户不能管理 worker
- **WHEN** 非超级管理员调用 worker 列表、详情或并发设置 API
- **THEN** 后端 SHALL 拒绝请求
- **AND** 响应 MUST NOT 泄露 worker 实例、任务或主机信息

### Requirement: Worker prefetch 必须固定为一
后端 worker SHALL 将 RabbitMQ 任务 listener 的 prefetch 固定为 `1`，并 MUST NOT 将其作为可配置、可展示或可编辑字段暴露。

#### Scenario: Worker listener 使用固定 prefetch
- **WHEN** worker 启动任务队列 listener
- **THEN** listener container SHALL 使用 `prefetch=1`
- **AND** 每个 consumer 同时最多持有一条未确认任务消息

#### Scenario: 管理员接口不暴露 prefetch
- **WHEN** 超级管理员查询 worker 列表、worker 详情或更新 worker 并发
- **THEN** 响应 MUST NOT 包含 `prefetchCount`
- **AND** 请求 MUST NOT 接受 `prefetchCount` 作为可修改字段
