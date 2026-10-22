# gcc-clang-compilation-context

## Purpose

规范 GCC/Clang C/C++ 编译上下文导入、受限命令适配、配置身份及依赖重发现与缓存有效性。

## Requirements

### Requirement: Ingest supported compiler commands without shell execution
系统 SHALL 仅在可选 AST/profile 路径读取 GCC/Clang 的 C11/C17、C++17/C++20 编译数据库，校验 directory、file 和 arguments/command，优先使用字符串数组 arguments；SHALL 拒绝 MSVC/clang-cl、未知执行 wrapper 及含需执行 shell 操作的 command。读取只用于建立 `CompilationProfileIdentity` 和与外部 BC record 的显式 digest/TU 对齐，MUST NOT 执行原命令、依赖发现、`-emit-llvm`、object/BC 输出或链接。源文件/响应文件相对路径 SHALL 按对应工作目录和驱动语义解析，响应文件读取 SHALL 有路径、循环、深度和大小限制。

#### Scenario: Arguments take precedence over command
- **WHEN** 一条记录同时有合法 arguments 和内容不同的 command
- **THEN** 使用 arguments 建立 profile identity，同时保留两份原始字段和选择依据，不执行任一命令

#### Scenario: Command requests shell substitution
- **WHEN** command 含命令替换、管道或需要执行的重定向
- **THEN** 标记不支持的 profile 语义，不经 shell 执行，也不影响独立外部 BC 的 IR-only 导入

#### Scenario: Response files form a cycle
- **WHEN** GCC/Clang 响应文件递归引用自己或超过预算
- **THEN** 输出包含引用链的受限 AST/profile 诊断，外部 BC 保持独立但 SourceIRBinding 进入 partial/unknown

### Requirement: Preserve production context and explain adaptation
外部 BC record 和可选 AST profile SHALL 分别保存原始 argv digest、生产编译器与 BC producer 身份、语言标准、target/ABI/CPU、sysroot/SDK、宏与 include 有序序列、相关环境摘要以及可验证/自述/缺失字段。系统 SHALL 区分 producer host 与 BC target、显式选项与 driver 默认，不以 BC 可读取或 AST 可解析宣称与生产 GCC 语义等价；分析器 MUST NOT 为生成 BC 而转换或执行命令，未支持的 profile 字段不得静默补全。

#### Scenario: GCC implicit C++ headers are required for AST
- **WHEN** GCC 编译记录未显式给出标准库路径且 source worker 无法从可审计 profile 恢复
- **THEN** AST/profile 进入 partial/failed，外部 BC 仍可 IR-only 分析，但不得伪造标准库/ABI 对齐

#### Scenario: Ordered macro operations affect preprocessing
- **WHEN** 原始参数含重复宏定义、取消定义及多个有顺序的 include 目录
- **THEN** profile 保留其有效顺序和 digest，不将其转换为无序字典，也不重新执行命令生成另一份 BC

#### Scenario: Producer host differs from target
- **WHEN** x86_64 host 上的 Clang 产生 ARM target BC
- **THEN** 两种身份分别记录，AST/profile 和 IR 只在实际 target/ABI 一致时精确对齐

### Requirement: Give each effective TU a stable configuration identity
CompileContextId/physical TU identity SHALL 基于规范化源 profile、外部 record 和工具链身份，不依赖数据库条目、bundle 记录或调度顺序；SHALL 保留同源码不同配置，外部绝对路径不得仅以 basename 参与身份。相同重复记录允许映射到同一 TU，但 SHALL 保存原始 record 到 TU 的映射。内部 ArtifactKey SHALL 由分析器根据外部 BC digest、record 语义身份和 extractor protocol 计算，目标成员关系 SHALL 独立于 TU 和 artifact identity。

#### Scenario: Reorder external bundle and compilation database entries
- **WHEN** 只调整相同 record/编译记录的数组顺序
- **THEN** physical TU、CompileContextId 和内部 ArtifactKey 保持稳定，来源映射仍可追溯

