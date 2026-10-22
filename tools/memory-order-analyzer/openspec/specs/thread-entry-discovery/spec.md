# thread-entry-discovery

## Purpose

定义面向 GCC/Clang C11、C17、C++17 与 C++20 的版本化线程入口发现能力，以 Clang AST 语义类型和 LLVM BC 运行时 broker 双重证据保守识别线程创建点，并为 ExecutionRoot 驱动分析提供不改写既有协议的入口覆盖层。

## Requirements

### Requirement: Publish an independent versioned thread-entry discovery protocol
系统 SHALL 定义严格版本化的 `ThreadEntryDiscoveryRequest v1`、`ThreadEntryLocalFacts v1`、`ThreadEntrySiteIndex v1`、`ThreadEntryRootOverlay v1` 和 `ThreadEntryDiscoveryReport v1`，通过 kind、identity 与 canonical digest 显式引用 scope、编译 profile、P1/A1/SourceIRBinding、适用的 P3/A3/A5、R1 base artifact 及入口模型。新产物 MUST 使用独立 schema、artifact 和缓存命名空间，不得修改或重解释 P1–P4、A1–A5、A3 或 R1 v1 的事实、关系、finding、discharged、退出码和安全语义。

#### Scenario: Existing analysis runs without thread-entry discovery
- **WHEN** 调用方只执行现有 P1–P4、A1–A5、A3 或 R1 命令且没有新的 request/overlay
- **THEN** 现有输出、缓存、root、风险结果和 unknown 语义保持不变，缺少新产物不得解释为不存在额外线程入口

#### Scenario: A dependency digest was replaced
- **WHEN** request 引用的 scope、profile、SourceIRBinding、P3/A3/A5、R1 或模型 digest 与提供 artifact 不一致
- **THEN** 系统拒绝组合并输出稳定的中英文依赖错误，不扫描目录寻找替代产物

### Requirement: Preserve resolved semantic type and constructor evidence
Clang source worker SHALL 为入口相关 C++ 表达式保存 source spelled type、canonical semantic type、canonical record/entity、实际选中的 canonical constructor declaration、constructor specialization/kind、typedef/using/inline-namespace alias chain、声明来源、system boundary、宏位置和编译/标准库 profile。标准线程类型资格 MUST 由已验证 profile 登记的 canonical entity、声明来源与 ABI 指纹共同确定；qualified name、源码拼写、类型 basename 或单一 mangled symbol MUST NOT 单独构成线程类型证明。

#### Scenario: A type alias constructs std::thread
- **WHEN** `using Worker = std::thread` 后通过 `Worker t(callback)` 选择已验证 profile 中的 callable constructor
- **THEN** source facts 同时保存 `Worker` spelling、展开后的 canonical `std::thread` identity、constructor 和 alias chain，并生成一个 source create candidate

#### Scenario: A user type is also named thread
- **WHEN** 用户类型 `foo::thread` 具有相似 constructor 和 `join` 方法但 canonical entity、声明来源及 profile 均不属于已登记标准库类型
- **THEN** 系统不得把它采用为 `std::thread`，并记录 unsupported 或非线程类型证据

#### Scenario: Expression facts remain auditable downstream
- **WHEN** 下游读取一个 C++ construction local fact
- **THEN** 事实包含实际 canonical type、record、constructor 与 profile 引用，不以通用 `expression` 占位符替代这些入口判定字段

### Requirement: Distinguish object operations from actual thread creation
系统 SHALL 区分 `default`、`callable-construction`、`move-construction`、`copy-or-deleted`、`factory-return` 和 `other/unknown` 操作。只有受支持的 callable constructor 或 C API create call可以成为创建候选；默认构造、move、仅具有线程返回类型的调用和对象引用 MUST NOT 在当前调用点创建新的线程入口。`new`、copy-init、`auto` 变量和 materialized temporary MUST 绑定其内部实际 constructor site，不因外层 AST 节点重复生成 site。

#### Scenario: Default construction creates no thread
- **WHEN** 源码执行 `std::thread t;` 且 AST/BC 均证明只发生默认构造
- **THEN** site 可记录为 `does-not-create-thread`/`excluded`，不得生成 callback root 或 ThreadInstance

