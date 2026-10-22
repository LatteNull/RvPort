## Context

现有正式 Tree-sitter C/C++ Frontend 能产出 `constexpr_condition`，但它把整个 `if_statement` 作为位置和值，且 `CppEvidenceNormalizer` 没有承接该 kind；`template_declaration` 也会以 unsupported Evidence 结束。Frontend 不产出 `enum_specifier`、`enumerator` 或枚举成员引用，Local Detector 的 `architecture_candidate` 仅绑定 macro/preprocessor。实际运行现有 `enum class Backend { scalar, avx2 }; if constexpr (B == Backend::avx2)` fixture 会得到 0 个 Finding 和 2 个 `normalization.unsupported-evidence-kind` 诊断。

现有 knowledge 已从固定版本 GCC/LLVM 数据中提供 `targetFeatures` 和 `architectureAliases`，其中包括 `avx2`、SSE/AVX512 特性和大量 x86 CPU/architecture 名称。因此缺口主要在结构 Evidence、引用关系和保守分类，不需要创建第二套 enum 专用知识或修改两份冻结 compiler fact 文件。

## Goals / Non-Goals

**Goals:**

- 对 C/C++ enum 声明、成员声明、成员引用及其 constexpr/switch/case 选择位置生成精确、项目相对、可追溯的 Evidence。
- 在没有 compilation database 时仍提供 Tree-sitter 结构基线，在 Clang enrichment 可用时增加真实 declaration/reference binding；两者均不得执行项目代码。
- 复用现有 architecture/feature knowledge，把疑似架构枚举名称表达为 candidate，并通过 Evidence Graph 判断它是否真的控制 x86 依赖以及对 RISC-V 是 selected、inactive 还是 unknown。
- 在默认 Schema V2 Finding 中提供自包含的 enum 证据链；显式 V1 保持顶层结构、artifact、退出码和旧 constexpr 规则身份。
- 为所有新增或修改业务模块补齐隔离单元测试与 90% line / 80% branch 容器门禁。

**Non-Goals:**

- 不扫描所有 identifier，不用源码正则补造 enum 语义，不把字符串、注释或普通变量当作 enum。
- 不求值任意 C++ 常量表达式，不实例化模板，不运行预处理器、编译器、构建命令或测试，也不声称真实 RISC-V 编译结果。
- 不因枚举成员名字包含 x86/AVX/SSE 就直接判 blocker；不把 ARM-only、OS、内核、驱动、板级内容加入扫描范围。
- 不增加新的主结果文件、不设计 Schema V3、不修改后端或生产容器。
- 不修改 `clang-x86-entries.json`、`gcc-x86-entries.json` 或本 change 之外的 knowledge production policy；`amd64`/`x64` 等尚未 accepted 的 alias 继续 deferred。

## Decisions

### 1. Frontend 只产出有语法边界的 enum Evidence

新增 scanner-owned Evidence kinds：

- `enum_declaration`：enum/enum class 的名称、style 和精确声明 span。
- `enum_member_declaration`：单个 enumerator 的 spelling、qualified name、所属 enum declaration Evidence ID、initializer 是否存在和精确 token span。
- `enum_member_reference`：被语法或 Clang binding 识别为 enumerator 使用的 token，携带 qualified name、binding status、可用的 declaration Evidence ID 和使用上下文。

现有 `constexpr_condition` 保留，但 Tree-sitter 应投影 condition value 而不是整个 `if_statement`；switch/case 中的枚举引用通过 `enum_member_reference.metadata.referenceContext` 表达。Tree-sitter 使用两阶段局部索引：先收集本文件 enum/member，再绑定同文件限定或唯一非限定引用。跨文件、多个同名成员和无法绑定的引用保留 partial/ambiguous，不按遍历顺序选择。可选 Clang enrichment 映射 `ENUM_DECL`、`ENUM_CONSTANT_DECL` 以及 referenced cursor 为 enum constant 的 `DECL_REF_EXPR`，提供跨 include/translation-unit 的高置信绑定。

选择这一方式而不是生成所有 identifier Evidence，是为了让 Frontend 保持结构化和有界：普通声明、变量、函数名、注释和字符串不会进入 enum 路径。选择 Tree-sitter baseline 加可选 Clang enrichment，而不是强制依赖 Clang，是为了让无 compilation database 的项目仍然得到可解释结果。

