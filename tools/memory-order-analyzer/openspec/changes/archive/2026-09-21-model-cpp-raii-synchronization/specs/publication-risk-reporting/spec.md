## ADDED Requirements

### Requirement: Cite A4 evidence without changing P4 result semantics

PublicationRiskReport 或 additive wrapper SHALL 引用采用或拒绝的 A4 proof、mutex/owner/thread/held-region、profile、完整性和 gap；既有 finding code、severity、discharged、unknown、`safety=not_established` 与 0/3/2/1 退出码语义 MUST 保持不变。面向用户的说明和建议 SHALL 同时提供中文与英文。

#### Scenario: Archived mutex sample is discharged in the bounded model
- **WHEN** `safe/03_pthread_mutex.cpp` 的锁定本地副本通过完整 A4 proof 消解原候选
- **THEN** 报告说明“在受限同 mutex 模型内消解”、证据链与限制，不输出“线程安全”或“全程序安全”

#### Scenario: A4 is unavailable
- **WHEN** 候选依赖 RAII 同步但 A4 未请求、失败或 partial
- **THEN** 保持 unknown/partial 和现有退出码规则，不把零 proof 计作零风险

### Requirement: Preserve candidate-relevant exit-code priority

正式 P4 risk 仅在没有更高优先级候选相关 A4/A2 缺口时触发 `3`；存在相关 partial/unknown/frontier 时 SHALL 返回 `2`，无效或全部不可用返回 `1`，完整无正式风险返回 `0`。A4 自身的完成状态不得覆盖 P4 的风险优先级。

#### Scenario: One candidate is risky and another has an A4 gap
- **WHEN** 报告同时存在正式风险和候选相关 RAII 未决缺口
- **THEN** 依照既有完整性优先规则选择退出码并分别保留两类证据，不用 A4 完成度抹除风险或缺口
