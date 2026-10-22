## Context

现有流水线已能从 `compile_commands.json` 重放 GCC/Clang C/C++ TU，生成 BC、P1 `ModuleFacts/RunReport v2`、P2 `EffectSummary v1`、P3 `ThreadContextGraph v1`、P4 单次发布风险结果，以及 A1 的 `SourceSemanticFacts`、程序实体索引、Source–IR binding 和 canonical overlay。A1 解决了受支持 pthread 单次发布模式中的跨 TU 实体与对象证据，但默认流程仍以 BC/IR 产物为后续分析前提，缺少“AST 成功而 BC 或后续阶段失败”时的统一降级协议。

对归档 `memory-model-ir-checker/samples` 的外部回归显示：33 个逻辑程序中 21 个完成分析、5 个编译失败、7 个后续分析失败；已完成项中 `safe/03_pthread_mutex.cpp` 因 `std::lock_guard<std::mutex>` 最终表现为未识别的 `__gthread_mutex_lock/unlock`，P3 没有建立 mutex 边，而 P4 仍输出普通冲突风险。这说明“没有证明同步”被错误地当成“已证明没有同步”。本 change 不实现 RAII 语义，但必须先把这种候选降为 unknown。

约束如下：

- 输入限定 GCC/Clang 用户态 C11、C17、C++17、C++20；Windows、MSVC、clang-cl 明确排除。
- C 与 C++ 使用独立语言 profile、AST 规则、fixture 和真值分母；C 路径不得依赖 C++ 类型或标准库模型。
- AST、BC 和下游分析都不要求原生链接或运行目标程序；`compile_commands.json` 不提供完整 target/link 图。
- P1–P4 与 A1 已发布协议保持可读且原义不变；新能力通过独立协议和 additive dependency wrapper 接入。
- AST 不能替代实际 IR memory effect、atomic ordering、LLVM 局部顺序、RF/SW/HB 证明。
- 日常验收离线运行，不依赖 SSH、DevKit、GenMC、herdtools7 或 sibling checker 实现。

## Goals / Non-Goals

**Goals:**

- 为每个计划 TU 独立采集并保存 AST 与 IR 阶段状态，定义稳定失败分类和证据可用性。
- 提供 AST+IR、IR-only、AST-only、failed 四种可审计模式，并允许同一请求内按 TU、候选和依赖切片混合。
- 在 BC 或后续 IR 阶段失败时保留可信的源实体、跨 TU 关系、控制事实和 source candidate，同时明确缺失的 IR 证明。
- 使未知 mutex、RAII、同步 wrapper 和相关预算缺口成为候选相关的同步 blocker，阻止错误 finding/discharge。
- 保持无关 TU 或无关缺口不影响已闭合候选，完整记录全局与逐候选完整性。
- 以独立 C11/C17/C++17/C++20 验证矩阵、归档误报回归和至少 90% 单元行/分支覆盖率交付。

**Non-Goals:**

- 不实现 `std::thread`、`std::jthread`、`std::async`、线程池或自定义线程运行时。
- 不实现 `std::mutex`/RAII 的完整同步语义；未知 RAII 只作为 blocker。
- 不实现通用 points-to、虚调用、复杂堆别名、fence、RMW/CAS release sequence、consume 或通用 HB/data-race 求解。
- 不从错误恢复 AST、名称、源码邻近或单独 API 拼写产生正式风险、安全、RF、SW 或 HB 结论。
- 不支持 Windows API、MSVC、clang-cl，不修复或纳入相应归档样例。
- 不合并开发/生产 Dockerfile，不修改被分析源码，不自动生成 target scope。

## Decisions

### 1. AST 是并列事实层，不是失败后临时重跑

新增降级编排器对显式 scope 中每个 TU 分别计划 source extraction 与 BC/P1 extraction。二者共享不可变 `CompilationProfileIdentity`、源码/include 依赖摘要和物理 TU 身份，但具有独立状态、预算和产物引用。这样 AST 成功不会掩盖 BC 失败，BC 成功也不会把 AST replay 失败升级为完整。

