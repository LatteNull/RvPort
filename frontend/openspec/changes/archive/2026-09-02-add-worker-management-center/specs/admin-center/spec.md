## ADDED Requirements

### Requirement: Administrator Worker management

前端 SHALL 为超级管理员提供独立 Worker 管理页面，使用后端 Worker 管理 API 展示自动接入实例、运行状态、并发状态、最近心跳和当前运行任务，并允许设置单实例任务消费并发限制。

#### Scenario: Administrator inspects Worker instances

- **WHEN** 超级管理员进入 `/admin/workers`
- **THEN** 前端 SHALL 展示 Worker 列表并支持按实例、主机、在线状态和运行任务筛选
- **AND** 列表 SHALL 区分期望并发、实际并发和运行任务数量
- **AND** 管理员 SHALL 能查看单个 Worker 的完整信息与当前运行任务

#### Scenario: Administrator updates Worker concurrency

- **WHEN** 超级管理员为 Worker 提交非负整数 `concurrencyLimit`
- **THEN** 前端 SHALL 调用对应 Worker 并发更新 API
- **AND** 成功后 SHALL 刷新列表和详情中的并发状态
- **AND** 当值为 `0` 时 SHALL 说明 Worker 将暂停接收新任务，但不会取消正在运行的任务

#### Scenario: Administrator refreshes Worker state

- **WHEN** 超级管理员需要获取最新心跳或负载状态
- **THEN** 前端 SHALL 提供显式刷新入口
- **AND** 页面 SHALL NOT 为此新增后台轮询
