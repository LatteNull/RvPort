## Context

R1 `RootDrivenAnalysisPlan v1` 和 R1.1 `ThreadEntryRootOverlay v1` 已经给出函数、上下文、TU 与消费者维度的分析需求，R2 也只在该可达域内构造并发访问候选。然而当前深度事实仍是 eager 产生的：P1 `facts.cpp::extract` 遍历模块内全部函数体，P2 local worker 为全部已定义函数构造 DT/BasicAA/MemorySSA，P3 local worker 为全部函数构造 DT/PDT/LoopInfo，Python 编排还会在不同分析层重复启动 worker 和解析同一 BC。因此现状是“输出按 root 过滤”，不是“计算按 demand 发生”。

LLVM 21 已提供 `getLazyBitcodeModule` 和 `GlobalValue::materialize`，可在模块级符号信息可见时延迟函数体物化。现有身份规则以 artifact 与 symbol 组成函数 ID，并以函数内 block/instruction 原始顺序组成局部 ID；这允许在单个函数被物化后生成与 eager 路径相同的身份，但前提是不能先做 IR 变换、不能按调度顺序重新编号，也不能用 shard 顺序参与 semantic digest。

R3 横跨 LLVM C++ worker、Python 编排、缓存、schema、CLI、质量与文档。其核心约束是加法式接入：`ModuleFacts v2`、`EffectSummary v1`、`ThreadContextGraph v1`、`ExecutionRoot v1`、`ThreadEntry v1` 与 `ConcurrentAccessCandidateGraph v1` 的协议和报告语义必须保持不变。部分函数事实只能存在于独立 R3 sidecar；旧消费者通过只读适配器看到语义等价的完整输入，不能看到伪造的“部分 ModuleFacts”。

## Goals / Non-Goals

**Goals:**

- 建立只读取模块级必要信息、不会预先物化全部函数体的 `LLVMModuleIndexFacts v1`。
- 将 R1/R1.1 root 与精确 direct-call/callback 扩展转化为有界、单调、可解释的 function/context demand graph。
- 使用 LLVM 21 lazy bitcode module 按需求物化函数体，并分别输出完整的 semantic/effect/thread function shard。
- 按 artifact、分析层、函数和上下文确定性批处理，单批 BC 只解析一次，并允许受限并行与单 worker 失败隔离。
- 保持 eager CLI 与 P1–R2 产物不变，通过显式 R3 CLI 和只读适配器验证 eager/lazy 规范化语义等价。
- 对递归、未知调用、AST-only、依赖失败、crash、timeout 和预算耗尽形成非空 frontier，并提供双语、可追溯的完整性与资源报告。
- 同时支持 GCC/Clang 的 C11、C17、C++17、C++20，离线回归 R2 四语言 truth 和 TinyCThread。

**Non-Goals:**

- 不修改或替换 P1 `ModuleFacts v2`、P2 `EffectSummary v1`、P3 `ThreadContextGraph v1`、R1/R1.1/R2 协议及其既有 eager CLI。
- 不把 AST 解析改为按函数懒解析；AST 源事实仍是独立 TU 级事实层。
- 不在未知需求出现时回退为 all-defined、全 BC load/store 扫描或全模块深度分析。
- 不实现 A6 fence/RMW/CAS release sequence、通用 points-to、通用 data-race/HB、风险规则修改、持久 LLVM daemon、B1 CMake scope 导入或 B2 容器整合。
- 不支持 Windows、MSVC、clang-cl；不执行 configure、build、link、目标程序、网络或 SSH 操作。

## Decisions

### 1. 以独立 R3 sidecar 表达部分计算

R3 新增以下 v1 协议：

- `DemandDrivenAnalysisRequest`：显式 scope、R1 plan/R1.1 overlay 引用、请求层、策略、预算和缓存选项。
- `LLVMModuleIndexFacts`：artifact、完整 BC digest、target、`DataLayout`、profile/ABI、symbol、definition/declaration、linkage 和必要 `SourceIRBinding` 引用。
- `FunctionSemanticFacts`、`FunctionEffectFacts`、`FunctionThreadFacts`：一个完整 function/context/layer 的 shard，含原始身份、依赖、完整性和证据引用。
- `AnalysisDemandGraph`：seed、扩展边、状态、frontier 与预算消耗。
- `WorkerExecutionManifest`：确定性 batch、worker attempt、parse/materialize、资源和失败记录。
- `DemandDrivenAnalysisReport`：双语诊断、计数、覆盖、完整性、缓存与资源指标。

只读适配器只在所需 shard 全部完成且引用闭合时，为既有 P2/P3/R2 消费者构造内存中的兼容视图。它不得写出带旧 schema 名称的部分 artifact，也不得把 `partial` 或 `failed` shard 变成空函数效果。

选择该方案而不是升级 P1/P2/P3 schema，是因为旧协议表示各自既定分析分母；把 demand 子集塞入旧 artifact 会让缺失函数和无事实无法区分，并破坏已归档缓存与报告含义。

### 2. 全局索引与函数体事实严格分层

