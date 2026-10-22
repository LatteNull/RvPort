## ADDED Requirements

### Requirement: C 和 C++ 编译器依赖必须按能力与 provider package 匹配
依赖分析 SHALL 将构建实际执行的工具名称、编译器能力和源 provider package 分别保存和匹配，并 MUST NOT 使用仅提供 C 编译能力的工具或软件包满足 C++ 编译器依赖。

#### Scenario: 目标仓库提供源侧 C++ provider package
- **WHEN** 构建证据观测到 `c++`，源环境确认其由 `gcc-c++` 提供，目标环境未安装 `c++` 或 `g++`，但目标仓库提供 `gcc-c++`
- **THEN** 结果 SHALL 保留 `dependencyName=c++`
- **AND** `sourceProviderPackage` 和 `targetProviderPackage` SHALL 为 `gcc-c++`
- **AND** `targetMatchStatus` SHALL 为 `REPO_AVAILABLE`
- **AND** `riskLevel` SHALL 为 `MEDIUM`

#### Scenario: 目标仅安装 GCC C 编译器
- **WHEN** 源构建需要 `c++` 或 `g++`，而目标环境仅安装 `gcc` 且目标仓库没有对应 C++ provider package
- **THEN** 依赖分析 MUST NOT 使用 `gcc` 将该依赖判定为 `TARGET_INSTALLED`
- **AND** 结果 SHALL 为 `MISSING/HIGH` 或基于快照可用性的等价未满足状态

#### Scenario: 目标已安装同家族 C++ 编译器
- **WHEN** 源侧 `c++` 的 provider 属于 GCC C++ 家族，且目标已安装 `c++`、`g++` 或相同 provider package
- **THEN** 结果 SHALL 为 `TARGET_INSTALLED`
- **AND** 匹配证据 SHALL 返回实际命中的工具或 provider package

#### Scenario: Clang 与 GCC 家族不得交叉误配
- **WHEN** 源侧 C++ 工具明确由 GCC 或 Clang 家族 provider 提供
- **THEN** 等价工具匹配 SHALL 限制在相同编译器家族
- **AND** 后端 MUST NOT 仅因另一家族的 C 或 C++ 命令存在而报告已满足

#### Scenario: 源 provider 信息缺失
- **WHEN** 构建观测到 C++ 编译工具但源环境无法确认 provider package
- **THEN** 后端 SHALL 优先匹配目标严格同名工具或可证明等价的 C++ 驱动
- **AND** 后端 MUST NOT 回退到裸 `gcc` 并报告已满足
- **AND** 匹配证据 SHALL 表达 provider 信息缺失和实际采用的回退依据

### Requirement: 所有构建工具证据必须共享统一目标匹配规则
compile database、execve summary、execve tool 和构建日志文本提取出的工具依赖 SHALL 使用同一套 provider-aware 目标匹配规则，并 SHALL 在去重后保留最高质量的真实使用证据。

#### Scenario: compile database 和 execve 同时观测到 c++
- **WHEN** 同一构建的 `compile_commands.json` 和 `strace execve` 都包含 `c++`
- **THEN** 结果 SHALL 只保留一个 `BUILD_TOOL c++` 主条目
- **AND** 条目 SHALL 使用高置信度真实执行证据及一致的 provider 匹配状态

#### Scenario: 宏采样包含未用于构建的 g++
- **WHEN** 环境宏采样产生 `compilerBuiltinMacros g++`，但构建命令、compile database 和 execve 均未使用 `g++`
- **THEN** 后端 MUST NOT 仅根据宏采样创建 `g++` 构建依赖

#### Scenario: 既有工具别名继续工作
- **WHEN** 构建使用 `cc`、binutils 工具、`ninja`、`rpmbuild` 或 `configure`
- **THEN** 统一匹配规则 SHALL 保持既有经过验证的 provider 或软件包别名行为
- **AND** 不同证据来源 MUST NOT 对同一工具返回互相矛盾的满足状态
