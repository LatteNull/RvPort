## ADDED Requirements

### Requirement: KB AI 扩展必须消费 schema v2 finding

KB AI 扩展任务 MUST 使用 schema v2 finding 作为 agent 输入，不再依赖 schema v1 的 trace 或扁平字段。

#### Scenario: 导出 AI 扩展输入

- **WHEN** 用户对 KB 扫描结果启动 AI 扩展扫描
- **THEN** 后端 MUST 生成包含 schema v2 finding 的输入文件
- **AND** 每条输入 MUST 包含 `fact`、`conclusion`、`occurrences`、`evidenceChain` 和可用源码上下文
- **AND** 输入 MUST 包含 finding 的当前人工确认状态和报告纳入状态

#### Scenario: finding 信息不足

- **WHEN** v2 finding 自带 evidence 不足以判断迁移建议
- **THEN** agent prompt MUST 允许 agent 在项目源码目录中读取相关源码
- **AND** 后端 MUST 继续保留可用的 finding evidence 和源码上下文

#### Scenario: 部分 AI 扩展结果写入

- **WHEN** agent 只为部分 finding 生成有效建议
- **THEN** 后端 MUST 写入有效建议
- **AND** 未生成建议的 finding MUST 保持原状态
- **AND** 列表和详情 API MUST 对已写入的 finding 返回 AI 扩展建议
