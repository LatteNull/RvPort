## MODIFIED Requirements

### Requirement: 任务运行时必须支持完成态日志内容读取
任务运行时 SHALL 提供任务日志内容读取 API，使前端可以在构建或测试完成后按 `merged`、`stdout`、`stderr` 三类读取日志正文；日志分页 offset SHALL 面向前端展示顺序，而不是物理文件存储方向。

#### Scenario: 默认读取三类日志最新展示页
- **WHEN** 已登录用户调用 `GET /api/tasks/{taskId}/log-content` 且不传查询参数
- **THEN** 后端 SHALL 根据任务所属项目执行访问守卫
- **AND** 后端 SHALL 返回 `merged`、`stdout` 和 `stderr` 三类日志内容
- **AND** 每类日志 SHALL 默认返回最新展示页最多 100 行
- **AND** 响应 MUST NOT 暴露服务器真实日志文件路径

#### Scenario: 只读取单类日志
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/log-content?types=stdout`
- **THEN** 后端 SHALL 只返回 `stdout` 日志内容
- **AND** 响应 SHALL 不包含未请求的 `merged` 或 `stderr` 内容

#### Scenario: 同时读取多类不同 offset
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/log-content?types=merged,stdout,stderr&mergedOffset=0&stdoutOffset=100&stderrOffset=200&lines=100`
- **THEN** 后端 SHALL 按每个日志类型各自的 offset 从最新展示页向更旧日志分页读取
- **AND** 每类日志 SHALL 独立返回 `offset`、`lines`、`returnedLines`、`hasMore` 和 `content`
- **AND** 某类日志缺失时该类 SHALL 返回空内容和 `hasMore=false`，而不是导致整个请求失败

#### Scenario: 倒序日志文件首屏读取最新日志
- **WHEN** 日志文件中较新的日志位于文件头部且较早的日志位于文件尾部
- **AND** 前端调用 `GET /api/tasks/{taskId}/log-content?types=merged&mergedOffset=0&lines=100`
- **THEN** 后端 SHALL 返回文件头部开始的最新展示页
- **AND** 后端 MUST NOT 从物理文件尾部返回最早日志作为首屏内容
- **AND** 单页内容 SHALL 保持文件内自然顺序

#### Scenario: 倒序日志文件读取更旧页面
- **WHEN** 日志文件中较新的日志位于文件头部且较早的日志位于文件尾部
- **AND** 前端调用 `GET /api/tasks/{taskId}/log-content?types=merged&mergedOffset=100&lines=100`
- **THEN** 后端 SHALL 跳过最新展示页的 100 行并返回更旧的下一页
- **AND** `hasMore` SHALL 表示展示顺序中是否仍存在更旧日志

#### Scenario: 单类行数覆盖全局行数
- **WHEN** 请求同时包含 `lines=100` 和 `stdoutLines=50`
- **THEN** `stdout` SHALL 使用 50 行作为读取数量
- **AND** 未指定单类行数的日志类型 SHALL 使用全局 `lines`

#### Scenario: 到达日志最旧端
- **WHEN** 某类日志请求的 offset 已经超过或到达展示顺序的总行数
- **THEN** 后端 SHALL 返回空内容或剩余可用内容
- **AND** 该类日志 SHALL 返回 `hasMore=false`

#### Scenario: 拒绝非法日志内容参数
- **WHEN** 请求包含未知 `types`、负数 offset、负数 lines 或超过上限的 lines
- **THEN** 后端 SHALL 返回统一参数校验错误
- **AND** 后端 MUST NOT 读取日志文件

#### Scenario: 无权限读取日志内容
- **WHEN** 无权限用户调用 `GET /api/tasks/{taskId}/log-content`
- **THEN** 后端 SHALL 返回与任务不存在一致的安全错误
- **AND** 响应 MUST NOT 暴露任务是否存在、日志类型、日志大小或日志内容

#### Scenario: 日志内容读取不替代 SSE
- **WHEN** 任务仍在运行中
- **THEN** 前端 SHALL 继续使用任务级日志 SSE 获取动态日志
- **AND** 完成态日志内容接口 SHALL 只作为日志文件内容读取能力，不承担实时推送职责
