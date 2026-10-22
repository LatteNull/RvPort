## Context

P1 已保存原始 IR 值、GEP、phi/select、内存访问和字节范围；P2 已提供 global/parameter/local 对象、局部求值、私有栈槽传播、直接调用采用、参数和返回替换；A1 已提供严格的跨 TU entity index、SourceIRBinding 和全局对象 overlay；A4 已能在对象 lineage 完整时构造受限 mutex/RAII 证明。当前断点是这些层没有共同表达“某个运行时基对象实例的某条子对象路径”：AST `MemberExpr` 只落到 `FieldDecl`，A1 可为 field entity 分配 program object key，却不能把声明相等解释为实例相等；LLVM pointer walker 主要处理 constant GEP/bitcast，A4 provenance 又只是受限 operand 图遍历。

本 change 同时服务 C11/C17 与 C++17/C++20。C 路径必须独立支持 `struct/union`、多级指针、C linkage、参数和返回值；C++ 路径增加 `this`、对象/指针/mutex 字段，但不得使 C 依赖 C++ AST 或标准库 profile。分析仍是 compile-only、显式 scope、逐 TU AST/BC；`compile_commands.json` 只提供重放命令，不提供完整链接图。实现锁定 LLVM/Clang 21.1.8，并保持 P1–P4、A1–A4 的版本、缓存和报告语义不变。

## Goals / Non-Goals

**Goals:**

- 新增独立、版本化、内容寻址的 A5 请求、AST 路径事实、LLVM 局部 provenance 事实、跨 TU 图和双语报告。
- 将 program entity、字段声明、LLVM value、storage instance、subobject instance、调用实例和线程实例分离，以显式边关联。
- 复用 Clang record layout 与 LLVM DataLayout/ValueTracking/AA/MemorySSA/DT/CaptureTracking，在不改写 BC 的前提下产生可审计局部证据。
- 对 `phi/select/cast/GEP`、私有指针槽、指针字段 store/load 和确定直接调用执行有界、带 guard 的候选传播，严格区分 must、may、unknown。
- 在 A1 精确 definition、P2 adopted call edge、ABI/profile 和实例证据完整时，跨 TU 组合参数、返回值和 C++ receiver/`this`。
- 为 A4/P4 提供加法式 object identity adapter；只有 A5 exact singleton 可提升既有消费者的对象绑定，缺少 A5 时既有行为不变。
- 对全部新增/修改/复用自有代码执行有效单元测试，并强制项目整体、C++、Python及每个受影响模块行/分支覆盖率至少 90%。

**Non-Goals:**

- 不实现堆分配/placement new/custom allocator、容器/迭代器内部别名、虚调用、通用函数指针、任意 ptr-int 算术、无界数组索引或全程序通用 points-to。
- 不从 A5 生成 reads-from、sequenced-before、synchronizes-with、happens-before、data-race、risk/discharged 或全程序安全结论。
- 不把 TBAA、`noalias`、AA `NoAlias`、AST 类型/名称/字段声明或 `getUnderlyingObjectAggressive` 单独当作跨 TU must-alias/noalias 证明。
- 不引入 SVF/PhASAR，不访问网络、SSH、ARM DevKit，不链接或执行被分析程序；外部 pointer-analysis 后端留给独立 change 评估。
- 不支持 Windows、MSVC 或 clang-cl，不合并生产与开发 Dockerfile。

## Decisions

### 1. A5 使用独立 sidecar，冻结 P1–P4、A1–A4 语义

新增 `BoundedObjectProvenanceRequest v1`、逐 TU 的 `SourceObjectPathFacts v1` 与 `LLVMObjectProvenanceFacts v1`、scope 级 `BoundedObjectProvenanceGraph v1` 和 `BoundedObjectProvenanceReport v1`。请求通过 kind/id/digest 显式引用 source facts、entity index、binding/overlay、ModuleFacts v2、LocalAnalysisFacts/LocalEvaluationResult、EffectSummary v1 和可选 A3/A4/P4 产物。

选择 sidecar 而不是升级 `SourceSemanticFacts v1`、`ModuleFacts v2` 或 `EffectSummary v1`，因为对象路径和 points-to 候选具有独立预算、完整性和失效条件。未请求 A5 时旧 CLI、产物和缓存必须保持语义兼容；A5 产物也不得覆盖旧 artifact。

