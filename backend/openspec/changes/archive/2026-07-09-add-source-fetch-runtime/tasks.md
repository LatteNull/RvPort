## 1. 配置与边界确认

- [x] 1.1 新增后端本机源码 runtime 目录配置，默认使用 `./runtime/sources`，并支持通过环境变量覆盖。
- [x] 1.2 确认 `SOURCE_GIT_SYNC` 只在后端本机执行 Git，不使用 SSH 环境或跳板机。
- [x] 1.3 确认 Git URL 继续禁止携带用户名、密码或 token。
- [x] 1.4 确认普通 `mvn test` 不依赖真实 Git 服务、外网、Docker Compose 或真实凭据。

## 2. Git 凭据运行时读取

- [x] 2.1 为 `CredentialService` 增加类型化 Git 凭据运行时读取方法，复用 active/project 校验。
- [x] 2.2 支持 `GIT_TOKEN` payload 解密并映射为运行时 token 凭据。
- [x] 2.3 支持 `GIT_PASSWORD` payload 解密并映射为运行时用户名密码凭据。
- [x] 2.4 处理凭据不存在、项目不匹配、类型不匹配、payload 格式非法和解密失败。
- [x] 2.5 补充 Git 凭据运行时解密测试，断言 API 响应、任务输入、日志和错误摘要不包含明文密码、token 或密文。

## 3. Git 执行适配层

- [x] 3.1 定义 `GitClientAdapter` 接口，支持 clone/fetch/checkout 和读取实际 commit。
- [x] 3.2 基于 `ProcessBuilder` 实现本机 Git 执行适配器。
- [x] 3.3 实现命令超时控制，超时后销毁 Git 进程并返回安全错误。
- [x] 3.4 实现临时 credential helper、askpass 或等效机制，避免把 token/password 拼接到 Git URL 或命令参数。
- [x] 3.5 确保临时凭据文件在成功、失败和超时后删除。
- [x] 3.6 将 Git stdout/stderr 和异常转换为安全结果，不暴露 token、密码、密文或临时文件路径。
- [x] 3.7 为适配层增加 fake/mock 友好测试，普通单元测试不执行真实 Git 网络操作。

## 4. Source Runtime 与工作副本管理

- [x] 4.1 新增 `SourceFetchRuntimeService`，按任务输入读取 source import、Git URL、branch、commit、credentialId 和 activate 标记。
- [x] 4.2 为每次 Git 同步生成新的 sourceRevisionId，并使用 `projectId/sourceRevisionId` 作为最终工作副本目录。
- [x] 4.3 clone/fetch 先写入临时目录，成功后移动到最终工作副本目录。
- [x] 4.4 checkout 指定 commit 时固定到该 commit；未指定 commit 时使用指定 branch 或远端默认分支。
- [x] 4.5 成功后读取实际 checkout commit。
- [x] 4.6 失败时清理该次任务创建的临时目录，不删除其他源码版本目录。
- [x] 4.7 确认工作副本路径只保存到内部字段，不通过 API 响应返回。

## 5. Source Import 与 Source Revision 状态更新

- [x] 5.1 为 `SourceRepository` 增加创建 Git source revision 的方法。
- [x] 5.2 为 `SourceRepository` 增加 source import 成功更新方法，绑定 `source_revision_id` 并设置 `SUCCEEDED`。
- [x] 5.3 为 `SourceRepository` 增加 source import 失败更新方法，设置 `FAILED` 和安全 `error_message`。
- [x] 5.4 成功且 `activate=true` 时清除同项目其他 active revision 并启用新 revision。
- [x] 5.5 成功后更新项目阶段为 `SOURCE_IMPORTED`。
- [x] 5.6 失败时不创建成功态 source revision，不改变当前 active source revision。

## 6. Worker Handler 与执行记录

- [x] 6.1 新增 `SourceGitSyncHandler` 并注册任务类型 `SOURCE_GIT_SYNC`。
- [x] 6.2 handler 通过 `TaskExecutionContext` 解析安全输入快照。
- [x] 6.3 handler 调用 source runtime 执行 Git 同步，成功后返回安全成功消息。
- [x] 6.4 handler 异常路径交给 worker 标记 `FAILED`，并保留安全错误码和安全摘要。
- [x] 6.5 为 Git 同步写入 `tool_runs`，保存脱敏 Git URL、branch、commit、exit code、耗时和工作副本摘要。
- [x] 6.6 使用任务执行上下文写入进度、stdout/stderr 日志摘要和安全失败摘要。
- [x] 6.7 确认队列消息仍只包含任务 ID 等路由信息，任务输入快照不包含明文凭据。

## 7. API 与 E2E 脚本

- [x] 7.1 确认 `POST /api/projects/{projectId}/sources/git-sync` 任务输入包含 `sourceImportId`、脱敏 Git URL、branch、commit、credentialId、versionLabel、versionNote 和 activate。
- [x] 7.2 确认 Git token/password 创建请求只保存加密凭据，不在响应中返回明文。
- [x] 7.3 更新 API E2E 测试脚本，使用本地 bare repository 或可配置测试仓库验证 Git 同步端到端流程。
- [x] 7.4 E2E 验证成功后通过 API 查询源码列表，确认新 Git revision 出现且不返回本机路径。
- [x] 7.5 E2E 验证任务日志、tool run summary 和 API 响应不包含 token/password。
- [x] 7.6 E2E 运行完成后清理测试数据和本地临时源码目录，避免脏数据。

## 8. 测试与验证

- [x] 8.1 为 Git runtime 补充正常流程测试：公开仓库同步、token 凭据同步、指定 branch、指定 commit、创建 revision、更新 import、activate 和 tool run。
- [x] 8.2 为 Git runtime 补充异常流程测试：Git 命令不存在、认证失败、仓库不存在、checkout commit 不存在、凭据不存在、凭据项目不匹配、凭据类型不匹配、凭据解密失败和进程超时。
- [x] 8.3 为 Git runtime 补充 edge case 测试：重复同步同一仓库、并发同步同一项目、空 branch 使用默认分支、失败清理临时目录、失败不改变 active source、日志脱敏和任务输入脱敏。
- [x] 8.4 为 `SourceGitSyncHandler` 补充 handler 成功和失败测试。
- [x] 8.5 更新 `SourceServiceTests`，覆盖任务输入脱敏、credentialId 引用、新建凭据和 Git URL 拒绝策略。
- [x] 8.6 更新 repository 测试或使用 mock 验证 source import/revision 状态更新行为。
- [x] 8.7 运行受影响测试类。
- [x] 8.8 运行完整 `mvn test`。
- [x] 8.9 如本机有 Git 可用，运行 API E2E 脚本并记录实际任务、source revision 和日志脱敏结果。
