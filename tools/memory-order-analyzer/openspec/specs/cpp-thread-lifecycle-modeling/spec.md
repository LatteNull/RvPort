# cpp-thread-lifecycle-modeling

## Purpose

定义独立、版本化且证据驱动的 C++ `std::thread` 生命周期、callable 解析、对象状态机、实例身份、顺序关系与预算边界。

## Requirements

### Requirement: Define independent versioned C++ thread lifecycle contracts

系统 SHALL 定义严格、版本化的 `CppThreadLifecycleRequest v1`、`CppThreadLocalFacts v1`、`CppThreadLifecycleGraph v1` 和 `CppThreadLifecycleReport v1`，包含 schema/producer/policy、显式 scope/root、编译与标准库 profile、依赖 digest、预算、完整性和 canonical identity。A3 产物 SHALL 只引用而不修改 P1 `ModuleFacts v2`、P2 `EffectSummary v1`、P3 `ThreadContextGraph v1`、P4 报告、A1 source-evidence 与 A2 degraded-source 产物；未来版本、未知字段、悬空/替换依赖或混合 profile MUST 被拒绝。

#### Scenario: A lifecycle request references one replaced source binding
- **WHEN** 请求记录的 SourceIRBinding digest 与提供产物不一致
- **THEN** A3 拒绝组合并输出稳定中英文依赖错误，不把新旧证据拼成线程实例

#### Scenario: Existing analysis runs without A3
- **WHEN** 调用方只执行既有 P1–P4、A1 或 A2 请求且没有 A3 sidecar
- **THEN** 既有 schema、缓存、报告和退出语义保持兼容，缺少 A3 不得解释为不存在 C++ 线程

### Requirement: Resolve supported C++ callables through source and ABI evidence

系统 SHALL 仅在 AST canonical callable、跨 TU program entity、SourceIRBinding 和已采用标准库 ABI broker 证据兼容时解析 `std::thread` callback。首版 SHALL 支持唯一自由函数、受限 lambda、成员函数和具有唯一非虚 `operator()` 的简单 functor，并保存 callable、对象、capture/参数、wrapper、调用点和候选基数；名称、类型拼写、单一 mangled symbol 或底层 `pthread_create` MUST NOT 单独构成采用证明。

#### Scenario: A cross-TU free function has complete evidence
- **WHEN** 构造点 AST 指向 scope 内唯一自由函数 definition，IR broker 与实参绑定精确且标准库 profile 匹配
- **THEN** 生成 callback/context 候选并保留源实体、definition、binding、wrapper 和参数证据

#### Scenario: A member object has several provenance candidates
- **WHEN** 成员函数实体唯一但对象经 phi、逃逸或未知调用形成多个无法排除的候选
- **THEN** 保留有限 may-target 或 unknown frontier，不任选对象且不生成 must thread instance

#### Scenario: A callback is inferred only from a wrapper name
- **WHEN** IR 仅包含形似已知 broker 的符号而缺少兼容 AST callable 或 profile 证据
- **THEN** 不采用 C++ 线程模型并报告证据缺口

### Requirement: Track thread object ownership with a guarded state machine

系统 SHALL 为每个规范化线程对象和 native handle lineage 表达 `empty`、`construction-pending`、`joinable`、`joined`、`detached`、`moved-from`、`failed`、`terminated-path` 或 `unknown` 状态；构造、move construction/assignment、`join`、`detach`、`joinable` 和析构转移 SHALL 引用 AST/IR anchor、成功/异常 guard、对象候选和前态。覆盖、逃逸、目标仍 joinable、self move 或候选超限 MUST 保守合并，不能伪造唯一所有权。

#### Scenario: Move construction transfers one known thread
- **WHEN** 源对象唯一处于 joinable，目标为空且 move 的源/目标 IR 操作与 AST 绑定完整
- **THEN** 目标继承同一 handle/ThreadInstance lineage，源变为 moved-from，并保存条件化转移证据

#### Scenario: Move assignment overwrites a possibly joinable target
- **WHEN** 目标前态可能 joinable 或异常/terminate 路径无法证明排除
- **THEN** 路径标为 terminated-path/unknown，不把源实例无条件转移到目标或继续生成 join 证明

#### Scenario: Joinable is queried
- **WHEN** `joinable()` 返回值控制后续路径
- **THEN** 记录状态查询及 guard 候选，但查询本身不产生 join-complete、synchronizes-with 或 happens-before

### Requirement: Keep thread contexts and dynamic instances separate