#### Scenario: One source uses different macro configurations
- **WHEN** 相同 source 对应两条具有不同宏、target 或 BC digest 的外部记录
- **THEN** 产生不同配置与 artifact identity，不按源路径或 BC 文件名覆盖

### Requirement: Validate dependencies before artifact cache reuse
系统 SHALL 使用外部 record 声明的源码、头文件、响应文件、生成输入、工具链/SDK、profile 和 BC 内容摘要形成 provenance 与缓存身份，并区分 analyzer-verified 与 producer-attested 字段。分析器 MUST NOT 为验证 cache 执行编译器依赖发现；每次复用前 SHALL 校验 bundle/record/BC 及已发布 artifact digest。依赖清单缺失、不可验证或与可选源码不一致时 SHALL 降低 source/profile 完整性，不得把内容可读提升为生产配置等价。

#### Scenario: External dependency evidence is absent
- **WHEN** BC 可读但 record 没有头文件/生成输入摘要
- **THEN** IR facts 可保留，source/profile provenance 为 partial，缓存不得声称覆盖未登记依赖变化

#### Scenario: Published artifact changes after ingestion
- **WHEN** 内容寻址 store 中 BC 与登记 hash 不一致
- **THEN** cache 复用失败并报告损坏，不调用 compiler 重建或静默继续

#### Scenario: A required generated header was missing upstream
- **WHEN** 外部构建 record 明确报告生成头文件缺失且没有 BC
- **THEN** 该 TU 保留在 planned 分母并记录 upstream-failed，不自动运行构建脚本或从 scope 删除

### Requirement: Plan source and IR evidence independently from one compiler context

系统 SHALL 对 GCC/Clang 的每个有效 C11/C17/C++17/C++20 编译记录，在同一不可变配置身份下独立计划 SourceSemanticFacts 与 BC/P1；两条路径 SHALL 共享源码、include、宏、target/ABI、语言标准和工具链 lineage，但分别记录完成、失败、预算和产物。任一路径成功 MUST NOT 覆盖另一条路径的失败。

#### Scenario: Source extraction succeeds before BC emission fails

- **WHEN** 前端语义分析成功且 profile 一致，但 BC emission 或 verify 失败
- **THEN** 保存可信 source 产物及独立 IR 失败，允许下游选择 ast-only 而非丢弃 TU

#### Scenario: A generated header is missing

- **WHEN** AST 和 BC 都需要的生成头文件不存在
- **THEN** 两条计划均保留在分母并报告 frontend/dependency failure，不用错误恢复 AST伪造降级成功

### Requirement: Keep C and C++ compilation identities distinct during degradation

语言标准、C/C++ language kind、C/C++ linkage 和相关前端选项 MUST 属于配置及缓存身份。C11/C17 的 pthread、struct/union、宏、`_Atomic`/`<stdatomic.h>` SHALL 可在不加载 C++ 标准库或 C++ AST 规则的情况下计划和提取；C 与 C++ 同名实体或配置不得因降级模式合并。

#### Scenario: Equivalent file names use C17 and C++17

- **WHEN** 两条编译记录路径或符号相似但语言标准分别为 C17 和 C++17
- **THEN** 系统产生不同 profile/TU identity、cache key 和诊断分母，不跨语言复用 source 或 IR 产物

### Requirement: Capture C++ standard-library and ABI identity for lifecycle analysis

GCC/Clang C++17/C++20 编译上下文 SHALL 为 A3 记录生产与分析标准库 vendor/version、C++ ABI、target、异常/RTTI/线程配置、resource/sysroot、关键 driver 默认及可验证的头文件/wrapper digest，并把它们纳入 profile、依赖和缓存身份。无法恢复 GCC 隐式标准库或 Clang 重放不等价时 MUST 降级；C11/C17 profile SHALL 不加载或依赖这些 C++ 字段才能继续直接 pthread 分析。

#### Scenario: GCC uses implicit libstdc++ defaults
- **WHEN** 编译数据库没有显式标准库 include，但锁定 GCC 安装与依赖发现可以确定实际 libstdc++ 版本和路径
- **THEN** 记录可审计来源和完整 profile，再由 Clang 等价重放；无法恢复时报告 profile gap

