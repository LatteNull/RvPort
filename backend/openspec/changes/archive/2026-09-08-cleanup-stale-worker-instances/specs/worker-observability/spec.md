## ADDED Requirements

### Requirement: 失效 Worker 必须按阶段自动收敛和清理
后端 SHALL 周期性检查 Worker 心跳，并 SHALL 将短时离线、确认失联和超过保留期的 Worker 作为不同生命周期阶段处理。

#### Scenario: 短时离线 Worker 不被删除
- **WHEN** Worker 的最近心跳超过离线阈值但尚未超过失联确认时间
- **THEN** 管理 API SHALL 将该 Worker 展示为 `OFFLINE`
- **AND** 后端 MUST NOT 将其运行中任务标记为失败
- **AND** 后端 MUST NOT 删除该 Worker 注册记录

#### Scenario: 确认失联 Worker 的运行句柄被收敛
- **WHEN** Worker 的最近心跳超过失联确认时间
- **AND** 该 Worker 存在状态为 `ACTIVE`、`CANCEL_REQUESTED` 或 `CANCELLING` 的 runtime handle
- **THEN** 后端 SHALL 将这些 runtime handle 标记为 `WORKER_LOST`
- **AND** SHALL 记录终止时间和不包含凭据、命令输入或服务器真实路径的安全错误摘要

#### Scenario: 确认失联 Worker 的运行任务失败
- **WHEN** 被标记为 `WORKER_LOST` 的 runtime handle 对应任务仍为 `RUNNING`
- **THEN** 后端 SHALL 将任务更新为 `FAILED`
- **AND** SHALL 使用统一错误码 `WORKER_LOST`
- **AND** SHALL 设置任务完成时间
- **AND** SHALL 追加一次 `task.failed` 事件并发布对应项目级 SSE 状态变化
- **AND** SHALL 清理该任务的临时 secret payload

#### Scenario: 已终态任务不被失联清理覆盖
- **WHEN** 失联 Worker 的 runtime handle 对应任务已经是 `SUCCEEDED`、`FAILED`、`CANCELLED` 或 `TIMEOUT`
- **THEN** 后端 MUST NOT 修改任务状态或重复发布终态事件
- **AND** 后端 MAY 将仍为非终态的 runtime handle 收敛为 `WORKER_LOST`

#### Scenario: 超过保留期的 Worker 被删除
- **WHEN** Worker 最近心跳超过配置的记录保留期
- **AND** 该 Worker 不存在非终态 runtime handle
- **THEN** 后端 SHALL 删除该 `worker_instances` 注册记录
- **AND** MUST NOT 删除或修改历史任务、任务事件、日志和终态 runtime handle

#### Scenario: 存在非终态句柄时禁止删除 Worker
- **WHEN** Worker 最近心跳超过记录保留期
- **AND** 该 Worker 仍存在 `ACTIVE`、`CANCEL_REQUESTED` 或 `CANCELLING` runtime handle
- **THEN** 后端 MUST NOT 删除该 Worker 注册记录
- **AND** SHALL 优先尝试收敛相关句柄和任务

### Requirement: 失效 Worker 清理必须支持并发幂等
后端 SHALL 允许多个应用实例执行清理调度，并 MUST 保证同一 Worker、runtime handle 和任务不会被重复终止或生成重复事件。

#### Scenario: 多个调度器同时处理同一 Worker
- **WHEN** 两个或更多调度器同时选择同一个失联 Worker
- **THEN** 仅一个处理流程 SHALL 完成对应 runtime handle 和任务的终态迁移
- **AND** 每个任务 MUST 最多新增一次由本次失联收敛产生的 `task.failed` 事件
- **AND** 重复执行清理 SHALL 得到相同的最终状态

#### Scenario: 清理期间 Worker 恢复心跳
- **WHEN** Worker 在候选查询后、状态迁移提交前恢复有效心跳
- **THEN** 后端 SHALL 在提交前重新检查最近心跳
- **AND** MUST NOT 将已恢复 Worker 的任务标记为 `WORKER_LOST`
- **AND** MUST NOT 删除该 Worker 注册记录

#### Scenario: 单个 Worker 清理失败
- **WHEN** 某个失联 Worker 因数据库或事件处理异常未能完成收敛
- **THEN** 后端 SHALL 记录脱敏错误日志
- **AND** SHALL 继续处理本批次中的其他候选 Worker
- **AND** 后续调度 SHALL 能够幂等重试该 Worker

### Requirement: Worker 清理策略必须可配置且有界
后端 SHALL 提供 Worker 清理开关、调度周期、失联确认时间、记录保留时间和批量大小配置，并 SHALL 使用安全默认值限制单轮清理负载。

#### Scenario: 使用默认清理策略
- **WHEN** 部署未显式设置 Worker 清理配置
- **THEN** 后端 SHALL 默认启用清理
- **AND** SHALL 使用 300 秒失联确认时间、24 小时记录保留时间、300000 毫秒调度周期和 100 条批量上限
- **AND** 现有离线展示阈值 SHALL 保持 60 秒

#### Scenario: 禁用自动清理
- **WHEN** `rvport.worker.cleanup.enabled` 被设置为 `false`
- **THEN** 后端 MUST NOT 自动收敛或删除失效 Worker
- **AND** 现有 Worker 心跳和离线查询行为 SHALL 保持可用

#### Scenario: 清理配置时间边界非法
- **WHEN** 失联确认时间不大于离线阈值，或记录保留时间不大于失联确认时间
- **THEN** 后端 SHALL 拒绝使用该配置启动清理调度
- **AND** SHALL 输出不包含敏感信息的明确配置错误

#### Scenario: 单轮候选超过批量上限
- **WHEN** 待收敛或待删除 Worker 数量超过配置的批量大小
- **THEN** 后端 SHALL 在当前调度周期内最多处理配置数量的候选
- **AND** 剩余候选 SHALL 由后续调度继续处理
