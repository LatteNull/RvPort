## Why

当前 staged KB Scanner 能准确识别局部 x86 头文件、intrinsic 和向量类型，但宏定义、宏调用、include、分支与替代实现之间没有跨文件关系，因此既会遗漏宏替换体中的 x86 依赖，也不能为后续构建可达性和分类提供 proof path。AVX 真实项目已证明单纯对齐 Legacy 数量会保留漏报和错误分类，所以现在需要建立 scanner-owned Evidence Graph，并改用人工审计事实验收新管线。

## What Changes

- 引入可替换的 `GraphStore` 合同和经容器基准验证的 NetworkX `MultiDiGraph` adapter，并保持第三方图对象不泄漏到领域合同。
- 建立项目、文件、宏、分支、符号、调用和实现的稳定 Entity，以及 `defines`、`includes`、`invokes_macro`、`expands_to`、`calls`、`guarded_by`、`has_branch`、`alternative_to` 和 `reachable_from` 关系。
- 扩展基础 C/C++ Frontend，以结构化、可定位且无副作用的 Evidence 保留函数式宏参数和 replacement tokens；宏定义不得被伪装成函数调用。
- 对同项目头文件的简单宏建立从调用点到定义、再到最终 x86 intrinsic 的有界 proof path；循环、截断、缺失 include 和不支持预处理语义必须显式返回 partial/unknown。
- 识别条件编译的 sibling branch，并在有证据时关联 x86 实现与 RISC-V、generic、portable、scalar 或 fallback 替代实现；本阶段不判定 blocking、severity 或项目 readiness。
- 将 AVX/AVX2 真实项目固化为人工审计的关系验收基线，验证宏定义与宏体 intrinsic 关系，不以 Legacy 的 Finding 总数、严重度或 blocking 结论作为 correctness oracle。
- 立即固化 Legacy 隔离策略：新 Graph、Analyzer 和测试不得导入 Legacy parser/evaluator/YAML；Legacy 仅保留默认 CLI 与输出兼容基线，物理删除仍留给最终 cut-over change。
- 为每个新增或实质修改的 Frontend、GraphStore、Graph Analyzer、proof-path 和关系归一模块提供隔离单元测试，并在唯一 `kb-scanner-test` 容器中执行逐模块 90% 行 / 80% 分支覆盖门禁。
- 保持现有 `scan-result.json` `schemaVersion: "1.0"`、顶层字段和三个 artifact；本阶段使用 recording/no-op Projector，不生成第二套主结果。

## Capabilities

### New Capabilities
- `kb-scanner-evidence-graph`: 定义可替换图存储、稳定图身份、跨文件宏/include/分支/替代实现关系、有界 proof path、完整性状态和真实项目关系验收。

### Modified Capabilities
- `kb-scanner-cpp-frontends`: 增加可定位的宏参数/replacement token Evidence，并严格区分宏定义、宏使用和函数调用。
- `kb-scanner-core-pipeline`: 将真实 Graph Analyzer 接入 staged qualification，传播 Relation、proof completeness 和 Diagnostic，但不提前切换默认 CLI。
- `kb-scanner-knowledge-and-local-detection`: 将“宏和替代实现关系”从纯 deferred 推进为消费现有 Observation/Knowledge 的可追溯图分析，同时继续将构建选择与最终分类留给后续 change。

## Impact

- 影响 `kb_scanner/core`、`kb_scanner/frontends/cpp`、新增 graph/analyzer 模块、staged qualification profile、测试 inventory 和容器测试 runner。
- 新增并锁定 NetworkX 作为首个图 adapter；任何依赖安装和性能/内存基准只在独立测试容器中执行。
- 不修改两份既有 Clang/GCC facts、新增 generated/curated knowledge 的事实语义、Legacy YAML，也不复用 Legacy DTO/evaluator。
- 不实现 Make/Autoconf/CMake/RPM 选择求值、不执行项目代码、不做真实 RISC-V 编译，不分析 OS、内核、系统调用、驱动或板级迁移。
