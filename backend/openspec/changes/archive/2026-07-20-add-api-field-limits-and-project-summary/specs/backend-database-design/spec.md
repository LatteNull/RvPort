## MODIFIED Requirements

### Requirement: 用户名和邮箱必须保持唯一
数据库 SHALL 对用户名和非空邮箱保持唯一约束，确保管理员创建和修改用户时不会产生重复登录标识；用户名还 SHALL 受最大长度约束保护。

#### Scenario: 用户名唯一
- **WHEN** 创建或维护 `users` 表
- **THEN** 数据库 SHALL 对 `users.username` 建立唯一索引或唯一约束

#### Scenario: 用户名最大长度
- **WHEN** 创建或维护 `users` 表
- **THEN** 数据库 SHALL 约束 `users.username` 最大 64 字符
- **AND** 数据库 MUST NOT 接受超过 64 字符的用户名

#### Scenario: 非空邮箱唯一
- **WHEN** 创建或维护 `users` 表
- **THEN** 数据库 SHALL 对非空 `users.email` 建立唯一索引或唯一约束
- **AND** 多个空邮箱 MAY 被允许

## ADDED Requirements

### Requirement: 项目名称允许重复
数据库 SHALL 允许多个项目使用相同名称，项目唯一识别以 `projects.id` 为准。

#### Scenario: 不创建项目名称唯一约束
- **WHEN** 创建或维护 `projects` 表
- **THEN** 数据库 MUST NOT 对 `projects.name` 建立全局唯一约束
- **AND** 数据库 MUST NOT 对 `created_by, name` 建立唯一约束

#### Scenario: 保存同名项目
- **WHEN** 同一用户或不同用户创建名称相同的项目
- **THEN** 数据库 SHALL 允许保存这些项目
- **AND** 每个项目 SHALL 通过不同 `projects.id` 区分
