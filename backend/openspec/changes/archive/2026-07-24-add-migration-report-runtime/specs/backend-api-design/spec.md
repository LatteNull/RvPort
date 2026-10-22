## ADDED Requirements

### Requirement: API 必须支持迁移评估报告生成和查询
后端 API SHALL 支持创建、查询和下载迁移评估报告，并 SHALL 对所有报告接口执行项目访问权限校验。

#### Scenario: 创建迁移评估报告
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/reports/evaluation`
- **THEN** 后端 SHALL 校验用户有该项目访问权限
- **AND** 请求体 MAY 包含 `sourceRevisionId`
- **AND** 未提交 `sourceRevisionId` 时后端 SHALL 使用项目当前 active source revision
- **AND** 后端 SHALL 校验源码版本属于该项目
- **AND** 响应 SHALL 返回报告生成任务的 `taskId`、任务类型和当前状态

#### Scenario: 创建报告没有源码版本
- **WHEN** 项目没有 active source revision 且请求未提交 `sourceRevisionId`
- **THEN** 后端 SHALL 返回统一业务错误
- **AND** 后端 MUST NOT 创建报告任务

#### Scenario: 查询项目报告列表
- **WHEN** 用户调用 `GET /api/projects/{projectId}/reports/evaluation`
- **THEN** 后端 SHALL 返回该项目的分页报告列表
- **AND** 列表接口 SHALL 支持按 `sourceRevisionId`、`status`、`riskLevel` 和时间范围过滤
- **AND** 列表接口 SHALL 支持按 `generatedAt`、`createdAt`、`status` 和 `riskLevel` 排序
- **AND** 响应 MUST NOT 返回 `htmlPath`、`jsonPath` 或其他服务器真实路径

#### Scenario: 查询最新迁移评估报告
- **WHEN** 用户调用 `GET /api/projects/{projectId}/reports/evaluation/latest`
- **THEN** 后端 SHALL 返回该项目最近生成或创建的评估报告摘要
- **AND** 请求 MAY 支持 `sourceRevisionId` 过滤
- **AND** 没有报告时 SHALL 返回空数据或明确的 not found 业务响应

#### Scenario: 查询报告详情
- **WHEN** 用户调用 `GET /api/reports/{reportId}`
- **THEN** 后端 SHALL 通过 reportId 反查所属项目并校验访问权限
- **AND** 响应 SHALL 包含报告 ID、项目 ID、源码版本 ID、任务 ID、类型、状态、标题、摘要、总体风险、生成时间和创建时间
- **AND** 响应 MUST NOT 返回服务器真实文件路径、bucket 或 object key

#### Scenario: 查询报告输入快照
- **WHEN** 用户调用 `GET /api/reports/{reportId}/inputs`
- **THEN** 后端 SHALL 返回该报告使用的输入快照分页列表
- **AND** 列表接口 SHALL 支持按 `inputType` 和关键字过滤
- **AND** 列表接口 SHALL 支持按 `createdAt`、`inputType` 和快照内风险展示字段排序

#### Scenario: 下载报告
- **WHEN** 用户调用 `GET /api/reports/{reportId}/download?format=HTML` 或 `format=JSON`
- **THEN** 后端 SHALL 校验报告所属项目访问权限
- **AND** 后端 SHALL 从对象存储制品或兼容的历史受控存储中返回对应格式的报告内容
- **AND** 后端 MUST NOT 支持未明确允许的格式
- **AND** 响应 MUST NOT 暴露对象存储 bucket、object key 或服务器真实路径

#### Scenario: 普通用户不能访问其他项目报告
- **WHEN** 普通用户通过 reportId 访问其他用户项目的报告详情、输入快照或下载接口
- **THEN** 后端 SHALL 返回 `FORBIDDEN` 或等效访问拒绝错误
- **AND** 后端 MUST NOT 泄露报告是否存在于其他项目
