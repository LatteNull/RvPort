## 1. 依赖与边界确认

- [x] 1.1 加入 Apache MINA SSHD 客户端依赖，确认其支持密码、私钥、passphrase，并通过一层跳板机支持目标环境执行。
- [x] 1.2 新增 SSH runtime 包结构，隔离 SSH 客户端适配层、连接请求模型、执行结果和异常模型。
- [x] 1.3 确认本 change 不修改数据库 schema、不实现 Git clone、构建命令或测试命令。

## 2. 凭据运行时解密

- [x] 2.1 为 `CredentialService` 增加类型化 SSH 凭据运行时读取方法，复用 active/project 校验。
- [x] 2.2 支持 `SSH_PASSWORD` payload 解密并映射为运行时密码凭据。
- [x] 2.3 支持 `SSH_KEY` payload 解密并映射为运行时私钥凭据和可选 passphrase。
- [x] 2.4 处理凭据不存在、项目不匹配、类型不匹配、payload 格式非法和解密失败。
- [x] 2.5 补充凭据运行时解密测试，断言 API 响应、任务输入、日志和错误摘要不包含明文秘密或密文。

## 3. SSH 客户端适配层

- [x] 3.1 定义 `SshClientAdapter` 接口，支持直连执行命令和一层跳板机执行命令。
- [x] 3.2 基于 Apache MINA SSHD 实现 SSH 客户端适配器，支持密码认证、私钥认证和可选 passphrase。
- [x] 3.3 实现“每次命令一个短生命周期 SSH session”的执行模型，不做连接池、不跨命令或跨任务复用长期 SSH session。
- [x] 3.4 实现连接超时、命令超时和 session 关闭策略，确保成功、失败和超时都关闭目标与跳板机 session。
- [x] 3.5 将底层 SSH 异常转换为安全的 runtime 异常，不暴露密码、私钥、passphrase、token、密文或服务器真实路径。
- [x] 3.6 为适配层增加 fake/mock 友好的测试，普通 `mvn test` 不依赖真实 SSH 服务。

## 4. SSH Runtime 与 Env Runner 语义

- [x] 4.1 新增 `SshRuntimeService`，按 environmentId 读取目标环境、跳板机环境和各自凭据。
- [x] 4.2 定义统一连接探测脚本，输出 `RVPORT_PROBE=ok`、kernel、arch、远程用户、工作目录检查结果和基础工具存在性。
- [x] 4.3 实现探测输出解析器，将 `KEY=VALUE` 输出映射为连接检查结果摘要。
- [x] 4.4 直连场景下构造目标连接请求并执行统一连接探测脚本。
- [x] 4.5 跳板机场景下构造跳板机连接请求和目标连接请求，并通过适配层执行统一连接探测脚本。
- [x] 4.6 防御性校验禁用环境、多级跳板、凭据类型不匹配和凭据项目不匹配。
- [x] 4.7 根据连接结果更新环境状态为可连接或不可连接状态，并成功时更新 `last_connected_at`。
- [x] 4.8 为所有远程执行写入 `tool_runs` 执行记录，保存安全 command summary、exit code、started/finished 和结构化 summary。
- [x] 4.9 使用任务执行上下文写入连接进度、stdout/stderr 日志摘要和安全失败摘要。
- [x] 4.10 确认连接测试不写入 `environment_snapshots`、不更新 `last_collected_at`。

## 5. 环境检查、采集和脚本执行结果

- [x] 5.1 定义 `ENV_RUN_SCRIPT` 的内置 `ENV_CHECK` 脚本语义，支持 `CONNECTION`、`BASIC_TOOLS`、`WORKING_DIRECTORY`、`PERMISSIONS` 检查项。
- [x] 5.2 将环境检查结果写入 `tool_runs.summary.checkResults`，不写入 `environment_snapshots` 或 `environment_components`。
- [x] 5.3 定义 `ENV_COLLECT` 内置采集脚本语义，覆盖 OS、kernel、arch、package manager、软件源摘要、已安装包摘要和基础工具版本。
- [x] 5.4 实现环境采集结果映射策略：成功时写入 `environment_snapshots`，必要时写入 `environment_components`，并更新 `last_collected_at`。
- [x] 5.5 确认环境采集失败时只保存执行记录和日志，不覆盖上一轮成功快照，不更新 `last_collected_at`。
- [x] 5.6 定义普通远程脚本执行记录语义：保存脚本类型、工作目录检查结果、执行用户、安全命令摘要、耗时、退出码、stdout/stderr 日志和审计信息。
- [x] 5.7 确认脚本执行记录、日志摘要和审计详情不包含明文凭据、私钥、passphrase、token 或未经脱敏的敏感脚本内容。

## 6. 环境运行 API

