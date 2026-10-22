## ADDED Requirements

### Requirement: API 必须以前置项目运行环境作为远程运行环境来源
后端 API SHALL 提供项目运行环境配置接口，并 SHALL 使 SBOM、源码部署、构建验证和自动化测试从该配置读取环境，而不是从业务运行请求读取环境选择。

#### Scenario: 查询项目运行环境配置
- **WHEN** 前端打开环境管理页或项目概览页
- **THEN** 前端 SHALL 能调用 `GET /api/projects/{projectId}/runtime-environments`
- **AND** 响应 SHALL 包含 source 环境、target 环境、配置版本、是否 ready 和缺失项

#### Scenario: 更新项目运行环境配置
- **WHEN** 前端在环境管理页选择源环境、目标环境或同时选择两者
- **THEN** 前端 SHALL 调用 `PATCH /api/projects/{projectId}/runtime-environments`
- **AND** 请求 MAY 只包含 `sourceEnvironmentId`
- **AND** 请求 MAY 只包含 `targetEnvironmentId`
- **AND** 请求 MAY 同时包含 `sourceEnvironmentId` 和 `targetEnvironmentId`
- **AND** 后端 SHALL 校验提交的环境属于当前项目且已启用

#### Scenario: SBOM 创建不再提交环境 ID
- **WHEN** 前端调用 `POST /api/projects/{projectId}/sbom-analyses`
- **THEN** 请求 MUST NOT 要求提交 `sourceEnvironmentId` 或 `targetEnvironmentId`
- **AND** 后端 SHALL 从项目运行环境配置读取双环境
- **AND** 双环境未配置完整时 API SHALL 返回明确业务错误

#### Scenario: 源码部署不再提交环境列表
- **WHEN** 前端调用 `POST /api/projects/{projectId}/source-deployments`
- **THEN** 请求 MUST NOT 要求提交 `environmentIds`
- **AND** 后端 SHALL 将源码部署到项目运行环境配置中的源环境和目标环境
- **AND** 双环境未配置完整时 API SHALL 返回明确业务错误

#### Scenario: 构建验证不再提交源码部署环境选择
- **WHEN** 前端调用 `POST /api/projects/{projectId}/builds`
- **THEN** 请求 MUST NOT 要求提交 `sourceDeploymentIds`
- **AND** 后端 SHALL 基于当前源码版本、项目运行环境配置和成功源码部署记录创建构建运行
- **AND** 缺少可用源码部署记录时 API SHALL 返回明确业务错误

#### Scenario: 自动化测试不再提交环境 ID
- **WHEN** 前端调用 `POST /api/projects/{projectId}/tests`
- **THEN** 请求 MUST NOT 要求提交 `environmentId`
- **AND** 后端 SHALL 从关联构建运行或当前项目运行环境配置确定测试环境
- **AND** API 响应 MUST NOT 暴露明文凭据或服务器真实路径
