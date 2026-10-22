## ADDED Requirements

### Requirement: Block formal publication assessments on relevant degraded evidence

P4 additive 消费路径 SHALL 检查候选闭包中的 AST-only/failed 依赖和 `SynchronizationGap`。任一缺口可能改变线程、对象、访问、顺序或同步且无法证明无关时，候选 MUST 为 unknown，并列明缺失证据；不得输出 potential-data-race、publication-order-risk 或 discharged。无关缺口不清空完整候选，但降低请求级完整性。

#### Scenario: Unknown RAII may synchronize a reported conflict

- **WHEN** publication 候选的普通 payload 访问可能受未建模 RAII mutex 保护
- **THEN** 候选为 unknown，不能仅因 P3 没有 mutex 边输出 potential-data-race

#### Scenario: AST-only producer supplies no memory effects

- **WHEN** producer TU 只有 source facts，没有实际 payload/flag IR effect 和 ordering
- **THEN** 可保留 SourceCandidate，但不得形成或评价正式 publication protocol

#### Scenario: An unrelated failed TU is outside the protocol slice

- **WHEN** protocol 的线程、对象、调用、控制、同步和 IR 依赖完整，且失败 TU 可证明无关
- **THEN** P4 保留既有 finding/discharged/unknown 评价，顶层报告记录非完整 scope
