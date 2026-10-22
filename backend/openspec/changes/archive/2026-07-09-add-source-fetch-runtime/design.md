## Context

当前 `POST /api/projects/{projectId}/sources/git-sync` 已经完成输入校验、凭据保存、`source_imports` 创建、`SOURCE_GIT_SYNC` 任务创建和队列投递。缺口在 worker 侧：没有 handler 实际在后端本机执行 Git 获取源码，也没有把执行结果写回 `source_revisions`、`source_imports`、`tool_runs` 和任务日志。

用户已明确 MVP 约束：源码获取和后续检测都在后端本机执行，不通过 SSH 环境拉源码。SSH runtime 保持用于远程环境检查、采集和远程命令执行。

## Goals / Non-Goals

**Goals:**

- 实现 `SOURCE_GIT_SYNC` worker handler，在后端本机执行 Git clone/fetch/checkout。
- 成功后创建新的 `source_revisions` 记录，保存 Git URL、branch、commit 和本机工作副本路径。
- 成功后按请求 `activate` 切换当前源码版本，并更新项目阶段为 `SOURCE_IMPORTED`。
- 失败后更新 `source_imports.status/error_message`，任务失败，保留 `tool_runs`、stdout/stderr 日志和安全错误摘要。
- Git 凭据仅在 worker 执行期间解密，不进入任务输入、队列消息、API 响应、日志 excerpt 或审计详情。
- 单元测试和 API E2E 覆盖正常流程、异常流程和 edge case。

**Non-Goals:**

- 不实现远程 SSH 环境上的 Git clone/fetch。
- 不实现构建、扫描、recheck 或报告任务。
- 不实现 Git LFS、submodule 递归策略、浅克隆深度配置以外的高级 Git 策略。
- 不解析源码内容或做语言/依赖识别。

## Decisions

### 1. Git 同步在后端本机执行

`SOURCE_GIT_SYNC` handler 使用本机进程执行 Git 命令。源码工作目录由后端配置控制，建议新增 `RVPORT_SOURCE_DIR`，默认 `./runtime/sources`。

理由：

- 后续检测运行在后端本机，源码必须最终落在后端可访问路径。
- 避免 SSH 环境、跳板机、远程文件同步带来的额外状态和失败面。
- 当前 source 表已有 `working_copy_path` 字段，适合表达后端本机工作副本。

备选方案是远程环境 clone 后再同步回后端。该方案需要文件传输、权限和重试设计，超出当前 MVP。

### 2. 每次 Git 同步写入新的 source revision

Git 同步成功后创建新的 `source_revisions`，不覆盖旧记录。工作副本目录使用 `projectId/sourceRevisionId` 组织。若 `activate=true`，同一事务中清除项目其他 active revision 并启用新 revision。

理由：

- 保持“修复后重新入库”的可追溯性。
- 后续检测任务可以明确绑定一个不可变 source revision。

### 3. source_import 是导入过程状态事实来源

API 创建 `source_imports` 为 `PENDING`，任务创建后变为任务初始状态。worker 成功时更新为 `SUCCEEDED` 并绑定新 `source_revision_id`；失败时更新为 `FAILED` 并保存安全错误摘要。

理由：

- `tasks` 表表达长任务运行状态。
- `source_imports` 表表达源码入库业务状态。
- 两者需要通过 `task_id` 和 `source_import_id` 关联。

### 4. Git 凭据通过临时机制传入 Git，不写入 URL

后端继续拒绝 Git URL 携带用户名、密码或 token。worker 解密 Git 凭据后，通过临时 credential helper、临时 askpass 脚本或等效安全机制传给 Git 命令。日志和 `tool_runs.summary` 只保存脱敏 URL、branch、commit、exit code 和耗时。

约束：

- 不把 token/password 拼进 `gitUrl`。
- 不把明文凭据写入任务输入、队列消息、stdout/stderr excerpt、审计详情。
- 临时凭据文件必须位于受控临时目录，并在成功、失败、超时后删除。

### 5. Git 执行适配层可测试

新增 `GitClientAdapter`，生产实现使用 `ProcessBuilder` 调用本机 `git`。业务 handler 依赖接口，单元测试用 fake adapter，不依赖真实网络仓库。

理由：

- 普通 `mvn test` 不应依赖外网、真实 Git 服务或真实凭据。
- E2E 脚本可单独使用本地 bare repository 或明确配置的测试仓库做端到端验证。

## Risks / Trade-offs

- Git 命令不存在 → 启动或任务执行时返回明确失败；测试覆盖缺失 Git 的错误路径。
- 仓库很大导致任务长时间运行 → 使用任务输入 `timeoutSeconds` 或默认超时控制进程，超时后销毁进程并标记失败。
- 凭据泄漏到进程参数或日志 → 不拼接 URL，不打印环境变量，日志 excerpt 经过脱敏；临时 helper/askpass 文件执行后删除。
- 工作副本目录残留半成品 → clone 到临时目录，成功后原子移动到 revision 目录；失败时清理临时目录。
- 并发同步同一项目 → revisionId 目录天然隔离；active 切换在事务中完成。

## Migration Plan

- 无数据库 schema 迁移要求，现有 `source_revisions`、`source_imports`、`tasks`、`tool_runs` 可承载本 change。
- 需要新增运行时配置项，默认值保证本地开发无需额外配置。
- 回滚时停止 worker 即可阻止新 Git 同步执行；已创建的 source revisions/imports 保留为历史记录。
