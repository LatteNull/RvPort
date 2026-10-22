## ADDED Requirements

### Requirement: Version A6 artifacts independently and preserve existing semantics
系统 SHALL 定义版本化的 `FenceRmwPublicationRequest`、`AtomicSourceConstructFacts`、`AdvancedAtomicFunctionFacts`、`AdvancedAtomicLocalFacts`、`BoundedAtomicCommunicationGraph`、`AdvancedPublicationProtocolOverlay` 和双语 `FenceRmwPublicationReport`。A6 MUST 通过独立 sidecar、稳定引用和只读 overlay 接入，MUST NOT 修改或伪装成 P1–P4、A1–A5、R1/R1.1、R2 或 R3 产物，也 MUST NOT 改变其 schema、semantic digest、缓存身份、finding、discharged、unknown 或报告语义。

#### Scenario: A P4 unsupported protocol is analyzed by A6
- **WHEN** P4 protocol 因相关 fence、RMW 或 CAS 保持 unsupported，且 A6 获得完整证据
- **THEN** A6 overlay 引用原 P4 protocol 并独立记录 A6 assessment，原 P4 artifact 和 assessment 保持逐字节及语义不变

#### Scenario: A6 is not requested
- **WHEN** 用户运行任一既有 eager、P2、P3、P4、R1、R2 或 R3 命令而未选择 A6
- **THEN** 既有行为、协议、缓存和退出码不依赖 A6 artifact 且与 change 前一致

### Requirement: Extract canonical atomic source constructs for C and C++
系统 SHALL 为 GCC/Clang 的 C11/C17 `<stdatomic.h>` 与 C++17/C++20 `<atomic>` 分别提取独立源码事实。分类 MUST 基于 Clang canonical semantic declaration、实际 selected operation/method/overload、canonical type、object/value/order 参数、声明来源和 profile；C++ 还 MUST 绑定经验证的标准库、版本和 ABI。系统 SHALL 同时保存 spelled form 供诊断，但 MUST NOT 仅凭函数名、类型名、文本包含 `atomic`、宏拼写或 mangled symbol 判定原子构造。

#### Scenario: C macro lowers to an AtomicExpr
- **WHEN** C11/C17 fixture 使用 `<stdatomic.h>` 宏且 Clang 将其解析为带精确 operation、object 和 order 参数的 `AtomicExpr`
- **THEN** source facts 使用 C profile 保存 canonical operation 与参数，并且不加载 C++ AST 或标准库模型

#### Scenario: A user type is named atomic
- **WHEN** C++ 程序声明同名 `atomic` 类型或方法但 selected declaration 不属于已验证的 `std::atomic` profile
- **THEN** 系统不得采用为精确高级原子构造，并输出可追溯 candidate/unsupported 诊断

#### Scenario: Source facts have no runtime binding
- **WHEN** TU 只有 AST 事实或 SourceIRBinding 无法唯一对齐实际原子 IR 事件
- **THEN** 系统仅保留 source candidate 和 partial/unknown，不建立 RF、MO、SW、HB、risk 或 discharged

### Requirement: Preserve outcome-aware LLVM atomic events
`AdvancedAtomicLocalFacts` SHALL 按 artifact、function、context 和 `ThreadInstance` 保存实际 `fence`、`atomicrmw` 与 `cmpxchg` 事件。每个事件 MUST 包含稳定 IR identity、source binding、kind、精确对象/range/address space、ordering、failure ordering、syncscope、RMW operation、CAS compare/desired/observed value、weak、guard、multiplicity、依赖和完整性；不存在的字段 SHALL 显式为空而不得用默认值制造证据。

#### Scenario: Compare exchange has success and failure paths
- **WHEN** LLVM `cmpxchg` 的 success 和 failure ordering 不同且其 success flag 控制后续分支
- **THEN** 系统生成互斥的 success 与 failure outcome；success 表示 read 加 modification，failure 表示 read-only，并保留各自 ordering、guard 和控制证据

