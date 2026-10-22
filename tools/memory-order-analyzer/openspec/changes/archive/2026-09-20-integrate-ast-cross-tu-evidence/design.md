## Context

现有流水线以 `compile_commands.json` 重放各 TU，生成 BC、P1 `ModuleFacts/RunReport v2`、P2 `EffectSummary v1`、P3 线程上下文和 P4 单次发布风险结果。它能保留每个模块中的 LLVM 事实，但跨 TU 对象仍主要依赖 artifact-local identity、符号名和有限 debug 信息。P5 的 8-case 人工真值显示 exact match `3/8`、TP=3、FP=0、strict FN=7、abstention `8/8`：部分风险已被发现，但跨 TU flag/payload、wrapper、pthread handle 和请求级完整性无法组成可信的端到端证据链。

AST 可以补充源语言实体、声明/定义关系、linkage、规范类型、调用和控制结构，但不能替代 IR 中实际生成的内存访问、优化后控制流、atomic ordering 或执行关系。因此本 change 采用“源语义索引 + IR 事实 + 显式绑定”的双层架构，不构建巨型合并 AST，也不把 `compile_commands.json` 误当 target/link 图。

约束如下：

- 输入限定 GCC/Clang 的 C11/C17/C++17/C++20；排除 MSVC/clang-cl。
- 开发容器锁定 LLVM/Clang 21.1.8；AST 与 BC 必须来自同一规范化编译 profile。
- P1–P5 已发布协议继续可读，旧命令默认行为不变；新增能力通过独立协议和显式依赖进入。
- 单元和固定验证必须离线，不依赖 SSH、ARM DevKit、GenMC、herdtools7 或目标程序运行。
- 新增或修改的自有 C++/Python 模块以及项目整体、各语言和受影响模块的行/分支覆盖率均至少 90%。

## Goals / Non-Goals

**Goals:**

- 逐 TU 提取稳定、可审计的源码实体、引用、直接调用、初始化/赋值、控制依赖线索、pthread 与 atomic 源语义事实。
- 在显式 scope 内解析跨 TU 声明/定义和对象身份，严格区分外部链接、内部链接、匿名 namespace、C tentative definition、C++ inline/template/ODR、weak/COMDAT 与 TLS。
- 将源实体绑定到 LLVM function/global，并将源表达式映射到一个或多个 IR 指令候选，保存 exact/candidate/ambiguous/unresolved 状态和证据。
- 以 supplemental overlay 改善 P2–P4 的跨 TU 对象、直接 wrapper、pthread callback/handle 和候选相关完整性，不改变 AST/IR 各自能证明的语义边界。
- 用 P5 人工真值和真实工程 profile 量化准确性、abstention、完整性、性能、内存与缓存变化。

**Non-Goals:**

- 不导入 CMake target/link 图；`compile_commands.json` 仍只表示 TU 重放记录，显式 scope 仍由调用方给出。
- 不实现通用 points-to/alias analysis、间接调用求解、`std::thread`/RAII、线程池或自定义同步原语。
- 不实现 fence、RMW/CAS release sequence、consume、通用 happens-before 求解或通用 data-race 检测。
- 不使用 AST 推断优化后未生成的操作，也不以行号、statement 文本顺序或 `EffectSummary.order` 猜测执行关系。唯一例外是：同一 `CompoundStmt` 内相邻 expression statement 可由 Clang 语言语义产生独立、精确的 source `sequenced-before` 关系；遇到 declaration/control/loop/return 等其他 statement 必须断开，不跨节点串接。只有关系两端都精确投影到同一线程上下文中的实际 IR memory effect 时，P4 才可把它作为局部 must-before 补充。该补充不得生成 `reads-from`、`synchronizes-with`、`happens-before` 或安全结论。
- 不把所有 TU 导入一个 ASTContext；ASTImporter 仅保留为未来受限按需方案。
- 不在本 change 合并开发 Dockerfile 与生产 Dockerfile。

## Decisions