### 2. 身份采用 storage instance 与 subobject path 的乘积

`StorageInstance` 首版只包含：已解析 global、带 invocation/allocation cardinality 的 stack allocation、形式 parameter/receiver、受审计 system external boundary 和 unknown。形式 parameter/receiver 不是最终存储对象，只有调用点实例化后才能绑定实际候选。

`SubobjectPath` 是有序 segment：record/field canonical entity、字段序号、`.`/`->`、ABI 字节 offset/size/alignment、常量数组下标和 union overlap group。`ObjectInstance` 由 scope、profile、storage、path、address space、invocation/lifetime identity 组成。字段声明只标识路径 segment；`a.mutex` 与 `b.mutex` 即使引用同一 `FieldDecl`，只要 storage instance 不同就必须得到不同对象身份。

C union 的不同成员共享 overlap group；成员名或类型不同不能证明 disjoint。C/C++ struct/class 只有在同一 exact base、DataLayout/record layout 一致且半开字节区间不重叠时才能发布局部 disjoint。pointer field subobject 与 load 后的 pointee 是两个身份，禁止把字段槽本身当作所指对象。

### 3. AST worker 只发布语言路径事实，不发布运行时 alias 结论

`SourceObjectPathFacts` 复用相同 compilation profile 和 physical TU identity，读取 `MemberExpr::getBase()/isArrow()/getMemberDecl()`、`CXXThisExpr`、`DeclRefExpr`、地址/解引用、显式/隐式 cast、conditional expression、return、call argument，以及 `ASTContext::getASTRecordLayout()`。它保存完整基表达式、嵌套字段路径、canonical declaration/type、布局、source range、宏 spelling/expansion 和 C/C++ 规则。

AST worker 对不完整类型、柔性数组、位域、匿名 record、union、继承、宏或 layout 缺口显式分类。首版允许普通 C record 和无歧义 C++ 非虚数据成员；虚基、多重继承调整、重载间接选择等未完整建模形状进入 frontier。AST-only 仅能输出 source candidate、实体和路径，不能发布 runtime object、alias/noalias 或消费者 proof。

选择独立路径事实而不是修改 A1 SourceSemanticFacts，是为了保留已归档 A1 的 schema 和绑定语义；两者以 source node/entity 引用连接。

### 4. LLVM worker 复用分析 API，但将每次关键查询登记为证据

`LLVMObjectProvenanceFacts` 在原始、已 hash/parse/verify 的 BC 上只读构建 DataLayout、DominatorTree、LoopInfo、AssumptionCache、TargetLibraryInfo、BasicAA/AAResults、MemorySSA 和 CaptureTracking。ValueTracking 使用 `getUnderlyingObject(s)`、`GetPointerBaseWithConstantOffset`、`stripAndAccumulateConstantOffsets` 及受支持的 returned-argument 规则提取 root/offset；不以正则解析 IR，不运行会改写原始 IR 的优化 pass。

每个 AA query 保存两个 `MemoryLocation` 的 value、size、address space、上下文、结果和分析配置；每个 MemorySSA 关系保存 use/def/MemoryPhi、walker clobber、支配与候选边；capture 查询保存 mask、use budget 和结果。LLVM API 的结果只是局部证据：`MayAlias` 保留 may，AA `NoAlias` 仅适用于该函数内查询，不能单独生成跨 TU canonical identity。

### 5. 候选域显式区分 bottom、must、may 和 unknown

内部 lattice 包含未处理 `bottom`；合法发布值只能是：`must` singleton、非空有限 `may` candidates 或带非空原因的 `unknown`。每个 candidate 包含 ObjectInstance、可选 byte range、guard 合取、proof 引用、opposed evidence 和依赖切片；候选之间为析取，不任选一项。

`phi/select` 合并可行候选并保留 predecessor/condition guard；只有所有可行分支在规范化后均为同一 exact object/path/range 且没有相关缺口时才可折叠为 must。候选、guard、路径深度、循环、关系或工作量超限时不得截取为假精确集合，而应保留已有事实并将相关值升级为 unknown/partial。

### 6. 指针字段传播要求唯一到达定义和无 clobber 证据