#### Scenario: Weak CAS can fail spuriously
- **WHEN** `cmpxchg weak` 的 observed value 相等但 spurious failure 仍可能发生
- **THEN** failure outcome 保持可行；若相关重试或消费者控制不能闭合，则产生 candidate-relevant unknown 而非假定成功

#### Scenario: RMW participates in communication
- **WHEN** `atomicrmw` 的对象、operation、输入和 observed old value 均可精确表示
- **THEN** 事件同时作为 atomic read 和 MO modification，且其 RF 来源必须由后续求解约束为 MO 直接前驱

### Requirement: Normalize eager and demand-driven atomic facts without changing their protocols
系统 SHALL 从 P1 eager 事实或 R3 demanded function/context 生成相同规范化的 A6 atomic event identity 和语义。R3 handoff MUST 只调度 root/candidate 相关 function/context，MUST NOT 回退为 all-defined 或全 BC 原子扫描；A6 function shard 不得序列化为部分 `ModuleFacts` 或既有 R3 shard。

#### Scenario: The same function is processed eagerly and lazily
- **WHEN** 同一 BC digest、profile、function/context 分别通过 eager 和 R3 A6 路径提取
- **THEN** 规范化 event、outcome、guard、对象和值引用及 semantic digest 等价，只允许 operational 字段不同

#### Scenario: O0 dispatcher and O2 direct lowering represent one source operation
- **WHEN** 同一受支持 C++ atomic API 在 `-O0` 形成多个 guarded ordering 变体而在 `-O2` 形成直接原子指令
- **THEN** profile、selected overload、SourceIRBinding、guard 和可达 outcome 闭合时两者得到相同源码级原子语义，且 `-O0` 指令数不得被解释为多次动态调用

### Requirement: Reuse roots and candidates only as demand evidence
A6 SHALL 使用 `RootDrivenAnalysisPlan`、`ThreadEntryRootOverlay`、R2 atomic handoff 和 R3 `AnalysisDemandGraph` 建立需求切片，并 SHALL 组合 P3 `ThreadInstance`/MHP、A5 object provenance 与 P4 flag/payload/gate。P2 `EffectSummary.order`、P3 reads-from candidate、R2 candidate/handoff、AST statement order 和 MemorySSA MUST NOT 单独生成 sequenced-before、RF、MO、SW、HB、风险或安全结论。

#### Scenario: R2 hands off a CAS pair
- **WHEN** R2 候选包含 CAS 并标记需要 A6 高级原子语义
- **THEN** A6 为其相关 function/context 请求 local facts，但只有后续实际 outcome、对象和 RF/MO 证据可进入正式证明链

#### Scenario: A fence is absent from R2 projection
- **WHEN** publication chain 需要一个没有对象地址且未形成 R2 access pair 的 fence
- **THEN** A6 从相关 root/function/context 的 local facts 取得 fence，不因 R2 未投影而错误宣称不存在 fence

### Requirement: Bind formal reasoning to exact runtime objects and ranges
正式 RF/MO 和 release/fence 证明 SHALL 仅使用 A5 `must` singleton 运行时对象、精确 byte range、address space、生命周期和调用/实例绑定。`may`、`unknown`、未知 range、开放生命周期或候选截断 MUST 形成 candidate-relevant frontier；字段声明不得直接充当运行时对象，union 不得因成员名不同被判定 disjoint。

#### Scenario: Two instances have the same atomic field declaration
- **WHEN** 两个运行时对象实例包含同一 `FieldDecl` 对应的 atomic 字段
- **THEN** A6 使用基对象实例加子对象路径区分它们，不按字段声明合并 RF/MO

#### Scenario: The atomic object has multiple may candidates
- **WHEN** provenance 只能给出两个可能对象且无法在预算内消歧
- **THEN** 相关 protocol 为 partial/unknown 并列出对象 frontier，不选择任一对象建立证明

