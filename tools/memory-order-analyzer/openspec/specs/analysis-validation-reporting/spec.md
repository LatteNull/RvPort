# analysis-validation-reporting

## Purpose

定义独立、版本化且可复现的验证请求、报告、准确性/完整性指标和扩展决策，确保 P1–P4 观察结果与人工真值保持边界。

## Requirements

### Requirement: Define independent versioned validation contracts

系统 SHALL 为 `AnalysisValidationRequest`、`AnalysisValidationReport` 和 `AnalysisExtensionDecision` 定义严格 v1 schema、kind、runner/policy 版本、确定性排序与跨产物引用；报告 SHALL 引用 suite、truth、真实工程 profile、P1–P4 请求/产物和可选 backend bundle 的 canonical digest。未来版本、未知字段、混合 profile、悬空引用或依赖替换 MUST 被拒绝。

#### Scenario: A complete validation product set is consumed

- **WHEN** 请求、suite、truth、P1–P4 结果和报告的版本、身份、预算与 digest 一致
- **THEN** 消费者接受并能从每个 metric/assessment 回溯到输入与观察证据

#### Scenario: A P4 report is replaced after validation

- **WHEN** AnalysisValidationReport 引用的 PublicationRiskReport digest 与当前提供文件不同
- **THEN** 报告被判陈旧或无效，不把新旧代际结果拼接

### Requirement: Expose an explicit validation CLI without changing existing commands

系统 SHALL 提供 `validate-analysis --request --artifact-store --output --worker`，要求新的空输出目录，按显式 suite/profile/预算执行，不扫描目录猜测最新产物、不扩大 scope、不原生链接且不运行目标程序。stdout 只输出最终合法报告 JSON，stderr 用于日志；P1–P4 既有 CLI 与退出码 MUST 保持不变。

#### Scenario: All required validations match

- **WHEN** 请求的语料和真实工程阶段完整、truth 全部匹配且必需 gate 通过
- **THEN** 发布全部引用、报告和决策记录并退出 0

#### Scenario: A complete run has a truth mismatch

- **WHEN** 全部计划阶段完成但出现 expected/observed 不匹配或必需阈值失败
- **THEN** 报告保留 mismatch 证据并退出 3，不把它伪装成工具执行失败

#### Scenario: Usable results are incomplete

- **WHEN** 已有可用结果但存在 partial、unknown、预算截断或显式请求后端不可用
- **THEN** 报告保留已知 mismatch 与 frontier 并退出 2；partial 优先于 3

#### Scenario: The request is invalid or wholly unavailable

- **WHEN** schema/依赖无效、输出目录非空或所有必需输入不可用
- **THEN** 命令退出 1 并尽力输出小型合法失败报告，不删除历史结果

### Requirement: Preserve P1 through P4 products and semantic boundaries

验证 runner SHALL 把 ModuleFacts/RunReport v2、EffectSummary v1、ThreadContextGraph v1、PublicationRiskReport v1 及相关 sidecar 作为只读依赖，不补字段、不回写 unknown、不更改缓存身份或安全结论。验证成功、truth 匹配、零 finding 或外部工具一致 MUST NOT 将 `safety` 提升为已建立。

#### Scenario: A P4 case matches reviewed truth

- **WHEN** 一个正确对照或风险 case 的全部期望与观察一致
- **THEN** 只记录 validation matched，原 P4 `safety=not_established` 和 P1–P3 报告语义不变

#### Scenario: Validation explains an existing unknown

- **WHEN** 人工裁决为某 unknown 提供更具体解释
- **THEN** 解释保存在 validation/adjudication 层，不修改原始产物或推广到其他上下文

### Requirement: Report layered completeness with exact denominators

报告 SHALL 分别统计 request/input、compile、P1、P2、P3、P4、truth comparison、real-project sampling、performance 和 backend evaluation 的 complete/partial/failed/not_run，以及计划/成功 TU、调用、对象、同步、candidate、assessment、finding、discharged、unknown、unsupported、excluded 与 frontier 的 hit/total。失败、截断和未运行项 MUST 留在分母；零分母比例为 null。

#### Scenario: One translation unit times out after findings exist

- **WHEN** 部分 TU 已产生 finding 而另一个计划 TU 超时
- **THEN** 保留 finding、超时 TU、完整原分母和预算，整体完整性不为 complete

#### Scenario: No publication candidate exists

- **WHEN** 输入处理完整但 P4 候选分母为零
- **THEN** candidate ratio 为 null，并只陈述支持范围内无候选，不显示 100% 安全或准确率

### Requirement: Compute accuracy only from eligible reviewed truth

系统 SHALL 对具备完整人工 truth 的固定语料按 finding code 计算 TP/FP/FN、strict precision/recall、supported-only 条件指标、exact-match 和 abstention/unknown 比例，并公开每个分母。truth 预期 finding 而分析返回 unknown/unsupported SHALL 计入 strict recall 未检出，同时在 abstention 中单列；未经审核、陈旧或不适用 case MUST NOT 进入准确率分母。

#### Scenario: A known risky case becomes unknown

