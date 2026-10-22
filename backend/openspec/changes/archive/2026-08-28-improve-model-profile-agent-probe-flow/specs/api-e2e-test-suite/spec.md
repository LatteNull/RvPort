## ADDED Requirements

### Requirement: API E2E 必须覆盖模型连通性和多 Agent Probe 流程
API E2E 测试套件 SHALL 覆盖模型 profile 连通性测试、多 agent runtime 兼容性 probe、活跃 run 恢复、异常输入和无权限访问。

#### Scenario: 连通性测试正常流程
- **WHEN** E2E 使用超级管理员创建带有效连接配置的模型 profile 并调用连通性测试 API
- **THEN** 响应 SHALL 返回连通性状态、脱敏消息、测试时间和耗时
- **AND** 再次查询 profile 列表 SHALL 返回最近连通性摘要
- **AND** 响应 MUST NOT 包含 API key、授权头或完整 prompt

#### Scenario: 多 Agent Probe 正常流程
- **WHEN** E2E 使用超级管理员提交多个已启用 `agentRuntimeIds`
- **THEN** 创建接口 SHALL 返回 `runId` 和初始状态
- **AND** E2E SHALL 通过 run 查询接口获取每个 agent runtime 的分项 probe 结果
- **AND** 单个 runtime 的结果 SHALL 包含 agent 类型、runtime ID、分项状态、聚合兼容性状态和脱敏消息

#### Scenario: 列表返回活跃 Probe Run
- **WHEN** E2E 创建 agent probe run 后立即查询模型 profile 列表或详情
- **THEN** 对应 profile SHALL 返回 `activeAgentProbeRun`
- **AND** `activeAgentProbeRun.runId` SHALL 与创建接口返回的 run ID 一致
- **AND** E2E SHALL 能使用该 run ID 继续查询测试结果

#### Scenario: Agent Probe 异常输入
- **WHEN** E2E 提交空 `agentRuntimeIds`、重复 ID、不存在 ID 或禁用 runtime ID
- **THEN** API SHALL 返回统一参数或业务错误
- **AND** 后端 MUST NOT 创建部分非法 run
- **AND** 响应 MUST NOT 泄漏内部执行细节

#### Scenario: 单 Agent 失败不影响其他结果
- **WHEN** E2E 使用一个可用 runtime 和一个受控失败 runtime 创建 probe run
- **THEN** run SHALL 最终进入 `PARTIAL_SUCCESS` 或等效受控终态
- **AND** 成功 runtime 的结果 SHALL 被保存
- **AND** 失败 runtime 的结果 SHALL 返回脱敏失败原因

#### Scenario: 普通用户不能测试模型 Profile
- **WHEN** 普通用户调用连通性测试、agent probe run 创建、run 查询或 profile-agent 结果查询 API
- **THEN** 后端 SHALL 返回无权限错误
- **AND** 响应 MUST NOT 泄漏 profile、runtime 或 run 是否存在

#### Scenario: 旧测试接口兼容
- **WHEN** E2E 调用旧 `POST /api/admin/model-profiles/{profileId}:test`
- **THEN** 后端 SHALL 返回兼容旧结构的响应或明确迁移提示
- **AND** 响应 MUST NOT 泄漏 API key、授权头、完整 agent 命令或服务器真实敏感路径
