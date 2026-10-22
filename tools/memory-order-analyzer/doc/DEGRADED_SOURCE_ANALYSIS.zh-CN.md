# 降级源码分析与保守完整性传播

[English](DEGRADED_SOURCE_ANALYSIS.md) | 简体中文

`add-degraded-source-analysis` 在 P1–P4 与 A1 之上增加独立的 A2 wrapper。它解决两类问题：某个 TU 无法生成或分析 BC 时仍保留可信源码事实；发现未知 mutex、RAII 或同步 wrapper 时，不再把“尚未建模”错误解释成“确定不存在同步”。A2 不修改 `ModuleFacts v2`、`EffectSummary v1`、`ThreadContextGraph v1`、`SinglePublicationProtocolGraph v1` 或 A1 产物的语义和缓存身份。

## 1. 支持范围

- 编译器只接受 GCC/G++ 与 Clang/Clang++ 的兼容编译记录；Windows、MSVC 和 clang-cl 明确拒绝。
- 语言 profile 独立为 C11、C17、C++17、C++20。C 路径覆盖 C linkage、直接 pthread、全局/静态对象、struct/union 字段、宏、`_Atomic` 和 `<stdatomic.h>`，不依赖 C++ AST 类型或标准库模型。
- C++ 路径可观察 pthread、atomic 及 `lock_guard`/`unique_lock`/`scoped_lock` 类型，但 A2 不为 RAII 建立锁区间或同步边。
- 运行始终是 compile-only/source-analysis-only：不链接、不执行目标程序、不运行 CMake 配置、不联网，也不扩展显式 scope。

`compile_commands.json` 只为每个 Translation Unit（TU）的 AST/source worker 提供可选真实参数，不生成 BC。A2 请求使用固定摘要显式引用 source request、外部 bundle record、IR binding request、ModuleFacts 及可选 P3/P4 产物；某个外部 BC 缺失或 reader 失败时可保留 AST-only 候选，但必须是 partial/unknown。目录中“最新文件”不会被自动选取。

## 2. 协议与产物

协议文件为 [`protocols/degraded-source-analysis-protocol.json`](../protocols/degraded-source-analysis-protocol.json)，严格 schema 为 [`schemas/degraded_source_analysis.json`](../schemas/degraded_source_analysis.json)。新增产物均为 v1：

| 产物 | 作用 |
| --- | --- |
| `DegradedSourceAnalysisRequest` | 固定 scope、source/IR 请求摘要、ModuleFacts、可选 P3/P4 产物、预声明失败和预算 |
| `TUEvidenceAvailability` | 保存每个 TU 的 profile、各阶段产物、失败记录及四种证据模式 |
| `SourceCandidate` | 仅表示源码中值得继续分析的 pthread/atomic/访问/控制/未知同步形状 |
| `SynchronizationGap` | 表示 mutex kind、RAII lifetime、wrapper、锁对象/路径或预算方面的未知同步 |
| `DegradedSourceAnalysisReport` | 汇总候选级降级、正式评估适配、精确分母、缓存、诊断和退出码 |
| `DegradedValidationSuite/Truth/Report` | 分别记录四语言 profile 的独立真值与比较指标 |

AST 提取不是 BC 失败后的临时 fallback。每个计划 TU 都先形成独立 source work item；后续 IR 或分析失败不会删除已发布的 `SourceSemanticFacts` 摘要和内容身份。

## 3. 四种模式

| 模式 | AST | IR/P1 | 允许的结论 |
| --- | --- | --- | --- |
| `ast-ir` | 可信 | 可用 | 可继续使用原 P1–P4 正式分析；A2 仍检查相关缺口 |
| `ir-only` | 不可用 | 可用 | 保留既有 IR-only 行为，不继承失败或 profile 不匹配的源码身份 |
| `ast-only` | 可信 | 不可用 | 只发布 `SourceCandidate`、unknown/frontier 和缺失证据 |
| `failed` | 不可信 | 不可用 | 不产生源码候选；报告失败原因 |

同一请求中出现多种 TU 模式时，请求模式为 `mixed`。顶层 partial 不会自动污染所有候选：依赖切片能够证明失败 TU 与候选无关时，该候选仍可保留正式评估；无法证明无关时必须保守保留依赖并降级。

## 4. AST 信任边界

完整 AST 或只因显式节点/引用预算截断的 partial AST 可以作为源码事实。`clang-replay-failed`、缺失头文件、语法/类型错误、profile 冲突、fatal diagnostic 或 error-recovery 节点使该 TU 的 AST 不可信。错误恢复树不能用于实体、控制或同步证据。

每个 `SourceCandidate` 固定为：

