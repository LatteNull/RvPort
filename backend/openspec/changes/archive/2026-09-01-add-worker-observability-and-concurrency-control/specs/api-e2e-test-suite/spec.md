## ADDED Requirements

### Requirement: API E2E 必须覆盖 worker 观测和并发控制
API E2E 测试套件 SHALL 覆盖 worker 实例注册、心跳、列表查询、详情查询、并发设置和暂停接新任务行为。

#### Scenario: 覆盖 worker 注册和列表
- **WHEN** E2E 以 worker enabled 的后端实例运行
- **THEN** 测试 SHALL 查询 `GET /api/admin/workers`
- **AND** 响应 SHALL 包含当前 worker 实例
- **AND** worker SHALL 包含在线状态、并发限制、实际并发、运行任务数量和最近心跳时间
- **AND** 响应 MUST NOT 包含 `prefetchCount`

#### Scenario: 覆盖 worker 详情和运行任务
- **WHEN** E2E 创建可控长任务并等待其进入 `RUNNING`
- **THEN** 测试 SHALL 查询对应 worker 详情
- **AND** 响应 SHALL 在运行任务列表中包含该任务
- **AND** 任务摘要 SHALL 包含任务 ID、任务类型、项目 ID、状态、进度和 runtime handle ID

#### Scenario: 覆盖并发大于一
- **WHEN** E2E 将 worker `concurrencyLimit` 设置为 `2`
- **AND** E2E 投递两个可控长任务
- **THEN** 两个任务 SHALL 能同时进入 `RUNNING`
- **AND** 任一任务完成或取消 MUST NOT 影响另一个任务继续执行

#### Scenario: 覆盖暂停接新任务
- **WHEN** E2E 将 worker `concurrencyLimit` 设置为 `0`
- **AND** E2E 投递新的异步任务
- **THEN** 该 worker SHALL 不再认领新的任务
- **AND** 已经运行中的任务 SHALL 不因该设置被取消

#### Scenario: 覆盖非法并发和权限
- **WHEN** E2E 使用非法 `concurrencyLimit` 或普通用户访问 worker 管理 API
- **THEN** API SHALL 返回统一错误
- **AND** 后端 MUST NOT 修改 worker 并发限制
- **AND** 响应 MUST NOT 泄露 worker 主机或任务明细

#### Scenario: 覆盖离线 worker 展示
- **WHEN** E2E 使用测试支持能力制造超过心跳阈值的 worker 记录
- **THEN** worker 列表 SHALL 将该实例展示为 `OFFLINE`
- **AND** 该实例 MUST NOT 被展示为可接收新任务
