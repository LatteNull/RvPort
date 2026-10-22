## Context

当前后端已经支持创建 SSH 环境、保存 SSH 密码/私钥凭据、创建 `ENV_TEST_CONNECTION` 任务，并且任务执行上下文已经能写进度、事件和任务日志。但 worker 还没有真实 SSH runtime，`ENV_TEST_CONNECTION` 还只是一个可投递的任务类型，不能实际验证目标环境是否可连接。

本 change 的目标是让 SSH 连接测试真实执行，作为后续环境采集、远程脚本和构建任务的基础。

## Goals / Non-Goals

**Goals:**

- 引入 SSH 客户端封装，支持直连和一层跳板机。
- 支持 SSH 密码、SSH 私钥和可选 passphrase。
- 增加凭据运行时解密读取能力，只在 worker 执行期间使用明文凭据。
- 实现 `ENV_TEST_CONNECTION` handler，真实执行统一的远程连接探测命令。
- 明确 `ENV_TEST_CONNECTION`、`ENV_COLLECT`、`ENV_RUN_SCRIPT` 三类远程执行的命令边界、保存位置和执行记录语义。
- 使用 `TaskExecutionContext` 写进度、日志摘要和失败摘要。
- 成功或失败后更新环境连接状态。
- 测试覆盖正常流程、异常流程和 edge case。

**Non-Goals:**

- 不实现 Git clone/fetch。
- 不在本 change 中完成完整 SBOM 采集、构建命令、测试命令、文件上传下载或长期交互式 shell。
- 不支持多级跳板机。
- 不修改数据库 schema。
- 不在普通 `mvn test` 中要求真实 SSH 服务器。

## Decisions

### 1. 使用 Java SSH 客户端库并通过适配层隔离

实现中新增 `SshClientAdapter` 或等价接口，业务服务只依赖适配层，不直接散落第三方库 API。适配层负责建立 session、执行命令、关闭连接和转换异常。

优先选择 Apache MINA SSHD。原因是本项目需要一层跳板机能力，并且希望跳板机由 SSH 客户端库通过 `ProxyJump` / `HostConfigEntry` 这类原生模型处理，而不是由业务代码自行维护本地端口转发、direct-tcpip 通道、生命周期和异常映射。Apache MINA SSHD 对 OpenSSH 风格的 host config 和 proxy jump 支持更贴近当前需求。

SSHJ 仍可作为备选方案：它的命令执行 API 简洁，直连、认证、SFTP/SCP 和端口转发能力成熟；但跳板机场景通常需要我们自己编排转发链路，因此不作为本 change 的优先选择。

JSch 不作为优先选择，因为它维护状态和现代算法支持较弱。

### 2. 凭据运行时解密集中在 CredentialService

新增运行时读取方法，例如 `CredentialService.decryptPayload(...)` 或类型化方法：

- `sshPasswordCredential(credentialId, projectId)`
- `sshKeyCredential(credentialId, projectId)`

该方法先复用 `requireActive` 校验凭据存在、启用且属于项目，再解析 `credentials.encrypted_payload`，使用 `CredentialCipher.decrypt` 解密，然后映射为类型化运行时凭据对象。

明文密码、私钥和 passphrase 只保存在方法栈中的短生命周期对象中，不写日志、不写任务事件、不放入任务输入快照。

### 3. SshRuntimeService 负责环境解析和连接编排

新增 `SshRuntimeService`，对外提供：

- `testConnection(environmentId, TaskExecutionContext context)`
- 后续可扩展 `execute(environmentId, command, options, context)`

`SshRuntimeService` 负责读取目标环境、读取跳板机环境、读取并解密凭据、构造连接请求，并调用 SSH 适配层执行统一的连接探测命令。

SSH runtime 的执行模型 SHALL 是“每次远程命令创建一次短生命周期 SSH session”。MVP 不做 SSH 连接池，不跨任务复用 SSH session，也不让一个长期空闲连接等待后续命令。这样可以避免长时间空闲连接被网络设备、sshd 配置或跳板机断开后，后续命令落在不可预期状态。

如果后续业务需要执行多个步骤，应优先选择以下两种方式之一：

- 将多个原子步骤组合成一次受控脚本，在单次 SSH session 中执行并收集 exit code、stdout 和 stderr。
- 将每个步骤作为独立远程命令执行，每个命令独立建立和关闭 SSH session，并由任务执行上下文记录阶段进度。

对于单条长时间运行命令，runtime 可以配置命令超时、输出读取和必要的 keepalive，但该 session 仍只服务于这一条命令，命令完成或失败后必须关闭。

