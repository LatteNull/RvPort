# 任务清单

- [x] 创建根目录 `docker-compose.yml`，包含 PostgreSQL、RabbitMQ、Redis 服务。
- [x] 创建根目录 `.env.example`，包含镜像版本、端口、账号密码和本地目录配置。
- [x] 确保根目录 `.env` 被 `.gitignore` 忽略。
- [x] 创建 `backend/infra/postgres/init/001_extensions.sql`，启用 `pgcrypto`。
- [x] 创建 `backend/docs/INFRASTRUCTURE.md` 中文文档。
- [x] 在文档中说明 PostgreSQL、RabbitMQ、Redis 的职责边界。
- [x] 在文档中说明 RabbitMQ 只投递 `task_id`，Redis 只作为缓存。
- [x] 验证 `docker compose config` 可以解析配置。
- [x] 验证 OpenSpec 变更。
