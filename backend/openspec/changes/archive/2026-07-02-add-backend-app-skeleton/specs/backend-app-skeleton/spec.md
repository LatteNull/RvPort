## ADDED Requirements

### Requirement: 后端工程使用 Java Spring Boot 技术栈
后端应用 SHALL 使用 Java 25 LTS、Spring Boot 4.1.x 和 Maven 构建工程骨架。

#### Scenario: 创建后端工程
- **WHEN** 创建后端应用骨架
- **THEN** 工程 SHALL 使用 Maven 管理构建和依赖
- **AND** 工程 SHALL 使用 Java 25 LTS
- **AND** 工程 SHALL 使用 Spring Boot 4.1.x

#### Scenario: 选择 Web 框架
- **WHEN** 实现 MVP HTTP API
- **THEN** 后端 SHALL 使用 Spring Web MVC
- **AND** MVP MUST NOT 要求使用 WebFlux

### Requirement: 后端数据访问使用 Liquibase 和 jOOQ
后端应用 SHALL 使用 Liquibase 管理 schema 变更，并 SHALL 使用 jOOQ 作为 MVP 主数据访问方式。

#### Scenario: 管理数据库 schema
- **WHEN** 新增或修改数据库结构
- **THEN** 变更 SHALL 通过 Liquibase changelog 管理
- **AND** Liquibase SHALL 是 MVP schema 变更入口

#### Scenario: 访问数据库
- **WHEN** 后端读写 PostgreSQL
- **THEN** 后端 SHALL 使用 jOOQ 表达 SQL、状态转移、聚合查询和 PostgreSQL 特性
- **AND** MVP SHOULD NOT 引入 JPA 作为主数据访问方式

#### Scenario: 生成 jOOQ 代码
- **WHEN** 空 PostgreSQL 数据库已经通过 Liquibase changelog 创建或更新 schema
- **THEN** 后端 SHALL 能基于迁移后的 PostgreSQL schema 运行 jOOQ codegen
- **AND** jOOQ codegen MUST NOT 作为 schema 创建入口

### Requirement: 后端配置通过环境变量管理
后端应用 SHALL 通过环境变量读取数据库、Redis、RabbitMQ、session cookie 和安全相关配置。

#### Scenario: 读取基础设施连接配置
- **WHEN** 后端应用启动
- **THEN** 应用 SHALL 从环境变量读取 PostgreSQL、Redis 和 RabbitMQ 连接配置
- **AND** 应用 MUST NOT 在日志中输出密码、token、私钥或加密主密钥

#### Scenario: 读取安全配置
- **WHEN** 后端应用启动
- **THEN** 应用 SHALL 从环境变量读取凭据加密主密钥配置
- **AND** 缺少必需安全配置时 SHOULD 失败启动或以明确错误提示退出

### Requirement: 浏览器登录态使用服务端 Session 和 Cookie
MVP 浏览器登录态 SHALL 使用 Spring Security Session、Spring Session Redis 和 HttpOnly Cookie，不 SHALL 使用 JWT 作为默认登录态。

#### Scenario: 用户登录
- **WHEN** 用户通过登录接口完成认证
- **THEN** 后端 SHALL 创建服务端 session
- **AND** session SHALL 存储到 Redis
- **AND** 响应 SHALL 设置 `RVPORT_SESSION` Cookie

#### Scenario: 前端获取当前用户
- **WHEN** 前端刷新页面或初始化应用状态
- **THEN** 前端 SHALL 调用 `GET /api/auth/me` 获取当前用户信息
- **AND** 未登录用户 SHALL 收到 `401` 响应

#### Scenario: 避免 JWT 作为 MVP 默认登录态
- **WHEN** 设计 MVP 浏览器认证
- **THEN** 系统 MUST NOT 要求前端保存 JWT
- **AND** 系统 MUST NOT 要求使用 JWT 完成浏览器登录态恢复

### Requirement: 密码和业务凭据必须使用不同安全策略
后端应用 SHALL 使用 Argon2id 保存用户密码哈希，并 SHALL 为 Git/SSH 等业务凭据提供应用层 AES-256-GCM 加密能力。

#### Scenario: 保存用户密码
- **WHEN** 后端保存或更新用户密码
- **THEN** 系统 SHALL 保存 Argon2id 哈希
- **AND** 系统 MUST NOT 保存明文密码
- **AND** 系统 MUST NOT 使用 SHA-256、MD5 等快哈希保存密码

#### Scenario: 加密业务凭据
- **WHEN** 后续凭据管理能力保存 Git token、Git 密码、SSH 密码、SSH 私钥或 SSH passphrase
- **THEN** 秘密载荷 SHALL 使用应用层 AES-256-GCM 加密
- **AND** 加密主密钥 SHALL 来自环境变量或后续 KMS/Vault
- **AND** API、日志和审计 MUST NOT 输出明文秘密

#### Scenario: 区分平台级秘密和业务凭据
- **WHEN** 管理 PostgreSQL、Redis、RabbitMQ 密码或凭据加密主密钥
- **THEN** 这些平台级秘密 SHALL 来自 `.env` 或环境变量
- **AND** Git/SSH 等业务凭据 MAY 写入 `credentials` 表，但秘密字段 MUST 加密保存

### Requirement: 后端骨架提供统一响应和错误格式
后端应用 SHALL 提供统一成功响应包络和统一错误响应结构，使后续 API 与既有 API 设计保持一致。

#### Scenario: 返回成功响应
- **WHEN** 健康检查或后续业务 API 请求成功
- **THEN** 响应 SHALL 包含 `data`、`traceId` 和 `timestamp`

#### Scenario: 返回错误响应
- **WHEN** 请求失败
- **THEN** 响应 SHALL 包含错误 `code`、`message`、可选 `details`、`traceId` 和 `timestamp`

### Requirement: 后端骨架提供健康检查和基础测试
后端应用 SHALL 提供最小健康检查接口和可运行的 Maven 测试命令。

#### Scenario: 调用健康检查
- **WHEN** 客户端调用 `GET /health` 或 `GET /api/health`
- **THEN** 后端 SHALL 返回统一响应包络
- **AND** 响应 SHALL 表示应用进程可用

#### Scenario: 运行测试
- **WHEN** 开发者执行 Maven 测试命令
- **THEN** 应用 SHALL 运行基础测试
- **AND** 测试 SHALL 至少覆盖应用启动、配置绑定和健康检查

### Requirement: API 和 worker 同仓库但不同启动入口
后端工程 SHALL 支持 API 和 worker 在同一仓库、同一依赖包内开发，并 SHALL 为二者保留不同启动入口或启动参数约定。

#### Scenario: 启动 API
- **WHEN** 开发者以 API 模式启动后端
- **THEN** 应用 SHALL 启动 HTTP API 能力

#### Scenario: 启动 worker
- **WHEN** 后续开发者以 worker 模式启动后端
- **THEN** 应用 SHALL 能运行异步任务消费逻辑
- **AND** worker SHALL 复用同一套配置、数据访问、日志和安全基础组件
