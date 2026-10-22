# bounded-object-provenance

## Purpose

规范 GCC/Clang C11、C17、C++17 和 C++20 的有界对象来源分析协议，以可审计的 AST/LLVM 证据形成保守对象候选、字段路径和直接跨 TU 绑定，同时严格保持同步与安全证明边界。

## Requirements

### Requirement: Publish an independent versioned bounded object provenance protocol

系统 SHALL 定义 `BoundedObjectProvenanceRequest v1`、`SourceObjectPathFacts v1`、`LLVMObjectProvenanceFacts v1`、`BoundedObjectProvenanceGraph v1` 和 `BoundedObjectProvenanceReport v1`，通过 kind、identity 与 canonical digest 显式引用 scope/profile、P1/P2、A1 及可选 P3/P4/A2/A3/A4 依赖。A5 产物 MUST 使用独立 schema、节点命名空间、artifact 和缓存，不得修改或重解释 P1–P4、A1–A4 的现有版本与报告语义。

#### Scenario: A5 is not requested
- **WHEN** 调用方只运行 P1–P4 或 A1–A4 且没有 A5 request/artifact
- **THEN** 既有输出、缓存、退出码和 unknown 语义保持不变，缺少 A5 不得解释为不存在对象别名

#### Scenario: A dependency has been replaced
- **WHEN** request 引用的 source、IR、entity、binding、summary 或 profile digest 与实际 artifact 不一致
- **THEN** 组合被拒绝并输出稳定的中英文引用错误，不从目录搜索替代文件或混合新旧事实

### Requirement: Separate entity, storage, subobject and runtime-instance identities

系统 SHALL 分离 program entity、字段声明、LLVM value、`StorageInstance`、`SubobjectPath`、`ObjectInstance`、摘要复用上下文、调用/分配实例和线程实例。`ObjectInstance` MUST 至少绑定显式 scope/profile、storage、子对象路径、address space 与调用或生命周期身份；字段声明只能作为路径 segment，不得单独充当运行时对象实例。

#### Scenario: Two instances access the same declared mutex field
- **WHEN** `a.mutex` 与 `b.mutex` 引用同一 `FieldDecl` 但 `a`、`b` 是不同 exact storage instances
- **THEN** 图输出两个不同 ObjectInstance/MutexInstance 候选，不因字段声明、名称、类型或偏移相同而合并

#### Scenario: One instance passes through a direct wrapper
- **WHEN** 同一 exact 对象及字段经合法直接调用参数和返回路径跨 TU 传递
- **THEN** 图保持原 storage/invocation identity 并追加调用证据，不把 callee parameter 或摘要模板登记成新的运行时对象

### Requirement: Extract C and C++ source object paths without claiming runtime aliasing

`SourceObjectPathFacts` SHALL 在与 BC 相同的锁定 Clang profile 下提取基表达式、`.`/`->`、嵌套 member、canonical record/field、字段序号、ABI offset/size/alignment、数组常量下标、宏 spelling/expansion、C union overlap group、C++ `this`/receiver 及参数/返回/调用关系。C11/C17 与 C++17/C++20 MUST 使用独立语言规则；AST-only facts MUST NOT 发布 runtime object、must/may alias、noalias、同步或安全结论。

#### Scenario: A nested C struct field is observed
- **WHEN** C17 源码访问 `root->inner.ptr` 且 record layout 完整
- **THEN** source facts 保存 root、两段字段路径、箭头/成员关系和 ABI 布局，同时仅将其标为 source candidate

#### Scenario: Union members have the same storage
- **WHEN** C11 union 的两个不同 member 被访问
- **THEN** 两条路径保存各自字段实体但共享 overlap group，不因字段名、类型或 ordinal 不同输出 disjoint

#### Scenario: C++ this selects a mutex field
- **WHEN** C++20 成员函数访问 `this->mutex`
- **THEN** source facts 将 `this` 保存为 receiver formal identity并把 mutex 保存为子对象路径，不把 `FieldDecl` 或成员函数实体当作动态对象

### Requirement: Produce auditable LLVM local pointer evidence using locked analyses

`LLVMObjectProvenanceFacts` SHALL 在已 hash/parse/verify 的原始 LLVM 21.1.8 BC 上只读使用 DataLayout、ValueTracking、BasicAA/AAResults、MemorySSA、DominatorTree、LoopInfo、AssumptionCache、TargetLibraryInfo 和 CaptureTracking。每个采用的 root/offset、AA、clobber、dominance、capture 与 returned-argument 查询 MUST 保存输入、结果、预算和原始/分析节点引用；不得通过正则 IR、变换 pass 或单一 aggressive root 猜测替代。

