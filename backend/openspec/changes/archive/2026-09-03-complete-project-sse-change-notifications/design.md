## Context

当前后端已经有统一任务运行时和项目级 SSE：

- `TaskService` 创建任务后写入 `task.created`，提交事务后投递 RabbitMQ。
- `TaskWorkerService` 在任务认领、成功、失败、取消、重试时写入任务事件。
- `DefaultTaskExecutionContext` 在 handler 运行期间写入进度和日志摘要事件。
- `TaskSseController` 提供 `GET /api/projects/{projectId}/task-events`，并按 `projectId` 做访问控制和事件隔离。
- `ProjectService.overview` 已返回 `latestTaskEventId`，可以作为前端首次连接 SSE 的 baseline。

缺口在于事件语义不够完整：

- `TaskEventView` 只有 `taskType`，缺少 `stageId`、`resourceType`、`resourceId`、`environmentRole`、`mode` 等前端局部刷新所需元数据。
- `task_events.task_id` 当前为 `NOT NULL`，无法表达 active source、运行环境选择、环境配置版本这类非任务绑定的项目上下文变更。
- 源码上传/激活、git sync 激活、项目运行环境选择更新等路径只更新数据库和 audit，没有统一推送 `project.context.changed`。

本次设计以“轻量通知”为边界：SSE 不承载完整业务数据，不承担完整历史恢复；前端收到事件后重新读取 overview、节点列表、节点详情或 readiness。

## Goals / Non-Goals

**Goals:**

- 让每个异步节点的任务生命周期事件都能携带可识别的节点和资源元数据。
- 让源码版本、运行环境选择、环境配置版本等项目上下文变化通过同一项目级 SSE 通道通知前端。
- 保持 SSE 严格按项目隔离。
- 保持 `overview.latestTaskEventId` 作为首次连接 baseline。
- 补齐单元测试和 E2E，覆盖事件元数据、上下文变更事件和项目隔离。

**Non-Goals:**

- 不实现完整历史事件回放。
- 不让 SSE 返回完整业务详情、完整日志、完整报告或扫描结果。
- 不修改前端展示逻辑。
- 不重新设计任务队列、worker 并发、任务日志 SSE 或业务节点状态模型。

## Decisions

### 1. SSE 作为项目变更通知通道，不作为完整数据通道

事件 payload 保持轻量，包含：

- `id`
- `projectId`
- `taskId`
- `taskType`
- `eventType`
- `status`
- `progress`
- `message`
- `stageId`
- `resource`
- `occurredAt`

前端收到事件后按 `stageId/resource` 判断刷新范围，再读取 overview、列表或详情接口。

备选方案是把节点完整结果直接塞进 SSE。这会造成事件体过大、权限审计复杂、前端状态合并复杂，不适合当前系统。

### 2. 任务创建时写入稳定节点元数据

扩展 `TaskCreateCommand`，允许业务模块提供：

- `stageId`
- `resourceType`
- `resourceId`
- `resourceMode`
- `environmentRole`

这些字段写入 `tasks`，事件查询时从 `tasks` join 出来；必要时也可在 `task_events` 中保留快照字段。MVP 推荐先写入 `tasks`，减少重复字段，事件只表达当前任务关联的稳定资源。

对于典型映射：