### 1. 使用逐 TU LibTooling 提取器，而不是 JSON AST dump、libclang 或全量 ASTImporter

新增 C++ worker `memory-order-source-worker`，使用与项目 LLVM 21.1.8 相同版本的 LibTooling/ASTMatchers/RecursiveASTVisitor。每个进程只处理一个规范化 TU 请求并在 stdout 输出一个严格 JSON 文档，stderr 仅写日志；Python orchestrator 负责计划、隔离、缓存和汇总。

选择 LibTooling 是因为需要完整 canonical declaration、linkage、mangling、类型、模板/匿名 namespace 和 SourceManager 信息。JSON AST dump 不作为稳定生产协议；libclang API 较稳定但暴露的语义不足；全量 ASTImporter 会带来版本耦合、污染 ASTContext 和导入错误传播，不适合首版规模边界。

### 2. AST 与 BC 共享一个不可变 `CompilationProfileIdentity`

在现有编译记录规范化结果上增加 profile identity，至少包含：原始编译器家族/版本、被重放的 Clang 版本、language standard、target triple、data layout、sysroot、resource dir、include 路径、宏、强制 include、语言/ABI 选项、工作目录、主文件内容 hash、路径映射和规范化 argv digest。

同一 TU 的 AST 与 BC 请求必须引用同一个 profile identity。对 GCC 记录，系统只转换已登记的 driver/diagnostic/output 参数，不猜测不兼容扩展；Clang 语义重放失败、产生不可接受诊断或 profile 不一致时，该 TU 为 partial/failed，并保留原始 GCC 身份与原因。一次成功 BC 编译不能覆盖失败的 AST profile，反之亦然。

### 3. 定义四类独立 v1 协议及不可变引用

- `SourceSemanticRequest/SourceSemanticFacts`：单 TU 输入与 AST 原始事实。
- `ProgramEntityIndexRequest/ProgramEntityIndex`：显式 scope 内实体分组、定义选择、canonical entity/object key 与歧义。
- `SourceIRBindingRequest/SourceIRBinding`：源实体/表达式与 P1 LLVM facts 的绑定关系。
- `AstAssistedAnalysisRequest/AstAssistedAnalysisReport`：计划分母、预算、依赖、缓存、双语诊断、frontier 和下游消费结果。

每个协议使用严格 schema、`schema_version=1`、kind、producer/policy version、canonical digest、确定性排序和显式 dependency references。未知字段、未来版本、混合 profile、悬空引用、digest 替换或重复身份均拒绝。原始 P1/P2/P3/P4/P5 文档不增加字段；若下游请求需要表示新依赖，则创建 additive 新版本/包装请求并保持旧 reader 与 CLI 路径。

### 4. 原始 AST 节点与程序实体分离

`SourceSemanticFacts` 保存 TU-local node identity，使用 `profile_id + physical_tu_id + node_kind + stable source anchor + ordinal`，并登记 canonical declaration、definition、USR、qualified name、mangled name、language linkage、storage/linkage、TLS、visibility、canonical type、source spelling/expansion range、宏栈和包含文件 hash。

原始节点不跨 TU 合并。`ProgramEntityIndex` 另外产生 program entity 和 abstract object identity，使“复用摘要上下文”“源实体”“LLVM 对象”“调用/线程实例”保持不同命名空间，避免将分析复用误当运行时实例同一性。

### 5. 跨 TU 解析使用分层 key 和保守定义选择

解析顺序为：

1. 检查显式 scope、语言、target/ABI 和 profile 兼容性。
2. 对 external language linkage 使用 USR、mangled name、canonical type、entity kind 与 ABI 属性形成候选组。
3. 对 internal linkage、`static` 和匿名 namespace 加入 physical TU identity，永不跨 TU 合并。
4. 对 C tentative/common definition、C++ inline/template/weak_odr/linkonce_odr、weak/COMDAT/TLS 应用显式分类规则。
5. 只有存在唯一兼容定义或规则允许的等价定义集合时输出 resolved；无定义为 unresolved；冲突定义、类型/profile 不兼容或无法证明等价为 ambiguous/conflict。

