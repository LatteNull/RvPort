## 1. 协议基线与兼容边界

- [x] 1.1 盘点并固定 P1 `ModuleFacts v2`、P2 `EffectSummary v1`、P3 `ThreadContextGraph v1`、R1 `ExecutionRoot v1`、R1.1 `ThreadEntry v1`、R2 `ConcurrentAccessCandidateGraph v1` 的 schema、CLI、缓存和规范化报告基线，增加不可变回归快照，证明本 change 不迁移既有协议。
- [x] 1.2 在项目 schema/协议清单中定义并校验 `DemandDrivenAnalysisRequest v1`、`LLVMModuleIndexFacts v1`、三类 `Function*Facts v1`、`AnalysisDemandGraph v1`、`WorkerExecutionManifest v1` 和 `DemandDrivenAnalysisReport v1`，补齐引用闭包、状态机、预算、双语字段及正常/缺字段/非法引用单元测试。
- [x] 1.3 定义 R3 artifact 布局、canonical JSON 与 semantic/operational 字段分界，确保 batch、worker、调度、cache hit 和资源时间不进入 semantic digest，并增加顺序扰动与 operational 字段变化的单元测试。
- [x] 1.4 为 GCC/Clang 的 C11、C17、C++17、C++20 定义独立 R3 profile/ABI/target/DataLayout 校验，明确拒绝 Windows、MSVC、clang-cl，并验证 C 路径不加载 C++ AST/标准库模型。

## 2. LLVM 21 轻量索引与稳定身份

- [x] 2.1 将既有 eager identity 逻辑抽取为共享的 symbol、argument 和 function-local block/instruction identity helper，保持现有 eager 产物字节/语义兼容，并为匿名值、local linkage、alias/ifunc、phi/invoke、无 debug 增加 C++ 单元测试。
- [x] 2.2 新增基于 LLVM 21 `getLazyBitcodeModule` 的 module-index worker，只读取 symbol、definition/declaration、linkage/visibility/COMDAT、ABI/profile、target、DataLayout 和必要源码绑定，不遍历函数体或构造函数分析。
- [x] 2.3 在索引 worker 中记录 parse、materialized function/instruction 和失败证据，加入“很多不可达定义但索引阶段零 body materialization”的 C/C++ 单元测试及损坏 BC、unsupported target、缺失 DataLayout 异常测试。
- [x] 2.4 使用 `GlobalValue::materialize` 新增按指定 function identity 物化入口，拒绝声明、歧义实体和 identity/digest 不匹配，并逐项比较 eager/lazy function、argument、block、instruction identity。

## 3. 按函数与上下文的深度事实 shard

- [x] 3.1 实现 `FunctionSemanticFacts v1` 提取器，仅处理已物化 demanded function，覆盖既有 P1 所需语义节点、边、内存事件和源码引用，并对正常、无 debug、unsupported instruction、预算中断及引用闭合编写单元测试。
- [x] 3.2 实现 `FunctionEffectFacts v1` 提取器，按 function/context 构造必要的 DT/BasicAA/MemorySSA 与局部求值证据，保留 P2 原始语义、bottom/unknown/guard/binding/dependency 和预算，并增加正常、别名未知、clobber、递归依赖和异常单元测试。
- [x] 3.3 实现 `FunctionThreadFacts v1` 提取器，按 function/context 构造必要的 DT/PDT/LoopInfo 与线程局部证据，保持 P3 order/source mapping 语义，并增加 pthread、thrd、C++ broker、循环、异常边和预算单元测试。
- [x] 3.4 强制每个 function/context/layer shard 仅在完整且引用闭合时标记 completed；materialize/分析/预算失败输出 partial/failed 与具体缺失证据，不得输出空效果冒充完成，并覆盖所有状态转换测试。
- [x] 3.5 在同一 lazy module batch 内安全复用已物化函数体和只读基础结构，同时保持 semantic/effect/thread shard 独立版本化，增加多层需求和单层失败不污染其他层的单元测试。

## 4. Demand graph、有界 worklist 与 frontier