### 4. 远程执行类型和结果保存位置必须统一

原型中存在四类容易混淆的动作：测试连接、环境检查、采集环境信息、运行脚本。它们都通过 SSH runtime/Env Runner 执行，但保存语义不同：

| 动作 | 任务类型 | 主要目的 | 保存位置 | 是否更新采集结果 |
| --- | --- | --- | --- | --- |
| 测试连接 | `ENV_TEST_CONNECTION` | 验证 SSH 登录、远程命令执行、工作目录和基础权限 | `tasks`、`task_events`、`tool_runs`、`task_logs`，并更新 `environments.status` / `last_connected_at` | 否 |
| 环境检查 | `ENV_RUN_SCRIPT`，`scriptType=ENV_CHECK` | 构建/测试前检查连接、基础工具、工作目录、权限 | `tasks`、`task_events`、`tool_runs`、`task_logs` | 否 |
| 采集环境信息 | `ENV_COLLECT` | 采集 OS、kernel、arch、包管理器、软件源、已安装包和基础工具版本 | 上述执行记录，外加 `environment_snapshots` 和 `environment_components`，并更新 `last_collected_at` | 是 |
| 运行脚本 | `ENV_RUN_SCRIPT` | 执行内置或审核过的 bash 脚本，保留审计和排障记录 | `tasks`、`task_events`、`tool_runs`、`task_logs` | 仅内置采集脚本可以更新 |

所有远程执行都必须写 `tool_runs` 作为执行记录事实来源：

- `tool_name` 使用稳定名称，例如 `rvport-ssh-connectivity-probe`、`rvport-env-check`、`rvport-env-collect`、`rvport-remote-script`。
- `command_summary` 只保存安全摘要，不保存明文脚本全文、密码、私钥、passphrase、token 或服务器真实敏感路径。
- `exit_code` 保存远程命令退出码；连接或认证阶段失败且没有远程进程时允许为空。
- `summary` 保存结构化结果，例如检查项结果、解析后的探测字段、脚本类型、工作目录是否可用、基础工具缺失列表。
- stdout/stderr 通过现有任务日志能力落到本地日志文件，并在 `task_logs` 中保存路径、大小、哈希和安全 excerpt。

`environment_snapshots` 只表达“环境信息采集结果”，不用于普通连接测试或构建前检查。这样 `last_collected_at`、环境详情页的 OS/包管理器/软件源/已安装包摘要才不会被一次连接测试污染。

### 5. 前端 API 必须显式表达运行类型

前端触发远程执行时不能直接构造内部 task input，也不能把环境检查伪装成普通脚本。后端对外提供明确 API，每个 API 只创建任务并返回任务摘要，实际执行仍由 worker 完成。

| API | 运行类型 | 任务类型 | 典型页面 |
| --- | --- | --- | --- |
| `POST /api/projects/{projectId}/environments/{environmentId}/test-connection` | 测试连接 | `ENV_TEST_CONNECTION` | 环境列表、新建/修改环境 |
| `POST /api/projects/{projectId}/environments/{environmentId}/check` | 环境检查 | `ENV_RUN_SCRIPT`，`scriptType=ENV_CHECK` | 环境检查配置弹窗、构建/测试前置检查 |
| `POST /api/projects/{projectId}/environments/{environmentId}/collect` | 采集环境信息 | `ENV_COLLECT` | 环境列表、环境详情 |
| `POST /api/projects/{projectId}/environments/{environmentId}/scripts` | 运行脚本 | `ENV_RUN_SCRIPT` | 脚本执行页 |

请求和响应约定：

- 所有环境运行 API 都必须同时接收 `projectId` 和 `environmentId`，并在创建任务前校验环境属于该项目。
- 所有环境运行 API 都必须校验当前用户有权访问该项目；如果项目不存在、环境不属于项目或当前用户无权限，后端必须拒绝请求，且不得创建任务或投递队列。
- 连接测试请求体可以为空，或只包含 `timeoutSeconds` 等非敏感执行参数；响应返回 `taskId`、`taskType`、`status`、`message`。
- 环境检查请求体包含 `checkItems` 和可选 `workingDirectory`、`timeoutSeconds`。`checkItems` 只能从 `CONNECTION`、`BASIC_TOOLS`、`WORKING_DIRECTORY`、`PERMISSIONS` 中选择。
- 环境采集请求体包含可选 `collectScopes`、`timeoutSeconds`。未传时使用默认采集范围。
- 脚本执行请求体包含 `scriptType`、`workingDirectory`、`timeoutSeconds`，以及内置脚本参数；如果后续允许自定义脚本，只保存脚本摘要或哈希到任务输入和执行记录。
- 所有 API 的队列消息仍只包含任务 ID 等路由信息，明文凭据、私钥、passphrase、token 和未经脱敏的敏感脚本内容不得进入请求回显、任务输入快照、队列消息、日志摘要或审计详情。

