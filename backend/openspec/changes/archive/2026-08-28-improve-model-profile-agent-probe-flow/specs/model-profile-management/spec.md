## ADDED Requirements

### Requirement: 模型 Profile 连通性测试必须独立于 Agent Probe
模型 profile 管理 SHALL 提供独立连通性测试能力，用于验证模型 provider 配置是否可用，且 SHALL NOT 在连通性测试中启动 agent runtime。

#### Scenario: 测试模型连通性
- **WHEN** 超级管理员对模型 profile 发起连通性测试
- **THEN** 后端 SHALL 使用 profile 的 provider 类型、base URL、模型名、wire API、timeout 和 API key 执行最小模型调用
- **AND** 后端 SHALL 返回连通性状态、脱敏消息、测试时间和耗时
- **AND** 后端 SHALL 保存最近一次连通性测试摘要
- **AND** 响应和数据库 MUST NOT 保存 API key、授权头、完整 prompt 或服务器真实敏感路径

#### Scenario: 临时覆盖配置测试连通性
- **WHEN** 超级管理员提交临时覆盖配置执行连通性测试
- **THEN** 后端 SHALL 使用覆盖后的配置执行测试
- **AND** 临时覆盖中的 API key MUST NOT 被持久化，除非调用保存 API
- **AND** 测试结果中的错误信息 MUST 脱敏

#### Scenario: 连通性测试不启动 Agent
- **WHEN** 后端执行模型连通性测试
- **THEN** 后端 SHALL NOT 创建 agent workspace
- **AND** 后端 SHALL NOT 调用 Codex、DeepSeek Harness、OpenCode 或其他 agent runtime adapter

### Requirement: 模型 Profile Agent Probe 必须支持多 Runtime 选择
模型 profile 管理 SHALL 支持超级管理员选择一个或多个 agent runtime 对模型 profile 执行兼容性 probe，并 SHALL 独立保存每个 agent runtime 的分项结果。

#### Scenario: 创建多 Agent Probe Run
- **WHEN** 超级管理员提交 `agentRuntimeIds` 列表测试模型 profile
- **THEN** 后端 SHALL 校验列表非空、runtime 存在且启用
- **AND** 后端 SHALL 创建一次 agent probe run
- **AND** 响应 SHALL 返回 `runId`、聚合状态、所选 runtime 摘要和创建时间
- **AND** 后端 SHALL 在后台执行所选 agent runtime 的兼容性 probe

#### Scenario: 查询 Agent Probe Run
- **WHEN** 超级管理员查询 agent probe run
- **THEN** 后端 SHALL 返回 run 的聚合状态、profile 摘要、所选 runtime 摘要、每个 runtime 的分项 probe 结果、脱敏消息、开始时间和结束时间
- **AND** 单个 runtime 失败 SHALL 只影响该 runtime 的结果和 run 聚合状态
- **AND** 响应 MUST NOT 返回 API key、授权头、完整 agent 命令、完整 prompt 或服务器真实敏感路径

#### Scenario: 查询 Profile Agent 兼容性矩阵
- **WHEN** 超级管理员查询模型 profile 详情或 agent probe 结果列表
- **THEN** 后端 SHALL 返回该 profile 对各 agent runtime 的最近兼容性状态
- **AND** 每个结果 SHALL 包含 agent runtime ID、agent 类型、基础 agent 能力状态、workspace/tool 闭环状态、测试比较 schema 状态、最近测试时间和脱敏消息

#### Scenario: 后续新增 Agent Runtime
- **WHEN** 后端新增新的 agent runtime 类型
- **THEN** 模型 profile agent probe SHALL 能为该 runtime 记录独立结果
- **AND** 后端 SHALL NOT 要求改变 `model_profiles` 的基础配置结构

### Requirement: 模型 Profile 测试旧接口必须作为兼容入口
模型 profile 管理 SHALL 保留旧模型 profile 测试接口的兼容语义，但新功能 SHALL 使用独立连通性测试和多 agent probe run API。

#### Scenario: 旧接口兼容调用
- **WHEN** 旧前端调用 `POST /api/admin/model-profiles/{profileId}:test`
- **THEN** 后端 SHALL 返回兼容格式的单 agent 测试结果或明确迁移提示
- **AND** 后端 SHALL 使用指定 `agentRuntimeId`、阶段绑定 runtime 或默认 runtime 之一进行兼容处理
- **AND** 响应 MUST NOT 泄漏 provider secret、完整 agent 命令或服务器真实敏感路径

#### Scenario: 新前端使用新接口
- **WHEN** 前端需要测试模型 profile
- **THEN** 前端 SHALL 优先调用连通性测试 API 验证模型配置
- **AND** 前端 SHALL 调用多 agent probe run API 验证用户选择的 agent runtime 列表
