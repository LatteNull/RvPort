## ADDED Requirements

### Requirement: 本地基础设施通过 Docker Compose 启动
RvPort SHALL 提供根目录 `docker-compose.yml`，用于启动后端 MVP 所需的 PostgreSQL、RabbitMQ 和 Redis 基础设施。

#### Scenario: 开发者启动基础设施
- **WHEN** 开发者在项目根目录运行 Docker Compose 启动命令
- **THEN** Compose 配置 SHALL 启动 PostgreSQL、RabbitMQ 和 Redis 服务
- **AND** 这些服务 SHALL 位于同一个 Compose 网络内

#### Scenario: 后端服务按服务名访问基础设施
- **WHEN** 后续 API 或 worker 容器加入同一 Compose 网络
- **THEN** 它们 SHALL 能通过 `postgres`、`rabbitmq` 和 `redis` 服务名访问对应基础设施

### Requirement: 基础设施配置通过环境变量管理
Docker Compose 配置 SHALL 通过根目录 `.env` 读取本地私有配置，并 SHALL 提供 `.env.example` 作为可提交模板。

#### Scenario: 提供配置模板
- **WHEN** 开发者首次配置本地环境
- **THEN** 根目录 `.env.example` SHALL 包含数据库、队列、缓存、端口和本地目录相关变量
- **AND** `.env.example` MUST NOT 包含真实密码

#### Scenario: 保护本地私有配置
- **WHEN** 开发者填写真实基础设施密码或本地路径
- **THEN** 这些值 SHALL 写入根目录 `.env`
- **AND** `.env` MUST 被版本控制忽略

### Requirement: PostgreSQL 使用当前稳定版本并启用 pgcrypto
基础设施 SHALL 使用 PostgreSQL 当前稳定镜像，并 SHALL 为后端数据库启用 `pgcrypto` 扩展。

#### Scenario: 启动 PostgreSQL
- **WHEN** Compose 启动 PostgreSQL 服务
- **THEN** 服务 SHALL 使用 `postgres:18.4`
- **AND** 数据 SHALL 持久化到命名卷
- **AND** 容器内数据卷挂载点 SHALL 覆盖 `/var/lib/postgresql`

#### Scenario: 初始化数据库扩展
- **WHEN** PostgreSQL 初始化脚本执行
- **THEN** 初始化脚本 SHALL 执行 `CREATE EXTENSION IF NOT EXISTS pgcrypto`
- **AND** 该脚本 SHALL 可重复执行

### Requirement: RabbitMQ 作为异步任务投递队列
基础设施 SHALL 使用 RabbitMQ 作为异步任务投递队列，并 SHALL 保持队列载荷最小化。

#### Scenario: 启动 RabbitMQ
- **WHEN** Compose 启动 RabbitMQ 服务
- **THEN** 服务 SHALL 使用 `rabbitmq:4.3.2-management`
- **AND** SHALL 暴露 AMQP 端口和本地管理界面端口
- **AND** RabbitMQ 用户、密码和 vhost SHALL 从环境变量读取

#### Scenario: 投递任务消息
- **WHEN** 后端 API 创建长任务并投递队列
- **THEN** RabbitMQ 消息载荷 SHALL 只包含 `task_id` 和必要路由信息
- **AND** RabbitMQ MUST NOT 作为任务输入、任务状态、任务进度、任务结果或日志的事实来源

### Requirement: Redis 作为缓存而不是事实来源
基础设施 SHALL 使用 Redis 作为缓存和短期状态存储，但 SHALL NOT 作为业务事实来源。

#### Scenario: 启动 Redis
- **WHEN** Compose 启动 Redis 服务
- **THEN** 服务 SHALL 使用 `redis:8.8.0`
- **AND** Redis 端口和密码 SHALL 从环境变量读取

#### Scenario: 使用 Redis 缓存
- **WHEN** 后端需要缓存登录态、token、短期 nonce 或限流计数
- **THEN** 后端 MAY 使用 Redis 保存这些短期数据
- **AND** Redis 数据失效或丢失 MUST NOT 破坏 PostgreSQL 中的权威业务状态

#### Scenario: 避免 Redis 承载任务事实
- **WHEN** 任务状态、任务事件、任务结果或审计记录需要保存
- **THEN** 系统 MUST 使用 PostgreSQL 作为事实来源
- **AND** 系统 MUST NOT 依赖 Redis 作为任务队列

### Requirement: 本地运行期文件目录可配置
基础设施配置 SHALL 为日志、归档和上传文件提供可配置的本地目录变量。

#### Scenario: 配置本地日志目录
- **WHEN** 开发者复制 `.env.example` 创建 `.env`
- **THEN** 配置 SHALL 包含 `RVPORT_LOG_DIR`、`RVPORT_ARCHIVE_DIR` 和 `RVPORT_UPLOAD_DIR`
- **AND** 默认值 SHALL 指向 `backend/runtime` 下的对应目录

#### Scenario: 保存完整任务日志
- **WHEN** 后续 worker 写入完整 stdout 或 stderr 日志
- **THEN** 日志 SHOULD 写入 `RVPORT_LOG_DIR` 指向的目录
- **AND** PostgreSQL 只保存日志元数据和摘要

### Requirement: 基础设施文档使用中文说明边界
RvPort SHALL 在 `backend/docs/INFRASTRUCTURE.md` 维护中文基础设施文档，说明启动方式、环境变量和服务职责边界。

#### Scenario: 阅读基础设施文档
- **WHEN** 开发者查看 `backend/docs/INFRASTRUCTURE.md`
- **THEN** 文档 SHALL 说明如何复制 `.env.example`、如何启动和停止 Docker Compose
- **AND** 文档 SHALL 说明 PostgreSQL、RabbitMQ 和 Redis 的职责边界
- **AND** 文档 SHALL 说明 `.env` 不应提交到版本控制