#### Scenario: Move construction transfers an existing object
- **WHEN** `std::thread t2(std::move(t1))` 选择 move constructor
- **THEN** 事实记录对象转移候选但不得把 move site 当作新线程创建，A3 原有生命周期语义不变

#### Scenario: A factory returns a thread object
- **WHEN** 调用表达式返回 canonical `std::thread` 但当前 callsite 没有可证明的 callable constructor/broker
- **THEN** 当前 callsite 不生成创建点；若被调函数内部存在真实构造，只在其内部物理 site 单独发现

#### Scenario: New and temporary share one physical constructor identity
- **WHEN** `new std::thread(callback)` 或临时 `std::thread(callback).detach()` 同时被外层和内层 AST visitor 命中
- **THEN** 索引按 canonical physical callsite 去重为一个创建点并保留全部 AST anchors

### Requirement: Discover source and IR candidates independently and align conservatively
系统 SHALL 从可信 AST/source facts 与 parse/verify 成功的 BC/LLVM facts独立发现候选，以并集建立分母，再按 physical TU/profile、SourceIRBinding、source/IR call identity、canonical callable、linkage、ABI/target/DataLayout、model、broker role、参数与 guard 对齐。每个 site MUST 分别保存 `evidence_status`、`execution_semantics` 与 `root_disposition`；一侧缺失不得删除另一侧候选，行号相同、名称相似或底层出现 `pthread_create` 不得单独对齐 C++ site。

#### Scenario: Source and IR agree on one creation site
- **WHEN** AST callable constructor/C create call、唯一 callback、SourceIRBinding 和相容 BC broker 指向同一 physical site 且 profile/ABI 匹配
- **THEN** 索引生成一个 `dual-exact` site，保存双方证据并按该 API 的执行语义决定是否 adopted

#### Scenario: AST and IR callbacks disagree
- **WHEN** source candidate 唯一指向 callback A，而同一 site 的 IR callback 唯一指向不兼容的 callback B
- **THEN** site 为 `ambiguous`/`frontier` 并保存 opposed evidence，不任选其中一个 root

#### Scenario: Only source evidence survives optimization or IR failure
- **WHEN** AST 保存有效构造或 create call，但对应 BC、binding 或 broker 无法唯一恢复
- **THEN** site 保持 `source-candidate` 和非空 IR frontier，不解释为没有线程且不创建正式实例

#### Scenario: One physical site has duplicate source observations
- **WHEN** declaration、constructor、new/temporary 或宏 expansion 为同一 physical callsite 生成多条观察
- **THEN** 索引去重为一个 site并保留 observation 列表，不重复增加 truth actual 或动态实例

### Requirement: Model C pthread and C11 thread entry APIs independently from C++
系统 SHALL 在 GCC/Clang C11 与 C17 profile 下支持直接或已采用受限 wrapper 的 `pthread_create` 和 `thrd_create`，保存 C linkage、目标 ABI、handle/result、callback SSA、参数角色和成功 guard。`thrd_create` SHALL 使用 `<threads.h>` 的 `thrd_t` 与 `int (*)(void *)` 语义；C 路径 MUST NOT 依赖 C++ AST、libstdc++/libc++ 或 A3 profile。无 AST/no-debug BC 只有在直接性、ABI、scope、callback 与参数角色均唯一时才可成为 `ir-exact`。

#### Scenario: A valid C11 thrd_create call is complete
- **WHEN** 真正 `.c` fixture 在 C11 profile 下包含 ABI 相容的 `thrd_create`，AST 与 BC callback、argument、result 和成功条件唯一对齐
- **THEN** 系统发布一个 `creates-thread`、`adopted` 的精确入口并保留 C linkage 证据

#### Scenario: C analysis has no C++ profile
- **WHEN** C17 scope 仅包含 `pthread_create`/`thrd_create` 且没有标准 C++ 库 profile
- **THEN** C 入口发现可完整执行，不要求或伪造任何 C++ 类型、constructor 或库证据

