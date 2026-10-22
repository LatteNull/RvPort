## MODIFIED Requirements

### Requirement: Explain BC generation prerequisites and stages
文档 SHALL 说明 BC 生成仍需要预处理、语义检查与 IR 生成，但这些阶段由外部构建系统负责，生产分析器只导入和校验已有 BC，不执行编译、链接或目标程序。文档 SHALL 区分 producer host、BC target、翻译单元、源码/头文件和分析 artifact，并列出上游生成文件、工具链、SDK、优化/debug profile、manifest 和 scope 前提。

#### Scenario: Analyze externally generated BC
- **WHEN** 读者已从 x86 构建流水线获得逐 TU raw LLVM BC
- **THEN** 文档给出 bundle manifest 与 `ingest-bc-bundle` 示例，不再要求分析器运行 `-emit-llvm`

#### Scenario: Required generated header was missing upstream
- **WHEN** 外部构建未产出某 TU，原因是配置或生成头文件缺失
- **THEN** 文档要求把该 TU 作为 missing/failed 记录保留在 bundle 分母，而不是由分析器补跑 configure/build

### Requirement: Document production compiler adaptation limits
文档 SHALL 区分源码生产编译器、BC producer、producer host、BC target 和可选 AST Clang，并说明哪些字段可从 BC 验证、哪些仅由外部 record 自述。当前源码 profile SHALL 限定 GCC/Clang 用户态 C/C++并排除 MSVC/clang-cl；正式 BC 输入 SHALL 限定受支持的 raw LLVM bitcode，明确 GCC LTO/GIMPLE、对象容器、未知 LLVM dialect 和未声明 linked/LTO 不受支持。文档 MUST 说明可读取 BC 不证明与生产编译器语义完全等价。

#### Scenario: A GCC project supplies Clang-produced analysis BC
- **WHEN** 生产配置来自 GCC，而外部流水线另由 Clang 产生 LLVM BC
- **THEN** 文档要求同时记录 GCC source profile 与 Clang BC producer/偏差，不能仅以成功导入宣称等价

#### Scenario: A user supplies GCC LTO or clang-cl artifacts
- **WHEN** 输入是 GCC LTO/GIMPLE、MSVC/clang-cl 对象或嵌入式 bitcode 容器
- **THEN** 文档明确拒绝并要求上游提供受支持 raw LLVM BC，不给出分析器内转换方案

#### Scenario: An x86 host emits a non-x86 target
- **WHEN** 外部 producer 在 x86 host 上交叉产生 ARM/RISC-V BC
- **THEN** 文档要求以实际 triple/DataLayout/ABI 作为证据范围；若实际 target 是 x86_64，则不得推广到其他架构

### Requirement: Define compilation database capabilities and gaps
文档 SHALL 解释 `compile_commands.json` 的 directory、file、arguments/command、可选 output 仍可用于可选 AST profile 和与外部 record 的显式 digest/TU 对齐，但生产分析器不得据此生成 BC。文档 SHALL 明确数据库不单独提供外部 BC 路径/摘要、实际头文件依赖、完整 target/link 图、调用图或线程关系，并列出 bundle record、依赖 manifest、target codemodel/link evidence 和显式 scope 等补充来源。

#### Scenario: Only compile_commands.json is available
- **WHEN** 输入只有编译数据库和源码，没有外部 BC bundle
- **THEN** 文档说明可计划 AST/source-only 分析但不能执行 BC 生成或形成 IR 内存模型证明，并要求上游构建提供 BC

#### Scenario: Compile database and bundle are both available
- **WHEN** bundle record 显式引用 compile record digest 和 physical TU
- **THEN** 文档说明如何形成 AST+IR 对齐，同时强调 target/scope 仍来自显式 bundle/构建证据

### Requirement: Preserve configuration-specific translation unit identity
文档 SHALL 给出外部 record、TU/profile、BC 内容和 target scope 的分层身份示例，记录源路径、compile record digest、producer/toolchain、target、ABI、语言、优化/debug、BC SHA-256 与构建变体，并区分外部 record identity、分析器 ArtifactKey、内容哈希和目标成员关系。文档 SHALL 说明相同字节可属于不同配置、相同源码可产生多个 BC，不能按路径或 basename 合并。

#### Scenario: One source has multiple external BC records
- **WHEN** 相同源码路径在不同宏、target、语言标准或优化配置下产生多份 BC
- **THEN** 文档示例保留不同 record/TU/artifact identity，并要求 scope 显式选择成员

#### Scenario: Linked BC loses physical TU identity
- **WHEN** 上游只提供 linked/LTO BC
- **THEN** 文档说明其只能作为受限 IR-only/partial 输入，不能从 debug 路径重建完整逐 TU lineage

## ADDED Requirements

### Requirement: Document the external bundle lifecycle and completeness report
文档 SHALL 提供 bundle/record/scope 的最小合法示例、路径根和 digest 规则、ingestion 校验顺序、内容寻址输出布局、record-to-artifact 映射、0/2/1 退出码和完整性计数，并明确 `import-bc` 仅是单文件低完整性兼容入口。所有示例 MUST 使用已有外部 BC，不能在 ingestion 命令中嵌入 compiler/linker/build 操作。

#### Scenario: Reader follows the production quick start
- **WHEN** 用户按 README 和 BC 流水线文档运行最小示例
- **THEN** 只执行 reader/worker ingestion、scope index 和后续分析，报告 planned/verified/published/frontier 且不生成新 BC
