## MODIFIED Requirements

### Requirement: 依赖分析必须提取构建和运行依赖
依赖分析 worker SHALL 从 x86 构建事实中提取构建依赖、链接依赖、运行依赖和可选测试依赖，并 MUST NOT 将 compiler flag、宏或构建元数据文件本身作为依赖分析结果项。

#### Scenario: 使用多信号识别构建系统
- **WHEN** worker 分析用户提供的自定义构建脚本
- **THEN** worker SHALL 使用源码静态探测、`PS4` shell trace、可选 `strace execve`、构建日志和构建产物扫描组合识别构建系统
- **AND** 构建系统识别结果 SHALL 支持多个候选值、证据来源和置信度
- **AND** worker MUST NOT 依赖单一构建系统类型作为依赖提取前置条件

#### Scenario: strace 可用时采集 execve
- **WHEN** source/x86 环境存在 `strace`
- **THEN** 构建 wrapper MAY 使用 `strace -f -e execve` 采集真实子进程启动链
- **AND** worker SHALL 从 exec trace 中提取构建工具、编译器、linker、pkg-config、测试工具和关键参数摘要
- **AND** 采集结果 MUST 进行敏感参数脱敏

#### Scenario: strace 不可用时有限安装
- **WHEN** source/x86 环境不存在 `strace`
- **THEN** worker MAY 在构建前按目标环境包管理器执行一次受控、有限的 `strace` 安装尝试
- **AND** 安装尝试 MUST 有超时、日志记录和失败降级
- **AND** 安装失败 MUST NOT 阻断用户构建
- **AND** worker SHALL 记录 `straceUnavailable` 或等效 warning

#### Scenario: 无 strace 降级分析
- **WHEN** `strace` 不可用或被环境策略禁止
- **THEN** worker SHALL 继续使用 `PS4` shell trace、构建日志解析和产物扫描提取依赖事实
- **AND** 依赖分析 MUST NOT 因缺少 `strace` 直接失败

#### Scenario: 采集自然生成的编译数据库
- **WHEN** x86 构建完成后源码目录或构建目录中存在 `compile_commands.json`、`CMakeCache.txt` 或 `build.ninja`
- **THEN** worker SHALL 采集这些文件的结构化摘要
- **AND** worker SHALL 从中提取编译器、源文件、include path、编译参数、构建 generator 和构建工具线索
- **AND** 响应和结果 MUST NOT 暴露服务器真实路径或未脱敏的敏感参数
- **AND** `compile_commands.json`、`CMakeCache.txt`、`build.ninja` 文件本身 MUST NOT 作为依赖分析结果项保存或展示

#### Scenario: 采集编译器内置宏
- **WHEN** source/x86 构建环境存在 `cc`、`gcc`、`clang`、`c++`、`g++` 或 `clang++`
- **THEN** 构建 wrapper MAY 使用实际编译器执行 `-dM -E` 采集本次环境的 C/C++ 内置宏集合
- **AND** worker MAY 使用该集合辅助内部 evidence 分类
- **AND** `make`、`cmake`、`ninja`、`meson` 等构建系统 MUST NOT 被当作 C/C++ 编译器内置宏来源
- **AND** 编译器内置宏、项目自定义宏和构建系统 flag probe 宏 MUST NOT 作为依赖分析结果项保存或展示

#### Scenario: 使用 Bear 生成 compile_commands
- **WHEN** source/x86 环境存在 Bear
- **THEN** 构建 wrapper MAY 使用 Bear 包裹用户构建脚本生成 `compile_commands.json`
- **AND** Bear 生成结果 SHALL 标记来源为 `BEAR`
- **AND** worker SHALL 将 Bear 结果作为增强 evidence，而不是唯一依赖来源
- **AND** Bear 自身 MUST NOT 作为用户项目依赖结果项展示，除非它由用户构建命令显式依赖且不是后端为了采集临时安装或调用

#### Scenario: Bear 不可用时有限安装
- **WHEN** source/x86 环境不存在 Bear
- **THEN** worker MAY 在构建前按目标环境包管理器执行一次受控、有限的 Bear 安装尝试
- **AND** 安装尝试 MUST 有超时、日志记录和失败降级
- **AND** 安装失败 MUST NOT 阻断用户构建
- **AND** worker SHALL 记录 `bearUnavailable` 或等效 warning

