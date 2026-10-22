## ADDED Requirements

### Requirement: 任务运行时必须支持测试结果比较任务类型
任务运行时 SHALL 支持 `TEST_LOG_COMPARE` 长任务类型，用于异步执行测试结果比较。

#### Scenario: 自动创建测试结果比较任务
- **WHEN** 自动化测试节点两侧测试记录完成且比较模型配置可用
- **THEN** 任务类型 SHALL 为 `TEST_LOG_COMPARE`
- **AND** 任务输入 SHALL 只包含比较运行 ID、项目 ID、两条测试运行 ID 和必要路由信息
- **AND** 任务输入 MUST NOT 包含完整日志、完整报告、完整 agent 输入、明文凭据或模型 secret

#### Scenario: 模型不可用时不投递任务
- **WHEN** 自动化测试节点两侧测试记录完成但比较模型未配置或不可用
- **THEN** 后端 SHALL 记录比较不可用摘要
- **AND** 后端 MUST NOT 投递 `TEST_LOG_COMPARE` 任务
- **AND** 自动化测试任务状态 MUST NOT 因比较不可用被改写为失败

#### Scenario: 执行测试结果比较任务
- **WHEN** worker 消费 `TEST_LOG_COMPARE` 任务
- **THEN** worker SHALL 将任务和比较运行状态更新为 `RUNNING`
- **AND** worker SHALL 聚合测试结果并调用 Codex agent
- **AND** worker SHALL 在完成后写回比较运行、差异项和 agent 输出 artifact
- **AND** worker SHALL 在失败时写回受控错误摘要

#### Scenario: 测试结果比较任务事件
- **WHEN** 测试结果比较任务状态或进度变化
- **THEN** 后端 SHALL 追加 `task_events`
- **AND** 项目级 SSE SHALL 只向有权访问该项目的订阅者推送事件

#### Scenario: 取消测试结果比较任务
- **WHEN** `TEST_LOG_COMPARE` 任务被取消
- **THEN** worker SHALL 尝试终止 Codex agent 进程
- **AND** 任务状态 SHALL 更新为 `CANCELLED`
- **AND** 比较运行状态 SHALL 更新为 `CANCELLED`
