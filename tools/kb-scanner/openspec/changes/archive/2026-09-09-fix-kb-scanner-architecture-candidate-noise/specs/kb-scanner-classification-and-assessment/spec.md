## ADDED Requirements

### Requirement: Candidate evidence insufficient 只能表示真正未决的架构相关性
Migration Classifier SHALL 仅在 Observation 为有明确候选依据的 `candidate`、架构归属为 unknown 且引用完整有效时返回 `unknown / candidate-evidence-not-sufficient`。已证明 foreign、与架构无关或由重复子节点产生的输入 MUST NOT 形成该 Classification；遇到这种输入 SHALL 返回结构化合同 Diagnostic，而不是影响项目迁移结论。

#### Scenario: 未知 inline asm candidate
- **WHEN** Detector 提供 `unclassified_inline_asm` candidate 且没有 x86/foreign/portable 完整 proof
- **THEN** Classifier SHALL 返回非阻断、非操作的 unknown classification，reason 为 `candidate-evidence-not-sufficient`
- **AND** Assessment SHALL 保持 provisional 而不是 RISC-V ready 或 blocking

#### Scenario: 已证明 ARM 分支的汇编到达 Classifier
- **WHEN** 一个 Observation 标记为 foreign/arm 但仍被错误传入 Migration Classifier
- **THEN** Classifier SHALL 产生输入合同 Diagnostic 且不得生成 x86 migration Classification
- **AND** 该输入 MUST NOT 增加 finding、blocking、issue 或 candidate 计数

#### Scenario: 通用 attribute 到达 Classifier
- **WHEN** `no_sanitize` 等无架构语义 attribute 被错误标为 candidate
- **THEN** Classifier SHALL 拒绝将其解释为 `candidate-evidence-not-sufficient`
- **AND** Assessment MUST NOT 因该属性变为 provisional 或问题状态

#### Scenario: 确认 x86 Evidence 不降级
- **WHEN** Observation 引用完整 x86 KnowledgeEntry 并为 `confirmed_local`
- **THEN** Classifier SHALL 按现有 reachability/proof 规则产生 blocking、inactive 或 actionable non-blocking 分类
- **AND** 候选过滤 MUST NOT 把它降级为 unknown

### Requirement: 候选噪声修复必须具有逐模块单元覆盖门禁
本 change 实质修改的 branch attribution、Normalizer、Local Detector、Classification Policy 和 Assessment 输入聚合模块 SHALL 各自登记隔离单元测试，并 SHALL 在独立 `kb-scanner-test` 容器中达到每模块至少 90% line 和 80% branch 覆盖率。zlib、AVX 或全量回归 MUST NOT 替代该门禁。

#### Scenario: 审计测试清单
- **WHEN** 候选资格或架构归属业务模块新增、删除或重命名
- **THEN** 机器可读 inventory SHALL 同步记录 unit suite、fake/mock 边界和高层回归
- **AND** 缺失映射、模块零执行行或覆盖不足 SHALL 使容器门禁失败
