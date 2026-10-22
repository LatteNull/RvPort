## Why

R1/R1.1 已能确定执行根、线程入口及可达需求切片，P2–A5 也分别保存内存效果、线程实例、生命周期、受限互斥和对象 provenance，但这些证据尚未组合成稳定的并发访问候选协议。现在需要建立 R2，将“哪些访问可能由并行执行实例作用于重叠对象”显式化，同时保留未知边界，供 P4/A6 和后续风险消费者使用，而不提前宣称 data race、happens-before 或程序安全。

这是运行时分析能力与架构文档 change，不是纯文档调整。

## What Changes

- 新增独立 v1 `ConcurrentAccessCandidateRequest`、`ConcurrentAccessProjectionFacts`、`ExecutionInstanceBindingOverlay`、`AccessProtectionOverlay`、`ConcurrentAccessCandidateGraph` 与双语 `ConcurrentAccessCandidateReport`，保持 P1–P4、A1–A5、R1 和 R1.1 现有协议及报告语义不变。
- 以 `RootDrivenAnalysisPlan` 和 `ThreadEntryRootOverlay` 的可达需求切片为分析分母，组合 P2 内存 effect、P3 pthread 生命周期/MHP、A3 C++ 生命周期、A4 受限 mutex/RAII 证明及 A5 must/may/unknown 对象 provenance。
- 精确区分 `ExecutionRoot`、`ThreadContext`、`ThreadInstance` 与 merged/repeated 动态实例，并对齐多 root P3 图、`pthread_create`、`thrd_create`、`std::thread`、`std::jthread` 及显式 `std::async`；deferred async 明确排除，默认或组合 policy 进入 conditional frontier。
- 仅在访问可能并行、对象范围 must/may overlap 且至少一侧为 write/rmw/cas 时生成候选；显式记录 same-single-instance、proven-not-parallel、read/read 和 must-disjoint 排除理由，并保留 merged/repeated 自并发可能性。
- 对对象未知、MHP 未知、AST-only、开放 scope、依赖失败和预算耗尽生成非空 frontier；按对象候选、byte range、执行族和线程实例分桶，禁止以全局笛卡尔积制造伪候选。
- 只有访问、实例、held-region、普通非 robust mutex 身份和依赖闭合时，才允许标记 `protected-within-bounded-model`；其余同步证据不足必须保持候选或 frontier。
- atomic pair 继续保留给 P4/A6；fence、RMW/CAS release sequence 和通用原子语义标记为 unsupported/frontier。报告固定 `safety=not_evaluated`、`findings=null`，退出码仅为 `0/2/1`。
- 输入限定 GCC/Clang 的 C11、C17、C++17、C++20，排除 Windows、MSVC 和 clang-cl；不实现通用 data-race、通用 happens-before、风险判定、P4 规则修改、A6 fence/RMW 语义或 R3 按函数懒提取。
- 增加四语言单 TU、跨 TU、no-debug、AST-only、字段/指针、mutex 内外、merged instance、预算和缓存 truth；归档样例只有在最小化复制、记录 provenance 并人工重标后才能进入分母。
- 为全部新增、修改或复用的自有代码增加正常、边界、异常和 partial/unknown 单元测试，并验收项目整体、各实现语言和每个受影响模块的行/分支覆盖率均至少 90%。

## Capabilities

### New Capabilities

- `concurrent-access-candidate-graph`: 规定 root 可达域内的访问投影、执行实例绑定、对象重叠、候选配对、受限保护证明、frontier、缓存、预算、CLI 和双语报告语义。

### Modified Capabilities

- `analyzer-unit-test-quality`: 增加 R2 自有模块单元测试、四语言人工 truth、既有协议回归以及整体、实现语言和逐受影响模块行/分支覆盖率至少 90% 的 required gate。

## Impact

- Python 编排层将新增 R2 请求/契约、artifact 读取与引用校验、实例绑定、候选分桶/配对、保护 overlay、完整性、缓存、CLI、报告和 acceptance 逻辑。
- Clang/LLVM C++ worker 仅在现有事实无法表达 R2 所需局部投影时增加独立 `ConcurrentAccessProjectionFacts v1`；不得修改 `ModuleFacts v2`、`EffectSummary v1` 或既有 sidecar schema。
- 新增 JSON Schema、协议清单、C11/C17/C++17/C++20 fixtures、truth/诊断断言、性能与缓存验收，以及 R2 架构/验证文档；README 和路线图同步说明候选图不是风险或安全结论。
- 现有 P4 可继续独立运行；R2 的 atomic pair 只作为加法式输入候选，不改变现有 P4 finding/discharged 语义。开发容器继续使用锁定的 GCC/Clang/LLVM 环境，不引入外部在线或 ARM DevKit 依赖。
