## Why

当前构建验证要求前端先调用源码部署 API，再调用构建 API；这把内部准备步骤暴露成了业务流程，导致构建、依赖分析和自动化测试前置链路割裂。源码应在构建任务创建后由后端自动部署或复用，前端只表达“开始构建/测试”的意图。

## What Changes

- 构建验证创建 API 改为自动确保所需运行环境存在当前源码版本的成功部署记录。
- 构建验证任务在 worker 执行时先执行或复用源码部署步骤，再执行构建脚本。
- `buildScope=SOURCE_ONLY` 只准备 source/x86 环境部署；默认双环境构建准备 source/x86 和 target/RISC-V 两侧部署。
- 正式业务流程不再要求前端调用源码部署创建接口。
- 源码部署查询能力保留为审计/排障入口；手动触发源码部署若仅用于测试，应迁移到 `test-support` API。
- 调整 E2E，使构建验证链路直接覆盖“未预先部署源码时自动部署并构建”的场景。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `source-deploy-runtime`: 源码部署从前端显式业务动作收敛为构建验证内部准备能力，并保留查询/审计语义。
- `build-validation-runtime`: 构建验证创建时自动部署或复用源码，不再因缺少预先部署记录直接拒绝构建。
- `api-e2e-test-suite`: E2E 覆盖构建创建自动触发源码部署、复用部署和测试专用部署入口。

## Impact

- 后端 API：`POST /api/projects/{projectId}/builds` 的创建语义改变为自动准备源码部署。
- 后端 API：正式 `POST /api/projects/{projectId}/source-deployments` 需要废弃、禁用或迁移到 test-support。
- 任务编排：源码部署不再作为构建前置独立任务暴露，成为 `BUILD_VALIDATION` handler 的内部步骤。
- 数据模型：优先复用现有 `source_deploy_runs`、`build_runs.source_deploy_run_id` 和 `tasks`，无强制新增表。
- 测试：需要更新构建验证、源码部署、E2E 和权限测试。
