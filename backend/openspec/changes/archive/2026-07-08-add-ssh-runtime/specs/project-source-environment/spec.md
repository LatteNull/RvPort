## ADDED Requirements

### Requirement: SSH runtime 必须真实执行环境连接测试
后端 SHALL 提供 SSH runtime，用于 worker 根据环境配置真实建立 SSH 连接并执行统一的轻量探测命令。

#### Scenario: 每次命令使用短生命周期 SSH session
- **WHEN** SSH runtime 执行连接测试或后续远程命令
- **THEN** SSH runtime SHALL 为该次命令建立 SSH session
- **AND** 命令完成、失败或超时后 SHALL 关闭该 SSH session
- **AND** SSH runtime MUST NOT 跨任务或跨命令复用长期空闲 SSH session

#### Scenario: 直连环境连接测试成功
- **WHEN** worker 执行 `ENV_TEST_CONNECTION` 任务且目标环境未配置跳板机
- **THEN** SSH runtime SHALL 使用目标环境的主机、端口、用户名和凭据建立 SSH 连接
- **AND** SHALL 执行统一的轻量探测命令验证远程命令执行能力
- **AND** 任务 SHALL 写入进度事件和安全日志摘要
- **AND** 环境状态 SHALL 更新为可连接状态

#### Scenario: 连接测试执行统一探测命令
- **WHEN** SSH runtime 执行 `ENV_TEST_CONNECTION`
- **THEN** SSH runtime SHALL 运行无需 sudo 且无写入副作用的 POSIX shell 兼容探测脚本
- **AND** 探测脚本 SHALL 输出 `RVPORT_PROBE=ok`
- **AND** 探测脚本 SHALL 检查 kernel name、kernel version、machine arch、远程执行用户、远程命令执行能力、工作目录可用性和基础工具存在性
- **AND** 基础工具存在性 SHALL 至少覆盖 `sh`、`bash`、`git`、`gcc`、`g++`、`make`、`cmake`、`python3`、`java`、`mvn`
- **AND** 探测脚本 MUST NOT 读取项目目录、源码目录、用户 home 敏感文件或输出服务器真实路径

#### Scenario: 连接测试保存执行记录
- **WHEN** `ENV_TEST_CONNECTION` 探测命令成功且输出包含 `RVPORT_PROBE=ok`
- **THEN** 后端 SHALL 写入一条 `tool_runs` 执行记录
- **AND** `tool_runs.tool_name` SHALL 为稳定的连接探测工具名
- **AND** `tool_runs.exit_code` SHALL 保存远程命令退出码
- **AND** `tool_runs.summary` SHALL 保存探测命令版本、kernel、arch、远程用户、工作目录检查结果、基础工具存在性和解析警告
- **AND** 后端 SHALL 通过 `task_logs` 保存 stdout/stderr 日志文件元数据和安全 excerpt
- **AND** 后端 SHALL 更新 `environments.status` 和 `last_connected_at`
- **AND** 连接测试 MUST NOT 写入 `environment_snapshots` 或 `environment_components`
- **AND** 连接测试 MUST NOT 更新 `last_collected_at`

#### Scenario: 跳板机环境连接测试成功
- **WHEN** worker 执行 `ENV_TEST_CONNECTION` 任务且目标环境配置 `jumpHostEnvironmentId`
- **THEN** SSH runtime SHALL 先连接跳板机环境
- **AND** SHALL 通过该跳板机连接目标环境
- **AND** SHALL 使用跳板机和目标环境各自绑定的 SSH 凭据
- **AND** 当前命令完成、失败或超时后 SHALL 关闭目标 session 和跳板机 session
- **AND** 任务日志和事件 MUST NOT 包含跳板机或目标环境的明文凭据

#### Scenario: 连接测试失败
- **WHEN** SSH 连接、认证或探测命令执行失败
- **THEN** worker SHALL 将任务标记为 `FAILED`
- **AND** 任务错误摘要 SHALL 使用安全错误消息
- **AND** 环境状态 SHALL 更新为不可连接或未知状态
- **AND** 错误摘要 MUST NOT 包含密码、私钥、passphrase、token、加密密文或服务器真实路径