### Requirement: Solve bounded reads-from and modification order deterministically
系统 SHALL 按精确原子对象和 range 分桶，在 candidate-relevant 闭合域内构建 value/guard/path-compatible RF 候选与 MO 偏序约束。RMW 和 CAS-success MUST 是 MO 成员，CAS-failure MUST NOT 是 MO 成员；RMW 读取 MUST 来自其 MO 直接前驱。求解器 SHALL 确定性枚举或约束传播所有预算内有效 assignment，并记录输入分母、约束、选择、拒绝原因和搜索完整性，MUST NOT 建立全局事件笛卡尔积。

#### Scenario: All valid assignments establish communication
- **WHEN** RF/MO 候选集合闭合且全部有效 assignment 都将 consumer observation 连接到受支持的 release chain
- **THEN** communication graph 可记录 universally-proven RF/MO 结论并供受限 discharge 使用

#### Scenario: One valid assignment lacks synchronization
- **WHEN** 存在一个完整有效 assignment 使 consumer 读取另一个 modification 且相关普通 payload 冲突缺少 SW/HB
- **THEN** A6 可保存该 assignment 作为风险 witness，不以其他安全 assignment 消解风险

#### Scenario: Search budget is exhausted
- **WHEN** RF/MO assignment、branch、事件、guard、CPU、wall 或输出预算在闭合前耗尽
- **THEN** 相关候选为 unknown 并报告已探索/总分母与预算 frontier，不从已探索子集输出 discharged

### Requirement: Apply language-version-specific release sequence rules
A6 MUST 根据请求中已验证的 C11、C17、C++17 或 C++20 profile 选择版本化 release-sequence policy。C11/C17/C++17 SHALL 接受 release head 后连续的同线程 modification 或 RMW；C++20 SHALL 只接受 release head 后连续的 RMW。精确 RMW follower SHALL 在 release sequence 识别后评价，不得先被一般多写者规则拒绝；竞争 head、plain writer 或连续性不明 MUST 形成 frontier 或有效反例。

#### Scenario: Same-thread relaxed store follows a release head
- **WHEN** consumer acquire read 精确读取 release head 后同线程的 relaxed store 且其他证据闭合
- **THEN** C11、C17 和 C++17 policy 可将该 store 纳入受限 release sequence，而 C++20 policy 不得如此处理

#### Scenario: Another thread performs a precise RMW follower
- **WHEN** release head 后的连续 modification 是另一线程对同一对象的精确 RMW，且其 RF/MO 前驱闭合
- **THEN** 四种语言 policy 均可将该 RMW 纳入受限 release sequence，且不得仅因线程不同标记一般多写者 unsupported

### Requirement: Prove three bounded acquire-release fence patterns
A6 SHALL 支持 release-fence/acquire-fence、release-fence/acquire-operation 和 release-operation/acquire-fence 三类 publication chain。每条证明 MUST 引用 release/acquire 端、同一精确原子对象的 carrier write/read、精确 RF、局部 must-before、相关 ThreadInstance 和完整 control/path 证据；只在 system syncscope 与有效 acquire/release 强度下生成 SW。

#### Scenario: Release fence and acquire fence communicate through relaxed operations
- **WHEN** producer 的 payload write must-before release fence，fence must-before relaxed carrier write，consumer relaxed carrier read 精确 reads-from 该 write 且 must-before acquire fence，之后才访问 payload
- **THEN** A6 建立 fence-fence SW 和受限 publication chain，并引用每个局部顺序与 RF 证据

#### Scenario: A release fence occurs after publication
- **WHEN** carrier write must-before release fence 而没有其他合法 release 来源
- **THEN** A6 不建立 release-fence publication proof，并在完整反例存在时报告 publication-order risk

#### Scenario: An acquire fence is too late
- **WHEN** consumer 在 acquire fence 前已访问 payload
- **THEN** 该 fence 不保护先前 payload access，A6 不输出 discharged