- [x] 4.1 实现 `AnalysisDemandGraph` 的 stable key、seed、edge、consumer、状态与 provenance 模型，从 R1 plan/R1.1 overlay 读取 `main`、显式入口、pthread、thrd、`std::thread`、`std::jthread` 和显式 async roots，并覆盖四语言 seed 单元测试。
- [x] 4.2 实现有界单调 worklist、重复 demand 确定性合并和 exact direct-call 扩展，沿既有 linkage/ABI/SourceIRBinding 规则保存 callsite 证明，不因同名 symbol 或未知定义扩展。
- [x] 4.3 实现已验证 callback 扩展，组合 callback SSA、源码实体、编译 profile、ABI 和标准库 profile；歧义 callback、间接调用、默认/组合 async policy 生成非空 frontier 而不调度所有定义。
- [x] 4.4 实现递归/SCC identity、有限上下文合并与迭代预算，预算内收敛时确定性闭合，超限时输出 `recursion-budget` frontier，增加直接递归、互递归、重复 root 和 context 爆炸测试。
- [x] 4.5 实现开放 scope、AST-only、缺失定义、依赖失败和 unsupported 扩展的候选相关 frontier，证明不会触发 all-defined 或全 BC load/store fallback，并覆盖与无关 root 隔离的单元测试。

## 5. 确定性调度、worker 隔离与资源预算

- [x] 5.1 实现按 artifact、analysis layer、function、context stable key 的 deterministic batch planner，定义 batch size、worker count 和公平调度规则，并验证输入排列、单/多 worker 下语义计划一致。
- [x] 5.2 实现单 batch 只解析一次 BC 的 worker 执行协议与 `WorkerExecutionManifest`，记录 attempt、parse、materialize、completion、CPU/wall/peak RSS/output，不在线程间共享可变 LLVM Module。
- [x] 5.3 为 function、context、SCC、batch、artifact、root 和请求实现 materialized instruction、分析查询、递归、CPU、wall、RSS、输出字节等预算，超限精确归因到 demand/frontier。
- [x] 5.4 实现 parse/materialize/analysis error、worker crash、timeout 与非法输出隔离；失败 batch 的依赖切片降级，独立 batch 继续，并加入进程非零退出、截断 JSON、超时、OOM/预算模拟单元测试。
- [x] 5.5 规范化 manifest 与报告聚合顺序，确保不同并行度、完成顺序和 retry attempt 不改变 semantic digest，并以重复运行单元测试锁定确定性。

## 6. Shard 缓存、只读适配与既有阶段组合

- [x] 6.1 实现 completed function/context/layer shard 缓存 key，纳入完整 BC digest、schema/extractor/策略、profile、target、DataLayout、函数/上下文/层和语义预算；禁止缓存 partial、failed、timeout、crash 或未闭合 SCC。
- [x] 6.2 实现缓存 value 的 schema、digest、引用闭包和完整性校验；损坏、旧版本、预算/profile/target/DataLayout/whole-BC digest 不匹配时拒绝并重算，增加 cold/warm、污染与 sibling-definition 变化测试。
- [x] 6.3 实现面向 P2 的只读 shard adapter，在需求闭合时产生与 eager local/effect 输入规范化等价的内存视图，在缺 shard 时传播 frontier 而不写出伪 `LocalAnalysisFacts` 或空 effect。
- [x] 6.4 实现面向 P3 的只读 shard adapter，在需求闭合时保持线程局部事实、source mapping、execution order 和完整性语义，在缺 shard 时不得推导 not-parallel、同步或安全。
- [x] 6.5 将 R3 adapter 加法式接入 R2，验证 execution instance、对象、MHP、protection、candidate/exclusion/frontier 与 eager 分母等价；不得修改 R2 `safety=not_evaluated`、`findings=null` 或风险规则。
- [x] 6.6 保持全部既有 eager CLI、默认参数、缓存和退出码不变，增加回归测试证明未显式选择 R3 时不会进入 lazy 路径。

## 7. R3 CLI、报告与可观测性

