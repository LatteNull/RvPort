## MODIFIED Requirements

### Requirement: 项目 API 必须提供工作台根实体管理
后端 SHALL 提供项目列表、创建、详情、基础信息更新和概览 API，并 SHALL 使用 `projects` 表作为项目根实体事实来源。项目名称允许重复，项目唯一识别 SHALL 使用 `projectId`。

#### Scenario: 创建项目
- **WHEN** 已登录用户调用 `POST /api/projects` 并提交项目名称、描述、源架构和目标架构
- **THEN** 后端 SHALL 创建 `projects` 记录
- **AND** 默认 `stage` SHALL 为 `PROJECT_CREATED`
- **AND** 默认 `status` SHALL 为 `ACTIVE`
- **AND** `created_by` SHALL 使用当前登录用户 ID

#### Scenario: 创建同名项目
- **WHEN** 已登录用户创建一个与已有项目名称相同的新项目
- **THEN** 后端 SHALL 允许创建
- **AND** 后端 SHALL 使用新的 `projectId` 区分该项目
- **AND** 后端 MUST NOT 因名称重复返回冲突错误

#### Scenario: 查询项目列表
- **WHEN** 已登录用户调用 `GET /api/projects`
- **THEN** 后端 SHALL 返回未软删除项目的分页列表
- **AND** 列表 SHALL 支持按 `status`、`stage` 和关键字筛选
- **AND** 每个列表项 SHALL 包含 `highRiskCount`、`latestScanAt`、`latestBuildStatus` 和 `latestTestStatus`
- **AND** 尚无对应扫描、构建或测试记录时，摘要字段 SHALL 返回 `0` 或 `null`

#### Scenario: 更新项目基础信息
- **WHEN** 已登录用户调用 `PATCH /api/projects/{projectId}`
- **THEN** 后端 SHALL 只允许更新项目名称、描述、源架构、目标架构和项目状态
- **AND** 后端 MUST NOT 通过该接口把 `stage` 当作任意可写状态机字段

#### Scenario: 读取项目概览
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/overview`
- **THEN** 后端 SHALL 返回项目基本信息、当前启用源码版本、源码版本数量、环境摘要、最近任务摘要和推荐下一步动作
- **AND** 概览 SHALL 从源码版本、环境和任务等事实数据聚合当前状态
- **AND** 概览 MUST NOT 只依赖 `projects.stage` 表达项目真实状态
