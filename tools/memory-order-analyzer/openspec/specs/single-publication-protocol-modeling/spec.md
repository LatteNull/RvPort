# single-publication-protocol-modeling

## Purpose

规范一次性发布协议候选的语义构造、受限 reads-from 唯一化、完整发布证明链、风险分类和保守未知边界。

## Requirements

### Requirement: Build publication candidates from semantic identities
系统 SHALL 以 publisher/consumer ThreadInstance、payload 写/读、flag 写/读、成功观察、对象范围、谓词、guard、独立执行顺序和 MHP 构造一次性发布候选；候选 MUST 由值流、控制流和对象证据识别，不得依赖变量/函数名称或源码邻近。不同对象、范围不重叠、单线程或已证明不并行的组合 SHALL 被明确排除。

#### Scenario: Renaming the signal does not change the result
- **WHEN** 两个输入除 atomic flag 名称分别为 `ready` 和 `signal` 外具有相同事实和身份关系
- **THEN** 生成等价协议候选和 assessment，不使用名称提高或降低置信度

#### Scenario: The consumer uses another flag
- **WHEN** payload read 由不同对象的 observation 控制
- **THEN** 不把 publisher flag write 与该 observation 配成同一发布协议

### Requirement: Require an explicit one-shot protocol boundary
首版候选 SHALL 要求精确 flag/payload 范围、唯一发布写者、相关发布不重复、消费者成功 gate 可识别、线程实例未因递归/循环合并为不确定 cardinality，且相关 scope/边界/调用依赖足以枚举可能写者。多写者、重复发布、ABA、对象生命周期不明或未知 clobber MUST 进入 unknown/frontier，不得任意选择一个写者。

#### Scenario: One writer publishes once
- **WHEN** closed scope 内只有一个 single publisher effect 写入被成功谓词接受的值，且没有相关 clobber
- **THEN** 候选满足 one-shot 写者资格并保存枚举分母和无其他写者的证据

#### Scenario: Two publishers can write an accepted value
- **WHEN** 两个可能并行实例或一个 repeated effect 均可写入成功谓词接受的 flag 值
- **THEN** 候选为 unknown/unsupported，不通过排序或选择首个写者继续证明

### Requirement: Unique reads-from only under value exclusion
系统 SHALL 仅在 flag 初值精确且被成功谓词拒绝、发布值精确且被接受、没有其他可接受值写、对象/位宽/syncscope 兼容、相关边界完整且没有 RMW/CAS/release-sequence 语义时，把 P3 reads-from candidate 提升为该受限候选的唯一读取来源。该提升 MUST 局限于 P4 协议图，不得回写 P3 或声称完整 modification order。

#### Scenario: Initial false and unique published true distinguish the source
- **WHEN** flag 初值为 0、唯一发布写为 1、消费者只在观察值非零后使用 payload，且所有其他资格满足
- **THEN** 成功观察的受限 reads-from 唯一指向该发布写，并记录值排除证明

#### Scenario: Initial and published values are indistinguishable
- **WHEN** 初值也满足成功谓词，或另一个写入值同样满足谓词
- **THEN** 保留 reads-from 候选集合并将协议判断降为 unknown

### Requirement: Establish only a complete restricted publication chain
受限模式内的消解 SHALL 同时要求 payload 写 must-before flag 发布写、发布 store 具有 release 或 seq_cst、成功观察 load 具有 acquire 或 seq_cst、syncscope 可跨线程、reads-from 已按本规格唯一化、成功观察在 payload 使用之前并控制该使用。P2 `EffectSummary.order`、P3 candidate 共存、相邻位置或目标机器指令 MUST NOT 独立满足任何边。

#### Scenario: Release-acquire single publication is complete
- **WHEN** 唯一发布值由 release store 写入，成功 acquire load 读取该值，且两侧 payload 顺序和全部范围/线程条件均有证明
- **THEN** 候选记为 `discharged-within-single-publication-model` 并保存完整证明链，不输出全程序安全

#### Scenario: Release and acquire merely coexist
- **WHEN** 同对象存在 release store 和 acquire load，但读取来源、成功 gate或 payload 顺序未证明
- **THEN** 不建立 synchronizes-with/HB，候选保持 unknown

### Requirement: Classify ordinary conflicts and publication-order risks separately
系统 SHALL 在已识别协议内区分 `potential-data-race` 与 `publication-order-risk`，并允许用同一 `protocol_id` 分组多个 assessment。普通 flag/payload 的可能并行冲突且无完整 HB SHALL 产生 potential-data-race；atomic flag 缺少 release/acquire、acquire 位于 payload 使用之后、发布已证明早于 payload 写或 all-atomic relaxed 可能观察旧 payload SHALL 产生 publication-order-risk。严重性与证据等级 MUST 分开。

#### Scenario: Relaxed flag protects an ordinary payload
- **WHEN** payload 普通写/读可能并行，flag 发布/观察均为 relaxed 且其他 one-shot 条件满足
- **THEN** 输出相关联的 potential-data-race 与 publication-order-risk，并列明缺少的同步边

#### Scenario: All payload accesses are relaxed atomic
- **WHEN** payload 和 flag 均为 atomic relaxed 且消费者 gate 可识别
- **THEN** 不输出 ordinary data race，但输出可能观察旧 payload 的 publication-order-risk

#### Scenario: Acquire happens after the payload read
- **WHEN** release 发布存在，但控制消费的 observation 为 relaxed，另一个 acquire load 已证明位于 payload 使用之后
- **THEN** 输出 `acquire-too-late` 风险，后置 acquire 不保护先前读取

#### Scenario: Publication is proven too early
- **WHEN** flag 发布 store must-before 对应 payload 写
- **THEN** 输出 `publication-store-too-early` 风险；若两者顺序只是不明，则结果必须 unknown 而非同类 finding

### Requirement: Keep unsupported synchronization and relevant gaps conservative
consume、fence、RMW/CAS release sequence、`singlethread` scope、复杂 mutex、未知同步、通用别名、多写者、重复发布、ABA、`std::thread`/RAII 和对象回收 SHALL 保留原始事实并进入 unknown/frontier。相关缺口既不得被假设为同步，也不得被假设不存在；只有与候选证明切片无关的缺口可以不阻止局部 finding，但仍降低全局完整性。

#### Scenario: Fence publication pattern is encountered
- **WHEN** relaxed flag 依赖 release/acquire fence 才能形成同步
- **THEN** 首版报告 unsupported/unknown 并保存 fence 位置，不按 relaxed 直接报已确认风险，也不按 fence 共存消解

#### Scenario: An unrelated module is partial
- **WHEN** 某 TU 的缺口与候选线程、对象、调用及同步切片均无依赖
- **THEN** 已有候选 assessment 可保留，但顶层完整性反映该 partial，报告不得扩展为全程序结论

### Requirement: Never convert candidate absence into global safety
协议图 SHALL 区分 planned、candidate、evaluated、finding、discharged、unknown、unsupported 和 excluded。零候选、零 finding、全部已消解或分析 complete 只描述 `single-publication-risks-v1` 支持范围，MUST NOT 输出全程序安全或无并发缺陷。

#### Scenario: No supported protocol is found
- **WHEN** 全部计划项 complete 但没有符合首版 gate 和 one-shot 边界的候选
- **THEN** 结果为 no supported risk found，候选分母为零/null，safety 仍未建立

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
