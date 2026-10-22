## ADDED Requirements

### Requirement: API 必须提供依赖分析接口并标记 SBOM deprecated
后端 API SHALL 新增构建事实驱动的依赖分析接口，并 SHALL 将旧 SBOM 分析接口标记为 deprecated 兼容能力。

#### Scenario: 创建依赖分析
- **WHEN** 前端调用 `POST /api/projects/{projectId}/dependency-analyses`
- **THEN** 后端 SHALL 基于当前源码版本和成功 source/x86 构建运行创建 `DEPENDENCY_ANALYSIS` 任务
- **AND** 响应 SHALL 返回依赖分析运行 ID、任务 ID、源码版本 ID、source 构建运行 ID 和初始状态

#### Scenario: 查询依赖分析列表
- **WHEN** 前端调用 `GET /api/projects/{projectId}/dependency-analyses`
- **THEN** 后端 SHALL 返回分页列表
- **AND** 列表 SHALL 支持按 `sourceRevisionId`、状态、风险等级和创建时间过滤
- **AND** 列表 SHALL 支持稳定排序白名单

#### Scenario: 查询依赖分析结果
- **WHEN** 前端调用依赖分析结果列表或详情接口
- **THEN** 响应 SHALL 返回依赖类型、依赖名称、目标匹配状态、风险等级、位置标签、建议和 evidence 摘要
- **AND** 响应 MUST NOT 返回完整构建日志、完整脚本、明文凭据或服务器真实路径

#### Scenario: 构建 API 接收 buildScope
- **WHEN** 前端调用 `POST /api/projects/{projectId}/builds`
- **THEN** 请求体 MAY 包含 `buildScope`
- **AND** 未提交时默认 `BOTH`
- **AND** `SOURCE_ONLY` SHALL 只构建 source/x86 环境

#### Scenario: SBOM API 标记 deprecated
- **WHEN** 文档或响应描述旧 SBOM API
- **THEN** 后端 API 设计 SHALL 标记其为 deprecated
- **AND** 新流程文档 SHALL 引导前端使用依赖分析 API
