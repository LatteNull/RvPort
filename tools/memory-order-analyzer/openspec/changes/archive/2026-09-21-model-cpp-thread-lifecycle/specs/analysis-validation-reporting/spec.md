## ADDED Requirements

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