### 6. 连接测试命令和保存内容

连接测试使用无需 sudo、无写入副作用的轻量探测脚本。脚本应尽量兼容 POSIX shell，并避免读取项目目录、源码路径、用户 home 下的敏感文件或服务器真实路径。

```text
printf 'RVPORT_PROBE=ok\n'
printf 'KERNEL_NAME=%s\n' "$(uname -s 2>/dev/null || true)"
printf 'KERNEL_VERSION=%s\n' "$(uname -r 2>/dev/null || true)"
printf 'MACHINE_ARCH=%s\n' "$(uname -m 2>/dev/null || true)"
printf 'REMOTE_USER=%s\n' "$(id -un 2>/dev/null || whoami 2>/dev/null || true)"
printf 'REMOTE_PWD_ACCESSIBLE=%s\n' "$(pwd >/dev/null 2>&1 && printf true || printf false)"
if [ -n "$RVPORT_WORKDIR" ]; then
  [ -d "$RVPORT_WORKDIR" ] && printf 'WORKDIR_EXISTS=true\n' || printf 'WORKDIR_EXISTS=false\n'
  [ -r "$RVPORT_WORKDIR" ] && printf 'WORKDIR_READABLE=true\n' || printf 'WORKDIR_READABLE=false\n'
  [ -w "$RVPORT_WORKDIR" ] && printf 'WORKDIR_WRITABLE=true\n' || printf 'WORKDIR_WRITABLE=false\n'
fi
for tool in sh bash git gcc g++ make cmake python3 java mvn; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf 'TOOL_%s_PRESENT=true\n' "$tool"
  else
    printf 'TOOL_%s_PRESENT=false\n' "$tool"
  fi
done
```

成功条件：

- SSH 连接建立成功。
- 命令在超时时间内结束。
- exit code 为 0。
- stdout 包含 `RVPORT_PROBE=ok`。

连接测试输出统一按 `KEY=VALUE` 解析，并保存到 `tool_runs.summary`：

- `probeVersion`
- `kernelName`
- `kernelVersion`
- `machineArch`
- `remoteUser`
- `workingDirectory` 检查结果，只保存 configured/present/readable/writable 等布尔状态，不保存敏感真实路径
- `basicTools` 检查结果，记录 `sh`、`bash`、`git`、`gcc`、`g++`、`make`、`cmake`、`python3`、`java`、`mvn` 是否存在
- `warnings`

连接测试不写 `environment_snapshots`，也不更新 `last_collected_at`。它只更新 `environments.status` 和 `last_connected_at`。

### 7. 环境采集命令和保存内容

`ENV_COLLECT` 使用内置采集脚本，采集内容至少包含：

- OS name / OS version。
- kernel version。
- machine arch。
- package manager。
- 软件源摘要，例如 apt/yum/dnf/zypper/apk/pacman 的仓库来源摘要。
- 已安装包摘要。
- 基础工具版本首行：`bash`、`git`、`gcc`、`g++`、`make`、`cmake`、`python3`、`java`、`mvn`。

采集脚本成功后：

- `environment_snapshots.os_name`、`os_version`、`kernel_version`、`arch`、`package_manager` 保存结构化字段。
- `environment_snapshots.repo_summary` 保存软件源摘要 JSON。
- `environment_snapshots.tool_versions` 保存基础工具版本 JSON。
- `environment_snapshots.raw_snapshot` 保存标准化后的非敏感完整采集结果、脚本版本和解析警告。
- `environment_components` 保存已安装包、库、工具、native 文件等组件摘要。
- `environments.last_collected_at` 更新为采集完成时间。

采集失败时保留执行记录、stdout/stderr 和失败摘要，但不覆盖上一轮成功的环境快照，也不更新 `last_collected_at`。

### 8. 环境检查和脚本执行

环境检查是 `ENV_RUN_SCRIPT` 的受控内置脚本类型，建议 `scriptType=ENV_CHECK`。输入中的 `checkItems` 与原型保持一致：

- `CONNECTION`
- `BASIC_TOOLS`
- `WORKING_DIRECTORY`
- `PERMISSIONS`

