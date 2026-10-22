## ADDED Requirements

### Requirement: Agent Runtime 选择必须允许 KB_AI_EXTENSION 阶段
后端 SHALL 将 `KB_AI_EXTENSION` 纳入受控 agent runtime 阶段白名单，使 KB AI 扩展扫描能通过统一 adapter 执行。

#### Scenario: 执行 KB AI 扩展 agent
- **WHEN** `KB_AI_EXTENSION` 阶段绑定选择某个已启用 agent runtime
- **THEN** 后端 SHALL 使用对应 agent adapter 构造受控命令并传入模型 profile
- **AND** adapter SHALL 在 KB AI 扩展专用 workspace 中执行任务
- **AND** 业务代码 MUST NOT 直接拼接某个 agent 的专用命令

#### Scenario: KB AI 扩展 agent 输出保存
- **WHEN** KB AI 扩展任务需要保存 agent 原始输出 artifact
- **THEN** 后端 SHALL 保存包含 `stdout`、`stderr`、`mergedOutput`、`exitCode` 和 `timedOut` 的结构化输出
- **AND** 保存前 SHALL 对 API key、授权头、完整 prompt 和服务器真实敏感路径做脱敏处理

#### Scenario: 未声明阶段被拒绝
- **WHEN** 请求为非白名单阶段绑定或执行 agent runtime
- **THEN** 后端 SHALL 返回统一参数错误或业务错误
- **AND** 后端 MUST NOT 尝试执行任意外部命令
