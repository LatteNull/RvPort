## Why

当前正式 C/C++ 管线虽然能够从 Tree-sitter 看到整个 `if constexpr` 节点，却不会提取 enum 声明、枚举成员或成员引用，Normalizer 也未承接 `constexpr_condition`。因此像 `Backend::avx2`、`X86_AESNI` 这类应当作为疑似架构选择线索的代码会产生 unsupported Evidence 诊断但没有 Finding，现有编译器派生 `targetFeatures` 与 `architectureAliases` 知识无法被使用。

这不是补一份硬编码枚举词表的问题，而是要补齐“语法事实 → 规范化事实 → 知识匹配 → 选择关系 → 分类 → 自包含报告”整条静态证据链，同时避免恢复全文件 identifier 正则扫描带来的误报。

## What Changes

- 为 C 和 C++ 增加有界的 enum Evidence：enum 声明、枚举成员声明、可解析的成员引用和精确的 constexpr/switch/case 条件位置；只消费 AST/Clang 语义，不扫描所有 identifier。
- 让 Normalizer 无损承接 enum 与 constexpr Evidence，保留声明/引用身份、限定名、源码 span、producer、compilation context、confidence 和解析完整性。
- 使用现有 `targetFeatures`、`architectureAliases`、`platformMacros` 等知识识别装饰后的枚举成员名称；名称命中只形成 candidate，不把枚举标签直接宣称为 x86 依赖。
- 在 Evidence Graph 中连接 enum 声明、成员引用、选择条件、被保护分支和下游调用/类型依赖；支持 complete、partial、ambiguous、inactive 和 unknown，不凭未实例化模板猜测 RISC-V 会选择哪个值。
- 扩展分类策略：孤立枚举线索保持非阻断 unknown；只有完整关系证明其保护真实 x86 依赖时才成为可操作结论，随后按 RISC-V selected/inactive/unknown 证据分别判为 blocking、guarded 或未决。
- Schema V2 Finding 继续作为默认结果，在单个 Finding 中展示 enum 定义、成员引用、选择条件、下游依赖、源码上下文和链路断点；显式 Schema V1 保留原顶层结构和三个固定 artifact，并为既有 `CPP.X86.CONSTEXPR_ARCH_BRANCH` 行为提供兼容投影。
- 为每个新增或修改的 Frontend、Normalizer、matcher、graph、classifier 和 projector 业务模块登记隔离单元测试，在独立 `kb-scanner-test` 容器内维持每模块至少 90% line / 80% branch，并增加真实 C/C++ enum component 与报告回归。
- 不执行编译、模板实例化、预处理、项目命令或测试；不涉及 OS、内核、系统调用、驱动、板级迁移，也不修改后端或生产容器。

## Capabilities

### New Capabilities

- 无；本 change 补齐现有 C/C++ 静态分析能力中的 deferred 枚举路径。

### Modified Capabilities

- `kb-scanner-cpp-frontends`: 从 deferred 提升为可定位的 enum 声明、成员、引用和选择条件 Evidence，并保持无全 identifier sweep 的边界。
- `kb-scanner-knowledge-and-local-detection`: 让枚举事实消费现有架构/特性知识并产生有依据的 candidate Observation，替换“普通枚举只能 deferred”的现状。
- `kb-scanner-evidence-graph`: 增加枚举声明—引用—条件—分支—依赖的有界关系和 proof path。
- `kb-scanner-classification-and-assessment`: 定义枚举 candidate 在 isolated、selected、inactive、ambiguous 和 incomplete 关系下的保守分类。
- `kb-scanner-report-schema-v2`: 在自包含 Finding evidenceChain 中投影 enum/condition step、关系、上下文与 break。
- `kb-scanner-compatible-projection-and-cutover`: 为显式 V1 投影恢复既有 constexpr 架构分支规则语义，同时保持 V1 字段与 artifact 合同不变。

## Impact

- 主要影响 `kb_scanner/frontends/cpp/`、`normalization/cpp.py`、`detectors/`、`analyzers/evidence_graph.py`、`classifiers/` 和 `projection/`，以及对应测试 inventory、fixtures 和 OpenSpec 主规格。
- 复用现有 Tree-sitter C/C++ 与可选 Clang 18 enrichment，不新增宿主机依赖；所有依赖和验证仍只存在于独立测试容器。
- `clang-x86-entries.json`、`gcc-x86-entries.json` 及当前 generated/curated knowledge 内容、分类、路径与 SHA-256 保持不变；本 change 只增加这些知识在 enum Evidence 上的使用方式。
- 默认 `scan-result.json` 继续使用 Schema V2，显式 `--schema-version 1.0` 继续兼容 Schema V1；`scan-result.json`、`scan-report.html`、`scan.log` 文件名及原子发布语义不变。
