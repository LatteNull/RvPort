## ADDED Requirements

### Requirement: Report degraded results by analysis mode and language

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
