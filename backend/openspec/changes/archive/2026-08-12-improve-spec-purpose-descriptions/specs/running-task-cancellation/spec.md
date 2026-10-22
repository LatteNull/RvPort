## ADDED Requirements

### Requirement: 运行中任务取消说明必须满足严格校验
`running-task-cancellation` 主 spec 的 Purpose SHALL 清晰描述取消请求、任务状态、worker 定点取消、运行时句柄和底层资源清理边界。

#### Scenario: 严格校验运行中任务取消说明
- **WHEN** 执行 `openspec validate running-task-cancellation --type spec --strict`
- **THEN** 该 spec SHALL 不再因为 `Purpose section is too brief` 失败
