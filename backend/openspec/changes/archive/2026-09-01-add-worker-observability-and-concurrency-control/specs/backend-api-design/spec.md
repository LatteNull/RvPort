## ADDED Requirements

### Requirement: 管理员 API 必须提供 worker 观测和并发控制
后端 API SHALL 提供超级管理员专用 worker 管理接口，用于查看自动接入 worker、查看 worker 当前任务和控制单 worker 最大并发。

#### Scenario: 查询 worker 列表
- **WHEN** 超级管理员调用 `GET /api/admin/workers`
- **THEN** API SHALL 返回分页 worker 列表
- **AND** 每个 worker SHALL 包含实例 ID、主机名、状态、并发限制、实际并发、运行任务数量、启动时间和最近心跳时间
- **AND** 响应 MUST NOT 包含 `prefetchCount`

#### Scenario: 查询 worker 详情
- **WHEN** 超级管理员调用 `GET /api/admin/workers/{workerInstanceId}`
- **THEN** API SHALL 返回 worker 基础信息和当前运行任务列表
- **AND** 运行任务 SHALL 包含任务 ID、项目 ID、项目名称、任务类型、状态、进度、消息、开始时间和 runtime handle ID

#### Scenario: 调整 worker 并发
- **WHEN** 超级管理员调用 `PUT /api/admin/workers/{workerInstanceId}/concurrency`
- **AND** 请求体包含合法 `concurrencyLimit`
- **THEN** API SHALL 更新该 worker 的期望并发限制
- **AND** API SHALL 返回更新后的 worker 并发摘要

#### Scenario: 暂停 worker 接新任务
- **WHEN** 超级管理员将 `concurrencyLimit` 设置为 `0`
- **THEN** API SHALL 接受该请求
- **AND** 后端 SHALL 将该 worker 标记为暂停接收新任务
- **AND** 后端 MUST NOT 取消该 worker 已经运行中的任务

#### Scenario: 非法并发限制
- **WHEN** 请求提交负数、超过系统上限或非数字的 `concurrencyLimit`
- **THEN** API SHALL 返回统一参数或业务错误
- **AND** 后端 MUST NOT 修改原有并发限制

#### Scenario: 非超级管理员访问 worker API
- **WHEN** 非超级管理员访问 worker 管理 API
- **THEN** API SHALL 返回无权限错误
- **AND** 响应 MUST NOT 泄露 worker 是否存在、主机名、任务信息或部署信息

#### Scenario: Worker 列表支持分页排序过滤
- **WHEN** 超级管理员查询 worker 列表
- **THEN** API SHALL 支持分页参数
- **AND** API SHALL 支持按状态、实例 ID、主机名和是否有运行任务过滤
- **AND** API SHALL 支持按最近心跳时间、启动时间和运行任务数量排序
