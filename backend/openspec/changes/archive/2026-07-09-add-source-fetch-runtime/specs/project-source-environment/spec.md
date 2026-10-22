## ADDED Requirements

### Requirement: Git 同步运行时必须在后端本机获取源码
后端 SHALL 提供 `SOURCE_GIT_SYNC` worker runtime，在后端本机执行 Git clone/fetch/checkout，并将源码工作副本保存到受配置控制的本地 runtime source 目录。

#### Scenario: Git 同步任务成功获取源码
- **WHEN** worker 认领 `SOURCE_GIT_SYNC` 任务
- **THEN** worker SHALL 从任务输入快照读取 `projectId`、`sourceImportId`、`gitUrl`、可选 `gitBranch`、可选 `gitCommit`、可选 `credentialId` 和 `activate`
- **AND** worker SHALL 在后端本机执行 Git 获取源码
- **AND** worker SHALL 将源码工作副本写入受配置控制的本地目录
- **AND** worker SHALL 获取实际 checkout commit
- **AND** worker SHALL 创建新的 `source_revisions` 记录，`revision_type` 为 `GIT`
- **AND** `source_revisions.working_copy_path` SHALL 保存后端本机工作副本路径
- **AND** `source_revisions.git_url`、`git_branch`、`git_commit` SHALL 保存脱敏后的 Git URL、目标分支和实际 commit
- **AND** worker SHALL 将对应 `source_imports` 更新为 `SUCCEEDED` 并绑定新 `source_revision_id`
- **AND** worker SHALL 将任务标记为 `SUCCEEDED`

#### Scenario: Git 同步按请求启用新源码版本
- **WHEN** `SOURCE_GIT_SYNC` 任务成功
- **AND** 任务输入快照中的 `activate` 为 `true`
- **THEN** 后端 SHALL 在同一事务中清除同项目其他源码版本的启用状态
- **AND** 后端 SHALL 将新创建的 Git 源码版本设为当前启用版本
- **AND** 后端 SHALL 将项目阶段更新为 `SOURCE_IMPORTED`

#### Scenario: Git 同步失败
- **WHEN** Git clone、fetch、checkout、凭据解密或文件系统写入失败
- **THEN** worker SHALL 将任务标记为 `FAILED`
- **AND** worker SHALL 将对应 `source_imports` 更新为 `FAILED`
- **AND** `source_imports.error_message` SHALL 保存安全错误摘要
- **AND** worker SHALL 保存 `tool_runs` 执行记录和 stdout/stderr 任务日志
- **AND** 后端 MUST NOT 创建成功态 `source_revisions`
- **AND** 后端 MUST NOT 改变当前 active source revision

#### Scenario: Git 同步保存执行记录
- **WHEN** worker 执行 `SOURCE_GIT_SYNC`
- **THEN** 后端 SHALL 写入一条 `tool_runs` 记录
- **AND** `tool_runs.tool_name` SHALL 使用稳定 Git runtime 工具名
- **AND** `tool_runs.exit_code` SHALL 保存 Git 进程退出码
- **AND** `tool_runs.summary` SHALL 保存脱敏 Git URL、branch、commit、工作副本摘要、耗时和解析警告
- **AND** 后端 SHALL 通过 `task_logs` 保存 stdout/stderr 日志文件元数据和安全 excerpt

#### Scenario: Git 同步清理失败工作目录
- **WHEN** Git 同步在 clone、fetch 或 checkout 过程中失败
- **THEN** worker SHALL 清理该次任务创建的临时工作目录
- **AND** worker MUST NOT 删除其他 source revision 的工作副本

### Requirement: Git 同步运行时必须保护 Git 凭据
后端 SHALL 只在 worker 执行期间解密 Git 凭据，并 SHALL 避免明文 Git 密码、token 或用户名密码组合进入任务输入、队列消息、日志、审计和 API 响应。

#### Scenario: 解密 Git token 凭据
- **WHEN** `SOURCE_GIT_SYNC` 任务输入包含 `credentialId`
- **AND** 凭据类型为 `GIT_TOKEN`
- **THEN** worker SHALL 校验凭据存在、启用且属于当前项目
- **AND** worker SHALL 解密 token
- **AND** worker SHALL 通过临时安全机制将 token 提供给 Git 进程
- **AND** token MUST NOT 出现在 Git URL、任务输入快照、队列消息、日志 excerpt、事件、审计详情或 `tool_runs.summary`

