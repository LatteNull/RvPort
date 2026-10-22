## ADDED Requirements

### Requirement: Codex Provider 配置必须复用 System Configs
数据库 SHALL 使用既有 `system_configs` 表保存 Codex provider 配置，并 SHALL 通过 namespace 和 key 白名单表达单个默认 provider。

#### Scenario: 保存 Codex provider 普通配置
- **WHEN** 后端保存 Codex provider 的普通配置项
- **THEN** 数据库 SHALL 将配置写入 `system_configs` 的 `codex-provider` namespace
- **AND** 普通配置项 SHALL 使用非加密值保存
- **AND** `wireApi` SHALL 使用非加密值保存，并 SHALL 只表达 `RESPONSES` 或 `CHAT`
- **AND** `namespace + config_key` 唯一约束 SHALL 保证每个配置 key 只有一个当前值

#### Scenario: 保存 Codex provider secret
- **WHEN** 后端保存 Codex provider API key
- **THEN** 数据库 SHALL 将其写入 `system_configs` 的 `codex-provider` namespace 和 `apiKey` key
- **AND** `encrypted` SHALL 为 `true`
- **AND** `value_type` SHALL 为 `SECRET`
- **AND** `config_value` MUST NOT 保存 API key 明文

#### Scenario: 查询 Codex provider 配置
- **WHEN** 后端读取 Codex provider 配置
- **THEN** 数据库 SHALL 支持按 `namespace = codex-provider` 查询全部配置项
- **AND** 后端 SHALL 将 secret 配置转换为 `apiKeyConfigured` 和遮蔽摘要
- **AND** 后端 MUST NOT 将 secret 明文或密文传递到 API 响应

#### Scenario: 保存最近一次 provider 测试摘要
- **WHEN** Codex provider 测试完成
- **THEN** 数据库 SHALL 保存 `lastTestStatus`、`lastTestMessage` 和 `lastTestedAt`
- **AND** `lastTestMessage` MUST 为脱敏后的短摘要
- **AND** `lastTestMessage` MUST NOT 包含 API key、授权头或服务器真实敏感路径