- **WHEN** truth 要求某 finding，而 P4 因完整性缺口返回 unknown
- **THEN** strict recall 记录一个未检出，supported-only 指标不伪装处理成功，并单独增加 abstention

#### Scenario: Every eligible denominator is zero

- **WHEN** 过滤无效 truth 后没有可评价 case 或 finding
- **THEN** 对应 precision/recall 为 null 并说明原因，不输出 100%

### Requirement: Separate real-project sampling from whole-project accuracy

真实工程报告 SHALL 公开 deterministic seed、分层规则及 finding/discharged/unknown/unsupported 各层的计划与抽中样本，并保存人工裁决状态、证据和未裁决项。只有已裁决样本可以计算样本指标，MUST NOT 将其外推为全工程召回率、误报率或安全结论。

#### Scenario: Only findings are manually reviewed

- **WHEN** 人工样本没有覆盖 unknown、discharged 或无候选层
- **THEN** 报告明确选择偏差，只给 finding 样本结果，不宣称全工程 precision/recall

#### Scenario: A sampled item lacks enough evidence

- **WHEN** 裁决者无法从保存的 source/IR/线程/对象证据确认类别
- **THEN** 样本状态为 inconclusive 且留在抽样分母，不被强制标成 TP 或 FP

### Requirement: Measure cold and warm performance reproducibly

规模验证 SHALL 对相同 request 至少记录 cold/warm 成对运行的逐阶段 wall/CPU time、峰值 RSS、产物字节、工作预算、cache hit/miss 和环境指纹，并计算排除时间/路径/资源字段后的 semantic digest。cold/warm 语义 digest MUST 一致；预算耗尽 SHALL 为 partial 并保存 frontier。

#### Scenario: A warm cache changes semantic output

- **WHEN** 相同输入和策略的 warm run 产生不同 candidate、assessment 或 evidence digest
- **THEN** 确定性 gate 失败并保存差异，不能仅报告加速比例

#### Scenario: The run exceeds its resource budget

- **WHEN** 达到 wall、memory 或工作量上限
- **THEN** 保存已完成阶段、实际计数和未处理计划，性能/完整性状态不为 complete

### Requirement: Produce evidence-based extension decisions with bilingual explanations

`AnalysisExtensionDecision` SHALL 分别记录 B1 CMake scope、`std::thread`、更强指针分析、fence/RMW 的阻塞 case/TU/candidate 数、潜在覆盖收益、证据来源、成本/兼容性风险、`recommend`/`defer`/`insufficient-evidence` 状态及人工确认。面向用户的 detail/suggestion/decision 字段 SHALL 提供中文与英文字段，机器身份与排序不得依赖翻译文本。

#### Scenario: Unknown calls dominate the real-project frontier

- **WHEN** 可追溯统计表明未知指针/间接调用阻塞的候选显著多于其他类别
- **THEN** 指针分析候选记录实际分母和受影响切片，但仍需人工确认，不能自动创建 change

#### Scenario: Evidence is insufficient for a priority

- **WHEN** 某扩展只有少量、不完整或未裁决样本
- **THEN** 状态为 insufficient-evidence，中英文理由说明缺口，不用主观分数伪造推荐

### Requirement: Report source and binding completeness as separate validation layers

`AnalysisValidationReport` 的 AST-assisted 扩展 SHALL 分别统计 profile replay、SourceSemanticFacts、ProgramEntityIndex、entity binding、expression binding、canonical overlay 和下游 candidate slice 的 complete/partial/failed/not_run 及 hit/total。失败、歧义、截断与未运行项 MUST 留在分母；零分母比例为 null，且不得折叠进原 P1–P4 完整性字段。

#### Scenario: Source extraction completes but expression binding does not

- **WHEN** 全部 TU AST 成功且实体绑定完整，但无 debug 导致部分表达式无法映射
- **THEN** source/entity 层为 complete、expression 层为 partial，并保留受影响 candidate 分母

### Requirement: Quantify AST-assisted benefit and regressions against one truth set

报告 SHALL 对相同 reviewed truth 和固定预算并列 IR-only 与 AST-assisted 的 exact match、TP/FP/FN、strict precision/recall、supported-only 指标、abstention、运行时间、峰值 RSS、产物大小和 cache 行为，并列出新增命中、新增误报、仍未知和回退 case。任一模式 partial 时 MUST 保留严格 FN/abstention 语义，不得只发布改善百分比。

#### Scenario: Recall improves while one false positive appears

- **WHEN** AST-assisted 模式减少 FN 但新增 FP
- **THEN** 报告同时公开两个变化、case identity 和证据，不以单一综合分数掩盖回退

#### Scenario: Cold and warm reports differ semantically

- **WHEN** 相同 AST-assisted request 的 cold/warm candidate、binding 或 finding digest 不同
- **THEN** 确定性 gate 失败并保存差异，性能结果不得标为通过

#### Scenario: Downstream source evidence is actually consumed

- **WHEN** P2/P3/P4 以显式 source-evidence bundle 完成分析
- **THEN** 验证报告的 downstream consumption 层记录已计划/已消费/失败的依赖与候选分母，不再沿用索引阶段的 `not_run 0/0`