### 2. Normalizer 保留声明与引用身份，不在此层分类

`CppEvidenceNormalizer` 将上述 Evidence 映射为 `enum_declaration`、`enum_member`、`enum_reference` 和 `selection_condition` NormalizedFact，稳定 ID 使用项目相对路径、完整 token span、qualified name、scope 和 compilation context。metadata 保留 declaration Evidence IDs、binding status、enum style、reference context、producer 与解析完整性。

Normalizer 同时正式承接 `constexpr_condition`，消除当前 unsupported 诊断。它只验证引用形状并规范化值，不判断成员属于 x86、RISC-V 或 portable，也不通过文件读取补全缺失声明。

### 3. 枚举名称匹配复用现有知识，但结果始终从 candidate 开始

为 enum member/reference 定义独立 matcher。matcher 对完整 spelling、qualified name 末段，以及按 `_`、`-`、namespace 和 camel/digit 边界拆分的 identifier components 做确定性匹配，复用 `targetFeatures`、`architectureAliases` 和适用的 `platformMacros` KnowledgeEntry。匹配必须是完整 component，不允许 `avx2_counted` 之类的任意子串命中；装饰名称如 `BACKEND_AVX2`、`X86_AESNI` 可以由独立 component 提供候选依据。

即使命中 accepted KnowledgeEntry，enum 名称也只是项目自定义标签，Observation 初始状态仍为 `candidate`。Knowledge provenance 用于解释“为什么疑似架构相关”，不等价于“代码依赖该 ISA”。未知名称没有 fake knowledge；仅当它包含现有受审计的强架构 family token 时才允许无 knowledge 的 structural candidate。

### 4. Evidence Graph 使用声明—成员—引用—选择—依赖链

Graph index 新增 `enum_type`、`enum_member` 和 `selection_predicate` Entity，并使用现有关系词汇构造有界关系：

```text
source file ─defines────▶ enum type
enum type   ─contains───▶ enum member
condition   ─selects────▶ enum member
x86 call    ─guarded_by─▶ condition
enum member ─matches────▶ KnowledgeEntry（通过 Observation/knowledge refs 表达）
```

同文件唯一绑定可为 complete；Clang semantic binding 可为 complete；同名非限定引用、多声明候选、缺少声明、动态表达式和 parser recovery 分别产生 ambiguous/partial/unknown relation 与稳定 reason。未实例化 `template <Backend B>` 只证明条件引用成员，不能证明 `B` 的取值。switch/case 与 if/if constexpr 共用 selection predicate 抽象，但本 change 不实现任意 data-flow 或 constexpr evaluator。

选择复用现有 `defines`、`contains`、`selects`、`guarded_by`，是为了不扩大 Schema V2 的封闭 edge vocabulary。内部可记录更具体 relation metadata，但投影不得让消费者自行猜关系。

### 5. 分类由关系强度决定，而不是由 enum 名称决定

分类格固定为：

- 只有 enum member/reference candidate：`unknown / candidate-evidence-not-sufficient`，non-blocking、non-actionable。
- 完整证明 candidate 条件保护真实 knowledge-backed x86 intrinsic/API/type/asm，但目标选择未知：`actionable_non_blocking`，表示需要补充或确认迁移分支。
- 完整证明 RISC-V 目标会选择该 x86 分支：`blocking_issue`。
- 完整证明 RISC-V 排除该分支，或选择 RISC-V/generic/portable sibling：`guarded_inactive`。
- 声明/引用冲突、模板未实例化、动态 selector 或路径预算截断：保持 `unknown` 并保留 break/Diagnostic。

ARM 枚举成员可作为同一 enum 的上下文或 alternative，但不能独立形成本 x86-to-RISC-V scanner 的 Finding。RISC-V、generic、portable、scalar 成员可以帮助建立 sibling role；它们也不单独形成 x86 Finding。

### 6. Schema V2 复用核心 vocabulary，通过命名空间 extension 表达 enum 细节

枚举 Finding 的 `fact.kind` 使用已有 `architecture_probe`；enum declaration/member/reference/condition chain step 使用已有 `source_evidence`，关系使用已有 `defines`、`contains`、`selects`、`guarded_by`、`matches_knowledge` 和 `classified_as`。enum 特有字段放入 `org.rvport.kb-scanner.architecture-enum` extension，至少包含 role、enumType、member、qualifiedName、referenceContext 和 bindingStatus。

