## Context

默认 CLI 已切换到完整 staged pipeline，并通过 Compatible Report Projector 输出 schema 1.0。对 AVX 示例项目的人工复核表明，底层检测事实数量是完整的：39 个 x86 header、362 个向量类型、360 个直接 intrinsic call、18 个宏替换终端引用、45 个注释提示以及 24 个构建参数 occurrence 均被恢复。差距主要位于两个边界：一是 AnalysisSnapshot 中已有的 symbol、完整 span、宏定义和 occurrence 信息没有完整投影；二是 build target、source、宏定义和 x86 dependency 之间的 proof closure 不足，使分类、portability gap 和 readiness 过度停留在 unknown。

本 change 是跨 graph/analyzer/classifier/assessor/projector 的修正，但不改变 scanner 的四层总体结构，不替换现有结果合同，也不引入新的运行时依赖。所有验证继续只在独立 `kb-scanner-test` 容器内执行。

## Goals / Non-Goals

**Goals:**

- 让每个发布 Finding 能从现有 Evidence/Relation 恢复语义 symbol、完整 source span 和闭合的 trace 引用。
- 让聚合 Finding 保留所有底层 occurrence，而不改变既有 Finding 数量与顶层主位置语义。
- 建立 build target → selected source → x86 dependency 的有界静态 proof，并对局部重复宏定义做基于可见性和 configuration 的消歧。
- 让 diagnostics、Classification、portability gap 和项目 Assessment 对同一 proof 状态给出一致、可读且保守的结果。
- 以修正后的 AVX 人工基线和字段级断言防止回归。

**Non-Goals:**

- 不设计 schema 2.0，不增加全局 Evidence/Relation 表或第二套主结果。
- 不执行 compiler、linker、build tool、test runner、项目命令或网络访问，也不验证真实 RISC-V 构建与运行。
- 不修改 compiler-derived Clang/GCC facts、curated knowledge 内容或知识生产流程。
- 不恢复 Legacy/YAML 生产路径，不处理 OS、内核、系统调用、驱动、板级或 RVWMO 语义分析。
- 不建模 `uname` 在交叉编译场景选错架构；已识别的探测值仍按正确目标架构处理。

## Decisions

### 1. 继续使用“丰富内部模型 → schema 1.0 兼容投影”

现有顶层 `location.line/column`、Finding、summary 和三个 artifact 保持不变。新增信息只进入已有对象型 `trace` 的可选字段：完整 evidence closure、primary span、occurrence count/occurrences 和聚合 diagnostic provenance。旧消费者可忽略这些字段，新消费者无需解析第二套报告。

替代方案是直接引入 schema 2.0 的全局图表。它能减少重复引用，但会扩大后端、持久化和用户界面的迁移范围；当前问题均可由兼容 trace 表达，因此本 change 不采用。

### 2. Projector 只解析引用，不重新扫描文本

在 projection reference index 上增加确定性的闭包解析：从 Classification/Observation 的 Evidence、Relation 和 ProofPath ID 出发，递归收集被关系引用的 source/target Evidence，并验证对象存在、类型匹配和完整性。`symbol` 的选择顺序固定为主语义 Evidence 的结构化 value、KnowledgeEntry symbol、终端 symbol Relation target；不得从 snippet 重新使用正则猜测。

完整 span 复用内部 Evidence 的 start/end 坐标写入 `trace.primarySpan`；顶层兼容 `location` 仍只保留主 Evidence 的 file/line/column。闭包断裂时保留现有局部 Finding 和 failed/partial Diagnostic，不伪造 symbol 或位置。

### 3. 聚合 Finding 显式携带 occurrences

Finding 的既有语义根因和聚合 identity 不变。对于 24 个构建参数命中这类多 occurrence 根因，mapper 在 `trace.occurrences` 中按 path、span、configuration、selection status 和 Evidence ID 确定排序，并提供 `trace.occurrenceCount`。主位置仍按既有稳定策略选择，因此 summary/finding count 不因表达细节变化而膨胀。

替代方案是每个 occurrence 发布一个 Finding；这会改变现有计数和消费者行为，故不采用。

### 4. 关系问题先结构化，再在投影边界聚合诊断

Graph Analyzer 为 unresolved/ambiguous relation 保留稳定 reason code、relation kind、configuration、位置和相关 ID，不为每个相同问题生成面向用户的重复文案。Projector 的 Diagnostic Aggregator 按 code、reason、relation kind、stage 和 severity 分组，输出一条代表诊断，并在可选 details 中保留 count、代表位置和引用列表。排序与输入遍历顺序无关。

