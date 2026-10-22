## ADDED Requirements

### Requirement: 归档 API 必须支持当前状态归档和最新归档概览
后端 API SHALL 为归档节点页提供当前状态归档入口、最新归档 overview、归档列表、详情和下载能力。

#### Scenario: 查询归档 overview
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/archives/overview`
- **THEN** 后端 SHALL 校验用户有权访问该项目
- **AND** 响应 SHALL 返回最新一条归档记录摘要
- **AND** 响应 SHALL 返回该归档记录包含的 `nodeType`、`candidateType`、标题、格式和数量摘要
- **AND** 若项目尚无归档记录，响应 SHALL 返回空 overview

#### Scenario: 创建当前状态归档
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/archives`
- **THEN** 后端 SHALL 校验用户有权访问该项目
- **AND** 后端 SHALL 以当前 active 源码版本创建归档任务
- **AND** 响应 SHALL 返回 `taskId`、归档 ID、初始归档状态和当前源码版本 ID

#### Scenario: 查询归档列表
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/archives`
- **THEN** 后端 SHALL 返回分页归档列表
- **AND** 列表接口 SHALL 支持按 `sourceRevisionId`、`status` 和时间范围过滤
- **AND** 列表接口 SHALL 支持按 `createdAt`、`status` 和 `name` 排序

### Requirement: 归档详情 API 必须按归档项展示报告
归档详情 API SHALL 返回归档创建时固化的归档项，使前端能够分别查看不同报告和摘要。

#### Scenario: 查询归档详情
- **WHEN** 已登录用户调用 `GET /api/archives/{archiveId}`
- **THEN** 后端 SHALL 按归档所属项目校验访问权限
- **AND** 响应 SHALL 返回归档元数据、源码版本摘要、状态、summary 和归档项列表
- **AND** 每个归档项 SHALL 包含 `nodeType`、`candidateType`、标题、资源引用、格式列表和安全摘要
- **AND** 响应 MUST NOT 返回对象存储 bucket、object key、服务器真实路径或明文凭据

#### Scenario: 查看归档项内容
- **WHEN** 已登录用户调用 `GET /api/archives/{archiveId}/items/{itemId}?format=HTML|JSON|LOG`
- **THEN** 后端 SHALL 校验归档项属于该归档
- **AND** 后端 SHALL 返回该归档项在创建时固化的对应格式内容
- **AND** 不支持或不存在的格式 SHALL 返回明确业务错误

#### Scenario: 下载归档包
- **WHEN** 已登录用户调用 `GET /api/archives/{archiveId}/download`
- **THEN** 后端 SHALL 按归档所属项目校验访问权限
- **AND** 后端 SHALL 返回该归档记录生成的压缩包
- **AND** 响应 MUST NOT 暴露对象存储 bucket、object key 或服务器真实路径

### Requirement: 归档 API 必须以源码版本隔离当前状态
归档 API SHALL 保证“归档当前状态”只归档当前 active 源码版本下的候选内容。

#### Scenario: 新源码版本隔离归档内容
- **WHEN** 项目已经激活新的源码版本
- **THEN** 创建归档请求 SHALL 使用新的 active `sourceRevisionId`
- **AND** 后端 MUST NOT 将上一源码版本的候选内容加入新归档

#### Scenario: 越权访问归档
- **WHEN** 用户访问无权限项目的归档 overview、列表、详情、归档项内容或下载接口
- **THEN** 后端 SHALL 返回访问拒绝错误
- **AND** 响应 MUST NOT 泄漏归档、项目、源码版本或候选是否存在