#### Scenario: 探测输出无法识别
- **WHEN** SSH 连接成功但探测输出不包含 `RVPORT_PROBE=ok` 或无法按 `KEY=VALUE` 解析
- **THEN** worker SHALL 将连接测试任务标记为 `FAILED`
- **AND** 任务错误摘要 SHALL 表示探测输出无效
- **AND** 后端 MUST NOT 保存不可信的环境快照

### Requirement: SSH runtime 必须统一环境采集和脚本执行记录语义
后端 SHALL 通过统一 Env Runner/SSH runtime 模型支撑环境检查、环境信息采集和远程脚本执行，并 SHALL 统一保存执行记录、日志和结构化结果。

#### Scenario: 环境检查保存检查结果
- **WHEN** worker 执行 `ENV_RUN_SCRIPT` 且 `scriptType` 为 `ENV_CHECK`
- **THEN** SSH runtime SHALL 根据输入检查项执行受控环境检查脚本
- **AND** 检查项 SHALL 支持 `CONNECTION`、`BASIC_TOOLS`、`WORKING_DIRECTORY`、`PERMISSIONS`
- **AND** 后端 SHALL 将每个检查项的结果写入 `tool_runs.summary.checkResults`
- **AND** 后端 SHALL 保存 stdout/stderr 到任务日志
- **AND** 环境检查 MUST NOT 写入 `environment_snapshots` 或 `environment_components`

#### Scenario: 环境采集保存环境快照
- **WHEN** worker 执行 `ENV_COLLECT`
- **THEN** SSH runtime SHALL 执行内置环境采集脚本
- **AND** 采集脚本 SHALL 采集 OS、kernel、arch、package manager、软件源摘要、已安装包摘要和基础工具版本
- **AND** 后端 SHALL 写入 `environment_snapshots` 记录
- **AND** `environment_snapshots.task_id` SHALL 指向当前任务
- **AND** `os_name`、`os_version`、`kernel_version`、`arch`、`package_manager` SHALL 来自采集输出
- **AND** `repo_summary` SHALL 保存软件源摘要 JSON
- **AND** `tool_versions` SHALL 保存基础工具版本 JSON
- **AND** `raw_snapshot` SHALL 保存标准化后的非敏感采集结果、脚本版本和解析警告
- **AND** 后端 MAY 写入 `environment_components` 保存系统包、库、工具和 native 文件摘要
- **AND** 后端 SHALL 更新 `environments.last_collected_at`

#### Scenario: 环境采集失败不覆盖上一轮成功结果
- **WHEN** `ENV_COLLECT` 连接、认证、脚本执行或解析失败
- **THEN** worker SHALL 将任务标记为 `FAILED`
- **AND** 后端 SHALL 保存执行记录、stdout/stderr 日志和安全失败摘要
- **AND** 后端 MUST NOT 覆盖上一轮成功的 `environment_snapshots`
- **AND** 后端 MUST NOT 更新 `last_collected_at`

#### Scenario: 远程脚本执行保存执行记录
- **WHEN** worker 执行 `ENV_RUN_SCRIPT`
- **THEN** 后端 SHALL 写入 `tool_runs` 执行记录
- **AND** `tool_runs.summary` SHALL 保存脚本类型、工作目录检查结果、执行用户、安全命令摘要和耗时
- **AND** `tool_runs.exit_code` SHALL 保存远程脚本退出码
- **AND** 后端 SHALL 通过 `task_logs` 保存 stdout/stderr
- **AND** 后端 SHALL 写入审计日志记录执行人、环境、脚本类型、开始时间、结束时间、状态和退出码
- **AND** 执行记录、日志摘要和审计详情 MUST NOT 包含明文凭据、私钥、passphrase、token 或未经脱敏的敏感脚本内容

#### Scenario: 连接测试超时
- **WHEN** SSH 连接或探测命令超过配置的超时时间
- **THEN** worker SHALL 将任务标记为 `FAILED`
- **AND** 任务错误摘要 SHALL 表示连接超时或命令超时
- **AND** SSH session 和跳板机 session SHALL 被关闭

