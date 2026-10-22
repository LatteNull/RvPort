# add-jooq-codegen-script 设计

## 设计目标

建立稳定的 jOOQ 代码生成工作流，让数据库 schema 的事实来源仍然是 Liquibase，而 Java 业务代码可以依赖已经提交的 jOOQ 生成代码完成普通编译。

核心目标：

- schema 变更后显式刷新 jOOQ 代码。
- 普通构建不依赖数据库。
- Docker build 不依赖数据库。
- `mvn clean` 不删除 jOOQ 生成源码。
- Windows 和 Linux/macOS 都有一致入口。

## 生成链路

```text
Liquibase changelog
        │
        ▼
已迁移 PostgreSQL schema
        │
        ▼
generate-jooq 脚本
        │
        ▼
mvn -Pjooq-codegen generate-sources
        │
        ▼
src/generated/java/cn/rvport/backend/jooq
        │
        ▼
mvn clean package 直接编译已提交源码
```

jOOQ codegen 只读取数据库 schema，不创建、修改或替代 Liquibase changelog。

## 输出目录

生成代码建议输出到：

```text
src/generated/java
```

原因：

- `mvn clean` 默认只清理 `target`，不会删除该目录。
- 生成代码可以随 Liquibase schema 变更一起提交。
- 普通编译和 Docker build 不需要重新连接数据库。
- IDE 可以稳定索引生成类型。

包名保持：

```text
cn.rvport.backend.jooq
```

## Maven 约定

普通构建：

```powershell
mvn clean package
```

普通构建不得执行 jOOQ codegen，也不得要求 PostgreSQL 可连接。

jOOQ 生成：

```powershell
mvn -Pjooq-codegen generate-sources
```

`jooq-codegen` profile 负责：

- 启用 `jooq-codegen-maven`。
- 设置 PostgreSQL JDBC driver 作为 plugin dependency。
- 从环境变量读取连接信息。
- 读取 `public` schema。
- 排除 Liquibase 表：
  - `databasechangelog`
  - `databasechangeloglock`
- 排除 `pgcrypto` 扩展暴露的非业务对象，例如 `pgp_*` 表值函数。
- 不生成 PostgreSQL routine、sequence 和 UDT 辅助代码。
- 输出到 `src/generated/java`。
- 将 `src/generated/java` 加入 Maven compile source root。

## 脚本入口

Windows：

```powershell
.\scripts\generate-jooq.ps1
```

Linux/macOS：

```bash
./scripts/generate-jooq.sh
```

脚本职责：

- 定位项目根目录和后端目录。
- 读取根目录 `.env`。
- 设置 jOOQ 所需环境变量：
  - `RVPORT_JOOQ_JDBC_URL`
  - `RVPORT_JOOQ_JDBC_USER`
  - `RVPORT_JOOQ_JDBC_PASSWORD`
- 检查必要变量是否存在。
- 调用 Maven profile 执行 codegen。
- 在失败时给出明确错误信息。

脚本不负责：

- 自动修改 Liquibase changelog。
- 自动创建 schema。
- 在 Docker build 阶段运行。

## 环境变量映射

脚本优先读取显式 jOOQ 变量：

```text
RVPORT_JOOQ_JDBC_URL
RVPORT_JOOQ_JDBC_USER
RVPORT_JOOQ_JDBC_PASSWORD
```

如果未提供，可以从本地应用数据库变量推导：

```text
RVPORT_DB_URL      -> RVPORT_JOOQ_JDBC_URL
RVPORT_DB_USERNAME -> RVPORT_JOOQ_JDBC_USER
RVPORT_DB_PASSWORD -> RVPORT_JOOQ_JDBC_PASSWORD
```

如果现有 `.env` 使用的是 PostgreSQL compose 变量，则脚本可以组合出默认本地 JDBC URL：

```text
jdbc:postgresql://localhost:${POSTGRES_PORT}/${POSTGRES_DB}
```

并使用：

```text
POSTGRES_USER
POSTGRES_PASSWORD
```

## 生成物提交策略

jOOQ 生成代码应提交到仓库，并与 Liquibase changelog 同步变更。

推荐流程：

```text
修改 Liquibase changelog
        │
        ▼
启动 PostgreSQL
        │
        ▼
运行 Liquibase 迁移
        │
        ▼
运行 generate-jooq 脚本
        │
        ▼
检查 src/generated/java diff
        │
        ▼
提交 migration + generated jOOQ code
```

这样普通开发者拉取代码后可以直接编译，不需要为了编译先启动数据库。

## 风险和取舍

### 生成代码提交会增加 diff

jOOQ 代码量可能较多，但它换来的是构建稳定性。数据库 schema 是事实来源，生成代码只是其 Java 投影。

### 生成结果可能与 schema 不一致

风险来自修改 Liquibase 后忘记重新生成 jOOQ。缓解方式：

- 在任务清单中要求 schema 变更后运行脚本。
- 后续 CI 可以增加“重新生成后检查 git diff 是否为空”的校验。

### codegen 依赖真实数据库

这是 jOOQ 数据库反向生成的正常模式。该依赖被限制在显式生成步骤，不进入普通编译链路。

## 验证策略

apply 阶段至少验证：

- 当前 Docker Compose PostgreSQL 已迁移完成。
- Windows 脚本可以生成 jOOQ 代码。
- Maven profile 可以直接生成 jOOQ 代码。
- 生成目录包含业务表对应代码，不包含 Liquibase 表对应代码。
- 生成目录不包含 `pgcrypto` 扩展 routine 对应代码。
- `mvn clean package` 在不执行 codegen 的情况下通过。
- `openspec validate add-jooq-codegen-script` 通过。
