## ADDED Requirements

### Requirement: Report A4 synchronization evidence as an independent overlay

报告 SHALL 独立展示 A4 request/model/profile、mutex/owner/held-region、线程实例、proof、完整性、frontier、预算、缓存和对 P3/A3 的稳定引用，不得把 A4 字段内嵌成旧 `ThreadContextGraph v1` 的新含义。每条诊断 SHALL 同时提供中文和英文 detail、limitation、suggestion。

#### Scenario: A mutex proof is complete
- **WHEN** A4 建立完整受限互斥 proof
- **THEN** 报告列出双方线程、访问、mutex、acquire/release、路径、profile 和模型限制，并保持 `safety=not_established`

#### Scenario: Profile mismatch blocks the proof
- **WHEN** 实际标准库/ABI fingerprint 与注册 profile 不匹配
- **THEN** 报告中英文说明实际/期望 identity、缺失资格和复现建议，不把它写成没有 mutex

### Requirement: Distinguish absence, incompleteness and zero proofs

报告 MUST 区分未请求 A4、请求失败、partial/unknown、完整运行但零候选、存在候选但零 proof 以及成功 proof；零 proof、零 finding 或缓存命中 MUST NOT 表示程序安全。

#### Scenario: Complete analysis finds no RAII candidates
- **WHEN** A4 完整运行且 scope 中没有相关 RAII/mutex 构造
- **THEN** 报告为 complete-zero-candidate，并与未运行、失败或证据不完整分开
