# root-readme-backend-guide Specification

## Purpose
TBD - created by archiving change add-root-readme-backend-guide. Update Purpose after archive.
## Requirements
### Requirement: 根 README 必须作为项目入口文档
根目录 `ReadMe.md` SHALL 作为 RvPort 项目入口文档，覆盖项目定位、目录结构、后端启动和深入文档导航。

#### Scenario: 读取项目入口
- **WHEN** 新开发者打开根目录 `ReadMe.md`
- **THEN** README SHALL 简要说明 RvPort/RISC-V Migration Service 的项目目的
- **AND** README SHALL 指向后端、本地基础设施、工具、文档和示例目录

### Requirement: 根 README 必须为前端工程预留目录
根目录 `ReadMe.md` SHALL 明确正式前端工程后续放置在根目录 `frontend/` 下。

#### Scenario: 查看项目结构
- **WHEN** README 展示项目结构
- **THEN** README SHALL 包含当前已有的 `backend/` 目录
- **AND** README SHALL 包含预留的 `frontend/` 目录说明
- **AND** README SHALL 说明正式前端工程暂未加入当前仓库
- **AND** README SHALL 区分 `frontend/` 正式工程和 `prototypes/` 原型目录

### Requirement: 根 README 必须列出后端本地开发前置软件
根目录 `ReadMe.md` SHALL 列出后端本地开发所需的软件和版本范围。

#### Scenario: 准备本地开发环境
- **WHEN** 开发者阅读前置软件章节
- **THEN** README SHALL 列出 JDK 25、Maven、Docker Compose、Git 和 PowerShell 或 bash
- **AND** README SHALL 说明后端使用 Java 25、Spring Boot 4.1.x、Maven、Liquibase 和 jOOQ

### Requirement: 根 README 必须说明基础设施启动方式
根目录 `ReadMe.md` SHALL 说明使用根目录 `docker-compose.yml` 启动 PostgreSQL、RabbitMQ 和 Redis。

#### Scenario: 启动本地基础设施
- **WHEN** 开发者需要启动本地基础设施
- **THEN** README SHALL 指导从 `.env.example` 复制 `.env`
- **AND** README SHALL 给出 `docker compose up -d` 命令
- **AND** README SHALL 给出查看服务状态和停止服务的命令
- **AND** README MUST NOT 包含真实本地密码或秘密

#### Scenario: 理解基础设施职责
- **WHEN** 开发者阅读基础设施章节
- **THEN** README SHALL 说明 PostgreSQL 是权威持久化数据库
- **AND** README SHALL 说明 RabbitMQ 用于异步任务投递
- **AND** README SHALL 说明 Redis 用于 session 和缓存

### Requirement: 根 README 必须说明后端初始化和启动方式
根目录 `ReadMe.md` SHALL 说明后端数据库初始化、API 启动和 worker mode 启动方式。

#### Scenario: 初始化数据库
- **WHEN** 开发者首次使用空数据库
- **THEN** README SHALL 说明通过 `RVPORT_LIQUIBASE_ENABLED=true` 运行 Liquibase 初始化 schema
- **AND** README SHALL 说明默认超级管理员账号为 `admin`
- **AND** README SHALL 说明默认密码为 `admin123`

#### Scenario: 启动后端 API
- **WHEN** 开发者启动后端 API
- **THEN** README SHALL 给出进入 `backend` 目录并运行 `mvn spring-boot:run` 的命令
- **AND** README SHALL 给出健康检查地址

#### Scenario: 启动 worker mode
- **WHEN** 开发者需要启动 worker 消费任务队列
- **THEN** README SHALL 说明设置 `RVPORT_WORKER_ENABLED=true`
- **AND** README SHALL 给出避免占用固定 API 端口的启动示例
- **AND** README SHALL 简要说明 worker 会消费 RabbitMQ、读取 PostgreSQL 任务并写回任务事件

### Requirement: 根 README 必须说明测试和 jOOQ 生成方式
根目录 `ReadMe.md` SHALL 说明后端测试命令和 schema 变更后的 jOOQ 代码生成流程。

#### Scenario: 运行后端测试
- **WHEN** 开发者需要验证后端
- **THEN** README SHALL 给出 `mvn test` 命令
- **AND** README SHALL 说明迁移验证测试默认跳过，需真实数据库时显式启用

#### Scenario: 生成 jOOQ 代码
- **WHEN** 开发者修改 Liquibase schema
- **THEN** README SHALL 说明普通 Maven 构建不会自动生成 jOOQ
- **AND** README SHALL 给出 Windows `backend/scripts/generate-jooq.ps1` 命令
- **AND** README SHALL 给出 Linux/macOS `backend/scripts/generate-jooq.sh` 命令
- **AND** README SHALL 说明 jOOQ 生成应在 Liquibase 迁移完成的数据库上运行

### Requirement: 根 README 必须链接深入文档
根目录 `ReadMe.md` SHALL 将详细设计内容链接到已有后端文档，而不是在根 README 中重复展开。

#### Scenario: 查找详细设计
- **WHEN** 开发者需要 API、数据库、基础设施或开发计划详情
- **THEN** README SHALL 链接 `backend/docs/API_DESIGN.md`
- **AND** README SHALL 链接 `backend/docs/DATABASE_DESIGN.md`
- **AND** README SHALL 链接 `backend/docs/INFRASTRUCTURE.md`
- **AND** README SHALL 链接 `backend/docs/BACKEND_DEVELOPMENT_PLAN.md`