### Requirement: Restrict syncscope and sequential consistency claims
`atomic_signal_fence` 或 LLVM `syncscope("singlethread")` MUST NOT 建立线程间 SW；target-specific 或未建模 syncscope MUST 进入 explicit frontier。`seq_cst` MAY 在已支持模式中按同时具备 acquire/release 强度处理，但 A6 MUST NOT 声称求解全局 SC total order。

#### Scenario: Signal fence appears between threads
- **WHEN** source/IR 证据表明 fence 为 signal/singlethread scope
- **THEN** A6 输出 `signal-fence-interthread-unsupported` 中英文 frontier，不建立线程间同步

#### Scenario: A result would require global SC order
- **WHEN** protocol 结论依赖多个对象上的全局 `seq_cst` 排序而非已支持的局部 publication pattern
- **THEN** A6 输出 `seq-cst-global-order-unsupported` 并保持 unknown

### Requirement: Evaluate A6 protocols with conservative quantifiers
只有当 candidate slice、对象、事件、outcome、RF/MO assignment、release/fence chain 和 payload 访问全部闭合，并且所有有效 assignment 都建立所需同步时，A6 SHALL 输出 `discharged-within-bounded-model`。存在完整有效反例 assignment 时 SHALL 输出对应风险；任一 candidate-relevant 缺口或搜索未闭合时 MUST 输出 partial/unknown。任何结果 MUST 保持 `safety=not_established`，不得描述为全程序安全。

#### Scenario: A supported publication is universally proven
- **WHEN** 全部相关有效 assignment 都包含从 payload producer 到 consumer 的受支持 SW/HB 链且没有相关 frontier
- **THEN** overlay 在明确受限模型和证据分母内标记 discharged，并保留“非全程序安全证明”的双语说明

#### Scenario: Risk and incomplete evidence coexist
- **WHEN** 一个候选有完整风险 witness，但另一个 candidate-relevant 分支仍未闭合
- **THEN** 报告同时保留风险和 unknown/frontier，并按既有 P4 聚合优先规则计算退出状态，不丢弃未知分母

### Requirement: Propagate candidate-relevant completeness and explicit frontier
每个 A6 candidate SHALL 保存 root、TU、function/context、source binding、object、ThreadInstance、event/outcome、guard、RF/MO search 和 P4 protocol 的依赖闭包。相关缺失 MUST 产生非空中英文 frontier 并阻止正式消解；可证明无关的失败只降低 request-level completeness，不得清空独立完整候选。

#### Scenario: An unrelated translation unit fails
- **WHEN** 失败 TU 不属于某候选的 root、调用、对象、线程、事件或 protocol 依赖闭包
- **THEN** 请求级报告为 partial，但该候选仍按其闭合证据评价

#### Scenario: A runtime atomic call is not modeled
- **WHEN** 宽原子或非 lock-free lowering 产生未经 profile 的 `libatomic` runtime call 且与候选相关
- **THEN** 候选输出 `atomic-runtime-call-unsupported` 并保持 unknown，不把调用当成无原子效果

#### Scenario: A CAS loop or ABA-sensitive protocol is found
- **WHEN** outcome 依赖重复 weak CAS、循环收敛、ABA 或对象回收
- **THEN** A6 输出对应 unsupported/frontier，不把一次展开当成完整动态协议

### Requirement: Cache only complete A6 semantic artifacts conservatively
A6 SHALL 分层缓存完整、引用闭合的 local fact shard 与 solver result。缓存 key MUST 至少包含完整 source/BC digest、schema/extractor/solver/policy version、compiler/profile/stdlib/ABI/target/DataLayout、language standard、function/context、对象、依赖 digest 和影响语义/完整性的预算。partial、failed、开放候选集、未穷尽搜索、损坏或陈旧引用 MUST NOT 作为 complete result 复用；调度顺序、cache hit 和运行资源指标 MUST NOT 进入 semantic digest。

