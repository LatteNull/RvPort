## ADDED Requirements

### Requirement: 任务日志内容 API 必须返回每类日志总行数
后端 API SHALL 在 `GET /api/tasks/{taskId}/log-content` 的每个日志类型响应对象中返回 `totalLines`，用于前端展示行号和计算日志分页状态。

#### Scenario: 响应包含 totalLines 字段
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/log-content`
- **THEN** API SHALL 返回完成态日志内容响应
- **AND** 每个返回的 `logs.<type>` 对象 SHALL 包含 `totalLines`
- **AND** `totalLines` SHALL 为非负整数

#### Scenario: totalLines 与请求分页参数解耦
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/log-content?types=merged&mergedOffset=100&lines=50`
- **THEN** `logs.merged.totalLines` SHALL 表示 merged 日志总逻辑行数
- **AND** `logs.merged.totalLines` MUST NOT 被截断为当前页 `returnedLines`
- **AND** `logs.merged.totalLines` MUST NOT 随 offset 增大而减少，除非日志内容被后台清理或重建

#### Scenario: 多日志类型响应分别返回总行数
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/log-content?types=merged,stdout&mergedOffset=0&stdoutOffset=100`
- **THEN** API SHALL 分别返回 `logs.merged.totalLines` 和 `logs.stdout.totalLines`
- **AND** 两个字段 SHALL 分别对应各自日志类型，不得复用 merged 行数作为 stdout 行数

#### Scenario: 日志仍在运行中时返回快照行数
- **WHEN** 任务仍在运行且日志仍在追加
- **THEN** API SHALL 返回响应时刻可见的 `totalLines`
- **AND** API MUST NOT 为了等待最终行数而阻塞请求
