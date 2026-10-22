## ADDED Requirements

### Requirement: API E2E 必须覆盖运行中任务取消
API E2E 测试套件 SHALL 覆盖运行中任务取消的正常流程、异常流程和 edge case，并 SHALL 验证任务事件、SSE 和清理状态。

#### Scenario: 正常取消运行中任务
- **WHEN** E2E 创建可控运行中任务并调用 `POST /api/tasks/{taskId}/cancel`
- **THEN** API SHALL 返回 `CANCELLED` 任务状态
- **AND** E2E SHALL 验证任务详情、项目任务列表和 SSE 均能观察到 `task.cancelled`
- **AND** E2E SHALL 验证对应 runtime handle 进入取消清理终态或可解释的清理异常状态

#### Scenario: 无权限取消运行中任务
- **WHEN** E2E 使用无项目权限用户取消另一个项目的运行中任务
- **THEN** API SHALL 返回安全错误
- **AND** E2E SHALL 验证任务状态未被改变
- **AND** E2E SHALL 验证未产生取消事件或取消清理消息

#### Scenario: 重复取消任务
- **WHEN** E2E 对同一运行中任务连续调用取消接口
- **THEN** API SHALL 幂等返回 `CANCELLED` 或当前终态
- **AND** E2E SHALL 验证不会重复产生不可解释的取消清理副作用

#### Scenario: 取消清理失败可观测
- **WHEN** E2E 通过 test-support 制造取消清理失败
- **THEN** 任务业务状态 SHALL 保持 `CANCELLED`
- **AND** runtime handle SHALL 记录失败状态和安全错误摘要
- **AND** 取消消息 SHALL 按配置进入重试或 DLQ

#### Scenario: 目标 worker 取消队列不存在
- **WHEN** E2E 通过 test-support 制造 active runtime handle 指向不存在的 `workerInstanceId`
- **THEN** 取消 API SHALL 仍将任务业务状态更新为 `CANCELLED`
- **AND** RabbitMQ unroutable publisher return SHALL 被捕获
- **AND** runtime handle SHALL 记录路由不可达、worker 不存在或等效清理异常状态
