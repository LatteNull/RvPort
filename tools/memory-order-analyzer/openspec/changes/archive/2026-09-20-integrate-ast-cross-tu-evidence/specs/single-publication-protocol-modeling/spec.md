## ADDED Requirements

### Requirement: Resolve cross-TU publication objects through verified overlays

在显式 AST-assisted publication 请求中，P4 SHALL 使用 resolved program entity/object 和有效 SourceIRBinding，将生产者与消费者 TU 中的 flag/payload artifact-local identities 关联到 canonical object。只有 scope、profile、定义和绑定依赖全部兼容时才能组合；ambiguous/conflict/unresolved MUST 进入 unknown/frontier。

#### Scenario: Flag declaration and definition are in different translation units

- **WHEN** extern flag 声明、唯一外部定义和各自 LLVM global 形成可回溯绑定
- **THEN** P4 可把发布 store 与消费者 load 放入同一候选，并保留原始与 canonical object evidence

#### Scenario: Two possible payload definitions remain

- **WHEN** payload 对应 weak/ODR 候选且缺少唯一链接选择
- **THEN** 候选为 partial/unknown，不任取一个对象形成风险或 discharge

### Requirement: Specialize direct wrappers without using source order as memory proof

P4 SHALL 可使用 verified direct source callee/entity binding 传播 atomic load 经有限 compare/cast/直接返回 wrapper 到消费者成功分支的参数和返回值关系；实际 observation、IR control dependency、payload access 和 memory ordering 仍必须由 P4 LLVM 局部事实证明。`EffectSummary.order`、行号或一般 AST statement order MUST NOT 作为 SB/SW/HB。仅当 `SourceSemanticFacts` 给出同一 `CompoundStmt` 相邻 expression statement 的精确 source sequence，且两端唯一投影到同一线程上下文的实际 IR effect 时，P4 可把它作为局部 must-before 补充；遇到 declaration/control/loop/return 必须断开，它不得生成 RF/SW/HB。

#### Scenario: A direct cross-TU load wrapper controls success

- **WHEN** wrapper target、返回值 binding、consumer compare/branch 和相关 atomic IR load 均唯一且在预算内
- **THEN** P4 可建立成功观察实例和发布证明链，同时分别标注 source 与 IR 证据

#### Scenario: Wrapper binding is source-only

- **WHEN** AST 能识别 wrapper 但优化/无 debug 导致返回值至 IR load 的绑定不完整
- **THEN** 保留 wrapper 候选并输出 unknown，不以源码函数体替代 IR 观察证明

#### Scenario: Publication store precedes payload write in adjacent expression statements

- **WHEN** 精确 source sequence 证明发布 store 所在 expression statement 在 payload write 所在相邻 expression statement 之前，且两端唯一绑定到同一线程实例中的真实 IR effect
- **THEN** P4 可据此形成 `publication-store-too-early` 的局部顺序证据；不得由此推导 reads-from、synchronizes-with、happens-before 或全程序安全

### Requirement: Compute completeness from candidate-relevant dependencies

AST-assisted P4 SHALL 同时报告全请求完整性和每个 publication candidate 的相关依赖完整性。与候选无实体、调用、对象、线程或绑定依赖的失败不得自动清空该候选；任一相关 TU/实体/binding/IR 事实缺失则该候选保持 partial/unknown。相关性闭包和分母 MUST 可审计。

#### Scenario: An unrelated scoped translation unit fails AST parsing

- **WHEN** 失败 TU 不在某候选的 canonical object、call、thread 或 binding 依赖闭包内
- **THEN** 请求总体为 partial，而候选可继续按其完整依赖接受风险或受限 discharge

#### Scenario: The producer binding is incomplete

- **WHEN** producer TU 的发布 store 与 source flag 无法唯一绑定
- **THEN** 该候选为 partial/unknown，即使其他 scope 成员完整

#### Scenario: Unrelated external declarations remain unresolved

- **WHEN** flag/payload、producer/consumer、thread 和 IR order 的候选相关闭包完整，但 scope 中还有无关系统声明或其他 source entity 为 unresolved
- **THEN** 全局 source report 可保持 partial，该 publication candidate 仍必须评价为 finding/discharged/unknown 之一，不得因全局 partial 被清空

#### Scenario: Relevant facts exist but no protocol candidate is formed

- **WHEN** P3 已建立可能并行 producer/consumer 实例，且 P4 可见 atomic flag 和 payload access，但 object/binding/control 组合后协议候选数为零
- **THEN** 报告输出 `publication-candidate-unresolved` 的中英文诊断、结构化 missing reasons 和 relevant dependency 分母，不以空 frontier 返回 inconclusive
