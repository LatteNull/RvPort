## MODIFIED Requirements

### Requirement: 模型测试 API 必须返回指定 agent 兼容性分项结果
后端 API SHALL 在模型 profile 测试响应中返回 agent 类型、阶段无关的通用分项 probe 结果和聚合兼容性状态，使前端能够判断模型 Profile 是否能被指定 Agent Runtime 驱动。

#### Scenario: 返回模型测试分项结果
- **WHEN** 超级管理员调用模型 profile Agent 兼容性测试 API
- **THEN** 响应 SHALL 包含每个通用 probe 的名称、状态、错误码、脱敏消息和测试时间
- **AND** 响应 SHALL 包含当前测试的 agent runtime ID 和 agent 类型
- **AND** 响应 SHALL 包含 Agent 响应、workspace 读取、workspace 写入和聚合兼容状态
- **AND** 响应 MUST NOT 包含测试比较、KB AI 扩展或其他业务阶段兼容状态
- **AND** 响应 MUST NOT 返回 API key、授权头、完整 agent 命令或服务器真实路径

#### Scenario: 列表展示最近兼容性状态
- **WHEN** 超级管理员查询模型 profile 列表或详情
- **THEN** 列表项 SHALL 返回每个 Agent Runtime 的最近通用兼容状态、通用检查摘要和测试时间
- **AND** 列表项 MUST NOT 返回 `lastTestCompareCompatible` 或其他阶段兼容性字段
- **AND** 列表项 MUST NOT 返回 provider secret

### Requirement: 模型 Profile API 必须拆分连通性测试和 Agent 兼容性测试
后端 API SHALL 为超级管理员提供独立的模型连通性测试 API 和多 agent runtime 通用兼容性测试 API，避免长时间 agent probe 阻塞同步 HTTP 请求，并保持阶段绑定职责独立。

#### Scenario: 模型连通性测试
- **WHEN** 超级管理员调用 `POST /api/admin/model-profiles/{profileId}:test-connectivity`
- **THEN** API SHALL 使用已保存配置或请求中的临时覆盖配置执行模型 provider 连通性测试
- **AND** API SHALL 返回 `status`、`message`、`testedAt`、`durationMillis` 和脱敏后的 `details`
- **AND** 后端 SHALL 记录最近一次连通性测试摘要
- **AND** 响应 MUST NOT 返回 API key、授权头、完整 prompt 或服务器真实敏感路径

#### Scenario: 创建多 Agent 测试 Run
- **WHEN** 超级管理员调用 `POST /api/admin/model-profiles/{profileId}:test-agents` 并提交 `agentRuntimeIds`
- **THEN** API SHALL 校验 `agentRuntimeIds` 非空且去重后全部指向已启用 agent runtime
- **AND** API SHALL 创建 agent probe run 并立即返回 `runId`、`status`、`profileId`、`agentRuntimes`、`createdAt`
- **AND** 后端 SHALL 在后台执行所选 agent runtime 的通用兼容性测试
- **AND** 后端 MUST NOT 读取 `model_stage_assignments` 决定测试内容或结果
- **AND** 响应 MUST NOT 等待所有 agent runtime probe 完成

#### Scenario: 查询 Agent 测试 Run
- **WHEN** 超级管理员调用 `GET /api/admin/model-profile-agent-test-runs/{runId}`
- **THEN** API SHALL 返回 run 聚合状态、模型 profile 摘要、agent runtime 分项状态、通用 probe、脱敏消息、开始时间和结束时间
- **AND** 未完成的 runtime SHALL 返回 `PENDING` 或 `RUNNING`
- **AND** 失败 runtime SHALL 返回脱敏失败原因
- **AND** 响应 MUST NOT 返回业务阶段兼容性字段

#### Scenario: 查询 Profile Agent Probe 结果
- **WHEN** 超级管理员调用 `GET /api/admin/model-profiles/{profileId}/agent-probe-results`
- **THEN** API SHALL 返回该 profile 对各 agent runtime 的最近通用兼容性结果
- **AND** 响应 SHALL 支持按 agent 类型、runtime 启用状态、兼容性状态和最近测试时间过滤或排序
- **AND** 兼容性结果 SHALL 以模型 Profile ID 与 Agent Runtime ID 为组合维度

#### Scenario: 列表返回测试摘要
- **WHEN** 超级管理员调用 `GET /api/admin/model-profiles`
- **THEN** 列表项 SHALL 返回最近连通性状态、最近连通性测试时间和脱敏连通性消息
- **AND** 列表项 SHALL 返回通用 agent 兼容性摘要或可展开结果引用
- **AND** 如果该 profile 存在 `PENDING` 或 `RUNNING` 的 agent probe run，列表项 SHALL 返回 `activeAgentProbeRun`
- **AND** `activeAgentProbeRun` SHALL 包含 `runId`、`status`、所选 agent runtime 摘要和创建时间
- **AND** 列表项 SHALL NOT 返回 `activeConnectivityRun`，因为连通性测试为同步请求且不创建后台 run
- **AND** 响应 MUST NOT 返回 provider secret 或阶段兼容性字段

#### Scenario: 详情返回活跃 Agent Probe Run
- **WHEN** 超级管理员调用模型 profile 详情 API
- **THEN** API SHALL 返回该 profile 最近连通性摘要、通用 agent 兼容性矩阵摘要和当前活跃 agent probe run
- **AND** 如果不存在未终态 run，`activeAgentProbeRun` SHALL 为空
- **AND** API SHALL NOT 返回活跃连通性 run
- **AND** 前端 SHALL 能依据 `activeAgentProbeRun.runId` 继续查询 run 结果

#### Scenario: 阶段绑定独立于兼容性测试
- **WHEN** 超级管理员查询或保存 `model_stage_assignments`
- **THEN** API SHALL 继续按阶段保存模型 Profile 与 Agent Runtime 组合
- **AND** 阶段绑定 SHALL NOT 改变该组合的通用兼容性记录
- **AND** 兼容性测试 SHALL NOT 因组合绑定到不同阶段而产生不同结果结构

#### Scenario: 普通用户访问测试 API
- **WHEN** 非超级管理员调用模型连通性、agent probe run 或结果查询 API
- **THEN** API SHALL 返回无权限错误
- **AND** 响应 MUST NOT 泄漏 profile、runtime、run 是否存在或内部执行细节
