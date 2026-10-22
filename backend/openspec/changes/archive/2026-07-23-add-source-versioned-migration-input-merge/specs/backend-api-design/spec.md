## ADDED Requirements

### Requirement: API 必须提供迁移输入列表和详情
后端 API SHALL 提供源码版本作用域下的迁移输入 reference 列表、详情和状态更新接口。

#### Scenario: 查询源码版本迁移输入列表
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/source-revisions/{sourceRevisionId}/migration-inputs`
- **THEN** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 后端 SHALL 校验源码版本属于该项目
- **AND** 响应 SHALL 返回分页迁移输入 reference 列表
- **AND** 列表项 SHALL 包含 `id`、`issueTitle`、`sourceType`、`sourceRefId`、`detectedLevel`、`locationLabel`、`recommendationSummary`、`status`、`createdAt` 和 `updatedAt`

#### Scenario: 迁移输入列表过滤排序
- **WHEN** 用户查询迁移输入列表
- **THEN** API SHALL 支持按 `sourceType`、`detectedLevel`、`status` 和关键字过滤
- **AND** API SHALL 支持按 `createdAt`、`updatedAt`、`sourceType`、`detectedLevel`、`status` 和 `issueTitle` 排序
- **AND** 后端 MUST 拒绝不在白名单内的过滤或排序字段

#### Scenario: 查询迁移输入详情
- **WHEN** 已登录用户调用 `GET /api/migration-inputs/{migrationInputId}`
- **THEN** 后端 SHALL 根据 reference 所属项目校验访问权限
- **AND** 响应 SHALL 返回 reference 摘要和按来源类型展开的真实详情
- **AND** 响应 MUST NOT 暴露服务器真实路径、完整任务输入快照或明文凭据

#### Scenario: 更新迁移输入确认状态
- **WHEN** 用户调用 `PATCH /api/migration-inputs/{migrationInputId}` 更新确认状态或备注
- **THEN** 后端 SHALL 校验项目访问权限
- **AND** `status` SHALL 只允许 `CANDIDATE`、`CONFIRMED` 或 `EXCLUDED`
- **AND** 后端 SHALL 更新 reference 状态和更新时间

### Requirement: API 必须支持迁移输入批量导入和自动合并
后端 API SHALL 提供批量导入真实结果记录和自动合并当前前序结果的接口。

#### Scenario: 批量导入迁移输入
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/source-revisions/{sourceRevisionId}/migration-inputs:import`
- **THEN** 请求 SHALL 包含 `sourceType` 和非空 `sourceRefIds`
- **AND** 后端 SHALL 校验项目权限和源码版本归属
- **AND** 后端 SHALL 将合法来源记录导入该源码版本迁移输入集合
- **AND** 响应 SHALL 返回 `createdCount`、`skippedDuplicateCount` 和已创建 reference 摘要

#### Scenario: 自动合并迁移输入
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/source-revisions/{sourceRevisionId}/migration-inputs:auto-merge`
- **THEN** 请求 SHALL 包含一个或多个启用的来源类型
- **AND** 后端 SHALL 基于当前源码版本或当前项目查找对应来源的当前有效结果
- **AND** 后端 SHALL 复用批量导入规则生成 reference
- **AND** 响应 SHALL 返回按来源分组的创建、重复跳过和无结果计数

### Requirement: API 报告生成必须只消费确认后的迁移输入
后端报告生成 API SHALL 只使用当前源码版本下已确认的迁移输入 reference 作为报告内容来源。

#### Scenario: 生成报告时读取确认项
- **WHEN** 用户为某个源码版本生成迁移报告
- **THEN** 后端 SHALL 查询该 `sourceRevisionId` 下 `status=CONFIRMED` 的迁移输入 reference
- **AND** 后端 SHALL 按 `sourceType` 和 `sourceRefId` 回查真实来源详情构造报告内容
- **AND** 后端 MUST NOT 直接把未确认的 KB findings 或 SBOM result items 写入报告

#### Scenario: 无确认项生成报告
- **WHEN** 当前源码版本没有已确认迁移输入
- **THEN** 后端 SHALL 返回明确业务错误或生成空内容摘要
- **AND** 行为 SHALL 在 API 文档中明确