对于私有栈槽或对象 pointer field 的 load，只有 base/path/range exact、MemorySSA 找到唯一支配 store、AA 排除其他可达 clobber、pointer 未以不受支持方式逃逸、lifetime 有效且路径 guard 一致时，才传播 store value。MemoryPhi 或多个合法 store 产生带 guard 的有限候选；unknown call、MayAlias 写、并发共享字段写、volatile/atomic pointer load、部分覆盖、lifetime end 或 capture 超限使相关结果 unknown。

该规则只推导“局部值可能来自哪些对象”，MemorySSA 不被解释为跨线程 reads-from/HB。对多级指针逐次应用 load-hop 预算；一个字段槽精确并不意味着其 pointee 精确。

### 7. GEP/cast/范围传播以 ABI 和常量证据为边界

constant GEP 在 AST/IR layout 相容时追加路径和字节偏移；非结构化但可计算的常量 offset 可保留 byte-path，并标记缺少 source field。有限 dynamic index 只有在值域、element size、bounds 和候选预算全部可证明时展开 may candidates，否则 unknown。bitcast 只在 pointer representation/address space 兼容时保留 provenance；addrspacecast、inttoptr/ptrtoint、非线性算术或 offset overflow 默认 unknown。

GEP 可计算不等于 in-bounds、对象存活或 alias 证明；这些条件分别保存。访问 overlap/disjoint 使用同一 exact storage 和半开字节区间，parameter 间或不同 unknown roots 不默认 disjoint。

### 8. 跨 TU 只组合确定直接调用、参数、返回和 receiver

跨 TU edge 必须同时具备：显式 scope 成员、A1 唯一兼容 definition/实体、P2 合法 adopted direct-call edge、支持的 C ABI/调用约定/属性、实参与形参基数一致、profile/target/DataLayout 相容以及 invocation/context 预算。调用点将 actual candidate 域代入 callee formal parameter 或 C++ receiver；callee 返回的 parameter-derived/global-derived path 再绑定回 caller，保留 offset/path、guard、proof 和实例身份。

返回 callee local alloca 为 expired/unknown；heap/allocator return、间接/虚调用、vararg、sret/byval/inalloca/preallocated、未知 operand bundle、scope 外定义、weak/COMDAT 冲突或递归未收敛均不得精确替换。递归采用 SCC/迭代预算和单调 may/unknown 合并，不以空摘要表示无对象关系。

### 9. 四种证据模式和候选相关完整性保持保守

AST+IR 可在所有依赖闭合时发布 must/may；IR-only 可保留 LLVM local storage/root/byte range，但缺少语言字段路径时相应 source completeness 为 partial；AST-only 只能发布 source candidate；AST 与 IR 均不可用时为 failed。模式按 TU 记录，scope 级图按候选依赖切片传播，不相关失败 TU 不阻塞独立候选。

完整性分母至少包括计划/完成 TU、source path、LLVM value/query、call edge、candidate、object/path binding 和 consumer adapter。零候选必须区分“完整证明没有相关对象”与“输入/预算/绑定失败未形成候选”，后者不得返回 complete empty。

### 10. A4/P4 只消费 exact adapter，A5 不越过内存模型边界

A5 为消费者输出独立 adapter view。A4 只有在 mutex base/path 为 exact singleton、profile/ABI/lifetime 完整且没有相关 frontier 时，才能将其映射到既有 `MutexInstance`；may/unknown 保持 `mutex-provenance-ambiguous`。回归必须证明两个类/struct 实例的同一 mutex `FieldDecl` 不会合并，同一实例经直接跨 TU wrapper 可保持身份。

P4 可使用 exact object identity 改善 flag/payload 对象匹配，但 reads-from、发布顺序、SW/HB 和 risk/discharged 仍完全由 P3/P4 既有规则建立。A5 adapter 不新增消费者结果类别、退出码或“安全”结论，缺少 A5 时旧语义不变。

### 11. 请求、缓存、预算、CLI 和报告独立版本化

请求预算覆盖 TU、source/IR node、path segment/depth、value、candidate、guard、load hop、AA query、MemorySSA clobber walk、capture use、call context、SCC iteration、relation、output bytes 和 worker/request wall time。耗尽记录 category、hit/limit、受影响依赖和双语建议，保留已有 may facts并使相关切片 partial/unknown。

