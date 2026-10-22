## ADDED Requirements

### Requirement: 数据库必须保存 Agent Runtime 配置
数据库 SHALL 使用专用表保存 agent runtime 配置，使模型配置和 agent 执行器配置解耦。

#### Scenario: 创建 agent runtime 表
- **WHEN** 执行数据库迁移
- **THEN** 数据库 SHALL 创建 `agent_runtimes` 表
- **AND** 表 SHALL 包含 `id`、`agent_type`、`name`、`enabled`、`executable_path`、`default_args`、`config`、`last_probe_status`、`last_probe_message`、`last_probe_details`、`last_probe_at`、`created_at` 和 `updated_at`
- **AND** `agent_type` SHALL 支持 `CODEX`、`DEEPSEEK_HARNESS` 和 `OPENCODE`

#### Scenario: Agent runtime 唯一性
- **WHEN** 后端初始化或保存 agent runtime
- **THEN** 数据库 SHALL 保证 `agent_type` 唯一
- **AND** 数据库 SHALL 保证 runtime `name` 在未删除记录中唯一或通过等效策略避免展示重名歧义

#### Scenario: Agent runtime 安全边界
- **WHEN** 保存 `default_args`、`config` 或最近 probe 结果
- **THEN** 数据库 MUST NOT 保存 API key 明文、授权头、完整 prompt、完整 agent 输入或服务器真实敏感路径
- **AND** 可执行路径 SHALL 只作为后端配置字段返回给超级管理员

#### Scenario: 初始化默认 runtime
- **WHEN** 首次执行迁移或应用启动初始化
- **THEN** 数据库 SHALL upsert `CODEX`、`DEEPSEEK_HARNESS` 和 `OPENCODE` 默认 runtime
- **AND** 该初始化 SHALL 可重复执行

## MODIFIED Requirements

### Requirement: 模型 Profile 配置必须使用专用表
数据库 SHALL 使用专用模型配置表保存多个模型 profile，并 SHALL 使用阶段绑定表表达测试结果比较阶段使用哪个模型和哪个 agent runtime。历史 `system_configs` 的 `codex-provider` namespace MAY 作为一次性迁移来源，但 SHALL NOT 作为兼容读取来源；测试结果比较运行时模型和 agent 选择 SHALL 以 `model_profiles`、`agent_runtimes` 和 `model_stage_assignments` 为事实来源。

#### Scenario: 保存模型 profile 普通配置
- **WHEN** 后端保存模型 profile 的普通配置项
- **THEN** 数据库 SHALL 将配置写入 `model_profiles`
- **AND** `name` SHALL 在未删除 profile 中唯一
- **AND** `model_provider_type` SHALL 表达 provider 类型，MVP 只允许 `OPENAI_COMPATIBLE`
- **AND** `wire_api` SHALL 使用非加密值保存，并 SHALL 只表达 `RESPONSES` 或 `CHAT`
- **AND** `enabled` SHALL 表达该 profile 是否可被阶段绑定和运行时解析
- **AND** `model_profiles` MUST NOT 作为 agent runtime 可执行路径的事实来源

#### Scenario: 保存模型 profile secret
- **WHEN** 后端保存模型 profile API key
- **THEN** 数据库 SHALL 将 API key 加密载荷写入 `model_profiles.api_key_encrypted`
- **AND** `api_key_encrypted` MUST NOT 保存 API key 明文
- **AND** 查询 API SHALL 只返回 API key 是否已配置和遮蔽摘要

#### Scenario: 保存模型 profile 测试摘要
- **WHEN** 模型 profile 测试完成
- **THEN** 数据库 SHALL 保存 `last_test_status`、`last_test_message`、`last_tested_at`、`last_test_agent_type` 和 `last_test_details`
- **AND** `last_test_details` SHALL 包含测试使用的 agent runtime ID 和分项 probe 摘要
- **AND** `last_test_message` MUST 为脱敏后的短摘要
- **AND** `last_test_message` MUST NOT 包含 API key、授权头或服务器真实敏感路径

#### Scenario: 保存阶段模型绑定
- **WHEN** 后端保存阶段模型绑定
- **THEN** 数据库 SHALL 将绑定写入 `model_stage_assignments`
- **AND** `stage` SHALL 唯一
- **AND** 本 change 只要求保存 `TEST_LOG_COMPARE` 阶段绑定
- **AND** `model_profile_id` SHALL 外键引用 `model_profiles.id`
- **AND** `agent_runtime_id` SHALL 外键引用 `agent_runtimes.id`
- **AND** 后端 SHALL 拒绝绑定不存在或已禁用的模型 profile
- **AND** 后端 SHALL 拒绝绑定不存在或已禁用的 agent runtime

#### Scenario: 查询阶段模型绑定
- **WHEN** 后端按阶段解析模型和 agent 配置
- **THEN** 数据库 SHALL 支持按 `model_stage_assignments.stage` 查询绑定 profile 和 runtime
- **AND** 数据库 SHALL 支持按 `model_profiles.enabled` 和 `agent_runtimes.enabled` 过滤可用配置
- **AND** 后端 MUST NOT 从历史 `system_configs.codex-provider` 直接解析阶段模型或 agent