+### Requirement: Report degraded results by analysis mode and language

验证报告 SHALL 对 C11、C17、C++17、C++20 分别列出 planned、completed、eligible、ast-ir、ir-only、ast-only、failed、source candidate、formal candidate、TP/FP/FN、strict precision/recall、supported-only 指标和 abstention；零分母为 null。报告 MAY 提供合并汇总，但 MUST NOT 用汇总通过掩盖任一语言 profile 的缺失、误报或门禁失败。

#### Scenario: C profiles pass while C++ has a false positive

- **WHEN** C11/C17 全部匹配而 C++17 的 unknown RAII 被错误报告为风险
- **THEN** C++17 单独记录 FP/门禁失败，合并指标不能使验收通过

#### Scenario: AST-only matches the expected degradation

- **WHEN** truth 要求 source candidate/unknown 且报告没有正式 finding
- **THEN** 记录 mode/status exact match 和 abstention，不把该 case 计为风险 TP 或安全 TN

### Requirement: Compare cold and warm degraded evidence deterministically

相同请求的 cold/warm 报告 SHALL 在排除时间、路径、资源和 cache counters 后具有相同 TU mode、failure class、source candidate、dependency slice、formal assessment 和 semantic digest；报告 SHALL 分阶段记录 wall/CPU、峰值 RSS、产物字节与 cache hit/miss。

#### Scenario: A cached transient timeout changes a TU mode

- **WHEN** warm run 因复用 transient worker failure 而从 ast-ir 变为 ast-only/failed 或反向变化
- **THEN** 确定性和 cache gate 失败，性能结果不得标为通过

### Requirement: Report lifecycle truth separately from risk accuracy

验证报告 SHALL 分别列出 C11、C17、C++17、C++20 的计划、完成、失败、unknown/abstention，以及 callback、instance 和 lifecycle relation 的 expected/actual、exact match、FP/FN 与证据完整性。生命周期关系指标 MUST NOT 与 P4 risk TP/FP/FN 合并，也不得从 exact match 外推全程序线程安全或风险检测准确率。

#### Scenario: All lifecycle relations match a bounded corpus
- **WHEN** 固定 A3 truth 的 callback、实例和关系均 exact match
- **THEN** 报告只声明该版本语料和能力范围内匹配，继续列出排除项、unknown 与选择偏差

#### Scenario: Risk truth is also executed
- **WHEN** 同次验收运行既有 P4 人工真值
- **THEN** 风险 TP/FP/FN 与 A3 lifecycle FP/FN 分表报告，不能用任一组数字替代另一组

### Requirement: Publish profile cache performance and completeness evidence

报告 SHALL 记录实际 libstdc++/libc++ fingerprint、模型版本、工具链、命令、cold/warm wall/CPU/RSS/输出、cache hit/miss、semantic digest、预算和完整性；瞬态失败或 profile mismatch MUST 明确显示，不得当作缓存性能样本或 supported profile。

#### Scenario: Warm cache changes lifecycle semantics
- **WHEN** warm run 的实例、关系、guard、unknown 或 semantic digest 与 cold run 不同
- **THEN** 确定性 gate 失败并保留差异，不能只因运行更快而通过验收

### Requirement: Report A4 semantic metrics per language profile

验证报告 SHALL 对 C11、C17、C++17、C++20 分别列出 planned、completed、eligible、ast-ir、ir-only、ast-only、failed、formal candidate、proof、TP、FP、FN、strict precision/recall、abstention、profile 和预算状态；零分母 SHALL 为 null。合并汇总 MUST NOT 掩盖任一语言/profile 的缺失或失败。

#### Scenario: One C++ profile abstains unexpectedly
- **WHEN** C++20 libc++ 支持范围 case 因实现错误返回 unknown，而其他语言全部匹配
- **THEN** C++20 单独记录 strict FN/abstention 且 required gate 失败

### Requirement: Separate proof accuracy from coverage and program safety

报告 SHALL 分开呈现单元覆盖率、语义 truth、profile eligibility、性能/cache 和完整性；90% 覆盖率、zero finding、proof 命中或 exact match MUST NOT 表述为全程序安全或真实工程准确率。

#### Scenario: Coverage passes but one mutex identity is wrong
- **WHEN** 所有行/分支覆盖率达标而 truth 中一个 mutex/owner/proof identity 不匹配
- **THEN** 语义 gate 失败并记录错误关系，不能用覆盖率替代修复

### Requirement: Publish deterministic cold and warm A4 evidence

验证报告 SHALL 记录 cold/warm 命令、输入/依赖/profile/model 摘要、cache hit/miss、semantic digest、实例/关系/guard/unknown 差异、时间和内存。相同依赖下 cold/warm 语义 MUST 一致；瞬态失败不得成为长期语义缓存命中。

#### Scenario: Warm run drops an unknown edge
- **WHEN** warm run 与 cold run 的 frontier、guard、proof 或 semantic digest 不同
- **THEN** 确定性 gate 失败并保留差异，不因 warm run 更快而通过
