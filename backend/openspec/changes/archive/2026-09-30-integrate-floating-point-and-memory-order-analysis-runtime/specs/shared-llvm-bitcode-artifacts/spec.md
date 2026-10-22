## ADDED Requirements

### Requirement: 后端必须解析当前分析所需的共享 BC 制品
系统 SHALL 根据项目、当前源码版本和成功的 source/x86 构建解析唯一的 `SharedLlvmBitcodeArtifactSet@2.0`、compile database 和源码制品，不得信任客户端传入对象 key 或服务器路径。

#### Scenario: 解析一致制品
- **WHEN** 构建、compile database、manifest 和源码具有一致的源码身份与编译上下文
- **THEN** resolver SHALL 返回固定的 artifact set ID、stored artifact reference 和校验摘要

#### Scenario: 制品身份不一致
- **WHEN** BC manifest 的源码身份、compile context 或构建关联与当前运行不一致
- **THEN** resolver MUST 拒绝该制品
- **AND** 分析任务 MUST NOT 启动

### Requirement: 分析输入必须安全物化
系统 SHALL 在 Worker 任务私有目录中流式下载并校验源码、compile database 和 BC bundle，且 SHALL 对路径、条目类型、大小、数量、SHA-256 和 manifest 声明执行严格校验。

#### Scenario: 正常物化
- **WHEN** 所有对象和归档成员满足 v2 manifest 与预算
- **THEN** materializer SHALL 生成只读输入目录和稳定相对路径

#### Scenario: 路径或内容不安全
- **WHEN** bundle 包含绝对路径、`..`、反斜杠逃逸、符号链接、硬链接、设备文件、重复条目、未声明文件或哈希错误
- **THEN** materializer MUST 终止并清理任务目录
- **AND** MUST NOT 调用分析工具

### Requirement: v2 制品必须确定性适配两个消费者
系统 SHALL 提供浮点扫描和 memory-order external bundle 的版本化 adapter，并 SHALL 保留计划分母、profile、capability、target、ABI、producer、输入摘要和 Scope 完整性。

#### Scenario: 适配浮点扫描器
- **WHEN** 浮点任务消费 v2 artifact set
- **THEN** adapter SHALL 固定 manifest SHA-256、请求的 profile 和所需 capability
- **AND** 不满足能力的 record SHALL 形成明确诊断而不是被静默忽略

#### Scenario: 适配内存序分析器
- **WHEN** 内存序任务消费 v2 artifact set
- **THEN** adapter SHALL 生成合法 external bundle/record/scope
- **AND** produced、missing、failed 与 open boundary MUST 保持不变
