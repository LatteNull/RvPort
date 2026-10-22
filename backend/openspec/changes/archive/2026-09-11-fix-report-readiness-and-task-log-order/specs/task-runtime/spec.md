## MODIFIED Requirements

### Requirement: 任务运行时必须支持完成态日志内容读取
任务运行时 SHALL 提供任务日志内容读取 API，使前端可以在构建或测试完成后按 `merged`、`stdout`、`stderr` 三类读取日志正文；物理日志 SHALL 按产生时间追加，日志分页 offset SHALL 从最新日志向更早日志计算，单页内容 SHALL 按产生时间正序返回。

#### Scenario: 默认读取三类日志最新展示页
- **WHEN** 已登录用户调用 `GET /api/tasks/{taskId}/log-content` 且不传查询参数
- **THEN** 后端 SHALL 根据任务所属项目执行访问守卫
- **AND** 后端 SHALL 返回 `merged`、`stdout` 和 `stderr` 三类日志内容
- **AND** 每类日志 SHALL 默认返回物理文件最后最多 100 行
- **AND** 每类单页内容 SHALL 从较早行到较新行正序排列
- **AND** 响应 MUST NOT 暴露服务器真实日志文件路径

#### Scenario: 只读取单类日志
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/log-content?types=stdout`
- **THEN** 后端 SHALL 只返回 `stdout` 日志内容
- **AND** 响应 SHALL 不包含未请求的 `merged` 或 `stderr` 内容

#### Scenario: 同时读取多类不同 offset
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/log-content?types=merged,stdout,stderr&mergedOffset=0&stdoutOffset=100&stderrOffset=200&lines=100`
- **THEN** 后端 SHALL 按每个日志类型各自的 offset 从最新页向更早日志分页读取
- **AND** 每类日志 SHALL 独立返回 `offset`、`lines`、`returnedLines`、`hasMore` 和 `content`
- **AND** 每类日志的单页内容 SHALL 保持从较早行到较新行的时间正序
- **AND** 某类日志缺失时该类 SHALL 返回空内容和 `hasMore=false`，而不是导致整个请求失败

#### Scenario: 正序追加日志首屏读取最新页
- **WHEN** 日志文件中较早日志位于文件头且较新日志追加在文件尾
- **AND** 前端调用 `GET /api/tasks/{taskId}/log-content?types=merged&mergedOffset=0&lines=100`
- **THEN** 后端 SHALL 返回文件尾部最后最多 100 行
- **AND** 返回内容 SHALL 按文件内自然顺序从较早行排列到最新行
- **AND** 后端 MUST NOT 返回文件头部最早 100 行作为首屏内容

#### Scenario: 从最新页读取更早页面
- **WHEN** 日志文件中较早日志位于文件头且较新日志追加在文件尾
- **AND** 前端调用 `GET /api/tasks/{taskId}/log-content?types=merged&mergedOffset=100&lines=100`
- **THEN** 后端 SHALL 跳过文件末尾最新 100 行并返回其前方最多 100 行
- **AND** 返回页内部 SHALL 保持时间正序
- **AND** `hasMore` SHALL 表示当前页之前是否仍存在更早日志

#### Scenario: 前端拼接多个完成态日志页
- **WHEN** 前端先取得最新页并继续请求更早页面
- **THEN** 前端 SHALL 将更早页面整体插入已有日志之前
- **AND** 前端 MUST NOT 反转任何单页中的日志行
- **AND** 拼接后的完整内容 SHALL 从最早日志排列到最新日志

#### Scenario: 单类行数覆盖全局行数
- **WHEN** 请求同时包含 `lines=100` 和 `stdoutLines=50`
- **THEN** `stdout` SHALL 使用 50 行作为读取数量
- **AND** 未指定单类行数的日志类型 SHALL 使用全局 `lines`

#### Scenario: 到达日志最旧端
- **WHEN** 某类日志请求的 offset 已经超过或到达该日志的总行数
- **THEN** 后端 SHALL 返回空内容或剩余可用内容
- **AND** 该类日志 SHALL 返回 `hasMore=false`

#### Scenario: 不同换行和无末尾换行
- **WHEN** 日志使用 `LF` 或 `CRLF`，或者最后一行没有换行符
- **THEN** 后端 SHALL 按逻辑行正确计算分页窗口
- **AND** 返回内容 MUST NOT 丢失、重复或拆分日志行

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
- **THEN** 前端 SHALL 继续使用任务级日志 SSE 获取变化通知并使用增量日志接口读取新增内容
- **AND** `/log-increments` 返回的新增日志 SHALL 保持现有时间正序
- **AND** 完成态日志内容接口 SHALL 只作为日志文件内容读取能力，不承担实时推送职责

### Requirement: 任务运行时必须支持迁移报告生成任务
任务运行时 SHALL 支持 `REPORT_GENERATE` 任务类型，用于异步生成迁移评估报告，并 SHALL 允许没有 confirmed 输入的当前源码版本生成全零报告。

#### Scenario: 创建报告生成任务
- **WHEN** 报告 API 创建迁移评估报告
- **THEN** 后端 SHALL 创建类型为 `REPORT_GENERATE` 的任务
- **AND** `tasks.input_snapshot` SHALL 包含 `projectId`、`sourceRevisionId` 和 `reportId`
- **AND** 输入快照 MUST NOT 包含服务器真实报告路径或未脱敏的敏感信息

#### Scenario: 没有 confirmed 输入时生成全零报告
- **WHEN** 当前源码版本没有 confirmed 迁移输入
- **THEN** 后端 SHALL 允许创建并执行 `REPORT_GENERATE` 任务
- **AND** 报告任务 SHALL 生成输入数量和风险统计均为 0 的 HTML 与 JSON 报告
- **AND** 报告任务及报告记录 SHALL 进入 `SUCCEEDED`

#### Scenario: 报告任务状态推送
- **WHEN** 报告生成任务进入 `QUEUED`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED` 或 `TIMEOUT`
- **THEN** 任务运行时 SHALL 追加对应任务事件
- **AND** 项目级 SSE SHALL 只向该报告所属项目推送事件

#### Scenario: 报告任务因运行时错误失败
- **WHEN** 报告生成 handler 因报告制品保存失败、输入快照写入失败或其他运行时错误而失败
- **THEN** 任务运行时 SHALL 将任务标记为 `FAILED`
- **AND** 任务错误摘要 SHALL 使用脱敏后的业务错误信息

#### Scenario: 取消报告生成任务
- **WHEN** 用户取消尚未完成的 `REPORT_GENERATE` 任务
- **THEN** 任务运行时 SHALL 按现有取消机制更新任务状态
- **AND** 报告记录 SHALL 最终进入 `CANCELLED` 或与任务终态一致的状态
