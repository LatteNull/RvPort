## ADDED Requirements

### Requirement: 环境连接测试必须支持未落库目标配置
环境运行时 SHALL 支持基于未创建环境的 SSH 目标配置执行一次性连接预检，并 SHALL 将预检结果限定在任务事实内。

#### Scenario: 执行新建环境连接预检任务
- **WHEN** worker 认领由新建环境预检接口创建的 `ENV_TEST_CONNECTION` 任务
- **THEN** worker SHALL 使用任务输入中的目标主机、端口、用户名、正式凭据引用或任务级临时凭据引用、工作目录和可选跳板机执行 SSH 探测
- **AND** worker SHALL 写入任务进度、任务日志和项目级 SSE 事件
- **AND** worker SHALL 根据探测结果将任务标记为 `SUCCEEDED` 或 `FAILED`
- **AND** worker MUST NOT 创建或更新 `environments`、`environment_snapshots` 或 `environment_components`

#### Scenario: 读取任务级临时 SSH 凭据
- **WHEN** target 模式任务输入包含 `temporaryCredentialPayloadId` 且不包含 `credentialId`
- **THEN** worker SHALL 按 `projectId`、`taskId` 和 payload ID 读取 `task_secret_payloads`
- **AND** worker SHALL 解密并校验 payload hash 后构造 SSH runtime 凭据
- **AND** worker MUST NOT 查询或创建正式 `credentials` 记录
- **AND** 解密失败或 hash 不匹配时任务 SHALL 失败并返回安全错误

#### Scenario: 任务终态后清理任务级临时 SSH 凭据
- **GIVEN** target 模式环境预检在 `task_secret_payloads` 保存了加密凭据
- **WHEN** 任务进入 `SUCCEEDED`、`FAILED`、`CANCELLED` 或 `TIMEOUT`
- **THEN** worker SHALL 删除该任务关联的 `task_secret_payloads` 记录
- **AND** worker SHALL 保留任务状态、任务事件和任务日志供前端查看
- **AND** worker MUST NOT 在任务重试重新入队时删除临时凭据

#### Scenario: 新建环境预检成功
- **WHEN** 新建环境预检 SSH 探测成功且输出包含预期探测标记
- **THEN** 任务 SHALL 进入 `SUCCEEDED`
- **AND** 任务日志和 tool run summary SHALL 保存脱敏后的 OS、arch、远程用户、工作目录检查和基础工具检查摘要
- **AND** 后端 MUST NOT 更新任何正式环境的 `status` 或 `last_connected_at`

#### Scenario: 新建环境预检失败
- **WHEN** 新建环境预检发生连接失败、认证失败、跳板机失败、探测命令失败或超时
- **THEN** 任务 SHALL 进入 `FAILED` 或 `TIMEOUT`
- **AND** 错误摘要 SHALL 使用安全错误码和安全消息
- **AND** 后端 MUST NOT 创建无效环境记录
- **AND** 日志、事件和审计 MUST NOT 暴露明文凭据

#### Scenario: 复测已创建环境仍更新环境状态
- **WHEN** worker 认领包含 `environmentId` 的 `ENV_TEST_CONNECTION` 任务
- **THEN** worker SHALL 保持现有行为，基于正式环境配置执行连接测试
- **AND** 成功时 SHALL 更新对应环境为可连接状态
- **AND** 失败时 SHALL 更新对应环境为连接失败状态

### Requirement: 环境查询必须支持运行状态筛选
环境管理能力 SHALL 允许调用方按 `environments.status` 查询环境列表，并 SHALL 与角色、启用状态过滤共同生效。

#### Scenario: 查询可用环境
- **WHEN** 用户查询项目环境列表并提交 `status=AVAILABLE`
- **THEN** 后端 SHALL 只返回状态为 `AVAILABLE` 的环境
- **AND** 返回环境 MAY 包含最新成功基础信息摘要
- **AND** 后端 MUST NOT 因缺少最新基础信息摘要而隐藏状态可用的环境

#### Scenario: 查询禁用环境状态
- **WHEN** 用户查询项目环境列表并提交 `enabled=false` 或 `status=DISABLED`
- **THEN** 后端 SHALL 按请求条件返回匹配环境
- **AND** 禁用环境 MUST NOT 被新建任务接口作为可运行环境使用

#### Scenario: 组合筛选 SBOM 可选环境
- **WHEN** 前端为 SBOM 配置查询源环境或目标环境
- **THEN** 后端 SHALL 支持 `role=SOURCE_X86&status=AVAILABLE&enabled=true`
- **AND** 后端 SHALL 支持 `role=TARGET_RISCV&status=AVAILABLE&enabled=true`
- **AND** 响应 SHALL 保持分页、凭据遮蔽摘要和跳板机非敏感摘要
