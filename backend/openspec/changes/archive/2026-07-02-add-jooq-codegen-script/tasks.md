# 任务清单

- [x] 调整 Maven jOOQ codegen 配置，新增显式 `jooq-codegen` profile。
- [x] 为 jOOQ codegen plugin 增加 PostgreSQL JDBC driver 依赖。
- [x] 将 jOOQ 输出目录改为 `src/generated/java`。
- [x] 将 `src/generated/java` 加入 Maven compile source root。
- [x] 配置 jOOQ 排除 `databasechangelog` 和 `databasechangeloglock`。
- [x] 配置 jOOQ 排除 `pgcrypto` 扩展暴露的非业务对象。
- [x] 新增 Windows 脚本 `scripts/generate-jooq.ps1`。
- [x] 新增 Linux/macOS 脚本 `scripts/generate-jooq.sh`。
- [x] 脚本支持读取根目录 `.env` 并映射 jOOQ JDBC 环境变量。
- [x] 使用当前已迁移 PostgreSQL 实际运行 jOOQ codegen。
- [x] 确认生成代码包名为 `cn.rvport.backend.jooq`。
- [x] 确认生成代码不包含 Liquibase changelog 表。
- [x] 确认生成代码不包含 `pgcrypto` 扩展 routine。
- [x] 更新中文后端开发计划，记录 jOOQ 生成流程。
- [x] 执行 `mvn clean package`，确认普通构建不依赖数据库 codegen。
- [x] 执行 `openspec validate add-jooq-codegen-script`。
