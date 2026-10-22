## ADDED Requirements

### Requirement: 环境采集必须记录库文件 provider 证据
环境采集 SHALL 在源环境和目标环境中为 `.so` 与 native 文件记录可用的 provider/owner package 证据，供 SBOM 分析使用。

#### Scenario: x86 源环境采集库 owner package
- **WHEN** worker 执行 `SOURCE_X86` 环境的 `ENV_COLLECT`
- **THEN** 后端 SHALL 尝试查询已发现 `.so` 或 native 文件所属的软件包
- **AND** 后端 SHALL 将 owner package、owner version、owner arch 和查询工具写入对应 `environment_components.metadata`
- **AND** 后端 SHALL 保留原始库文件名和原始组件事实

#### Scenario: RISC-V 目标环境采集库 owner package
- **WHEN** worker 执行 `TARGET_RISCV` 环境的 `ENV_COLLECT`
- **THEN** 后端 SHALL 尝试查询已安装 `.so` 或 native 文件所属的软件包
- **AND** 后端 SHALL 将 owner package、owner version、owner arch 和查询工具写入对应 `environment_components.metadata`
- **AND** owner 查询失败时 SHALL 在快照 `raw_snapshot.parseWarnings` 中记录安全警告

#### Scenario: provider 查询工具缺失
- **WHEN** 远程环境缺少 `rpm`、`dpkg-query` 或其他可用 owner 查询工具
- **THEN** `ENV_COLLECT` MAY 成功保存基础快照和库文件组件
- **AND** 后端 SHALL 记录 provider 查询不可用的解析警告
- **AND** 后端 MUST NOT 将工具缺失伪装为库不存在

### Requirement: RISC-V 仓库候选采集必须准备 metadata
RISC-V 目标环境仓库候选采集 SHALL 在查询可用包或 provides 能力前执行受控 metadata refresh 或 metadata 可用性检查。

#### Scenario: metadata refresh 成功
- **WHEN** worker 执行 `TARGET_RISCV` 环境的 `ENV_COLLECT`
- **THEN** 后端 SHALL 在仓库候选查询前运行受控 metadata refresh 或校验命令
- **AND** 命令 SHALL 使用超时、低重试和 `skip_if_unavailable` 等非交互参数
- **AND** 后端 SHALL 在 `raw_snapshot.repositories` 或等效摘要中记录 refresh 成功状态

#### Scenario: metadata refresh 失败
- **WHEN** RISC-V 仓库 metadata refresh 因 DNS、超时、源不可用或 repo 配置错误失败
- **THEN** `ENV_COLLECT` MAY 成功保存基础快照、已安装组件和工具版本
- **AND** 后端 SHALL 记录 refresh 失败原因的安全摘要
- **AND** 后端 SHALL 将仓库候选结果标记为不完整

#### Scenario: metadata refresh 不允许提权
- **WHEN** 远程仓库 metadata refresh 需要 sudo 或交互输入
- **THEN** 后端 SHALL 跳过该 refresh 操作并记录警告
- **AND** 后端 MUST NOT 在 MVP 中要求或保存 sudo 密码

### Requirement: 环境采集必须生成架构归一化候选
环境采集 SHALL 为库文件名、库路径和包名生成跨架构查询候选，但不得覆盖原始事实。

#### Scenario: 归一化 x86 架构路径
- **WHEN** 源侧库路径包含 `x86_64`、`amd64` 或等效架构 token
- **THEN** 后端 SHALL 生成不含源架构 token 的 normalized library name
- **AND** 后端 MAY 生成 RISC-V 目标架构路径或 `*/libname.so*` 查询 pattern
- **AND** 后端 SHALL 在 metadata 中保存原始值和归一化依据

#### Scenario: 归一化包名架构后缀
- **WHEN** 源侧包名或库名包含 x86 架构后缀
- **THEN** 后端 SHALL 生成去除源架构 token 的 package candidate
- **AND** 后端 MAY 生成替换为目标架构 token 的 package candidate
- **AND** 这些候选 MUST 标记为查询候选而非事实字段

#### Scenario: 归一化候选可能冲突
- **WHEN** 多个源侧组件生成相同 normalized name 或 package candidate
- **THEN** 后端 SHALL 保留每个源组件的独立 fingerprint
- **AND** 后端 SHALL 在 metadata 中记录候选来源，避免合并不同组件事实
