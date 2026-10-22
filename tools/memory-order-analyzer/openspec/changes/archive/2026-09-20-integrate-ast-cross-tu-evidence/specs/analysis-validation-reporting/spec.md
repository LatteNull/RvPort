## ADDED Requirements

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
