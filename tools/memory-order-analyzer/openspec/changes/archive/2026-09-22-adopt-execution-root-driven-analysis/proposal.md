## Why

当前分析器虽然在 P2/P3 使用显式 roots，但 P1、A1、P4 及后续 sidecar 仍分别扫描和组合 scope 事实，缺少统一的线程创建点、执行入口与可达分析计划，导致“哪些线程入口被覆盖、哪些调用上下文实际需要深度分析、哪些入口缺口会使结论不完整”无法由一个稳定协议回答。现在需要把架构调整为“全局轻量索引 + ExecutionRoot 驱动深度分析”，先统一 AST 与 BC 的线程入口证据，再为后续并发访问候选和按函数懒提取建立可靠边界。

## What Changes

- 这是运行时实现与架构文档 change，不是纯文档调整；新增 R1 root discovery/planning 编排、CLI、缓存、schema、报告和验证入口。
- 新增独立 v1 `ExecutionRootDiscoveryRequest`、`ThreadCreationSiteIndex`、`ExecutionRootIndex`、`RootDrivenAnalysisPlan` 与 `RootDrivenAnalysisReport`，不修改 P1–P4/A1–A5 已冻结产物。
- 从 AST 与 BC 独立发现线程创建候选，取并集后按物理 TU、profile、SourceIRBinding、ABI/linkage、调用点、callback SSA/source entity 和标准库 profile 对齐，区分 `dual-exact`、`ir-exact`、`source-candidate`、`ambiguous`、`unsupported` 与 `failed`。
- 支持显式程序入口、唯一 `main`、用户声明的库导出入口、直接 `pthread_create` callback、A3 已验证 `std::thread` callable 和用户显式框架线程入口；禁止仅凭名称、类型或相似 wrapper 建立 root。
- 从 root 沿 A1/P1/P2 已采用直接调用和受支持 wrapper 有界扩展 reachable function/context/TU，统一编排现有 P2/P3 roots 模式并发布可审计分析需求计划。
- 将间接调用、歧义 callback、开放 scope、AST-only、编译/BC 失败、profile/ABI 冲突、递归和预算耗尽保存为非空 frontier，并分别报告 root coverage、reachable coverage 与候选相关完整性；相关 root 不完整时不得给出完整无风险含义。
- 更新 README、架构说明和 `doc/IMPLEMENTATION_ROADMAP.md`，修正 A5 已同步归档状态，并将 R1、后续 R2 并发访问候选图和 R3 按函数懒提取拆分清楚。
- 首版不重写 P1 全量事实提取，不实现 `ConcurrentAccessCandidateGraph`，不新增或修改 P4 风险规则，也不实现通用 data-race、fence、RMW/CAS 或 happens-before。
- 输入限定 GCC/Clang 的 C11、C17、C++17、C++20；C pthread 路径独立于 C++ AST/标准库模型；Windows、MSVC 和 clang-cl 明确排除。
- 为全部新增、修改或复用的自有代码增加正常、边界、异常和 unknown/partial 单元测试，项目整体、C++、Python及每个受影响模块的行/分支覆盖率均至少 90%。

## Capabilities

### New Capabilities

- `execution-root-driven-analysis`: 规定 AST/BC 双源线程创建点、ExecutionRoot、root 驱动可达计划、完整性、缓存、CLI 和报告的 R1 行为与证明边界。

### Modified Capabilities

- `analyzer-unit-test-quality`: 增加 R1 自有模块单元测试、四语言离线语义矩阵、旧协议回归以及整体/语言/逐受影响模块行分支覆盖率至少 90% 的验收要求。

## Impact

- Python 编排层将新增 root discovery、证据对齐、可达规划、缓存、契约、CLI 和报告模块，并复用现有 P2/P3 roots 调度器而不切换到 `all-defined`。
- Clang/LLVM C++ worker 将新增或扩展轻量线程创建候选事实，但 P1 `ModuleFacts v2`、A1、P3 与 A3 原始产物和缓存身份保持不变。
- 新增协议清单、JSON Schema、C11/C17/C++17/C++20 单/跨 TU fixture、truth/诊断断言及机器可读 acceptance；开发容器仍锁定现有 LLVM/Clang，不引入 DevKit、SVF、PhASAR 或网络依赖。
- 文档将明确旧 P4 入口继续兼容，新 R1 报告不产生 finding/discharged/safe；未来 R2/R3 另立 change，不在本 change 中提前实现。
