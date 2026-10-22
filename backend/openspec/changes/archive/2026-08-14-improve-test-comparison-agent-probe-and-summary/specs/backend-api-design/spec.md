## ADDED Requirements

### Requirement: 模型测试 API 必须返回指定 agent 兼容性分项结果
后端 API SHALL 在模型 profile 测试响应中返回 agent 类型、分项 probe 结果和聚合兼容性状态，使前端能够判断模型是否适用于当前阶段使用的 agent。

#### Scenario: 返回模型测试分项结果
- **WHEN** 超级管理员调用模型 profile 测试 API
- **THEN** 响应 SHALL 包含每个 probe 的名称、状态、错误码、脱敏消息和测试时间
- **AND** 响应 SHALL 包含当前测试的 agent 类型
- **AND** 响应 SHALL 包含基础可用状态、agent 兼容状态和测试比较兼容状态
- **AND** 响应 MUST NOT 返回 API key、授权头、完整 agent 命令或服务器真实路径

#### Scenario: 列表展示最近兼容性状态
- **WHEN** 超级管理员查询模型 profile 列表
- **THEN** 列表项 SHALL 返回最近一次 agent 类型、基础可用状态、agent 兼容状态、测试比较兼容状态和测试时间
- **AND** 列表项 MUST NOT 返回 provider secret

### Requirement: 自动化测试 API 必须暴露合并日志摘要
自动化测试 API SHALL 在测试详情或日志查询能力中区分 merged log、stdout log 和 stderr log，并 SHALL 将 merged log 作为推荐展示日志。

#### Scenario: 查询测试详情包含 merged log 引用
- **WHEN** 用户查询自动化测试详情
- **THEN** 响应 SHALL 返回 merged log 引用或可查询状态
- **AND** 响应 MAY 返回 stdout/stderr 调试日志引用
- **AND** 响应 MUST NOT 返回服务器真实日志路径

### Requirement: 测试比较 API 必须返回结构化环境统计
测试比较 API SHALL 返回 source 与 target 两侧结构化测试统计，供前端展示测试数量、通过数、失败数、失败项和失败原因。

#### Scenario: 查询比较详情返回环境统计
- **WHEN** 已登录用户调用 `GET /api/test-comparisons/{comparisonId}`
- **THEN** 响应 SHALL 包含 source 与 target 环境的测试统计摘要
- **AND** 每侧摘要 SHALL 包含状态、退出码、测试总数、执行数、通过数、失败数、跳过数、失败项、失败原因、统计依据和置信度
- **AND** 响应 MUST NOT 返回完整日志、完整 agent 输入、API key、对象存储内部 key 或服务器真实路径
