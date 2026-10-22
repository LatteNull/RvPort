## ADDED Requirements

### Requirement: Agent Runtime Probe 必须支持按模型 Profile 批量执行
后端 agent runtime 选择能力 SHALL 支持模型 profile 针对多个指定 agent runtime 执行兼容性 probe，并 SHALL 使用统一 adapter 返回一致的分项结果。

#### Scenario: 按 Runtime 列表执行 Probe
- **WHEN** 模型 profile agent probe run 包含多个 agent runtime
- **THEN** 后端 SHALL 对每个 runtime 使用对应 agent adapter 执行兼容性 probe
- **AND** 每个 runtime SHALL 生成独立的 probe 状态、分项结果、耗时和脱敏消息
- **AND** 单个 runtime 失败 SHALL NOT 阻止其他 runtime 执行

#### Scenario: Runtime 不可用
- **WHEN** 请求中的 agent runtime 不存在、未启用或没有已注册 adapter
- **THEN** 后端 SHALL 拒绝创建 probe run 或将对应 runtime 标记为受控失败
- **AND** 响应 MUST NOT 泄漏完整命令、内部路径或 provider secret

#### Scenario: Probe 输出统一
- **WHEN** 任意 agent runtime 执行 profile 兼容性 probe
- **THEN** 后端 SHALL 使用统一结果结构保存 `AGENT_TEXT`、`AGENT_WORKSPACE_TOOL` 和 `TEST_COMPARE_SCHEMA` 分项结果
- **AND** 结果 SHALL 能表达该 runtime 是否可用于 `TEST_LOG_COMPARE` 阶段
