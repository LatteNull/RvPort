## ADDED Requirements

### Requirement: E2E 必须覆盖 Agent Runtime 选择
API E2E 测试套件 SHALL 覆盖 agent runtime 展示、阶段绑定、模型测试和测试比较运行时解析。

#### Scenario: 查询 agent runtime 列表
- **WHEN** E2E 使用超级管理员调用 agent runtime 列表 API
- **THEN** 响应 SHALL 至少包含 `CODEX`、`DEEPSEEK_HARNESS` 和 `OPENCODE`
- **AND** 响应 MUST NOT 包含 API key、授权头、完整 prompt 或服务器真实敏感路径

#### Scenario: 保存 TEST_LOG_COMPARE 模型和 agent 绑定
- **WHEN** E2E 创建或使用一个模型 profile 并选择一个已启用 agent runtime
- **THEN** E2E SHALL 调用阶段绑定 API 保存 `TEST_LOG_COMPARE` 绑定
- **AND** 再次查询 SHALL 返回同一个模型 profile 和 agent runtime

#### Scenario: 模型测试指定 agent runtime
- **WHEN** E2E 调用模型 profile 测试 API 并指定 agent runtime
- **THEN** 响应 SHALL 返回 agent 类型、agent runtime ID、分项 probe 和聚合兼容性状态
- **AND** 响应 MUST NOT 泄漏 API key 或完整命令

#### Scenario: 测试比较使用阶段绑定 agent
- **WHEN** E2E 通过 test-support 或完整自动化测试链路触发测试结果比较
- **THEN** 后端 SHALL 使用 `TEST_LOG_COMPARE` 阶段绑定的模型 profile 和 agent runtime
- **AND** 比较详情 SHALL 返回使用的 agent 类型或 runtime 摘要

#### Scenario: Agent runtime 缺失或禁用
- **WHEN** E2E 将 `TEST_LOG_COMPARE` 绑定到不可用 agent runtime 或未完成绑定
- **THEN** 测试比较 SHALL 返回不可用或受控失败状态
- **AND** 自动化测试结果本身 SHALL 仍可查询
