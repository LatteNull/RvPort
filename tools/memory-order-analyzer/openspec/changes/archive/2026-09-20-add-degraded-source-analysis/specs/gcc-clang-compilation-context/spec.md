## ADDED Requirements

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
