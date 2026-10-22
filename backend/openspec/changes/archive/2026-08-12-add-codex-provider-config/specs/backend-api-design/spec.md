## ADDED Requirements

### Requirement: 管理员 Codex Provider 配置 API 必须受超级管理员保护
后端 API SHALL 为超级管理员提供 Codex provider 配置查询、保存和测试接口，用于配置 Codex 作为后续日志比较 agent runtime 的默认 provider。

#### Scenario: 查询 Codex provider 配置
- **WHEN** 超级管理员调用 `GET /api/admin/configs/codex-provider`
- **THEN** API SHALL 返回 Codex provider 配置摘要
- **AND** 响应 SHALL 包含 `enabled`、`executablePath`、`modelProviderType`、`baseUrl`、`model`、`wireApi`、`timeoutSeconds`、`maxRuntimeSeconds`、`apiKeyConfigured`、`apiKeyMasked`、`lastTestStatus`、`lastTestMessage` 和 `lastTestedAt`
- **AND** 响应 MUST NOT 返回 API key 明文或密文

#### Scenario: 保存 Codex provider 配置
- **WHEN** 超级管理员调用 `PATCH /api/admin/configs/codex-provider`
- **THEN** API SHALL 校验并保存 Codex provider 配置
- **AND** `modelProviderType` SHALL 只允许 `OPENAI_COMPATIBLE`
- **AND** `wireApi` SHALL 只允许 `RESPONSES` 或 `CHAT`
- **AND** `baseUrl` SHALL 只允许 `http` 或 `https` URL
- **AND** `model` SHALL 为非空字符串
- **AND** `timeoutSeconds` 和 `maxRuntimeSeconds` SHALL 在后端定义的安全范围内
- **AND** API MUST NOT 接受未声明的任意配置 key

#### Scenario: 保存 Codex provider API key
- **WHEN** 超级管理员保存 Codex provider 配置且请求包含非空 `apiKey`
- **THEN** 后端 SHALL 加密保存 API key
- **AND** API 响应 MUST NOT 返回 API key 明文或密文

#### Scenario: 保留或清空 Codex provider API key
- **WHEN** 超级管理员保存 Codex provider 配置且请求不包含 `apiKey`
- **THEN** 后端 SHALL 保留已有 API key
- **WHEN** 超级管理员保存 Codex provider 配置且 `apiKey` 为空字符串
- **THEN** 后端 SHALL 清空已有 API key

#### Scenario: 测试 Codex provider 配置
- **WHEN** 超级管理员调用 `POST /api/admin/configs/codex-provider:test`
- **THEN** API SHALL 使用已保存配置或请求中的临时覆盖配置执行最小可用性测试
- **AND** 临时覆盖配置中的 API key MUST NOT 被持久化
- **AND** 响应 SHALL 返回成功或失败状态、脱敏消息和测试时间
- **AND** 后端 SHALL 记录最近一次测试状态、脱敏消息和测试时间

#### Scenario: 普通用户访问 Codex provider 配置
- **WHEN** 非超级管理员调用 Codex provider 配置查询、保存或测试接口
- **THEN** API SHALL 返回无权限错误
- **AND** 后端 MUST NOT 泄漏任何 provider secret 或内部执行细节

#### Scenario: Codex provider 不直接暴露模型调用能力
- **WHEN** 前端配置 Codex provider
- **THEN** 后端 SHALL 只保存和测试 Codex agent runtime 配置
- **AND** 后端 MUST NOT 通过该 API 提供任意提示词执行或直接 LLM 调用能力
