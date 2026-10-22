## Why

根目录 `ReadMe.md` 目前仍是交付包目录说明，缺少后端开发者第一次启动项目所需的软件依赖、基础设施启动、数据库初始化、API/worker 启动和测试说明。后端基础能力已经逐步落地，现在需要把根 README 升级为项目入口文档，并为后续前端工程加入预留清晰位置。

## What Changes

- 重写根目录 `ReadMe.md`，保留项目说明和目录导航，同时补充后端本地开发启动指南。
- 明确当前已有目录和后续预留 `frontend/` 目录，说明正式前端工程暂未加入当前仓库。
- 增加本地开发前置软件清单：JDK 25、Maven、Docker Compose、Git、PowerShell/bash。
- 增加 `.env.example` 到 `.env` 的配置流程和关键环境变量说明。
- 增加基础设施启动、停止、状态查看和清理提醒。
- 增加数据库初始化、默认管理员、后端 API 启动、worker mode 启动、测试和 jOOQ 代码生成说明。
- 增加常用本地地址和深入文档链接。

## Capabilities

### New Capabilities
- `root-readme-backend-guide`: 规定根 README 作为项目入口文档时必须覆盖的后端启动、基础设施、前端预留和文档导航内容。

### Modified Capabilities

## Impact

- 影响根目录 `ReadMe.md`。
- 不修改后端应用代码、数据库 schema、Docker Compose 配置或 OpenSpec 后端主规格。
- 后续前端工程加入时，可在根 README 的预留 `frontend/` 小节下继续扩展前端启动方式。
