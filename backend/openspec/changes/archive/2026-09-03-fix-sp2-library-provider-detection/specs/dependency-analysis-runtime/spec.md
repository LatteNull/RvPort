## ADDED Requirements

### Requirement: 链接库依赖必须使用 provider-aware 匹配
依赖分析 SHALL 对构建事实中发现的链接库使用 provider-aware 匹配，并 SHALL 在目标库文件证据缺失时使用源侧 owner package 回退到目标 provider package。

#### Scenario: compile commands 链接库使用 provider 匹配
- **WHEN** 依赖分析从 `compile_commands.json` 中解析出 `-l<name>` 链接库
- **THEN** 后端 SHALL 将其规范化为 `lib<name>.so`
- **AND** 后端 SHALL 查询源环境中该库或相关路径的 owner package 证据
- **AND** 后端 SHALL 使用源侧 owner package、目标侧库文件、目标侧 repository provide 和目标侧 package 清单共同决定匹配结果

#### Scenario: strace 链接库使用 provider 匹配
- **WHEN** 依赖分析从 strace execve 观测中解析出 linker 参数 `-l<name>`
- **THEN** 后端 SHALL 将其规范化为 `lib<name>.so`
- **AND** 后端 SHALL 使用 provider-aware 匹配
- **AND** 后端 MUST NOT 仅因目标环境缺少 `INSTALLED_LIBRARY` 组件就判定该链接库缺失

#### Scenario: linker flag 链接库使用 provider 匹配
- **WHEN** 依赖分析从构建日志或 linker flag 中解析出 `-l<name>`
- **THEN** 后端 SHALL 使用与 compile commands 和 strace 相同的 provider-aware 匹配语义
- **AND** 结果字段 SHALL 包含可用的 source provider package/version、target provider package/version 和 provider version status

### Requirement: 源侧 owner package 必须作为目标 provider 回退依据
当源侧 owner package 已知时，依赖分析 SHALL 在目标库文件匹配失败后回退到目标环境的 package 证据。

#### Scenario: 目标库文件缺失但同名包存在
- **WHEN** 源环境确认 `libc.so` 由 `glibc` 提供
- **AND** 目标环境快照没有采集到 `libc.so` 或 `libc.so.6` 的 `INSTALLED_LIBRARY`
- **AND** 目标环境存在 `glibc` 的 `INSTALLED_PACKAGE` 或 `REPOSITORY_PACKAGE`
- **THEN** 依赖分析 SHALL 使用 `glibc` 作为目标 provider package
- **AND** 结果 MUST NOT 为 `MISSING`

#### Scenario: 目标库文件缺失但基础库别名包存在
- **WHEN** 源环境确认 `libgcc_s.so` 由 `gcc` 或 `libgcc` 相关包提供
- **AND** 目标环境快照没有采集到 `libgcc_s.so` 的 `INSTALLED_LIBRARY`
- **AND** 目标环境存在 `gcc` 或 `libgcc` 的 package 证据
- **THEN** 依赖分析 SHALL 使用匹配到的目标 provider package
- **AND** 结果 SHALL 根据源/目标 provider package 主版本关系生成风险等级

#### Scenario: 源侧 owner package 和目标 provider 都缺失
- **WHEN** 链接库没有源侧 owner package 证据
- **AND** 目标环境也没有库文件、repository provide 或 package 候选
- **THEN** 依赖分析 SHALL 保持缺失或需要人工确认的结果
- **AND** evidence SHALL 说明缺少源侧 owner package 和目标 provider 证据

### Requirement: 基础库别名必须参与目标 provider 匹配
依赖分析 SHALL 将基础 C/C++ 运行时库别名纳入目标 provider 匹配，避免常见链接名与包名不一致导致误判。

#### Scenario: libc 链接名映射 glibc
- **WHEN** 依赖分析处理 `libc.so` 或 `libc.so.6`
- **THEN** 目标 provider 匹配 SHALL 尝试 `glibc`
- **AND** 命中后 SHALL 返回目标 provider package/version

#### Scenario: libgcc_s 链接名映射 gcc 和 libgcc
- **WHEN** 依赖分析处理 `libgcc_s.so` 或 `libgcc_s.so.1`
- **THEN** 目标 provider 匹配 SHALL 尝试 `gcc` 和 `libgcc`
- **AND** 命中后 SHALL 返回目标 provider package/version

#### Scenario: 版本关系映射风险等级
- **WHEN** 源 provider package 和目标 provider package 都有版本
- **THEN** 后端 SHALL 使用主版本关系生成 `SAME_MAJOR`、`TARGET_NEWER` 或 `TARGET_OLDER`
- **AND** 风险等级 SHALL 与当前 provider version status 风险映射保持一致
