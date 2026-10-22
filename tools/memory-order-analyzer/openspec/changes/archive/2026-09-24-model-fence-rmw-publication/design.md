## Context

P1 已能从 LLVM IR 保存 `fence`、`atomicrmw` 和 `cmpxchg` 的基本属性，P2/P3 也能把高级原子访问投影到 effect 与线程上下文；但这些事实没有表达 CAS 成功/失败的动态 outcome、RMW 读取的前驱修改，也没有求解每个原子对象的 reads-from（RF）和 modification order（MO）。P4 因此只接受受限的 atomic store/load 发布，并把相关 fence、RMW、CAS 标为 unsupported。

A5 已提供 must/may/unknown 对象 provenance 与 byte range，R1/R1.1 已把分析范围收敛到执行根和线程入口，R2 已能把高级原子访问作为 A6 handoff，R3 已支持按 function/context 物化 LLVM 事实。A6 应复用这些边界构造一个独立 sidecar，而不是升级或重解释任何既有协议。

输入限定 GCC/Clang 的 C11、C17、C++17、C++20。C 与 C++ 分别使用独立 source profile；C 路径不得依赖 C++ AST 或标准库模型。Windows、MSVC、clang-cl、在线服务、SSH 和运行被分析程序均不属于实施范围。

## Goals / Non-Goals

**Goals:**

- 用独立版本协议保存 AST 高级原子源码事实、实际 LLVM 原子事件、RF/MO 约束、release sequence、fence pairing、P4 overlay 和双语报告。
- 在 root-driven、function/context-demanded、candidate-relevant 的有限域内证明或反驳一次性 publication chain。
- 正确区分 RMW、CAS success、CAS failure 和 weak CAS spurious failure，并按语言版本应用 release-sequence 规则。
- 支持 fence-fence、fence-atomic 和 atomic-fence 三类标准化发布模式。
- 对证据、scope、对象、动态 outcome 或搜索不闭合的候选保守输出 partial/unknown 和非空 frontier。
- 保持 P1–P4、A1–A5、R1/R1.1、R2、R3 的 schema、semantic digest、缓存身份和报告语义不变。
- 建立四语言人工 truth、优化级别归一化、离线质量入口和整体/语言/逐受影响模块行分支双 90% 门禁。

**Non-Goals:**

- 通用 happens-before/data-race 求解、完整交错枚举或全程序线程安全证明。
- consume dependency、全局 `seq_cst` total order、任意多写者、CAS loop、ABA、对象回收和一般 lock-free 算法。
- target-specific syncscope、`atomic_signal_fence` 的线程间证明、未经 profile 的 `libatomic` runtime broker。
- 通用 points-to、虚调用、任意函数指针、堆生命周期扩张或修改既有风险规则。
- 把 GenMC、herdtools7、ARM DevKit 作为运行时依赖、CI 必需项或正确性 oracle。

## Decisions

### 1. 使用独立 A6 sidecar 和只读 overlay

新增六类 v1 产物：

- `FenceRmwPublicationRequest`：输入 scope、语言标准、既有 artifact 引用、预算和策略。
- `AtomicSourceConstructFacts`：每 TU 的 canonical 原子源码构造、selected declaration、spelled/canonical type、order expression、标准库/profile 身份和 SourceIRBinding 候选。
- `AdvancedAtomicFunctionFacts`：由独立 A6 worker 按 demanded function/context 生成的引用闭合 atomic shard；它复用 R3 的 lazy module materialization 和 demand transport，但不写入或冒充 `FunctionSemanticFacts`。
- `AdvancedAtomicLocalFacts`：每 artifact/function/context 的实际 LLVM 原子事件、outcome、guard、对象和值关系。
- `BoundedAtomicCommunicationGraph`：动态事件实例、RF 候选/选择、MO 约束、release sequence、fence pairing、SW 边和求解 frontier。
- `AdvancedPublicationProtocolOverlay`：引用 P4 protocol/candidate，附加 A6 assessment 与证明链，不复制或改写 P4 内容。
- `FenceRmwPublicationReport`：双语诊断、计数、完整性、缓存和退出状态。

替代方案是把字段加入 P1/P3/P4；这会改变稳定协议、缓存与历史 truth，且会把局部事实和跨线程求解耦合，因此拒绝。

### 2. AST 只负责源码语义和绑定，不负责运行时通信证明

C 的 extractor 使用 Clang `AtomicExpr` 的 operation、object/value/order 参数和 canonical declaration；C++ extractor 使用 canonical `std::atomic<T>` specialization、实际 selected method/overload、canonical member declaration、标准库与 ABI profile。两者都保存 spelled form 以供诊断，但 classification 不能依赖名字包含 `atomic`、源码拼写或 mangled symbol。

AST-only 可保存 source candidate、order expression 和跨 TU entity relation，但不能生成 RF、MO、SW、HB、risk 或 discharged。原因是源码本身不能证明实际 lowering、动态 outcome 或运行时读取来源。

