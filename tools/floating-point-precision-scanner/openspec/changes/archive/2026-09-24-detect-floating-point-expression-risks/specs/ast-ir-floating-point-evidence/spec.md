## ADDED Requirements

### Requirement: 表达式风险 evidence 必须保留结构关系和证据强度
融合层 SHALL 为转换、比较/use、环境调用/摘要、归约 group、数学调用和架构 API facts 建立版本化多对多关系。关系 MUST 记录 source/IR refs、relation kind、binding method、profile/build-context refs、provenance、confidence class 和 ambiguity；结构化位置、声明身份、sidecar、inline chain 与 operand/use 关系 MAY 共同形成 strong/exact binding，名称或同行文本匹配 MUST NOT 单独产生确定性 binding。

#### Scenario: 隐式转换绑定 fptrunc
- **WHEN** 同一 TU/context 中唯一的 AST implicit narrowing 与 `fptrunc` 共享函数、范围、类型和 use provenance
- **THEN** evidence 建立 conversion-lowering relation，并保留两端类型与 binding method

#### Scenario: AST 归约绑定向量归约
- **WHEN** AST accumulator recurrence 与 build-faithful IR vector reduction 通过 sidecar 或唯一结构关系关联
- **THEN** evidence 使用 reduction-lowering 多对多关系引用循环、accumulator、phi/vector facts 和实际 flags

#### Scenario: 同一行多个比较无法区分
- **WHEN** 多个 AST comparison 与多个 `fcmp` 只有相同行号且缺少列、scope、operand 或 sidecar 区分
- **THEN** evidence 记录 ambiguous candidates，不任选一对支持 deterministic finding

### Requirement: 启发式判断不得改变底层 evidence 事实
`FloatingPointEvidenceBundle` SHALL 只表达可验证的 facts 关系和 binding confidence，不得把规则层的“容差不合理”“归约数值敏感”或“可能存在库差异”写成确定 evidence。规则产生 heuristic finding 时 MUST 引用原始 evidence refs 和固定 rationale code；该 finding 不得覆盖、重写或提升 evidence bundle 的 confidence。

#### Scenario: 仅能识别精确相等模式
- **WHEN** evidence 能确定源码比较与 IR `fcmp` 的关系，但没有业务容差或输入域证明
- **THEN** bundle 只发布比较 lowering 关系，规则可据此产生 heuristic assessment，但不得把脆弱性写成 exact evidence