#### Scenario: 解密 Git 密码凭据
- **WHEN** `SOURCE_GIT_SYNC` 任务输入包含 `credentialId`
- **AND** 凭据类型为 `GIT_PASSWORD`
- **THEN** worker SHALL 校验凭据存在、启用且属于当前项目
- **AND** worker SHALL 解密用户名和密码
- **AND** worker SHALL 通过临时安全机制将用户名和密码提供给 Git 进程
- **AND** 明文用户名密码组合 MUST NOT 出现在 Git URL、任务输入快照、队列消息、日志 excerpt、事件、审计详情或 `tool_runs.summary`

#### Scenario: Git 凭据类型不匹配
- **WHEN** `SOURCE_GIT_SYNC` 任务引用的凭据不是 `GIT_PASSWORD` 或 `GIT_TOKEN`
- **THEN** worker SHALL 拒绝执行 Git 同步
- **AND** 任务 SHALL 失败并写入安全错误摘要
- **AND** 后端 MUST NOT 创建源码版本

#### Scenario: Git 凭据临时文件必须清理
- **WHEN** worker 为 Git 凭据创建临时 helper、askpass 或等效临时文件
- **THEN** worker SHALL 在任务成功、失败或超时后删除临时文件
- **AND** 临时文件路径 MUST NOT 写入 API 响应、审计详情或任务日志 excerpt

### Requirement: Git 同步运行时必须配套测试覆盖
Git 同步运行时 SHALL 配套单元测试和 API E2E 覆盖，并 SHALL 满足正常流程、异常流程和 edge case 测试策略。

#### Scenario: 覆盖正常流程
- **WHEN** 为 Git 同步运行时编写测试
- **THEN** 测试 SHALL 覆盖无凭据公开仓库同步、token 凭据同步、指定 branch、指定 commit、创建 source revision、更新 source import、按请求 activate 和写入 tool run

#### Scenario: 覆盖异常流程
- **WHEN** 为 Git 同步运行时编写测试
- **THEN** 测试 SHALL 覆盖 Git URL 无效、Git 命令不存在、认证失败、仓库不存在、checkout commit 不存在、凭据不存在、凭据项目不匹配、凭据类型不匹配和进程超时

#### Scenario: 覆盖 edge case
- **WHEN** 为 Git 同步运行时编写测试
- **THEN** 测试 SHALL 覆盖重复同步同一仓库、并发同步同一项目、空 branch 使用默认分支、失败清理临时目录、日志脱敏、任务输入不含明文凭据和 active revision 不被失败任务改变

## MODIFIED Requirements

### Requirement: 源码版本 API 必须支持修复后源码重新入库
后端 SHALL 提供源码版本列表、压缩包上传、Git 同步任务创建和当前源码版本切换 API，并 SHALL 通过新增 `source_revisions` 表记录表达每次源码入库。

#### Scenario: 查询源码版本列表
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/sources`
- **THEN** 后端 SHALL 返回该项目的源码版本分页列表
- **AND** 响应 SHALL 标记哪个源码版本是当前启用版本
- **AND** 响应 MUST NOT 返回 `archive_path` 或 `working_copy_path`

#### Scenario: 上传源码压缩包
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/sources/archive` 并上传源码压缩包
- **THEN** 后端 SHALL 将文件保存到 `RVPORT_UPLOAD_DIR` 管理的本地目录
- **AND** 后端 SHALL 创建新的 `source_revisions` 记录，`revision_type` 为 `ARCHIVE`
- **AND** 后端 SHALL 创建对应 `source_imports` 记录
- **AND** 如果请求要求启用该版本，后端 SHALL 将同项目其他源码版本置为非启用，并将新版本置为启用
- **AND** 响应 MUST NOT 返回服务器本地文件路径

#### Scenario: 修复后再次上传源码
- **WHEN** 同一项目已有当前源码版本并再次上传修复后的源码压缩包
- **THEN** 后端 SHALL 创建新的 `source_revisions` 记录
- **AND** 后端 MUST NOT 覆盖旧源码版本记录

#### Scenario: 创建 Git 同步任务
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/sources/git-sync`
- **THEN** 后端 SHALL 校验 Git URL 不包含用户名、密码或 token
- **AND** 后端 SHALL 创建 `source_imports` 记录
- **AND** 后端 SHALL 创建任务类型为 `SOURCE_GIT_SYNC` 的 `tasks` 记录并投递队列
- **AND** 队列载荷 SHALL 只包含任务 ID 等路由信息
- **AND** 任务输入快照 SHALL 包含 `sourceImportId`、脱敏 Git URL、可选 branch、可选 commit、可选 credentialId 和 activate 标记
- **AND** 任务输入快照 MUST NOT 包含明文凭据
- **AND** 任务输入快照 MUST NOT 包含带用户名、密码或 token 的 Git URL

#### Scenario: Git 同步成功后产生源码版本
- **WHEN** `SOURCE_GIT_SYNC` 任务成功完成
- **THEN** 后端 SHALL 创建新的 `source_revisions` 记录，`revision_type` 为 `GIT`
- **AND** 后端 SHALL 将对应 `source_imports` 更新为 `SUCCEEDED`
- **AND** 后端 SHALL 记录实际 checkout commit
- **AND** 后端 SHALL 保存后端本机工作副本路径作为内部字段
- **AND** API 响应 MUST NOT 返回服务器本机工作副本路径

#### Scenario: 切换当前源码版本
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/sources/{sourceRevisionId}/activate`
- **THEN** 后端 SHALL 验证源码版本属于该项目
- **AND** 后端 SHALL 在同一事务中取消同项目其他源码版本的启用状态，并启用目标源码版本

