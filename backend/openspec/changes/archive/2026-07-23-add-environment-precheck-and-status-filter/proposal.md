## Why

当前新建环境页面需要在环境尚未创建时验证 SSH 连接，但现有连接测试接口依赖已有 `environmentId`，导致前端无法在提交前做有效校验。同时 SBOM 配置等页面需要只展示当前可用环境，现有环境列表只能按 `role` 和 `enabled` 过滤，不能按运行状态筛选。

## What Changes

- 新增项目作用域的环境连接预检 API，允许前端提交新建环境表单中的 SSH 配置并创建一次连接测试任务。
- 环境预检不创建 `environments` 记录，不提前保存无效环境；任务输入必须脱敏，并使用任务级临时加密凭据承载未保存表单中的密码或私钥。
- 扩展环境列表 API，支持按 `status` 过滤环境，例如筛选 `AVAILABLE` 环境供 SBOM 分析配置使用。
- 保持已有 `POST /api/projects/{projectId}/environments/{environmentId}/test-connection` 接口，用于已创建环境的复测。
- 补充单元测试和 E2E，覆盖正常流程、异常流程和 edge case。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `backend-api-design`: 增加新建环境前连接预检 API 和环境列表 `status` 过滤的接口契约。
- `project-source-environment`: 增加环境预检任务行为和环境状态过滤能力要求。

## Impact

- 影响后端环境 API、环境 service/repository、环境运行任务输入模型、SSH runtime 任务处理、Liquibase schema 和 API E2E 测试。
- 新增 `task_secret_payloads` 表保存任务级临时加密凭据；未保存环境表单提交的密码或私钥不得写入正式 `credentials` 表。
- 不涉及前端实现，但接口契约会支持前端新建环境表单和 SBOM 环境选择流程。
