## Context

根目录 `ReadMe.md` 当前来自交付包生成说明，主要列出 `docs/`、`tools/`、`demos/` 等目录，没有覆盖本地开发者最需要的后端启动路径。后端已经具备 Spring Boot 工程、Docker Compose 基础设施、Liquibase schema、jOOQ 代码生成脚本、认证、任务队列和 worker 主干，因此根 README 需要成为新开发者的第一入口。

同时，正式前端工程还没有加入当前仓库，但后续会以根目录 `frontend/` 与 `backend/` 并列。因此 README 的项目结构不能只描述现状，也要明确 `frontend/` 是预留目录，避免未来接入时文档结构再大改。

## Goals / Non-Goals

**Goals:**

- 将根 README 改造成项目入口文档。
- 说明当前目录结构，并为未来 `frontend/` 预留清晰位置。
- 说明后端技术栈、本地前置软件和基础设施服务。
- 给出 `.env` 配置、Docker Compose 启停、数据库初始化、API 启动、worker 启动、测试和 jOOQ 代码生成命令。
- 链接深入文档，避免根 README 复制完整设计内容。

**Non-Goals:**

- 不修改后端代码、Docker Compose、`.env.example` 或数据库迁移。
- 不编写前端启动方式，因为正式前端工程尚未加入仓库。
- 不在根 README 中展开完整 API、数据库或基础设施设计。
- 不提交真实 `.env` 内容或任何本地密码。

## Decisions

### 1. README 使用“快速上手优先”的结构

根 README SHALL 先回答新开发者最常见的问题：

```text
需要装什么
如何启动基础设施
如何初始化数据库
如何启动 API
如何启动 worker
如何运行测试
schema 变化后如何生成 jOOQ
```

原因：根 README 是入口文档，不是设计文档。详细边界继续链接到 `backend/docs/API_DESIGN.md`、`backend/docs/DATABASE_DESIGN.md`、`backend/docs/INFRASTRUCTURE.md` 和 `backend/docs/BACKEND_DEVELOPMENT_PLAN.md`。

### 2. 项目结构同时表达现状和前端预留

README SHALL 明确：

- `backend/` 当前存在并承载 Java Spring Boot 后端。
- `frontend/` 暂未加入当前仓库，后续作为正式 Web UI 工程位置。
- `prototypes/` 是原型或交互验证，不等同于正式前端工程。

原因：用户已经明确后续会加入前端项目，现在需要避免 README 让读者误以为没有前端规划。

### 3. 启动命令以 Windows PowerShell 为主，同时保留 bash 提示

当前开发环境主要在 Windows，但仓库也包含 Linux/macOS jOOQ 脚本。README SHALL 优先给出 PowerShell 命令，并在 jOOQ 生成等跨平台位置补充 bash 命令。

原因：这能贴合当前开发者环境，同时不排斥 Linux/macOS 开发者。

### 4. README 只引用 `.env.example`，不写真实本地秘密

README SHALL 使用 `change_me` 或占位说明，不复制当前 `.env` 中的真实密码。数据库、RabbitMQ、Redis、凭据主密钥等配置均指向 `.env.example`。

原因：根 README 会提交到版本控制，不能泄露本地秘密。

### 5. worker mode 作为独立小节说明

README SHALL 说明 API 和 worker 使用同一后端代码包，通过 `RVPORT_WORKER_ENABLED=true` 开启 worker 消费逻辑。为避免和 API 端口冲突，README SHALL 给出 `--server.port=0` 示例。

原因：当前 worker 已经可横向多实例消费 RabbitMQ 队列，这是后端启动方式的重要组成。

## Risks / Trade-offs

- [风险] README 内容过长，后续维护成本高。→ 只保留启动和导航信息，详细设计链接到 `backend/docs`。
- [风险] 前端尚未加入，过度描述会造成误导。→ 明确 `frontend/` 是预留目录，暂不提供前端启动命令。
- [风险] 复制真实 `.env` 信息会泄露秘密。→ README 只引用 `.env.example` 和占位值。
- [风险] Liquibase 初始化命令可能被误用于日常启动。→ 明确首次空库或需要迁移时才开启 `RVPORT_LIQUIBASE_ENABLED=true`。
- [风险] jOOQ 生成被误认为每次构建自动执行。→ 明确普通 `mvn test/package` 只编译已提交生成代码，schema 变更后才运行生成脚本。

## Migration Plan

1. 重写根目录 `ReadMe.md`。
2. 保留原目录说明中的有效内容，并加入 `backend/` 和预留 `frontend/`。
3. 根据 `.env.example`、`docker-compose.yml` 和 `backend/docs` 补充命令。
4. 检查 README 不包含真实 `.env` 秘密。
5. 检查链接路径和命令路径从仓库根目录执行时有效。

## Open Questions

- 后续正式前端工程加入后，是否需要将 README 拆分为根 README、`backend/README.md` 和 `frontend/README.md` 三层。
