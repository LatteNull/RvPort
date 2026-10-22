## ADDED Requirements

### Requirement: 环境采集必须提取 ELF metadata
环境采集 SHALL 对源 x86 和目标 RISC-V 环境中的 ELF `.so` 与 native 文件提取非敏感 ELF metadata，并将其写入 `environment_components.metadata`。

#### Scenario: 提取 ELF SONAME 和 NEEDED
- **WHEN** worker 执行 `SOURCE_X86` 或 `TARGET_RISCV` 环境的 `ENV_COLLECT`
- **THEN** 后端 SHALL 对采集到的 ELF `.so` 或 native 文件尝试提取 `SONAME`
- **AND** 后端 SHALL 尝试提取 `NEEDED` 依赖列表
- **AND** 后端 SHALL 将 `elfSoname`、`elfNeeded` 和 `elfScanner` 写入组件 metadata
- **AND** 后端 MUST NOT 将完整敏感路径或凭据写入 API 响应、事件或日志摘要

#### Scenario: 提取 ELF machine 和 class
- **WHEN** ELF header 可读取
- **THEN** 后端 SHALL 提取 ELF machine 和 ELF class
- **AND** 后端 SHALL 将 `elfMachine` 和 `elfClass` 写入组件 metadata
- **AND** 后端 SHALL 保留组件原始 `arch` 字段，不得用解析失败的 ELF 信息覆盖原始架构事实

#### Scenario: ELF 工具不可用
- **WHEN** 远程环境缺少 `readelf`、`objdump` 或等效 ELF metadata 工具
- **THEN** `ENV_COLLECT` MAY 成功保存基础快照、包、库和 owner package 信息
- **AND** 后端 SHALL 在 `raw_snapshot.parseWarnings` 中记录 ELF metadata scanner 不可用
- **AND** 后端 MUST NOT 将工具缺失解释为 ELF 文件不存在

### Requirement: 环境采集必须记录 installed ELF provides capability
环境采集 SHALL 在源 x86 和目标 RISC-V 环境中记录已安装 ELF 文件提供或依赖的 capability，用于 SBOM 分析做精确匹配。

#### Scenario: 记录源环境 ELF capability
- **WHEN** 源 x86 环境采集到 ELF `.so` 或 native 文件
- **THEN** 后端 SHALL 基于 `SONAME`、文件名和 owner package 生成 installed provides capability
- **AND** 后端 SHALL 将 `providesCapabilities` 写入组件 metadata
- **AND** 若存在 `NEEDED` 依赖，后端 SHALL 将 `requiredCapabilities` 写入组件 metadata

#### Scenario: 记录目标环境 ELF capability
- **WHEN** 目标 RISC-V 环境采集到已安装 ELF `.so` 或 native 文件
- **THEN** 后端 SHALL 记录目标侧 installed provides capability
- **AND** 后端 SHALL 保留目标 ELF machine/class 作为匹配 evidence
- **AND** 后端 SHALL 将 owner package、provider scanner 和 capability evidence 关联到同一组件 metadata

#### Scenario: capability 冲突
- **WHEN** 多个组件提供同一个 SONAME 或 capability
- **THEN** 后端 SHALL 保留每个组件独立记录
- **AND** 后端 SHALL 在 metadata 中记录 capability 来源，避免合并不同组件事实

### Requirement: 仓库 provides 查询必须优先使用 ELF capability
目标 RISC-V 仓库候选采集 SHALL 优先使用 ELF SONAME/capability 查询 repository provides，再 fallback 到路径、文件名和 normalized library name。

#### Scenario: 使用 exact SONAME 查询 repository provides
- **WHEN** 源侧或目标侧采集到 `elfSoname`
- **THEN** 后端 SHALL 尝试使用 exact SONAME 或包管理器支持的 ELF capability 表达式查询目标仓库
- **AND** 命中结果 SHALL 写入 `environment_components` 并标记 `source=REPOSITORY_PROVIDE`
- **AND** metadata SHALL 包含 `provideKind=ELF_SONAME`、`queryValue`、`packageName` 和 `scanner`

#### Scenario: fallback 到路径或文件名查询
- **WHEN** exact SONAME/capability 查询不可用或无命中
- **THEN** 后端 MAY 使用 `*/libname.so*`、文件名或 normalized library name 查询
- **AND** metadata SHALL 标记 fallback 查询类型
- **AND** 后端 SHALL 在 warning 或 metadata 中区分 fallback 证据与 exact capability 证据

#### Scenario: repository provides 查询失败
- **WHEN** repoquery、yum whatprovides 或 apt-file search 因 metadata、网络、权限或工具缺失失败
- **THEN** `ENV_COLLECT` MAY 成功保存基础快照和已安装组件
- **AND** 后端 SHALL 记录安全失败摘要
- **AND** 后端 MUST NOT 把 repository provides 缺失解释为目标环境无替代包