### Requirement: Git 和 SSH 凭据必须加密保存并遮蔽展示
后端 SHALL 使用应用层凭据加密能力保存 Git/SSH 业务凭据，并 SHALL 保证 API 响应、任务输入摘要、日志和审计详情不包含明文秘密。

#### Scenario: 保存 SSH 密码凭据
- **WHEN** 用户创建或更新 SSH 环境并提交密码
- **THEN** 后端 SHALL 将凭据 payload 加密后写入 `credentials.encrypted_payload`
- **AND** `credentials.kind` SHALL 为 `SSH_PASSWORD`
- **AND** 响应 SHALL 只返回配置状态、凭据类型、名称和遮蔽摘要

#### Scenario: 保存 SSH 私钥凭据
- **WHEN** 用户创建或更新 SSH 环境并提交私钥
- **THEN** 后端 SHALL 将私钥和可选 passphrase 加密保存
- **AND** `credentials.kind` SHALL 为 `SSH_KEY`
- **AND** 响应 MUST NOT 返回私钥、passphrase 或加密密文

#### Scenario: 保存 Git 凭据
- **WHEN** 用户创建 Git 同步请求并提交 Git 密码或 token
- **THEN** 后端 SHALL 将 Git 凭据加密保存或引用已有凭据
- **AND** `credentials.kind` SHALL 为 `GIT_PASSWORD` 或 `GIT_TOKEN`
- **AND** Git URL MUST NOT 保存用户名、密码或 token
- **AND** API 响应、任务输入快照、任务日志、事件和审计详情 MUST NOT 包含明文 Git 密码或 token

#### Scenario: 凭据加密密钥缺失
- **WHEN** 请求需要保存业务凭据但 `RVPORT_CREDENTIAL_MASTER_KEY` 未配置或无效
- **THEN** 后端 SHALL 拒绝请求并返回明确错误
- **AND** 后端 MUST NOT 保存明文凭据

#### Scenario: 运行时读取 Git 凭据
- **WHEN** worker 执行 `SOURCE_GIT_SYNC` 并需要 Git 凭据
- **THEN** 后端 SHALL 校验凭据存在、启用且属于当前项目
- **AND** 后端 SHALL 只在 worker 执行期间解密凭据
- **AND** 解密后的凭据 SHALL 只传递给 Git 执行适配层
- **AND** 后端 MUST NOT 持久化运行时明文凭据

### Requirement: 单元测试必须覆盖正常异常和边界路径
项目、源码、环境和凭据相关实现 SHALL 配套单元测试或轻量集成测试，并 SHALL 覆盖正常流程、异常流程和 edge case。

#### Scenario: 覆盖正常流程
- **WHEN** 为项目、源码、环境、凭据和任务投递能力编写测试
- **THEN** 测试 SHALL 覆盖合法输入下的创建、查询、更新、启用、任务创建和队列投递行为
- **AND** 测试 SHALL 覆盖 Git 同步成功创建源码版本、更新导入状态和写入执行记录

#### Scenario: 覆盖异常流程
- **WHEN** 为项目、源码、环境、凭据和任务投递能力编写测试
- **THEN** 测试 SHALL 覆盖未登录、资源不存在、状态不允许、Git URL 携带凭据、凭据密钥无效和禁用环境创建任务等错误路径
- **AND** 测试 SHALL 覆盖 Git 同步认证失败、仓库不存在、checkout 失败、凭据解密失败和进程超时

#### Scenario: 覆盖 edge case
- **WHEN** 为项目、源码、环境、凭据和任务投递能力编写测试
- **THEN** 测试 SHALL 覆盖空列表、可选字段为空、重复源码上传、active 源码切换、跳板机自引用、多级跳板、跨项目跳板、分页边界和 SSH 端口边界
- **AND** 测试 SHALL 覆盖重复 Git 同步、失败不改变 active source、临时目录清理、任务输入脱敏和日志脱敏