### 3. 用 outcome-aware LLVM 事件作为正式语义输入

`AtomicEventInstance` 至少保存 stable event ID、artifact/function/context/ThreadInstance、IR instruction identity、source binding、kind、exact object/range/address space、ordering、failure ordering、syncscope、RMW operation、compare/desired/observed value、weak、guard、multiplicity 和 completeness。

CAS 被拆为互斥的条件 outcome：success 是 read 加 modification，使用 success ordering；failure 是 read-only，使用 failure ordering，不进入 MO 或 release sequence。weak CAS 额外保留 spurious-failure 可能性。RMW 是读加不可分割 modification，必须读取 MO 的直接前驱。

P1 eager 事实和 R3 demanded fact 使用同一规范化事件模型并进行语义等价验收，但不修改 P1/R3 产物。`-O0` 标准库 order dispatcher 产生的多条 guarded IR 指令只有在 source binding、guard 和可达 outcome 闭合后才能归一化；不得按指令条数当作多次动态操作。

### 4. R2 handoff 只触发需求，A6 直接消费局部事件

R1/R1.1 给出 root 和 reachable slice，R2 的 atomic candidate/handoff 给出 A6 consumer seed，R3 demand graph 据此调度所需 function/context。独立 A6 worker 先产生 `AdvancedAtomicFunctionFacts`，再归一化为 `AdvancedAtomicLocalFacts`；fence 没有对象地址且 R2 不投影 fence pair，因此 demand 不能只依赖 R2 对象 pair。

不得把 P2 `EffectSummary.order` 当作 sequenced-before，不得把 P3 reads-from candidate 当作 RF，不得把 R2 pair 当作风险或安全结论，也不得把 MemorySSA 当作线程间 MO。它们只能缩小需求或提供局部依赖候选。

### 5. 正式求解仅接受精确对象与闭合事件域

A6 按 A5 exact must-singleton 对象、精确 byte range 和 address space 分桶。may/unknown 对象、范围重叠未知、生命周期或 provenance 不完整会产生 candidate-relevant frontier。union overlap 保持可能别名，不能因成员名不同而排除。

每个对象的求解域由 root/reachable slice、相关 ThreadInstance、P4 protocol gate 和 exact local events 构成；禁止全局事件笛卡尔积或 all-defined fallback。开放 scope、歧义 callback、失败 shard 和相关外部修改使域不闭合。

### 6. 使用确定性的有限 RF/MO 约束求解器

求解器先按对象、byte range、值、guard、线程和局部顺序生成 RF 候选，再构造每个原子对象的 MO 偏序约束。RMW/CAS-success 是 MO 成员，CAS-failure 不是；RMW 的 RF 来源必须是其 MO 直接前驱。初始化事件作为可选的已知首修改进入模型。

首版使用项目自有的确定性有限域回溯/约束传播，而不是引入外部 SMT 或 model checker。预算至少覆盖对象、动态事件、RF edge、MO node/branch、assignment、guard、递归、CPU、wall 和输出大小。排序、cache hit 和 worker 完成顺序不得进入 semantic digest。

assessment 采用全称/存在量词：所有闭合有效 assignment 都建立所需 publication chain 才能 `discharged-within-bounded-model`；存在一条完整有效 assignment 暴露相关普通 payload 冲突且缺少 SW/HB 时可形成 risk；候选集合或搜索未闭合时必须 unknown，不能从已搜索子集推出消解。

### 7. release sequence 按语言标准选择策略

请求的 language/profile identity 决定不可隐式转换的 release-sequence policy：

- C11、C17、C++17：release head 后连续的同线程修改或任意线程 RMW 可进入受限 release sequence。
- C++20：release head 后只有连续 RMW 可进入 release sequence。

受限链允许精确的 RMW follower，因此不能被“一般多写者不支持”规则提前拒绝；竞争 release head、plain writer 或无法确定连续性的修改仍进入 frontier。缓存 key 必须包含 language standard 和 policy version。

### 8. fence pairing 显式引用原子载体事件

支持以下三类链：release fence 到 acquire fence、release fence 到 acquire operation、release operation 到 acquire fence。每条 pairing 必须引用 release/acquire fence、同一精确原子对象上的 carrier write/read、精确 RF、局部 must-before 以及对应 ThreadInstance。

只有 system scope 且 ordering 满足模式时才生成 SW。`syncscope("singlethread")`/`atomic_signal_fence` 不建立线程间同步；target-specific scope 进入 frontier。`seq_cst` 仅在这些模式中按具备 acquire/release 强度处理，不求解全局 SC 顺序。

### 9. P4 通过 overlay 保持原语义

