## Purpose

定义后端 Agent Runtime 的选择、执行和输出边界，使测试结果比较阶段可以在 Codex、DeepSeek Harness、OpenCode 等不同 agent 之间切换，同时保持模型密钥、命令参数、工作目录和输出制品的安全约束。

## Requirements

### Requirement: 后端必须提供可选 Agent Runtime
后端 SHALL 支持多个 agent runtime，并 SHALL 至少提供 `CODEX`、`DEEPSEEK_HARNESS` 和 `OPENCODE` 三种可选 agent 类型。

#### Scenario: 初始化默认 agent runtime
- **WHEN** 执行数据库迁移或应用初始化
- **THEN** 后端 SHALL 创建或保留 `CODEX`、`DEEPSEEK_HARNESS` 和 `OPENCODE` 三类 agent runtime 配置
- **AND** 每个 runtime SHALL 包含 agent 类型、展示名称、可执行路径、启用状态和安全摘要
- **AND** 初始化过程 SHALL 可重复执行

#### Scenario: 查询 agent runtime 列表
- **WHEN** 超级管理员打开模型或阶段配置页面
- **THEN** 后端 SHALL 提供 agent runtime 列表
- **AND** 列表项 SHALL 包含 runtime ID、agent 类型、展示名称、启用状态、可执行路径摘要、最近探测状态和最近探测时间
- **AND** 响应 MUST NOT 返回完整命令、API key、授权头、完整 prompt 或服务器真实敏感路径

#### Scenario: 查询 agent runtime 详情
- **WHEN** 超级管理员查询单个 agent runtime
- **THEN** 后端 SHALL 返回该 runtime 的配置摘要、支持阶段、最近探测结果和可用性状态
- **AND** 响应 MUST NOT 返回明文密钥或完整命令行

### Requirement: Agent Runtime 必须通过统一 Adapter 执行
后端 SHALL 通过统一 agent adapter 接口执行不同 agent，业务运行时 MUST NOT 直接拼接某个 agent 的专用命令。

#### Scenario: 执行 Codex agent
- **WHEN** 阶段绑定选择 `CODEX`
- **THEN** 后端 SHALL 使用 Codex adapter 构造受控命令并传入模型 profile
- **AND** adapter SHALL 在专用 workspace 中执行任务

#### Scenario: 执行 DeepSeek Harness agent
- **WHEN** 阶段绑定选择 `DEEPSEEK_HARNESS`
- **THEN** 后端 SHALL 使用 DeepSeek Harness adapter 构造受控命令并传入模型 profile
- **AND** adapter SHALL 在专用 workspace 中执行任务

#### Scenario: 执行 OpenCode agent
- **WHEN** 阶段绑定选择 `OPENCODE`
- **THEN** 后端 SHALL 使用 OpenCode adapter 构造受控命令并传入模型 profile
- **AND** adapter SHALL 在专用 workspace 中执行任务

#### Scenario: Agent 类型未支持
- **WHEN** 阶段绑定引用后端未注册 adapter 的 agent 类型
- **THEN** 后端 SHALL 返回明确业务错误
- **AND** 后端 MUST NOT 尝试执行任意外部命令

### Requirement: Agent 输出必须保留合并输出
后端 SHALL 为所有 agent adapter 生成统一执行结果，其中 `mergedOutput` 必须表达 stdout 和 stderr 按真实产生顺序交织后的完整输出。

#### Scenario: 记录 stdout stderr 顺序
- **WHEN** agent 进程同时产生 stdout 和 stderr
- **THEN** 后端 SHALL 分别保存 stdout 和 stderr
- **AND** 后端 SHALL 生成 `mergedOutput`
- **AND** `mergedOutput` SHALL 保留输出事件顺序和流来源标签

#### Scenario: agent 执行失败
- **WHEN** agent 进程退出码非 0、超时或被中断
- **THEN** 后端 SHALL 使用脱敏后的 `mergedOutput` 生成失败摘要
- **AND** 错误响应和任务事件 MUST NOT 泄漏 API key、授权头、完整 prompt 或服务器真实敏感路径

#### Scenario: agent 输出保存
- **WHEN** 业务需要保存原始 agent 输出 artifact
- **THEN** 后端 SHALL 优先保存包含 `stdout`、`stderr`、`mergedOutput`、`exitCode` 和 `timedOut` 的结构化输出
- **AND** 保存前 SHALL 对密钥和授权头做脱敏处理

### Requirement: Agent Runtime 选择必须仅用于受控阶段
后端 SHALL 只允许已声明阶段使用 agent runtime，当前允许 `TEST_LOG_COMPARE` 和 `KB_AI_EXTENSION` 阶段绑定 agent runtime。

#### Scenario: 保存 TEST_LOG_COMPARE agent 绑定
- **WHEN** 超级管理员保存 `TEST_LOG_COMPARE` 阶段绑定
- **THEN** 请求 SHALL 同时指定已启用模型 profile 和已启用 agent runtime
- **AND** 后端 SHALL 保存该阶段到模型 profile 和 agent runtime 的唯一绑定