每个 BC artifact 先以 LLVM 21 lazy bitcode reader 打开。索引阶段允许读取模块标识、target triple、`DataLayout`、全局值名称和属性、declaration/definition、linkage/visibility/COMDAT 及 profile/ABI/source binding 所需元数据，但不得遍历 basic block、instruction、load/store/call，亦不得构造 DT、AA、MemorySSA、PDT 或 LoopInfo。

`LLVMModuleIndexFacts` 记录 `body_materialized=false` 的可验证计数与索引来源。无法在不物化函数体的情况下取得的信息不得偷偷加入索引；应推迟到对应 function shard 或形成缺失证据。

替代方案“先生成完整 ModuleFacts 再过滤”实现简单，但不能减少计算和内存，直接违背 R3 目标，因此拒绝。

### 3. 稳定身份以原始模块顺序为准

函数身份继续使用既有 artifact + symbol 规则；参数 ID 继续使用 `:arg:<argNo>`；函数体物化后按照原始 basic block 与 instruction 顺序生成 `:bN:iN`。R3 将抽取可复用的 function-local identity helper，并用 eager/lazy 对照测试锁定一致性。

禁止在编号前运行会插入、删除或重排 IR 的 pass，也禁止把 batch 序号、worker ID、调度顺序、cache hit 或 wall time 放入 semantic identity/digest。匿名 global、alias/ifunc、local linkage 和跨 TU 同名实体仍遵守既有 artifact/linkage/ABI 规则。

替代方案“为 lazy 路径设计新 ID”会迫使 P2/P3/R2 全部迁移并破坏证据引用，因此拒绝。

### 4. 需求图采用有界单调 worklist

seed 来自 R1 plan 与 R1.1 overlay 中已验证的 `main`、显式入口、`pthread_create`、`thrd_create`、`std::thread`、`std::jthread` 和显式 async root。每个 demand key 至少包含 artifact、function identity、analysis layer、context identity 和策略版本；状态按 `indexed -> demanded -> scheduled -> materialized -> completed|partial|failed` 单调前进。

函数 shard 中发现的精确 direct-call 或已验证 callback 可新增 callee/context demand，并保存触发它的 callsite 与证据边。重复 demand 合并原因而不重复计算。递归和 SCC 通过稳定 SCC identity、迭代轮次与上下文合并预算收敛；预算内不能闭合时产生 `recursion-budget` frontier，而不是扩大到模块全部定义。

间接调用、歧义 callback、默认/组合 async policy、开放 scope 和缺失定义只生成带依赖切片的 frontier。只有精确绑定才能扩展 demand。

### 5. 同一 batch 内复用一次 lazy module parse

调度器先按 artifact 分组，再按分析层、函数和 context 的稳定 key 排序，切成受预算限制的 batch。一个 batch worker 打开一次 lazy module，在同一个 `LLVMContext`/`Module` 内依次 materialize 被调度函数并运行对应分析；同一函数被多个层需要时允许在单批共享已物化 body 和只读基础结构，但各层输出仍是独立 shard。

并行边界是 artifact batch；同一个 `Module` 不跨线程共享可变 LLVM 对象。最大 worker、batch functions、materialized instructions、分析查询、CPU、wall、RSS 与输出字节均有显式预算。确定性只约束语义产物和 manifest 的规范化顺序，不要求 wall/CPU 数值相同。

相比“每个 function/context 启一个进程”，该设计减少重复 BC parse；相比持久 daemon，它保持故障边界、离线可复现和首版实现复杂度可控。

### 6. 完整 shard 才进入缓存

首版缓存 key 包含完整 BC digest、schema/extractor/策略版本、profile、target、`DataLayout`、artifact/function identity、analysis layer、context identity 与所有影响语义/完整性的预算。缓存 value 必须是引用闭合且状态为 `completed` 的单 function/context/layer shard；`partial`、`failed`、crash、timeout 和未完成 SCC 不缓存。

whole-BC digest 是保守失效边界：即使目标函数文本未变，其他定义、module flags 或链接属性变化也会失效。这样牺牲部分命中率以避免首版跨模块依赖漏失。cache hit、调度次序、attempt ID 与资源时间只进入 operational manifest，不进入 semantic digest。

cold/warm 运行必须产生相同规范化语义；损坏、版本不符或引用不闭合的缓存项被拒绝并重算，不能降级为“无事实”。

### 7. 失败和未知按候选依赖切片传播

每个 demand node 记录依赖它的 root、callsite、consumer 和候选切片。worker crash、timeout、解析失败、materialize 失败、分析异常和预算耗尽只使相关节点/后继为 `partial|failed`，其他独立 artifact/batch 继续。报告必须生成至少一个具体 frontier item，包含 `reason/reason_en`、受影响 root/function/context/layer、缺失证据、attempt 和可恢复性。

AST-only TU 可以贡献独立 source facts 和 source candidate，但没有 BC function shard；其 demand 为 `partial` 并形成 `ast-only-no-runtime-facts` frontier。开放 scope 或未知间接调用不得触发全局扫描。任一候选相关 root 不完整时，既有消费者只能得到 partial/unknown，不能输出完整无风险结论。

