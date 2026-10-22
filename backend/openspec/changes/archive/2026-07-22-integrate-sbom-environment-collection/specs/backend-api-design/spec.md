## MODIFIED Requirements

### Requirement: SBOM API 必须创建和查询分析运行
后端 API SHALL 提供项目级 SBOM 分析创建、运行列表、运行详情、组件结果和采集详情接口，并 SHALL 由后端 SBOM 任务内部负责本轮环境采集。

#### Scenario: 创建 SBOM 分析任务
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/sbom-analyses`
- **THEN** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 后端 SHALL 校验源环境和目标环境属于该项目
- **AND** 请求 MUST NOT 要求 `sourceSnapshotId` 或 `targetSnapshotId`
- **AND** 请求 MUST NOT 要求前端提交采集范围或分析选项
- **AND** 后端 SHALL 使用默认全量采集和默认分析策略创建任务
- **AND** 后端 SHALL 创建 `SBOM_ANALYSIS` 任务并返回 `taskId`、任务类型和初始状态
- **AND** 后端 SHALL 创建或准备关联该任务的 SBOM 运行记录，运行记录 MAY 在采集完成前没有源快照或目标快照
- **AND** API 响应 MUST NOT 返回服务器真实路径、完整任务输入快照或明文凭据

#### Scenario: 查询项目 SBOM 分析列表
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/sbom-analyses`
- **THEN** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 后端 SHALL 返回该项目下 SBOM 运行分页列表
- **AND** 列表项 SHALL 包含运行 ID、任务 ID、状态、环境摘要、已生成的快照摘要、统计摘要和关键时间字段
- **AND** 当快照尚未生成时，列表项 SHALL 返回空快照摘要或明确的采集中状态，而不是返回错误

#### Scenario: 查询 SBOM 分析详情
- **WHEN** 已登录用户调用 `GET /api/sbom-analyses/{analysisId}`
- **THEN** 后端 SHALL 根据 SBOM 运行所属项目校验访问权限
- **AND** 响应 SHALL 返回运行摘要、任务状态、环境摘要、已生成的快照摘要、统计摘要和警告摘要
- **AND** 当采集失败或分析失败时，响应 SHALL 返回安全的失败阶段和错误摘要
- **AND** 响应 MUST NOT 暴露服务器真实路径

### Requirement: SBOM API 必须提供采集详情
后端 API SHALL 提供分析所用源快照和目标快照的采集详情摘要，帮助前端解释分析可信度，并 SHALL 支持采集尚未完成的中间状态。

#### Scenario: 查询采集详情
- **WHEN** 已登录用户调用 `GET /api/sbom-analyses/{analysisId}/collection-detail`
- **THEN** 后端 SHALL 根据 SBOM 运行所属项目校验访问权限
- **AND** 响应 SHALL 返回源快照和目标快照的采集时间、OS、kernel、arch、包管理器、软件源摘要、工具版本摘要、组件数量和解析警告
- **AND** 响应 MUST NOT 返回敏感路径、明文凭据或服务器真实路径

#### Scenario: 快照尚未生成
- **WHEN** SBOM 运行仍在源环境采集或目标环境采集阶段
- **THEN** 采集详情响应 SHALL 表达对应侧快照尚未可用
- **AND** 后端 MUST NOT 将快照尚未生成误报为资源不存在

#### Scenario: 环境采集失败
- **WHEN** SBOM 任务的源环境采集或目标环境采集失败
- **THEN** 采集详情响应 SHALL 返回已经成功生成的快照摘要
- **AND** 失败侧 SHALL 返回安全错误摘要和失败阶段
- **AND** 响应 MUST NOT 暴露明文凭据、SSH 连接细节或敏感路径
