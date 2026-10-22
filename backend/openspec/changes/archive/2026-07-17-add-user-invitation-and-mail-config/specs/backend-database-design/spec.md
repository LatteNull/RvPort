## MODIFIED Requirements

### Requirement: 用户表支持强制改密标记
数据库设计 SHALL 在 `users` 表中提供强制改密标记，用于管理员直接重置密码后的强制改密流程。管理员邀请注册和用户忘记密码 SHALL 使用独立用户 action token 表，不通过 `users` 表增加邮箱验证字段表达状态。

#### Scenario: 定义用户强制改密字段
- **WHEN** 定义 `users` 表字段
- **THEN** Schema SHALL 包含 `must_change_password boolean not null default false`

#### Scenario: 超级管理员创建用户
- **WHEN** 超级管理员创建本地普通用户并发送邀请
- **THEN** 后端 SHALL 创建用户记录
- **AND** 后端 SHALL 通过用户 action token 表保存邀请 token hash
- **AND** 后端 MUST NOT 在 `users` 表保存明文邀请 token

#### Scenario: 超级管理员重置密码
- **WHEN** 超级管理员重置用户密码并要求下次登录改密
- **THEN** 后端 SHALL 将该用户的 `must_change_password` 设置为 `true`

#### Scenario: 用户完成改密
- **WHEN** 用户成功修改自己的密码
- **THEN** 后端 SHALL 将该用户的 `must_change_password` 设置为 `false`

#### Scenario: 不新增邮箱验证字段
- **WHEN** 设计邀请注册和忘记密码数据库字段
- **THEN** Schema MUST NOT 增加 `email_verified_at` 或等效邮箱验证字段
- **AND** 邮箱可达性 SHALL 由用户 action token 的消费事实表达

## ADDED Requirements

### Requirement: 用户名和邮箱必须保持唯一
数据库 SHALL 对用户名和非空邮箱保持唯一约束，确保管理员创建和修改用户时不会产生重复登录标识。

#### Scenario: 用户名唯一
- **WHEN** 创建或维护 `users` 表
- **THEN** 数据库 SHALL 对 `users.username` 建立唯一索引或唯一约束

#### Scenario: 非空邮箱唯一
- **WHEN** 创建或维护 `users` 表
- **THEN** 数据库 SHALL 对非空 `users.email` 建立唯一索引或唯一约束
- **AND** 多个空邮箱 MAY 被允许

### Requirement: 用户 action token 必须持久化为 hash
数据库 SHALL 使用 `user_action_tokens` 表保存邀请注册和忘记密码的一次性 token hash。

#### Scenario: 创建用户 action token 表
- **WHEN** 执行数据库迁移
- **THEN** Schema SHALL 创建 `user_action_tokens` 表
- **AND** 表 SHALL 包含 `id`、`user_id`、`token_type`、`token_hash`、`expires_at`、`consumed_at`、`created_by`、`created_at` 和 `metadata`
- **AND** `token_type` SHALL 至少支持 `INVITATION` 和 `PASSWORD_RESET`

#### Scenario: 保存 token
- **WHEN** 后端生成邀请或密码重置 token
- **THEN** 数据库 SHALL 只保存 token hash
- **AND** 数据库 MUST NOT 保存明文 token
- **AND** `expires_at` SHALL 为必填字段

#### Scenario: 限制 token 查询路径
- **WHEN** 创建 `user_action_tokens` 表
- **THEN** 数据库 SHALL 为 `token_hash` 建立唯一索引
- **AND** SHALL 为 `user_id, token_type, consumed_at` 建立索引
- **AND** SHALL 为 `expires_at` 建立索引

#### Scenario: 消费 token
- **WHEN** 用户接受邀请或确认密码重置
- **THEN** 后端 SHALL 设置 `consumed_at`
- **AND** 同一个 token MUST NOT 被重复消费

### Requirement: 系统配置必须统一持久化
数据库 SHALL 使用统一 `system_configs` 表保存邮箱、通知以及后续服务配置。

#### Scenario: 创建系统配置表
- **WHEN** 执行数据库迁移
- **THEN** Schema SHALL 创建 `system_configs` 表
- **AND** 表 SHALL 包含 `id`、`namespace`、`config_key`、`config_value`、`value_type`、`encrypted`、`description`、`updated_by`、`created_at` 和 `updated_at`
- **AND** 数据库 SHALL 对 `namespace, config_key` 建立唯一约束

#### Scenario: 保存 secret 配置
- **WHEN** 配置项为 SMTP 密码、token 或其他 secret
- **THEN** `encrypted` SHALL 为 `true`
- **AND** `config_value` SHALL 保存加密后的值
- **AND** 数据库 MUST NOT 保存 secret 明文

#### Scenario: 保存非 secret 配置
- **WHEN** 配置项为 host、port、from address、TLS 开关或超时时间
- **THEN** `value_type` SHALL 表达值类型
- **AND** API 层 SHALL 在写入前完成类型和范围校验
