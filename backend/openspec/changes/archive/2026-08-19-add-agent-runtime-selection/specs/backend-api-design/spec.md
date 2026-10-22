## ADDED Requirements

### Requirement: Agent Runtime API 必须受超级管理员保护
后端 API SHALL 为超级管理员提供 agent runtime 展示和可用性探测能力，供前端在阶段绑定时选择。

#### Scenario: 查询 agent runtime 列表
- **WHEN** 超级管理员调用 `GET /api/admin/agent-runtimes`
- **THEN** API SHALL 返回 agent runtime 列表或分页列表
- **AND** 响应 SHALL 包含 runtime ID、agent 类型、名称、启用状态、可执行路径摘要、最近探测状态、最近探测时间和支持阶段
- **AND** 响应 MUST NOT 返回 API key、授权头、完整命令、完整 prompt 或服务器真实敏感路径

#### Scenario: 查询 agent runtime 详情
- **WHEN** 超级管理员调用 `GET /api/admin/agent-runtimes/{runtimeId}`
- **THEN** API SHALL 返回 runtime 配置摘要和最近探测分项结果
- **AND** 响应 MUST NOT 返回明文 secret 或完整 agent 命令

#### Scenario: 普通用户访问 agent runtime API
- **WHEN** 非超级管理员调用 agent runtime 管理或展示接口
- **THEN** API SHALL 返回无权限错误
- **AND** 后端 MUST NOT 泄漏 runtime 是否存在或内部执行细节

## MODIFIED Requirements

### Requirement: 管理员 Codex Provider 配置 API 必须受超级管理员保护
后端 API SHALL 为超级管理员提供模型 profile 管理、agent runtime 展示和 `TEST_LOG_COMPARE` 阶段模型/agent 绑定接口，用于配置测试结果比较阶段使用的 OpenAI-compatible 模型和后端 agent runtime。旧 `codex-provider` 单例配置 API SHALL NOT 继续作为管理入口保留，测试结果比较模型和 agent 选择 SHALL 以模型 profile、agent runtime 和阶段绑定为事实来源。

#### Scenario: 查询模型 profile 列表
- **WHEN** 超级管理员调用 `GET /api/admin/model-profiles`
- **THEN** API SHALL 返回分页模型 profile 列表
- **AND** 响应 SHALL 包含 `id`、`name`、`enabled`、`modelProviderType`、`baseUrl`、`model`、`wireApi`、`timeoutSeconds`、`maxRuntimeSeconds`、`apiKeyConfigured`、`apiKeyMasked`、`lastTestStatus`、`lastTestMessage`、`lastTestAgentType`、`lastTestDetails`、`lastTestedAt`、`createdAt` 和 `updatedAt`
- **AND** 响应 MUST NOT 返回 API key 明文或密文

#### Scenario: 创建或更新模型 profile
- **WHEN** 超级管理员调用 `POST /api/admin/model-profiles` 或 `PATCH /api/admin/model-profiles/{profileId}`
- **THEN** API SHALL 校验并保存模型 profile
- **AND** `modelProviderType` SHALL 只允许 `OPENAI_COMPATIBLE`
- **AND** `wireApi` SHALL 只允许 `RESPONSES` 或 `CHAT`
- **AND** `baseUrl` SHALL 只允许 `http` 或 `https` URL
- **AND** `model` SHALL 为非空字符串
- **AND** `timeoutSeconds` 和 `maxRuntimeSeconds` SHALL 在后端定义的安全范围内
- **AND** API MUST NOT 接受未声明的任意配置字段
- **AND** 新 API MUST NOT 要求使用 `executablePath` 表达 agent 可执行路径

#### Scenario: 保存模型 profile API key
- **WHEN** 超级管理员保存模型 profile 且请求包含非空 `apiKey`
- **THEN** 后端 SHALL 加密保存 API key
- **AND** API 响应 MUST NOT 返回 API key 明文或密文

#### Scenario: 保留或清空模型 profile API key
- **WHEN** 超级管理员更新模型 profile 且请求不包含 `apiKey`
- **THEN** 后端 SHALL 保留已有 API key
- **WHEN** 超级管理员更新模型 profile 且 `apiKey` 为空字符串
- **THEN** 后端 SHALL 清空已有 API key

#### Scenario: 测试模型 profile
- **WHEN** 超级管理员调用 `POST /api/admin/model-profiles/{profileId}:test`
- **THEN** API SHALL 使用已保存配置或请求中的临时覆盖配置执行最小可用性测试
- **AND** 请求 SHALL 支持指定 `agentRuntimeId`
- **AND** 未指定 `agentRuntimeId` 时后端 SHALL 使用 `TEST_LOG_COMPARE` 当前绑定的 agent runtime 或默认 Codex runtime
- **AND** 临时覆盖配置中的 API key MUST NOT 被持久化
- **AND** 响应 SHALL 返回成功或失败状态、agent 类型、agent runtime ID、分项 probe、脱敏消息和测试时间
- **AND** 后端 SHALL 记录最近一次测试状态、脱敏消息、agent 类型、agent runtime ID、分项结果和测试时间

#### Scenario: 查询和保存阶段模型绑定
- **WHEN** 超级管理员调用 `GET /api/admin/model-stage-assignments` 或 `PATCH /api/admin/model-stage-assignments`
- **THEN** API SHALL 返回或保存 `TEST_LOG_COMPARE` 阶段到模型 profile 和 agent runtime 的绑定
- **AND** 阶段名称 SHALL 使用后端白名单枚举，且本 change 只允许 `TEST_LOG_COMPARE`
- **AND** 绑定目标 SHALL 为已启用模型 profile 和已启用 agent runtime
- **AND** 响应 MUST NOT 返回 API key 明文、密文、完整 agent 命令或完整 prompt

#### Scenario: 普通用户访问模型配置
- **WHEN** 非超级管理员调用模型 profile、agent runtime 或阶段绑定接口
- **THEN** API SHALL 返回无权限错误
- **AND** 后端 MUST NOT 泄漏任何 provider secret、agent 命令或内部执行细节

#### Scenario: 模型配置 API 不直接暴露模型调用能力
- **WHEN** 前端配置模型 profile、agent runtime 和阶段绑定
- **THEN** 后端 SHALL 只保存、查询、测试配置以及为后续测试结果比较 agent runtime 提供阶段解析
- **AND** 后端 MUST NOT 通过配置 API 提供任意提示词执行或直接 LLM 调用能力
