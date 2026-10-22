## ADDED Requirements

### Requirement: SBOM API 必须创建和查询分析运行
后端 API SHALL 提供项目级 SBOM 分析创建、运行列表、运行详情、组件结果和采集详情接口。

#### Scenario: 创建 SBOM 分析任务
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/sbom-analyses`
- **THEN** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 后端 SHALL 校验源环境、目标环境、源快照和目标快照属于该项目
- **AND** 后端 SHALL 创建 `SBOM_ANALYSIS` 任务并返回 `taskId`、任务类型和初始状态
- **AND** API 响应 MUST NOT 返回服务器真实路径、完整任务输入快照或明文凭据

#### Scenario: 查询项目 SBOM 分析列表
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/sbom-analyses`
- **THEN** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 后端 SHALL 返回该项目下 SBOM 运行分页列表
- **AND** 列表项 SHALL 包含运行 ID、任务 ID、状态、环境摘要、快照摘要、统计摘要和关键时间字段

#### Scenario: 查询 SBOM 分析详情
- **WHEN** 已登录用户调用 `GET /api/sbom-analyses/{analysisId}`
- **THEN** 后端 SHALL 根据 SBOM 运行所属项目校验访问权限
- **AND** 响应 SHALL 返回运行摘要、任务状态、环境摘要、快照摘要、统计摘要和警告摘要
- **AND** 响应 MUST NOT 暴露服务器真实路径

### Requirement: SBOM API 必须提供组件替代结果
后端 API SHALL 提供 SBOM 组件和替代候选结果查询能力，用于前端结果表格展示。

#### Scenario: 查询组件替代结果
- **WHEN** 已登录用户调用 `GET /api/sbom-analyses/{analysisId}/components`
- **THEN** 后端 SHALL 根据 SBOM 运行所属项目校验访问权限
- **AND** 后端 SHALL 返回分页组件结果
- **AND** 响应项 SHALL 包含源侧组件、候选替代项、替代结论、风险、建议和证据摘要

#### Scenario: 过滤组件替代结果
- **WHEN** 前端按风险、替代结论、组件名称或组件类型查询组件结果
- **THEN** 后端 SHALL 支持对应筛选参数
- **AND** 后端 SHALL 只返回当前分析运行内的结果

#### Scenario: 无权限查询组件结果
- **WHEN** 用户查询无权访问项目下的 SBOM 组件结果
- **THEN** 后端 SHALL 返回与资源不存在一致的安全错误
- **AND** 后端 MUST NOT 暴露分析运行、环境、快照或组件是否存在

### Requirement: SBOM API 必须提供采集详情
后端 API SHALL 提供分析所用源快照和目标快照的采集详情摘要，帮助前端解释分析可信度。

#### Scenario: 查询采集详情
- **WHEN** 已登录用户调用 `GET /api/sbom-analyses/{analysisId}/collection-detail`
- **THEN** 后端 SHALL 根据 SBOM 运行所属项目校验访问权限
- **AND** 响应 SHALL 返回源快照和目标快照的采集时间、OS、kernel、arch、包管理器、软件源摘要、工具版本摘要、组件数量和解析警告
- **AND** 响应 MUST NOT 返回敏感路径、明文凭据或服务器真实路径

#### Scenario: 快照包含仓库采集警告
- **WHEN** 目标快照存在仓库清单或 provides 采集警告
- **THEN** 采集详情响应 SHALL 返回可展示的警告摘要
- **AND** 响应 SHALL 不把该警告伪装为分析器失败

### Requirement: SBOM API MVP 不实现加入问题清单
本 change 的 SBOM API SHALL 不实现 `components:add-to-issues` 业务联动，避免提前耦合 issue 管理流程。

#### Scenario: 用户尝试调用加入问题清单接口
- **WHEN** 客户端调用 `POST /api/sbom-analyses/{analysisId}/components:add-to-issues`
- **THEN** 后端 MAY 返回未实现或接口不存在
- **AND** 后端 MUST NOT 在本 change 中创建或修改 `issues`、`issue_sources` 或 `issue_events`
