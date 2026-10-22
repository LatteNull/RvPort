# source-ir-evidence-binding

## Purpose

定义源实体、源码表达式与 LLVM 事实之间可审计、带基数和证据等级的绑定，确保依赖、预算、缓存和内存模型证明边界得到严格保持。

## Requirements

### Requirement: Bind source entities to LLVM values with explicit evidence levels

系统 SHALL 生成严格 `SourceIRBinding v1`，通过相同 profile/TU、mangled name、LLVM linkage/visibility/TLS/COMDAT、canonical type/ABI 大小和声明/定义角色，将 source entity 绑定至 P1 function/global facts。每条 binding SHALL 为 exact/candidate/ambiguous/unresolved 之一，并保存支持与反对证据、候选集合和依赖 digest。

#### Scenario: One definition matches one LLVM global

- **WHEN** source definition 与唯一 LLVM global 的 profile、mangling、linkage 和类型证据一致
- **THEN** 产生 exact entity binding，并可由两端 identity 回溯完整证据

#### Scenario: A weak source entity matches multiple globals

- **WHEN** weak/COMDAT 候选无法在缺少 link graph 时唯一选择
- **THEN** binding 为 ambiguous，保留全部候选，不按名称或顺序选择一个

#### Scenario: Several source declarations reach one LLVM definition

- **WHEN** resolved external program entity 包含多个兼容 `extern` declaration 和一个 source definition，且这些节点的 binding 最终指向同一 distinct LLVM global definition
- **THEN** 系统按 target identity 去重并保留每条 source binding 证据；declaration-to-definition 的单条角色差异不得伪造第二个 LLVM 定义或单独否定集合级唯一性

### Requirement: Model expression-to-instruction mappings as cardinality-aware candidates

表达式绑定 SHALL 结合 debug location、spelling/expansion range、inlined-at 链、所属函数、object binding、opcode/atomic ordering 和局部控制上下文，并明确一对一、一对多、多对一或无映射。最近行号、唯一行号或单独 debug 名称 MUST NOT 自动构成 exact。

#### Scenario: One source atomic expression expands to multiple instructions

- **WHEN** 一个源 atomic 构造在 IR 中对应地址计算、atomic load 和比较指令
- **THEN** binding 保存一对多映射及各指令角色，不丢弃辅助指令或伪造单一映射

#### Scenario: Optimized no-debug bitcode has only entity evidence

- **WHEN** function/global 可绑定但相关指令没有可用 debug/source range
- **THEN** 保留实体级 binding，表达式级完整性为 partial/unresolved，不使全部源证据失效

#### Scenario: Several expressions share one source line

- **WHEN** 同一行存在多个 flag/payload 表达式，而 IR debug location 提供 column
- **THEN** binding 仅在 column 落入受限 source range/列窗口且对象、opcode 与上下文一致时保留对应候选；缺少 column 或仍多义时降级为 candidate/ambiguous，不按行号把不同对象合并

### Requirement: Preserve the source-to-IR proof boundary

SourceIRBinding SHALL 只陈述源实体/表达式与 IR 事实的关联，不得自行生成或提升 memory order、sequenced-before、reads-from、synchronizes-with、happens-before 或安全结论。实际访问与 ordering MUST 来自 IR。P4 仅可把独立 `SourceSemanticFacts` 中同一 `CompoundStmt` 相邻 expression statement 的精确 source sequence 投影到两端均已唯一绑定、且属于同一线程上下文的实际 IR memory effect，形成局部 must-before 补充；declaration/control/loop/return 等节点必须断开关系。该补充不得产生 RF/SW/HB 或受限安全结论。

#### Scenario: AST source order suggests publication ordering

- **WHEN** 源码中 payload 赋值书写在 release store 之前，但它们不是同一 `CompoundStmt` 的相邻 expression statement，或任一端缺少唯一 IR effect binding
- **THEN** binding 只记录候选关联并传播 partial，不以行号或文本书写顺序 discharge 风险