#### Scenario: The language standard changes
- **WHEN** 相同源文件和 BC 以 C++17 与 C++20 release-sequence policy 请求分析
- **THEN** solver cache identity 不同，系统不得跨标准复用可能改变结论的结果

#### Scenario: A complete warm cache is used
- **WHEN** 全部语义输入、依赖 digest、策略和预算相同且缓存引用验证通过
- **THEN** warm run 可复用 complete shard/result，cold/warm 规范化语义一致且 cache hit 仅进入 operational 字段

### Requirement: Expose a bounded offline CLI and bilingual report
A6 SHALL 提供显式 opt-in CLI，只消费已有 scope/artifact/事实输入，MUST NOT configure、build、link、运行目标程序、访问网络或 SSH。报告 SHALL 同时提供中文和英文的 finding、reason、limitation、suggestion、frontier，列出 protocol/event/RF/MO/release/fence 证据、分母、完整性、预算和缓存状态，并保持 `safety=not_established`。退出码 SHALL 保持 `0`（完整且无受支持风险）、`3`（完整风险）、`2`（candidate-relevant partial/unknown）和 `1`（请求/基础设施失败）的 P4 语义。

#### Scenario: Analysis completes with no supported risk
- **WHEN** 请求内全部 A6 候选闭合且均在受限模型内消解或不存在受支持风险
- **THEN** CLI 返回 0，同时报告明确说明这不是全程序安全证明

#### Scenario: Analysis has an unresolved candidate
- **WHEN** 任一 candidate-relevant frontier 阻止闭合且没有更高优先级的既有聚合状态
- **THEN** CLI 返回 2，并同时输出中文与英文的缺失证据和建议

### Requirement: Restrict compilers languages and advanced atomic scope
A6 SHALL 只支持 GCC/Clang 的 C11、C17、C++17、C++20，MUST 排除 Windows、MSVC 和 clang-cl。C profile MUST NOT 依赖 C++ AST 或标准库模型。consume、target-specific syncscope、未经 profile 的 runtime atomics、通用 SC order、一般多写者、CAS loop、ABA、reclamation、任意 lock-free algorithm、通用 model checking、通用 data race 和通用 happens-before MUST 保持 unsupported/frontier。

#### Scenario: An excluded compiler profile is requested
- **WHEN** 请求声明 Windows、MSVC 或 clang-cl profile
- **THEN** A6 以明确 failed/unsupported 诊断拒绝，不尝试按 GCC/Clang 语义解释

#### Scenario: C11 input is analyzed
- **WHEN** C11 fixture 使用 `<stdatomic.h>` fence、RMW 或 CAS
- **THEN** 系统仅使用 C AST/profile、实际 LLVM 事件和 C11 release-sequence policy完成分析

### Requirement: Validate four language profiles against reviewed truth
项目 SHALL 为 C11、C17、C++17、C++20 建立独立、人工复核的 planned/completed、TP、FP、FN 和 abstention 分母。required truth SHALL 覆盖直接 release/acquire 回归、三类 fence、错误 fence 位置、RMW release sequence、C++20 差异、CAS success/failure、weak/spurious、signal fence、competing modification、跨 TU、no-debug、AST+IR、IR-only、AST-only、开放 scope、对象不精确、预算和 cold/warm cache，并 SHALL 验证现有 P1–P4、A1–A5、R1–R3 回归不变。

#### Scenario: The cross-language release-sequence case is run
- **WHEN** 四种语言运行 release head、同线程 relaxed store、acquire consumer 的等价 fixture
- **THEN** truth 分别断言 C11/C17/C++17 与 C++20 的标准差异，并独立计入各语言分母

#### Scenario: Optional external backends are unavailable
- **WHEN** GenMC、herdtools7 或 ARM DevKit 不可用
- **THEN** required 离线 truth 与质量门禁仍可完成，外部 profile 记录 `not_run` 而不充当 oracle 或阻塞核心验收