| taskType | stageId | resourceType | 说明 |
|---|---|---|---|
| `SOURCE_GIT_SYNC` | `source` | `source_import` | Git 源码导入任务 |
| `ENV_TEST_CONNECTION` | `environment` | `environment` | 环境连接测试 |
| `ENV_RUN_SCRIPT` | `environment` | `environment` | 环境检查或自定义脚本 |
| `ENV_COLLECT` | `environment` | `environment_snapshot` | 环境采集，历史兼容 |
| `BUILD_VALIDATION` | `x86-build` 或 `build-validation` | `build_run` | `SOURCE_ONLY` 映射到 x86 前置构建，`BOTH` 映射到双环境构建验证 |
| `DEPENDENCY_ANALYSIS` | `dependency-analysis` | `dependency_analysis_run` | 构建驱动依赖分析 |
| `DEPENDENCY_AUTO_FIX` | `dependency-analysis` | `dependency_auto_fix_run` | 依赖一键修复 |
| `KB_SCAN` | `kb-scan` | `kb_scan_run` | 知识库扫描 |
| `KB_AI_EXTENSION` | `kb-scan` | `kb_ai_extension_run` | 知识库 AI 扩展 |
| `REPORT_GENERATE` | `evaluation-report` | `report` | 评估报告生成 |
| `REPORT_COMPARE` | `evaluation-report` | `report_comparison_run` | 报告比较 |
| `RECHECK_DIFF` | `evaluation-report` | `recheck_run` | 历史兼容的复检差异 |
| `AUTOMATED_TEST` | `automated-test` | `test_run` | 自动化测试 |
| `TEST_LOG_COMPARE` | `automated-test` | `test_comparison_run` | 测试结果比较 |
| `ARCHIVE_PROJECT` | `archive` | `project_archive` | 项目归档 |
| `SBOM_ANALYSIS` | `dependency-analysis` | `sbom_run` | deprecated 历史任务 |

### 3. 项目上下文变更事件允许无 taskId

源码 active revision、运行环境选择、环境配置版本变更并不天然绑定某一个正在执行的任务。为了避免伪造 task，事件流需要支持项目级事件。

推荐实现方式：

- 将 `task_events.task_id` 改为 nullable。
- 查询事件时从 `JOIN tasks` 改为 `LEFT JOIN tasks`。
- `TaskEventView.taskId/taskType` 允许为空。
- 新增事件类型 `project.context.changed`。
- 上下文事件携带 `stageId=context`、`resourceType`、`resourceId`、`changedFields`。

备选方案是新建 `project_events` 表。这个方案模型更干净，但会引入双表合并排序和迁移复杂度。当前 endpoint 已经作为项目事件流使用，允许 `task_id` 为空是更小的变更。

### 4. 不做完整历史补发

当前 endpoint 已经支持：

- 无 cursor 时使用当前项目最新事件作为 baseline。
- `afterEventId` 或 `Last-Event-ID` 请求时读取游标之后的事件。

本次保持这个行为，但规范上不承诺完整历史回放。前端断线或首次打开页面应先读取 overview，再用 `latestTaskEventId` 建立 SSE baseline。后端可以提供有限 catch-up，但不能依赖它恢复完整页面状态。

### 5. 上下文事件必须在事务提交后发布

项目上下文事件应复用 `TaskEventService` 的 after-commit 发布机制，避免前端收到 SSE 后马上重读 overview 却读到旧数据。

需要补事件的路径至少包括：

- 上传源码并激活当前源码版本。
- 手动激活源码版本。
- Git 同步任务完成并激活当前源码版本。
- 更新项目运行环境选择。
- 环境配置变更导致当前 runtime environment version 失效或更新。

## Risks / Trade-offs

- [Risk] 修改 `task_events.task_id` 可空会影响 jOOQ 生成代码和既有测试断言。
  Mitigation: 用 Liquibase 增量迁移，更新 view/mapper/测试，保留已有 task 事件行为。

- [Risk] 不做完整历史补发后，前端如果只依赖 SSE 会丢状态。
  Mitigation: 明确契约为“事件触发刷新”，overview/list/detail 是事实来源。

- [Risk] 不同业务模块传入的 `stageId/resourceType` 不一致。
  Mitigation: 增加集中映射枚举或工厂方法，避免各 service 手写字符串。

- [Risk] 上下文事件和业务数据更新不在同一事务会造成短暂不一致。
  Mitigation: 所有上下文事件通过 `TaskEventService` after-commit 发布。

- [Risk] 历史 `SBOM_ANALYSIS` 等 deprecated 任务仍会出现在事件流。
  Mitigation: 保持兼容，标注为 deprecated 历史 task type，不作为新流程入口。