这样无需改变 `schemaVersion: "2.0"` 的封闭核心枚举，也不会让旧 V2 consumer 因遇到新 core enum value 而验证失败；详情页仍可从 step title、symbol、source/context 和 extension 完整展示链路。链断裂时使用现有 `missing_reference`、`multiple_candidates`、`dynamic_expression`、`type_conflict` 与预算 reason。

显式 V1 对 `if constexpr` 架构枚举分支继续投影为 `CPP.X86.CONSTEXPR_ARCH_BRANCH`；其他枚举候选使用稳定的 `C_CPP.X86.ARCH_ENUM_CANDIDATE` rule ID。两者不改变 V1 顶层字段、必需 Finding 字段、summary 计数单位、三个 artifact 名称或原子发布。

### 7. 测试按业务模块隔离并增加纵向 fixture

更新 frontend、knowledge-detection、evidence-graph、classification-assessment、projection-reachability 和 schema-v2-projection inventories。每个实质修改模块必须有直接实例化的 unit suite，在 `kb-scanner-test` 容器中单模块达到 90% line / 80% branch；Tree-sitter/Clang cursor、KnowledgeSnapshot、GraphStore、Projector/file writer 分别使用小型真实 grammar fixture 或 fake/in-memory boundary。

纵向 fixtures 覆盖 C/C++ scoped/unscoped enum、显式 initializer、qualified/unqualified reference、if constexpr、普通 if、switch/case、RISC-V/generic sibling、跨文件唯一/歧义声明、parser recovery、普通 enum、注释/字符串/变量近似词和装饰 identifier。真实 component 必须证明现有 constexpr fixture 从 0 Finding 恢复为可追溯结果，且 AVX 与 compiler fact 基线没有无关漂移。

## Risks / Trade-offs

- [Tree-sitter 不提供完整 C++ name resolution] → 只把同文件唯一绑定标为 complete；跨文件或重名引用依赖可选 Clang，否则显式 ambiguous/unknown。
- [enum 名称可能只是标签而非真实 ISA 依赖] → 初始状态始终 candidate，只有连接到真实 x86 Evidence 和目标选择 proof 才升级。
- [装饰 identifier 拆分可能产生误报] → 只在 enum AST 范围内运行、按完整 component 匹配、加入大量 near-miss 负例，并禁止任意 substring。
- [加入 enum graph 增加节点和路径数量] → 只索引候选 enum/member/selection 使用，沿用 depth/visited/path budget 并测试确定性截断。
- [V2 封闭词汇扩展会影响旧 consumer] → 不增加核心 fact/step/edge enum value，使用已有 `architecture_probe`/`source_evidence` 和命名空间 extension。
- [旧 V1 rule 语义比新关系模型粗] → 仅在兼容 projector 中映射稳定 rule ID；所有事实、状态和链路仍来自新 snapshots，不恢复 YAML/Legacy 执行。

## Migration Plan

1. 冻结当前 0 Finding/2 unsupported diagnostics 基线、现有 enum fixture、AVX 结果和两份 compiler fact SHA-256，并扩展机器可读 test inventories。
2. 先接入 Tree-sitter/Clang enum Evidence 与 Normalizer，确保普通 identifier 不扩张且 `constexpr_condition` 不再 unsupported。
3. 接入 knowledge-backed candidate matcher和 enum graph/proof，再接入保守分类。
4. 接入 V2 extension/chain 和显式 V1 rule 映射，运行默认 V2、显式 V2 和显式 V1 差异合同。
5. 在独立测试容器运行逐模块覆盖、enum component、AVX、事实数据合同和完整回归；验证后关闭容器。

回滚时可以回退本 change 的代码与 specs；报告版本选择、事实文件和上游 snapshots 不需要迁移。若新 enum 分析在某类项目产生噪声，分类必须先退回 unknown，不能通过回退到 Legacy 或关闭其他 x86 检测解决。

## Open Questions

- 跨 translation unit 的无 compilation database、非限定枚举引用是否值得后续增加项目级符号解析？本 change 默认保持 ambiguous/unknown，不把它作为完成阻塞项。
- `amd64`、`x64` 等 deferred alias 是否进入 accepted knowledge 仍由后续 knowledge-production change 决定，本 change 不临时补词。
