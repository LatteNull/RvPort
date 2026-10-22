## ADDED Requirements

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
后端 SHALL 只允许已声明阶段使用 agent runtime，当前只允许 `TEST_LOG_COMPARE` 阶段绑定 agent runtime。

#### Scenario: 保存 TEST_LOG_COMPARE agent 绑定
- **WHEN** 超级管理员保存 `TEST_LOG_COMPARE` 阶段绑定
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
