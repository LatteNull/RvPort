## ADDED Requirements

### Requirement: x86 可达性、替代实现和 portability gap 必须一致分类
Migration Classifier SHALL 对同一语义根因共同考虑 selected source/build proof、knowledge-backed x86 dependency 与 RISC-V/generic/portable alternative proof。完整 proof 证明 x86 dependency 对目标可达时 SHALL 产生相应 blocking/actionable Classification；只有适用输入范围完整且没有有效 alternative 时 SHALL 产生 portability gap，输入不完整时 MUST 保持 unknown。

#### Scenario: selected 源码依赖 AVX 且无替代实现
- **WHEN** 完整 build/source proof 证明目标选择 AVX 依赖，且完整 alternative 分析证明不存在 RISC-V/generic/portable 实现
- **THEN** Classifier SHALL 产生引用完整 proof 的 blocking/actionable Classification 和 portability gap
- **AND** summary、Finding 与 Assessment SHALL 对该根因使用一致状态

#### Scenario: alternative 枚举不完整
- **WHEN** selected x86 dependency 已证明但 sibling/alternative 输入范围不完整
- **THEN** x86 dependency Classification SHALL 保留，alternative/portability 维度 SHALL 为 unknown
- **AND** `portabilityGaps=0` MUST NOT 被用来暗示已经证明没有 gap

#### Scenario: x86 路径被完整排除
- **WHEN** 完整互斥 proof 证明含 x86 dependency 的 source/target 对目标 inactive/not_selected
- **THEN** Classification SHALL 为 guarded/inactive、non-blocking 和 non-actionable
- **AND** 该局部结论 MUST NOT 单独升级整个项目为 ready

### Requirement: 项目 Assessment 必须使用闭合 proof 而非报告计数
Migration Assessor SHALL 从有效 Classification、Observation、Relation 和 ProofPath 组合 target reachability、x86 dependency、alternative 与 portability gap 维度，并 SHALL 使 `summary.readiness` 和兼容 summary 计数反映同一状态。它 MUST NOT 从 Finding 总数、未命中或聚合方式反推项目结论。

#### Scenario: AVX-only 项目证据完整
- **WHEN** selected build/source 路径完整覆盖项目输入、依赖 x86/AVX 且没有有效 RISC-V/generic alternative
- **THEN** Assessment SHALL 产生 `x86_only` 并列出对应 blocking dimensions 与稳定引用
- **AND** metadata SHALL 保持 `staticScopeOnly=true`、`compiled=false`、`testsExecuted=false`

#### Scenario: 可达性或输入完整性不足
- **WHEN** build/source reachability、alternative 或测试选择任一适用维度为 partial/unknown
- **THEN** Assessment SHALL 保持 provisional/unknown 并列出阻塞更高结论的维度
- **AND** 它 MUST NOT 声称真实编译成功、测试通过或 RISC-V ready

### Requirement: 分类评估修正必须通过隔离单元与字段级 AVX 门禁
本 change 修改的 classification decision table、portability-gap policy、assessment dimension reducer 和 summary mapping SHALL 分别映射到隔离单元测试，并 SHALL 在 `kb-scanner-test` 容器中达到每模块至少 90% line / 80% branch；之后 SHALL 运行 AVX 字段级人工对照、schema 1.0 consumer contract 和完整回归。

#### Scenario: 运行分类评估单元门禁
- **WHEN** 独立容器执行 classification/assessment unit inventory
- **THEN** 合成 Observation/Proof 测试 SHALL 覆盖 complete、inactive、alternative-present、alternative-absent、unknown 和冲突输入并满足覆盖门槛
- **AND** 真实 scanner 端到端结果 MUST NOT 替代隔离单元覆盖

#### Scenario: AVX 人工对照验证结论而非只验证数量
- **WHEN** scanner 扫描修正后的 AVX fixture
- **THEN** 回归 SHALL 同时验证 symbol、span、macro definition closure、build occurrences、reachability、portability gap、Assessment 和聚合 diagnostics
- **AND** 任一缺失、额外或状态不一致 SHALL 使门禁失败
