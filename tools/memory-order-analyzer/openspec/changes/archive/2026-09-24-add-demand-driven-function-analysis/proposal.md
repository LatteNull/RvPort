## Why

R1/R1.1 已能生成执行根与可达需求计划，R2 也把候选分母限制在 root 可达域，但 P1/P2/P3 worker 仍会预先遍历全部函数体、为未被需求触达的函数构造深度 LLVM 分析，并在分散调用中重复解析 BC。现在需要落实 R3，把既有“需求切片”真正下推为按函数与上下文的懒提取、确定性调度和失败隔离，在不改变 P1–R2 语义的前提下降低大工程的 CPU、内存和输出成本。

这是运行时分析基础设施、CLI 与架构文档 change，不是纯文档调整。

## What Changes

- 新增独立版本化的 `DemandDrivenAnalysisRequest`、`LLVMModuleIndexFacts`、`FunctionSemanticFacts`、`FunctionEffectFacts`、`FunctionThreadFacts`、`AnalysisDemandGraph`、`WorkerExecutionManifest` 与双语 `DemandDrivenAnalysisReport`，通过只读适配器接入现有 P2/P3/R2，不把部分函数事实伪装成 `ModuleFacts`、`LocalAnalysisFacts` 或 `ThreadLocalFacts`。
- 全局阶段仅索引 symbol、definition/declaration、linkage、ABI、profile、target、`DataLayout` 与必要源码绑定；使用 LLVM 21 lazy bitcode module 和 `GlobalValue::materialize`，仅为 R1 plan、R1.1 overlay 以及后续精确 direct-call/callback 扩展产生的 demanded function/context 物化函数体和提取深度事实。
- 在保持既有 function、block 和 instruction identity 的前提下，以有界单调 worklist 支持 `main`、显式入口、`pthread_create`、`thrd_create`、`std::thread`、`std::jthread` 与显式 async roots；按 artifact、分析层、函数和上下文确定性分批并受限并行，单批 BC 只解析一次。
- 递归/SCC、歧义 callback、间接调用、开放 scope、AST-only、依赖失败、worker crash、超时和预算耗尽必须生成非空 frontier；禁止回退到 all-defined、全 BC load/store 扫描或把缺失事实解释成无效果。
- AST 源事实继续作为独立 TU 级事实层；本 change 不承诺 Clang AST 按函数懒解析。只有完整 function/context shard 可缓存，缓存以完整 BC digest、profile、target、`DataLayout`、函数身份、分析策略和预算为失效边界，调度顺序与 cache hit 不进入 semantic digest。
- 保持现有 eager CLI 行为不变，新增显式 R3 CLI、缓存、预算、完整性、0/2/1 退出码和中英文字段；执行期间不得 configure、build、link、运行目标程序、访问网络或 SSH。
- 输入限定 GCC/Clang 的 C11、C17、C++17、C++20，排除 Windows、MSVC 和 clang-cl；暂不实现 A6 fence/RMW、通用指针分析、风险规则修改、持久 LLVM daemon、B1 CMake scope 导入或 B2 容器整合。
- 增加 eager/lazy 规范化语义等价、不可达函数不物化、需求扩展、跨 TU、递归、失败隔离、cold/warm cache 与固定稀疏可达规模验收，并持续回归 R2 四语言 truth 与 TinyCThread；记录 indexed、demanded、scheduled、materialized、completed、partial、failed、cache-hit、module parse、CPU、wall、RSS 和输出大小。
- 为所有新增、修改或复用的自有代码增加正常、边界、异常和 partial/unknown 单元测试，并验收项目整体、各实现语言和每个受影响模块的行/分支覆盖率均至少 90%。

## Capabilities

### New Capabilities

- `demand-driven-function-analysis`: 规定 R3 轻量 LLVM 模块索引、按函数/上下文需求图、lazy materialization、函数级 sidecar、worker 调度、frontier、缓存、预算、CLI、双语报告以及与既有 eager/P2/P3/R2 协议的等价适配边界。

### Modified Capabilities

- `analyzer-unit-test-quality`: 增加 R3 自有模块单元测试、eager/lazy 等价、四语言 R2 与 TinyCThread 回归、稀疏可达规模和缓存验收，以及整体、实现语言和逐受影响模块行/分支覆盖率至少 90% 的 required gate。

## Impact

- LLVM C++ worker 将新增 lazy module 索引、稳定的函数局部 identity、按需 materialize 和分层函数 shard 提取入口；既有 eager 提取入口与 `ModuleFacts v2` 等协议保持不变。
- Python 编排层将新增 R3 请求/契约、需求图、有界 worklist、确定性 batch/worker manifest、失败隔离、完整性与 frontier、缓存、CLI、报告和 acceptance 逻辑，并以只读适配器向 P2/P3/R2 提供语义等价输入。
- 新增 JSON Schema、协议清单、C11/C17/C++17/C++20 fixtures、语义等价与规模验收、架构/使用/验证文档；README 与 `doc/IMPLEMENTATION_ROADMAP.md` 同步标记 R3 状态和边界。
- 不引入新的在线、SSH、专有工具或目标程序执行依赖；开发与验收继续使用项目锁定的 GCC/Clang/LLVM 21 独立环境。
