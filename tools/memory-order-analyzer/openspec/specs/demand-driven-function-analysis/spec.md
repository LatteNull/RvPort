# demand-driven-function-analysis

## Purpose

规范 R3 基于 LLVM 21 的轻量模块索引、按函数与上下文懒提取、需求图、worker 调度、缓存、完整性、双语报告，以及与既有 eager、P2、P3、R2 语义等价的只读适配边界。

## Requirements

### Requirement: Version R3 artifacts independently without changing existing protocols
系统 SHALL 定义版本化的 `DemandDrivenAnalysisRequest`、`LLVMModuleIndexFacts`、`FunctionSemanticFacts`、`FunctionEffectFacts`、`FunctionThreadFacts`、`AnalysisDemandGraph`、`WorkerExecutionManifest` 和双语 `DemandDrivenAnalysisReport`。R3 SHALL 通过独立 sidecar 和只读适配器接入，MUST NOT 将部分函数事实序列化或宣称为 `ModuleFacts v2`、`LocalAnalysisFacts`、`ThreadLocalFacts`、`EffectSummary v1`、`ThreadContextGraph v1` 或 `ConcurrentAccessCandidateGraph v1`，并 MUST 保持 P1–P3、R1、R1.1、R2 既有报告语义不变。

#### Scenario: Partial function facts are produced
- **WHEN** 一个请求只完成 scope 中部分 demanded function/context
- **THEN** 系统将结果保存为相应 R3 function shard 和 partial demand graph，不生成带既有全量协议名称的部分 artifact

#### Scenario: A complete lazy view is consumed by an existing stage
- **WHEN** 某既有 P2、P3 或 R2 消费切片所需的 R3 shard 全部完成且引用闭合
- **THEN** 只读适配器提供与 eager 输入规范化语义等价的内存视图，同时不修改既有 artifact schema、报告字段或缓存身份

### Requirement: Build a lightweight LLVM module index without materializing function bodies
系统 SHALL 使用 LLVM 21 lazy bitcode module 为每个 BC artifact 生成 `LLVMModuleIndexFacts`，索引仅包含 artifact/完整 BC digest、symbol、definition/declaration、linkage/visibility/COMDAT、ABI、profile、target、`DataLayout` 及必要源码绑定。索引阶段 MUST NOT 遍历 basic block 或 instruction、扫描 load/store/call、构造函数级 LLVM 分析，亦 MUST NOT 预先 materialize 全部函数体。

#### Scenario: A module contains many unreachable definitions
- **WHEN** 索引一个只有少量 root 可达、但包含大量已定义函数的有效 BC
- **THEN** 所有定义可作为 symbol/index 条目出现，而索引阶段的函数体物化数和深度函数事实数均为零

#### Scenario: Index metadata cannot be obtained without a body
- **WHEN** 某项信息必须 materialize 函数体才能取得
- **THEN** 系统将该信息推迟到 function shard 或记录缺失证据，而不是在索引阶段隐式物化函数体

### Requirement: Preserve eager function block and instruction identities
系统 SHALL 在 materialize 原始函数体后，使用与 eager 路径相同的 artifact/symbol、argument number、原始 basic-block 顺序和 instruction 顺序生成 function、argument、block 与 instruction identity。调度顺序、batch、worker、cache hit、运行时间和并发完成顺序 MUST NOT 改变 identity 或 semantic digest。

#### Scenario: The same function is extracted eagerly and lazily
- **WHEN** 同一完整 BC digest 中的函数分别经过既有 eager 提取和 R3 lazy 提取
- **THEN** 其 function/argument/block/instruction identity 及引用闭包逐项一致

#### Scenario: Worker order changes
- **WHEN** 使用不同 worker 数量或 batch 完成顺序处理同一请求
- **THEN** 规范化后的 semantic digest、identity 和证据引用保持一致

### Requirement: Seed and expand a bounded monotonic demand graph
系统 SHALL 从 `RootDrivenAnalysisPlan v1` 和 `ThreadEntryRootOverlay v1` 中已验证的 `main`、显式入口、`pthread_create`、`thrd_create`、`std::thread`、`std::jthread` 及显式 async roots 生成 demand seed，并 SHALL 只沿 function shard 中精确绑定的 direct call 或 callback 单调扩展 function/context demand。每个 demand SHALL 记录 artifact、函数、分析层、context、来源 root/callsite、consumer、状态和预算；重复 demand SHALL 确定性合并。

#### Scenario: An exact direct call discovers a new function
- **WHEN** 已完成 shard 中的直接调用通过既有 linkage/ABI/SourceIRBinding 规则唯一绑定到 scope 内定义
- **THEN** worklist 增加对应 callee/context demand，并记录触发 callsite 和证明边

#### Scenario: A callback is ambiguous
- **WHEN** callback SSA、源码实体、ABI 或 profile 无法唯一对齐目标
- **THEN** 系统生成关联 root/callsite 的 ambiguous-callback frontier，且不调度所有可能定义或 all-defined fallback

