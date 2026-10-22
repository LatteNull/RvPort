## ADDED Requirements

### Requirement: 测试辅助 API 说明必须满足严格校验
`test-support-api` 主 spec 的 Purpose SHALL 清晰描述测试辅助 API 的构建期隔离、安全边界、白名单能力、E2E 使用方式和生产禁用要求。

#### Scenario: 严格校验测试辅助 API 说明
- **WHEN** 执行 `openspec validate test-support-api --type spec --strict`
- **THEN** 该 spec SHALL 不再因为 `Purpose section is too brief` 失败
