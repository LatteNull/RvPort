# 设计：后端工程骨架

## 背景

当前 `backend` 目录已经有正式的数据库设计、API 设计、基础设施设计和后端开发计划，但还没有应用工程。第一个实现切片应优先固定工程主干，使后续业务模块共享同一套技术栈、配置、响应、错误、测试和安全基础约定。

## 技术栈决策

| 领域 | 决策 |
| --- | --- |
| 语言 | Java 25 LTS |
| 框架 | Spring Boot 4.1.x |
| 构建工具 | Maven |
| Web 框架 | Spring Web MVC |
| 安全框架 | Spring Security |
| 登录态 | Spring Security Session + Spring Session Redis + HttpOnly Cookie |
| 数据库 | PostgreSQL |
| Schema 管理 | Liquibase |
| 数据访问 | jOOQ |
| 缓存 | Spring Data Redis |
| 队列 | Spring AMQP |
| 健康检查 | Spring Boot Actuator |
| 指标 | Micrometer |
| 测试 | JUnit 5 + Testcontainers |
| 密码哈希 | Argon2id |
| 凭据加密 | 应用层 AES-256-GCM |

## 不使用 JPA 的原因

RvPort 的核心模型偏向任务事实流、追加事件、审计、状态机和跨表聚合，而不是围绕大型对象图进行生命周期管理。MVP 数据访问层应优先使用 jOOQ 显式表达 SQL、状态转移条件、JSONB 字段和 PostgreSQL 特性。

JPA 不作为 MVP 主数据访问方式。后续如确需引入，必须通过单独 change 说明引入范围和边界。

## 数据库与代码生成

Schema 管理顺序：

```text
空 PostgreSQL 数据库
  └─ Liquibase changelog
      └─ 创建/更新 PostgreSQL schema
          └─ jOOQ codegen 读取迁移后的 schema
              └─ Repository / Query Service
                  └─ Application Service
```

约定：

- Liquibase 是唯一 schema 变更入口。
- 本地数据库可以从空库开始，所有业务 schema 都应由 Liquibase changelog 创建。
- jOOQ codegen 不定义 schema，它只读取 Liquibase 已迁移完成后的 PostgreSQL schema 并生成代码。
- 业务查询和状态转移优先通过 jOOQ 表达。
- 本 change 可以建立 Liquibase 和 jOOQ 的工程配置，但不要求创建完整业务表迁移。
- 完整业务表 changelog 将由后续 `add-database-migrations` change 补齐；届时 jOOQ codegen 才需要生成完整业务表代码。

## 会话与前端交互

MVP 登录态使用服务端 session，而不是 JWT。

```text
POST /api/auth/login
  ├─ 后端校验用户名和密码
  ├─ 创建 Spring Security session
  ├─ Session 存储到 Redis
  └─ Set-Cookie: RVPORT_SESSION=...

GET /api/auth/me
  ├─ 浏览器自动携带 Cookie
  ├─ 已登录返回当前用户
  └─ 未登录返回 401
```

Cookie 约定：

- `HttpOnly`
- `Secure` 在生产环境开启
- `SameSite=Lax` 作为默认值
- cookie 名称使用 `RVPORT_SESSION`

非 GET 请求应保留 CSRF 防护设计空间。具体 CSRF token 端点可在认证用户管理 change 中实现。

## 密码与凭据

用户密码：

- 只保存 Argon2id 哈希。
- 不保存明文密码。
- 不使用 SHA-256、MD5 等快哈希保存密码。

平台级秘密：

- PostgreSQL、RabbitMQ、Redis 密码来自 `.env` 或环境变量。
- 凭据加密主密钥来自 `.env` 或环境变量。

业务凭据：

- Git token、Git username/password、SSH password、SSH private key、SSH passphrase 等业务凭据后续需要写入 `credentials` 表。
- 秘密载荷必须使用应用层 AES-256-GCM 加密。
- 每条凭据使用独立随机 nonce/iv。
- 数据库可保存算法、key id、遮蔽摘要、公钥、指纹等非敏感元数据。
- API、日志和审计不得输出明文秘密。

## 工程目录建议

```text
backend
├─ pom.xml
├─ src
│  ├─ main
│  │  ├─ java
│  │  │  └─ cn/rvport/backend
│  │  │     ├─ RvPortBackendApplication.java
│  │  │     ├─ common
│  │  │     ├─ config
│  │  │     ├─ health
│  │  │     ├─ security
│  │  │     └─ worker
│  │  └─ resources
│  │     ├─ application.yml
│  │     └─ db/changelog
│  └─ test
│     └─ java
└─ docs
```

后续业务模块可以继续增加：

- `auth`
- `users`
- `projects`
- `sources`
- `environments`
- `credentials`
- `tasks`
- `logs`
- `scans`
- `sbom`
- `issues`
- `reports`
- `validation`
- `archives`
- `audit`

## 基础 API 约定

本 change 只需要提供最小健康检查和通用结构约定：

- `GET /health`
- `GET /api/health`

响应包络应与 API 设计保持一致，包含：

- `data`
- `traceId`
- `timestamp`

错误响应应包含：

- `code`
- `message`
- 可选 `details`
- `traceId`
- `timestamp`

## 测试策略

首个骨架应建立可运行的测试命令：

- Spring context smoke test。
- 健康检查 API 测试。
- 配置绑定测试。
- 后续可接入 Testcontainers 验证 PostgreSQL、Redis、RabbitMQ。

本 change 不要求完成完整数据库迁移和业务集成测试，但 Maven 测试命令必须可运行。

## 风险

- Spring Boot 4.1.x 较新，依赖生态需要通过 Maven BOM 收敛版本。
- Java 25 LTS 要求本地和 CI 使用一致 JDK。
- jOOQ codegen 依赖 Liquibase 已迁移后的数据库 schema，工程骨架阶段可以先建立配置，完整生成流程应随数据库迁移 change 完成。
- Session + Cookie 需要 CSRF 策略配合，认证实现阶段必须补齐。
