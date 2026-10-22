## ADDED Requirements

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