USR 是重要证据但不是唯一身份。仅名称相同、debug 名称相同或 P1 object key 相同不得跨 TU 合并。首版不替代链接器解析；缺少 target/link 图时 weak/COMDAT/ODR 只在受限规则内合并，其余进入 frontier。

### 6. AST–IR 绑定分实体级和表达式级，禁止伪精确

实体级绑定优先使用：profile/TU identity、mangled name、LLVM linkage/visibility/TLS/comdat、canonical type/ABI 大小和定义/声明角色。唯一且全部关键证据一致可为 exact；存在多个兼容值或证据缺失则为 candidate/ambiguous。

表达式级绑定使用 debug location、spelling/expansion range、inlined-at 链、所属函数、object binding、opcode/atomic ordering 和局部控制上下文。一个源码表达式可映射多个 IR 指令，多个源码构造也可折叠到一个指令；映射始终保存基数和证据，不能因最近行号或唯一行号自动标 exact。同一行包含多个表达式时，只有 debug column 落在受限 source range/列窗口内且对象、opcode 与上下文一致才保留候选；无 column 或仍有多个对象时必须降级。无 debug 时实体级绑定仍可用，表达式级映射明确 incomplete。

绑定结果只说明“该源实体/表达式与该 IR 事实相关”。内存访问是否存在、ordering、执行顺序、reads-from 和同步关系仍由 P1/P3/P4 的 IR 证据建立。

### 7. 通过 `CanonicalObjectOverlay` 接入 P2–P4，候选相关地传播完整性

Python 层从 `ProgramEntityIndex + SourceIRBinding` 派生不可变 `CanonicalObjectOverlay`，把多个 artifact-local object key 映射到一个 program object key，并附 resolution/binding evidence。P2 摘要、P3 线程模型和 P4 发布协议只在显式 AST-assisted 请求中消费它；旧请求继续走原路径。

下游组合遵循：

- resolved + exact/candidate 但唯一可判定的对象关系可以补充跨 TU direct wrapper、flag/payload、pthread callback 和受限 `pthread_t` 声明/赋值 provenance。
- ambiguous/conflict/unresolved 不得选任一候选；相关 candidate 为 partial/unknown，并保留 frontier。
- 与某 publication candidate 无依赖关系的其他 TU 缺口不得自动清空该 candidate；相关依赖通过切片闭包判定。
- 任何 AST overlay 均不得直接形成 IR execution-order、reads-from、synchronizes-with 或 happens-before 边。

### 8. 请求、预算、缓存和失败保持分层

新增 CLI `index-source-evidence --request --artifact-store --output --worker`。输出目录必须新建且为空，stdout 只输出最终合法报告 JSON；无效请求/完全不可用退出 1，可用但 partial/unknown/预算耗尽退出 2，完整成功退出 0。风险退出码仍由既有 P4 命令负责，不与索引结果混用。

预算至少限制计划 TU、AST 节点/引用、实体组、绑定候选、wall time、worker output 和下游依赖切片。预算耗尽保留已完成产物、准确分母和未处理 frontier。

缓存分为 TU source facts、entity index、IR binding 和 overlay 四层；key 包含 schema/producer/policy、profile、scope、源码/include hash、P1 dependency digest 和预算类别。缓存命中必须重新校验 schema、引用和 digest；cold/warm semantic digest 必须一致，时间、路径与 cache counters 不进入 semantic digest。

### 9. 以固定语料和受影响模块覆盖率作为交付门禁

新增 C/C++ 单元测试覆盖 AST 提取器的声明/定义、linkage、USR、类型、宏、source range、直接调用、pthread/atomic 事实及失败诊断。Python 单元测试覆盖 schema、索引解析、歧义、绑定基数、overlay、候选相关完整性、预算、缓存损坏、CLI 退出码和双语字段。

