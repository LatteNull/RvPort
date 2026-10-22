## ADDED Requirements

### Requirement: Consume only complete A4 mutex proofs in publication assessment

P4 adapter SHALL 仅消费 schema/profile/引用有效且候选相关完整的 A4 mutual-exclusion proof，并保留原 `SinglePublicationProtocolGraph`、finding/discharged/unknown 和安全语义。AST-only、类型/函数名、词法 scope、partial held-region 或 A4 零候选 MUST NOT 直接产生 risk 或 discharged。

#### Scenario: Publication accesses share a proven mutex
- **WHEN** P4 候选的发布/消费冲突访问落入同一 A4 受限 mutex proof 且其他候选条件完整
- **THEN** P4 可按既有类别在限定模式内消解该候选，并引用 A4 证明而不改写 P4 graph 版本

#### Scenario: RAII evidence is incomplete
- **WHEN** candidate-relevant A4 profile、异常路径、对象或 owner 状态任一不完整
- **THEN** P4 结果为 unknown/partial，不能回退为“没有同步”的正式风险，也不能误判 discharged

### Requirement: Keep mutex reasoning separate from atomic publication proofs

A4 mutex proof MUST NOT 被当作 atomic reads-from、release sequence、fence 或 modification-order 证明；P4 原子发布规则和不支持边界 SHALL 保持不变。

#### Scenario: A relaxed atomic protocol also uses an unrelated mutex
- **WHEN** relaxed flag/payload 候选旁存在另一个 mutex 的完整 A4 proof
- **THEN** 不以无关 mutex 消解 atomic publication-order-risk，继续按对象和路径相关性评价
