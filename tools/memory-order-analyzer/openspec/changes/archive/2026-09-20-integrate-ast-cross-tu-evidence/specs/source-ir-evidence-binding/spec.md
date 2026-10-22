## ADDED Requirements

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
