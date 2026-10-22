## Why

源码部署能力已经可以把同一源码版本同步到 x86 和 RISC-V 环境，但后端还没有构建验证运行时。后续迁移流程需要在远端环境中执行用户确认的构建脚本，并记录状态、退出码和日志，验证修复后的源码没有破坏原始环境且能在目标环境构建。

## What Changes

- 新增构建验证后端 API，支持基于一个或多个成功的源码部署记录创建构建任务。
- 新增 `BUILD_VALIDATION` 任务类型和 worker handler，在远端源码部署目录中执行构建脚本。
- 构建脚本按任务保存并加密存储，worker 执行时上传为临时脚本，执行完成或失败后删除远端临时脚本。
- 构建运行结果写入 `build_runs`，包括项目、任务、源码版本、环境、源码部署记录、命令摘要、工作目录、退出码、状态、失败分类、日志引用和时间字段。
- 构建日志复用已有任务日志和项目级 SSE，前端可通过任务事件实时展示进度，并通过任务日志 API 查看历史日志。
- 构建查询 API 支持分页、排序和按源码版本、环境、状态、时间范围过滤。
- 构建取消复用已有运行中任务取消机制，取消远端 SSH 命令并同步 `build_runs` 终态。
- 更新 E2E 模块，覆盖构建验证创建、远端执行、列表/详情、权限隔离、失败和取消行为。

## Capabilities

### New Capabilities
- `build-validation-runtime`: 定义构建验证 API、远端执行、状态持久化、日志/SSE 和取消行为。

### Modified Capabilities
- `source-deploy-runtime`: 明确构建验证必须引用成功源码部署记录，且支持同一源码版本在多个环境分别构建。
- `backend-api-design`: 将构建验证 API 输入从客户端提交远端工作目录调整为引用 `sourceDeploymentIds`。
- `backend-database-design`: 为 `build_runs` 补充源码部署引用、构建脚本摘要和查询索引约束。
- `api-e2e-test-suite`: 增加构建验证模块化 E2E 覆盖要求。

## Impact

- 后端 API：新增/调整 `/api/projects/{projectId}/builds`、`/api/builds/{buildId}`、`/api/builds/{buildId}/cancel`。
- 数据库：扩展 `build_runs`，必要时新增索引；复用 `task_script_payloads` 存储构建脚本密文。
- Worker：新增 `BUILD_VALIDATION` handler，复用 SSH runtime、任务运行时、取消机制和日志事件。
- E2E：新增构建验证模块，依赖 PostgreSQL、Redis、RabbitMQ、后端服务和可访问 SSH 环境。
