## Why

现有 P4 只能证明受限的一次性 atomic store/load 发布协议，并会把相关 `fence`、atomic RMW 和 CAS 候选降为 unsupported；虽然 P1–P3 已保存部分 LLVM 原子事实，A5、R1–R3 也已提供精确对象、执行根和按需分析基础，但项目仍缺少可审计的 reads-from、modification order、release sequence 和 fence 同步证明链。A6 需要在不扩张为通用 happens-before 求解器的前提下补齐这一能力，避免把高级原子协议永久留在 unknown，也避免仅凭 ordering 名称误判安全。

这是运行时分析、协议、CLI、验证语料和文档 change，不是纯文档调整。

## What Changes

- 新增独立版本化的 `FenceRmwPublicationRequest`、`AtomicSourceConstructFacts`、`AdvancedAtomicFunctionFacts`、`AdvancedAtomicLocalFacts`、`BoundedAtomicCommunicationGraph`、`AdvancedPublicationProtocolOverlay` 和双语 `FenceRmwPublicationReport`；保持 P1–P4、A1–A5、R1/R1.1、R2 和 R3 既有产物与报告语义不变。
- 在 GCC/Clang 的 C11、C17、C++17 和 C++20 范围内，支持 `<stdatomic.h>` 与 `<atomic>` 的 acquire/release fence、atomic RMW、CAS success/failure order、受限 modification order、reads-from、release sequence，以及 fence-fence、fence-atomic、atomic-fence 发布证明；排除 Windows、MSVC 和 clang-cl。
- AST 层基于 canonical semantic declaration、实际选中的操作/方法、类型、order 参数、声明来源和经验证的标准库 profile 保存独立源码事实；LLVM 层按 function/context 保存实际 fence、`atomicrmw`、`cmpxchg`、syncscope、RMW operation、CAS compare/desired/observed value、weak、success/failure outcome、guard、multiplicity 和 ThreadInstance，并验证 `-O0` dispatcher 与 `-O2` 直接 lowering 的受支持语义归一化。
- 复用 A5 must/may/unknown 对象 provenance、P3 ThreadInstance/MHP、P4 flag/payload/gate、R1/R1.1 root slice、R2 atomic handoff 和 R3 demand graph；R2 仅触发需求，P2 order、P3 reads-from candidate、R2 candidate、AST 源事实和 MemorySSA 均不得单独建立线程间顺序证明。
- 按精确原子对象执行有界 RF/MO 求解，区分 CAS success 的读写修改和 failure 的只读语义，约束 RMW 读取 modification order 直接前驱；所有闭合有效 assignment 都建立发布链时才在 A6 受限模型内消解，存在完整反例 assignment 时报告风险，证据或搜索不闭合时进入 partial/unknown。
- 按语言标准区分 release sequence：C11/C17/C++17 允许 release head 后连续的同线程修改或 RMW，C++20 仅允许后续 RMW；受限 release sequence 中的精确 RMW 不作为一般多写者拒绝。
- `atomic_signal_fence`、target-specific syncscope、未建模 `libatomic` runtime、consume、通用 `seq_cst` total order、一般多写者、CAS loop、ABA、对象回收、任意 lock-free 算法、通用 model checking 和通用 happens-before 不在本 change 内，必须形成明确且候选相关的 frontier。
- 通过 A6 overlay 引用和补充 P4 protocol，不重写 P4 原始产物，不宣称全程序安全；保留缓存、资源预算、candidate-relevant 完整性和 0/3/2/1 退出码语义。
- 建立 C11、C17、C++17、C++20 独立 truth 分母，覆盖正确/错误 fence 发布、RMW release sequence、C++20 规则差异、CAS success/failure、weak CAS、signal fence、跨 TU、no-debug、AST+IR、IR-only、AST-only、开放 scope、对象不精确、预算和缓存；GenMC、herdtools7 与 ARM DevKit 只作为可选离线对照，不作为核心依赖或正确性 oracle。
- 为所有新增、修改或复用的自有代码补充正常、边界、异常和 partial/unknown 单元测试；项目整体、各实现语言以及每个受影响模块的行覆盖率和分支覆盖率均须至少 90%。

## Capabilities

### New Capabilities

- `fence-rmw-publication-analysis`: 定义 A6 源码与 LLVM 高级原子事实、有界 RF/MO 求解、release sequence、fence 同步、P4 overlay、证明边界、frontier、缓存、预算、CLI 和双语报告。

### Modified Capabilities

- `analyzer-unit-test-quality`: 增加 A6 自有代码单元测试、四语言 truth、优化级别归一化、跨 TU/降级/预算/缓存回归，以及项目整体、实现语言和逐受影响模块行/分支覆盖率至少 90% 的 required gate。

## Impact

- 影响 Clang source worker、LLVM eager 与 R3 demand-driven worker、Python RF/MO 求解和 P4 overlay 编排层、JSON Schema、artifact store、缓存、CLI、双语报告、验证语料和用户文档。
- 新产物通过稳定 ID 和 digest 只读引用现有 SourceIRBinding、ModuleFacts v2、EffectSummary v1、ThreadContextGraph v1、PublicationRiskReport、BoundedObjectProvenanceGraph、RootDrivenAnalysisPlan、ThreadEntryRootOverlay、ConcurrentAccessCandidateGraph 和 AnalysisDemandGraph；不请求 A6 时既有流程保持可用。
- 继续使用项目锁定的 GCC/Clang/LLVM 21 工具链；不新增在线、SSH、专有工具、目标程序链接或执行依赖，也不把成功编译、零 finding 或外部工具结果解释为并发安全证明。
