# 任务清单

- [x] 创建 Maven Spring Boot 工程骨架。
- [x] 配置 Java 25 LTS、Spring Boot 4.1.x 和 Maven 基础依赖管理。
- [x] 引入 Spring Web MVC、Spring Security、Spring Session Redis、Spring AMQP、Spring Data Redis、Actuator、Liquibase、jOOQ、PostgreSQL JDBC、JUnit 5 和 Testcontainers 依赖。
- [x] 创建后端应用入口和基础包结构。
- [x] 创建 `application.yml`，从环境变量读取 PostgreSQL、Redis、RabbitMQ、session cookie 和凭据加密主密钥相关配置。
- [x] 配置统一响应包络和统一错误响应结构。
- [x] 创建 `GET /health` 和 `GET /api/health` 健康检查接口。
- [x] 配置 Spring Security 基础骨架，使用 session + cookie，不启用 JWT。
- [x] 配置 Argon2id 密码哈希组件。
- [x] 配置 AES-256-GCM 凭据加密组件骨架，密钥从环境变量读取。
- [x] 配置 Liquibase 基础 changelog 入口。
- [x] 配置 jOOQ codegen 基础结构或占位配置，并说明 codegen 应在 Liquibase 将空库迁移出 schema 后运行。
- [x] 创建 API 和 worker 分离启动入口或启动参数约定。
- [x] 创建基础测试，覆盖应用启动、配置绑定和健康检查。
- [x] 更新中文后端开发计划，记录已确认技术栈与工程约定。
- [x] 验证 Maven 测试命令可运行。
- [x] 验证 OpenSpec 变更。