备选方案“BC 失败后才调用 AST”会使 cold/warm 行为和失败路径改变证据集合，也无法稳定比较正常与降级模式，因此不采用。已有 A1 source cache 可复用，但必须通过显式 digest 引用，不能扫描最新产物。

### 2. 新增独立 v1 协议并保持 P1–P4/A1 原义

新增严格协议：

- `DegradedSourceAnalysisRequest v1`：scope、roots、四语言 profile、阶段预算、所需产物和策略身份。
- `TUEvidenceAvailability v1`：每个 TU 的 source/BC/P1/P2/P3/P4 状态、失败分类、产物 digest 和可用证据。
- `SourceCandidate v1`：仅含源实体、对象候选、线程/同步构造、控制关系、假设、缺失证据和依赖切片，不使用 P4 finding 身份。
- `DegradedSourceAnalysisReport v1`：模式分母、全局/候选完整性、source candidates、只读下游报告引用、缓存/预算、双语诊断和退出状态。

协议使用严格 schema、版本、kind、producer/policy identity、canonical digest、确定排序和依赖引用。旧 RunReport、EffectSummary、ThreadContextGraph、PublicationRiskReport、SourceSemanticFacts 和 AstAssistedAnalysisReport 不增加有歧义的可选字段；需要下游消费时使用 additive wrapper。

### 3. 四种模式按 TU 和候选计算，请求级允许 mixed

单个 TU/候选使用：

- `ast-ir`：可信 AST 与所需 IR/下游证据均可用。
- `ir-only`：IR 证据可用但 AST 不可用；保持现有 IR-only 边界。
- `ast-only`：可信 AST 可用但所需 IR 或下游证据不可用。
- `failed`：AST 与 IR 均不可用，或输入/profile 无法形成可信分析。

请求级报告给出四类精确分母；出现多类时状态为 mixed，而不是选择最乐观模式。候选模式由其传递依赖闭包决定，不由请求全局最差 TU 决定。AST-only source candidate 始终是 partial/unknown，不能进入 P4 finding/discharged 分母。

### 4. 失败分类区分输入无效、重放不兼容、IR 生成和分析阶段

稳定分类至少包括：

- `frontend-invalid`：语法/类型、必需 include、宏或生成输入使前端不能形成可信 AST。
- `profile-replay-incompatible`：GCC 记录无法由锁定 Clang 等价重放，或语言/target/ABI 关键配置冲突。
- `ir-generation-failed`：可信 AST 已形成，但 IR emission/BC verify/serialization 失败。
- `worker-budget`：source、IR 或下游 worker 达到时间、节点、输出或工作量预算。
- `artifact-validation-failed`：schema、digest、引用、profile 或缓存产物校验失败。
- `analysis-stage-failed`：P2/P3/P4 等后续阶段失败，同时保留其具体 stage/code。

每条失败保存 stage、transient/deterministic 分类、原始受限诊断摘要和中英文字段。错误恢复 AST 只有在无 fatal diagnostic、profile 一致且事实提取器明确标为 usable 时才可进入 AST-only；否则为 failed。旧样例中的缺失 `boost`、未声明 API 或无效调用不因存在 partial AST 而获得风险结论。

### 5. AST-only 只产生 source candidate，不复制 P4 判定

SourceCandidate 可以描述直接 pthread/atomic 源构造、C/C++ 实体、C struct/union 或 C++ 字段、宏展开、控制依赖、相邻受限 source sequence 和跨 TU declaration/definition；必须列出未验证的实际 memory effect、ordering、访问范围、线程实例、RF/SW/HB 等缺口。

SourceCandidate 不含 P4 `finding_code`，只使用独立的 `candidate_kind`、`evidence_level=source-only`、`verdict=unknown` 和 `safety=not-established`。即使源码形态看起来明显危险，也不能在本 change 中提升。未来若需要纯源码 lint，必须另立规则 capability 和准确率语料。

### 6. C 与 C++ 事实和验证并列，不做隐式语言折叠

