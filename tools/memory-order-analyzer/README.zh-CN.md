# 内存序分析器

[English](README.md) | 简体中文

RvPort 的 C/C++ 内存序分析工具。使用锁定的 LLVM/Clang 21.1.8 只读消费外部 raw BC，结合可选 AST、显式 Scope、线程入口及按需函数分析，输出受限模型内的风险、源码候选和消解结果。

## 使用入口

后端使用唯一项目入口 `analyze-project`；请求、DAG、缓存/恢复和取消见 [统一项目分析](doc/UNIFIED_PROJECT_ANALYSIS.zh-CN.md)。上游负责生成 BC，扫描器不执行编译、链接、构建脚本、网络、SSH 或被分析程序。`compile_commands.json` 仅辅助源码对齐，不能替代 bundle Scope。

| 项目退出码 | 含义 |
|---|---|
| 0 | 支持模型内没有 Finding，不表示线程安全 |
| 3 | 完整受限模型内存在 risk |
| 2 | partial、unknown 或 cancelled；即使有 risk 也保留不完整状态 |
| 1 | 请求失败或全部 Scope 失败 |

AST-only 只能生成 `source-candidate` 和非空断点，不能独立建立正式 risk、消解或安全结论。P1–P3/R1–R3 保留 `safety=not_evaluated`，风险层保持 `not_established`。局部对象、同步和发布证明不等于通用 HB、data-race 检测或全程序安全证明。

## 开发与文档

运行资源按用途存放，运行时和构建过程均从这些目录读取：

| 目录 | 用途 |
|---|---|
| `protocols/` | 17 份协议定义：版本、数据类型、分析预算及 worker 通信约定 |
| `models/` | 线程入口模型，描述标准库入口及底层包装函数 |
| `config/` | 工具链版本、来源与摘要锁定配置 |
| `schemas/` | 请求、分析事实和结果的数据结构校验 |
| `cpp-thread-profiles/`、`cpp-raii-profiles/` | C++ 标准库线程与锁的识别配置 |

- [文档索引](doc/README.zh-CN.md)：按输入、语义、线程、按需分析和结果协议组织。
- [Docker 开发与质量命令](doc/development.zh-CN.md)：独立镜像、只读源码、专用输出卷及双 90% 门槛。
- [结果协议](doc/MEMORY_ORDER_FINDING_SCHEMA.zh-CN.md#doc-memory-order-finding-schema)：双语结论、证据图、源码快照与断点。

生产集成由根 `backend/Dockerfile` 构建；独立开发使用本工具 `Dockerfile.dev`。所有构建和测试在 Docker 中进行。

历史 P5 `validate-and-scale-analysis` 已完成实现与质量验收、同步主规格并归档；该历史验证仍是非全程序安全结论。