#### Scenario: No-debug direct C ABI is exact
- **WHEN** AST 不可用但 verified no-debug BC 中直接 C create ABI、target、scope 和唯一 callback SSA 均完整
- **THEN** site 可按受限规则成为 `ir-exact`，同时明确 source evidence unavailable

### Requirement: Discover verified std::thread and std::jthread entries without changing lifecycle models
系统 SHALL 在 GCC/Clang C++17/C++20 与完全匹配的已验证 libstdc++/libc++ model profile 下发现 `std::thread`，并在 C++20 profile 下发现 `std::jthread`。精确采用 MUST 同时具有 canonical AST type/constructor/callable、SourceIRBinding、相容 ABI broker、callback/argument mapping 与成功 guard；IR-only wrapper 名、底层 pthread 调用或源码类型本身不得采用。`std::jthread` SHALL 区分普通 invocable 与 profile 允许的隐式 `stop_token` 注入形式，歧义时不得任选。新入口事实和 overlay MUST NOT 修改 A3 的对象状态机、join/detach/析构关系或引入 jthread stop/join 生命周期证明。

#### Scenario: Existing std::thread forms remain exact
- **WHEN** 自由函数、非限定名/类型别名、copy-init、`auto`、`new`、临时对象、lambda、受限非虚成员函数或唯一简单 functor 满足现有 A3 与新增 site 证据规则
- **THEN** 系统生成一个去重的精确创建点，并可引用 A3 context/instance而不复制或改变 A3 关系

#### Scenario: A jthread callable uniquely receives stop_token
- **WHEN** C++20 AST 与验证 profile 唯一证明 `std::jthread` 选择 stop-token-injected invocable，BC broker 与参数映射一致
- **THEN** site 记录注入参数和 callback 并可 adopted 为入口，但报告明确未建模 stop 请求和析构 join 生命周期

#### Scenario: Standard-library profile mismatches
- **WHEN** canonical type 看似标准线程类型，但 vendor、version、ABI、target、header/broker digest 或 model profile 不匹配
- **THEN** site 为 `unsupported` 或 `ambiguous` 并进入 frontier，不按类型名或 mangled symbol创建 root

### Requirement: Preserve std::async launch-policy semantics
系统 SHALL 在 C++17/C++20 已验证标准库 profile 下恢复 `std::async` 的 canonical function/overload、callable、实参和 launch-policy 值流，并分别表达 `launch::async`、`launch::deferred`、同时允许两者的默认/组合 policy 以及 unknown policy。精确 `launch::async` 只有在 AST/BC broker 和 callback 完整时才能 adopted；精确 `launch::deferred` MUST 不生成并发 root；默认或同时允许两者 MUST 为 `may-create-thread` 与 `conditional-frontier`，不得作为确定 MHP、HB 或风险证明。

#### Scenario: Explicit async policy starts an eligible entry
- **WHEN** policy 被证明仅为 `std::launch::async`，且 callable、broker、profile、binding 与 guard 完整
- **THEN** site 为精确 `creates-thread` 并进入 root overlay，同时不生成 future wait/get 生命周期关系

#### Scenario: Explicit deferred policy creates no concurrent root
- **WHEN** policy 被证明仅为 `std::launch::deferred`
- **THEN** site 保存精确非并发语义并标记 `excluded`，不得生成线程 root

#### Scenario: Default async policy remains conditional
- **WHEN** 调用省略 policy 或 policy 同时允许 async 与 deferred
- **THEN** site 保存 `may-create-thread`、`conditional-frontier` 和实现选择限制，不提升为确定并发实例

#### Scenario: Launch policy propagation exceeds the budget
- **WHEN** policy 经未知调用、非受限位运算或候选集合超限而无法唯一分类
- **THEN** site 为 unknown/frontier并保留已知 policy candidates，不按默认 async 处理