overlay 以稳定 ID 引用 P4 protocol、flag、payload、producer/consumer、success observation 和原 assessment，再附加 A6 event/RF/MO/release/fence proof。P4 原本的 unsupported 仍保留；A6 报告单独说明它是否在 A6 受限模型中变为 risk、discharged 或 unknown。

报告继续使用 `safety=not_established`。退出码保持 `0`（完整且无受支持风险）、`3`（完整且有风险）、`2`（candidate-relevant partial/unknown）、`1`（请求/基础设施失败）；存在风险与 unknown 时按不丢失 unknown 的既有优先规则汇总。

### 10. candidate-relevant 完整性和 frontier 是证明的一部分

每个 candidate 保存依赖闭包和分母：root、function/context、TU、source binding、object、thread instance、event、guard、RF/MO search 与 P4 protocol。无关失败只降低 request-level completeness，不清空独立候选；相关 frontier 必须使候选 unknown。

frontier 至少区分 source/IR binding ambiguous、profile/ABI mismatch、AST-only、object/range unknown、runtime call unsupported、syncscope unsupported、signal fence、dynamic order、CAS outcome、weak spurious path、CAS loop、RMW transition、competing modification、open RF set、incomplete MO search、release-sequence budget、fence pairing、global SC、consume 和依赖/worker/预算失败，并同时输出中文与英文字段。

### 11. 缓存只复用完整、引用闭合的语义 shard

local facts 和 solver result 分层缓存。key 至少包含完整 source/BC digest、schema/extractor/solver/policy version、compiler/profile/stdlib/ABI/target/DataLayout、language standard、function/context、对象、依赖 digest 和影响语义或完整性的预算。partial、failed、开放候选集和未穷尽搜索不作为 complete result 复用；损坏或陈旧引用必须拒绝。

### 12. 四语言 truth 与单元覆盖是 required gate

C11、C17、C++17、C++20 分别记录 planned、completed、TP、FP、FN、abstention。固定矩阵包含 direct release/acquire 回归、三类 fence、错误 fence 位置、RMW chain、C++20 release-sequence 差异、CAS success/failure、weak/spurious、signal fence、competing writer、跨 TU/no-debug、四种 evidence mode、开放 scope、provenance、预算和 cold/warm cache。

GenMC、herdtools7、ARM DevKit 可使用录制或可选 live profile 作差异调查，结果与人工 truth 分开。所有新增/修改/复用自有执行代码必须有有效单元测试；项目整体、Python、C++ 和每个受影响模块的 line/branch 均至少 90%，集成 truth 不补入单元覆盖。

## Risks / Trade-offs

- [有限域过窄导致 abstention 较高] → 明确分母与 frontier，先保证不从不闭合搜索推出错误消解，再由 truth 指标决定后续扩域。
- [`-O0` 标准库 dispatcher 制造多个 IR 变体] → 使用 source binding、guard、selected overload 和 profile 归一化，并以 `-O0`/`-O2` 等价作为 required gate。
- [RF/MO 枚举组合爆炸] → 按对象和 candidate slice 分桶，先传播 guard/value/MO 约束，再使用硬预算和可审计 partial。
- [C++20 规则误用于其他语言] → language-standard policy 进入请求、缓存和证据链，并用跨语言差异 fixture 锁定。
- [把 RMW follower 误认为一般多写者] → 在竞争写者检查前识别精确 release-sequence member；链外 competing modification 才触发 frontier。
- [外部工具与内部语义不一致] → 只记录对照和版本，不以外部工具覆盖人工 truth 或内部证据完整性。
- [独立 overlay 造成更多产物] → 使用稳定引用和 manifest，换取既有协议兼容与可独立回滚。

## Migration Plan

1. 先增加 schema、引用验证和只读协议模型，不接管既有 P4 CLI。
2. 增加 AST/LLVM A6 local facts，并验证 eager/R3 与 `-O0`/`-O2` 规范化等价。
3. 增加按对象 RF/MO、release-sequence 和 fence 求解及 candidate-relevant frontier。
4. 增加 P4 overlay、独立 CLI、缓存和双语报告；默认既有命令保持不变。
5. 跑四语言 truth、既有全量回归、单元覆盖和文档校验，通过后才允许同步和归档。

回滚只需移除 A6 opt-in CLI/sidecar；因为既有 schema 和默认命令未修改，历史产物无需迁移。

## Open Questions

- 首版精确 RMW value transition 是否只接受整数 `xchg/add/sub/and/or/xor`，其余 operation 全部 unknown；实施时应以 LLVM 21 实际 opcode 和四语言 fixture 固化最终白名单。
- 风险与 candidate-relevant unknown 同时存在时的顶层退出码应沿用 P4 当前优先规则；实施前需用现有 P4 report aggregator 测试锁定，不新增不兼容解释。
- 未经 profile 的宽原子 `libatomic` 调用首版固定为 unsupported；后续是否增加 runtime broker profile 应由 A6 truth 与真实工程 abstention 数据单独提案。
