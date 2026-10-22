## Why

RvPort 后端已经确定使用 PostgreSQL 作为持久化事实来源、RabbitMQ 作为异步任务投递队列、Redis 作为缓存，并将完整日志、归档和上传文件保存在本地文件系统。当前还缺少一套可重复启动的本地基础设施定义，后续后端实现、迁移脚本和本地调试需要统一运行环境。

## What Changes

- 在项目根目录增加 `docker-compose.yml`，通过 Docker 启动 PostgreSQL、RabbitMQ 和 Redis。
- 在项目根目录增加 `.env.example`，将数据库账号密码、服务端口、镜像版本和本地目录等参数集中到环境变量。
- 确保根目录 `.env` 不进入版本控制。
- 使用截至 2026-07-01 的当前稳定镜像版本：
  - PostgreSQL：`postgres:18.4`
  - Redis：`redis:8.8.0`
  - RabbitMQ：`rabbitmq:4.3.2-management`
- 为 PostgreSQL 增加初始化 SQL，启用 `pgcrypto` 扩展。
- 明确 RabbitMQ 只承担任务 ID 投递，不保存任务状态、任务输入、进度或结果。
- 明确 Redis 只作为缓存，用于登录态/token、短期 nonce、限流等场景，不作为任务队列或事实来源。
- 增加 `backend/docs/INFRASTRUCTURE.md` 中文文档，说明启动方式、服务边界、环境变量和常见运维注意事项。

## Capabilities

### New Capabilities

- `backend-infrastructure`: 定义 RvPort 后端本地基础设施启动、环境变量、服务版本、队列边界、缓存边界和运行期目录约定。

### Modified Capabilities

- 无。

## Impact

- 根目录：
  - `docker-compose.yml`
  - `.env.example`
  - `.gitignore`
- `backend` 目录：
  - `backend/infra/postgres/init/*.sql`
  - `backend/docs/INFRASTRUCTURE.md`
- 不实现后端应用代码。
- 不创建数据库业务表迁移。
- 不实现 worker、API 服务或任务消费逻辑。
- 不引入 Kubernetes、Helm 或生产部署编排。