#### Scenario: 保存 KB_AI_EXTENSION agent 绑定
- **WHEN** 超级管理员保存 `KB_AI_EXTENSION` 阶段绑定
- **THEN** 请求 SHALL 同时指定已启用模型 profile 和已启用 agent runtime
- **AND** 后端 SHALL 保存该阶段到模型 profile 和 agent runtime 的唯一绑定

#### Scenario: 绑定未知阶段
- **WHEN** 请求绑定未知阶段或非本 change 允许阶段
- **THEN** 后端 SHALL 返回统一参数错误
- **AND** 后端 MUST NOT 保存部分绑定

#### Scenario: 绑定禁用 agent
- **WHEN** 请求绑定已禁用或不存在的 agent runtime
- **THEN** 后端 SHALL 拒绝绑定
- **AND** 响应 MUST NOT 泄漏内部命令路径或配置细节

### Requirement: Agent Runtime Probe 必须支持按模型 Profile 批量执行
后端 agent runtime 选择能力 SHALL 支持模型 profile 针对多个指定 agent runtime 执行阶段无关的通用兼容性 probe，并 SHALL 使用统一 adapter 返回一致的分项结果。

#### Scenario: 按 Runtime 列表执行 Probe
- **WHEN** 模型 profile agent probe run 包含多个 agent runtime
- **THEN** 后端 SHALL 对每个 runtime 使用对应 agent adapter 执行兼容性 probe
- **AND** 每个 runtime SHALL 生成独立的 probe 状态、通用分项结果、耗时和脱敏消息
- **AND** 单个 runtime 失败 SHALL NOT 阻止其他 runtime 执行

#### Scenario: Runtime 不可用
- **WHEN** 请求中的 agent runtime 不存在、未启用或没有已注册 adapter
- **THEN** 后端 SHALL 拒绝创建 probe run 或将对应 runtime 标记为受控失败
- **AND** 响应 MUST NOT 泄漏完整命令、内部路径或 provider secret

#### Scenario: Probe 输出统一
- **WHEN** 任意 agent runtime 执行 profile 兼容性 probe
- **THEN** 后端 SHALL 使用统一结果结构保存 Agent 模型响应、workspace 读取、workspace 写入和基础 JSON 解析分项结果
- **AND** 聚合兼容状态 SHALL 只由这些通用分项计算
- **AND** probe MUST NOT 执行或返回 `TEST_COMPARE_SCHEMA`、`KB_AI_EXTENSION_SCHEMA` 或其他业务阶段专属检查

#### Scenario: Workspace 写入闭环
- **WHEN** Agent Runtime 执行通用 workspace 写入检查
- **THEN** Agent SHALL 根据中性输入文件写出受控 JSON 结果文件
- **AND** 后端 SHALL 校验文件存在、JSON 合法且 marker 与预期一致
- **AND** 临时 workspace SHALL 在 probe 完成、失败或超时后按现有安全策略清理

#### Scenario: 容器内 Agent CLI 完整安装
- **WHEN** 构建后端运行镜像
- **THEN** 镜像 SHALL 安装与 Codex CLI 版本匹配的平台二进制依赖
- **AND** 构建过程 SHALL 实际执行各内置 Agent CLI 的版本命令
- **AND** backend 与 backend-worker SHALL 使用包含相同 Agent CLI 的同一后端镜像

### Requirement: Agent Runtime 选择必须允许 KB_AI_EXTENSION 阶段
后端 SHALL 将 `KB_AI_EXTENSION` 纳入受控 agent runtime 阶段白名单，使 KB AI 扩展扫描能通过统一 adapter 执行。

#### Scenario: 执行 KB AI 扩展 agent
- **WHEN** `KB_AI_EXTENSION` 阶段绑定选择某个已启用 agent runtime
- **THEN** 后端 SHALL 使用对应 agent adapter 构造受控命令并传入模型 profile
- **AND** adapter SHALL 在 KB AI 扩展专用 workspace 中执行任务
- **AND** 业务代码 MUST NOT 直接拼接某个 agent 的专用命令

#### Scenario: KB AI 扩展 agent 输出保存
- **WHEN** KB AI 扩展任务需要保存 agent 原始输出 artifact
- **THEN** 后端 SHALL 保存包含 `stdout`、`stderr`、`mergedOutput`、`exitCode` 和 `timedOut` 的结构化输出
- **AND** 保存前 SHALL 对 API key、授权头、完整 prompt 和服务器真实敏感路径做脱敏处理

#### Scenario: 未声明阶段被拒绝
- **WHEN** 请求为非白名单阶段绑定或执行 agent runtime
- **THEN** 后端 SHALL 返回统一参数错误或业务错误
- **AND** 后端 MUST NOT 尝试执行任意外部命令

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