C11/C17 fixture 覆盖直接 pthread create/join/mutex、C linkage、全局与 static、struct/union 字段、宏、`_Atomic` 和 `<stdatomic.h>`；C++17/C++20 覆盖对应 pthread/atomic 形式及未知 RAII blocker。语言标准是 profile 和 cache identity 的组成部分。

实体索引可按已有 C language linkage 规则跨 TU 解析，但不得将 C struct 与 C++ class、C `_Atomic` 与未经证明的 C++ wrapper、或 C/C++ 同名实体自动合并。验证报告分别计算四种 profile，合并汇总不能替代任一语言门禁。

### 7. 未知同步作为一等 `SynchronizationGap`

P3 或适配层为未识别 mutex kind、RAII lifetime、同步 wrapper、锁对象、平衡关系、失败路径和相关预算生成结构化 `SynchronizationGap`，登记调用/对象/线程/路径候选及来源。P4 在冲突/发布候选切片中检查 gap：

- gap 可能覆盖相关访问且不能证明无关时，候选为 unknown，不产生 potential-data-race、publication-order-risk 或 discharge。
- gap 与候选线程、对象、路径和调用闭包可证明无关时，保留现有 assessment，但顶层完整性仍反映 gap。
- 不得仅因 wrapper 名称像 lock 而建立同步，也不得仅因模型不识别而断言无锁。

该规则使 `safe/03_pthread_mutex.cpp` 在本 change 中从 risk 降为 unknown；直到未来 RAII change 建立完整锁证据后才可能受限消解。直接 C pthread mutex 正例继续使用现有支持模型，反例仍可形成风险。

### 8. 候选依赖切片决定降级，不以全局 partial 清空结果

依赖图包含 TU、source fact、entity、binding、object、function/call、thread instance、memory effect、synchronization gap 和 publication candidate。每个正式 assessment/source candidate 保存闭包摘要和 missing evidence。一个 TU 失败只影响依赖它的候选；如果无法证明某缺口与候选无关，保守视为相关。

计划、完成、失败、source candidate、P4 candidate、finding、discharged、unknown 和 excluded 分母分别统计。零正式候选与零 source candidate 都不表示安全。

### 9. CLI、退出码和双语报告保持风险边界

新增 `analyze-degraded-source --request --artifact-store --output --source-worker --ir-worker`，要求新建空输出目录，不扫描最新文件、不扩大 scope、不原生链接或运行目标。stdout 只输出最终合法报告，stderr 为日志。

退出语义：完整且无 P4 风险为 0；存在正式 P4 risk 且无更高优先级 incomplete 为 3；存在 AST-only/source candidate、unknown、partial、预算截断或混合不可完整评价时为 2；请求无效或全部不可用为 1。source candidate 本身永不触发 3。面向用户的 failure、limitation、candidate、suggestion 字段同时提供中文和英文，机器 identity 不依赖翻译。

### 10. 缓存区分成功、确定失败和瞬态失败

source、IR availability、source candidate 与组合报告分别缓存；key 包含 schema/producer/policy、scope/profile、源码/include digest、显式依赖、预算类别和工具链身份。可重复的 frontend/profile 失败可以短期缓存并在依赖变化时失效；崩溃、timeout、资源不足等瞬态失败不作为长期语义 cache hit。缓存命中必须重新校验引用，cold/warm semantic digest 必须一致。

### 11. 固定语料、归档样例和质量门禁分层

新增离线矩阵至少覆盖每种语言的 ast-ir、ir-only、ast-only、failed，以及单 TU/跨 TU、无关失败 TU、缺失 include、GCC replay 不兼容、IR worker 失败、P2/P3/P4 失败、预算、cache corruption、C pthread mutex 正反例和 C++ unknown RAII。归档 sibling 样例复制或以只读路径作为外部回归输入时，必须记录来源；Windows、不可编译或未人工裁决样例不得进入准确率分母。

所有新增/修改 C++、Python、schema、CLI、cache、报告和质量代码都有正常、边界、异常、unknown 单元测试。单元 profile 中项目整体、C++、Python及每个受影响模块的 line/branch 均至少 90%；集成执行不补入单元覆盖。语义报告分别列出 C11/C17/C++17/C++20 的计划、完成、TP/FP/FN、strict 指标和 abstention。

