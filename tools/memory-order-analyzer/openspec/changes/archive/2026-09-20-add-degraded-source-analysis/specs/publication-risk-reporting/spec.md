## ADDED Requirements

### Requirement: Separate degraded source candidates from P4 risk products

风险报告或其 additive wrapper SHALL 分别引用 SourceCandidate 与 P4 protocol/assessment；source-only 候选不得获得 finding code、severity、discharged 状态或风险计数。面向用户的 mode、evidence、failure、missing evidence、limitation 和 suggestion SHALL 同时提供中文与英文字段，机器 identity 不依赖翻译。

#### Scenario: Archived mutex sample becomes inconclusive

- **WHEN** `safe/03_pthread_mutex.cpp` 的相关 `std::lock_guard` 只形成未知 RAII SynchronizationGap
- **THEN** 报告将原确定风险降为 unknown/partial，说明缺少 RAII mutex 证明，不宣称样例安全

### Requirement: Preserve risk exit codes under degraded orchestration

组合入口 SHALL 保持 0=完整无正式风险、3=存在正式 P4 risk 且请求不因更高优先级缺口而 incomplete、2=存在可用 partial/unknown/source candidate/预算截断、1=无效或全部不可用。SourceCandidate MUST NOT 单独触发 3，零 source candidate 或零 finding MUST NOT 表示安全。

#### Scenario: Formal risk and AST-only candidate coexist

- **WHEN** 一个完整候选产生 P4 risk，另一个计划候选仅为 AST-only
- **THEN** 组合请求按 incomplete 优先退出 2，同时保留正式 risk 和 source candidate 的独立计数
