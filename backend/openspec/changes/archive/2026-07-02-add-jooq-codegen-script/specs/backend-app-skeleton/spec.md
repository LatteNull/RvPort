## MODIFIED Requirements

### Requirement: 后端数据访问使用 Liquibase 和 jOOQ
后端应用 SHALL 使用 Liquibase 管理 schema 变更，并 SHALL 使用 jOOQ 作为 MVP 主数据访问方式。

#### Scenario: 管理数据库 schema
- **WHEN** 后端需要新增或修改数据库结构
- **THEN** 变更 SHALL 通过 Liquibase changelog 管理
- **AND** Liquibase SHALL 是 MVP schema 变更入口

#### Scenario: 使用 jOOQ 访问数据库
- **WHEN** 后端业务代码需要访问 PostgreSQL
- **THEN** 后端 SHALL 使用 jOOQ 表达 SQL、状态转移、聚合查询和 PostgreSQL 特性
- **AND** 后端 MUST NOT 在 MVP 阶段引入 JPA 作为主数据访问方式

#### Scenario: 生成 jOOQ 代码
- **WHEN** 空 PostgreSQL 数据库已经通过 Liquibase changelog 创建或更新 schema
- **THEN** 后端 SHALL 能基于迁移后的 PostgreSQL schema 运行 jOOQ codegen
- **AND** jOOQ codegen MUST NOT 作为 schema 创建入口
- **AND** jOOQ codegen SHALL 作为显式开发期步骤执行，而不是普通 Maven 编译的默认步骤

#### Scenario: 普通构建不依赖数据库 codegen
- **WHEN** 开发者执行普通 Maven 编译、测试、打包或 Docker build
- **THEN** 构建 SHALL 编译已经提交的 jOOQ 生成源码
- **AND** 构建 MUST NOT 默认连接 PostgreSQL 执行 jOOQ codegen
- **AND** 构建 MUST NOT 因 `mvn clean` 清理 `target` 而丢失 jOOQ 生成源码

#### Scenario: 跨平台生成脚本
- **WHEN** 开发者需要在 schema 变更后刷新 jOOQ 代码
- **THEN** 后端 SHALL 提供 Windows PowerShell 生成脚本
- **AND** 后端 SHALL 提供 Linux/macOS Shell 生成脚本
- **AND** 脚本 SHALL 从环境变量或根目录 `.env` 获取数据库连接信息