离线集成矩阵至少覆盖 C11/C17/C++17/C++20、GCC/Clang 记录、单/至少三物理 TU、external/internal/static 同名、匿名 namespace、C tentative、inline/template/ODR、weak/COMDAT/TLS、宏、不同 profile、debug/no-debug、跨 TU wrapper、pthread handle、路径重映射和预算。既有 P5 truth 不原地修改；新增 suite version 比较旧 IR-only 与 AST-assisted 结果，分别报告 exact match、TP/FP/FN、strict recall、abstention 和每层完整性。

质量入口必须统计未加载源码，报告项目整体、C++、Python 和每个受影响模块的 line/branch hit/total，全部至少 90%。集成测试、真实工程运行或编译成功不能补入单元覆盖率。

### 10. 文档按证据层维护

- `README.md` 与 `doc/README.md`：入口、阶段状态、归档/active change 和非安全证明声明。
- `doc/IMPLEMENTATION_ROADMAP.md`：P5 后续优先级、AST+IR 阶段边界及仍未实现的 B1/std::thread/pointer/fence/RMW。
- 新增 `doc/AST_CROSS_TU_EVIDENCE.md`：协议、实体解析、绑定、CLI、完整性和示例。
- 新增 `doc/AST_CROSS_TU_EVIDENCE_VALIDATION.md`：实际命令、环境/hash、测试/覆盖率、truth 指标、性能/缓存和限制。

文档只记录实际观察；未运行的 profile 标为 not_run。面向用户的诊断示例同时展示中文和英文字段。

### 11. 验收后 FN 纠偏使用集合级唯一性，不放宽内存模型证明

2026-09-20 对实际产物的逐层审计显示，P3 已经建立两个跨 TU 风险样本的 producer/consumer `ThreadInstance`、MHP 候选和 IR memory effects，但 P4 因 flag/payload overlay 降级为 candidate 而产生零个 publication protocol。这不是 fence/RMW 或通用 pointer analysis 缺口，而是首版实现的绑定与完整性组合错误。

纠偏规则为：

1. `CanonicalObjectOverlay` 首先按 `(artifact_key, id, kind)` 对 LLVM target 去重。同一 source declaration 从多条 binding 路径到达同一 IR symbol 不得被计为多个定义。
2. exact 判定基于 program entity 的集合级证明：resolved entity、唯一 distinct 非 declaration LLVM definition、每个相关 TU 的兼容 artifact-local symbol 以及无 ABI/profile/linkage/TLS/visibility 冲突。头文件 `extern` declaration 在定义 TU 中只能指向该 LLVM definition 时，单条 binding 可保留 candidate/角色差异，但不得单独否定已由唯一定义证明的 overlay。
3. scope 内只有声明且由已建模系统 API 提供的 `pthread_create`/`pthread_join`、标准库枚举和类似系统头实体记为 external-boundary evidence；它们不是 program object 定义缺失，不得污染无关 flag/payload candidate 的完整性。未识别的外部声明仍 unresolved。
4. 请求级 source report 仍可为 partial，但 P4 只用 candidate-relevant dependency slice 决定某个候选是否可评价。无关系统实体或其他 TU 缺口不得清空已建立候选。
5. 当 scope 中已有可用 atomic/payload/thread facts 却生成零个 protocol 时，P4 必须输出稳定中英文 `publication-candidate-unresolved` 诊断和结构化缺失原因，不得以空 frontier 返回 inconclusive。
6. 修复后必须在同一 reviewed truth 上使 `c11-risk-multi` 和 `cpp20-risk-multi` 从 unknown 变为 risk，不新增 FP；同时 fence/CAS 的既定 unsupported/unknown 边界不变。
7. declaration-only TU 若没有引用某个外部对象，Clang/LLVM 可以不发射对应 LLVM declaration。只要该 source declaration 属于已解析 program entity、全 scope 仍有唯一兼容 LLVM definition 且不存在 ABI/profile/linkage/TLS/visibility 冲突，这个“未发射声明”是中性证据，不得伪造缺失定义；有引用但缺失对应符号、未知外部实体或多个定义时仍保持 unresolved/ambiguous。
8. 对 `cpp20-risk-multi` 的“发布早于 payload 写”证明只能消费 `SourceSemanticFacts` 中同一 `CompoundStmt` 相邻 expression statement 的精确 source sequence，并将两端分别绑定到同一线程上下文中的真实 IR effect。缺失 column/range、遇到 declaration/control/loop/return、跨调用或绑定不唯一时不产生该局部顺序；它不修改 P1/P2/P3 协议，也不得提升为 SW/HB。

