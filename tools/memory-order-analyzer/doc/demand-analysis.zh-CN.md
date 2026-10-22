# 执行入口与按需分析

[English](demand-analysis.md) | 简体中文

本页按语义层次组织仍使用的协议、CLI、预算和限制。以 [统一项目入口](UNIFIED_PROJECT_ANALYSIS.zh-CN.md) 为产品调用入口；各分层 CLI 用于开发排查，不能把候选或局部证明解释为全程序安全。示例命令仅在 Docker 开发容器内执行。

- [ExecutionRoot 驱动分析架构](#doc-execution-root-driven-analysis)
- [R2 并发访问候选图](#doc-concurrent-access-candidate-graph)
- [R3 按需函数分析](#doc-demand-driven-function-analysis)

<a id="doc-execution-root-driven-analysis"></a>

## ExecutionRoot 驱动分析架构

### 1. 目标与边界

R1 将分析入口从“遍历 scope 中全部 load/store 后反推线程关系”调整为“全局轻量索引 + ExecutionRoot 驱动深度分析”。它不删除 P1–P4、A1–A5 的事实或报告，也不改变任何既有风险规则：R1 只发现线程创建点和执行根，沿已经证明的直接调用边形成有界可达域，并为 P2/P3 生成受控 root 请求。

R1 固定 `safety=not_evaluated`、`findings=null`。零候选只表示显式 scope 中没有发现候选，不等于无线程、无并发或安全。后续 `expand-thread-entry-discovery` 以独立 sidecar 扩大入口识别并只读叠加 root，不改变本协议。R2 的 `ConcurrentAccessCandidateGraph`、R3 的按函数懒提取、通用 data-race、fence、RMW/CAS 和通用 happens-before 均不在 R1 中。

编译器范围为 GCC/Clang，语言范围为 C11、C17、C++17、C++20。C 的直接 pthread 路径不读取 `CppThreadLocalFacts`，不依赖 C++ AST、标准库类型或 wrapper profile。Windows、MSVC 和 clang-cl 明确排除。

### 2. 总体数据流

```text
可选 compile_commands.json（仅 AST profile）+ 外部 BC bundle + 显式 scope
              │
              ├── P1 ModuleFacts v2 ───────────────┐
              ├── A1 AST / SourceIRBinding ────────┤ 全局轻量证据视图
              ├── P3 ThreadLocalFacts ─────────────┤
              ├── A3 CppThreadLocalFacts ──────────┤
              └── P2 EffectSummary adoption ───────┘
                                      │
                AST 候选 ∪ BC 候选；证明按精确交集采纳
                                      │
                         ThreadCreationSiteIndex
                                      │
               显式入口/main/导出/框架/pthread/std::thread
                                      │
                            ExecutionRootIndex
                                      │
                精确直接调用、已采纳 wrapper 有界扩展
                                      │
                         RootDrivenAnalysisPlan
                         ├── P2 root requests
                         ├── P3 root requests
                         └── A3 lifecycle overlays
                                      │
                         RootDrivenAnalysisReport
```

全局索引仍会轻量读取 scope 内全部已声明事实，以免在线程入口发现前遗漏调用点；深度分析需求只由 ExecutionRoot 可达域产生。R1 没有宣称 P1 已按函数懒提取。

### 3. 字段来源审计

| R1 需求 | 既有来源 | 采用规则 | 是否新增 worker 字段 |
| --- | --- | --- | --- |
| 物理 TU、语言和 profile | A1 request、R1 member | 请求显式声明，C/C++ profile 分开 | 否 |
| 函数定义、linkage、局部 direct call | P1 `ModuleFacts.functions/calls` | 只采纳 scope 内同 artifact 精确定义 | 否 |
| 源码 `pthread_create` 与 callback | A1 `SourceSemanticFacts.relations` | `pthread_create` 与同 call expression 的 `callback` 配对 | 否 |
| 源调用点/实体到 LLVM | A1 `SourceIRBinding.expression_bindings/entity_bindings` | 只采纳 `resolution=exact` 且唯一 target | 否 |
| BC 线程调用点、ABI、callback SSA 候选 | P3 `ThreadLocalFacts.calls` | direct、P3 eligible、唯一 callback target 才是 `ir-exact` | 否 |
| `std::thread` callable 与 wrapper | A3 `CppThreadLocalFacts.callables/operations` | exact callable + 成功 construct + `construct-attempt` + 精确 SourceIRBinding | 否 |
| 跨 TU direct call | A1 精确调用/实体 binding；P2 `EffectSummary.adoptions` | 只接受精确 A1 绑定或 P2 `unique-definition`/`odr-body-under-contract` | 否 |
| 已有深度观察 | P2 summary、P3 local/graph | 仅作 plan/observed 对账，不改变原语义 | 否 |

结论：P1/A1/P2/P3/A3 已覆盖 R1 当时所需字段，因此 R1 没有增加 LLVM/Clang worker 或修改既有产物。后续线程入口 change 为更精确的 canonical type、constructor、C11 `thrd_create` 和 C++ broker 证据增加新事实，但仍通过独立 `ThreadEntry* v1` 产物消费，不回写 R1。

#### 4.1 线程入口发现 overlay

R1 原始索引只覆盖直接 pthread 和 A3 已验证的 `std::thread`。`expand-thread-entry-discovery` 将入口识别细化为独立的 `ThreadEntryLocalFacts`、`ThreadEntrySiteIndex`、`ThreadEntryRootOverlay` 和 `ThreadEntryDiscoveryReport`：

- AST 侧按 canonical semantic type、canonical record、实际选中 constructor、声明来源与标准库 profile 识别入口，不使用源码拼写或同名类型猜测；
- BC 侧验证 C API callback SSA，或从 SourceIRBinding 对齐的 C++ 源调用沿确定 wrapper 找到精确 runtime broker；
- 两侧候选取并集保留召回率，证据对齐才提升为 `dual-exact`；C 的有限 `ir-exact` 与 C++ 必须双源采用规则保持分离；
- default/move/factory-return、deferred async、conditional async、unsupported framework 和证据失败保留明确 disposition/frontier；
- overlay 只读引用 R1 base root/plan，按 `adopted-from` 去重并新增需求，base digest 与报告不变。

详见 [线程入口发现](thread-analysis.zh-CN.md#doc-thread-entry-discovery)。识别出精确入口只说明后续分析起点可信，不会直接建立 MHP、synchronizes-with、happens-before 或安全结论。

### 4. 线程创建点对齐

AST 与 BC 分别发现候选，初始集合取并集以保留召回率；精确采用则要求证据交集。规范化分类为：

- `dual-exact`：源码调用点和 callback 经 A1 精确绑定到同一个 P3 调用点与 callback，或 A3 已同时验证 AST callable 与 ABI/IR wrapper。
- `ir-exact`：P3 已证明直接调用、ABI 合格且 callback SSA 候选唯一，但缺少匹配 AST 候选。
- `source-candidate`：只有 AST 候选；它可以保留源码实体和控制证据，但不能单独建立运行时线程根。
- `ambiguous`：多 callback、多绑定或 AST/IR target 冲突。
- `unsupported`：间接调用、ABI/profile/wrapper 不支持。
- `failed`：相关证据层失败且不能形成候选。

只有 `dual-exact` 与受支持的 `ir-exact` 形成正式线程 ExecutionRoot。不得仅凭函数名、类型名、相似 wrapper 或 AST-only callback 建立线程实例。相同 callback 在不同创建点启动两次时共享 `thread_context_key`，但必须保留不同 `thread_instance_key`。

### 5. ExecutionRoot 与可达域

ExecutionRoot 来源包括：

1. 请求中显式 `program` 入口；
2. 显式启用后，scope 内唯一且有定义的 `main`；
3. 请求显式声明的 `exported` 库入口；
4. `dual-exact`/`ir-exact` 的直接 `pthread_create` callback；
5. A3 验证的 `std::thread` callable；
6. 用户显式声明且绑定源实体的 `framework` 入口。

导出入口和框架入口不通过 linkage、名字或类型自动猜测。根可达扩展只使用 P1 同 artifact 精确 direct call、A1 精确跨 TU 绑定和 P2 已采纳 adoption。间接调用、target 缺失、开放 scope、递归/预算截断形成非空 frontier；不会回退到“把所有已定义函数都当 root”。

`RootDrivenAnalysisPlan.demands` 以 function + context + physical TU 形成稳定需求身份；P2/P3 请求按 root 生成，A3 标准库线程另外登记 lifecycle overlay。`reconciliation` 同时记录计划函数、已索引函数、已有 P2 深度观察和 P3 artifact 观察。缺少已有深度观察并不被伪装成已分析，后续执行器可直接消费这些受控请求。

### 6. 完整性与资源预算

报告分别计算：

- `root`：正式 root 的计划数、完整数和比例；
- `reachable`：可达 function/context 的计划数、完整定义数和比例；
- `candidate_relevant`：与 root 可达切片相关的线程创建候选分母及精确数。

不相关 TU 的候选缺口不会污染当前 root 的候选相关完整性；精确线程创建点自身始终相关。开放 scope、相关 source-only/ambiguous/unsupported 候选、定义缺失和预算耗尽使计划为 `partial`，退出码为 2。完整规划退出 0；请求无效、证据全部不可用或编排失败退出 1。R1 不使用风险退出码 3。

预算覆盖 TU、源码/IR/binding 候选、roots、functions、contexts、call edges、wrapper depth、SCC 迭代、frontier、诊断和总请求时间/输出大小。预算命中必须产生双语 frontier，不能截断为空后返回 complete。

### 7. 协议、缓存和 CLI

新增协议文件 `protocols/execution-root-analysis-protocol.json` 和 schema `schemas/execution_root_analysis.json`，产物均为 v1：

- `ExecutionRootDiscoveryRequest`
- `ThreadCreationSiteIndex`
- `ExecutionRootIndex`
- `RootDrivenAnalysisPlan`
- `RootDrivenAnalysisReport`

请求只读取 `artifact_store` 下显式相对路径、kind、id 和 digest 匹配的 evidence；绝对路径、`..` 逃逸、内容变化、profile 混用或未支持 kind 都拒绝。缓存命名空间为 `execution-root-driven-analysis-v1`，key 包含请求、policy 和全部依赖 digest；failed/transient 结果不缓存。

```bash
python3 -m memory_order_analyzer plan-execution-roots \
  --request /input/execution-root-request.json \
  --artifact-store /artifacts \
  --output /output/root-plan \
  --source-worker /output/build/memory-order-source-worker \
  --ir-worker /output/build/moa-worker
```

R1 当前复用已生成证据，所以 worker 参数只为 CLI 稳定性和后续受控执行预留，不会隐式重新编译或修改旧产物。输出目录必须全新，布局为：

```text
request.json
thread-creation-sites/index.json
execution-roots/index.json
plans/<semantic-digest>.json
effects/requests/<request-id>.json
threads/requests/<request-id>.json
report.json
```

### 8. 与其他层的关系

- 线程入口发现：已通过独立 `ThreadEntry* v1` overlay 扩展 C11/C17/C++17/C++20 入口事实、类型归一化与 R1 组合，不改变 R1 base artifact。
- R2：在 `RootDrivenAnalysisPlan + ThreadEntryRootOverlay` 的需求切片上构建 `ConcurrentAccessCandidateGraph`，仍不等于通用 data-race/HB。
- R3：把 P1/P2/P3 局部事实提取改为真正按函数/上下文懒执行，并用 R1 计划约束 worker 调度。
- A6：fence、RMW/CAS 与受限 release sequence，独立于 R1 架构切换。

R2/R3 必须通过新的 OpenSpec change 授权，不能在 R1 中偷偷改变 P4 风险语义。

<a id="doc-concurrent-access-candidate-graph"></a>

## R2 并发访问候选图

### 1. 目标与架构位置

R2 把 R1/R1.1 的执行根需求、P2 内存效果、P3/A3 生命周期、A4 mutex 证明和 A5 对象 provenance 投影到统一的动态访问空间，再形成可审计的并发访问候选。

```text
RootDrivenAnalysisPlan + ThreadEntryRootOverlay
                    │ demanded root/context/function/TU
                    ▼
      ExecutionInstanceBindingOverlay
      ├─ ExecutionRoot
      ├─ ThreadContext（可复用 callback）
      ├─ ThreadInstance（创建点级动态实例）
      └─ MHP: parallel-possible / not-parallel / unknown
                    │
EffectSummary + ThreadContextGraph + BoundedObjectProvenanceGraph
                    ▼
       ConcurrentAccessProjectionFacts
                    │ AccessInstance
                    ▼
      有限对象桶 + overlap/MHP 配对
                    │
CppRaiiSynchronizationGraph ──► AccessProtectionOverlay
                    │
                    ▼
       ConcurrentAccessCandidateGraph
                    ▼
       ConcurrentAccessCandidateReport
```

该流程仍是“全局轻量索引 + ExecutionRoot 驱动深度分析”：只实例化 demanded slice，不回退到全 BC load/store 扫描。AST 与 BC 在上游分别保留候选，R2 只消费已经版本化、内容寻址并通过 profile/lineage 校验的事实。

### 2. 上游字段审计

| 上游能力 | 直接复用 | R2 独立补充 | 禁止推断 |
| --- | --- | --- | --- |
| R1 `RootDrivenAnalysisPlan v1` | demanded root/context/function/TU、可达完整性 | base/overlay demand 分母 | 不从 observed-but-not-demanded 或 all-defined 扩域 |
| R1.1 `ThreadEntryRootOverlay v1` | adopted root、物理创建点、模型、callable、cardinality、conditional frontier | scope 级 instance binding | 不按函数名、类型名或 broker 名采用入口 |
| P2 `EffectSummary v1` | effect、invocation、guard、range、atomic/order | 动态 `AccessInstance` | `EffectSummary.order` 不是 SW/HB |
| P3 `ThreadContextGraph v1` | pthread instance、create/join、同 root MHP | 多 root execution family 与统一 MHP disposition | 缺少关系不等于 `not-parallel`；reads-from candidate 不是同步证明 |
| A3 生命周期 | `std::thread` callback/object/move/join/detach | 与 R1 root/site 的实例对齐 | 不完整 jthread/async 生命周期不得猜测 join/wait |
| A4 RAII 同步 | exact mutex、owner、held-region、受限 proof | access-level protection overlay | 类型名、词法作用域或函数内出现 lock 不能保护访问 |
| A5 provenance | must/may/unknown、storage/path/range/union/lifetime | overlap disposition、bucket 和 pair evidence | 字段声明、字符串 key、AST-only path 不能证明 runtime alias/noalias |

R2 不修改 P1–P4、A1–A5、R1 或 R1.1 的 schema、缓存或报告。没有额外 LLVM 局部事实时，`ConcurrentAccessProjectionFacts v1` 由既有事实适配生成，不需要修改 C++ worker。

### 3. 协议与身份层

协议文件为 `protocols/concurrent-access-candidate-protocol.json`，schema 为 `schemas/concurrent_access_candidate.json`，固定 policy/cache namespace `concurrent-access-candidate-graph-v1`。六类产物为：

- `ConcurrentAccessCandidateRequest v1`：显式 scope、target、ABI、DataLayout、TU profile、source/BC/binding lineage，以及每个上游 artifact 的 kind/id/digest/schema/producer/path。
- `ConcurrentAccessProjectionFacts v1`：demanded effect 的动态访问实例，以及 observed-but-not-demanded 审计计数。
- `ExecutionInstanceBindingOverlay v1`：分离 root、context、instance、invocation 和 MHP disposition。
- `AccessProtectionOverlay v1`：把具体访问对绑定到闭合的 A4 held-region 和 exact mutex proof。
- `ConcurrentAccessCandidateGraph v1`：candidate、exclusion、atomic handoff、frontier 和分母。
- `ConcurrentAccessCandidateReport v1`：双语诊断、四语言计数、退出码和固定非安全结论字段。

`AccessInstance` 身份包含 scope/profile、root、context、invocation、原始 source/effect 证据、动态 `ThreadInstance`、operation、atomicity、guard、对象候选域、半开字节范围和 cardinality。同一 callback context 被两个创建点采用时生成两个实例；同一动态访问经 AST/IR/P2/P3 重复观察时合并证据。对象或范围出现相互矛盾的精确信息时不强行合并，而生成 `source-ir-access-conflict` frontier。

### 4. Root、线程实例与 MHP

base/overlay root 只在物理创建点、API model 和 callback identity 一致时去重，并记录 `adopted_from`。context 允许复用，instance 必须保留父实例、创建点、guard、模型和 cardinality。

- P3 pthread 和 A3 `std::thread` 优先采用其生命周期实例与 MHP 证明。
- R1.1 exact `pthread_create`、`thrd_create`、`std::thread`、`std::jthread` 和显式 `std::launch::async` 在唯一父执行实例可确定时形成受限 `parallel-possible` 区间。
- `launch::deferred` 在 R1.1 已排除；default/combined async policy 不形成正式 root，只进入 conditional frontier。
- `single` 实例不与自身并行；`merged`/`repeated` 抽象实例保留 self-concurrency。
- 不同 root 缺少生命周期关系时为 `unknown`，绝不默认为 `not-parallel`。

### 5. 对象、范围与候选规则

A5 对象域保留 storage instance、subobject path、union group、lifetime、address space、guard 和半开字节范围。比较结果只有 `must-overlap`、`may-overlap`、`must-disjoint` 和 `unknown`。union 的同组成员不能因字段不同而判为 disjoint；同名字段若基 storage instance 不同则保持不同对象。

配对先按 storage/address-space 对象候选建立有限倒排桶；未知对象不会与所有访问做全局笛卡尔积，而产生聚合 frontier。正式 candidate 同时要求：MHP 为 `parallel-possible`、对象为 must/may overlap，且至少一侧为 write、RMW 或 CAS。`same-single-instance`、`proven-not-parallel`、read/read 和 `must-disjoint` 形成显式 exclusion。pair identity 与左右顺序无关，多桶观察会合并 provenance/guard/evidence。

### 6. 保护、原子与证明边界

只有双方具体访问、动态实例、A4 owner、成功 acquire/release 或 RAII destruction、闭合 held-region、同一 exact 普通非 robust/recursive mutex、线程绑定、guard 和完整依赖同时成立，候选才标记为 `protected-within-bounded-model`。该标记只针对这一访问对，不表示函数或程序安全。

普通/atomic、atomic/atomic、RMW 和 CAS 冲突对继续保留。atomic pair 进入 `atomic_handoff`；RMW/CAS/failure-order/release-sequence/fence 需要 A6，生成 `advanced-atomic-semantics-unsupported` frontier。R2 不把 atomicity、P2 order 或 P3 reads-from candidate 转换成 synchronizes-with/happens-before。

### 7. 完整性、预算和缓存

分母分别记录 root、context、TU、effect、access、instance、MHP、object binding、bucket、pair 和 protection query 的 planned/completed/partial/failed。开放 scope、AST-only、IR-only、缺失 effect、source/IR conflict、unknown object/MHP/synchronization、profile/ABI/lineage 冲突及预算耗尽均形成非空 frontier。

预算覆盖 TU、root、context、effect、access、instance、object candidate、bucket、alias comparison、MHP query、candidate/exclusion/protection、frontier、递归/SCC、诊断、worker/request time 和输出字节。输出预算不足时保留强制报告信封并返回 partial，不升级为安全结论。

缓存使用独立 envelope，绑定 namespace、stage、完整 cache key 和 artifact。key 覆盖请求、预算及全部依赖 digest；命中时重新校验 envelope、schema、semantic digest 和当前显式输入闭包。partial、failed、timeout 和损坏条目不能作为成功命中。报告 semantic digest 排除 cache hit/miss 观测，因此 cold/warm 语义一致。

### 8. CLI 与输出

```bash
python3 -m memory_order_analyzer.cli build-concurrent-access-candidates \
  --request /path/to/request.json \
  --artifact-store /path/to/artifacts \
  --output /path/to/new-output
```

CLI 只读取 request 显式引用的相对路径，不扫描“最新”产物，不 configure/build/link、运行目标程序、访问网络或 SSH，并拒绝已有输出目录。输出固定包含 `request.json`、`projection/<semantic-digest>.json`、`execution-instance-binding.json`、`access-protection.json`、`candidate-graph.json` 和 `report.json`。

退出码为 `0`（complete）、`2`（partial/unknown/unsupported/frontier）和 `1`（request invalid 或全部不可用），不使用 P4 风险码 `3`。报告始终为 `safety=not_evaluated`、`findings=null`；所有面向用户的 detail、limitation、suggestion 同时提供中文和英文字段。

### 9. 支持矩阵

| 范围 | 首版状态 |
| --- | --- |
| 编译器/平台 | GCC/Clang、Linux 风格 ABI；排除 Windows、MSVC、clang-cl |
| 语言 | C11、C17、C++17、C++20 独立 profile/fixture/truth 分母 |
| 线程入口 | pthread、C11 `thrd_create`、`std::thread`、`std::jthread`、显式 async |
| 生命周期 | P3/A3 已证明关系；deferred 排除；不猜测 future wait 或 jthread 自动 join |
| 对象 | A5 有界 stack/global/argument/receiver/subobject/union/有限指针传播 |
| 保护 | C pthread mutex 与 A4 受限 RAII exact proof |
| 暂不支持 | 通用 data race/HB、线程池/executor、自定义同步、通用 points-to、fence、RMW/CAS release sequence |

### 10. 解读结果

R2 只生成 candidate、exclusion、`protected-within-bounded-model` 和 frontier。`exit 0`、零 candidate、零 frontier、atomic 访问、受限保护、truth exact match 或 90% 覆盖率都不能证明无 data race、happens-before 闭合或程序安全。候选需交给显式版本化的 P4/A6 或后续风险消费者；unsupported/frontier 必须作为 abstention 保留。

<a id="doc-demand-driven-function-analysis"></a>

## R3 按需函数分析

状态：`add-demand-driven-function-analysis` 已实现独立 R3 v1 sidecar；本能力是显式 opt-in，不替换现有 eager 路径，也不产生安全结论。

### 1. 架构位置

```text
RootDrivenAnalysisPlan + ThreadEntryRootOverlay
                    │ function/context/root demand
                    ▼
        AnalysisDemandGraph（有界单调 worklist）
                    │ exact direct-call / verified callback
                    ▼
LLVMModuleIndexFacts ── LLVM 21 lazy bitcode module
  （仅 symbol/linkage/ABI/target/DataLayout；零 body materialization）
                    │ GlobalValue::materialize(demanded function)
                    ▼
 FunctionSemanticFacts / FunctionEffectFacts / FunctionThreadFacts
                    │ completed shard cache + read-only adapters
                    ▼
       P2 effect view / P3 thread view / R2 input view
```

全局阶段只读取模块级身份、声明/定义、linkage、visibility、COMDAT、target、`DataLayout` 与必要源码绑定。它不遍历 basic block/instruction，也不构造 DT、AA、MemorySSA、PDT 或 LoopInfo。深度事实仅在 demand 被调度后提取；不可达函数可以出现在索引中，但不得出现 function shard 或 materialized instruction。

### 2. 独立协议和产物

协议清单位于 `protocols/demand-driven-analysis-protocol.json`，JSON Schema 位于 `schemas/demand_driven_analysis.json`。R3 v1 包含：

- `DemandDrivenAnalysisRequest`：显式 scope、R1/R1.1 引用、TU profile、请求层和全部预算。
- `LLVMModuleIndexFacts`：一个完整 BC artifact 的轻量索引，索引计数必须证明零函数体/指令物化。
- `FunctionSemanticFacts`、`FunctionEffectFacts`、`FunctionThreadFacts`：一个 function/context/layer 的引用闭合 shard。
- `AnalysisDemandGraph`：seed、调用边、consumer、状态、递归/预算和 frontier。
- `WorkerExecutionManifest`：batch、attempt、parse/materialize、CPU/wall/RSS/输出大小及失败隔离。
- `DemandDrivenAnalysisReport`：root/reachable/candidate-relevant 完整性、缓存和资源汇总。

部分 shard 不得伪装为 `ModuleFacts`、`LocalAnalysisFacts`、`ThreadLocalFacts` 或 `EffectSummary`。只读适配器输出 `R3EffectShardView`、`R3EffectSummaryInputView`、`R3ThreadShardView` 和 `R3ConcurrentAccessInputView`；其中 P2-compatible summary 只存在于内存并保留 R3 kind，缺 shard 时必须传播 frontier。

### 3. 显式 CLI

```bash
python3 -m memory_order_analyzer.cli analyze-demanded-functions \
  --request /input/r3-request.json \
  --artifact-store /input/artifact-store \
  --output /output/r3-run \
  --worker /opt/memory-order-analyzer/bin/moa-worker
```

输入必须是已存在并通过 digest/schema/producer 校验的 BC artifact、R1 plan 和 R1.1 overlay。命令不会执行 configure、build、link、目标程序、网络或 SSH。输出目录必须不存在，以免混入旧产物。退出码：`0` 表示请求分母内 shard 完整；`2` 表示 partial/unknown/frontier；`1` 表示请求或基础设施失败。三种状态都固定 `safety=not_evaluated`、`findings=null`。

### 4. Demand、身份和跨 TU 扩展

seed 只来自 R1/R1.1 已验证的 main、显式入口、pthread/thrd、`std::thread`、`std::jthread` 与显式 async root。函数 ID 继续使用 artifact + symbol；参数、basic block 和 instruction 使用既有原始 IR 顺序。R3 和 eager 共享 identity helper，因此调度顺序、worker、cache hit 和资源时间不会改变函数内身份。

完成 shard 中的 exact direct-call 或已验证 callback 才能扩展新 demand。跨 TU 目标必须在显式 scope 内按 linkage/ABI/SourceIRBinding 唯一绑定；间接调用、同名歧义、缺失定义、默认/组合 async policy只形成 frontier，不调度所有定义。递归按稳定节点和有限迭代闭合，超限为 `recursion-budget`。

### 5. Batch、缓存和预算

调度器按 artifact、function、context、layer 的 stable key 排序，并按 `functions_per_batch` 切分。一个 batch 只解析一次 BC；同一个 LLVM Module 不跨 worker 共享。worker crash、timeout、非零退出、非法 JSON、parse/materialize/analysis 失败只污染相关 demand slice，其他 batch 继续。

缓存 key 包含完整 BC digest、schema/extractor/policy、profile、target、`DataLayout`、函数、context、layer 和语义预算。只有 `completed` 且引用闭合的 shard可原子发布；partial、failed、timeout、crash 不缓存。whole-BC digest 是首版保守失效边界。cold/warm 的调度、命中和资源字段不同，但 semantic digest 必须一致。

预算覆盖 TU、root、demand、context、batch、worker、函数体指令、LLVM 查询、SCC/递归、frontier、诊断、CPU/wall、RSS 与输出字节。任何静默截断都不允许；预算耗尽必须定位到 artifact/function/context/layer/attempt，并降级为 partial/frontier。

### 6. 支持边界

- 编译器：GCC/Clang 输入 profile；实际 BC reader 和 worker 锁定 LLVM 21。排除 Windows、MSVC、clang-cl。
- 语言：C11、C17、C++17、C++20 独立 profile。C 路径不加载 C++ AST 或标准库模型。
- AST：仍是独立 TU 级事实层，本层协议 不承诺 Clang AST 按函数懒解析。
- 不实现：A6 fence/RMW/CAS release sequence、通用指针分析、通用 data-race/HB、风险规则修改、持久 LLVM daemon、B1/B2。

R3 的“完整”只表示显式 demand 和支持边界内的函数 shard 已闭合；零 frontier、零 candidate、cold/warm 等价或较少物化都不能证明线程安全、无 data race 或全程序安全。

### 7. 可重复质量入口

```bash
python3 -m memory_order_analyzer.quality --output /output/r3-quality --integration
openspec validate add-demand-driven-function-analysis --type change --strict --no-interactive
```

单元覆盖统计包含全部自有 Python/C++ 可执行代码和未被测试加载的源码；项目整体、实现语言和每个受影响模块行/分支覆盖率均不得低于 90%。