#### Scenario: A constant GEP reaches a local allocation
- **WHEN** 指针经过受支持 cast 和多层 constant GEP 且 DataLayout 可计算 base 与 offset
- **THEN** facts 保存原 alloca、累积 offset、address space、路径证据和访问范围，但不把可计算 GEP 单独解释为 in-bounds 或存活证明

#### Scenario: Phi has two underlying objects
- **WHEN** `getUnderlyingObjects` 和 CFG 证明一个 phi 可来自两个不同 storage instances
- **THEN** facts 保留两个带 predecessor guard 的候选，不采用 `getUnderlyingObjectAggressive` 任取一个 root

#### Scenario: Alias analysis returns MayAlias
- **WHEN** 两个 MemoryLocation 的 AA 查询结果为 MayAlias 或查询输入不在受支持局部边界
- **THEN** 证据登记 MayAlias/unknown 和原因，不输出 must-alias、noalias 或跨 TU object identity

### Requirement: Preserve finite guarded candidates and conservative unknown semantics

对象值域 SHALL 区分内部 `bottom`、发布的 `must` singleton、非空有限 `may` candidates 和带非空原因的 `unknown`。candidate SHALL 包含 ObjectInstance、可选 byte range、guard、proof、opposed evidence 和依赖切片；candidate 间为析取，guard 内为合取。候选、路径、循环或工作量超限 MUST 保留已有事实并使相关结果 partial/unknown，不得截断后伪装完整有限集合。

#### Scenario: Select arms normalize to the same object
- **WHEN** select 的全部可行分支在相同 profile/context 下规范化为同一 exact storage/path/range且没有相关 frontier
- **THEN** 结果可以折叠为 must singleton并引用每条分支和控制证据

#### Scenario: Candidate limit is exceeded
- **WHEN** phi/select、dynamic index 或递归调用产生的不同候选超过请求预算
- **THEN** 已知候选和 hit/limit 被保留，发布值为 unknown且报告 partial，不丢弃尾部候选后发布 may/must complete

### Requirement: Propagate pointer fields only through proven local memory definitions

系统 SHALL 对受支持私有栈槽和对象 pointer field 执行有限 store/load 传播。确定传播 MUST 要求 exact base/path/range、唯一支配 store、MemorySSA/AA 排除其他可达 clobber、指针未不受支持地逃逸、lifetime 有效且 guard 一致；MemoryPhi、多 store、MayAlias 写、unknown call、并发共享字段写、volatile/atomic pointer load、部分覆盖或 capture 超限 SHALL 产生 may/unknown而非旧值强更新。

#### Scenario: One private pointer field has one reaching store
- **WHEN** exact 对象的 pointer field 在 load 前有唯一支配 store且其他可达写均被 AA 排除
- **THEN** load 结果继承 store value 的候选、guard和完整 proof chain，并保持字段槽与 pointee 两个不同身份

#### Scenario: An unknown call may clobber the field
- **WHEN** load 前的外部调用可能修改该 pointer field且没有受支持摘要或 NoModRef 证据
- **THEN** 相关 load 变为 unknown/partial并记录 clobber frontier，不返回调用前的确定 pointee

### Requirement: Compose parameters, returns and receivers across exact direct calls

跨 TU 组合 SHALL 仅采用显式 scope 内 A1 唯一兼容 function definition、P2 合法 adopted direct-call edge、相容 profile/target/DataLayout、受支持 ABI、实参与形参基数及有界 invocation/context。系统 SHALL 将 caller actual candidate 代入 C/C++ parameter 或 C++ receiver/`this`，并将 callee 的 parameter/global-derived return path 重新绑定给 caller；guard、offset/path、proof 和实例身份 MUST 保留。

#### Scenario: A C wrapper returns a nested field pointer
- **WHEN** C17 wrapper 在另一 TU 有唯一 compatible definition并返回 `&parameter->inner.field`
- **THEN** 调用点结果绑定到实际对象的对应嵌套 path，引用 declaration/definition、adopted edge、形参与返回证据

#### Scenario: A member wrapper receives this across TUs
- **WHEN** C++17 直接成员调用的 receiver、definition、ABI 和对象候选均 exact
- **THEN** callee `this->mutex` 绑定到 caller receiver 实例的 mutex path，不按类型或 mangled name单独推断

