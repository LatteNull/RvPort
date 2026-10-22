## ADDED Requirements

### Requirement: Establish bounded RAII mutual exclusion from complete evidence

同步组合器 SHALL 仅在同一普通非 robust `MutexInstance`、成功 acquire、成对 release、访问包含于闭合 held-region、线程可能并行且候选相关证据完整时建立受限 mutual-exclusion/synchronization proof。proof SHALL 保留 mutex、owner、访问、thread、guard、source/IR/profile 依据；不同 mutex、may-alias、失败路径或未知 kind MUST NOT 被提升。

#### Scenario: Protected conflicting accesses are fully proven
- **WHEN** 两个可能并行线程对同一普通对象的冲突访问均位于同一已证明 mutex 的完整临界区
- **THEN** 输出受限互斥证明供下游消解该候选，并明确不构造通用 HB 或全程序安全证明

#### Scenario: One release path is missing
- **WHEN** 任一异常/正常出口不能证明 owner release 或 mutex 配对
- **THEN** 相关 held-region/proof 为 partial，候选不得因另一条完整路径而整体消解

### Requirement: Prohibit unsound ordering shortcuts

系统 MUST NOT 直接将 AST scope、源代码先后、P2 `EffectSummary.order`、P3 reads-from candidate、A3 join/detach、类型名、函数名或单个 lock/unlock presence 当作 sequenced-before、synchronizes-with、happens-before 或互斥证明。

#### Scenario: Source scope looks balanced but IR diverges
- **WHEN** AST 中 guard 包围访问，而 IR/CFG 显示未知 wrapper、提前退出或对象绑定歧义
- **THEN** 输出候选和 gap，不生成 must-held、SW 或 HB

### Requirement: Keep unsupported synchronization conservative

try/timed/recursive/robust mutex、condition variable、semaphore、rwlock、自定义同步和超出模型的 ownership 操作 SHALL 进入稳定 unknown/frontier；相关 gap MUST 阻断该候选的确定风险或消解，除非被独立完整证据证明无关。

#### Scenario: A recursive mutex protects both accesses
- **WHEN** C++ 类型或 profile 表明使用 `recursive_mutex`
- **THEN** A4 首版不套用普通 mutex 模型，报告 unsupported synchronization 并保持候选 unknown
