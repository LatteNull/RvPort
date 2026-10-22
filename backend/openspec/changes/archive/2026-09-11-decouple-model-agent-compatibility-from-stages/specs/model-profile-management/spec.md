## MODIFIED Requirements

### Requirement: 模型 Profile Agent Probe 必须支持多 Runtime 选择
模型 profile 管理 SHALL 支持超级管理员选择一个或多个 agent runtime 对模型 profile 执行阶段无关的通用兼容性 probe，并 SHALL 独立保存每个模型 Profile 与 agent runtime 组合的分项结果。

#### Scenario: 创建多 Agent Probe Run
- **WHEN** 超级管理员提交 `agentRuntimeIds` 列表测试模型 profile
- **THEN** 后端 SHALL 校验列表非空、runtime 存在且启用
- **AND** 后端 SHALL 创建一次 agent probe run
- **AND** 响应 SHALL 返回 `runId`、聚合状态、所选 runtime 摘要和创建时间
- **AND** 后端 SHALL 在后台执行所选 agent runtime 的通用兼容性 probe
- **AND** 后端 MUST NOT 查询或依赖该组合是否绑定到任何业务阶段

#### Scenario: 查询 Agent Probe Run
- **WHEN** 超级管理员查询 agent probe run
- **THEN** 后端 SHALL 返回 run 的聚合状态、profile 摘要、所选 runtime 摘要、每个 runtime 的通用分项 probe 结果、脱敏消息、开始时间和结束时间
- **AND** 单个 runtime 失败 SHALL 只影响该 runtime 的结果和 run 聚合状态
- **AND** 响应 MUST NOT 返回 API key、授权头、完整 agent 命令、完整 prompt 或服务器真实敏感路径

#### Scenario: 查询 Profile Agent 兼容性矩阵
- **WHEN** 超级管理员查询模型 profile 详情或 agent probe 结果列表
- **THEN** 后端 SHALL 返回该 profile 对各 agent runtime 的最近通用兼容性状态
- **AND** 每个结果 SHALL 包含 agent runtime ID、agent 类型、Agent 响应状态、workspace 读取状态、workspace 写入状态、聚合兼容状态、最近测试时间和脱敏消息
- **AND** 每个结果 MUST NOT 包含测试比较、KB AI 扩展或其他业务阶段的兼容性字段

#### Scenario: 后续新增 Agent Runtime 或业务阶段
- **WHEN** 后端新增新的 agent runtime 类型或新的 Agent 业务阶段
- **THEN** 模型 profile agent probe SHALL 能为新 runtime 记录独立通用结果
- **AND** 新业务阶段 MUST NOT 要求改变模型 Agent 兼容性结果结构
- **AND** 后端 SHALL NOT 要求改变 `model_profiles` 的基础配置结构

## ADDED Requirements

### Requirement: 阶段输出契约不得改写通用 Agent 兼容性
模型管理 SHALL 将阶段任务输出验证与模型 Profile 和 Agent Runtime 的通用兼容性状态分离。

#### Scenario: 阶段任务输出合法
- **WHEN** 已绑定的模型与 Agent Runtime 成功生成某业务阶段要求的输出
- **THEN** 该阶段任务 SHALL 按自身契约完成
- **AND** 后端 MUST NOT 因该业务成功额外创建或修改通用兼容性结果

#### Scenario: 阶段任务输出不合法
- **WHEN** 已绑定的模型与 Agent Runtime 生成不符合业务阶段 schema 的输出
- **THEN** 该阶段任务 SHALL 按自身错误语义失败
- **AND** 后端 MUST NOT 将该失败写成模型与 Agent Runtime 的通用不兼容结果
