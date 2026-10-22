## ADDED Requirements

### Requirement: 构建验证 API 必须使用源码部署引用
后端 API 设计 SHALL 将构建验证创建输入建模为源码部署引用，而不是客户端提交远端工作目录。

#### Scenario: 创建构建验证请求
- **WHEN** 前端调用 `POST /api/projects/{projectId}/builds`
- **THEN** 请求体 SHALL 包含 `sourceDeploymentIds`、`script` 和可选 `timeoutSeconds`
- **AND** 请求体 MAY 包含 `sourceRevisionId` 用于显式一致性校验
- **AND** 请求体 MUST NOT 包含任意远端 `workingDirectory` 或 `remotePath`
- **AND** 响应 SHALL 返回每个构建运行的 `buildRunId`、`taskId`、`environmentId`、`sourceRevisionId`、`sourceDeploymentId` 和初始状态

#### Scenario: 构建详情响应
- **WHEN** 前端调用 `GET /api/builds/{buildId}`
- **THEN** 响应 SHALL 包含构建运行状态、退出码、失败分类、任务引用、源码版本摘要、环境摘要、源码部署引用和日志引用
- **AND** 响应 MUST NOT 返回完整脚本明文、明文凭据、后端本机路径或未脱敏远端命令

#### Scenario: 构建实时状态
- **WHEN** 构建任务状态变化或输出日志摘要
- **THEN** 后端 SHALL 通过项目级 SSE 推送任务事件
- **AND** 前端 SHALL 通过任务详情和任务日志 API 补偿查询历史状态与日志
