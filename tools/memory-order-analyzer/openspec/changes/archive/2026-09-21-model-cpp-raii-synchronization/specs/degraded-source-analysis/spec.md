## ADDED Requirements

### Requirement: Resolve synchronization gaps only with candidate-equivalent A4 proof

A2 `SynchronizationGap` SHALL 按候选依赖切片与 A4 mutex/owner/path/profile identity 关联。只有 A4 为同一候选提供完整替代 proof 时，才可关闭 `unmodeled-raii-lifetime`、`mutex-kind-unknown` 或 wrapper gap；无关 proof、may-alias、AST-only 或 partial A4 MUST NOT 消除 gap。

#### Scenario: Archived safe mutex case has a complete A4 proof
- **WHEN** 本地锁定的 `safe/03_pthread_mutex.cpp` 候选具有完整同 mutex RAII proof
- **THEN** 对应未知 RAII gap 被有依据地关闭，候选可在受限模型内消解，但报告不宣称程序安全

#### Scenario: A proof belongs to another mutex
- **WHEN** A4 proof 完整但 mutex/object/thread/path 与待评估候选不同
- **THEN** 原 gap 保留且候选继续 partial/unknown

### Requirement: Preserve AST-only and failure semantics for A4

当 BC、SourceIRBinding、profile 或 A4 worker 不可用时，A2 MAY 保留 AST mutex/RAII source candidate，但 SHALL 输出 partial/unknown 和缺失证据；AST 单独 MUST NOT 建立 acquire/release、held-region、SW、HB、risk 或 discharged。

#### Scenario: A4 worker budget is exhausted for one TU
- **WHEN** 一个相关 TU 的 source facts 可用但 A4 IR/状态机预算耗尽
- **THEN** 依赖该 TU 的候选降级，已证明无关的其他候选可继续分析，顶层记录不完整
