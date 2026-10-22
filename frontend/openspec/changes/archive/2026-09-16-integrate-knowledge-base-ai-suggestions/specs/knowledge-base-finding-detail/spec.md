## ADDED Requirements

### Requirement: Finding 展示最新 AI 补充建议

Finding 列表和详情 SHALL 使用后端随 Finding 返回的最新 `aiExtension`，并 SHALL 将 AI 内容明确标识为静态扫描结论的补充信息。

#### Scenario: Finding 已有 AI 建议

- **WHEN** Finding 响应包含 `aiExtension`
- **THEN** 结果列表 SHALL 使用轻量标识说明该 Finding 已有 AI 补充
- **AND** 详情 SHALL 分别展示扫描器建议、AI 摘要、AI 建议、置信度和生成时间
- **AND** 详情 SHALL 说明 AI 补充不替代静态证据

#### Scenario: Finding 没有 AI 建议

- **WHEN** Finding 响应不包含 `aiExtension`
- **THEN** 页面 SHALL 保持扫描器建议的正常展示
- **AND** 页面 SHALL NOT 使用客户端生成内容或占位内容冒充 AI 建议

#### Scenario: AI 任务完成时正在查看 Finding

- **WHEN** 当前扫描的 AI 扩展任务进入成功或部分成功终态且用户正在查看 Finding 详情
- **THEN** 页面 SHALL 刷新当前 Finding 和所属结果列表
- **AND** 新返回的 `aiExtension` SHALL 在不退出详情的情况下可见
