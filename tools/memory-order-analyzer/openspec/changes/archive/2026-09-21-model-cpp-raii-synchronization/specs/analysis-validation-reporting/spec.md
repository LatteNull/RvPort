## ADDED Requirements

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