### 12. 文档按协议和实际证据更新

- `README.md`、`doc/README.md`：新增降级分析入口和非安全证明说明。
- `doc/IMPLEMENTATION_ROADMAP.md`：A2 从 proposed/applying/validated/archived 按实际状态更新，不提前标记完成。
- 新增 `doc/DEGRADED_SOURCE_ANALYSIS.md`：协议、模式、失败分类、CLI、缓存、退出码和 C/C++ 边界。
- 新增 `doc/DEGRADED_SOURCE_ANALYSIS_VALIDATION.md`：实际命令、版本/hash、测试/覆盖率、四语言 truth、归档回归、性能与限制。

## Risks / Trade-offs

- [AST-only 被用户误解为已确认风险] → 使用独立 SourceCandidate schema、unknown verdict、source-only evidence 和退出码 2，禁止复用 P4 finding code。
- [错误恢复 AST 对无效源码给出误导候选] → fatal diagnostic/profile 不一致时 failed；usable AST 条件进入 schema 和负向测试。
- [未知同步 blocker 造成过度 abstention] → 以候选依赖切片缩小影响；无法证明无关时优先 soundness，保留结构化 gap 供后续 RAII 支持消解。
- [C++ 实现细节污染 C 路径] → 分语言 profile、fixture、truth 与报告门禁，C extractor/规则不得依赖标准库类型。
- [请求内多种模式使状态复杂] → 模式按 TU/候选保存，请求顶层使用 mixed 和精确分母，不折叠为一个乐观状态。
- [失败缓存长期保留环境问题] → 区分 deterministic/transient，依赖摘要变化强制失效，瞬态错误不发布长期语义缓存。
- [AST 与 IR 并行增加成本] → 复用 A1 分层 cache、独立预算和 cold/warm 基线；不为 AST-only 展开无关标准库。
- [归档样例标签不可靠] → 只把可编译、人工复核且属于当前 capability 的 case 纳入准确率，其余仅作覆盖/frontier 观察。

## Migration Plan

1. 冻结现有 P1–P4/A1 schema、CLI、退出码和 semantic digest 回归，增加误报复现 fixture。
2. 添加降级协议 schema、失败分类、严格验证和纯 contract 单元测试，不接入 P3/P4。
3. 重构编排为独立 source/IR TU 计划并生成 `TUEvidenceAvailability`，保持旧 CLI 默认路径。
4. 生成 AST-only SourceCandidate、候选依赖图、预算/cache 和新 CLI；验证不产生正式内存模型边。
5. 接入 `SynchronizationGap` 与 P4 候选相关完整性，使 unknown RAII 回归从 risk 降为 unknown。
6. 扩展四语言 truth/validation、真实小规模 mixed-mode profile、质量入口和文档。
7. 在全新输出目录运行全量单元/覆盖率、OpenSpec/schema、四语言矩阵、旧协议回归、归档样例回归和 cold/warm 确定性门禁。

回滚时停用新 CLI/additive request，停止消费降级产物并保留其独立目录供审计；旧 P1–P4/A1 路径和缓存不迁移、不删除。若候选阻断规则导致不可接受回退，不能恢复误报行为，应保留 unknown 并通过后续 RAII change 扩展证明能力。

## Open Questions

- `ir-generation-failed` 的可重复注入应使用 worker test hook、固定非法 IR emission fixture 还是受控 fake runner？实施时优先不改变生产编译参数且能被单元断言的注入方式。
- 新 CLI 是否直接编排 P2–P4，或只组合显式既有产物？默认采用显式产物依赖加可选编排，禁止扫描最新结果；首个 contract 任务以现有 CLI 可复用边界确定最终字段。
- 归档 `safe/03_pthread_mutex.cpp` 是复制为项目内固定 fixture 还是只保留来源 hash？默认复制最小化、人工复核的等价 fixture，并把原样本作为外部观察，避免 sibling 目录成为运行依赖。
