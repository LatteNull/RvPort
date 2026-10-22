## ADDED Requirements

### Requirement: API 必须提供报告历史和报告比较入口
后端 API SHALL 将评估报告历史查看和报告比较作为报告页面的主流程能力，并 SHALL 保留源码复检 API 作为兼容入口。

#### Scenario: 查询评估报告历史列表
- **WHEN** 前端打开评估报告页面
- **THEN** 前端 SHALL 能调用 `GET /api/projects/{projectId}/reports/evaluation` 获取历史报告分页列表
- **AND** 列表接口 SHALL 支持分页、排序和过滤
- **AND** 响应 MUST NOT 暴露完整报告正文、对象存储内部 key 或服务器真实路径

#### Scenario: 创建报告比较
- **WHEN** 前端在报告页面发起当前报告与历史报告比较
- **THEN** 前端 SHALL 调用 `POST /api/reports/{reportId}/comparisons`
- **AND** 请求体 MAY 包含 `baseReportId`
- **AND** 未传入 `baseReportId` 时后端 SHALL 自动选择上一份可比较历史报告
- **AND** 响应 SHALL 返回比较运行 ID、任务 ID、状态、base report 摘要和 target report 摘要

#### Scenario: 查询报告比较结果
- **WHEN** 前端查看报告比较结果
- **THEN** 前端 SHALL 能调用 `GET /api/report-comparisons/{comparisonId}` 获取比较摘要
- **AND** 前端 SHALL 能调用 `GET /api/report-comparisons/{comparisonId}/diff-items` 获取分页差异项
- **AND** 前端 SHALL 能调用 `GET /api/report-comparisons/{comparisonId}/diff-items/{diffItemId}` 获取差异详情
- **AND** 差异列表接口 SHALL 支持分页、排序和过滤

#### Scenario: 源码比较 API 作为兼容能力保留
- **WHEN** 文档描述 `GET /api/projects/{projectId}/source/compare/latest`、`POST /api/projects/{projectId}/rechecks` 或 `POST /api/projects/{projectId}/rechecks/latest`
- **THEN** API 设计 SHALL 标记这些接口为兼容能力
- **AND** 新主流程 SHALL 引导前端使用报告比较 API
