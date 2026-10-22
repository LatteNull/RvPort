## ADDED Requirements

### Requirement: 项目 API 必须提供工作台根实体管理
后端 SHALL 提供项目列表、创建、详情、基础信息更新和概览 API，并 SHALL 使用 `projects` 表作为项目根实体事实来源。

#### Scenario: 创建项目
- **WHEN** 已登录用户调用 `POST /api/projects` 并提交项目名称、描述、源架构和目标架构
- **THEN** 后端 SHALL 创建 `projects` 记录
- **AND** 默认 `stage` SHALL 为 `PROJECT_CREATED`
- **AND** 默认 `status` SHALL 为 `ACTIVE`
- **AND** `created_by` SHALL 使用当前登录用户 ID

#### Scenario: 查询项目列表
- **WHEN** 已登录用户调用 `GET /api/projects`
- **THEN** 后端 SHALL 返回未软删除项目的分页列表
- **AND** 列表 SHALL 支持按 `status`、`stage` 和关键字筛选

#### Scenario: 更新项目基础信息
- **WHEN** 已登录用户调用 `PATCH /api/projects/{projectId}`
- **THEN** 后端 SHALL 只允许更新项目名称、描述、源架构、目标架构和项目状态
- **AND** 后端 MUST NOT 通过该接口把 `stage` 当作任意可写状态机字段

#### Scenario: 读取项目概览
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/overview`
- **THEN** 后端 SHALL 返回项目基本信息、当前启用源码版本、源码版本数量、环境摘要、最近任务摘要和推荐下一步动作
- **AND** 概览 SHALL 从源码版本、环境和任务等事实数据聚合当前状态
- **AND** 概览 MUST NOT 只依赖 `projects.stage` 表达项目真实状态

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
- **AND** 任务输入快照 MUST NOT 包含明文凭据

#### Scenario: 切换当前源码版本
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/sources/{sourceRevisionId}/activate`
- **THEN** 后端 SHALL 验证源码版本属于该项目
- **AND** 后端 SHALL 在同一事务中取消同项目其他源码版本的启用状态，并启用目标源码版本

### Requirement: 环境 API 必须管理 SSH 执行环境
后端 SHALL 提供 SSH 环境列表、创建、详情、更新、禁用和快照列表 API，并 SHALL 使用 `environments` 表作为环境配置事实来源。

#### Scenario: 创建 SSH 环境
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/environments`
- **THEN** 后端 SHALL 创建 `environments` 记录
- **AND** `role` SHALL 限定为 `SOURCE_X86`、`TARGET_RISCV` 或 `GENERAL_EXECUTION`
- **AND** `sshPort` SHALL 限定在 1 到 65535
- **AND** 默认 `status` SHALL 为 `UNKNOWN`
- **AND** 默认 `enabled` SHALL 为 `true`

#### Scenario: 创建使用跳板机的 SSH 环境
- **WHEN** 已登录用户创建环境并提交 `jumpHostEnvironmentId`
- **THEN** 后端 SHALL 验证跳板机环境存在且属于同一项目
- **AND** 后端 SHALL 验证跳板机环境已启用
- **AND** 后端 SHALL 保存该跳板机引用
- **AND** 后端 MUST NOT 允许环境引用自己作为跳板机
- **AND** 后端 MUST NOT 允许多级跳板链路

#### Scenario: 查询环境列表
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/environments`
- **THEN** 后端 SHALL 返回该项目环境列表
- **AND** 列表 SHALL 支持按环境角色和启用状态筛选
- **AND** 响应 SHALL 包含凭据遮蔽摘要
- **AND** 响应 SHALL 包含已配置跳板机的非敏感摘要

#### Scenario: 更新环境
- **WHEN** 已登录用户调用 `PATCH /api/environments/{environmentId}`
- **THEN** 后端 SHALL 允许更新名称、角色、架构、主机、端口、用户名、工作目录、启用状态、跳板机引用和凭据
- **AND** 当环境被禁用时，后端 SHALL 将 `enabled` 设置为 `false`
- **AND** 被禁用环境 MUST NOT 用于新的连接测试、环境采集或远程脚本任务

#### Scenario: 更新环境跳板机
- **WHEN** 已登录用户更新环境并设置 `jumpHostEnvironmentId`
- **THEN** 后端 SHALL 验证跳板机环境属于同一项目且已启用
- **AND** 后端 MUST NOT 允许自引用
- **AND** 后端 MUST NOT 允许多级跳板链路

