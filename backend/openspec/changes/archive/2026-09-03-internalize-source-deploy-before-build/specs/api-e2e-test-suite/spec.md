## ADDED Requirements

### Requirement: E2E 必须覆盖构建自动源码部署链路
API E2E SHALL 覆盖前端不调用正式源码部署创建接口时，构建验证能够自动部署源码并继续执行构建。

#### Scenario: 未预部署源码时创建构建
- **WHEN** E2E 创建项目、源码版本和当前双运行环境
- **AND** E2E 不调用正式 `POST /api/projects/{projectId}/source-deployments`
- **AND** E2E 调用 `POST /api/projects/{projectId}/builds`
- **THEN** 后端 SHALL 创建对应 `BUILD_VALIDATION` 任务和构建运行
- **AND** 构建任务 SHALL 在执行构建脚本前自动完成或复用源码部署
- **AND** E2E SHALL 验证构建记录包含 `sourceDeploymentId` 且状态可通过任务/SSE 观察

#### Scenario: 构建复用已有成功部署
- **WHEN** 同源码版本和同环境配置版本已经存在成功源码部署记录
- **AND** E2E 再次调用构建创建 API
- **THEN** 后端 SHALL 复用已有源码部署记录
- **AND** 构建任务 MUST NOT 重复执行源码传输

#### Scenario: 正式源码部署创建接口不再作为业务入口
- **WHEN** E2E 需要直接创建源码部署夹具
- **THEN** E2E SHALL 使用 `test-support` API 或数据库夹具准备数据
- **AND** 正式业务 E2E MUST NOT 依赖 `POST /api/projects/{projectId}/source-deployments` 作为构建前置步骤
