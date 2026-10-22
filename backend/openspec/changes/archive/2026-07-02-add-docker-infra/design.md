# 设计：Docker 基础设施启动

## 目标

为 RvPort 后端提供一套可重复、本地友好的基础设施启动方式，使开发者可以通过根目录 `docker-compose.yml` 启动数据库、缓存和队列，并通过 `.env` 管理敏感参数和端口配置。

## 架构概览

```text
┌─────────────────────────────────────────────────────────┐
│                    docker-compose.yml                    │
├─────────────────────┬─────────────────┬─────────────────┤
│ PostgreSQL 18.4      │ RabbitMQ 4.3.2   │ Redis 8.8.0      │
│ 持久化事实来源       │ 任务 ID 投递队列 │ 缓存与短期状态    │
├─────────────────────┼─────────────────┼─────────────────┤
│ tasks                │ task_id message │ login/session    │
│ task_events          │ routing only    │ nonce/rate limit │
│ users/projects/...   │ no task state   │ no source truth  │
└─────────────────────┴─────────────────┴─────────────────┘
```

任务流边界：

```text
API
 ├─ 1. 写入 PostgreSQL tasks 记录
 ├─ 2. 向 RabbitMQ 投递 task_id
 ▼
Worker
 ├─ 3. 从 RabbitMQ 消费 task_id
 ├─ 4. 从 PostgreSQL 读取任务输入快照
 └─ 5. 将状态、事件、结果和日志元数据写回 PostgreSQL
```

## 服务设计

### PostgreSQL

- 镜像：`postgres:18.4`
- 用途：后端 MVP 权威持久化数据库。
- 数据卷：挂载到容器内 `/var/lib/postgresql`。
- 原因：PostgreSQL 18 官方 Docker 镜像的默认 `PGDATA` 位于 `/var/lib/postgresql/18/docker`，将卷挂载到 `/var/lib/postgresql` 可以覆盖完整版本化数据目录。
- 初始化脚本目录：`backend/infra/postgres/init`
- 初始化要求：
  - 启用 `pgcrypto`。
  - 初始化脚本必须可重复执行。
  - 业务表迁移不属于本变更。
- 健康检查：使用 `pg_isready` 检查数据库可连接性。

### RabbitMQ

- 镜像：`rabbitmq:4.3.2-management`
- 用途：异步任务投递队列。
- 端口：
  - AMQP：默认 `5672`
  - 管理界面：默认 `15672`
- 队列边界：
  - 消息载荷只包含 `task_id` 和必要路由信息。
  - 不保存任务输入、状态、进度、结果或日志。
  - worker 必须以 PostgreSQL 中的任务记录作为事实来源。
- 数据卷：挂载 RabbitMQ 持久化数据目录，避免本地重启丢失队列定义和用户配置。

### Redis

- 镜像：`redis:8.8.0`
- 用途：缓存和短期状态。
- 典型场景：
  - 登录态或 token 缓存。
  - 短期 nonce。
  - 限流计数。
  - 轻量级前端会话辅助数据。
- 明确限制：
  - 不作为任务状态事实来源。
  - 不作为任务队列。
  - 不保存必须审计或长期追溯的业务结果。
- 数据卷：挂载 `/data`，支持本地缓存恢复。
- 安全：通过 `.env` 设置 `REDIS_PASSWORD`。

## 环境变量设计

根目录 `.env.example` 应包含以下变量：

```dotenv
COMPOSE_PROJECT_NAME=rvport

POSTGRES_IMAGE=postgres:18.4
POSTGRES_DB=rvport
POSTGRES_USER=rvport
POSTGRES_PASSWORD=change_me
POSTGRES_PORT=5432

RABBITMQ_IMAGE=rabbitmq:4.3.2-management
RABBITMQ_DEFAULT_USER=rvport
RABBITMQ_DEFAULT_PASS=change_me
RABBITMQ_DEFAULT_VHOST=rvport
RABBITMQ_AMQP_PORT=5672
RABBITMQ_MANAGEMENT_PORT=15672

REDIS_IMAGE=redis:8.8.0
REDIS_PASSWORD=change_me
REDIS_PORT=6379

RVPORT_LOG_DIR=./backend/runtime/logs
RVPORT_ARCHIVE_DIR=./backend/runtime/archives
RVPORT_UPLOAD_DIR=./backend/runtime/uploads
```

`.env` 包含真实密码和本地私有配置，必须被忽略；`.env.example` 只保留占位值。

## 卷和网络

建议的命名卷：

- `rvport-postgres-data`
- `rvport-rabbitmq-data`
- `rvport-redis-data`

建议的网络：

- `rvport-infra`

所有基础设施服务应位于同一 Compose 网络中，后续 API 和 worker 可以通过服务名访问：

- PostgreSQL：`postgres`
- RabbitMQ：`rabbitmq`
- Redis：`redis`

## 本地文件目录

基础设施配置应为以下本地目录预留环境变量：

- 日志目录：`backend/runtime/logs`
- 日志每日归档目录：`backend/runtime/archives`
- 上传目录：`backend/runtime/uploads`

这些目录承载运行期数据，不应作为 OpenSpec 或源代码文档的一部分提交实际内容。

## 安全与默认值

- `.env` 不提交到版本控制。
- `.env.example` 只使用占位密码。
- RabbitMQ 管理界面只用于本地开发，生产环境不应直接暴露。
- PostgreSQL、Redis、RabbitMQ 的默认端口可以通过 `.env` 改写，避免本地冲突。
- 初始化默认超级管理员属于数据库/应用初始化脚本职责，不在 Docker Compose 中保存明文业务用户密码。

## 风险和后续决策

- 固定最新稳定版本可以提高可重复性，但后续需要定期评估镜像升级。
- Redis 8.x 的许可证和分发策略应在商业分发前复核；MVP 本地开发阶段先按用户要求使用 Redis 最新稳定版本。
- RabbitMQ management 镜像便于调试，但生产环境可能需要切换到不带 management 插件或限制访问。
- PostgreSQL 18 的 Docker 数据目录与早期版本不同，迁移旧卷时需要单独处理。

## 版本依据

- PostgreSQL：官方发布说明显示 18 系列为当前稳定主线，18.4 为当前小版本。
- Redis：官方 Redis Open Source release notes 显示 8.8.0 为当前稳定版本。
- RabbitMQ：官方下载页显示 4.3.2 为当前发布版本。