#### Scenario: 单条长时间命令
- **WHEN** 后续任务通过 SSH runtime 执行单条长时间运行命令
- **THEN** SSH runtime SHALL 将该 SSH session 限定为服务当前命令
- **AND** SSH runtime SHALL 使用命令超时或任务超时控制最长运行时间
- **AND** SSH runtime MUST NOT 在命令完成后保留该 session 等待后续命令

### Requirement: SSH runtime 必须运行时解密并保护 SSH 凭据
后端 SHALL 只在 worker 执行期间解密 SSH 凭据，并 SHALL 避免明文凭据进入任务输入、队列消息、事件、日志、审计和 API 响应。

#### Scenario: 解密 SSH 密码凭据
- **WHEN** SSH runtime 需要使用 `SSH_PASSWORD` 凭据连接环境
- **THEN** 后端 SHALL 校验凭据存在、启用且属于当前项目
- **AND** SHALL 使用应用层凭据加密能力解密 `credentials.encrypted_payload`
- **AND** SHALL 将解密后的密码只传递给 SSH 客户端适配层

#### Scenario: 解密 SSH 私钥凭据
- **WHEN** SSH runtime 需要使用 `SSH_KEY` 凭据连接环境
- **THEN** 后端 SHALL 解密私钥和可选 passphrase
- **AND** SHALL 将解密后的私钥只传递给 SSH 客户端适配层
- **AND** 日志、事件和错误摘要 MUST NOT 包含私钥内容或 passphrase

#### Scenario: 凭据类型不匹配
- **WHEN** 环境绑定的凭据不是 `SSH_PASSWORD` 或 `SSH_KEY`
- **THEN** SSH runtime SHALL 拒绝执行连接
- **AND** 任务 SHALL 失败并写入安全错误摘要

#### Scenario: 凭据解密失败
- **WHEN** 凭据密文无法解密或加密主密钥无效
- **THEN** SSH runtime SHALL 拒绝执行连接
- **AND** 任务 SHALL 失败并写入安全错误摘要
- **AND** 错误摘要 MUST NOT 包含密文、主密钥或原始异常中的秘密内容

### Requirement: SSH runtime 必须配套测试覆盖
SSH runtime 相关实现 SHALL 配套单元测试或轻量集成测试，并 SHALL 覆盖正常流程、异常流程和 edge case。

#### Scenario: 覆盖正常流程
- **WHEN** 为 SSH runtime 编写测试
- **THEN** 测试 SHALL 覆盖密码直连、私钥直连、跳板机连接、统一探测输出解析、连接测试执行记录、环境检查结果保存、环境采集快照保存和 `ENV_TEST_CONNECTION` handler 成功路径

#### Scenario: 覆盖异常流程
- **WHEN** 为 SSH runtime 编写测试
- **THEN** 测试 SHALL 覆盖认证失败、连接超时、命令失败、探测输出无效、凭据不存在、凭据项目不匹配和凭据解密失败

#### Scenario: 覆盖 edge case
- **WHEN** 为 SSH runtime 编写测试
- **THEN** 测试 SHALL 覆盖 passphrase 为空、跳板机禁用、多级跳板防御、部分工具缺失、工作目录不存在、工作目录不可写、日志脱敏、每次命令关闭 session 和禁止跨命令复用 session

## MODIFIED Requirements

### Requirement: 环境长操作必须通过任务运行时投递
后端 SHALL 将环境连接测试、环境检查、环境采集和远程脚本执行建模为长任务，并 SHALL 复用已有 PostgreSQL 任务模型、RabbitMQ 投递、任务执行上下文和项目级 SSE。

