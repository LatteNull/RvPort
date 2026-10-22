## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Plan source and external IR evidence independently from one profile
系统 SHALL 对 GCC/Clang 的每个计划 C11/C17/C++17/C++20 physical TU 独立登记 SourceSemanticFacts 计划与外部 BC/P1 计划。两条路径 SHALL 通过显式 record/profile digest 共享源码、语言、target/ABI 和 lineage，但分别记录 available、complete、partial、failed 与预算；任一路径成功 MUST NOT 覆盖另一条路径的缺失或失败，且 AST 路径 MUST NOT 生成 BC。

#### Scenario: Source extraction succeeds while external BC is missing
- **WHEN** source worker 获得可信 profile/源码，但 bundle 将对应 record 标为 missing
- **THEN** 保存 AST 事实并把 TU 分类为 ast-only/partial，不调用 Clang emission 补产 BC

#### Scenario: External BC is available without source inputs
- **WHEN** record 的 BC 完整可读而源码、compile database 或 include profile不可用
- **THEN** 保存 IR-only 事实并报告 SourceIRBinding 缺口，不按 debug 文件名伪造 AST 对齐