### 8. 兼容路径与 CLI 明确分离

现有 eager commands、默认参数、产物位置、退出码及缓存保持不变。新增显式命令（实现阶段确定最终名称，设计基线为 `analyze-demanded-functions`）只接受已有 artifact/scope/R1/R1.1 输入，不调用编译数据库重放或构建工具。

R3 CLI 输出请求、module indexes、function shards、demand graph、worker manifest 和报告；退出码为：`0` 表示请求内 demanded shard 完成，`2` 表示有 partial/unknown/frontier，`1` 表示请求或基础设施失败。它始终保持 `safety=not_evaluated`、`findings=null`，不会因无候选或零 frontier 宣称程序安全。

### 9. 等价验收比较规范化语义而非字节布局

同一闭合输入上，eager 与 lazy 路径分别生成 P2/P3 兼容视图并运行 R2。比较时规范化数组排序、manifest/资源字段、cache 信息和物理输出路径，但不得忽略函数/指令 identity、对象、effect、thread、MHP、保护、候选、排除、frontier 或 completeness。不可达函数专门带有可观测 trap fixture，断言其函数体没有 materialize 且没有深度 shard。

固定稀疏可达规模集分别记录 indexed、demanded、scheduled、materialized、completed、partial、failed、cache-hit、module parse、CPU、wall、peak RSS 和输出字节。性能数据用于量化 R3 是否降低工作量，不作为安全正确性 oracle；R2 四语言 truth 与 TinyCThread 仍是独立回归门禁。

### 10. 文档按产品边界分工

- `README.md`：新增 R3 显式入口、产物和“非安全证明”提示。
- `doc/DEMAND_DRIVEN_FUNCTION_ANALYSIS.md`：架构、协议、CLI、预算、缓存、frontier 与 eager 兼容说明。
- `doc/DEMAND_DRIVEN_FUNCTION_ANALYSIS_VALIDATION.md`：实际命令、版本、测试/覆盖率、等价矩阵、四语言/TinyCThread 回归和资源统计。
- `doc/IMPLEMENTATION_ROADMAP.md`：实施前标记 R3 已创建/实施中，完成 required gate、同步、归档后再更新为完成；不得在 proposal 阶段提前声称已实现。

## Risks / Trade-offs

- [LLVM lazy reader 的某些查询可能隐式物化函数体] → 在 worker 中对每个阶段记录 materialized function/instruction 计数，并用不可达函数 fixture 断言索引阶段为零；出现隐式物化时收窄查询或形成 unsupported，而不是接受全量物化。
- [function-local identity 与 eager 路径漂移] → 抽取共享 identity helper，在 O0/O1、无 debug、匿名值、invoke/phi 等 fixture 上逐 ID 比较；任何漂移阻断兼容适配。
- [按 context 拆分导致 shard 数爆炸] → 使用稳定 context key、等价上下文合并、每函数/每 root/全局预算和非空 frontier；不得通过静默丢 context 控制规模。
- [whole-BC digest 降低增量缓存命中率] → 首版优先正确失效；记录失效原因与命中率，为后续依赖摘要型 key 提供数据，但本 change 不提前放宽边界。
- [受限并行带来非确定输出] → 所有输入和输出按稳定 key 规范化，semantic digest 排除调度与资源字段；多 worker/单 worker 必须语义等价。
- [只读适配器意外改变旧协议含义] → 对同一闭合 fixture 比较 eager 和 lazy 适配后的 P2/P3/R2 规范化语义，并保持旧 eager CLI 全量回归。
- [局部失败被误解为无访问] → 只有 completed shard 可消费/缓存；partial/failed 必须传播到关联 root/candidate frontier，质量测试覆盖 crash、timeout、损坏缓存和依赖缺失。
- [R3 资源指标受机器噪声影响] → 以物化数量、parse 次数和输出大小作为确定性主指标；CPU/wall/RSS 记录环境与多次样本，不以单次时间硬编码安全结论。

## Migration Plan

1. 先新增 schema、协议校验、module index 与共享 function-local identity helper，不改变任何 eager 入口。
2. 新增 function semantic/effect/thread shard worker，并在测试夹具中建立 eager/lazy identity 与语义等价。
3. 新增 demand graph、scheduler、worker manifest、失败隔离与缓存；保持功能开关和显式 R3 CLI，默认路径不切换。
4. 接入 R1/R1.1 seed 与精确 demand 扩展，再通过只读适配器回归 P2/P3/R2。
5. 完成四语言、TinyCThread、cold/warm、稀疏规模和 90% 覆盖率 required gate 后，才更新路线图完成状态并允许同步/归档。

回滚时删除或禁用 R3 显式入口及独立 sidecar 即可；既有 eager CLI、schema、缓存与产物没有迁移依赖，不需要重写用户数据。

## Open Questions

- 最终 CLI 名称可在实现时按现有命令命名规范确认，但必须保持“显式 opt-in、旧 eager 不变”的契约。
- 固定稀疏可达规模集的函数数量与资源基线需在锁定开发容器中测量后写入 acceptance；proposal 不预设未经实测的绝对性能阈值。
