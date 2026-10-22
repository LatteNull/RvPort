## ADDED Requirements

### Requirement: 后端容器必须提供 UTF-8 原生运行环境
后端运行镜像 SHALL 为 API、Worker 及其子进程提供一致的 UTF-8 locale，使 JVM 原生编码和 Agent CLI 文本边界支持完整 Unicode 内容。

#### Scenario: 启动 API 容器
- **WHEN** 使用后端运行镜像启动 API 进程
- **THEN** 容器 SHALL 设置有效的 UTF-8 `LANG` 和 `LC_ALL`
- **AND** JVM `native.encoding` 与 `sun.jnu.encoding` SHALL 为 UTF-8

#### Scenario: 启动 Worker 容器
- **WHEN** 使用同一后端运行镜像启动 Worker 进程
- **THEN** 容器 SHALL 设置与 API 进程相同的 UTF-8 locale
- **AND** Worker 启动的 Codex、DeepSeek Harness 和 OpenCode 子进程 SHALL 继承 UTF-8 locale

#### Scenario: 容器内执行中文子进程参数闭环
- **WHEN** 后端容器内的 JVM 启动子进程并传递非 ASCII 受控参数
- **THEN** 子进程接收到的 Unicode 内容 SHALL 与 Java 原始字符串一致
- **AND** 镜像验证 MUST NOT 仅检查 `file.encoding` 而忽略原生编码
