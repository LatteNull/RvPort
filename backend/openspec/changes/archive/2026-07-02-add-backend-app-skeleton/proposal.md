## Why

RvPort 后端已经完成数据库、API 和基础设施设计，但 `backend` 目录尚未包含可启动的后端应用工程。进入业务开发前，需要先固定 Java/Spring Boot 技术栈、工程结构、配置方式、安全基础约定、数据访问方式和基础测试方式，避免后续模块各自形成不一致的实现风格。

## What Changes

- 创建 Java + Spring Boot 后端工程骨架。
- 使用 Maven 作为构建工具。
- 固定后端主技术栈：
  - Java 25 LTS
  - Spring Boot 4.1.x
  - Spring Web MVC
  - Spring Security
  - Spring Session Redis
  - Spring AMQP
  - Spring Data Redis
  - Liquibase
  - jOOQ
  - PostgreSQL JDBC Driver
  - Actuator + Micrometer
  - JUnit 5 + Testcontainers
- 明确不引入 JPA 作为 MVP 主数据访问方式。
- 明确 Liquibase 是 schema 管理入口，空 PostgreSQL 数据库应先由 Liquibase 创建全新 schema，再由 jOOQ 基于迁移后的 schema 生成类型安全代码。
- 明确 API 和 worker 同仓库、同依赖包、不同启动入口。
- 建立配置读取、健康检查、统一响应包络、统一错误格式和基础测试约定。
- 固定认证基础约定：
  - 用户密码使用 Argon2id 哈希。
  - 登录态使用 Spring Security Session + Redis/Spring Session + HttpOnly Cookie。
  - 前端通过 `GET /api/auth/me` 获取当前用户信息。
  - MVP 不使用 JWT 作为浏览器登录态。
- 固定凭据安全约定：
  - 基础设施密码和加密主密钥来自 `.env` 或环境变量。
  - Git/SSH 等业务凭据后续写入 `credentials` 表时必须使用应用层 AES-256-GCM 加密。
  - API、日志和审计不得输出秘密值。

## Capabilities

### New Capabilities

- `backend-app-skeleton`: 定义后端应用骨架、技术栈、构建方式、配置方式、安全基础约定、会话机制、数据访问方式和测试基础。

### Modified Capabilities

- 无。

## Impact

- `backend` 目录将新增 Java/Spring Boot 工程文件和源码目录。
- 后续数据库迁移、认证用户管理、任务运行时、项目源码环境管理等 change 都应基于该骨架开发。
- 不在本 change 中实现完整业务表迁移。
- 不在本 change 中实现完整认证用户管理 API。
- 不在本 change 中实现任务队列消费、项目、源码、环境、扫描、SBOM、报告、构建、测试或归档业务能力。
