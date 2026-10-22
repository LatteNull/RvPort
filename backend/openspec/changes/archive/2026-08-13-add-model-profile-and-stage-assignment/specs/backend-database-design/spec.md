## MODIFIED Requirements

### Requirement: Codex Provider 配置必须复用 System Configs
数据库 SHALL 使用专用模型配置表保存多个模型 profile，并 SHALL 使用阶段绑定表表达测试结果比较阶段使用哪个模型。历史 `system_configs` 的 `codex-provider` namespace MAY 作为一次性迁移来源，但 SHALL NOT 作为兼容读取来源；测试结果比较运行时模型选择 SHALL 以 `model_profiles` 和 `model_stage_assignments` 为事实来源。

#### Scenario: 保存模型 profile 普通配置
- **WHEN** 后端保存模型 profile 的普通配置项
- **THEN** 数据库 SHALL 将配置写入 `model_profiles`
- **AND** `name` SHALL 在未删除 profile 中唯一
- **AND** `model_provider_type` SHALL 表达 provider 类型，MVP 只允许 `OPENAI_COMPATIBLE`
- **AND** `wire_api` SHALL 使用非加密值保存，并 SHALL 只表达 `RESPONSES` 或 `CHAT`
- **AND** `enabled` SHALL 表达该 profile 是否可被阶段绑定和运行时解析

#### Scenario: 保存模型 profile secret
- **WHEN** 后端保存模型 profile API key
- **THEN** 数据库 SHALL 将 API key 加密载荷写入 `model_profiles.api_key_encrypted`
- **AND** `api_key_encrypted` MUST NOT 保存 API key 明文
- **AND** 查询 API SHALL 只返回 API key 是否已配置和遮蔽摘要

#### Scenario: 保存模型 profile 测试摘要
- **WHEN** 模型 profile 测试完成
- **THEN** 数据库 SHALL 保存 `last_test_status`、`last_test_message` 和 `last_tested_at`
- **AND** `last_test_message` MUST 为脱敏后的短摘要
- **AND** `last_test_message` MUST NOT 包含 API key、授权头或服务器真实敏感路径

#### Scenario: 保存阶段模型绑定
- **WHEN** 后端保存阶段模型绑定
- **THEN** 数据库 SHALL 将绑定写入 `model_stage_assignments`
- **AND** `stage` SHALL 唯一
- **AND** 本 change 只要求保存 `TEST_LOG_COMPARE` 阶段绑定
- **AND** `model_profile_id` SHALL 外键引用 `model_profiles.id`
- **AND** 后端 SHALL 拒绝绑定不存在或已禁用的模型 profile

#### Scenario: 查询阶段模型绑定
- **WHEN** 后端按阶段解析模型配置
- **THEN** 数据库 SHALL 支持按 `model_stage_assignments.stage` 查询绑定 profile
- **AND** 数据库 SHALL 支持按 `model_profiles.enabled` 过滤可用 profile
- **AND** 后端 MUST NOT 从历史 `system_configs.codex-provider` 直接解析阶段模型
