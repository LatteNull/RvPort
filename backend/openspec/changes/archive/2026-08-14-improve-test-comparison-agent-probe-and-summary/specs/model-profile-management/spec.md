## ADDED Requirements

### Requirement: 模型 Profile 测试必须验证指定 agent 兼容性
模型 profile 管理 SHALL 在可用性测试中验证模型是否支持指定 agent 工作模式，并 SHALL 返回 agent 类型、分项 probe 结果和聚合兼容性状态。

#### Scenario: 测试基础文本能力
- **WHEN** 超级管理员测试模型 profile
- **THEN** 后端 SHALL 验证模型能够完成基础文本 JSON 输出
- **AND** 结果 SHALL 包含 `BASIC_TEXT` 或等效分项状态

#### Scenario: 测试 agent 纯文本能力
- **WHEN** 超级管理员测试模型 profile
- **THEN** 后端 SHALL 使用该 profile 配置运行指定 agent 的纯文本最小任务
- **AND** 结果 SHALL 包含 `AGENT_TEXT` 或等效分项状态
- **AND** 结果 SHALL 包含当前测试的 `agentType`

#### Scenario: 测试 agent workspace 工具闭环
- **WHEN** 超级管理员测试模型 profile
- **THEN** 后端 SHALL 创建临时 workspace 和测试输入文件
- **AND** 后端 SHALL 使用指定 agent 要求读取该文件并返回指定 JSON
- **AND** 测试 SHALL 覆盖模型发起工具调用、agent 执行工具、工具结果回传和最终 JSON 输出的完整闭环
- **AND** 结果 SHALL 包含 `AGENT_WORKSPACE_TOOL` 或等效分项状态
- **AND** 结果 SHALL 包含当前测试的 `agentType`

#### Scenario: 测试测试比较输出 schema
- **WHEN** 超级管理员测试用于 `TEST_LOG_COMPARE` 的模型 profile
- **THEN** 后端 SHALL 使用接近测试结果比较场景的最小输入验证指定 agent 能返回可解析的比较 JSON
- **AND** 结果 SHALL 包含 `TEST_COMPARE_SCHEMA` 或等效分项状态

#### Scenario: 返回聚合兼容性状态
- **WHEN** 模型 profile 测试完成
- **THEN** API 响应 SHALL 返回 agent 类型、基础可用状态、agent 兼容状态和测试比较兼容状态
- **AND** 后端 SHALL 保存最近一次测试的脱敏摘要、分项结果和测试时间
- **AND** 响应 MUST NOT 返回 API key、授权头、完整 agent 命令或服务器真实路径

#### Scenario: 基础可用但 agent 不兼容
- **WHEN** 模型基础文本测试通过但 workspace 工具闭环测试失败
- **THEN** 后端 SHALL 将基础可用状态标记为可用
- **AND** 后端 SHALL 将当前 agent 兼容状态标记为不兼容
- **AND** 脱敏消息 SHALL 明确说明该模型不能用于当前 agent 工作模式

#### Scenario: 后续新增 agent 类型
- **WHEN** 后端新增非 `CODEX` 的 agent 执行器
- **THEN** 模型 profile 测试结果 SHALL 能记录该 agent 类型对应的分项 probe 结果
- **AND** 阶段绑定 SHALL 能依据该 agent 类型判断模型是否适用于对应阶段
- **AND** 后端 SHALL NOT 要求重建模型 profile 的基础数据结构