#### Scenario: 禁用被引用的跳板机
- **WHEN** 已登录用户禁用一个已被其他环境引用的跳板机环境
- **THEN** 后端 SHALL 拒绝禁用并返回明确错误
- **AND** 后端 MUST NOT 让已有环境保留指向禁用跳板机的有效配置

#### Scenario: 查询环境快照
- **WHEN** 已登录用户调用 `GET /api/environments/{environmentId}/snapshots`
- **THEN** 后端 SHALL 返回该环境的快照分页列表
- **AND** 响应 SHALL 按采集时间倒序排列

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

#### Scenario: 凭据加密密钥缺失
- **WHEN** 请求需要保存业务凭据但 `RVPORT_CREDENTIAL_MASTER_KEY` 未配置或无效
- **THEN** 后端 SHALL 拒绝请求并返回明确错误
- **AND** 后端 MUST NOT 保存明文凭据

### Requirement: 环境长操作必须通过任务运行时投递
后端 SHALL 将环境连接测试、环境采集和远程脚本执行建模为长任务，并 SHALL 复用已有 PostgreSQL 任务模型、RabbitMQ 投递和项目级 SSE。

#### Scenario: 创建环境连接测试任务
- **WHEN** 已登录用户调用 `POST /api/environments/{environmentId}/test-connection`
- **THEN** 后端 SHALL 创建任务类型为 `ENV_TEST_CONNECTION` 的 `tasks` 记录
- **AND** 后端 SHALL 投递任务 ID 到 RabbitMQ
- **AND** 响应 SHALL 返回任务 ID 和初始任务状态
- **AND** 任务输入快照 MAY 包含 `jumpHostEnvironmentId`
- **AND** 任务输入快照 MUST NOT 包含目标环境或跳板机的明文凭据

#### Scenario: 创建环境采集任务
- **WHEN** 已登录用户调用 `POST /api/environments/{environmentId}/collect`
- **THEN** 后端 SHALL 创建任务类型为 `ENV_COLLECT` 的 `tasks` 记录
- **AND** 任务输入快照 SHALL 引用环境 ID 和项目 ID
- **AND** 任务输入快照 MUST NOT 包含明文凭据

#### Scenario: 创建远程脚本任务
- **WHEN** 已登录用户调用 `POST /api/environments/{environmentId}/scripts`
- **THEN** 后端 SHALL 创建任务类型为 `ENV_RUN_SCRIPT` 的 `tasks` 记录
- **AND** 任务输入快照 MAY 包含脚本摘要、超时和工作目录
- **AND** 任务输入快照 MUST NOT 包含明文凭据

### Requirement: 项目源码环境操作必须写入审计日志
后端 SHALL 对项目、源码、环境和凭据相关的敏感操作写入审计日志，并 SHALL 对审计详情做脱敏处理。

#### Scenario: 记录项目变更审计
- **WHEN** 用户创建或更新项目
- **THEN** 后端 SHALL 写入审计日志
- **AND** 审计日志 SHALL 包含用户 ID、动作、资源类型、资源 ID 和安全详情

#### Scenario: 记录凭据相关审计
- **WHEN** 用户创建或替换 Git/SSH 凭据
- **THEN** 后端 SHALL 写入审计日志
- **AND** 审计详情 MUST NOT 包含明文密码、私钥、token、passphrase 或加密密文

### Requirement: 单元测试必须覆盖正常异常和边界路径
项目、源码、环境和凭据相关实现 SHALL 配套单元测试或轻量集成测试，并 SHALL 覆盖正常流程、异常流程和 edge case。

#### Scenario: 覆盖正常流程
- **WHEN** 为项目、源码、环境、凭据和任务投递能力编写测试
- **THEN** 测试 SHALL 覆盖合法输入下的创建、查询、更新、启用、任务创建和队列投递行为

#### Scenario: 覆盖异常流程
- **WHEN** 为项目、源码、环境、凭据和任务投递能力编写测试
- **THEN** 测试 SHALL 覆盖未登录、资源不存在、状态不允许、Git URL 携带凭据、凭据密钥无效和禁用环境创建任务等错误路径

#### Scenario: 覆盖 edge case
- **WHEN** 为项目、源码、环境、凭据和任务投递能力编写测试
- **THEN** 测试 SHALL 覆盖空列表、可选字段为空、重复源码上传、active 源码切换、跳板机自引用、多级跳板、跨项目跳板、分页边界和 SSH 端口边界
