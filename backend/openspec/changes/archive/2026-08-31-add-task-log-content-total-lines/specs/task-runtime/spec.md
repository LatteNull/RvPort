## ADDED Requirements

### Requirement: 任务日志内容响应必须包含总行数
任务运行时 SHALL 在完成态日志内容读取 API 中为每个返回的日志类型提供当前总行数，并 SHALL 在日志写入或落库时维护该总行数。

#### Scenario: 默认读取时返回三类日志总行数
- **WHEN** 已登录用户调用 `GET /api/tasks/{taskId}/log-content` 且不传查询参数
- **THEN** 后端 SHALL 返回 `merged`、`stdout` 和 `stderr` 三类日志内容
- **AND** 每类日志对象 SHALL 包含 `totalLines`
- **AND** `totalLines` SHALL 表示该日志类型在响应时刻的总逻辑行数

#### Scenario: 单类读取时返回该类总行数
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/log-content?types=stdout`
- **THEN** 后端 SHALL 只返回 `stdout` 日志内容
- **AND** `stdout.totalLines` SHALL 表示 stdout 日志总逻辑行数
- **AND** 响应 MUST NOT 包含未请求日志类型的 `totalLines`

#### Scenario: 多类不同 offset 时总行数互不影响
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/log-content?types=merged,stdout,stderr&mergedOffset=0&stdoutOffset=100&stderrOffset=200&lines=100`
- **THEN** 后端 SHALL 按每个日志类型独立返回 `totalLines`
- **AND** `totalLines` MUST NOT 受对应请求 offset 或 lines 影响
- **AND** `hasMore` SHALL 仍基于该日志类型的 offset、lines 和 totalLines 判断是否还有更旧日志

#### Scenario: 运行中日志总行数动态增长
- **WHEN** worker 或任务执行上下文向某个任务日志追加内容并落库
- **THEN** 后端 SHALL 更新该日志类型的总逻辑行数
- **AND** 后续 `log-content` 响应 SHALL 反映更新后的 `totalLines`

#### Scenario: 缺失日志返回零总行数
- **WHEN** 某类日志记录不存在或日志文件不存在
- **THEN** 该类日志响应 SHALL 返回 `totalLines=0`
- **AND** 该类日志响应 SHALL 返回空内容、`returnedLines=0` 和 `hasMore=false`

#### Scenario: 不暴露日志文件实现细节
- **WHEN** 后端返回 `totalLines`
- **THEN** 响应 MUST NOT 暴露服务器真实日志文件路径、文件大小推断路径或未脱敏内容
