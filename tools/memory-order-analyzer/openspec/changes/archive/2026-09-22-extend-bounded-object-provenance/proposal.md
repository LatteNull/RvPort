## Why

现有分析已经能够从 AST 识别字段声明、从 LLVM IR 计算常量 GEP 偏移，并在直接调用中传播部分参数和返回关系，但尚不能稳定表达“某个运行时基对象实例的某条子对象路径”。这会使 C `struct/union`、嵌套指针、C++ `this`、对象字段和 mutex 字段在跨 TU 组合时停留在 candidate/unknown，甚至存在把同一 `FieldDecl` 对应的不同对象实例错误合并的风险，因此需要在 A4 之后补齐受限、可审计的对象 provenance 证据层。

## What Changes

- 这是运行时分析实现 change，而非仅文档变更；同时先把路线图中 A4 已通过 required gate、同步主规格并于 2026-09-21 归档的状态修正为事实状态。
- 新增独立版本化的 `BoundedObjectProvenanceRequest`、`SourceObjectPathFacts`、`LLVMObjectProvenanceFacts`、`BoundedObjectProvenanceGraph` 和报告协议，不修改 P1–P4、A1–A4 既有协议及报告语义。
- 在 GCC/Clang 的 C11、C17、C++17、C++20 范围内，建立“基对象实例 + 子对象路径 + 地址空间 + 调用/分配实例”的身份模型；字段声明不得直接充当运行时对象实例。
- 使用 Clang AST 的 `MemberExpr`、`CXXThisExpr`、record layout 和 canonical declaration/type 提取 C `struct/union`、C++ `this`、对象字段、指针字段及 mutex 字段的源码路径事实；C 和 C++ 保持独立 profile、规则和验证分母。
- 使用 LLVM 21.1.8 的 DataLayout、ValueTracking、BasicAA/AAResults、MemorySSA、DominatorTree 和 CaptureTracking 构造只读局部 provenance 证据，支持有限 `phi/select/cast/GEP` 和指针字段的受限 store/load 传播。
- 复用 A1 精确实体解析和 P2 直接调用采用/实例身份，在确定直接调用下组合参数、返回值与 C++ receiver/`this`，形成跨 TU 有限候选；compile database 不被解释为完整链接图。
- 每个值保留带 guard 的有限候选集合，严格区分 must、may、unknown；union 成员按重叠存储处理，候选截断、未知 clobber、生命周期、ABI/profile、scope 或调用目标缺口必须传播 partial/unknown。
- 提供确定性 CLI、内容寻址缓存、候选相关完整性、预算、双语 detail/limitation/suggestion，以及面向 A4/P4 的加法式 adapter；A5 自身不得生成 reads-from、synchronizes-with、happens-before、风险消解或全程序安全结论。
- 堆对象、容器内部别名、虚调用、通用函数指针、任意指针算术、通用 points-to 和外部 SVF/PhASAR 集成不在本 change 内；后者仅保留为后续独立版本、许可证、性能与精度评估项。
- 增加四语言独立 fixture、truth 分母、诊断断言和 A4 回归，覆盖单/跨 TU、无 debug、AST+IR、IR-only、AST-only、开放 scope、clobber、预算、缓存，以及“不同实例的同名 mutex 字段不得合并”和“同一实例经直接 wrapper 可精确绑定”。
- 所有新增、修改或复用的自有代码同步提供正常、边界、异常与 partial/unknown 单元测试；项目整体、实现语言及每个受影响模块的行覆盖率和分支覆盖率均至少 90%。

## Capabilities

### New Capabilities

- `bounded-object-provenance`: 定义 AST/LLVM 有界对象 provenance、有限候选域、子对象路径、跨 TU 直接调用组合、证明边界、协议、缓存、预算、CLI 和双语报告。

### Modified Capabilities

- `analyzer-unit-test-quality`: 增加 A5 自有代码单元测试、四语言 truth、对象实例/字段/跨 TU/降级模式回归和整体、实现语言、逐受影响模块双 90% 覆盖率门禁。

## Impact

- 影响 Clang LibTooling source worker、LLVM C++ worker、Python 跨 TU 调度与组合层、schema/引用校验、artifact store、缓存、CLI、报告和验证语料。
- 新产物通过 digest 引用现有 SourceSemanticFacts、ProgramEntityIndex、SourceIRBinding、ModuleFacts v2、LocalAnalysisFacts/LocalEvaluationResult、EffectSummary v1 及可选 A3/A4/P4 产物；既有产物在未请求 A5 时保持完全可用。
- 继续锁定 LLVM/Clang 21.1.8；不新增运行时外部依赖，不依赖 SSH、ARM DevKit、SVF、PhASAR、目标程序链接或执行。
- A5 的精确结果可为 A4 mutex identity 和 P4 object identity 提供额外证据，但 adapter 只能在依赖、候选和完整性全部满足时采用，且不得反向改变既有协议语义。
