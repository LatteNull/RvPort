## Context

自动化测试比较通过 `TestComparisonAgentRuntime` 生成中文 prompt，再由统一 Agent Adapter 启动外部 CLI。当前 Codex Adapter 将完整 prompt 放在 `ProcessBuilder` 命令参数中，通用 Adapter 对 DeepSeek Harness 和 OpenCode 也采用同一模式。后端运行镜像未声明 `LANG` 或 `LC_ALL`，实际 Worker JVM 的 `native.encoding` 与 `sun.jnu.encoding` 为 `ANSI_X3.4-1968`，导致 Java 创建子进程时把中文参数替换为 ASCII 问号。

现有进程执行器启动后立即关闭 stdin，并将 stdout、stderr 按字节块分别使用 `new String(..., UTF_8)` 解码。后一做法在 UTF-8 多字节字符跨越缓冲区边界时可能产生替换字符。问题不仅影响测试比较，也影响模型兼容性探测、KB AI 扩展和后续复用 Agent Runtime 的阶段。

## Goals / Non-Goals

**Goals:**

- 保证后端 API、Worker 及其 Agent 子进程在容器中具有一致的 UTF-8 locale。
- 为统一进程执行器增加显式、可选的 UTF-8 stdin 输入能力。
- 避免中文 prompt 通过 ASCII 原生命令参数发生不可逆替换，并降低长 prompt 触及系统命令行长度限制的风险。
- 保证 stdout、stderr 中跨读取缓冲区边界的 UTF-8 字符完整解码，同时维持现有分流与 `mergedOutput` 语义。
- 使测试比较输入、Agent 结果文件和原始输出制品明确使用 UTF-8。

**Non-Goals:**

- 不改变模型 profile、阶段绑定、Agent Runtime 管理 API 或数据库 schema。
- 不修改测试比较的业务 JSON schema、统计逻辑或提示词语义。
- 不解决第三方模型自身生成乱码、错误编码响应或不符合 JSON 契约的问题。
- 不在本 change 中升级 Agent CLI 版本。

## Decisions

### 1. 容器以 `C.UTF-8` 作为统一 locale

后端运行镜像声明 `LANG=C.UTF-8` 与 `LC_ALL=C.UTF-8`，使 JVM 启动时的 `native.encoding` 和 `sun.jnu.encoding` 为 UTF-8。API 与 Worker 使用同一镜像，因此两类进程获得相同基线；Compose 可显式保留该配置，避免部署覆盖后行为不一致。

选择 `C.UTF-8` 是因为 Ubuntu 运行镜像可直接使用，不需要额外生成区域数据。仅设置 `-Dfile.encoding=UTF-8` 不足以解决该问题，因为子进程参数转换依赖 JVM 启动时确定的原生编码。

### 2. 统一进程执行器接收可选 stdin，而不是让业务层直接操作进程流

扩展 Agent 进程执行请求，使调用方可提供可选 UTF-8 文本输入。`DefaultCodexProcessRunner` 在进程启动后以 `StandardCharsets.UTF_8` 写入 stdin 并关闭流；没有输入时保持关闭 stdin 的非交互行为。写入失败、进程提前退出和超时必须被转换为现有受控执行结果或异常，不得泄漏 prompt。

不让每个业务运行时自行写 stdin，是为了保持超时、输出收集、清理和脱敏边界集中在统一执行器中。

### 3. Adapter 决定各 CLI 的提示词传输协议

Codex Adapter 使用 Codex 非交互 stdin 协议传递 prompt，命令行仅保留 ASCII 或受控配置参数。DeepSeek Harness 与 OpenCode Adapter 在实现时通过镜像内已固定版本的 `--help` 和最小闭环测试确认其 stdin 协议；支持时使用统一 stdin，若固定版本不支持，则允许在 UTF-8 locale 基线下继续以单个命令参数传递 prompt。

无论采用哪种协议，业务运行时都只向 `AgentRuntimeAdapter` 提供 Java String，不感知 CLI 参数细节。自定义 `defaultArgs` 不得覆盖 prompt 编码与受控输入策略。

### 4. 使用有状态字符解码读取 Agent 输出

stdout 与 stderr 分别使用 UTF-8 `InputStreamReader`、`BufferedReader` 或等价的有状态 `CharsetDecoder` 读取，保证多字节字符跨底层字节缓冲区时不会被拆坏。收集器继续限制总输出大小，并保留流来源标签与观察到的输出顺序。

达到字节上限时必须在完整字符边界停止收集，不能生成半个 UTF-8 字符。输出读取期间发生异常时保留已收集内容，并沿用现有退出码判断。

### 5. Workspace 文本制品显式使用 UTF-8

测试比较输入、结果文件以及 Agent Adapter 生成的文本配置均显式指定 UTF-8。JSON 仍由 Jackson 负责结构化读写，不通过平台默认编码或文本替换处理。

### 6. 验证覆盖真实容器边界与三类单元测试

单元测试覆盖中文 prompt 正常传输、ASCII 输入、空 stdin、超长输入、中文输出跨缓冲区边界、stdout/stderr、超时和子进程提前退出。Adapter 测试验证 Codex 不再把完整 prompt 放入命令参数，并验证其他 Runtime 的选定协议。

容器验证必须检查 API 与 Worker 内 `native.encoding=UTF-8`，并至少通过一个中文 Agent probe 或测试比较闭环确认 Agent 收到原始中文且结果文件可解析。项目整体与受影响模块行覆盖率，以及工具可用时的分支覆盖率，均须达到 90%。

## Risks / Trade-offs

- [不同 Agent CLI 的 stdin 协议不一致] -> 由 Adapter 封装协议，并针对镜像内固定版本执行最小闭环验证；不支持 stdin 的 CLI 使用 UTF-8 locale 下的参数回退。
- [向已提前退出的进程写 stdin 产生异常] -> 将写入与输出读取纳入统一生命周期管理，保留进程输出并返回受控失败。
- [输出限制从字节块改为字符流后计数语义变化] -> 明确仍以 UTF-8 编码后的字节数执行总量限制，并只在完整字符边界截断。
- [只修改 Compose 无法覆盖其他部署方式] -> 将 locale 固化在运行镜像中，Compose 配置作为显式部署说明和防覆盖措施。
- [已有配置参数中包含非 ASCII 内容] -> UTF-8 locale 同时保护仍需通过命令参数传递的模型名、路径和固定版本不支持 stdin 的 prompt。

## Migration Plan

1. 扩展统一进程执行契约和测试，再迁移各 Agent Adapter。
2. 设置运行镜像 UTF-8 locale，并重新构建同供 API 与 Worker 使用的后端镜像。
3. 在容器中验证 Java 原生编码、三类 Agent CLI 版本命令和中文最小进程闭环。
4. 运行自动化测试比较或 Agent probe，确认日志不再出现由传输产生的连续问号且结构化结果可读取。
5. 若出现兼容性回归，可暂时让具体 Adapter 回退到 UTF-8 locale 下的参数传递；不得回退容器 UTF-8 locale。

## Open Questions

无。
