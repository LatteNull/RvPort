## 1. README 内容重写

- [x] 1.1 重写根目录 `ReadMe.md` 的标题、项目简介和目录结构说明。
- [x] 1.2 在目录结构中加入当前已有 `backend/`，并预留 `frontend/`，说明正式前端工程暂未加入。
- [x] 1.3 区分 `frontend/` 正式前端工程和 `prototypes/` 原型目录。
- [x] 1.4 增加后端技术栈和本地开发前置软件清单。

## 2. 后端启动和基础设施说明

- [x] 2.1 增加 `.env.example` 复制为 `.env` 的说明，并提醒 `.env` 不应提交。
- [x] 2.2 增加 Docker Compose 启动、查看状态、停止和谨慎清理数据卷命令。
- [x] 2.3 增加 PostgreSQL、RabbitMQ 和 Redis 的职责说明与常用端口。
- [x] 2.4 增加首次数据库初始化和默认管理员账号说明。
- [x] 2.5 增加后端 API 启动和健康检查说明。
- [x] 2.6 增加 worker mode 启动方式和 `RVPORT_WORKER_ENABLED=true` 说明。

## 3. 测试、jOOQ 和文档导航

- [x] 3.1 增加 `mvn test` 后端测试命令，并说明迁移测试默认跳过。
- [x] 3.2 增加 jOOQ 代码生成说明，覆盖 Windows 和 Linux/macOS 脚本。
- [x] 3.3 增加常用本地地址清单。
- [x] 3.4 增加 `backend/docs` 下 API、数据库、基础设施和开发计划文档链接。

## 4. 校验和收尾

- [x] 4.1 检查 README 中所有命令路径从仓库根目录或标注目录执行时清晰有效。
- [x] 4.2 检查 README 不包含真实 `.env` 密码、token 或凭据主密钥。
- [x] 4.3 检查 README 内容为中文，命令、路径、字段名和环境变量保留英文。
- [x] 4.4 检查 OpenSpec 状态，确认 change 可以进入 apply 阶段。