### Requirement: Handle recursion and unsupported expansion conservatively
系统 SHALL 以稳定 SCC/递归上下文身份、有限迭代和显式预算处理递归需求。间接调用、开放 scope、AST-only、缺失定义、默认或组合 async policy、递归不收敛以及预算耗尽 MUST 形成非空且可追溯的 frontier；系统 MUST NOT 回退为全 BC load/store 扫描、全模块深度提取或将缺失事实解释成无访问。

#### Scenario: A recursive SCC reaches its budget
- **WHEN** 递归/SCC 在允许的 context 或迭代预算内不能闭合
- **THEN** 相关 demand 标记 partial，报告 `recursion-budget` frontier 及受影响 root/consumer，不 materialize 无关函数

#### Scenario: An AST-only translation unit is demanded
- **WHEN** root 或调用依赖切片需要只有 AST 源事实而没有可用 BC 的 TU
- **THEN** 系统保留独立 AST 事实并报告 `ast-only-no-runtime-facts` frontier，不伪造 LLVM function shard、同步或安全结论

### Requirement: Materialize only demanded functions and extract complete layer shards
系统 SHALL 使用 `GlobalValue::materialize` 只物化已调度的函数，并分别生成引用闭合的 `FunctionSemanticFacts`、`FunctionEffectFacts` 和 `FunctionThreadFacts`。一个 shard MUST 覆盖其声明的完整 function/context/layer 分母及完整性状态；未完成分析 MUST 标记 partial/failed，而不得输出空效果作为 completed。

#### Scenario: An unreachable function contains memory accesses
- **WHEN** 一个定义不在任何 seed 或精确 demand 扩展路径上
- **THEN** 该函数没有 materialized body、深度 LLVM 分析或 function shard，其 load/store 也不会因全局扫描进入输出

#### Scenario: A demanded function needs multiple analysis layers
- **WHEN** 同一函数/context 同时被 semantic、effect 和 thread 层需求
- **THEN** 系统仅在各层完整时分别输出完整 shard，并允许在同一 batch 内复用该函数已物化的原始 body 而不混合各层协议

### Requirement: Schedule deterministic batches with bounded parallel workers
系统 SHALL 按 artifact、分析层、函数和 context 的稳定 key 形成确定性 batch，并 SHALL 对并行 worker 数、batch 函数数、materialized instruction、分析查询、递归、CPU、wall、RSS 和输出大小实施显式预算。单个 BC batch MUST 只解析一次；可变 LLVM `Module` MUST NOT 跨 worker 线程共享。

#### Scenario: Several demands target one bitcode artifact
- **WHEN** 一个 batch 含同一 BC artifact 的多个函数/context/layer demand
- **THEN** `WorkerExecutionManifest` 记录一次 module parse、确定的调度成员和逐函数 materialize/completion 状态

#### Scenario: Parallelism changes operational order
- **WHEN** 同一请求分别以一个和多个 worker 执行
- **THEN** 规范化语义产物相同，而 manifest 可记录不同的 attempt/order/resource 数据且这些数据不进入 semantic digest

### Requirement: Isolate worker failures and propagate candidate-relevant completeness
系统 SHALL 将 parse/materialize/analysis failure、worker crash、timeout、依赖失败和预算耗尽限制到相关 artifact/batch/function/context，并继续处理无依赖的 demand。每个 partial/failed demand MUST 产生至少一个包含中英原因、root、function/context/layer、缺失证据和 attempt 的 frontier；相关 root 或 R2 candidate 切片不完整时 MUST 保持 partial/unknown，不得输出完整无风险结论。

#### Scenario: One worker crashes while another artifact is independent
- **WHEN** 一个 artifact batch 的 worker crash，而另一个 batch 不依赖其 shard
- **THEN** 前者产生 worker-crash frontier，后者继续完成且其结果不会被全局失败清空

#### Scenario: A failed shard is candidate-relevant
- **WHEN** R2 候选或排除判断依赖 failed/partial effect、thread 或 semantic shard
- **THEN** 只读适配器将该依赖传播为 candidate-relevant frontier/unknown，不把缺失 shard 当成空访问、not-parallel 或 protected

### Requirement: Cache only complete function context shards with conservative invalidation
系统 SHALL 仅缓存状态为 completed、引用闭合的单 function/context/layer shard。缓存 key MUST 至少包含完整 BC digest、schema/extractor/分析策略版本、profile、target、`DataLayout`、artifact/function identity、analysis layer、context identity 和所有影响语义或完整性的预算；partial、failed、crash、timeout、未闭合 SCC 或损坏 shard MUST NOT 被复用。调度顺序和 cache hit MUST NOT 进入 semantic digest。