#### Scenario: 不得为采集改变用户构建行为
- **WHEN** worker 尝试采集编译数据库
- **THEN** worker MUST NOT 为了生成 `compile_commands.json` 强行修改用户传入的构建参数、CMake generator、构建目录或构建脚本语义
- **AND** 如果用户构建自然没有产生编译数据库且 Bear 不可用，worker SHALL 使用其他观测信号继续分析

#### Scenario: 提取构建依赖
- **WHEN** worker 分析 x86 构建命令和构建日志
- **THEN** worker SHALL 提取编译器、构建系统、pkg-config module、header、dev package、`-I`、`-L` 和构建工具线索
- **AND** 提取结果 SHALL 保留证据来源和置信度
- **AND** compiler flag、宏、构建数据库文件名和构建元数据文件名 MUST NOT 作为依赖结果项生成

#### Scenario: 提取链接和运行依赖
- **WHEN** worker 分析构建产物
- **THEN** worker SHALL 采集 ELF `NEEDED`、`SONAME`、解释器、动态库、owner package 和可执行文件依赖
- **AND** worker SHALL 将源环境 owner package、源版本、目标 provider package、目标版本、版本关系和风险映射作为可分页结果明细保存

#### Scenario: 排除本次构建生成产物
- **WHEN** worker 采集源码目录或构建目录中的 ELF、`.so` 或可执行文件
- **THEN** worker SHALL 通过构建前后 manifest 或等效机制区分仓库原有文件和本次构建新增产物
- **AND** 本次构建新增产物 SHALL 只作为排除证据记录，不作为依赖分析结果项
- **AND** 源码仓库原本携带的 ELF、`.so` 或可执行文件 SHALL 继续作为依赖候选分析

#### Scenario: 提取测试依赖
- **WHEN** 依赖分析输入包含可用测试事实
- **THEN** worker MAY 提取测试工具、测试报告路径和测试命令依赖
- **AND** 缺少测试事实 MUST NOT 导致依赖分析失败

### Requirement: 依赖分析必须查询 RISC-V 目标能力
依赖分析 worker SHALL 查询 RISC-V 目标环境已安装能力和仓库能力，用于判断 x86 构建事实中提取的依赖是否可满足，并 SHALL 对 ELF/SO provider package 执行源目标版本匹配。

#### Scenario: 查询目标已安装能力
- **WHEN** worker 执行依赖分析
- **THEN** worker SHALL 查询目标环境已安装包、工具、库文件、pkg-config module 和 header provider
- **AND** 查询结果 MUST NOT 暴露明文凭据或远端敏感路径

#### Scenario: 查询目标仓库能力
- **WHEN** 目标环境支持包管理器仓库查询
- **THEN** worker SHALL 刷新或读取仓库 metadata
- **AND** worker SHALL 查询 package search、provides/whatprovides、pkg-config provider 和 header provider
- **AND** 查询失败 SHALL 记录 warning 和 evidence，不得直接解释为依赖缺失

#### Scenario: 匹配源目标 ELF/SO provider package 版本
- **WHEN** source/x86 构建事实包含 ELF、SO、`NEEDED` 或 `SONAME` 依赖
- **THEN** worker SHALL 优先使用源环境包数据库解析这些文件或 SONAME 的 source owner package 和 source owner version
- **AND** worker SHALL 使用目标环境已安装包、目标软件源包和 provides/whatprovides 查询对应 target provider package 和 target provider version
- **AND** 匹配结果 SHALL 保存源 provider、目标 provider、版本关系、风险等级和 evidence

#### Scenario: 目标能力证据不足
- **WHEN** 目标环境查询失败或证据不完整
- **THEN** 对应依赖结果 SHALL 标记为 `MANUAL_CONFIRM_REQUIRED` 或等效证据不足状态
- **AND** 结果 SHALL 包含可审计 warning 摘要

### Requirement: 依赖分析必须逐条持久化结果
依赖分析运行时 SHALL 将每个依赖判断结果逐条写入数据库，支持分页、过滤、排序、迁移输入导入和报告生成，并 SHALL 对 ELF/SO provider package 结果保存版本匹配证据。

#### Scenario: 保存依赖分析结果
- **WHEN** 依赖分析 worker 完成匹配
- **THEN** 后端 SHALL 写入依赖分析结果明细
- **AND** 每条结果 SHALL 关联 `projectId`、`sourceRevisionId`、`taskId` 和依赖分析运行 ID
- **AND** 每条结果 SHALL 保存依赖类型、名称、版本、目标匹配状态、风险等级、位置标签、建议、证据摘要和创建时间
- **AND** ELF/SO provider package 结果 SHALL 在 evidence 中保存 `sourceLibraryPath`、`sourceLibraryName`、`sourceSoname`、`sourceOwnerPackage`、`sourceOwnerVersion`、`sourceVersionEvidence`、`targetProviderPackage`、`targetProviderVersion`、`targetProviderSource`、`versionRelation`、`riskMappingRule` 和 `matchEvidence`
- **AND** 后端 MUST NOT 将完整结果数组整体塞入单个 JSON 字段

