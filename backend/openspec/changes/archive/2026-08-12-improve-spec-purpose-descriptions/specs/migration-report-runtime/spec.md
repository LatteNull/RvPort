## ADDED Requirements

### Requirement: 迁移报告说明必须满足严格校验
`migration-report-runtime` 主 spec 的 Purpose SHALL 清晰描述报告输入快照、确认后的迁移输入、统计摘要、对象存储制品和受控下载边界。

#### Scenario: 严格校验迁移报告说明
- **WHEN** 执行 `openspec validate migration-report-runtime --type spec --strict`
- **THEN** 该 spec SHALL 不再因为 `Purpose section is too brief` 失败
