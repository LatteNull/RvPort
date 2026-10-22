## MODIFIED Requirements

### Requirement: API 通用约定必须统一
后端 API 设计 SHALL 定义统一的 base path、响应包络、错误格式、分页格式、时间格式、列表查询能力和浏览器 Session 安全约定。除非对应 spec 明确说明业务上不是列表查询，所有返回集合或列表数据的接口 SHALL 支持分页、排序和过滤。

#### Scenario: 返回成功响应
- **WHEN** API 请求成功
- **THEN** 响应 SHALL 使用统一响应包络，包含业务数据、请求追踪 ID 和时间戳

#### Scenario: 返回错误响应
- **WHEN** API 请求失败
- **THEN** 响应 SHALL 使用统一错误格式，包含错误码、错误消息、可选字段级详情、请求追踪 ID 和时间戳

#### Scenario: 返回分页列表
- **WHEN** API 返回列表数据
- **THEN** 响应 SHALL 支持 `page`、`pageSize`、`total`、`hasMore` 和 `items`
- **AND** 请求 SHALL 支持 `page` 和 `pageSize`
- **AND** 后端 SHALL 对 `page` 和 `pageSize` 执行边界校验和最大页大小限制

#### Scenario: 列表接口支持过滤
- **WHEN** API 返回列表数据
- **THEN** 请求 SHALL 支持该资源有业务意义的过滤字段
- **AND** 多个过滤条件 SHALL 使用 AND 语义，除非对应接口 spec 明确说明其他语义
- **AND** 过滤字段 SHALL 使用白名单定义
- **AND** 后端 MUST NOT 将客户端传入的任意字段名直接拼接到 SQL

#### Scenario: 列表接口支持排序
- **WHEN** API 返回列表数据
- **THEN** 请求 SHALL 支持 `sortBy` 和 `sortDirection` 或等效排序参数
- **AND** 后端 SHALL 为每个列表接口定义排序字段白名单
- **AND** 后端 SHALL 支持升序和降序
- **AND** 每个列表接口 SHALL 定义稳定默认排序
- **AND** 后端 MUST 拒绝不在白名单内的排序字段

#### Scenario: 列表能力例外
- **WHEN** 某个集合接口由于业务语义、协议语义或数据规模不适合分页、排序或过滤
- **THEN** 对应 capability spec MUST 明确说明例外原因
- **AND** 该接口 MUST 仍然保证响应规模可控

#### Scenario: 使用 Session Cookie 进行浏览器认证
- **WHEN** 前端调用需要登录态的 API
- **THEN** 前端 SHALL 依赖浏览器自动携带 HttpOnly Session Cookie
- **AND** 前端 MUST NOT 通过读取 JWT 恢复 MVP 登录态

#### Scenario: 状态变更请求提交 CSRF token
- **WHEN** 前端使用 Session Cookie 调用状态变更 API
- **THEN** 前端 SHALL 能先获取 CSRF token
- **AND** 状态变更请求 SHALL 通过约定 header 提交 CSRF token

## ADDED Requirements

### Requirement: SBOM API 必须提供分析结果明细查询
后端 API SHALL 提供 SBOM 分析结果明细查询能力，用于前端对 package、library、tool 和 native file 结果进行分页审计。

#### Scenario: 查询 SBOM 分析结果明细
- **WHEN** 已登录用户调用 `GET /api/sbom-analyses/{analysisId}/results`
- **THEN** 后端 SHALL 根据 SBOM 运行所属项目校验访问权限
- **AND** 响应 SHALL 返回该分析运行下的结果明细分页列表
- **AND** 列表项 SHALL 包含结果 ID、component type、source name、source version、source architecture、source package、target match status、target name、target version、target package、risk level、match strategy、recommendation 和 created at
- **AND** 列表响应 MUST NOT 返回完整 analyzer output 原文

#### Scenario: 分页过滤排序 SBOM 分析结果明细
- **WHEN** 已登录用户查询 SBOM 分析结果明细
- **THEN** 后端 SHALL 支持 `page` 和 `pageSize` 参数
- **AND** 后端 SHALL 支持按 `componentType`、`sourceName`、`sourceVersion`、`sourcePackageName`、`targetMatchStatus`、`targetName`、`targetVersion`、`targetPackageName`、`riskLevel`、`matchStrategy` 和 `recommendation` 过滤
- **AND** 后端 SHALL 支持按 `componentType`、`sourceName`、`sourceVersion`、`targetMatchStatus`、`riskLevel`、`matchStrategy` 和 `createdAt` 排序
- **AND** 默认排序 SHALL 为 `riskLevel DESC, componentType ASC, sourceName ASC`
- **AND** 后端 MUST 拒绝不在白名单内的排序字段

