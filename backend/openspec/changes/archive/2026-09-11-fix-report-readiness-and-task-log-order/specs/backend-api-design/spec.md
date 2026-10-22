## MODIFIED Requirements

### Requirement: 任务日志 API 不暴露服务器路径
任务日志 API SHALL 通过任务日志资源提供元数据分页、完成态正文尾部分页读取和受控下载能力，并 SHALL 隐藏服务器真实文件路径。

#### Scenario: 查询日志元数据
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/logs`
- **THEN** API SHALL 返回日志 ID、日志类型、大小、摘要和创建时间
- **AND** 响应 MUST NOT 返回 `file_path` 或服务器真实路径

#### Scenario: 读取日志内容
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/log-content`
- **THEN** API SHALL 返回完成态日志内容响应
- **AND** 响应 SHALL 支持 `merged`、`stdout`、`stderr` 三类日志
- **AND** 不传参数时每类默认返回物理日志文件末尾的最新展示页最多 100 行
- **AND** 每个返回页的 `content` SHALL 按日志产生时间正序排列
- **AND** 响应 MUST NOT 返回服务器真实日志文件路径

#### Scenario: 读取单类或多类不同 offset
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/log-content?types=merged,stdout&mergedOffset=0&stdoutOffset=100&mergedLines=100&stdoutLines=50`
- **THEN** API SHALL 只返回请求的日志类型
- **AND** 每个日志类型 SHALL 使用自己的 offset 和 lines
- **AND** offset SHALL 表示从对应日志文件尾部开始跳过的最新日志行数
- **AND** `offset=0` SHALL 返回该日志类型的最新展示页
- **AND** offset 增大时 SHALL 返回更早的日志页
- **AND** 未设置单类 lines 时 SHALL 使用全局 `lines` 或默认值

#### Scenario: 正序物理日志读取
- **WHEN** 日志文件物理内容为较早日志在文件头、较新日志追加在文件尾
- **THEN** `GET /api/tasks/{taskId}/log-content?types=merged&mergedOffset=0` SHALL 返回文件尾部对应的最新展示页
- **AND** 单页内容 SHALL 保持文件内自然顺序
- **AND** 前端拼接更早页面时 MUST NOT 反转单页日志行

#### Scenario: 下载日志文件
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/logs/{logId}/download`
- **THEN** API SHALL 校验日志属于该任务
- **AND** API SHALL 通过受控下载返回日志内容
- **AND** API MUST NOT 接受客户端传入服务器文件路径作为下载参数

### Requirement: API 必须提供评估报告页 readiness
后端 API SHALL 提供评估报告页 readiness 接口，用于返回当前源码版本下报告生成条件、输入统计、警告、最新报告和历史比较准备信息；没有 confirmed 输入 SHALL 表示当前报告输入为空，而不是报告生成阻塞条件。

#### Scenario: 查询评估报告 readiness
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/reports/evaluation/readiness`
- **THEN** 后端 MUST 校验当前用户对项目有访问权限
- **AND** 请求 MAY 包含 `sourceRevisionId`
- **AND** 未提交 `sourceRevisionId` 时后端 SHALL 使用项目当前 active source revision
- **AND** 响应 SHALL 包含 `canGenerate`、`blockers`、`warnings`、`sourceRevision`、`inputSummary`、`latestReport`、`latestComparableReport` 和 `latestComparison`
- **AND** 响应 MUST NOT 暴露服务器真实路径、对象存储内部 key、明文凭据或完整任务输入快照

#### Scenario: readiness 校验源码版本归属
- **WHEN** 用户提交的 `sourceRevisionId` 不属于 URL 中的项目
- **THEN** 后端 SHALL 返回统一业务错误
- **AND** 后端 MUST NOT 返回该源码版本或所属项目的详情

#### Scenario: 缺少源码版本时返回阻塞原因
- **WHEN** 当前源码版本不存在且请求未指定有效源码版本
- **THEN** 响应 SHALL 返回 `canGenerate=false`
- **AND** `blockers` SHALL 使用稳定错误码表达源码版本缺失
- **AND** 接口 MUST NOT 创建异步报告任务

#### Scenario: 没有 confirmed 输入时允许生成报告
- **WHEN** 当前源码版本存在但 confirmed 输入数量为 0
- **THEN** 响应 SHALL 返回 `canGenerate=true`
- **AND** `inputSummary` SHALL 返回 confirmed 输入数量为 0
- **AND** `blockers` MUST NOT 包含 confirmed 输入缺失错误
- **AND** 后续报告创建接口 SHALL 允许创建生成全零报告的异步任务
