## ADDED Requirements

### Requirement: 专项分析必须登记可插拔归档候选
浮点和内存序运行成功发布可查询结果后 SHALL 为当前源码版本登记归档候选，包括安全摘要、JSON 和 HTML；内存序 MAY 额外登记审计 bundle。

#### Scenario: 登记浮点制品
- **WHEN** 浮点运行完成并保存制品
- **THEN** 系统 SHALL 登记 node type、candidate type、run reference、JSON 与 HTML artifact

#### Scenario: 登记内存序制品
- **WHEN** 内存序运行完成并保存统一输出
- **THEN** 系统 SHALL 登记 JSON、HTML 和受控审计 bundle
- **AND** 摘要 SHALL 包含 verdict、Finding、candidate、Scope 和 diagnostic 数量

#### Scenario: 新源码版本隔离
- **WHEN** 项目激活新的源码版本
- **THEN** 归档当前状态 MUST NOT 收集旧源码版本的专项分析候选
- **AND** 历史归档详情仍 SHALL 保持可读

### Requirement: 专项归档摘要必须安全且轻量
归档候选摘要 SHALL 只包含展示所需计数、状态、版本和业务引用，不得嵌入完整 Finding、证据图、源码上下文或服务器路径。

#### Scenario: 内存序输出很大
- **WHEN** 审计 bundle 包含大量 evidence steps 和 source snapshots
- **THEN** candidate summary SHALL 仅保存聚合计数与 artifact reference
- **AND** 完整内容 SHALL 通过受控制品读取