### Requirement: Validate binding dependencies and budgets

binding 请求 SHALL 校验 SourceSemanticFacts、ProgramEntityIndex、ModuleFacts/RunReport 和 BC artifact 的版本、profile、scope 与 digest，并限制实体、表达式、候选和工作量预算。悬空/替换依赖必须拒绝；预算耗尽必须输出已完成绑定和未处理 frontier。

#### Scenario: Module facts belong to a different compilation profile

- **WHEN** P1 facts 的 artifact/profile 与 source facts 不一致
- **THEN** 该绑定被拒绝或标为 profile-conflict，不跨配置拼接证据

### Requirement: Bind C++ thread operations and callables with explicit cardinality

SourceIRBinding 的 A3 补充 SHALL 将构造、move、join/detach/joinable/析构表达式、线程对象、callable/receiver/capture 与标准库 wrapper/call/value/object token 建立 exact/candidate/ambiguous/unresolved 绑定，保存一对多/多对一基数、支持与反对证据及 profile/model digest。名称、最近行号、唯一 debug 行或单一 wrapper symbol MUST NOT 自动构成 exact。

#### Scenario: One constructor expands to several wrapper calls
- **WHEN** 一个 `std::thread` 构造在 IR 中包含 allocation、state setup、entry broker 和异常清理调用
- **THEN** binding 保存一对多映射及每个节点角色，不任取一个调用代表全部构造语义

#### Scenario: No-debug IR still has unique entity and ABI evidence
- **WHEN** debug location 缺失，但 caller、线程对象值、callable entity、wrapper 角色和 profile 均能唯一绑定
- **THEN** 可以形成相应 entity/object/call binding；若 callsite 基数仍不唯一则保持 candidate，不因无 debug 强行 exact

### Requirement: Keep C++ source binding below the lifecycle proof boundary

A3 binding SHALL 只关联源构造与 IR/ABI 事实，不得自行声明构造成功、动态线程创建、join 成功、MHP、SW、HB、risk 或安全。生命周期关系必须由 A3 状态机、执行顺序和成功/异常路径规则单独推导。

#### Scenario: Source order places join after construction
- **WHEN** AST 中 join 语句书写在构造之后但 IR 成功路径或对象 lineage 不完整
- **THEN** binding 仅保留表达式关系和缺口，不生成 start 或 join-complete

### Requirement: Bind RAII source operations to actual IR synchronization effects

SourceIRBinding SHALL 为每个 mutex/owner 构造、析构、move、lock/unlock 和 cleanup 候选记录 AST entity、IR call/invoke、参数/返回、对象 path、CFG/异常边、profile summary 及绑定基数。只有唯一或显式允许的有限绑定、同 profile/ABI 和完整引用闭包才可进入 A4 证明；名称、debug location 或类型相似 MUST NOT 单独采用。

#### Scenario: One destructor maps to normal and cleanup IR calls
- **WHEN** AST 析构在正常出口和异常 cleanup 各对应一个实际 unlock 调用
- **THEN** binding 分别保存带 guard 的 IR effect，并允许状态机检查所有出口是否闭合

#### Scenario: An IR lock call has no unique source owner
- **WHEN** 底层 wrapper 可绑定多个 guard/owner 且无法按对象和路径区分
- **THEN** 保留 binding 候选和歧义原因，不生成唯一 owner acquire

### Requirement: Reject AST-only synchronization completion

AST-only 模式 MAY 保存 mutex、owner、词法 lifetime 和调用形状作为 source candidate，但 MUST NOT 建立成功 acquire/release、held-region、mutex proof、SW、HB、risk 或 discharged。

#### Scenario: BC generation fails after successful AST extraction
- **WHEN** AST 完整识别 `lock_guard`，但该 TU 的 IR 生成或 A4 worker 失败
- **THEN** 输出 source candidate 和缺失 IR/profile 证据，结果为 partial/unknown
