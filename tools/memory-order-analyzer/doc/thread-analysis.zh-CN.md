# 线程、生命周期与同步

[English](thread-analysis.md) | 简体中文

本页按语义层次组织仍使用的协议、CLI、预算和限制。以 [统一项目入口](UNIFIED_PROJECT_ANALYSIS.zh-CN.md) 为产品调用入口；各分层 CLI 用于开发排查，不能把候选或局部证明解释为全程序安全。示例命令仅在 Docker 开发容器内执行。

- [P3 线程与同步上下文](#doc-thread-and-sync-contexts)
- [C++ `std::thread` 生命周期分析](#doc-cpp-thread-lifecycle)
- [C++ RAII 同步建模](#doc-cpp-raii-synchronization)
- [线程入口发现与 Root Overlay](#doc-thread-entry-discovery)

<a id="doc-thread-and-sync-contexts"></a>

## P3 线程与同步上下文

状态：`model-thread-and-sync-contexts` 已实现、通过最终质量复验、同步主规格并归档。P3 在 P1 `ModuleFacts v2` 和 P2 `EffectSummary v1` 之上增加独立、版本化的线程关系层；不修改 P1/P2 产物语义，也不输出风险结论。

### 1. 能力边界

首版输入限定为 GCC/Clang 编译的用户态 C/C++，要求显式 `ScopeManifest` 和显式分析根。支持直接调用下列 POSIX API：

| API | P3 事件 | 必要证据 | 不满足时 |
| --- | --- | --- | --- |
| `pthread_create` | create-attempt、thread-start | 直接 C ABI、4 个参数、callback metadata 不冲突、回调候选唯一、scope 内定义唯一 | unknown + 双语诊断 |
| `pthread_join` | join-attempt、join-complete | 直接 C ABI、2 个参数、句柄经受限 provenance 唯一到达某个实例 | 只保留 attempt 与 frontier |
| `pthread_mutex_lock` | may-acquire 候选 | 直接 C ABI、单参数、普通静态零初始化指纹 | mutex-state-unknown |
| `pthread_mutex_unlock` | release 候选 | 与 lock 同对象且局部执行顺序证明为 must-before | mutex-state-unknown |

本节 P3 层不支持 `std::thread`/RAII（分别由后文 A3/A4 层处理）、try/timed/robust/recursive mutex、condition variable、semaphore、rwlock、detach/cancel、线程池、自定义同步原语和通用指针分析。它们不会借用相似名称或邻近模型；结果保持 unknown。

### 2. 独立协议与产物

协议文件为 `protocols/thread-analysis-protocol.json`，固定：

- `protocol_version=1`
- `analysis_version=0.1.0`
- `policy_id=thread-sync-contexts-v1`
- `model_id=posix-pthread-v1`
- `llvm_version=21.1.8`

`schemas/threading.json` 定义五种严格产物：

1. `ThreadAnalysisRequest v1`：scope、显式 roots、模型和预算。
2. `ThreadLocalFacts v1`：pthread 候选、callback metadata/目标、handle/mutex provenance、normal/unwind/no-return anchor 输入。
3. `ExecutionOrderFacts v1`：LLVM CFG、DominatorTree、PostDominatorTree、LoopInfo 导出的局部顺序证明。
4. `ThreadContextGraph v1`：上下文、实例、生命周期、绑定效果、调用 anchor、顺序、MHP、mutex/reads-from 候选。
5. `ThreadAnalysisReport v1`：分层完整性、明确分母、依赖、frontier、双语诊断和退出码。

所有 schema 都拒绝未知字段、未来版本和错误 kind。诊断同时提供 `detail`/`detail_en`；存在修复建议时同时提供 `suggestion`/`suggestion_en`。机器判定使用稳定 code，不依赖翻译文本。

### 3. 数据流与 LLVM/自研边界

```text
compile_commands.json + 显式 scope
        │
        ├─ P1 compile-only BC + ModuleFacts v2（保持不变）
        ├─ P2 LocalAnalysisFacts / EffectSummary v1（保持不变）
        │
        └─ P3 LLVM worker
             ├─ ThreadLocalFacts v1
             └─ ExecutionOrderFacts v1
                       │
                       ▼
              自研 ThreadContextGraph
                       │
                       ▼
              ThreadAnalysisReport v1
```

LLVM 负责读取/校验 BC、原始身份、CFG 可达性、支配/后支配、循环和受限局部值形态。自研层负责 scope 内跨 TU 回调绑定、P2 invocation/effect 到线程实例的归属、句柄 token、生命周期、MHP、mutex 状态候选、atomic reads-from 候选、预算、缓存和完整性报告。

回调候选只传播直接函数地址、pointer cast、`select` 和 `phi`，候选域上限为 8。跨 TU 声明只在 closed scope、无外部边界、名称唯一且定义具有受支持 linkage/非 COMDAT 时绑定；否则保留 unknown。

### 4. ThreadContext 与 ThreadInstance

`ThreadContext` 是可复用分析模板，其身份包含 scope、入口、抽象参数、模型和预算，并引用对应 P2 `EffectSummary`。同一入口和参数可以复用模板。

`ThreadInstance` 表示某个根下由父实例和 create callsite 产生的抽象执行实例。两个 callsite 创建同一入口时共享 context，但必须得到两个 instance。循环或递归 create 不能无限展开，会形成 `merged` 实例并产生非空 frontier；merged 代表一个或多个动态线程，不能当作单例。

P2 invocation/effect 在绑定时生成 P3 `ThreadAnchor`/`ThreadEffect`，每个对象同时保留原始 `SourceRef`、P2 identity 和所属 `ThreadInstance`。调用者对象不会因为进入被调函数而被重新归属到错误线程。

### 5. 执行顺序与生命周期

`ExecutionOrderFacts` 是唯一可用于 P3 局部执行顺序组合的来源：

- 同一非重复基本块按指令序产生 must-before。
- CFG 单向可达但证明不足时产生 may-before。
- 支配、后支配且两端非重复时才可提升为跨块 must-before。
- 循环事件标记 repeated；可能跨迭代反转时不得提升为 must-before。
- 同一 invocation 内不可共同执行的 CFG 事件记录 mutually-exclusive。

P2 `EffectSummary.order` 只保留 P2 原始事实语义，P3 不读取它来证明 sequenced-before 或 happens-before。跨调用顺序通过 callsite、function-entry、function-exit、normal-successor anchor 组合；no-return 或缺少正常出口时不串接调用后继。

生命周期包含 root-start、create-attempt、thread-start、thread-exit、join-attempt、join-complete。create/join 的成功条件编码为 guard；返回值未检查时只能表达“可能成功”，不能产生无条件 spawn/join 证明。

### 6. MHP、mutex 与 atomic 候选

MHP 使用规范化无向 ThreadInstance pair，关系为 `may_parallel`、`not_parallel` 或 `unknown`。父线程 create 后继续和两个 worker 的重叠形成 may_parallel 候选；唯一句柄且成功 join 后，只对有局部 must-before 证据的父线程后续端点形成条件化 not_parallel。MHP 不是实际调度、冲突或缺陷证明。

mutex 只采用 worker 生成的 `zero-static:<sha256>` 指纹。hash 输入包含 target triple、DataLayout 和 initializer IR；动态初始化、未知 initializer、对象覆盖、lock/unlock 不平衡或缺少 must-before 都保留 unknown。两个线程各自在同一规范化对象上形成平衡区间时，发布 mutex 同步候选；不会因为“函数里出现过锁”保护全部效果。

P2 atomic read/write/RMW/CAS/fence 会绑定到 ThreadInstance，并保留对象、范围、value、success/failure order、syncscope 和 guard。跨线程同对象的 write/read 仅生成 reads-from candidate；不同对象明确 excluded。release/acquire 同对象、fence、CAS 自旋或未知 release sequence 都不会直接生成确定 synchronizes-with/happens-before。

### 7. CLI

请求示例：

```json
{
  "schema_version": 1,
  "kind": "ThreadAnalysisRequest",
  "analysis_version": "0.1.0",
  "policy_id": "thread-sync-contexts-v1",
  "scope": "scope.json",
  "roots": [{"artifact_key": "<64-hex>", "function_id": "<P1-function-id>", "arguments": []}],
  "model_id": "posix-pthread-v1",
  "budgets": {
    "local_steps": 100000,
    "value_candidates": 8,
    "thread_contexts": 4096,
    "thread_instances": 16384,
    "graph_items": 100000,
    "scc_iterations": 16,
    "worker_seconds": 60,
    "worker_output_bytes": 16777216,
    "request_seconds": 300,
    "request_output_bytes": 67108864
  }
}
```

在开发容器中运行：

```bash
python3 -m memory_order_analyzer model-threads \
  --request /input/thread-request.json \
  --artifact-store /input/artifact-store \
  --output /output/thread-run-new \
  --worker /output/build/moa-worker
```

`--output` 必须是不存在的新目录。命令先在显式 scope 上生成 P3 局部事实，再把用户 roots 与已采用的直接 `pthread_create` callback 目标转换为 P2 `mode=roots` 请求；callback 参数无法形成 SourceRef 时使用 P2 的“空参数即 unbound/unknown”规则，不伪造具体值。P2 内容寻址缓存仍可复用，但不会隐式切换为 `all-defined`。随后生成 P3 sidecar、graph 和 report；全程不执行 `llvm-link`，不原生链接，也不运行被分析程序。

退出码：0 表示所有已计划层完整；2 表示获得部分可用图但存在 unknown/frontier；1 表示请求、输入、worker 或结构性预算失败。任何退出码下 `safety=not_evaluated`、`findings=null`。

### 8. 预算、缓存与完整性

预算耗尽时不得发布悬空边或空结果冒充 complete。局部/图可保留有效子图并标 partial、产生非空 frontier；显式根连最小 context/instance/root-start 都无法表示时请求失败。整体墙钟和输出字节限制在编排层复核。

P3 cache key 包含请求、scope、profile、P1/P2 digest、worker 协议、模型和预算。ThreadContext 模板身份与 ThreadInstance 身份分离；callee-only 摘要变化或模型升级会使图 key 失效。损坏、未来版本或同 key 不同内容的缓存条目明确失败。

报告分别给出 input_integrity、effect_analysis、local_thread_analysis、thread_modeling、synchronization_analysis 和 source_mapping，并为 member/root/context 记录 planned、complete、partial、failed、not_run 和 complete_ratio。零分母使用 null，不伪装成 100%。

### 9. 结论层边界

P3 只提供可审计关系图。它不判定 data race、publication-order risk、C/C++ 全程序安全或目标硬件屏障正确性。缺少确定 HB 不是已证明存在错误；有 mutex/reads-from 候选也不是已证明同步成立。后续 P4 已在独立产物中实现受限的一次性发布规则，见 [一次性发布分析](publication-analysis.zh-CN.md#doc-single-publication-risks)；P3 本身的 `safety=not_evaluated`、`findings=null` 保持不变。

<a id="doc-cpp-thread-lifecycle"></a>

## C++ `std::thread` 生命周期分析

### 1. 能力定位

A3 `model-cpp-thread-lifecycle` 在既有 P1–P4、A1 和 A2 产物之上增加独立的 C++ 线程生命周期 overlay。它不修改 `ModuleFacts v2`、`EffectSummary v1`、`ThreadContextGraph v1`、`PublicationRiskReport v1` 或 A2 报告语义。C11/C17 的直接 `pthread_create`、`pthread_join` 仍由 P3 处理，C TU 不加载 C++ AST 类型或标准库 profile。

A3 支持 GCC/Clang C++17/C++20 输入中经过验证的 `std::thread` 构造、move construction/assignment、`joinable()`、`join()`、`detach()` 和析构，以及自由函数、lambda、非虚成员函数和唯一简单 functor callback。结论始终是生命周期证据，不是互斥、synchronizes-with、happens-before、风险或全程序安全证明。

### 2. 版本化产物

策略标识是 `cpp-thread-lifecycle-v1`，分析版本为 `0.1.0`。新增产物如下：

| 产物 | 作用 |
| --- | --- |
| `CppThreadLifecycleRequest v1` | 固定 scope/root、TU、P1/P3/A1 依赖、标准库 profile 和预算 |
| `CppThreadLibraryProfile v1` | 锁定 vendor/version、ABI、target、DataLayout、头文件与 wrapper digest |
| `CppThreadLocalFacts v1` | 保存独立 callable、对象操作、wrapper 角色和 AST/IR 证据 |
| `CppThreadLifecycleGraph v1` | 保存对象状态、context/instance、转移、start/join/detach/MHP overlay 和 gap |
| `CppThreadLifecycleReport v1` | 汇总完整性、双语诊断、cache hit/miss；固定 `safety=not_evaluated`、`findings=null` |

所有文档执行严格 schema、unknown-field、版本、引用、排序和 digest 校验。A3 cache 使用独立 namespace；协议、依赖、profile/model、工具链或预算类别变化都会改变 key。timeout/crash/failed 结果不得发布为长期语义缓存。

### 3. 证据链与模块边界

分析链是：

1. A1 source worker 识别 `std::thread` 源构造、对象、callable、move、join/detach/joinable 和隐式析构；ProgramEntityIndex 按 linkage、ODR/COMDAT、internal linkage 和系统边界解析实体。
2. P1 ModuleFacts 提供直接 wrapper call、参数/结果值和原始 IR 节点。A3 在 Python sidecar 中按已验证 profile 将调用归约为 `construct-attempt`、`entry-broker`、`join-attempt`、`detach-attempt`、`handle-transfer`。
3. 受限 SSA provenance 只穿过 alloca/load/store/cast/GEP/phi/select。逃逸、未知调用、多根或预算耗尽保持 candidate/unknown。
4. AST callable/entity/object 与 ABI/IR wrapper 求交后形成 `CppThreadLocalFacts`。名称、类型拼写、最近行号、单个 mangled symbol 或底层 `pthread_create` 均不能单独构成 exact。
5. 状态机生成 `ThreadContext` 与调用点特有 `ThreadInstance`。context 可复用；instance 必须绑定构造点、对象/handle lineage、guard 和 cardinality，不能随 cache 串用。
6. P3 adapter 只读取原 `ThreadContextGraph v1`。只有闭合的 worker-exit、join-complete、父线程后继/not-parallel 证据链才能使 A3 join 进入 `joined`；`EffectSummary.order`、源码顺序或 wrapper presence 不足以证明 join。

标准库 broker 内的底层 pthread 只作为 model-owned evidence，不能同时生成用户 pthread 实例。归属不明时保留冲突和 gap，不静默去重。

### 4. callable 与线程对象状态

callable 首版要求 AST 实体唯一、scope 内 definition compatible，并与 IR 绑定基数一致。lambda 保存 call operator；成员函数需要有限 receiver；简单 functor 只接受唯一非虚 `operator()`。重载未消解、虚调用、复杂 `std::bind`、通用函数指针、definition 缺失、对象逃逸或候选超限进入 unknown。

对象状态格包括 `empty`、`construction-pending`、`joinable`、`joined`、`detached`、`moved-from`、`failed`、`terminated-path`、`unknown`：

- 构造只有在 callback、对象、wrapper 和正常成功路径完整时才生成 thread-start；仅看到源构造不创建动态实例。
- move construction 转移同一实例/handle lineage，源变为 moved-from。
- move assignment 覆盖可能 joinable 的目标时进入 terminated-path/unknown，不能假装转移成功。
- `joinable()` 只记录查询和 guard，不生成完成顺序。
- 成功且证明闭合的 join 才生成 join-complete/not-parallel；异常、失败、moved-from 或未知对象保持 gap。
- detach 终止 join 所有权但保持 may-parallel，不生成 join 或 HB。
- joinable 对象析构表示可能 `std::terminate`，不是隐式 join/detach。
- 循环或递归构造使用 repeated/merged 实例桶并保留 frontier；一次 join 不能消解整个桶。

AST-only 模式可以保留 source candidate、callable 和对象操作，但必须为 partial/unknown；不得生成 ThreadInstance、thread-start/exit、join-complete、MHP、RF、SW、HB、risk 或 discharged。

### 5. 已验证标准库 profile

开发镜像锁定 Clang/LLVM 21.1.8、libstdc++ 13 和 libc++ 21，target 为 `x86_64-pc-linux-gnu`，Itanium ABI，64 位指针。当前注册项：

| 标准 | vendor | 版本标识 | profile id | 状态 |
| --- | --- | --- | --- | --- |
| C++17 | libstdc++ | `__GLIBCXX__=20240904` | `1ba2f7fe…ec448a` | verified |
| C++20 | libstdc++ | `__GLIBCXX__=20240904` | `3988f720…28551` | verified |
| C++20 | libc++ | `_LIBCPP_VERSION=210108` | `dc17dd0b…0b500` | verified |

注册项保存 `<thread>` header digest、DataLayout、exception/RTTI、wrapper symbol/calling convention/parameter role/digest 和 compile-only LLVM IR provenance。任一字段漂移、同一标准出现多个 profile、未知 vendor/ABI 或未验证状态都进入 partial/unknown，不做相似名称匹配。生产 Dockerfile 未修改；与开发容器合并仍属于独立 change。

### 6. CLI

```bash
python3 -m memory_order_analyzer model-cpp-thread-lifecycle \
  --request request.json \
  --artifact-store artifacts \
  --output output-a3 \
  --source-worker build/memory-order-source-worker \
  --ir-worker build/moa-worker
```

请求只消费显式引用的产物，不扫描“最新结果”、不扩大 scope、不运行构建或目标程序。输出目录必须尚不存在。`--source-worker`/`--ir-worker` 用于保持统一编排接口；A3 组合消费请求已引用的 worker 产物，不隐式重跑上游阶段。

退出码：`0` 表示请求范围内 lifecycle graph complete；`2` 表示 partial/unknown/unsupported；`1` 表示无效请求、依赖/profile 损坏、所有计划失败或运行错误。`0` 也不表示线程安全。

### 7. 完整性、预算与降级

预算覆盖 TU、callable、对象、instance、transition、relation、递归轮次、候选、worker/request 墙钟、输出和诊断字节。达到预算后保留已知事实、hit/total 和非空 frontier，结果为 partial。gap 按 TU/entity/object/call/thread/path/protocol 身份进入候选依赖切片；相关 P4 候选降为 unknown，已证明无关的 C pthread 候选可继续评价，但顶层 scope 仍标记不完整。

所有 gap/failure/unknown 具有稳定 code、中文 `detail/suggestion` 与英文 `detail_en/suggestion_en`。未知 RAII mutex 仍由 A2 `SynchronizationGap` 阻断风险判定；解析了 `std::thread` 生命周期不代表解析了 mutex lifetime。

### 8. 明确不支持

首版不支持 Windows、MSVC、clang-cl、`std::jthread`、`std::async`、线程池、executor、自定义调度框架、完整 RAII mutex、condition variable、semaphore、rwlock、try/timed/robust/recursive mutex、通用指针分析、fence、RMW/CAS release sequence 或通用 HB/data-race 求解。ABI/profile 不匹配和这些结构必须进入 unknown/frontier，不能解释为没有线程或没有同步。

实际验证与复现命令见 [生命周期验证记录](../tests/fixtures/documentation/history.md#doc-cpp-thread-lifecycle-validation)。C++ RAII 同步由 A4 建模，对象 provenance 由 A5 扩展，fence/RMW 由 A6 扩展。

<a id="doc-cpp-raii-synchronization"></a>

## C++ RAII 同步建模

### 1. 能力边界

A4 在不修改 P1 `ModuleFacts v2`、P2 `EffectSummary v1`、P3 `ThreadContextGraph v1`、P4 `SinglePublicationProtocolGraph v1`、A1、A2 和 A3 产物语义的前提下，增加独立的 `CppRaiiSynchronization* v1` sidecar。输入限定 GCC/Clang；新增标准库语义限定 C++17/C++20，C11/C17 继续使用独立的直接 `pthread_mutex_lock`/`pthread_mutex_unlock` 路径，不读取 C++ AST 类型或标准库 profile。

首版支持经实测 profile 的 `std::mutex`、`std::lock_guard`、受限 `std::unique_lock` 和固定小规模 `std::scoped_lock`。`try_lock`、timed/recursive/robust mutex、condition variable、semaphore、rwlock、通用指针分析、通用 happens-before、fence 与 RMW/CAS 不在本阶段；遇到这些形状输出 partial/unknown 和非空 frontier。

### 2. 分层架构与协议

`CppRaiiSynchronizationRequest v1` 显式列出 scope、物理 TU、source/IR 事实、P3/A3/A2/可选 P4 依赖、同步 profile 和逐层预算。依赖按 kind、id、SHA-256 摘要精确解析；摘要漂移、缺失、未来版本、混合 target/profile 或输出目录已存在时拒绝运行，不扫描目录补选替代产物。

`CppRaiiLocalFacts v1` 保存独立的 mutex、owner、操作、source/IR 节点与 frontier。Clang source worker 登记 `std::mutex` 对象/字段、RAII owner、构造、隐式析构、move、显式 lock/unlock/owns-lock 与不支持 tag；LLVM 层从 `ModuleFacts` 的真实 call/invoke、参数、DataLayout、calling convention、正常/异常后继和 SSA provenance 提取候选，再按 profile 精确采用。AST scope 只形成候选，不能单独建立 acquire、release、SW 或 HB。

`CppRaiiSynchronizationGraph v1` 分离 `MutexInstance`、`RaiiOwnerInstance`、operation、held-region 和 proof identity。`CppRaiiSynchronizationReport v1` 引用 graph/profile、完整性、预算、缓存和中英文字段；固定 `safety=not_established`、`findings=null`。机器 identity 不包含翻译文本。

协议文件为 [protocols/cpp-raii-synchronization-protocol.json](../protocols/cpp-raii-synchronization-protocol.json)，JSON Schema 为 [cpp_raii_synchronization.json](../schemas/cpp_raii_synchronization.json)。

### 3. Profile 与 ABI 支持矩阵

| 标准 | 标准库 | 锁定证据 | 状态 |
| --- | --- | --- | --- |
| C++17 | libstdc++ | Clang 21.1.8、`__GLIBCXX__=20240904`、Itanium ABI、x86_64、实际 mutex lock/unlock wrapper | verified |
| C++20 | libstdc++ | 同上，独立标准 identity，并关联 A3 lifecycle profile | verified |
| C++20 | libc++ | Clang/libc++ 21.1.8、`_LIBCPP_VERSION=210108`、Itanium ABI、x86_64、实际 mutex lock/unlock wrapper | verified |
| C++17 | libc++ | 未登记 | unsupported/unknown |

注册项位于 [cpp-raii-profiles](../cpp-raii-profiles)。采用时逐项比较 vendor、版本、标准、ABI、target、DataLayout、指针宽度、异常、RTTI、header digest、wrapper signature、模型版本及 A3 profile 关联；只凭 vendor 相同、函数名相似或 mangled name 相似不能采用。A3 匹配而 A4 不匹配时，线程生命周期可保留，RAII 同步必须降级。

开发容器已经同时提供 libstdc++ 与 libc++21，A4 没有修改生产 Dockerfile。profile probe 只编译到 LLVM IR，不链接或运行目标程序。

### 4. Owner 状态机

状态集合为 `uninitialized`、`owns`、`deferred`、`moved-from`、`released`、`unknown`。

- `lock_guard`：构造成功且实际 lock wrapper、对象、CFG/cleanup 均精确时进入 `owns`；正常与异常出口的唯一 unlock 闭合后进入 `released`。
- `unique_lock`：默认成功构造进入 `owns`；`defer_lock` 进入 `deferred`，唯一成功 `lock()` 后进入 `owns`；显式 `unlock()` 或持锁析构进入 `released`。重复 lock/unlock、adopt/try/release/swap 或不明 owns-lock guard 进入 unknown。
- move：只转移 ownership token，底层 mutex identity 不变；moved-from owner 不得重复 release。目标已有 ownership、self-move 或来源多义时保守 unknown。
- `scoped_lock`：所有 mutex identity、成功获取和逆序释放证据完整时整体成立；任一元素未知时整组不得成为 must-held proof。
- pthread：C 路径用 `pthread-direct` owner 表达配对区间，但 `synchronization_profile_id` 必须为空，不采用任何 C++ profile。

路径上存在构造抛出、缺失 cleanup、对象 may-alias、动态 GEP、候选超限或状态合并时，不发布 must-held region。

### 5. 受限证明链

完整 proof 必须同时具有：同一规范化普通非 robust mutex；精确且成功的 acquire；每条相关正常/异常路径上的成对 release；访问落入闭合 held-region；明确的 `ThreadInstance`；P3/A3 证明线程可能并行；profile、对象、路径和候选相关依赖均完整。proof 引用双方 operation、held-region、mutex、thread 与原始 source/IR 节点。

输出的 `mutual-exclusion` 和 `mutex-sync-candidate` 只表达该受限同 mutex 模型。它们不是通用 sequenced-before/happens-before 闭包，不能替代 atomic reads-from、modification order、release sequence 或 fence 证明，也不能把无关 mutex 用来消解 publication risk。P2 `order`、P3 reads-from candidate、A3 join/detach、类型名、函数名或词法 scope 都不能单独生成 proof。

A2/P4 组合采用候选依赖切片：仅同 TU/entity/object/call/thread/path/profile/protocol 的完整 A4 proof 可关闭相关 RAII/mutex gap；AST-only、may、partial、零候选或无关 proof 保留 unknown。归档样例 `safe/03_pthread_mutex.cpp` 的本地副本只在证据链完整时于受限模型内消解，不能据此宣称程序安全。

### 6. CLI、缓存与退出码

```bash
python3 -m memory_order_analyzer model-cpp-raii-synchronization \
  --request /input/cpp-raii-request.json \
  --artifact-store /artifacts \
  --source-worker /output/build/memory-order-source-worker \
  --ir-worker /output/build/moa-worker \
  --output /output/a4-run
```

输出目录必须不存在。产物包括 `request.json`、每 TU 的 `local-facts/*.json`、`graphs/*.json` 和 `report.json`。缓存位于独立的 `cpp-raii-synchronization-v1` 命名空间，key 覆盖 schema/model、全部依赖、toolchain/profile、预算和实现 identity；failed、timeout、wall-clock partial 与 profile mismatch 不作为长期语义命中。cold/warm 的 semantic digest 必须一致，cache hit/miss 不参与报告 semantic digest。

退出码：`0` 表示 A4 请求完整（可能是完整零候选）；`2` 表示 partial/unknown/frontier；`1` 表示请求无效或分析失败。A4 不返回风险码 `3`。所有用户诊断提供 `detail/detail_en`、`limitation/limitation_en` 和 `suggestion/suggestion_en`；即使完整 proof 也明确“受限模型内证明，不代表全程序安全”。

### 7. 预算与明确非目标

请求分别限制 TU、source/IR 节点、profile、mutex、owner、wrapper、调用上下文、状态转换、held-region、relation、递归轮次、候选数、worker/request 时间和输出大小。任一预算命中时保留已知 may facts、limit 和非空 frontier，不能以空摘要表示无同步。

本阶段不实现 Windows、MSVC、clang-cl、`std::jthread`、线程池、executor、自定义同步、完整 RAII mutex 族、通用 points-to、通用 data-race 或全程序安全证明。A5 独立层扩展受限对象 provenance，A6 扩展 fence/RMW/CAS；B1 CMake scope 导入和 B2 容器整合保持独立 change。

<a id="doc-thread-entry-discovery"></a>

## 线程入口发现与 Root Overlay

`expand-thread-entry-discovery` 在 R1 的“全局轻量索引 + ExecutionRoot 驱动深度分析”之前增加独立的线程入口语义层。它回答“哪些调用点可能创建线程、入口 callable 是什么、证据是否足以纳入 root”，不回答程序是否线程安全。

### 1. 分层流程

1. Clang source worker 从 C/C++ AST 提取入口候选：C API 声明、`CXXConstructExpr`、canonical record、实际 constructor、spelled/canonical type、alias chain、callable、对象与宏位置。
2. LLVM 事实层提取直接 `pthread_create`/`thrd_create` 的 callback SSA、handle、result 和成功观察；C++ 路径从 SourceIRBinding 绑定的外层调用沿确定直接 wrapper 有界查找已验证 broker。
3. `ThreadEntryLocalFacts v1` 保存 AST 与 IR 两套观察。候选取并集，证据只在 physical TU、编译 profile、model、callsite、callback、target、DataLayout 与 broker role 相容时相交提升精度。
4. `ThreadEntrySiteIndex v1` 把证据状态、执行语义和 root 处置拆成三个维度，避免把“发现候选”“一定创建线程”和“可以生成 root”混为一谈。
5. `ThreadEntryRootOverlay v1` 只读引用 R1 的 `ExecutionRootIndex v1` 与 `RootDrivenAnalysisPlan v1`，去除已有 root，新增 callable context、创建点 origin 和 reachable demand；R1 原产物不被修改。

### 2. AST 语义类型

标准 C++ 线程类型只按 Clang 已解析语义识别：

- canonical record 必须是 profile 登记的 `std::thread`、`std::__1::thread`、`std::jthread` 或 `std::__1::jthread`；
- 同时保存源码 spelled type 与 canonical type，因此 `using worker_thread = std::thread` 可以保留别名而不丢失标准类型身份；
- constructor 分类为 default、callable construction、move、copy/deleted、factory return 或 unknown；default、move 和 factory callsite 本身不创建新线程；
- 自定义 `thread`、未登记 `boost::thread`、`Form.submit`、`enqueue`、`post` 和 `clone` 不会因名字相似而被采用。

`std::jthread` 额外记录 stop-token 注入候选。`std::async` 从选中的 overload 和受限枚举值流分类 `async`、`deferred`、`default`、`both` 或 `unknown`。AST 事实不会单独建立 runtime broker、MHP、同步或 happens-before。

### 3. BC broker 与模型 profile

入口模型在 [models/thread-entry-models.json](../models/thread-entry-models.json) 中独立版本化。profile 绑定 API family、canonical source entity、标准库 vendor/version、C++ ABI、target、DataLayout、头文件 SHA-256、精确 broker symbol、wrapper role 和完整 profile digest。

锁定容器当前登记：

- libstdc++ `13.3.0-6ubuntu2~24.04.1`：`std::jthread` 与 `std::async` 最终使用精确 `_M_start_thread` broker；
- libc++ `21.1.8`：两者使用带 ABI tag 的精确 `__libcpp_thread_create` broker；
- 其他 vendor、版本、ABI、target 或 DataLayout 不近似匹配，保持 unsupported/partial。

同一个底层 broker 可能同时服务 `thread`、`jthread` 和 `async`，所以 mangled symbol 或底层 `pthread_create` 不能独立决定高层 API。分析器必须从 AST callsite 经 SourceIRBinding 进入确定 wrapper 链，再用对应 profile 验证 broker。优化后 broker 被内联、链路歧义或预算耗尽时保留源码候选并进入 frontier。

### 4. Site 的三个维度

| 维度 | 取值 | 含义 |
| --- | --- | --- |
| `evidence_status` | `dual-exact`、`ir-exact`、`source-candidate`、`ir-candidate`、`ambiguous`、`unsupported`、`failed` | AST/IR 证据是否对齐 |
| `execution_semantics` | `creates-thread`、`may-create-thread`、`does-not-create-thread`、`unknown` | 该调用点的创建语义 |
| `root_disposition` | `adopted`、`conditional-frontier`、`excluded`、`frontier` | 是否产生正式 root |

直接 C `pthread_create`/`thrd_create` 在 ABI、callback SSA 和模型证据完整时允许 `ir-exact`。C++ 标准库入口要求 AST 与 BC 双源精确，IR-only mangled name 不采用。显式 `launch::async` 可采用，`launch::deferred` 排除，默认或组合 policy 进入 conditional frontier。

相同物理调用点的重复 AST/IR observation 会合并；同一 callable 的不同创建点保持独立 site 和动态 root origin，但可共享 canonical callable context。循环或递归创建保存 `repeated`/`merged` cardinality。

### 5. 完整性、预算与缓存

request 限制 TU、source/IR facts、type/alias 深度、site/binding/callback/profile、wrapper、root/context、SCC、frontier、诊断、输出和 wall-clock。命中限制会保留已知事实并报告 `hit/limit`，结果为 partial；不会用空集合表示“没有线程”。开放 scope、相关依赖失败、profile/ABI 冲突、callback 歧义、broker 缺失和 conditional async 都形成非空 frontier。

缓存 namespace 固定为 `thread-entry-discovery-v1`。键包含完整 request、scope/profile、模型、预算和所有显式依赖 digest；只发布 deterministic complete 结果。损坏、陈旧、failed、timeout 或 wall-clock partial 不会作为有效命中。

### 6. CLI

```bash
python3 -m memory_order_analyzer.cli discover-thread-entries \
  --request /input/thread-entry-request.json \
  --artifact-store /input/artifact-store \
  --output /output/thread-entry-run \
  --source-worker /output/build/memory-order-source-worker \
  --ir-worker /output/build/moa-worker
```

v1 只读取 request 明确引用的版本化事实，不扫描“最新”目录，不触发编译、链接、目标程序、网络或 SSH。worker 参数保留统一 CLI 形状；已有显式事实时不会启动 worker。输出目录必须不存在。

退出码：`0` 表示请求范围内入口发现 complete，`2` 表示 partial/unknown/unsupported/frontier，`1` 表示请求无效或全部失败。所有报告固定 `safety=not_evaluated`、`findings=null`；精确入口和零候选都不是全程序安全证明。

### 7. 支持边界

支持 GCC/Clang 的 C11、C17、C++17、C++20；明确排除 Windows、MSVC 和 clang-cl。内置 API 为直接/受限 wrapper 的 pthread、C11 threads，以及已验证 profile 下的 `std::thread`、`std::jthread`、`std::async`。线程池、任意 executor、自定义调度框架、通用函数指针、通用 data race、fence、RMW/CAS 和 happens-before 求解不属于本层协议。
