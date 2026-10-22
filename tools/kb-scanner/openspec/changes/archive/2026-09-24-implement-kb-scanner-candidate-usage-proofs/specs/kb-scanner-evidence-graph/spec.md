## ADDED Requirements

### Requirement: 用途证明必须保持非执行性质与可核查闭包

Evidence Graph SHALL 保存候选使用、绑定、控制、逃逸及 semantic role 的真实 provenance，自动 role proof SHALL 引用完整的作用域摘要和支持闭包。用途关系 MUST NOT 直接进入执行可达、alternative 或构建选择判定；单一无依据 source_file 到 role 边不得构成自动排除证明。

#### Scenario: 完整纯数据用途

- **WHEN** Analyzer 已闭合候选全部相关使用
- **THEN** Graph SHALL 提供精确 fact/subject/configuration/root 的 role relation、非空完整 ProofPath 和可核查的使用计数及支持引用
- **AND** 原始执行 graph/proof SHALL 保持，不被用途关系替换

#### Scenario: 只有部分数据来源

- **WHEN** 输入可证明 selector 来源于数据但无法解释其受控调用
- **THEN** Graph SHALL 保存局部来源与 unknown 断点
- **AND** MUST NOT 生成 scopeComplete=true 或伪造 selected/alternative_to

### Requirement: 用途引用和预算必须在消费前闭合

Graph 与消费边界 SHALL 验证 proof 连续端点、对应 role relation、支持引用、统计一致性和 truncated 状态。重复、悬空、跨配置、部分角色或冲突用途 MUST NOT 被升级为完整排除。

#### Scenario: Proof 标 complete 但实际截断

- **WHEN** proof.truncated 为 true、缺少对应 role relation、支持范围不完整或使用计数不一致
- **THEN** SHALL 拒绝排除并保留原候选与诊断
- **AND** 不得仅相信 scopeComplete 或 complete 字符串
