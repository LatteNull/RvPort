## ADDED Requirements

### Requirement: Liquibase 必须创建初始 MVP Schema
后端数据库迁移 SHALL 使用 Liquibase 将空 PostgreSQL 数据库迁移为 MVP 可用 schema。

#### Scenario: 空库执行迁移
- **WHEN** PostgreSQL 数据库为空且 Liquibase 迁移被启用
- **THEN** 迁移 SHALL 创建数据库设计文档中的 MVP 表、主键、外键、检查约束、唯一约束和必要索引
- **AND** 迁移 SHALL 启用 `pgcrypto` 扩展

#### Scenario: 迁移脚本组织
- **WHEN** 维护数据库迁移脚本
- **THEN** `db.changelog-master.yaml` SHALL include 分层 changelog
- **AND** 具体 PostgreSQL DDL SHOULD 使用 formatted SQL changelog

#### Scenario: 迁移可重复执行
- **WHEN** 同一数据库已经成功执行过迁移
- **THEN** Liquibase SHALL 通过自身 changelog 记录避免重复执行同一 changeset
- **AND** 幂等 seed MUST NOT 创建重复业务数据

### Requirement: 默认超级管理员必须由初始化迁移幂等创建
数据库迁移 SHALL 在不存在默认管理员时创建默认超级管理员用户。

#### Scenario: 创建默认管理员
- **WHEN** Liquibase 执行用户初始化 changeset 且不存在 `username = 'admin'` 的用户
- **THEN** 迁移 SHALL 插入默认用户 `admin`
- **AND** `is_super_admin` SHALL 为 `true`
- **AND** `must_change_password` SHALL 为 `true`
- **AND** `status` SHALL 为 `ACTIVE`

#### Scenario: 默认密码不得明文存储
- **WHEN** 使用默认密码输入 `admin123` 初始化管理员
- **THEN** 数据库 MUST 只保存预计算后的密码哈希
- **AND** `password_hash` MUST NOT 等于 `admin123`

#### Scenario: 重复执行初始化
- **WHEN** 用户表中已经存在 `username = 'admin'`
- **THEN** 初始化 changeset MUST NOT 创建第二个默认管理员
- **AND** 初始化 changeset MUST NOT 覆盖已有管理员密码

### Requirement: 初始 Schema 不得包含 MVP 排除表
Liquibase 初始 schema SHALL 遵守 MVP 边界，不得提前创建数据库设计明确排除的数据表。

#### Scenario: 检查用户角色相关表
- **WHEN** 初始 schema 迁移完成
- **THEN** 数据库 MUST NOT 包含 `roles`
- **AND** 数据库 MUST NOT 包含 `user_roles`
- **AND** 数据库 MUST NOT 包含 `project_members`

#### Scenario: 检查非 MVP 结果表
- **WHEN** 初始 schema 迁移完成
- **THEN** 数据库 MUST NOT 包含通用 `artifacts` 表
- **AND** 数据库 MUST NOT 包含 `test_cases` 表
- **AND** 数据库 MUST NOT 包含邮箱验证或用户 action token 表

### Requirement: jOOQ Codegen 必须基于迁移后的 Schema
jOOQ codegen SHALL 读取已由 Liquibase 迁移完成的 PostgreSQL schema，而不得创建或替代 schema 迁移。

#### Scenario: 执行 jOOQ codegen
- **WHEN** 开发者需要生成 jOOQ 代码
- **THEN** 开发者 SHALL 先对目标 PostgreSQL 数据库执行 Liquibase 迁移
- **AND** jOOQ codegen SHALL 连接迁移后的数据库读取 schema

#### Scenario: 空库尚未迁移
- **WHEN** PostgreSQL 数据库尚未执行 Liquibase 迁移
- **THEN** jOOQ codegen MUST NOT 被视为 schema 创建入口
- **AND** 生成结果不应作为数据库迁移来源
