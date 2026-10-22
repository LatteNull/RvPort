## 1. 源码部署内部化

- [x] 1.1 梳理 `SourceDeployHandler` 和 `SourceDeployService` 的传输逻辑，抽取 `SourceDeployExecutor` 或等效内部组件，避免依赖 HTTP controller 和独立任务编排。
- [x] 1.2 保留 `source_deploy_runs` 查询和详情能力，确认响应不暴露后端本机路径或明文凭据。
- [x] 1.3 将正式 `POST /api/projects/{projectId}/source-deployments` 调整为废弃/禁用行为，或迁移同等测试能力到 `test-support` API。
- [x] 1.4 补充源码部署 executor 创建、复用、跨项目拒绝、缺少工作目录和工作副本不存在的单元测试。

## 2. 构建创建编排

- [x] 2.1 修改 `BuildValidationService.create()`，缺少成功源码部署时仍按 `buildScope` 创建构建任务和构建运行。
- [x] 2.2 已存在当前源码版本、当前环境配置版本、目标环境的成功部署时，创建构建运行时直接写入 `source_deploy_run_id`。
- [x] 2.3 缺少成功部署时，允许构建运行先创建并在执行早期由 handler 回填 `source_deploy_run_id`。
- [x] 2.4 修改 `BuildValidationHandler`，在执行构建脚本前调用源码部署 executor 完成或复用部署。
- [x] 2.5 部署失败时将对应 `BUILD_VALIDATION` 任务和 `build_runs` 标记为失败、取消或超时，并且不执行构建脚本。
- [x] 2.6 确认双环境构建中单侧部署或构建失败不影响另一侧状态写回。

## 3. API 响应和状态

- [x] 3.1 保持构建创建响应以构建运行为核心，支持运行早期 `sourceDeploymentId` 为空。
- [x] 3.2 构建任务完成或复用源码部署后，详情响应返回 `sourceDeploymentId`。
- [x] 3.3 保持正式构建 API 不接受 `sourceDeploymentIds`，继续返回 `BUILD_SOURCE_DEPLOYMENTS_DEPRECATED`。
- [x] 3.4 确认任务事件/SSE 能在同一个 `BUILD_VALIDATION` 任务中覆盖源码部署阶段和构建阶段。

## 4. 测试支持和 E2E

- [x] 4.1 如仍需直接创建源码部署夹具，新增 `test-support` API，并确保默认生产 jar 不包含该入口。
- [x] 4.2 更新 `002-project-source-environment` E2E，移除对正式源码部署创建 API 的业务依赖。
- [x] 4.3 更新构建验证 E2E，覆盖未预部署源码时直接创建构建，构建任务内部自动部署并执行构建。
- [x] 4.4 覆盖部署复用场景，确认已有成功部署时构建任务不会重复传输源码。
- [x] 4.5 覆盖权限、异常流程和 edge case，包括无项目权限、缺少运行环境、禁用环境、缺少工作目录、缺少源码工作副本。

## 5. 验证

- [x] 5.1 运行相关 Java 单元测试。
- [x] 5.2 运行 API E2E 的源码、构建和依赖分析相关模块；其中依赖分析模块因当前 shell 未配置真实 SSH E2E 环境变量而按用例要求失败并完成清理。
- [x] 5.3 重建后端容器，使用真实环境验证一次 source-only 构建和一次双环境构建，确认无需调用正式源码部署创建 API。
- [x] 5.4 运行 `openspec validate internalize-source-deploy-before-build --strict` 并修复发现的问题。