- [x] 6.1 将环境运行 API 统一调整为项目作用域路径：`/api/projects/{projectId}/environments/{environmentId}/...`。
- [x] 6.2 确认 `POST /api/projects/{projectId}/environments/{environmentId}/test-connection` 创建 `ENV_TEST_CONNECTION` 任务，并允许可选 `timeoutSeconds`。
- [x] 6.3 新增 `POST /api/projects/{projectId}/environments/{environmentId}/check`，创建 `ENV_RUN_SCRIPT` 任务并写入 `scriptType=ENV_CHECK`。
- [x] 6.4 为环境检查 API 校验 `checkItems` 只允许 `CONNECTION`、`BASIC_TOOLS`、`WORKING_DIRECTORY`、`PERMISSIONS`。
- [x] 6.5 确认 `POST /api/projects/{projectId}/environments/{environmentId}/collect` 创建 `ENV_COLLECT` 任务，并支持可选 `collectScopes` 和 `timeoutSeconds`。
- [x] 6.6 确认 `POST /api/projects/{projectId}/environments/{environmentId}/scripts` 创建 `ENV_RUN_SCRIPT` 任务，并支持 `scriptType`、`workingDirectory`、`timeoutSeconds` 和内置脚本参数。
- [x] 6.7 在所有环境运行 API 中校验环境存在且属于 URL 中的 `projectId`。
- [x] 6.8 在所有环境运行 API 中校验当前用户有权访问 URL 中的 `projectId`。
- [x] 6.9 确认所有环境运行 API 响应返回任务 ID、任务类型、初始状态和安全消息。
- [x] 6.10 确认所有环境运行 API 的任务输入快照和队列消息不包含明文凭据、私钥、passphrase、token 或未经脱敏的敏感脚本内容。
- [x] 6.11 为未知 `scriptType`、未知 `checkItems`、非法 `collectScopes` 补充校验错误，不创建任务、不投递队列。
- [x] 6.12 为跨项目 environmentId 和无项目权限用户补充拒绝逻辑，不创建任务、不投递队列、不暴露环境连接信息或凭据摘要。

## 7. ENV_TEST_CONNECTION Handler

- [x] 7.1 新增 `EnvironmentTestConnectionHandler` 并注册任务类型 `ENV_TEST_CONNECTION`。
- [x] 7.2 handler 通过 `TaskExecutionContext` 解析输入快照中的 `environmentId`。
- [x] 7.3 handler 调用 `SshRuntimeService.testConnection`，成功后返回安全成功消息。
- [x] 7.4 handler 异常路径交给 worker 标记 `FAILED`，并保留安全错误码和安全摘要。
- [x] 7.5 确认任务队列消息仍只包含任务 ID 等路由信息，任务输入快照不包含明文凭据。

## 8. 测试与验证

- [x] 8.1 为 SSH runtime 补充正常流程测试：密码直连、私钥直连、passphrase 私钥、跳板机连接、统一探测输出解析、连接测试执行记录、环境检查结果保存、环境采集快照保存。
- [x] 8.2 为 SSH runtime 补充异常流程测试：认证失败、连接超时、命令失败、探测输出无效、凭据不存在、凭据项目不匹配、解密失败、采集失败不覆盖成功快照。
- [x] 8.3 为 SSH runtime 补充 edge case 测试：passphrase 为空、多级跳板防御、跳板机禁用、部分工具缺失、工作目录不存在、工作目录不可写、每次命令关闭 session、禁止跨命令复用 session、日志脱敏。
- [x] 8.4 为项目作用域环境运行 API 补充正常流程测试：连接测试、环境检查、环境采集、脚本执行均能创建正确任务。
- [x] 8.5 为环境运行 API 补充异常流程测试：未知 `scriptType`、未知 `checkItems`、非法 `collectScopes` 不创建任务、不投递队列。
- [x] 8.6 为环境运行 API 补充权限测试：跨项目 environmentId、无项目权限用户均被拒绝，且不创建任务、不投递队列。
- [x] 8.7 为环境运行 API 补充 edge case 测试：空请求体、默认采集范围、默认工作目录、超时边界、敏感字段不进入输入快照。
- [x] 8.8 为 `EnvironmentTestConnectionHandler` 补充 handler 成功和失败测试。
- [x] 8.9 更新环境服务或仓储测试，覆盖环境状态、`last_connected_at` 和 `last_collected_at` 更新行为。
- [x] 8.10 运行受影响测试类。
- [x] 8.11 运行完整 `mvn test`，确认普通测试不依赖 Docker Compose、真实 RabbitMQ、Redis、PostgreSQL 或真实 SSH 服务。
- [x] 8.12 如有可用测试环境，记录手动 SSH 连通性验证命令和结果；真实测试结果：OpenSSH CLI 直连跳板机、经跳板机连接 x86、经跳板机连接 riscv 均成功；Apache MINA 适配器已通过一层跳板机成功采集 x86 和 riscv 环境信息。