#### Scenario: Warm cache repeats a complete request
- **WHEN** 输入、完整 BC digest、profile/target/DataLayout、策略和预算均未变化且缓存 shard 验证通过
- **THEN** warm run 可复用 completed shard，cold/warm 的规范化语义一致并在 operational 指标中记录 cache hit

#### Scenario: A sibling definition changes in the bitcode artifact
- **WHEN** 目标函数文本未变但完整 BC digest 因同 artifact 其他内容变化而改变
- **THEN** 首版缓存保守失效并重新分析，不基于局部文本摘要静默复用旧 shard

### Requirement: Keep eager commands unchanged and expose an explicit offline R3 CLI
系统 SHALL 保持现有 eager CLI 的默认行为、参数、产物、缓存和退出语义不变，并新增显式 opt-in 的 R3 CLI。R3 CLI SHALL 只消费已有 scope/artifact/R1/R1.1 输入，MUST NOT 执行 configure、build、link、目标程序、网络或 SSH；退出码 SHALL 为 `0`（请求内 demanded shard 完成）、`2`（partial/unknown/frontier）和 `1`（请求或基础设施失败），报告 SHALL 保持 `safety=not_evaluated`、`findings=null`。

#### Scenario: Existing eager command is invoked
- **WHEN** 用户不选择 R3 CLI 而运行任一既有 eager 命令
- **THEN** 其行为、协议和退出码与本 change 前一致，不被自动切换到 lazy 路径

#### Scenario: R3 completes with frontier
- **WHEN** demanded functions 中存在可报告的 unsupported、timeout 或预算 frontier
- **THEN** R3 CLI 返回 2、输出双语 partial/unknown 诊断，并且不把零 finding 描述为安全

### Requirement: Report demand coverage and operational metrics bilingually
`DemandDrivenAnalysisReport` SHALL 以中英文字段和可追溯引用分别报告 indexed、demanded、scheduled、materialized、completed、partial、failed、cache-hit、module parse、CPU、wall、peak RSS、输出大小、root/reachable coverage、frontier 与预算。计数分母和状态转换 MUST 明确；资源指标、缓存命中和调度信息 MUST 与 semantic evidence 分离。

#### Scenario: A sparse reachable benchmark completes
- **WHEN** 固定规模 BC 中只有一小部分函数从 roots 可达
- **THEN** 报告同时展示全部 indexed 定义数和较小的 demanded/materialized/completed 数、module parse 次数及资源指标，使未物化工作量可审计

#### Scenario: Diagnostics are emitted
- **WHEN** 任一 demand 为 partial、failed 或 unsupported
- **THEN** 报告同时提供 `reason`/`suggestion` 与 `reason_en`/`suggestion_en`，并引用对应 artifact/root/function/context/layer

### Requirement: Restrict compiler language and analysis scope
R3 SHALL 仅支持 GCC/Clang 的 C11、C17、C++17、C++20 输入，并 MUST 排除 Windows、MSVC 和 clang-cl。C 的 `pthread_create`/`thrd_create` 路径 MUST NOT 依赖 C++ AST 或标准库 profile。R3 MUST NOT 在本 change 中实现 A6 fence/RMW、通用指针分析、风险规则修改、持久 LLVM daemon、B1 CMake scope 导入或 B2 容器整合。

#### Scenario: A C11 thread root is analyzed
- **WHEN** C11 fixture 通过直接 pthread 或 C11 `thrd_create` 建立已验证 root
- **THEN** R3 仅使用 C profile、C AST/IR binding 和对应 runtime evidence 产生需求，不加载 C++ 标准库模型

#### Scenario: An excluded compiler profile is requested
- **WHEN** 请求声明 MSVC、clang-cl 或 Windows profile
- **THEN** 系统以明确 unsupported/failed 诊断拒绝，不尝试兼容编译或静默按 GCC/Clang 解释

### Requirement: Prove normalized eager and lazy semantic equivalence
项目 SHALL 为闭合支持范围建立 eager/lazy 规范化语义等价验收，比较 function/instruction identity、semantic/effect/thread facts、对象与执行实例引用、MHP、保护、R2 candidate/exclusion/frontier 和 completeness；只允许规范化调度顺序、cache/资源字段和物理输出路径。验收 SHALL 覆盖不可达函数不物化、需求扩展、跨 TU、递归、失败隔离、cold/warm cache、固定稀疏规模、R2 四语言 truth 与 TinyCThread。

#### Scenario: Lazy output is smaller but semantically complete for the demand slice
- **WHEN** eager 路径包含不可达函数而 R3 只分析 root 可达需求
- **THEN** 比较器在相同需求分母上得到等价的既有语义，同时断言不可达函数未物化且未出现在 R3 shard

#### Scenario: A semantic field differs
- **WHEN** eager/lazy 在任一 identity、effect、thread、candidate、exclusion、frontier 或 completeness 字段上存在不可允许差异
- **THEN** required equivalence gate 失败，不得用更小输出、性能提升或零 finding 覆盖差异