#### Scenario: 无权限查询分析结果明细
- **WHEN** 用户查询无权访问项目下的 SBOM 分析结果明细
- **THEN** 后端 SHALL 返回与资源不存在一致的安全错误
- **AND** 后端 MUST NOT 暴露分析运行、任务、环境、快照或结果明细是否存在

### Requirement: SBOM API 必须提供分析 artifact 查询
后端 API SHALL 提供 SBOM 分析 artifact 查询能力，用于前端审计页面和历史分析追溯。

#### Scenario: 查询 SBOM artifact 列表
- **WHEN** 已登录用户调用 `GET /api/sbom-analyses/{analysisId}/artifacts`
- **THEN** 后端 SHALL 根据 SBOM 运行所属项目校验访问权限
- **AND** 响应 SHALL 返回该分析运行下的 artifact 分页列表
- **AND** 列表项 SHALL 包含 artifact ID、artifact type、schema version、sha256、size bytes、created at 和 summary
- **AND** 列表响应 MUST NOT 返回完整 artifact content

#### Scenario: 分页查询 SBOM artifact
- **WHEN** 已登录用户调用 `GET /api/sbom-analyses/{analysisId}/artifacts?page=1&pageSize=20`
- **THEN** 后端 SHALL 返回分页响应
- **AND** 后端 SHALL 支持 `page` 和 `pageSize` 参数
- **AND** 后端 SHALL 对 `page` 和 `pageSize` 执行边界校验和最大页大小限制

#### Scenario: 过滤 SBOM artifact 列表
- **WHEN** 已登录用户查询 SBOM artifact 列表
- **THEN** 后端 SHALL 支持按 `artifactType`、`schemaVersion`、`taskId`、`sha256`、`createdFrom`、`createdTo`、`minSizeBytes` 和 `maxSizeBytes` 过滤
- **AND** 多个过滤条件 SHALL 使用 AND 语义
- **AND** 过滤结果 SHALL 仅限当前 `analysisId` 对应的 SBOM 运行

#### Scenario: 排序 SBOM artifact 列表
- **WHEN** 已登录用户查询 SBOM artifact 列表
- **THEN** 后端 SHALL 支持按 `artifactType`、`schemaVersion`、`createdAt`、`sizeBytes` 和 `sha256` 排序
- **AND** 后端 SHALL 支持升序和降序
- **AND** 默认排序 SHALL 为 `createdAt DESC, artifactType ASC`
- **AND** 后端 MUST 拒绝不在白名单内的排序字段

#### Scenario: 查询 SBOM artifact 内容
- **WHEN** 已登录用户调用 `GET /api/sbom-analyses/{analysisId}/artifacts/{artifactType}`
- **THEN** 后端 SHALL 根据 SBOM 运行所属项目校验访问权限
- **AND** 后端 SHALL 只返回该分析运行下指定类型的 artifact
- **AND** 响应 SHALL 包含 artifact metadata 和 content JSON
- **AND** 响应 MUST NOT 暴露明文凭据、私钥、token、passphrase、完整任务日志或服务器真实绝对路径

#### Scenario: 查询不存在的 artifact
- **WHEN** 用户查询不存在的 artifact type
- **THEN** 后端 SHALL 返回与资源不存在一致的安全错误
- **AND** 后端 MUST NOT 暴露其他项目或其他分析运行是否存在同类型 artifact

#### Scenario: 无权限查询 artifact
- **WHEN** 用户查询无权访问项目下的 SBOM artifact
- **THEN** 后端 SHALL 返回与资源不存在一致的安全错误
- **AND** 后端 MUST NOT 暴露分析运行、任务、环境、快照或 artifact 是否存在

#### Scenario: 不提供通用任务 artifact API
- **WHEN** 本 change 完成
- **THEN** 后端 SHALL NOT 新增通用 `GET /api/tasks/{taskId}/artifacts`
- **AND** 任务维度 artifact 查询 SHALL 留待后续 change 设计