### Requirement: Reject name-only custom frameworks and excluded platforms
系统 MUST NOT 仅凭 `thread` 类型 basename、`submit`/`enqueue`/`post` 方法名、receiver 名称、相似 wrapper 或底层 pthread 符号采用 Boost、线程池、executor、Linux `clone` 或自定义调度入口。自定义 API 只有在显式版本化 descriptor 绑定 canonical API/receiver entity、callback/argument role、异步保证、cardinality、library/version/ABI/target 和 broker digest 后才有资格进入后续采用；首版内置 adoption 不包含这些框架。Windows API、MSVC 与 clang-cl MUST 明确报告 excluded/unsupported。

#### Scenario: Ordinary submit method is not asynchronous
- **WHEN** 普通 `Form.submit` 与线程池方法同名但没有显式 framework descriptor
- **THEN** 系统不得生成线程入口，并保存名称不足以证明调度语义的诊断

#### Scenario: Boost thread has a familiar basename
- **WHEN** AST canonical entity 是 `boost::thread` 而名称 basename 为 `thread`
- **THEN** 系统不得套用 `std::thread` profile，未提供独立 descriptor 时保持 unsupported

#### Scenario: A Windows sample is present
- **WHEN** fixture 使用 `CreateThread`、`_beginthread`、`_beginthreadex` 或 MFC API
- **THEN** 语料清单记录平台排除且不进入支持 truth 分母，报告不得把排除解释为分析成功

### Requirement: Publish a non-mutating root overlay with candidate-related completeness
`ThreadEntryRootOverlay` SHALL 显式引用 R1 `ExecutionRootIndex v1` 和 `RootDrivenAnalysisPlan v1`，保存新增 adopted root、父创建点、canonical callable context、对象/handle lineage、guard、cardinality、可达 demand 及与 base root 的去重/冲突证据，但 MUST NOT 改写 base artifact。只有 `creates-thread` 且 root disposition 为 `adopted` 的 site可生成正式 overlay root；source/IR candidate、conditional、ambiguous、unsupported 和 failed site MUST 进入 root coverage、候选相关依赖切片和非空 frontier。相同 callable 的不同物理 site不得合并，循环或递归创建 MUST 使用 repeated/merged cardinality。

#### Scenario: Overlay and R1 already contain the same pthread site
- **WHEN** 新索引规范化的 pthread site 与 R1 base root 具有相同 physical callsite、model 和 callback identity
- **THEN** overlay 记录 adopted-from/base 引用且不重复新增 root或动态实例

#### Scenario: One callable appears at two construction sites
- **WHEN** 两个精确 site 启动相同 callback
- **THEN** overlay 可复用 callable context但保留两个 root origin、guard 和实例来源

#### Scenario: A related conditional site exists
- **WHEN** reachable slice 中存在默认 policy `std::async` 或其他 conditional frontier
- **THEN** root/reachable completeness 为 partial，报告不得因没有正式 overlay root而声称没有并发入口

#### Scenario: An unrelated translation unit fails
- **WHEN** 失败 TU 被证明显式不属于某个 site/root 的候选依赖切片
- **THEN** 该 slice 可保持 complete，同时顶层报告保留 scope failure及其无关证据

### Requirement: Bound, cache and report discovery deterministically
请求 SHALL 限制 scope members、TU、source/IR facts、type/alias depth、site/binding/callback/profile 候选、wrapper depth、root/context、递归/SCC、frontier、诊断、输出字节、worker/request 时间和 wall-clock。预算耗尽 MUST 保留已知事实、hit/limit 与非空 frontier。缓存键 MUST 包含 schema/producer/policy、Clang/LLVM、scope/profile、source/BC 与所有依赖 digest、标准库/API model、framework descriptor、预算类别和 root 配置；损坏、陈旧、failed、timeout 或 wall-clock partial 条目不得作为成功命中，cold/warm semantic digest MUST 一致。

`discover-thread-entries` CLI SHALL 只读取显式 request/artifact store/worker，要求全新输出目录且不得执行配置、构建、链接、目标程序、网络或 SSH。退出码 `0` 表示请求范围内发现和 overlay complete，`2` 表示 partial/unknown/unsupported/frontier，`1` 表示无效或全部 failed，且 MUST NOT 返回风险码 `3`。报告 SHALL 固定 `safety=not_evaluated`、`findings=null`，并为 detail、limitation 和 suggestion 提供中英文字段。

