## MODIFIED Requirements

### Requirement: API E2E 必须覆盖模型连通性和多 Agent Probe 流程
API E2E 测试套件 SHALL 覆盖模型 profile 连通性测试、多 agent runtime 通用兼容性 probe、活跃 run 恢复、异常输入、阶段无关性和无权限访问。

#### Scenario: 连通性测试正常流程
- **WHEN** E2E 使用超级管理员创建带有效连接配置的模型 profile 并调用连通性测试 API
- **THEN** 响应 SHALL 返回连通性状态、脱敏消息、测试时间和耗时
- **AND** 再次查询 profile 列表 SHALL 返回最近连通性摘要
- **AND** 响应 MUST NOT 包含 API key、授权头或完整 prompt

#### Scenario: 多 Agent Probe 正常流程
- **WHEN** E2E 使用超级管理员提交多个已启用 `agentRuntimeIds`
- **THEN** 创建接口 SHALL 返回 `runId` 和初始状态
- **AND** E2E SHALL 通过 run 查询接口获取每个 agent runtime 的通用分项 probe 结果
- **AND** 单个 runtime 的结果 SHALL 包含 agent 类型、runtime ID、Agent 响应、workspace 读取、workspace 写入、聚合兼容性状态和脱敏消息
- **AND** 结果 MUST NOT 包含测试比较、KB AI 扩展或其他业务阶段兼容性字段

#### Scenario: Probe 与阶段绑定无关
- **WHEN** E2E 对同一模型 Profile 与 Agent Runtime 组合执行兼容性 probe
- **AND** 该组合未绑定阶段或绑定到任意一个或多个允许阶段
- **THEN** probe 的检查集合和结果结构 SHALL 保持一致
- **AND** 后端 MUST NOT 因阶段绑定生成阶段专属检查

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

#### Scenario: 通用 Workspace 输出异常
- **WHEN** Agent 未创建结果文件、写出无效 JSON、marker 不匹配或 probe 超时
- **THEN** 对应 runtime 的通用兼容性结果 SHALL 为失败
- **AND** 临时 workspace SHALL 被清理
- **AND** 失败消息 MUST NOT 泄漏 API key、完整 prompt 或服务器真实路径

#### Scenario: 普通用户不能测试模型 Profile
- **WHEN** 普通用户调用连通性测试、agent probe run 创建、run 查询或 profile-agent 结果查询 API
- **THEN** 后端 SHALL 返回无权限错误
- **AND** 响应 MUST NOT 泄漏 profile、runtime 或 run 是否存在

#### Scenario: 旧测试接口兼容
- **WHEN** E2E 调用旧 `POST /api/admin/model-profiles/{profileId}:test`
- **THEN** 后端 SHALL 返回兼容旧入口的通用单 Agent 结果或明确迁移提示
- **AND** 响应 MUST NOT 返回阶段兼容性字段
- **AND** 响应 MUST NOT 泄漏 API key、授权头、完整 agent 命令或服务器真实敏感路径