- `evidence_level=source-only`
- `verdict=unknown`
- `safety=not-established`
- 明确列出缺失的 memory effect、execution order、byte range、thread instance、reads-from、synchronizes-with、happens-before；AST-only 还缺少 `ir-binding`。

源码中的先后书写、API 名称或类型名称不会生成 sequenced-before、reads-from、synchronizes-with 或 happens-before，也不会产生 P4 finding、severity、discharged 或“安全”结论。

## 5. 失败分类

失败记录同时包含阶段、稳定性和中英文字段：

| `failure_class` | 典型情况 |
| --- | --- |
| `frontend-invalid` | 缺失头文件、宏展开失败、语法/类型错误、fatal AST |
| `profile-replay-incompatible` | GCC-only 选项无法被固定 Clang 兼容重放 |
| `ir-generation-failed` | BC emission、parse 或 verify 失败 |
| `worker-budget` | 时间、输出、内存/资源或显式工作预算耗尽 |
| `artifact-validation-failed` | schema、摘要、身份、显式依赖或缓存损坏 |
| `analysis-stage-failed` | P2/P3/P4 或未单列的 worker 阶段失败 |

诊断被字节预算截断；stdout 只输出协议 JSON，worker 日志只进入有界 stderr/诊断。确定性、依赖仍有效的派生产物可以缓存；timeout、crash 和资源失败不作为长期语义成功缓存。

## 6. 同步缺口和 P4 适配

`SynchronizationGap` 保存 source/IR 引用、候选 TU、节点、关系、对象、线程、路径、预算和依赖摘要。当前生成：

- `mutex-kind-unknown`
- `unmodeled-raii-lifetime`
- `unknown-synchronization-wrapper`
- `unresolved-lock-object`
- `unbalanced-or-conditional-lock`
- `synchronization-budget`

适配器只读取 P4 assessment，不修改原 P4 graph/report。如果 finding 或 discharged 的依赖切片与 AST-only/failed TU 或同步缺口相交，或者无法解析其候选依赖，该 assessment 的 A2 `effective_status` 为 `unknown`；原始 ID、kind 和 status 保留用于审计。只有证明无关的缺口才能在局部忽略，顶层完整性仍登记所有缺口。

直接、同对象、普通非 robust 的 C/C++ `pthread_mutex_lock/unlock` 继续使用 P3 已支持模型，不会仅因出现锁名而创建缺口。`std::lock_guard` 的局部回归在 A2 中从误报降为 unknown；完整 RAII 消解属于 A4。

## 7. CLI

```bash
python3 -m memory_order_analyzer analyze-degraded-source \
  --request /input/degraded-request.json \
  --artifact-store /artifacts \
  --output /output/degraded-run-001 \
  --source-worker /output/build/memory-order-source-worker \
  --ir-worker /output/build/memory-order-source-worker
```

输出目录必须预先不存在。固定文件包括 `request.json`、`report.json`，以及按身份命名的 `source-facts/`、`llvm-binding-facts/`、`availability/`、`source-candidates/`、`synchronization-gaps/`。

退出码：

- `0`：完整执行且没有正式 risk；不是安全证明。
- `3`：完整执行且存在未被更高优先级不完整性覆盖的正式 risk。
- `2`：存在可用但 partial/unknown/source candidate/mixed/budget 结果；正式 risk 与 AST-only 计划候选并存时也返回 2。
- `1`：请求无效或全部证据不可用。

零候选、零 finding、exit 0 或 P4 discharged 都不能表述为全程序安全。

## 8. 缓存、预算与确定性

A2 使用 `derived/degraded-source-analysis-v1/` 独立缓存命名空间，不复用或改写 A1/P1–P4 键。availability、candidate 和 report 身份包含 schema/policy、scope/profile、源与 include 摘要、显式依赖摘要、预算和工具链相关身份；替换产物、悬空依赖和损坏条目都会拒绝。report 的 `semantic_digest` 排除命中/未命中计数，因此 cold/warm 语义相同。

切片支持循环和重复路径；达到 `slice_items` 预算时登记稳定 frontier，不能把截断解释为无依赖。所有列表按机器身份确定排序，中英翻译不参与候选 ID。

## 9. 当前限制与后续阶段

A2 不实现 `std::thread`、完整 RAII mutex、try/timed/recursive/robust mutex、condition variable、semaphore、rwlock、通用 points-to、fence、RMW/CAS release sequence 或通用 happens-before/data-race 检测。这些扩展由独立的 A3 生命周期、A4 RAII、A5 provenance 和 A6 fence/RMW 层提供，见主题手册。A2 wrapper 的保守边界不随其他层存在而自动放宽。