## Risks / Trade-offs

- [GCC 扩展无法由 Clang 等价解析] → 保存原始 compiler profile 与重放诊断，标记 partial/unsupported，不改写参数伪造成功。
- [Clang C++ API/ABI 不稳定] → 仅在锁定 LLVM 21.1.8 开发容器构建和验收，协议与内部 AST 类解耦，升级必须产生独立 change。
- [USR 在某些实体上为空或跨 profile 不稳定] → 使用 USR+mangling+linkage+type+profile 的复合证据并保留 unresolved；不以名称回退为 exact。
- [ODR、weak/COMDAT 与真实链接选择不确定] → 缺少 target/link 图时只应用白名单等价规则，其余 ambiguous；未来 B1 可补 target scope。
- [debug location 粗糙或优化折叠导致错误表达式绑定] → 允许一对多/多对一，debug 仅作候选证据，使用实体、opcode 和上下文交叉验证。
- [AST 规模增加时间和内存] → 逐 TU 子进程、分层缓存、显式预算和无巨型 AST；真实工程 cold/warm 基线量化成本。
- [下游把 AST 关系误当内存模型证明] → 协议区分 source relation、binding relation 和 IR proof relation；schema/测试禁止 overlay 生成 HB/RF/SW 边。
- [新模式改变旧结果且难以回滚] → 旧协议/CLI 默认路径保持不变，AST-assisted 以显式请求和独立产物启用，可删除新产物回退到 IR-only。

## Migration Plan

1. 增加 Clang 21 LibTooling 构建依赖、协议 schema 和纯 contract 测试，不接入下游。
2. 实现逐 TU source worker、Python orchestrator、预算/缓存和固定提取语料。
3. 实现 program entity index 与 linkage/ABI 解析，先发布独立报告。
4. 实现 AST–IR binding 与 canonical object overlay，完成无 debug/歧义行为测试。
5. 以显式 AST-assisted 请求接入 P2–P4；旧请求和旧 fixture 必须保持相同 semantic digest。
6. 扩展 P5 suite/profile，运行全量单元、覆盖率、离线真值和 TinyCThread cold/warm 验收，发布验证文档。
7. 若任一步失败，停用新 CLI/请求并保留独立产物供诊断；无需迁移或回写已有 P1–P5 artifact store。
8. 在归档前执行 FN 纠偏：修复 overlay/boundary/completeness/diagnostic，对两个跨 TU 样本运行针对性回归，再重跑全量单元、逐模块覆盖率、AST/IR truth 矩阵、TinyCThread 和文档/OpenSpec 门禁。

## Open Questions

- TinyCThread 是否提供足够的 external/internal/weak/ODR 真实样本？默认以固定合成语料承担语义真值，真实工程只验证规模与可审计样本，不据此延伸准确率。
- LLVM 21 对 C tentative/common 与不同优化级别的最终 GlobalValue 形态是否需要额外白名单？实施时以固定 fixture 记录，无法唯一绑定的形态保持 ambiguous，不阻塞基本外部链接路径。
- P2–P4 现有请求 schema 是否能通过通用 dependency 引用表达 overlay？若不能，创建 additive 请求版本或包装请求，禁止修改 v1/v2 原义；在首个接入任务中以 schema compatibility test 决定具体版本号。