缓存键包含协议/schema、实现 identity、LLVM/Clang、scope/profile/target/DataLayout、全部依赖 digest、模型/adapter 版本和预算类别。缓存命中重新验证引用闭包；陈旧、损坏、失败和 timeout 结果不得作为成功语义命中，cold/warm semantic digest 必须一致。

A5 CLI 接受显式 request/artifact store/output，确定排序输出 graph/report；退出码 `0` 表示请求完整，`2` 表示 partial/unknown/frontier，`1` 表示请求无效或全部不可用，A5 不使用风险码 `3`。面向用户的 detail/limitation/suggestion 同时提供中文和英文，机器 code/identity 与翻译分离。

### 12. 文档与验收产物分离设计、实测和限制

新增 `doc/BOUNDED_OBJECT_PROVENANCE.md` 说明协议、身份、模式、证明边界和使用方法；新增 validation 文档及机器可读 acceptance JSON，记录锁定环境、精确命令、版本/hash、测试数、四语言 truth、TP/FP/FN/abstention、覆盖率 hit/total、性能/内存/cache、排除项和报告路径。路线图只记录当前阶段状态，不把 proposal 视为已实现。

成功 compile、零 finding、AA query 成功或样例 exact match 都不得描述为并发安全证明。SVF/PhASAR 只在“后续候选”中记录，不声称已兼容 LLVM 21.1.8。

## Risks / Trade-offs

- [AST layout 与 LLVM DataLayout/profile 不一致造成错误字段绑定] → digest 绑定同一 compilation profile/target/ABI，偏移、大小或 physical TU 不一致即拒绝组合。
- [FieldDecl identity 合并不同运行时对象] → 字段只作为 path segment，ObjectInstance 必须包含 storage/invocation；单测覆盖两个实例同字段正反例。
- [MemorySSA/AA 的 may 信息被误升为 points-to must] → 查询结果显式登记，只有唯一支配 store、NoAlias clobber exclusion 和完整路径才 exact；MayAlias/MemoryPhi 保留 may/unknown。
- [候选、路径或调用上下文爆炸] → 所有维度独立预算，超限不截断为有限精确集，按候选相关切片传播 partial。
- [优化或无 debug 导致 AST/IR 映射缺失] → entity/ABI/IR local 证据可独立保留；缺少唯一表达式/路径绑定时不强制 exact。
- [C++ 对象布局过于复杂] → 首版限制普通非虚字段；虚基、多重继承调整和容器内部别名进入 frontier，不能用字段名猜测。
- [A5 改变既有 A4/P4 结果而难以回滚] → sidecar 和 adapter 可独立关闭；旧协议黄金回归及无 A5 请求回归为 required gate。
- [LLVM API 版本演进] → 继续锁定 21.1.8 并记录 API/profile identity；升级工具链需要独立 change 和重新验证。

## Migration Plan

1. 先合入 schema、引用验证、身份模型和 CLI 空编排，使旧协议回归保持不变。
2. 增加 AST `SourceObjectPathFacts` 与 LLVM `LLVMObjectProvenanceFacts`，分别完成单元和 fixture 门禁后再启用组合。
3. 实现候选 lattice、局部 pointer-field 传播、直接调用参数/返回/receiver 组合和 scope 图；默认不接入 A4/P4。
4. 增加 A4/P4 exact-only adapter、四语言 truth、no-debug/降级/预算/cache 回归和用户文档。
5. 在全新输出目录完成全部 required gate 后才同步/归档；回滚时禁用 A5 CLI/adapter并删除独立缓存，不迁移或重写 P1–A4 产物。

## Open Questions

- 首版有限 dynamic index 的默认候选数、pointer-load hop 和 call-context 限额由实现期基准决定；规格固定“显式预算、超限 unknown”，不预设未经测量的数值。
- 普通非虚 C++ 基类字段若 LLVM 21.1.8 与 AST layout 可形成双重精确证据，可作为实现期可选支持；required truth 不依赖继承形状。
- SVF/PhASAR 是否值得引入只根据 A5 truth 中持续 abstention、真实工程规模和许可证/版本实验决定，本 change 不预先选择后端。