环境检查结果写入 `tool_runs.summary.checkResults`，用于构建/测试前置判断。它不写 `environment_snapshots`。

普通脚本执行是 `ENV_RUN_SCRIPT` 的另一类脚本类型。MVP 应优先允许内置或审核过的 bash 脚本；如果允许用户提交自定义 bash，任务输入、执行记录和审计日志只能保存脚本摘要或哈希，不能把敏感内容写入普通日志摘要。脚本 stdout/stderr 进入任务日志文件，退出码进入 `tool_runs.exit_code`，执行人、环境、工作目录、开始/结束时间和状态由 `tasks`、`tool_runs`、`task_logs` 与审计日志共同表达。

### 9. 一层跳板机由 SSH runtime 统一处理

如果目标环境配置 `jumpHostEnvironmentId`，SSH runtime 先连接跳板机，再通过跳板机到目标环境建立连接。MVP 继续拒绝多级跳板链路，这个约束已经在环境配置层存在，runtime 仍需防御性校验。

跳板机 session 也遵循短生命周期模型：只在当前命令执行期间打开，当前命令完成、失败或超时后同时关闭目标 session 和跳板机 session。

跳板机和目标机使用各自环境绑定的凭据，runtime 不能把跳板机凭据复制到目标环境输入快照或日志。

### 10. ENV_TEST_CONNECTION handler 只编排任务，不直接写底层 SSH 代码

新增 `EnvironmentTestConnectionHandler`：

- 从 `TaskExecutionContext.input(...)` 读取 `environmentId`。
- 调用 `SshRuntimeService.testConnection(...)`。
- 用 context 写入连接开始、认证成功、探测命令完成等进度和日志摘要。
- 成功或失败时写入 `tool_runs` 执行记录和必要的 `task_logs` 摘要。
- 成功时返回 `TaskHandlerResult.success("环境连接测试成功")`。
- 失败时抛 `TaskExecutionException` 或业务异常，由 worker 统一标记失败。

### 11. 环境状态更新保持最小

成功连接后将环境状态更新为 `AVAILABLE` 或等价已存在状态，并更新 `last_connected_at`；失败后更新为 `UNAVAILABLE` 或等价状态。如果当前枚举不同，实现时以现有枚举为准，不新增 schema。

失败摘要只记录安全错误，例如认证失败、连接超时、命令执行失败，不记录密码、私钥、passphrase 或完整异常堆栈。

## Risks / Trade-offs

- [Risk] SSH 客户端库算法兼容性和目标机器配置有关。  
  Mitigation: 选择成熟库，提供明确错误摘要；实际连通性留给手动验证或独立环境测试。

- [Risk] 跳板机实现复杂度高于直连。  
  Mitigation: 只支持一层跳板机，runtime 防御性拒绝多级链路；单元测试通过 fake adapter 覆盖连接编排。

- [Risk] 普通单元测试无法依赖真实 SSH 服务。  
  Mitigation: SSH adapter 使用接口抽象，普通 `mvn test` 用 fake/mock；真实 SSH 连通性作为手动验证或后续 E2E 环境测试。

- [Risk] 运行时明文凭据可能被误写入日志。  
  Mitigation: 明文凭据只存在类型化 runtime credential 对象；日志和事件只写连接阶段、主机、端口、exit code 等非敏感摘要，并补充敏感信息断言。

- [Risk] 更新环境状态与任务失败事务边界可能不一致。  
  Mitigation: handler 内按阶段写入状态；任务最终状态仍以 `tasks` 为事实来源，环境状态只表达最近一次连接观测结果。

## Migration Plan

1. 增加 SSH 客户端依赖。
2. 增加凭据运行时解密读取能力和类型化 SSH 凭据对象。
3. 增加 SSH runtime 适配层和 fake-friendly 接口。
4. 增加 `ENV_TEST_CONNECTION` handler。
5. 增加环境状态更新仓储方法。
6. 补充单元测试和受影响测试。
7. 运行完整 `mvn test`。

回滚时移除 SSH runtime、handler 和依赖即可；不涉及数据库迁移。

## Open Questions

- SSH 客户端优先使用 Apache MINA SSHD；实施时只需确认 Maven 兼容性、Java 25 兼容性和当前依赖树是否存在冲突。
- 连接测试默认超时时间采用 10 秒还是复用任务 timeout，目前建议先使用 10 秒连接超时和 30 秒命令超时。
- 后续长时间命令是否需要 keepalive 参数，本 change 只预留命令级超时和单命令 session 模型，不引入跨命令长连接。
