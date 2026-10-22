## Why

后端 Worker 容器未设置 UTF-8 locale，JVM 的 `native.encoding` 实际为 ASCII；Agent Adapter 又将中文提示词作为子进程命令行参数传递，导致提示词在进入 Agent CLI 前被不可逆地替换为 `?`。该问题已经影响自动化测试结果比较，并同样威胁所有复用统一 Agent Runtime 的业务阶段，因此需要统一修复 Agent 进程的 UTF-8 输入输出边界。

## What Changes

- 为后端运行镜像以及 API、Worker 进程建立明确的 UTF-8 locale，保证 JVM 与子进程使用 UTF-8 原生编码。
- 扩展统一 Agent 进程执行契约，允许 Adapter 通过 stdin 以 UTF-8 传递提示词，避免中文命令行参数损坏和超长提示词触及系统参数长度限制。
- 调整 Codex、DeepSeek Harness、OpenCode Adapter，使其按各 CLI 支持的方式使用受控 UTF-8 输入；不支持 stdin 的运行时仍须在 UTF-8 locale 下安全传递参数。
- 使用有状态 UTF-8 解码读取 stdout、stderr，避免多字节字符跨读取缓冲区边界时产生替换字符，同时保持 `mergedOutput` 的现有语义。
- 明确比较输入、结果文件与 Agent 原始输出的 UTF-8 文件编码。
- 补充正常流程、异常流程和边界条件单元测试，并执行项目及受影响模块的覆盖率检查，行覆盖率与可用时的分支覆盖率均不得低于 90%。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `agent-runtime-selection`: Agent Runtime 的统一执行契约增加 UTF-8 提示词输入、UTF-8 输出解码和跨缓冲区字符完整性要求。
- `backend-infrastructure`: 后端容器增加 UTF-8 locale 要求，确保 API 与 Worker 进程及其子进程具有一致的 UTF-8 原生编码。

## Impact

- 影响统一 Agent Runtime Adapter、Agent 子进程运行器、自动化测试比较和 KB AI 扩展等调用 Agent 的业务阶段。
- 影响后端 Docker 运行镜像及 `docker-compose.yml` 中 API、Worker 的运行环境。
- 可能调整 `CodexProcessRunner` 等内部接口以接收可选 stdin，不改变外部 HTTP API 和数据库 schema。
- 需要重新构建后端镜像，并在独立 API/Worker 容器部署下验证中文提示词、中文输出和结构化结果文件。