#### Scenario: A callee returns local storage
- **WHEN** callee 返回自身 invocation 的 alloca 或其子对象
- **THEN** caller 结果为 expired/unknown并带 lifetime 诊断，不把该地址提升为可用跨调用 ObjectInstance

### Requirement: Preserve evidence modes and candidate-relevant completeness

系统 SHALL 按 TU 记录 AST/IR 证据可用性并区分 AST+IR、IR-only、AST-only 和 failed。AST+IR 只有依赖闭合时可发布 must/may；IR-only MAY 发布局部 LLVM storage/range但缺少语言 path 时相关完整性为 partial；AST-only 只能发布 source candidate；failed 必须保存失败分类。scope 级状态 SHALL 按候选依赖切片传播，无关失败 TU不得阻塞独立候选，候选相关失败不得被零候选掩盖。

#### Scenario: One unrelated TU fails BC generation
- **WHEN** 候选及其跨 TU 闭包不依赖失败 TU且其他所需 AST/IR/调用证据完整
- **THEN** 该候选可继续分析，报告同时保存无关 TU 失败但不将其升级为候选相关 frontier

#### Scenario: Only AST facts are available for a field
- **WHEN** AST 完整提取对象路径但 BC 或 LLVM provenance 阶段失败
- **THEN** 保留 source candidate并返回 partial/unknown，不输出 runtime alias/noalias、exact ObjectInstance或消费者证明

#### Scenario: No candidate is produced because a dependency failed
- **WHEN** candidate slice 的 binding、scope、预算或 worker 失败导致未形成候选
- **THEN** 报告说明零候选不可解释为不存在相关对象，退出码不得为完整成功

### Requirement: Keep object provenance below synchronization and safety proof boundaries

A5 SHALL 只陈述对象来源、候选、子对象范围及绑定关系，不得自行建立 reads-from、sequenced-before、synchronizes-with、happens-before、data-race、risk/discharged 或全程序安全。A4/P4 adapter SHALL 只消费 exact singleton 且依赖闭合的对象身份；may/unknown、AST-only、AA-only 或字段实体相等不得提升既有 proof。消费者类别、严重度、退出码和 `safety=not_established` 语义 MUST 保持不变。

#### Scenario: Two accesses have the same exact mutex instance
- **WHEN** A5 完整证明两个 A4 候选指向同一 exact mutex ObjectInstance
- **THEN** adapter 可提供对象身份证据，但 acquire/release、held-region、线程与同步证明仍必须由 A4/P3 既有规则建立

#### Scenario: AA says NoAlias without cross-TU identity
- **WHEN** 函数内 AA 查询返回 NoAlias但跨 TU storage、scope或调用实例未解析
- **THEN** A5 仅保留局部查询结论，不发布全局 noalias、不同 program object或安全结论

### Requirement: Bound resources, cache dependencies and expose deterministic bilingual reporting

请求 SHALL 对 TU、source/IR node、path/depth、value、candidate、guard、load hop、AA query、MemorySSA walk、capture use、call context、递归轮次、relation、输出和时间设置预算；耗尽时 SHALL 保存 category、hit/limit、已知事实和非空 frontier。缓存键 MUST 包含协议/schema、实现、LLVM/Clang、scope/profile/target/DataLayout、全部依赖、模型/adapter 和预算 identity；cold/warm semantic digest MUST 一致，陈旧、损坏、failed 或 timeout entry 不得成为成功命中。

A5 CLI SHALL 接受显式 request、artifact store 和 output，确定排序输出 graph/report；`0` 表示请求完整，`2` 表示 partial/unknown/frontier，`1` 表示无效或全部不可用，A5 MUST NOT 使用风险退出码 `3`。面向用户的 detail、limitation、suggestion SHALL 同时提供中文和英文，机器 code/identity 不依赖翻译。

#### Scenario: A MemorySSA walk exhausts its budget
- **WHEN** 某 pointer-field load 的 clobber walk 达到显式 limit
- **THEN** 报告记录 hit/limit和中英文建议，相关 slice 为 partial/unknown，其他无关候选仍可继续

#### Scenario: A cache dependency changes
- **WHEN** cache 结构有效但任一 source/IR/profile/model dependency digest 已变化
- **THEN** 系统拒绝该命中并重新分析或返回明确失败，不复用旧 object candidate或消费者绑定
