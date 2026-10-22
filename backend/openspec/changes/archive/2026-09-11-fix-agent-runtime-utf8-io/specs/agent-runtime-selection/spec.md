## ADDED Requirements

### Requirement: Agent Runtime 输入输出必须保持 UTF-8 字符完整性
后端 SHALL 在统一 Agent Runtime 执行边界以 UTF-8 传递文本输入并解码文本输出，任何受支持 Agent Adapter MUST NOT 因平台默认编码或读取缓冲区边界损坏非 ASCII 内容。

#### Scenario: Codex 接收中文提示词
- **WHEN** 业务阶段通过 Codex Adapter 提交包含中文的 prompt
- **THEN** Adapter SHALL 通过 Codex 支持的非交互输入协议以 UTF-8 提交完整 prompt
- **AND** 完整 prompt MUST NOT 作为依赖平台默认原生编码的命令行参数传递
- **AND** Codex 接收到的 Unicode 内容 SHALL 与业务阶段生成的内容一致

#### Scenario: 其他 Agent 接收中文提示词
- **WHEN** 业务阶段通过 DeepSeek Harness、OpenCode 或后续受支持 Adapter 提交包含中文的 prompt
- **THEN** Adapter SHALL 优先通过该 CLI 支持的非交互 stdin 协议以 UTF-8 传递 prompt
- **AND** 固定 CLI 版本不支持 stdin 时，Adapter SHALL 仅在已验证的 UTF-8 原生编码环境中通过受控参数传递
- **AND** Agent 接收到的 Unicode 内容 SHALL 与业务阶段生成的内容一致

#### Scenario: prompt 为空或仅包含 ASCII
- **WHEN** Agent 执行请求不包含 stdin 内容或 prompt 仅包含 ASCII
- **THEN** 统一进程执行器 SHALL 正确关闭 stdin 并保持非交互执行
- **AND** 现有 ASCII Agent 调用行为 SHALL NOT 因 UTF-8 支持而改变

#### Scenario: 中文输出跨读取缓冲区边界
- **WHEN** Agent stdout 或 stderr 中的 UTF-8 多字节字符跨越底层读取缓冲区边界
- **THEN** 后端 SHALL 使用有状态 UTF-8 解码保留完整字符
- **AND** stdout、stderr 与 `mergedOutput` MUST NOT 因分块解码产生替换字符或问号

#### Scenario: 达到 Agent 输出上限
- **WHEN** Agent 输出达到统一收集大小上限
- **THEN** 后端 SHALL 在完整 UTF-8 字符边界停止收集
- **AND** 已收集的 stdout、stderr 与 `mergedOutput` SHALL 保持可解码

#### Scenario: stdin 写入期间 Agent 提前退出
- **WHEN** Agent 在 UTF-8 prompt 写入完成前退出或关闭 stdin
- **THEN** 后端 SHALL 返回受控执行失败并保留已产生的脱敏输出
- **AND** 错误信息 MUST NOT 包含完整 prompt、API key 或授权头

#### Scenario: Workspace 文本文件读写
- **WHEN** Agent 业务阶段生成输入 JSON、读取结果 JSON 或写入 Agent 文本配置
- **THEN** 后端 SHALL 显式使用 UTF-8 编码
- **AND** 文件读写 MUST NOT 依赖宿主机或容器的平台默认编码