#### Scenario: Site budget is exhausted
- **WHEN** 候选数量达到 site limit且仍有未处理候选
- **THEN** 系统发布已知 site、准确 hit/limit 和 budget frontier，状态与退出码为 partial/`2`

#### Scenario: A warm cache entry is valid
- **WHEN** 全部 schema、工具链、scope/profile、依赖、模型、descriptor、root 配置和预算 identity 完全匹配
- **THEN** warm 结果与 cold 结果的 semantic digest、site 分类和 overlay 语义一致，并报告 cache hit

#### Scenario: No creation site is found
- **WHEN** 索引的正式和候选创建点均为零
- **THEN** 报告分别列出已完整扫描的分母和失败/未运行分母，且不输出“没有线程”“没有风险”或“程序安全”结论

#### Scenario: Output directory already exists
- **WHEN** CLI 指向已存在的输出目录
- **THEN** 命令拒绝覆盖并返回结构化失败及中英文修复建议

### Requirement: Validate four language profiles and all owned code at ninety percent coverage
项目 SHALL 在本项目内维护离线、可编译、人工真值的 C11、C17、C++17、C++20 fixture 和 provenance manifest，不得在测试运行时读取 `memory-model-ir-checker` 或其他兄弟目录。归档样例在最小化复制时 MUST 记录原相对路径、内容摘要和改写原因；语法/类型无效或语言错误的旧样例只有修复并人工复核后才能进入 truth。四种语言 SHALL 分别报告 planned、completed、failed、expected/actual site、exact match、TP、FP、FN、abstention 和 frontier，不得合并分母掩盖单一语言缺口。

全部新增、修改或复用的项目自有可执行代码 MUST 具有正常、边界、异常和 unknown 路径单元测试；项目整体、实现语言及每个受影响模块的行覆盖率和工具支持的分支覆盖率 MUST 均至少为 90%，且统计 MUST 包含未被测试加载的项目源码。集成 truth、编译成功和静态检查不得替代单元测试或覆盖率门禁。

#### Scenario: C and C++ truth matrices are complete
- **WHEN** required gate 执行入口语义验证
- **THEN** C11/C17 分别覆盖 pthread、`thrd_create`、C linkage、跨 TU 与 no-debug，C++17/C++20 分别覆盖支持的 `std::thread`/`std::async`，C++20 额外覆盖 `std::jthread`，并单列各自分母和结果

#### Scenario: Negative and frontier fixtures run
- **WHEN** truth 包含 `foo::thread`、`boost::thread`、默认/move/factory-return、`Form.submit`、callback 冲突、重复观察、开放 scope、profile 失配和预算耗尽
- **THEN** 每个 fixture 的 excluded、unsupported、ambiguous 或 unknown/frontier 结果与人工 truth 精确匹配，不以 abstention 伪装 complete

#### Scenario: Coverage is below the gate
- **WHEN** 项目整体、Python/C++ 实现语言或任一受影响模块的行/分支覆盖率低于 90%，或者存在未纳入统计的自有源码
- **THEN** 质量任务保持未完成且 change 不得进入可归档状态

### Requirement: Document operation, evidence boundaries and roadmap status
实现 SHALL 更新 README、架构说明、`doc/THREAD_ENTRY_DISCOVERY.md`、`doc/THREAD_ENTRY_DISCOVERY_VALIDATION.md` 和 `doc/IMPLEMENTATION_ROADMAP.md`，分别说明 CLI/产物、AST semantic type 与 BC broker 的证据分工、支持矩阵、分类/完整性/退出码、归档样例 provenance、四语言 truth 与覆盖率结果，以及后续生命周期、R2 并发访问候选图和框架 profile 的边界。文档 MUST 明确成功编译、精确入口或零 findings 均不是并发安全证明。

#### Scenario: Documentation is reviewed at the required gate
- **WHEN** 实现、truth 和覆盖率验证完成
- **THEN** 文档中的协议版本、命令、支持范围、实测分母、状态和限制与生成 artifact 一致，且不存在把入口发现描述为 MHP、HB、风险或全程序安全证明的表述