系统 SHALL 以 callback、抽象参数、scope/profile 和模型策略建立可复用 C++ `ThreadContext`，并以 root、父实例、构造调用实例、对象/handle lineage、guard 和 cardinality 建立 `ThreadInstance`。相同 callable 在不同构造点、循环或递归中 MUST 保留不同或明确 merged/repeated 的实例语义，缓存上下文不得复用调用者特有实例。

#### Scenario: One lambda is used at two construction sites
- **WHEN** 同一 lambda call operator 和相同抽象 capture 在两个 `std::thread` 构造点启动
- **THEN** 可以复用 ThreadContext，但生成两个带各自构造点、父实例、对象和生命周期的 ThreadInstance

#### Scenario: Construction occurs in an unbounded loop
- **WHEN** 构造点可重复执行且无法有界枚举动态线程
- **THEN** 输出 repeated/merged 实例桶、自并行可能和未展开前沿，不把它当作一个具体线程

### Requirement: Derive conditional start join and detach lifecycle relations

系统 SHALL 仅在构造成功、callback/对象/handle provenance 和执行顺序证据完整时生成 thread-start；仅在目标唯一或资格明确的有限候选、worker exit、`join` 成功及父线程后继均可证明时生成条件化 join-complete 关系。`detach` SHALL 终止 join 所有权但保持潜在并行；失败/异常 `join`/`detach`、析构、`joinable()`、源码顺序或 P2 order MUST NOT 生成完成、SW 或 HB。

#### Scenario: A unique worker is joined successfully
- **WHEN** 构造成功创建一个已绑定实例，join 对象仍持有该 handle，join 正常成功且父线程后继顺序可证明
- **THEN** 生成 worker-exit 到 join-complete 再到父线程后继的条件关系，并登记全部 guard 与证据

#### Scenario: A thread is detached
- **WHEN** 唯一 joinable 对象在可证明成功路径调用 `detach`
- **THEN** 对象转为 detached，实例仍可能与父线程后续并行，不产生 join-complete 或 happens-before

#### Scenario: A joinable object is destroyed
- **WHEN** 析构发生时对象可能仍 joinable
- **THEN** 记录可能 terminate 的路径和完整性缺口，不把析构当作隐式 join 或 detach

### Requirement: Bound lifecycle analysis and expose deterministic CLI semantics

系统 SHALL 提供 `model-cpp-thread-lifecycle --request --artifact-store --output --source-worker --ir-worker`，要求新建空输出目录并禁止扫描最新产物、扩大 scope、执行构建或运行目标。分析 SHALL 限制 TU、实体、callable、对象、候选、实例、状态转移、递归轮次、输出和墙钟预算；预算耗尽必须保存已知事实与非空 frontier。完整合法结果退出 `0`，partial/unknown/unsupported 退出 `2`，无有效请求或所有计划项 failed 退出 `1`；报告 SHALL 保持 `safety=not_evaluated`、`findings=null`。

#### Scenario: Instance budget is exhausted
- **WHEN** 已发现部分线程实例后达到实例或状态转移预算
- **THEN** 发布可验证 partial 图、准确 hit/total 和 frontier 并退出 2，不用空图或已完成冒充 complete

#### Scenario: A warm run reuses valid artifacts
- **WHEN** 协议、依赖、profile/model、预算类别和工具链完全相同且缓存未损坏
- **THEN** cold/warm semantic digest 与关系语义一致，报告 cache hit/miss；瞬态 timeout/crash 不作为长期语义命中

### Requirement: Compose A4 synchronization without changing A3 lifecycle semantics

A4 SHALL 只通过稳定引用消费 A3 `ThreadContext`、`ThreadInstance`、start/join/detach 和对象 lineage，不得修改 A3 graph、状态机、cache identity 或报告含义。mutex owner identity MUST 与线程对象 identity 分离；join/detach 或线程析构不得单独产生 mutex acquire/release。

#### Scenario: A joined thread contains a lock guard
- **WHEN** A3 已证明线程实例和 join-complete，A4 又在 worker 内识别完整 guard 临界区
- **THEN** 两组关系按显式引用组合但各自保留来源，join 不能替代 mutex 证明，mutex 也不能改写 join

#### Scenario: A detached thread has an RAII guard
- **WHEN** A3 只证明 detach，A4 识别线程内 guard
- **THEN** A4 可保留局部临界区候选，但 detach 不生成 join/HB 或扩大 guard lifetime
