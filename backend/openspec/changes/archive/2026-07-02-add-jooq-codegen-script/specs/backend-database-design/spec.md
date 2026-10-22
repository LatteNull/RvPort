## MODIFIED Requirements

### Requirement: jOOQ Codegen 必须基于迁移后的 Schema
jOOQ codegen SHALL 读取已由 Liquibase 迁移完成的 PostgreSQL schema，而不得创建或替代 schema 迁移。

#### Scenario: 执行 jOOQ codegen
- **WHEN** 开发者需要生成 jOOQ 代码
- **THEN** 开发者 SHALL 先对目标 PostgreSQL 数据库执行 Liquibase 迁移
- **AND** jOOQ codegen SHALL 连接迁移后的数据库读取 schema
- **AND** jOOQ 生成代码 SHALL 输出到可提交源码目录
- **AND** jOOQ 生成代码 SHALL 与对应 Liquibase schema 变更一起提交

#### Scenario: 空库尚未迁移
- **WHEN** PostgreSQL 数据库尚未执行 Liquibase 迁移
- **THEN** jOOQ codegen MUST NOT 被视为 schema 创建入口
- **AND** 生成结果不应作为数据库迁移来源

#### Scenario: 排除迁移元数据表
- **WHEN** jOOQ codegen 读取 `public` schema
- **THEN** 生成结果 MUST NOT 包含 Liquibase 元数据表对应代码
- **AND** `databasechangelog` MUST 被排除
- **AND** `databasechangeloglock` MUST 被排除

#### Scenario: 排除扩展非业务对象
- **WHEN** jOOQ codegen 读取启用了 `pgcrypto` 的 `public` schema
- **THEN** 生成结果 SHOULD 只包含业务 schema 所需的表、记录、键和索引代码
- **AND** 生成结果 SHOULD NOT 包含 `pgcrypto` 扩展 routine 对应代码
