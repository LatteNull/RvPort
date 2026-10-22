## MODIFIED Requirements

### Requirement: 管理员 Codex Provider 配置 API 必须受超级管理员保护
后端 API SHALL 为超级管理员提供模型 profile 管理和 `TEST_LOG_COMPARE` 阶段模型绑定接口，用于配置 Codex agent runtime 在测试结果比较阶段使用的 OpenAI-compatible 模型。旧 `codex-provider` 单例配置 API SHALL NOT 继续作为管理入口保留，测试结果比较模型选择 SHALL 以模型 profile 和阶段绑定为事实来源。

#### Scenario: 查询模型 profile 列表
- **WHEN** 超级管理员调用 `GET /api/admin/model-profiles`
- **THEN** API SHALL 返回分页模型 profile 列表
- **AND** 响应 SHALL 包含 `id`、`name`、`enabled`、`modelProviderType`、`baseUrl`、`model`、`wireApi`、`timeoutSeconds`、`maxRuntimeSeconds`、`apiKeyConfigured`、`apiKeyMasked`、`lastTestStatus`、`lastTestMessage`、`lastTestedAt`、`createdAt` 和 `updatedAt`
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
- **AND** 临时覆盖配置中的 API key MUST NOT 被持久化
- **AND** 响应 SHALL 返回成功或失败状态、脱敏消息和测试时间
- **AND** 后端 SHALL 记录最近一次测试状态、脱敏消息和测试时间

#### Scenario: 查询和保存阶段模型绑定
- **WHEN** 超级管理员调用 `GET /api/admin/model-stage-assignments` 或 `PATCH /api/admin/model-stage-assignments`
- **THEN** API SHALL 返回或保存 `TEST_LOG_COMPARE` 阶段到模型 profile 的绑定
- **AND** 阶段名称 SHALL 使用后端白名单枚举，且本 change 只允许 `TEST_LOG_COMPARE`
- **AND** 绑定目标 SHALL 为已启用模型 profile
- **AND** 响应 MUST NOT 返回 API key 明文或密文

#### Scenario: 普通用户访问模型配置
- **WHEN** 非超级管理员调用模型 profile 或阶段绑定接口
- **THEN** API SHALL 返回无权限错误
- **AND** 后端 MUST NOT 泄漏任何 provider secret 或内部执行细节

#### Scenario: 模型配置 API 不直接暴露模型调用能力
- **WHEN** 前端配置模型 profile 和阶段绑定
- **THEN** 后端 SHALL 只保存、查询、测试配置以及为后续测试结果比较 agent runtime 提供阶段解析
- **AND** 后端 MUST NOT 通过配置 API 提供任意提示词执行或直接 LLM 调用能力
