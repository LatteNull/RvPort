## ADDED Requirements

### Requirement: 数据库必须独立保存模型连通性测试结果
数据库 SHALL 支持保存模型 profile 最近连通性测试摘要，使模型 provider 可用性不与 agent runtime 兼容性混淆。

#### Scenario: 保存最近连通性结果
- **WHEN** 模型 profile 连通性测试完成
- **THEN** 数据库 SHALL 保存 profile 级最近连通性状态、脱敏消息、测试详情、测试时间和耗时
- **AND** 连通性结果 SHALL NOT 依赖 agent runtime ID
- **AND** 数据库 MUST NOT 保存 API key 明文、授权头、完整 prompt 或服务器真实敏感路径

#### Scenario: 查询连通性摘要
- **WHEN** 后端查询模型 profile 列表或详情
- **THEN** 数据库 SHALL 支持返回最近连通性状态和最近测试时间
- **AND** 查询 SHALL NOT 读取或返回 API key 密文字段作为响应内容

### Requirement: 数据库必须保存模型 Profile 到 Agent Runtime 的 Probe Run 和结果
数据库 SHALL 使用独立表保存模型 profile 对多个 agent runtime 的兼容性测试 run 和分项结果，避免 `model_profiles` 上的单组 `last_test_*` 字段覆盖多个 agent 的测试结果。

#### Scenario: 创建 Agent Probe Run
- **WHEN** 后端创建模型 profile 多 agent 测试
- **THEN** 数据库 SHALL 创建 `model_profile_agent_probe_runs`
- **AND** run SHALL 关联 `model_profile_id`
- **AND** run SHALL 保存聚合状态、触发用户、创建时间、开始时间、结束时间和脱敏消息
- **AND** run 状态 SHALL 支持 `PENDING`、`RUNNING`、`SUCCESS`、`PARTIAL_SUCCESS`、`FAILED` 和 `TIMEOUT`

#### Scenario: 保存单 Agent Probe 结果
- **WHEN** 某个 agent runtime 的 probe 完成
- **THEN** 数据库 SHALL 创建或更新 `model_profile_agent_probe_results`
- **AND** 结果 SHALL 关联 `run_id`、`model_profile_id` 和 `agent_runtime_id`
- **AND** 结果 SHALL 保存 agent 类型、聚合兼容性状态、分项 probe JSON、脱敏消息、错误码、开始时间、结束时间和耗时
- **AND** 数据库 SHALL 支持按 `model_profile_id`、`agent_runtime_id` 和最近测试时间查询最新结果

#### Scenario: 保持最新矩阵查询
- **WHEN** 后端查询某个模型 profile 的 agent 兼容性矩阵
- **THEN** 数据库 SHALL 能返回每个 agent runtime 的最近一次 probe 结果
- **AND** 新增 agent runtime SHALL NOT 要求修改 `model_profiles` 表的基础字段结构

#### Scenario: 查询活跃 Agent Probe Run
- **WHEN** 后端查询模型 profile 列表或详情
- **THEN** 数据库 SHALL 支持按 `model_profile_id` 查询最新的未终态 agent probe run
- **AND** 未终态 SHALL 包含 `PENDING` 和 `RUNNING`
- **AND** 查询 SHALL 能返回 run ID、聚合状态、所选 agent runtime 摘要和创建时间
- **AND** 同一个 profile 同时存在多个未终态 run 时，后端 SHALL 依据创建时间返回最新 run 并可将旧 run 标记为受控终态或忽略

#### Scenario: Probe 结果安全边界
- **WHEN** 保存 run 或 result 的详情字段
- **THEN** 数据库 MUST NOT 保存 API key、授权头、完整 agent 命令、完整 prompt、临时 workspace 绝对路径或服务器真实敏感路径
