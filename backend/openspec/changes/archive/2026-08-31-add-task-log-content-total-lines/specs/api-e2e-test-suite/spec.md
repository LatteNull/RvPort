## ADDED Requirements

### Requirement: E2E 必须覆盖日志内容总行数
API E2E 测试 SHALL 覆盖 `GET /api/tasks/{taskId}/log-content` 的 `totalLines` 返回行为，并 SHALL 覆盖正常流程、异常流程和 edge case。

#### Scenario: 正常流程返回准确总行数
- **WHEN** E2E 创建包含 merged、stdout 和 stderr 日志内容的任务 fixture
- **AND** E2E 调用 `GET /api/tasks/{taskId}/log-content`
- **THEN** 响应中每个日志类型 SHALL 包含对应的 `totalLines`
- **AND** `totalLines` SHALL 等于 fixture 中对应日志类型的总逻辑行数

#### Scenario: 单类请求不返回其他类型总行数
- **WHEN** E2E 调用 `GET /api/tasks/{taskId}/log-content?types=stdout`
- **THEN** 响应 SHALL 只包含 stdout 日志对象
- **AND** stdout 日志对象 SHALL 包含 `totalLines`
- **AND** 响应 MUST NOT 包含 merged 或 stderr 的日志对象

#### Scenario: offset 翻页不改变总行数
- **WHEN** E2E 对同一日志类型分别请求 `offset=0` 和更大的 offset
- **THEN** 两次响应的 `totalLines` SHALL 保持一致
- **AND** `returnedLines` MAY 随分页位置变化

#### Scenario: 缺失日志总行数为零
- **WHEN** E2E 创建缺少某类日志文件或日志记录的任务 fixture
- **AND** E2E 请求该日志类型
- **THEN** 响应 SHALL 返回 `totalLines=0`
- **AND** 响应 SHALL 返回空内容、`returnedLines=0` 和 `hasMore=false`

#### Scenario: 非法参数仍返回统一错误
- **WHEN** E2E 调用 `GET /api/tasks/{taskId}/log-content` 并传入非法 `types`、负数 offset 或超过上限的 lines
- **THEN** API SHALL 返回统一参数校验错误
- **AND** 响应 MUST NOT 返回 `totalLines`
