## ADDED Requirements

### Requirement: X86 Detector 必须按架构归属约束结构候选
Local Detector SHALL 在产生 inline asm 或 declaration attribute Observation 前结合现有 x86 KnowledgeEntry 和 AnalysisSnapshot 中可验证的 branch/selection role 判定候选资格。命中 x86 知识的事实 SHALL 保持 `confirmed_local`；位于已证明非 x86 分支的事实 MUST NOT 产生 x86 Observation；没有足够归属证据但仍具有汇编架构风险的事实 MAY 产生一个 `candidate`。Detector MUST NOT 通过隐藏的 ARM 或其他架构指令黑名单作出排除。

#### Scenario: ARMCRC32 分支包含 AArch64 汇编
- **WHEN** inline asm Evidence 位于可追溯的 ARM/AArch64 branch 且未命中任何 x86 instruction/register KnowledgeEntry
- **THEN** Detector MUST NOT 产生 x86 confirmed 或 candidate Observation
- **AND** 该排除 MUST NOT 被解释为已完成 ARM→RISC-V 迁移分析

#### Scenario: 汇编命中既有 x86 知识
- **WHEN** 完整 inline asm Evidence 命中现有 Clang/GCC/curated x86 instruction 或 register KnowledgeEntry
- **THEN** Detector SHALL 产生一个引用完整 Evidence 和全部适用知识来源的 `confirmed_local` Observation
- **AND** foreign/unknown 兜底 MUST NOT 覆盖该精确知识命中

#### Scenario: 无法归属的汇编
- **WHEN** 完整 inline asm Evidence 未命中 x86 知识且没有完整 foreign、RISC-V、portable 或 inactive branch proof
- **THEN** Detector MAY 产生一个 `candidate` 并记录 `unclassified_inline_asm` 依据
- **AND** 它 MUST NOT 被声明为 confirmed、blocking 或 RISC-V safe

#### Scenario: 混合架构 selector
- **WHEN** 条件同时包含 `__x86_64__` 与 `__aarch64__` 等多个架构分支语义
- **THEN** Analyzer/Detector SHALL 保留 x86 知识命中和可验证的 alternative/branch 关系
- **AND** 它 MUST NOT 因出现非 x86 token 而把整个条件或其 x86 证据直接过滤

### Requirement: 通用 declaration attribute 不得形成架构候选
Local Detector SHALL 仅对具有 target、target_clones、vector width、architecture alias 或已加载 target feature 知识语义的 declaration attribute 产生 Observation。sanitizer、visibility、packing、lifecycle 或其他没有架构选择/特性语义的通用属性 MUST NOT 产生 x86 candidate、hint 或 confirmed Observation。

#### Scenario: no_sanitize memory
- **WHEN** NormalizedFact 来自 `__attribute__((no_sanitize("memory")))`
- **THEN** Detector MUST NOT 产生 `target_attribute_candidate` 或其他 x86 Observation
- **AND** 该属性 MUST NOT 增加 Finding 或迁移问题计数

#### Scenario: target avx2
- **WHEN** declaration attribute 精确包含 `target("avx2")` 且 `avx2` 命中现有 x86 target feature KnowledgeEntry
- **THEN** Detector SHALL 产生 knowledge-backed `confirmed_local` Observation
- **AND** Observation SHALL 保留 KnowledgeEntry、Evidence 和 branch relation provenance

#### Scenario: 未知 target feature
- **WHEN** 属性种类明确为 target/target_clones 但 feature 无法由现有知识归属
- **THEN** Detector MAY 产生一个有明确 attribute-kind 依据的 candidate
- **AND** 普通属性不得借用该兜底路径

### Requirement: 候选去重必须以完整语义根和源码 span 为准
Normalizer 与 Local Detector SHALL 以 producer、source entity、configuration、完整语义 Evidence span 和 detector identity 建立候选根因；同一最外层 Evidence 的嵌套 AST 节点 MUST NOT 形成多个 NormalizedFact 或 Observation，不同源码 span 的独立语句 SHALL 保留为不同 occurrence。

#### Scenario: 九条 ARM 汇编具有嵌套节点
- **WHEN** Tree-sitter 为九条 asm 语句暴露 statement、qualifier 和 operand 子节点
- **THEN** 下游 SHALL 最多接收九个完整 inline asm facts，且 foreign 排除后不得形成 x86 Observation
- **AND** Evidence/Observation 数量 MUST NOT 随 grammar 暴露的嵌套节点数增长
