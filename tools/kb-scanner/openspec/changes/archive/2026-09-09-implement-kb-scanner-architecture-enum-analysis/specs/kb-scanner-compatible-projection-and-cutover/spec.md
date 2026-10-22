## ADDED Requirements

### Requirement: 架构枚举分析必须保持显式 Schema V1 兼容投影
显式 V1 Projector SHALL 从新的 enum Observation、Classification 和 proof snapshots 投影原 Schema 1.0 顶层结构与固定 artifact。if constexpr 中的架构 enum branch SHALL 使用既有 `CPP.X86.CONSTEXPR_ARCH_BRANCH` rule identity；其他结构化 enum candidate MAY 使用稳定 `C_CPP.X86.ARCH_ENUM_CANDIDATE` identity。兼容投影 MUST NOT 恢复 Legacy/YAML evaluator、改变默认 Schema V2、生成第二个主结果或把 candidate 伪装为 confirmed blocker。

#### Scenario: 显式 V1 扫描既有 constexpr fixture
- **WHEN** 用户以 `--schema-version 1.0` 扫描 `Backend::avx2` if constexpr fixture
- **THEN** V1 结果 SHALL 恢复 `CPP.X86.CONSTEXPR_ARCH_BRANCH` Finding，并保留现有必需字段、位置和 summary 计数语义
- **AND** `scan-result.json`、`scan-report.html`、`scan.log` 名称和 Schema 1.0 顶层字段 MUST 保持不变

#### Scenario: V1 投影孤立 enum candidate
- **WHEN** enum member 只有 candidate/unknown Classification
- **THEN** V1 Finding SHALL 保持非阻断、非操作和 unknown reachability，并可在兼容 trace 中携带结构化声明/引用摘要
- **AND** 它 MUST NOT 因 V1 字段较少而升级 severity 或丢失不完整 Diagnostic

#### Scenario: 默认扫描仍使用 V2
- **WHEN** 用户未传结果版本或显式传 `2.0`
- **THEN** Versioned Projector SHALL 只调用 V2 enum projection
- **AND** enum 投影失败 MUST NOT 静默回退 V1 或留下半套 artifact

#### Scenario: enum 功能不改变既有非枚举结果
- **WHEN** 输入不含 enum Evidence，或 enum 与架构知识无关
- **THEN** 显式 V1 的既有 x86 Finding、summary、Diagnostic、artifact bytes normalization 和退出码语义 SHALL 保持兼容
- **AND** AVX、compiler fact、comment hint、macro/build/test 既有回归中的未解释差异 SHALL 阻止 change 完成
