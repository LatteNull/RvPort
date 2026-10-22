# 受限发布风险与原子证明

[English](publication-analysis.md) | 简体中文

本页按语义层次组织仍使用的协议、CLI、预算和限制。以 [统一项目入口](UNIFIED_PROJECT_ANALYSIS.zh-CN.md) 为产品调用入口；各分层 CLI 用于开发排查，不能把候选或局部证明解释为全程序安全。示例命令仅在 Docker 开发容器内执行。

- [P4 一次性发布风险分析](#doc-single-publication-risks)
- [A6 fence、RMW/CAS 与受限发布证明](#doc-fence-rmw-publication)

<a id="doc-single-publication-risks"></a>

## P4 一次性发布风险分析

实现状态：2026-09-16 完成，change 为 `detect-single-publication-risks`。本阶段在 P1 `ModuleFacts v2`、P2 `EffectSummary v1` 和 P3 `ThreadContextGraph v1` 之上增加独立 P4 协议，不修改前三阶段产物及其 `safety/findings` 语义。

### 1. 支持范围

P4 首版分析 GCC/Clang 生成的 C11/C17/C++17/C++20 BC，入口限定为直接 POSIX `pthread_create`/`pthread_join`。候选必须具有显式 scope、可能并行的 publisher/consumer `ThreadInstance`、精确 flag/payload 对象范围、明确初值、唯一且不重复的发布写、可识别成功分支以及可审计的同线程顺序。

支持的核心模式为：

```text
payload write
  -> P4 local must-before
flag release/seq_cst store
  -> 受限唯一 reads-from
flag acquire/seq_cst successful observation
  -> 成功 edge 控制且 must-before
payload read/use
```

分析只说明该候选在 `c-cpp-single-publication-v1` 受限模型内被消解或存在风险。它不是全程序 data-race 检测器，也不证明程序安全。

暂不支持多写者或重复发布、ABA、consume、fence 协议、RMW/CAS release sequence、`std::thread`/RAII、复杂 mutex、condition variable、semaphore、rwlock、线程池、自定义同步、通用 points-to、对象回收和通用 data-race 检测。相关证据进入 `unknown`、`unsupported` 或 frontier，不会被假设为同步，也不会被假设不存在。

### 2. 输入与 CLI

先用现有 compile-only 流水线生成 artifact store 和显式 `ScopeManifest`，再准备 P3 `ThreadAnalysisRequest`。P4 请求只引用该线程请求，并显式携带模型与预算：

```json
{
  "schema_version": 1,
  "kind": "PublicationRiskRequest",
  "analysis_version": "0.1.0",
  "policy_id": "single-publication-risks-v1",
  "thread_request": "thread-request.json",
  "model_id": "c-cpp-single-publication-v1",
  "budgets": {
    "local_steps": 100000,
    "value_candidates": 8,
    "protocol_candidates": 10000,
    "assessments": 10000,
    "scc_iterations": 16,
    "worker_seconds": 60,
    "worker_output_bytes": 16777216,
    "request_seconds": 300,
    "request_output_bytes": 67108864
  }
}
```

请求中的相对路径以 P4 请求文件所在目录解析。输出目录必须不存在，工具不会覆盖旧结果：

```bash
memory-order-analyzer detect-publication-risks \
  --request publication-request.json \
  --artifact-store out \
  --output publication-result \
  --worker /path/to/moa-worker
```

命令只编译、读取和分析 BC，不执行被分析程序，不隐式 `llvm-link`，也不从同一目录或共同头文件猜测完整目标范围。`compile_commands.json` 只提供每个 TU 的编译身份；跨 TU 成员和开放边界仍由显式 scope 决定。

### 3. 四类版本化产物

| 产物 | 作用 |
| --- | --- |
| `PublicationRiskRequest v1` | 固定线程请求、模型和实际预算 |
| `PublicationLocalFacts v1` | 每个 BC 的访问、初值、观察、gate、return dependency、P4 局部顺序和证据 |
| `SinglePublicationProtocolGraph v1` | 线程/对象/观察组合、受限 reads-from、协议候选和 assessment |
| `PublicationRiskReport v1` | 分层完整性、精确分母、双语诊断、verdict、finding 和退出码 |

输出目录包含请求快照、P3 依赖输出、`publication-local/*.json`、`graphs/*.json` 和 `report.json`。缓存位于 artifact store 的 `derived/single-publication-risks-v1`，key 包含 BC/P1/P2/P3、完整请求、scope/profile、模型和预算的传递身份；缓存命中不会复用旧线程实例身份。

所有 schema 都拒绝未知字段、未来版本、悬空引用、跨 artifact/function 的伪造 `AnalysisRef`、重复 ID 和不一致计数。原始 IR 节点使用 `SourceRef`；DominatorTree gate/顺序等分析生成证明使用独立 `AnalysisRef`。

### 4. LLVM 与自研逻辑边界

LLVM C++ worker负责同版本 BC parse/verify、DataLayout、常量与访问范围、CFG、DominatorTree、LoopInfo、load/store/atomic order/syncscope、有限值依赖、成功 edge 控制区域和 P4 局部 `must-before` 证明。跨块顺序只在非重复访问满足 instruction dominance 时输出；循环中的动态发生次序不会从静态支配关系猜测。

自研 Python 层负责严格契约、worker 隔离、P1/P2/P3/P4 引用闭包、跨 TU direct-return wrapper 组合、线程实例/对象索引、唯一写者与受限 reads-from、风险规则、缓存、完整性和报告。P2 `EffectSummary.order` 不作为 sequenced-before 或 HB 证明；P3 reads-from candidate 也不会直接提升为 synchronizes-with。

P4 局部传输仅跟踪有限的 `icmp eq/ne`、zero/nonzero、布尔反转、支持的整数 cast、phi/select、Clang O0 的有界函数局部 spill 及确定 direct return。算术变换、候选爆炸、间接或歧义 wrapper 保持 unknown。

### 5. SuccessfulObservation

循环中的 atomic load 可能执行多次，所以原始 load 节点始终保留 `repeated/may` 含义。P4 另建 `SuccessfulObservation`：它绑定原始 read、P2 invocation、P3 `ThreadInstance`、谓词和成功 edge，表达“若本次观察满足谓词并沿该边到达消费区域”。

该节点不表示 load 必然发生，也不表示读取来源已确定。只有成功 edge 控制 payload use、wrapper 绑定唯一且证据闭合时，才可参与协议候选。

### 6. 受限 reads-from 唯一化

仅当以下条件同时成立时，flag store 到成功观察的关系才从候选提升为 `proved`：

1. flag 初值精确且被成功谓词拒绝；
2. 发布写值精确且被成功谓词接受；
3. closed scope 内只有一个可接受写，且 multiplicity 为 single；
4. 不存在相关 RMW/CAS、unknown clobber、开放边界或重复发布；
5. 写/读对象范围、位宽和 system syncscope 兼容；
6. gate、线程、顺序和预算证据完整。

该结论只属于当前协议候选，不会回写 P3 的通用 reads-from 或 modification order。初值与发布值不可区分、多写者、开放 scope 或相关证据 partial 时必须降级。

### 7. 风险分类

| code/类别 | 含义 |
| --- | --- |
| `ordinary-conflict` / `potential-data-race` | 已识别协议内普通 flag/payload 的可能并行重叠冲突，缺少完整同步链 |
| `missing-release` | 发布 store 不是 release-capable |
| `missing-acquire` | 控制 payload 的成功观察不是 acquire-capable |
| `acquire-too-late` | 另一个 acquire 已证明发生在 payload 使用之后 |
| `publication-store-too-early` | flag store 已证明早于 payload write |
| `all-atomic-relaxed` | flag/payload 均为 atomic，但 relaxed 组合不能建立发布链；不报普通 data race |
| `single-publication-discharged` | release/acquire 或 seq_cst 候选在受限模型内完整消解 |
| `protocol-unknown` / `protocol-unsupported` | 相关前提未知或同步形态超出首版边界 |

“缺少 payload-before 证明”本身只产生 unknown，不等于已经证明发布过早。正确对照只记录 `discharged`，不会输出“全程序安全”。

### 8. 完整性、预算和退出码

报告分别记录 input、P1、P2、P3、publication-local、candidate modeling 和 risk evaluation 状态，并保存 planned/candidate/evaluated/finding/discharged/unknown/unsupported/excluded 分母。零候选的比例为 `null`，不会伪装成 100%。

| 退出码 | 条件 |
| --- | --- |
| `0` | 所有阶段 complete，且无 supported finding |
| `3` | 所有阶段 complete，且至少一个 finding |
| `2` | partial、unknown 或 unsupported 导致结论不完整；优先于 finding |
| `1` | 请求、结构、worker 或关键输入失败 |

`safety` 固定为 `not_established`。`verdict=no_supported_risk_found` 只表示本次受限模型没有 supported finding，不能解释为安全证明。

所有用户诊断同时提供 `detail/detail_en`，建议同时提供 `suggestion/suggestion_en`。翻译文本不参与规则身份或退出码。即使无 debug 信息，报告仍保留 artifact/function/IR 节点证据。

### 9. 验证入口

语义矩阵使用直接 pthread 的 CASE0–CASE7，并另外覆盖 Clang C11、GCC C17、G++ C++17、Clang++ C++20、三个物理 TU wrapper、无 debug、开放 scope 和 `std::thread` 非支持边界。集成输入只 compile-only，不链接或执行。

<a id="doc-fence-rmw-publication"></a>

## A6 fence、RMW/CAS 与受限发布证明

`model-fence-rmw-publication` 在既有 P1–P4、A1–A5 和 R1–R3 产物之上增加独立的高级原子 sidecar。它不修改旧协议，也不把候选关系冒充为线程间顺序证明。分析入口是 `RootDrivenAnalysisPlan`、`ThreadEntryRootOverlay`、R2 atomic handoff 和 R3 demand graph；输出仍只说明受限模型内的风险、消解或未知，不代表全程序安全。

### 1. 版本化产物

`protocols/advanced-atomic-analysis-protocol.json` 注册七种 v1 文档：

1. `FenceRmwPublicationRequest`：输入引用、语言、scope、预算与缓存策略；
2. `AtomicSourceConstructFacts`：Clang AST canonical declaration、实际原子操作、类型、order 参数和标准库来源；
3. `AdvancedAtomicFunctionFacts`：独立 A6 worker 按 demanded function/context 产生的引用闭合 LLVM atomic shard；
4. `AdvancedAtomicLocalFacts`：LLVM `fence`、`atomicrmw`、`cmpxchg`、普通 atomic load/store 的事件、路径、上下文和线程实例；
5. `BoundedAtomicCommunicationGraph`：按精确对象构造的受限 RF/MO assignment、release sequence 与 fence 配对；
6. `AdvancedPublicationProtocolOverlay`：只读引用 P4 protocol，并记录 A6 补充证明或反例；
7. `FenceRmwPublicationReport`：完整性、frontier、双语诊断、统计、缓存和退出状态。

所有文档由 `schemas/advanced_atomic.json` 校验。语义摘要排除时间、路径、缓存命中等操作字段，使 cold/warm 运行保持同一 semantic digest。

### 2. 分析流水线

```text
AST canonical atomic facts ─┐
                            ├─ source/IR binding ─┐
P1/R3 demanded LLVM events ┘                     │
A5 object provenance + byte range ───────────────┼─ bounded RF/MO solver
P3 ThreadInstance/MHP ────────────────────────────┤          │
R1/R1.1 root slice + R2 atomic handoff ──────────┘          ▼
                                                   release sequence / fence proof
                                                                │
                                                     P4 read-only overlay + report
```

AST 负责确认源码构造、声明来源、canonical type 和 order 参数；LLVM 负责运行时事件、对象地址、控制路径与实际 lowering。AST-only 可以保存候选和缺失证据，但不能建立 reads-from、modification order、synchronizes-with、happens-before 或安全结论。

R3 的 `FunctionSemanticFacts` 保持原协议和语义不变。A6 通过 `moa-worker --advanced-atomic-batch REQUEST.json` 复用相同的 lazy bitcode materialization 与 demand transport，但输出独立 `AdvancedAtomicFunctionFacts`；`--demand-batch` 不包含 A6 私有字段。`-O2` direct lowering 可直接归一化；`-O0` 标准库 dispatcher 只在 canonical 源操作、order、函数/位置和 SourceIRBinding 足以唯一对齐时去重。缺少 A1/A5 对象或值绑定时仍为 partial，而不是把操作/order 等价误写成完整对象证明。

### 3. CAS、RMW 与 outcome

- `atomicrmw` 保存 operation、对象、输入/结果值、syncscope、multiplicity、function/context/ThreadInstance；当前支持 `xchg/add/sub/and/or/xor`。
- `cmpxchg` 分成 success 写入事件和 failure 只读事件。success/failure order 分开保存，failure 不得拥有 release 语义。
- weak CAS 若 outcome、guard 或循环 multiplicity 无法闭合，必须形成 frontier；不得把一次成功路径外推成整个 CAS loop 的结论。
- RMW 必须读取该对象 modification order 的直接前驱。普通候选边、MemorySSA 或 `EffectSummary.order` 均不能代替这一约束。

### 4. release sequence 的语言差异

| 语言 | release head 后可纳入的连续事件 |
| --- | --- |
| C11 / C17 / C++17 | release head 所在线程的连续修改，或任意线程的 RMW |
| C++20 | 仅后续 RMW |

求解器按对象枚举预算内的 MO 与 RF assignment。只有所有闭合有效 assignment 都支持同一发布链时，overlay 才能在受限模型内标记 `discharged`；存在完整反例 assignment 时报告 `risk`；对象、值、outcome、scope 或预算不完整时为 `unknown/partial`。

### 5. fence 组合

当前显式区分三类标准发布形式：

- fence-fence：release fence 之前的写，经原子写/读配对，到 acquire fence 之后的读；
- fence-atomic：release fence 之前的写，经其后的原子发布写和 acquire 原子读；
- atomic-fence：release 原子写被原子读观察，再经过 acquire fence。

fence 的源码位置、IR 事件和局部程序顺序必须同时可证。错误位置、`atomic_signal_fence`、target-specific syncscope 和未建模 `libatomic` runtime 均进入 frontier。

语义依据采用 [LLVM LangRef atomic instructions](https://llvm.org/docs/LangRef.html#memory-model-for-concurrent-operations)、[LLVM Atomic Instructions and Concurrency Guide](https://llvm.org/docs/Atomics.html)、[C++ fence synchronization](https://eel.is/c++draft/atomics.fences)、[C++ data-race 与 happens-before 定义](https://eel.is/c++draft/intro.races)、[P0982R1 的 C++20 release-sequence 修改](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2018/p0982r1.html)和 [C11 N1570](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf)。这些标准资料只定义语言/IR 语义，不替代本项目的实现验收。

### 6. CLI、缓存与退出码

```bash
memory-order-analyzer model-fence-rmw-publication \
  --request request.json \
  --artifact-store artifacts \
  --output output
```

运行不会 configure、build、link、执行目标程序、联网或 SSH。每个输入都按请求声明的 SHA-256 验证；缓存键绑定协议、输入内容、语言/profile/target/DataLayout、scope、策略与预算。只有完整且通过 schema/语义校验的产物可以写入缓存。

退出码：`0` 表示受限模型内完成且未发现风险，`3` 表示发现风险，`2` 表示 partial/unknown/frontier，`1` 表示请求、输入或工具失败。`0` 也不表示全程序安全。

### 7. 明确边界

以下能力不在 A6 首版：consume、通用 seq_cst total order、一般多写者、CAS loop、ABA、对象回收、任意 lock-free 算法、通用 model checking、通用 happens-before 与通用 data-race。GenMC、herdtools7 和 ARM DevKit 仅作为可选外部对照，不是核心依赖或正确性 oracle。