- [x] 7.1 按项目命名规范确定并实现显式 R3 CLI，仅读取已有 scope/artifact/R1/R1.1 输入，输出 indexes、function shards、demand graph、manifest 和 report，且不调用 configure/build/link、目标程序、网络或 SSH。
- [x] 7.2 实现 0/2/1 退出码、`safety=not_evaluated`、`findings=null` 和 root/reachable/candidate-relevant completeness；任何 partial/unknown/frontier 返回 2，基础设施或请求失败返回 1。
- [x] 7.3 实现 `DemandDrivenAnalysisReport` 的 indexed、demanded、scheduled、materialized、completed、partial、failed、cache-hit、module parse、CPU、wall、RSS、输出大小与预算分母，并校验状态计数守恒。
- [x] 7.4 为所有 frontier 和失败输出 `reason`/`reason_en`、`suggestion`/`suggestion_en` 以及 artifact/root/function/context/layer/attempt 引用，增加中英字段成对、稳定排序和无源码位置降级测试。

## 8. 四语言语义、等价与规模验收集

- [x] 8.1 建立独立 C11、C17、C++17、C++20 R3 fixture/truth 清单，覆盖单 TU、跨 TU、no-debug、AST+IR、IR-only、AST-only、不可达函数、精确 direct-call/callback、开放 scope 和各线程 root，C 用例不依赖 C++ 模型。
- [x] 8.2 实现 eager/lazy 规范化比较器，比较 identity、semantic/effect/thread facts、对象/执行实例、MHP、protection、R2 candidate/exclusion/frontier/completeness，仅忽略明确列出的调度、cache、资源和物理路径字段。
- [x] 8.3 增加带不可达 load/store/call 的哨兵 fixture，断言其 symbol 被索引但 body、instruction、LLVM 分析和 shard 均未物化；把任何隐式全量物化作为 required gate 失败。
- [x] 8.4 增加跨 TU demand 扩展、直接/互递归、歧义 callback、worker failure/timeout、预算、损坏缓存和 cold/warm truth，逐项断言 frontier、失败隔离、semantic digest 与 cache hit。
- [x] 8.5 建立固定稀疏可达规模集，分别记录 cold/warm 的 indexed、demanded、scheduled、materialized、completed、partial、failed、cache-hit、module parse、CPU、wall、peak RSS 和输出大小；记录环境与样本，不把单次性能当正确性 oracle。
- [x] 8.6 在 R3 路径持续运行并分别报告 R2 的 C11/C17/C++17/C++20 truth 与固定 TinyCThread revision，任何 eager/lazy 不允许差异、FP/FN 或新 abstention 阻断 required gate。

## 9. 单元覆盖、文档与最终 required gate

- [x] 9.1 为所有新增、修改或复用的 Python/C++ 自有可执行代码补齐正常、边界、异常和 partial/unknown 单元测试，将未加载源码、子目录和可执行头文件纳入统计；不得以集成、编译或性能测试代替单元测试。
- [x] 9.2 在全新输出目录运行项目整体、Python、C++及每个受影响模块的行覆盖率和分支覆盖率门禁，所有维度均至少 90%；记录 hit/total、报告路径和合法第三方/生成物排除理由。
- [x] 9.3 更新 `README.md`、新增 `doc/DEMAND_DRIVEN_FUNCTION_ANALYSIS.md`，说明 R3 架构、显式 CLI、协议、预算、缓存、frontier、eager 兼容、语言/编译器边界和“非安全证明”。
- [x] 9.4 更新 `doc/IMPLEMENTATION_ROADMAP.md` 的 R3 状态和后续依赖，并新增 `doc/DEMAND_DRIVEN_FUNCTION_ANALYSIS_VALIDATION.md`，记录精确离线命令、环境/hash、测试、覆盖、四语言等价、R2/TinyCThread、缓存、规模与资源证据；未通过前不得写成已完成。
- [x] 9.5 在锁定开发容器中以新输出目录执行全量 quality/integration、eager/lazy、R2 四语言、TinyCThread、不可达不物化、cold/warm、失败/预算和稀疏规模 required gates，确认运行期间无 configure/build/link、目标执行、网络或 SSH。
- [x] 9.6 运行文档链接/格式、schema/fixture/acceptance 一致性、`git diff --check` 和 `openspec validate add-demand-driven-function-analysis --type change --strict --no-interactive`；只有全部 required gate 通过并在 acceptance 留证后，才将任务标记完成并提示同步/归档。
