## Context

后端已经具备项目、源码版本、环境、SSH runtime、任务运行时、运行中任务取消、项目级 SSE、源码获取和源码部署能力。`build_runs` 表在初始 schema 中已存在，但当前还没有构建验证 API 和 worker handler。

构建验证应发生在远端环境中，并且后续流程通常需要同时验证 x86 原始环境和 RISC-V 目标环境。源码传输已经由 `SOURCE_DEPLOY` 完成，因此构建验证不应重新接受前端传入的远端路径，也不应隐式执行源码部署。

## Goals / Non-Goals

**Goals:**
- 提供构建验证 API，基于成功的 `source_deploy_runs` 创建一个或多个构建任务。
- 在远端源码部署目录执行用户提交的构建脚本，并写入构建运行状态、退出码、失败分类、日志和时间字段。
- 通过已有任务事件、任务日志和项目级 SSE 支持实时进度与历史日志查看。
- 支持 x86 和 RISC-V 环境分别构建，同一请求可创建多条独立构建记录。
- 复用现有运行中任务取消能力终止远端构建命令。
- 为分页、排序、过滤和 E2E 模块化测试建立清晰契约。

**Non-Goals:**
- 不实现自动化测试运行节点；测试运行由后续 `test_runs` 能力处理。
- 不解析构建系统类型，不自动生成 CMake、Make、Maven 或其他构建命令。
- 不解析编译错误结构化明细；MVP 只保存退出码、失败分类、摘要和日志引用。
- 不在构建 API 中隐式触发源码部署或覆盖远端源码目录。
- 不修改前端。

## Decisions

### 1. 构建输入引用 `sourceDeploymentIds`

`POST /api/projects/{projectId}/builds` 使用 `sourceDeploymentIds` 作为远端源码输入。后端校验每条源码部署记录必须：
- 属于 URL 中的 `projectId`
- 状态为 `SUCCEEDED`
- 绑定同一个 `sourceRevisionId`
- 关联的环境仍启用

理由：远端路径由后端生成并写入 `source_deploy_runs.remote_path`，构建验证只消费这个事实。这样避免前端传任意路径，也能明确“部署完成后才能构建”的流程边界。

替代方案是继续接收 `environmentId + workingDirectory`。这个方案会重复引入路径校验和源码目录一致性问题，不适合作为构建事实来源。

### 2. 一条部署记录对应一条构建运行

同一个创建请求可以提交多个 `sourceDeploymentIds`，后端为每个部署记录创建一条 `build_runs` 和一个 `BUILD_VALIDATION` 任务。x86 和 RISC-V 构建互不阻塞，各自拥有独立状态、退出码和日志。

理由：原始环境构建失败与目标环境构建失败语义不同，必须分别展示和审计。批量创建只是 API 便利，不改变任务隔离。

### 3. 构建脚本复用 `task_script_payloads`

构建脚本不直接写入 `tasks.input_snapshot` 或 `build_runs.command`。API 创建任务时将脚本加密保存到 `task_script_payloads`，并在 `build_runs.command` 保存脱敏摘要，例如首行命令或 `sha256:<hash>`。

理由：构建脚本可能包含仓库路径、参数、环境变量或内部地址。复用已有脚本密文表可以保持与 `CUSTOM_BASH` 一致的加密和长度约束。

### 4. Worker 上传临时脚本后执行

`BUILD_VALIDATION` handler 读取源码部署目录后，在远端创建临时脚本文件，写入脚本内容，执行：

```bash
cd "<source_deploy_runs.remote_path>" && bash "<temporary_script>"
```

执行结束、失败或取消时，worker 尝试删除远端临时脚本。

理由：直接把脚本拼进 SSH 命令会受到引号、换行、特殊字符和 stdin 消耗影响。上传脚本后执行更稳定，也与之前 `CUSTOM_BASH` 的问题处理方向一致。

### 5. 状态和日志以任务运行时为主线

worker 推进顺序：
1. 认领任务后将 `build_runs.status` 标记为 `RUNNING`，写 `started_at`。
2. 追加任务进度事件和日志事件。
3. 将远端 stdout/stderr 写入任务日志体系。
4. 根据退出码写入 `SUCCEEDED` 或 `FAILED`。
5. 同步 `build_runs.exit_code`、`failure_category`、`stdout_log_id`、`stderr_log_id`、`finished_at`。

项目级 SSE 继续使用 `task_events.id`，不新增任务级 SSE。

### 6. 失败分类保持轻量

MVP 使用有限分类：
- `SSH_CONNECTION_FAILED`
- `REMOTE_COMMAND_FAILED`
- `BUILD_COMMAND_FAILED`
- `SOURCE_DEPLOYMENT_NOT_READY`
- `BUILD_CANCELLED`
- `BUILD_TIMEOUT`
- `UNKNOWN`

分类用于列表筛选和报告摘要，不替代完整日志。

### 7. 查询接口统一分页、排序和过滤

`GET /api/projects/{projectId}/builds` 支持：
- 过滤：`sourceRevisionId`、`environmentId`、`status`、`createdFrom`、`createdTo`
- 排序：`createdAt`、`startedAt`、`finishedAt`、`status`、`environmentId`
- 分页：沿用现有 page/pageSize 模型

所有详情和列表都执行项目访问守卫。无权限时返回与资源不存在一致的错误。

## Risks / Trade-offs

- [Risk] 构建脚本可能长时间运行或卡住 → 使用 `timeoutSeconds`，并接入运行中任务取消。
- [Risk] 远端临时脚本删除失败 → 记录警告日志和任务事件，但不覆盖构建主结果。
- [Risk] 同一源码部署被重复构建造成资源压力 → MVP 允许显式多次构建，后续可增加复用或并发限制。
- [Risk] 构建命令中包含敏感信息 → `build_runs.command` 只保存脱敏摘要，完整脚本走加密 payload。
- [Risk] x86 和 RISC-V 任一环境不可达 → 每个环境独立失败，不影响其他环境构建记录写回。

## Migration Plan

1. 增加 Liquibase 变更，扩展 `build_runs` 的 `source_deploy_run_id`、脚本摘要字段和必要索引。
2. 运行 Liquibase 后重新生成 jOOQ 代码，生成文件提交到 `src/generated/java`。
3. 增加构建验证 service、repository、controller、DTO 和 worker handler。
4. 增加单元测试，覆盖正常流程、异常流程和 edge case。
5. 增加 E2E 模块，用已成功源码部署记录触发真实构建验证。
6. 验证默认构建、测试支持构建和 E2E 模块均可运行。

回滚时移除新增 API 和 worker handler；数据库新增字段可保留为空，不影响已有功能。

## Open Questions

- 构建脚本最大长度是否沿用 `task_script_payloads` 当前 12000 字符上限，还是需要为构建场景单独放宽。
- 是否需要在后续阶段增加构建产物归档到对象存储。
