# add-jooq-codegen-script 提案

## 背景

后端已经使用 Liquibase 创建 PostgreSQL MVP schema，并在 Maven 中预留了 jOOQ codegen 配置。当前仍缺少稳定的开发期生成流程：如果 jOOQ 代码只生成到 `target/generated-sources/jooq`，`mvn clean` 会删除生成物，普通编译又会因为业务代码引用 jOOQ 类型而依赖数据库生成流程，形成构建上的循环依赖。

本变更用于建立显式、可重复、跨平台的 jOOQ 代码生成脚本和 Maven 约定，使 schema 变更后可以手动刷新 jOOQ 代码，而普通 Maven 编译、Docker build 和 CI 构建不依赖正在运行的数据库。

## 范围

本变更将：

- 新增 Windows PowerShell 版本 jOOQ 生成脚本。
- 新增 Linux/macOS Shell 版本 jOOQ 生成脚本。
- 将 jOOQ codegen 设计为开发期显式步骤，而不是普通编译默认步骤。
- 调整 Maven jOOQ codegen profile，使其只在显式启用时连接 PostgreSQL。
- 将 jOOQ 生成输出改为可提交源码目录，避免 `mvn clean` 删除后导致普通编译失败。
- 将可提交生成目录加入 Maven compile source root。
- 排除 Liquibase 自身表，避免生成 `databasechangelog` 和 `databasechangeloglock` 对应代码。
- 确保 jOOQ codegen 读取已经由 Liquibase 迁移完成的 PostgreSQL schema。
- 补充中文开发文档，说明 schema 变更后的生成顺序。
- 实际运行脚本验证当前数据库 schema 可以生成 jOOQ 代码。

本变更不做：

- 不新增业务 Repository、Service、Controller。
- 不修改 Liquibase schema 内容。
- 不让 Dockerfile 在镜像 build 阶段连接数据库执行 codegen。
- 不让普通 `mvn clean package` 默认连接数据库。
- 不引入 JPA。

## 影响文件

预计影响：

- `pom.xml`
- `scripts/generate-jooq.ps1`
- `scripts/generate-jooq.sh`
- `src/generated/java/**`
- `docs/BACKEND_DEVELOPMENT_PLAN.md`
- `openspec/specs/backend-app-skeleton/spec.md`
- `openspec/specs/backend-database-design/spec.md`

## 验收标准

- Windows 脚本可以读取根目录 `.env` 并运行 jOOQ codegen。
- Linux/macOS 脚本可以读取根目录 `.env` 并运行 jOOQ codegen。
- jOOQ 生成代码输出到可提交源码目录，且不会被 `mvn clean` 删除。
- 普通 `mvn clean package` 不需要连接 PostgreSQL。
- jOOQ codegen 不生成 Liquibase changelog 表对应代码。
- 生成包名保持为 `cn.rvport.backend.jooq`。
- `mvn test` 通过。
- `openspec validate add-jooq-codegen-script` 通过。
