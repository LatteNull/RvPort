## ADDED Requirements

### Requirement: 知识库扫描说明必须满足严格校验
`kb-scan-runtime` 主 spec 的 Purpose SHALL 清晰描述知识库扫描运行时的独立 CLI 调用、源码输入、finding 输出、代码上下文和制品边界。

#### Scenario: 严格校验知识库扫描说明
- **WHEN** 执行 `openspec validate kb-scan-runtime --type spec --strict`
- **THEN** 该 spec SHALL 不再因为 `Purpose section is too brief` 失败
