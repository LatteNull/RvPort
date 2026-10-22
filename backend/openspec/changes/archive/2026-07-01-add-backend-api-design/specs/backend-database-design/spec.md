## ADDED Requirements

### Requirement: 用户表支持强制改密标记
数据库设计 SHALL 在 `users` 表中提供强制改密标记，用于超级管理员创建用户、重置密码和首次登录改密流程。

#### Scenario: 定义用户强制改密字段
- **WHEN** 定义 `users` 表字段
- **THEN** Schema SHALL 包含 `must_change_password boolean not null default false`

#### Scenario: 超级管理员创建用户
- **WHEN** 超级管理员创建本地普通用户并要求首次登录改密
- **THEN** 后端 SHALL 将该用户的 `must_change_password` 设置为 `true`

#### Scenario: 超级管理员重置密码
- **WHEN** 超级管理员重置用户密码并要求下次登录改密
- **THEN** 后端 SHALL 将该用户的 `must_change_password` 设置为 `true`

#### Scenario: 用户完成改密
- **WHEN** 用户成功修改自己的密码
- **THEN** 后端 SHALL 将该用户的 `must_change_password` 设置为 `false`

#### Scenario: 邮箱验证不进入 MVP
- **WHEN** 设计 MVP 用户管理相关数据库字段
- **THEN** Schema MUST NOT 因该流程要求增加邮箱验证字段或用户 action token 表