#### Scenario: 创建环境连接测试任务
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/environments/{environmentId}/test-connection`
- **THEN** 后端 SHALL 创建任务类型为 `ENV_TEST_CONNECTION` 的 `tasks` 记录
- **AND** 后端 SHALL 校验环境存在且属于 URL 中的 `projectId`
- **AND** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 后端 SHALL 投递任务 ID 到 RabbitMQ
- **AND** 响应 SHALL 返回任务 ID 和初始任务状态
- **AND** 任务输入快照 MAY 包含 `jumpHostEnvironmentId`
- **AND** 任务输入快照 MAY 包含 `timeoutSeconds`
- **AND** 任务输入快照 MUST NOT 包含目标环境或跳板机的明文凭据

#### Scenario: 创建环境检查任务
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/environments/{environmentId}/check`
- **THEN** 后端 SHALL 创建任务类型为 `ENV_RUN_SCRIPT` 的 `tasks` 记录
- **AND** 后端 SHALL 校验环境存在且属于 URL 中的 `projectId`
- **AND** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 任务输入快照 SHALL 包含 `scriptType=ENV_CHECK`
- **AND** 任务输入快照 SHALL 包含 `checkItems`
- **AND** `checkItems` SHALL 只允许 `CONNECTION`、`BASIC_TOOLS`、`WORKING_DIRECTORY`、`PERMISSIONS`
- **AND** 任务输入快照 MAY 包含 `workingDirectory` 和 `timeoutSeconds`
- **AND** 后端 SHALL 投递任务 ID 到 RabbitMQ
- **AND** 响应 SHALL 返回任务 ID 和初始任务状态
- **AND** 任务输入快照 MUST NOT 包含明文凭据

#### Scenario: 执行环境连接测试任务
- **WHEN** worker 认领 `ENV_TEST_CONNECTION` 任务
- **THEN** worker SHALL 调用 SSH runtime 真实测试目标环境连接
- **AND** worker SHALL 通过任务执行上下文写入进度、日志摘要和终态事件
- **AND** worker SHALL 根据连接结果更新任务状态和环境连接状态
- **AND** 任务日志和事件 MUST NOT 包含明文凭据或服务器真实路径

#### Scenario: 创建环境采集任务
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/environments/{environmentId}/collect`
- **THEN** 后端 SHALL 创建任务类型为 `ENV_COLLECT` 的 `tasks` 记录
- **AND** 后端 SHALL 校验环境存在且属于 URL 中的 `projectId`
- **AND** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 任务输入快照 SHALL 引用环境 ID 和项目 ID
- **AND** 任务输入快照 MAY 包含 `collectScopes` 和 `timeoutSeconds`
- **AND** `collectScopes` 未传时 SHALL 使用默认采集范围
- **AND** 后端 SHALL 投递任务 ID 到 RabbitMQ
- **AND** 响应 SHALL 返回任务 ID 和初始任务状态
- **AND** 任务输入快照 MUST NOT 包含明文凭据

#### Scenario: 创建远程脚本任务
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/environments/{environmentId}/scripts`
- **THEN** 后端 SHALL 创建任务类型为 `ENV_RUN_SCRIPT` 的 `tasks` 记录
- **AND** 后端 SHALL 校验环境存在且属于 URL 中的 `projectId`
- **AND** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 任务输入快照 SHALL 包含 `scriptType`
- **AND** 任务输入快照 MAY 包含脚本摘要、脚本哈希、超时、工作目录和内置脚本参数
- **AND** 后端 SHALL 投递任务 ID 到 RabbitMQ
- **AND** 响应 SHALL 返回任务 ID 和初始任务状态
- **AND** 任务输入快照 MUST NOT 包含明文凭据
- **AND** 任务输入快照 MUST NOT 包含未经脱敏的敏感脚本内容

#### Scenario: 拒绝不支持的环境运行类型
- **WHEN** 已登录用户调用环境运行 API 并提交未知 `scriptType`、未知 `checkItems` 或非法 `collectScopes`
- **THEN** 后端 SHALL 拒绝请求并返回校验错误
- **AND** 后端 MUST NOT 创建任务
- **AND** 后端 MUST NOT 投递队列消息

#### Scenario: 拒绝跨项目环境运行请求
- **WHEN** 已登录用户调用项目作用域环境运行 API
- **AND** URL 中的 `environmentId` 不属于 URL 中的 `projectId`
- **THEN** 后端 SHALL 拒绝请求
- **AND** 后端 MUST NOT 创建任务
- **AND** 后端 MUST NOT 投递队列消息

#### Scenario: 拒绝无项目权限的环境运行请求
- **WHEN** 已登录用户调用项目作用域环境运行 API
- **AND** 当前用户无权访问 URL 中的 `projectId`
- **THEN** 后端 SHALL 拒绝请求
- **AND** 后端 MUST NOT 暴露该项目环境的连接信息或凭据摘要
- **AND** 后端 MUST NOT 创建任务
- **AND** 后端 MUST NOT 投递队列消息