#### Scenario: C17 pthread analysis runs beside C++ profiles
- **WHEN** 同一 scope 含 C17 pthread TU 与 C++20 `std::thread` TU
- **THEN** 两者保持独立语言/profile/cache 身份，C17 TU 不加载 C++ 标准库模型或以其结果补全 C 证据

### Requirement: Record A4 synchronization compilation identity without coupling C profiles

GCC/Clang C++17/C++20 编译上下文 SHALL 记录 A4 所需的标准库、版本、ABI、target、异常/RTTI 选项、wrapper/header fingerprint 和模型 identity，并纳入请求与缓存摘要。C11/C17 profile SHALL 保持独立且不得加载 C++ 标准库同步模型。

#### Scenario: One scope mixes C17 pthread and C++20 RAII
- **WHEN** 显式 scope 同时包含 C17 直接 pthread mutex TU 和 C++20 `lock_guard` TU
- **THEN** 每个 TU 使用自己的语言/profile identity，C17 结果不依赖或继承 C++ A4 profile

#### Scenario: Driver defaults hide standard-library identity
- **WHEN** compile command 未显式写出标准库或 ABI 选择且不能从可审计编译上下文确定
- **THEN** A4 profile eligibility 为 unknown/partial，不以主机默认值静默补全

### Requirement: Plan source and external IR evidence independently from one profile
系统 SHALL 对 GCC/Clang 的每个计划 C11/C17/C++17/C++20 physical TU 独立登记 SourceSemanticFacts 计划与外部 BC/P1 计划。两条路径 SHALL 通过显式 record/profile digest 共享源码、语言、target/ABI 和 lineage，但分别记录 available、complete、partial、failed 与预算；任一路径成功 MUST NOT 覆盖另一条路径的缺失或失败，且 AST 路径 MUST NOT 生成 BC。

#### Scenario: Source extraction succeeds while external BC is missing
- **WHEN** source worker 获得可信 profile/源码，但 bundle 将对应 record 标为 missing
- **THEN** 保存 AST 事实并把 TU 分类为 ast-only/partial，不调用 Clang emission 补产 BC

#### Scenario: External BC is available without source inputs
- **WHEN** record 的 BC 完整可读而源码、compile database 或 include profile不可用
- **THEN** 保存 IR-only 事实并报告 SourceIRBinding 缺口，不按 debug 文件名伪造 AST 对齐
### Requirement: 编译上下文必须支持旧 C/C++ 标准
分析器 SHALL 规范化 C89/C90、C99、C11、C17/C18、C++98、C++03、C++11、C++14、C++17、C++20 及常见 GNU 别名，并 SHALL 保留完整 argv、基础标准、方言、来源和原始 `-std` 参数。C23/C++23 可按当前 Clang 能力接收；未知标准只隔离对应翻译单元，不得静默回退到 C17/C++17。

#### Scenario: 旧标准进入源码辅助
- **WHEN** compile entry 使用 `-std=c99` 或 `-std=c++03`
- **THEN** SourceSemanticRequest 使用 `c99` 或 `c++03` 基础标准继续 AST 分析

### Requirement: 编译上下文协议必须按 kind 协商版本

`CompilationProfileIdentity` 和 `SourceSemanticRequest` 的扩展语言上下文 SHALL 使用 v2；历史 v1 SHALL 仅保留既有 C11、C17、C++17、C++20 语义。统一分析请求引用 source request 时 SHALL 携带被引用文档的 `schema_version`，并在包含 v2 引用时使用 request v2。未知未来版本和相互矛盾的嵌套版本 MUST 被拒绝。

#### Scenario: v1 profile 携带新字段

- **WHEN** v1 profile 携带 `dialect`、`standard_source` 或 `standard_option`
- **THEN** 校验器拒绝该文档，而不是把它当作兼容性加法字段读取

#### Scenario: v2 统一请求引用 v2 source request

- **WHEN** 统一分析请求引用旧标准的 `SourceSemanticRequest v2`
- **THEN** 引用明确包含 `schema_version=2`，消费者按 v2 校验并保留真实语言上下文