不会简单丢弃重复诊断：聚合后的 count 与引用仍必须覆盖全部原始问题。

### 5. 可达性只由完整的 build/source proof 提升

Build Selection Analyzer 复用已恢复的 target、source membership、condition、configuration 和 argument Evidence，建立 selector/configuration → target → source → x86 dependency Relation/ProofPath。只有每条边均 complete 且 configuration 一致时，source dependency 才能被标为 selected/reachable；缺边、动态表达、冲突或预算截断继续为 partial/unknown。

宏定义消歧先按 translation unit/include 可见性、configuration 和定义位置过滤，再按结构化 macro identity 选择。只有唯一可见定义或多个完全等价定义时形成 complete definition proof；仍有多个非等价候选时保持 ambiguous。不会通过“取第一个定义”消除 unknown。

### 6. Classification、portability gap 与 readiness 共用同一 proof 状态

Classifier 以闭合 proof 将 selected x86 source/build dependency 分类为 blocking 或 actionable，并显式引用 alternative 分析。只有相关输入范围完整且证明不存在 RISC-V/generic/portable alternative 时，才形成 portability gap；alternative 范围不完整时该维度保持 unknown，而不是以 `portabilityGaps=0` 暗示不存在差距。

Assessor 只组合 Classification/Observation/Proof 状态，不从 Finding 数量反推项目状态。静态证据充分的 AVX-only 项目可以得到 `x86_only`；证据不充分时继续 provisional/unknown。所有 readiness 仍携带 `staticScopeOnly=true`、`compiled=false`、`testsExecuted=false`。

### 7. 人工 baseline 区分 scanner 缺陷与基线错误

修正 AVX 人工基线中三个与真实 token 起点不一致的列号，并把 24 个已支持的 Makefile flag occurrence 从 deferred 区域迁入正式断言。回归同时断言数量、path/start/end span、symbol、definition closure、occurrences、分类和 diagnostics 聚合，避免只比较总数。

### 8. 每个业务模块必须有隔离单元测试

机器可读 inventory 为每个新增或实质修改模块映射独立 unit suite。Graph/reachability 测试使用内存 snapshot/store 和 fake budget；projection 测试使用构造的 snapshots 与 temporary/fake writer；classification/assessment 测试使用手工 Observation/Proof，不读取真实项目；diagnostic aggregation 测试使用合成重复记录。每个模块在 `kb-scanner-test` 容器中达到至少 90% line / 80% branch，之后再运行 AVX component/contract 和完整回归。真实 compiler facts、Tree-sitter/libclang 集成或端到端测试不计入隔离单元覆盖率。

## Risks / Trade-offs

- [trace 中 occurrence/evidence 增多导致报告变大] → 仅对 Finding 相关闭包投影、稳定去重，并设置现有 traversal budget；超限显式 partial。
- [宏消歧错误把 ambiguous 提升为 complete] → 只接受 configuration/可见性支持的唯一或等价定义，冲突候选保持 unknown，并加入顺序扰动测试。
- [portability gap 语义调整改变摘要数值] → 以人工 proof baseline 和 approved correction 记录预期变化，同时保持字段类型与计算来源稳定。
- [诊断聚合掩盖单个位置] → 聚合对象保留原始 count、代表位置及全部稳定引用，HTML/log 提供摘要而 JSON trace 可追溯。
- [跨模块修改引入回归] → 先通过逐模块 unit gate，再运行 schema 1.0 consumer、AVX、build-selection、no-side-effect 和全量容器回归。

## Migration Plan

1. 先修正并冻结 AVX/build 人工 baseline，使预期事实和真实源码一致。
2. 实现 graph/reference closure、宏消歧和 build-source proof，并以隔离单元测试验证 complete/partial/unknown。
3. 实现兼容 trace/symbol/span/occurrence 与 diagnostic aggregation。
4. 调整 classifier/assessor/summary 语义，运行字段级 AVX 对照和旧消费者合同测试。
5. 在独立测试容器中运行逐模块覆盖门禁与完整回归；通过后同步 delta specs 并归档。

回滚时可回退本 change 的实现和 baseline 变更；由于 schemaVersion、必需字段和 artifact 未变，无需迁移已存储报告。不得通过恢复 Legacy 生产路径回滚。

## Open Questions

无阻塞问题。`trace` 可选字段的最终命名可在实现时与现有 projection contract 的命名风格对齐，但必须满足本设计定义的语义和兼容约束。
