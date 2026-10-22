## ADDED Requirements

### Requirement: API E2E 必须验证带诊断包装的 Agent Probe 输出
API E2E 测试套件 SHALL 使用不依赖外部模型服务的可控 Agent fixture，通过真实进程 stdout、stderr 与 workspace 文件验证模型 Profile Agent Probe 不会因 CLI 诊断包装而误判。

#### Scenario: DeepSeek Harness 风格输出
- **WHEN** fixture 在 stdout 返回预期单行 JSON，且 merged output 由运行器附加 `[STDOUT]` 标签
- **THEN** Agent Probe Run API 的对应 runtime 结果 SHALL 为成功
- **AND** 三个通用 probe SHALL 全部通过

#### Scenario: OpenCode 风格输出
- **WHEN** fixture 在 stderr 输出 ANSI 状态日志，在 stdout 返回预期 JSON，并按要求读写 workspace 文件
- **THEN** Agent Probe Run API SHALL 返回 Agent 响应、workspace 读取和 workspace 写入全部成功
- **AND** ANSI 日志与通道标签 MUST NOT 出现在结构化判定中

#### Scenario: 无效输出和脱敏
- **WHEN** fixture 返回零退出码但没有匹配 JSON，或返回包含测试密钥的失败诊断
- **THEN** API SHALL 返回对应 probe 失败及稳定错误码
- **AND** API 响应和持久化消息 MUST NOT 包含完整 API key
