## ADDED Requirements

### Requirement: 测试结果比较必须使用 TEST_LOG_COMPARE 阶段绑定
模型 profile 管理 SHALL 将 `TEST_LOG_COMPARE` 阶段绑定作为测试结果比较 agent runtime 的唯一模型来源。

#### Scenario: 比较任务解析模型
- **WHEN** 后端准备自动创建或执行测试结果比较任务
- **THEN** 后端 SHALL 通过 `TEST_LOG_COMPARE` 阶段绑定解析模型 profile
- **AND** 后端 MUST NOT 从业务请求体读取 base URL、模型名、API key 或 provider 参数

#### Scenario: 比较任务模型不可用
- **WHEN** 阶段未绑定、绑定 profile 被禁用或 profile 缺少必要连接信息
- **THEN** 后端 SHALL 将自动比较摘要标记为不可用或返回测试结果比较功能不可用错误
- **AND** 后端 MUST NOT 泄漏 provider secret 或内部执行细节
