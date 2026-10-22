## ADDED Requirements

### Requirement: API 必须提供优化轮次聚合查询
后端 API SHALL 提供项目级优化轮次概览、列表和详情接口，用于展示多轮优化结果聚合。

#### Scenario: 查询当前优化概览
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/optimization/overview`
- **THEN** 后端 SHALL 校验用户有权访问该项目
- **AND** 响应 SHALL 返回当前 active 源码版本对应的优化轮次
- **AND** 响应 SHALL 包含迁移输入、报告、复检、源码部署、构建、测试和测试结果比较摘要
- **AND** 响应 MUST NOT 返回完整日志、完整报告正文、完整 agent 输入、明文凭据或服务器真实路径

#### Scenario: 查询优化轮次列表
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/optimization/cycles`
- **THEN** 后端 SHALL 返回该项目优化轮次分页列表
- **AND** 列表接口 SHALL 支持按 `sourceRevisionId`、`status` 和时间范围过滤
- **AND** 列表接口 SHALL 支持按 `cycleNumber`、`createdAt`、`updatedAt` 和 `startedAt` 排序

#### Scenario: 查询优化轮次详情
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/optimization/cycles/{cycleId}`
- **THEN** 后端 SHALL 校验该轮次属于该项目
- **AND** 响应 SHALL 返回轮次元数据、源码版本摘要、聚合摘要和相关资源引用
- **AND** 响应 MUST NOT 返回任何子节点的完整日志正文、对象存储内部 key 或服务器真实路径

#### Scenario: 优化轮次 API 不触发任务
- **WHEN** 用户查询优化概览、轮次列表或轮次详情
- **THEN** 后端 MUST NOT 创建扫描、报告、复检、源码部署、构建、测试或测试比较任务
- **AND** API 只返回已有事实数据的聚合展示