#### Scenario: 查询结果列表
- **WHEN** 用户调用依赖分析结果列表 API
- **THEN** 后端 SHALL 返回分页列表
- **AND** 列表 SHALL 支持按依赖类型、目标匹配状态、风险等级、关键字和创建时间过滤
- **AND** 列表 SHALL 支持稳定排序白名单
- **AND** 列表 MUST NOT 返回 compiler flag、宏或构建元数据文件本身的结果项

#### Scenario: 查询结果详情
- **WHEN** 用户查询单条依赖分析结果详情
- **THEN** 后端 SHALL 校验结果所属项目访问权限
- **AND** 响应 SHALL 返回结构化 evidence、source 构建事实摘要、目标候选摘要和建议
- **AND** 响应 MUST NOT 返回明文凭据、完整构建日志、完整脚本或服务器真实路径

## ADDED Requirements

### Requirement: ELF/SO provider package 风险必须按版本关系映射
依赖分析 SHALL 对 ELF/SO provider package 匹配结果使用固定版本关系和风险等级映射，避免用模糊置信度替代实际替代风险。

#### Scenario: 源目标 provider 大版本一致
- **WHEN** 源环境存在 source owner package 和版本
- **AND** 目标环境或目标软件源存在对应 target provider package 和版本
- **AND** 源目标 package 大版本一致
- **THEN** 结果 SHALL 使用 `versionRelation=SAME_MAJOR`
- **AND** `riskLevel` SHALL 为 `INFO`

#### Scenario: 目标 provider 版本高于源 provider
- **WHEN** 源环境存在 source owner package 和版本
- **AND** 目标环境或目标软件源存在对应 target provider package 和版本
- **AND** 目标 package 版本高于源 package 版本
- **THEN** 结果 SHALL 使用 `versionRelation=TARGET_NEWER`
- **AND** `riskLevel` SHALL 为 `LOW`

#### Scenario: 目标 provider 版本低于源 provider
- **WHEN** 源环境存在 source owner package 和版本
- **AND** 目标环境或目标软件源存在对应 target provider package 和版本
- **AND** 目标 package 版本低于源 package 版本
- **THEN** 结果 SHALL 使用 `versionRelation=TARGET_OLDER`
- **AND** `riskLevel` SHALL 为 `HIGH`

#### Scenario: 源无 owner 但目标存在 provider
- **WHEN** 源环境无法解析 source owner package
- **AND** worker 能从源文件名、SONAME、readelf、symlink 或路径提取 source version evidence
- **AND** 目标环境或目标软件源存在对应 target provider package 和版本
- **THEN** 结果 SHALL 使用 `versionRelation=TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED`
- **AND** `riskLevel` SHALL 为 `MEDIUM`

#### Scenario: 源无 owner 且目标无可确认版本
- **WHEN** 源环境无法解析 source owner package
- **AND** worker 无法确认目标环境或目标软件源存在对应版本
- **THEN** 结果 SHALL 使用 `versionRelation=NO_TARGET_VERSION_FOUND`
- **AND** `riskLevel` SHALL 为 `CRITICAL`

### Requirement: ELF/SO provider package 结果必须去重聚合
依赖分析 SHALL 避免把同一个软件包因多个库文件命中重复展示成大量相同风险项。

#### Scenario: 源 provider package 多个 SO 命中同一目标 provider
- **WHEN** 多个源 ELF/SO 具有相同 source owner package、source owner major version、target provider package、target provider major version 和 version relation
- **THEN** 列表结果 SHOULD 聚合为同一条 provider package 结果
- **AND** 详情 evidence SHALL 保留所有命中的源路径、SONAME 和 target provides 证据

#### Scenario: 源无 owner 的库文件聚合
- **WHEN** 多个源无 owner 的 ELF/SO 具有相同 library stem、source version evidence、target provider package、target provider major version 和 version relation
- **THEN** 列表结果 SHOULD 聚合为同一条结果
- **AND** 详情 evidence SHALL 保留所有命中的源路径和目标 provider 证据
