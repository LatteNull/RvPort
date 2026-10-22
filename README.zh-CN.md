# RvPort

[English](README.md) | 简体中文

RvPort 面向 x86 到 RISC-V 的迁移评估与实施，提供项目和源码管理、运行环境登记、依赖与代码风险分析、构建验证及迁移结果管理。

后端采用 Java 25、Spring Boot 4.1、PostgreSQL、Redis 和 RabbitMQ，通过 API 节点接收请求、worker 节点执行异步任务。对象存储保存分析制品；KB Scanner、浮点扫描器和内存序分析器提供不同类型的分析能力。前端采用 React、TypeScript 和 Vite。

## 开始使用

安装和运行步骤见 [安装指南](docs/安装指南.md)，开发、构建与测试见 [开发指南](docs/开发指南.md)。所有编译、代码生成和测试在 Docker 中执行，不要求宿主机安装 Java、Maven、Python 或 LLVM。

覆盖率统计范围见 [测试与覆盖率范围](docs/测试与覆盖率范围.md)，前端开发见 [前端说明](frontend/README.zh-CN.md)。

## 进一步阅读

- [后端 API](backend/docs/API_DESIGN.zh-CN.md)与[数据库设计](backend/docs/DATABASE_DESIGN.zh-CN.md)
- [知识扫描器](tools/kb-scanner/README.zh-CN.md)
- [浮点扫描器](tools/floating-point-precision-scanner/README.zh-CN.md)
- [内存序分析器](tools/memory-order-analyzer/README.zh-CN.md)

## 目录

| 目录或文件 | 用途 |
|---|---|
| `backend/` | API、worker、数据库迁移、生成的 jOOQ 类型及单元测试 |
| `tools/kb-scanner/` | 基于规则、构建上下文和源码证据的迁移分析 |
| `frontend/` | Web 界面、构建配置、单元测试和前端 OpenSpec |
| `tools/floating-point-precision-scanner/` | 浮点迁移风险与源码证据分析 |
| `tools/memory-order-analyzer/` | 内存序、线程及发布模式相关分析 |
| `docs/` | 安装、开发、测试和第三方来源说明 |
| `openspec/` 和各子项目的 `openspec/` | 规范、进行中的变更和历史记录 |
| `docker-compose.yml` | 前后端及基础设施编排 |
| `.env.example` | 配置模板，不包含可用于真实部署的主密钥 |

## 能力边界

分析结果依赖语言、编译选项、源码和 bitcode 的可用程度。未知、证据缺失或降级结果必须按对应工具协议解释；无风险提示不能推导为程序正确或全程序安全。

完整工具环境使用 Linux 容器与固定版本的 Clang/LLVM。生产镜像以 x86_64 工具链为基础；RISC-V 目标环境按工具说明单独准备。首次构建需要下载工具链和依赖，耗时与网络条件有关。

项目采用 [Apache License 2.0](LICENSE)，代码仓库为 [RvPort/RvPort](https://github.com/RvPort/RvPort)。第三方材料与资源授权见 [第三方来源说明](docs/第三方来源说明.md)。
