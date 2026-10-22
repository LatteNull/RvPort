## Why

P3 已能提供线程实例、执行顺序、MHP、mutex 和原子 reads-from 候选，但这些关系既不能证明某次消费读取了发布写，也不能判断 relaxed、过早发布或过晚 acquire 是否形成风险。为落实路线图 P4，需要在保持 P1/P2/P3 原始语义不变的前提下，增加首个受限、可解释且完整性可审计的一次性发布／消费风险检查器。

## What Changes

- 这是一个**运行时实现 change**；本次 propose 只定义实施契约，不表示风险检查能力已经可用。
- 新增独立版本化的 `PublicationRiskRequest`、`PublicationLocalFacts`、`SinglePublicationProtocolGraph` 和 `PublicationRiskReport`，引用而不改写 P1 `ModuleFacts v2`、P2 `EffectSummary v1`、P3 `ThreadContextGraph v1` 及原报告。
- 从 LLVM 局部值流和控制流生成 flag 初值、发布值、观察谓词、成功控制边及分析生成的“成功观察实例”证据；支持 atomic load 经有限 compare/cast/直接返回及确定跨 TU wrapper 到消费者分支的传播。
- 在 GCC/Clang 的 C11/C17/C++17/C++20、直接 POSIX `pthread_create`/`pthread_join` 和显式 scope 内，组合唯一发布写者、非重复发布、精确 flag/payload 对象范围、MHP、执行顺序、消费者 gate 和受限 reads-from 唯一化，构造一次性发布协议候选。
- 检测普通 flag/payload 的 `potential-data-race`，以及 relaxed、缺少或过晚 acquire、发布早于 payload 写和 all-atomic relaxed 的 `publication-order-risk`；release/acquire 或 seq_cst 只记录“在受限模式内消解”，不宣称全程序安全。
- 将多写者、重复发布、ABA、consume、fence、RMW/CAS release sequence、`std::thread`/RAII、复杂 mutex、未知同步和通用指针别名显式降为 unknown/frontier；不把 P3 reads-from candidate 或 P2 `EffectSummary.order` 直接提升为 synchronizes-with、sequenced-before 或 happens-before。
- 新增显式风险分析 CLI、传递缓存、分层完整性、明确候选分母、双语诊断和 `0/3/2/1` 退出语义；零候选、零 finding、partial 或 unsupported 不得被表述为安全。
- 新增 pthread 版 C/C++ 单 TU、跨 TU wrapper、无 debug、开放 scope、预算边界及 CASE0–CASE7 等价语义矩阵，并要求所有新增、修改或复用的自有执行代码具有单元测试；项目整体、各语言及受影响模块行/分支覆盖率均至少 90%。

## Capabilities

### New Capabilities

- `llvm-publication-analysis-facts`: 定义独立 LLVM 发布局部事实、初值与观察值依赖、成功 gate、原始/分析节点身份、预算和 unknown 语义。
- `single-publication-protocol-modeling`: 定义一次性发布候选、成功观察实例、受限 reads-from 唯一化、发布证明链、风险分类及保守降级。
- `publication-risk-reporting`: 定义风险请求、协议图、报告、CLI、缓存、双语诊断、完整性分母和风险退出码。

### Modified Capabilities

- `analysis-integrity-reporting`: 增加 P4 跨层依赖校验、风险分析完整性与 findings/unknown/已消解结果分离要求，同时保持早期报告语义不变。
- `analyzer-unit-test-quality`: 增加一次性发布规则的 pthread C/C++ 固定语义矩阵和 P4 受影响模块覆盖率验收。

## Impact

- 预计影响 `src/` 的 LLVM 局部发布事实与 worker 操作，`python/memory_order_analyzer/` 的协议校验、候选组合、受限求解、风险规则、缓存、报告和 CLI，以及 `schemas/`、构建配置、测试夹具和 `doc/`。
- 不修改现有 P1/P2/P3 schema、kind、身份、缓存或命令语义；P3 继续输出 `safety=not_evaluated`、`findings=null`。
- 首版继续使用项目锁定的 LLVM 开发环境和现有依赖，不引入 DevKit、SSH、SVF、PhASAR、GenMC 或网络作为运行时、离线测试或正确性 oracle。
- `doc/experiments/publication.cpp` 的 `std::thread` 样例只作为 IR 表达对照；端到端验收使用直接 pthread 的新固定输入。
