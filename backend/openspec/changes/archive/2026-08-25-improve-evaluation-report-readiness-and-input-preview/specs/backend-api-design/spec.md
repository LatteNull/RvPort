## ADDED Requirements

### Requirement: API 必须提供评估报告页 readiness
后端 API SHALL 提供评估报告页 readiness 接口，用于返回当前源码版本下报告生成条件、输入统计、警告、最新报告和历史比较准备信息。

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

#### Scenario: readiness 返回阻塞原因
- **WHEN** 当前源码版本不存在或没有 confirmed 输入
- **THEN** 响应 SHALL 返回 `canGenerate=false`
- **AND** `blockers` SHALL 使用稳定错误码表达阻塞原因
- **AND** 接口 MUST NOT 创建异步报告任务

### Requirement: API 必须提供评估报告输入预览
后端 API SHALL 提供当前源码版本的报告输入预览列表，供前端在评估报告页展示将进入报告或可人工处理的输入。

#### Scenario: 查询评估报告输入预览
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/reports/evaluation/input-preview`
- **THEN** 后端 MUST 校验当前用户对项目有访问权限
- **AND** 请求 MAY 包含 `sourceRevisionId`
- **AND** 未提交 `sourceRevisionId` 时后端 SHALL 使用项目当前 active source revision
- **AND** 响应 SHALL 返回分页数据
- **AND** 每条记录 SHALL 包含 `id`、`sourceType`、`sourceRefId`、`issueTitle`、`detectedLevel`、`locationLabel`、`status`、`recommendationSummary`、`note`、`updatedAt` 和受控来源定位摘要

#### Scenario: 输入预览支持过滤排序
- **WHEN** 用户调用输入预览接口并提交 `sourceType`、`status`、`riskLevel`、`keyword`、`page`、`pageSize`、`sortBy` 或 `sortDirection`
- **THEN** 后端 SHALL 使用分页响应格式
- **AND** 过滤条件 SHALL 使用 AND 语义组合
- **AND** `sortBy` 白名单 SHALL 至少包含 `updatedAt`、`sourceType`、`status`、`detectedLevel`、`issueTitle` 和 `locationLabel`

#### Scenario: 输入预览拒绝非法查询参数
- **WHEN** 用户提交非法 `status`、非法 `sourceType`、非法 `riskLevel` 或非法排序字段
- **THEN** API SHALL 返回统一参数校验错误
- **AND** 后端 MUST NOT 将非法参数拼接到 SQL

### Requirement: API 报告详情必须返回当前输入摘要
后端 API SHALL 在评估报告详情响应中返回当前源码版本输入状态摘要，并 SHALL 保持历史报告快照不可变。

#### Scenario: 报告详情包含当前输入状态
- **WHEN** 已登录用户调用 `GET /api/reports/{reportId}`
- **THEN** 后端 SHALL 返回历史报告 summary、artifact 摘要和源码版本摘要
- **AND** 响应 SHALL 返回 `currentInputSummary`
- **AND** `currentInputSummary` SHALL 包含总数、按状态统计、按来源统计、按风险统计和 LOW candidate 数量

#### Scenario: 报告详情权限校验
- **WHEN** 普通用户通过 reportId 查询其他用户项目的报告详情
- **THEN** 后端 SHALL 返回访问拒绝或项目不存在错误
- **AND** 后端 MUST NOT 泄露报告是否存在于其他项目
