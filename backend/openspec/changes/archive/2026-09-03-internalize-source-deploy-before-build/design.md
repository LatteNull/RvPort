## Context

当前后端已经具备 `SOURCE_DEPLOY` handler、`source_deploy_runs` 记录、构建运行对 `source_deploy_run_id` 的引用，以及基于当前项目运行环境版本的过滤。问题在于创建构建时仍要求前端先完成源码部署，否则返回 `SOURCE_DEPLOYMENT_NOT_READY`。这会把内部准备步骤暴露给页面，并让构建验证、依赖分析前置构建和自动化测试链路产生额外状态耦合。

本次变更只处理后端。前端后续只需要调用构建相关 API，不需要再显式调用源码部署创建 API。

## Goals / Non-Goals

**Goals:**

- 构建验证任务执行时自动准备源码部署。
- 保留 `source_deploy_runs` 作为审计和构建输入事实。
- 复用现有源码部署传输逻辑，但不再把部署作为构建前置独立任务编排。
- 支持默认双环境构建和 `SOURCE_ONLY` 前置构建。
- 将正式源码部署创建入口从业务流程中移除或禁用，测试用途迁移到 `test-support`。
- 补齐正常流程、异常流程和 edge case 单元测试/E2E。

**Non-Goals:**

- 不修改前端页面。
- 不改变源码上传、Git 拉取和源码版本管理机制。
- 不改变自动化测试依赖构建记录的模型。
- 不引入 Docker Swarm/K8s 级别的跨节点编排。
- 不删除 `source_deploy_runs` 历史记录和查询能力。

## Decisions

### 1. `BUILD_VALIDATION` handler 负责源码部署准备

`BuildValidationService.create()` 创建 `BUILD_VALIDATION` task 和 `build_runs` 记录时，不再要求已经存在成功的源码部署记录。真正执行时，由 `BUILD_VALIDATION` handler 在远端构建前对每个构建运行执行：

```text
BUILD_VALIDATION task
 │
 ├─ ensureSourceDeployed(projectId, sourceRevisionId, environmentId, envVersion)
 │    ├─ 已有 SUCCEEDED 部署：复用 source_deploy_runs.remote_path
 │    └─ 无成功部署：在当前任务内打包、上传、解包源码，并写入 source_deploy_runs
 │
 └─ 在部署目录执行构建脚本
```

理由：源码部署是构建的输入准备，不是用户独立决策。放到构建任务内部能让一个用户动作对应一个主要任务，取消、失败、日志和 SSE 都围绕 `BUILD_VALIDATION` 展开。

备选方案是保留正式源码部署按钮，由前端串联两个 API。这个方案会继续暴露内部状态，并且容易造成依赖分析、构建验证、自动化测试之间的调用顺序漂移。

### 2. 抽取源码部署执行器，而不是复用独立 `SOURCE_DEPLOY` worker 编排

保留 `source_deploy_runs` 和源码部署传输实现，但应将实际传输步骤抽成内部组件，例如 `SourceDeployExecutor`。`SOURCE_DEPLOY` handler 如果仍保留，可作为测试或兼容路径调用同一个 executor；正式构建路径由 `BUILD_VALIDATION` handler 直接调用 executor。

理由：这样能复用 tar over SSH、日志、取消、失败状态和脱敏处理，同时避免“部署任务完成后再触发构建任务”的跨任务状态机。

### 3. 构建创建立即产生构建运行

构建创建 API 应继续返回构建运行列表。每个构建运行初始可为 `PENDING` 或 `QUEUED`，`source_deploy_run_id` 可以在创建时为空，待 handler 完成部署后更新为实际使用的 `source_deploy_runs.id`。

如果创建时已经能复用成功部署，则可以直接写入 `source_deploy_run_id`。如果不能复用，则 handler 在执行部署后补齐该字段。

理由：前端点击构建后应立刻获得构建运行 ID，后续日志、取消、详情和列表都围绕构建运行工作，而不是先展示部署准备任务。

### 4. 正式 source deploy 创建入口降级

`GET /api/projects/{projectId}/source-deployments` 和 `GET /api/source-deployments/{id}` 保留，用于审计、排障和历史状态。`POST /api/projects/{projectId}/source-deployments` 和 cancel 这类驱动动作不再作为正式业务入口。

测试或 E2E 需要直接准备部署记录时，使用 `src/test-support/java` 下的 `/api/test-support/**` 入口。生产 jar 默认不包含这些接口。

### 5. 响应保持构建语义

构建创建 API 返回构建运行 ID、任务 ID、环境 ID、sourceRevision ID、environmentConfigVersion 和状态。部署阶段的日志和失败也写入同一个构建任务日志/SSE；响应不新增后端本机路径，远端 `remotePath` 仍只通过既有安全摘要或详情策略暴露。

## Risks / Trade-offs

- [Risk] 构建任务内部增加源码部署步骤后，构建失败原因可能来自部署而不是编译。
  Mitigation：保留明确错误码，例如 `SOURCE_DEPLOYMENT_FAILED`、`SOURCE_DEPLOY_REMOTE_TAR_REQUIRED`，并在构建日志中标明阶段。

- [Risk] `build_runs.source_deploy_run_id` 在任务开始前可能为空。
  Mitigation：构建 handler 完成部署或复用部署后立即回填；构建详情需允许运行早期该字段为空。

- [Risk] 旧的 `SOURCE_DEPLOY` handler 与新的内部 executor 逻辑分叉。
  Mitigation：把传输逻辑抽成单一 executor，handler 和构建路径都调用它。

- [Risk] 正式源码部署 POST 直接删除会破坏现有前端或脚本。
  Mitigation：先改为 deprecated/disabled 明确错误，E2E 和前端迁移后再考虑删除 controller 方法。

## Migration Plan

1. 抽取源码部署传输 executor，保留现有部署记录写入、日志、错误码和脱敏策略。
2. 更新构建创建服务，使缺少成功部署时仍创建 `BUILD_VALIDATION` task 和 `build_runs`。
3. 更新构建 handler，在执行构建脚本前调用 executor 完成或复用源码部署，并回填 `source_deploy_run_id`。
4. 废弃正式源码部署创建 API，必要时迁移直接触发能力到 test-support。
5. 更新单元测试和 E2E。
6. 重建后端容器，验证未预部署源码时构建任务能先部署源码再构建。

Rollback 策略：如果内部部署步骤出现阻塞，可以临时恢复构建 handler 对已成功部署记录的要求，并保留源码部署 POST 的 deprecated 兼容入口。

## Open Questions

- 无。
