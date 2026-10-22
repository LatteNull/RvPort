## MODIFIED Requirements

### Requirement: 测试结果比较必须调用 Codex agent 并保存结构化结果
测试结果比较运行时 SHALL 通过 `TEST_LOG_COMPARE` 阶段解析的模型 profile 和 agent runtime 调用已绑定 agent，并保存结构化比较结果。

#### Scenario: agent 比较成功
- **WHEN** 已绑定 agent 返回合法比较结果
- **THEN** 后端 SHALL 保存比较运行状态为 `SUCCEEDED`
- **AND** 后端 SHALL 保存总体结论、风险等级、置信度、摘要和建议
- **AND** 后端 SHALL 保存结构化差异项
- **AND** 后端 SHALL 保存原始 agent 输出 artifact
- **AND** 原始输出 artifact SHALL 包含脱敏后的 `mergedOutput`

#### Scenario: agent 输出不可解析
- **WHEN** 已绑定 agent 返回非 JSON、字段缺失或结构不合法的输出
- **THEN** 后端 SHALL 保存原始 agent 输出 artifact
- **AND** 后端 SHALL 将比较运行标记为 `FAILED` 或等效受控失败状态
- **AND** 后端 SHALL 返回基于 `mergedOutput` 的脱敏错误摘要

#### Scenario: agent 执行失败
- **WHEN** 已绑定 agent 超时、进程退出码非 0 或 provider 调用失败
- **THEN** 后端 SHALL 将比较运行标记为 `FAILED` 或 `TIMEOUT`
- **AND** 后端 SHALL 保存基于 `mergedOutput` 的脱敏失败摘要
- **AND** 任务状态 SHALL 与比较运行状态一致

## ADDED Requirements

### Requirement: 测试结果比较必须使用阶段绑定的 Agent Runtime
测试结果比较 SHALL 使用 `TEST_LOG_COMPARE` 阶段绑定的 agent runtime，而不是固定使用 Codex。

#### Scenario: 解析完整阶段绑定
- **WHEN** 后端执行测试结果比较任务
- **THEN** 后端 SHALL 从阶段绑定解析模型 profile 和 agent runtime
- **AND** 后端 SHALL 通过 agent adapter registry 选择对应 adapter
- **AND** 业务任务输入 MUST NOT 包含 agent 类型、可执行路径、模型名、base URL 或 API key

#### Scenario: Agent runtime 未配置
- **WHEN** `TEST_LOG_COMPARE` 阶段没有绑定 agent runtime 或绑定 runtime 不可用
- **THEN** 后端 SHALL 将比较标记为不可用或失败
- **AND** 自动化测试结果本身 MUST 保持可查询
- **AND** 错误摘要 MUST NOT 泄漏内部命令或密钥

#### Scenario: 保存运行时摘要
- **WHEN** 比较任务完成或失败
- **THEN** 比较详情 SHALL 能返回使用的 agent 类型和 agent runtime 摘要
- **AND** 响应 MUST NOT 返回完整 agent 命令、完整 prompt、API key 或服务器真实路径
