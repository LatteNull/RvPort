# degraded-source-analysis

## Purpose

定义降级源码分析的独立协议、证据可用性、保守候选边界、失败分类、依赖切片、缓存与退出语义，使 GCC/Clang 的 C/C++ 翻译单元在 BC 或后续 IR 阶段失败时仍可保留可信源码证据，同时禁止把 AST-only 结果提升为内存模型证明或全程序安全结论。

## Requirements

### Requirement: Define independent degraded source analysis contracts

系统 SHALL 定义严格、版本化的 `DegradedSourceAnalysisRequest v1`、`TUEvidenceAvailability v1`、`SourceCandidate v1` 和 `DegradedSourceAnalysisReport v1`，包含 kind、schema/producer/policy identity、scope/profile、预算、确定排序、canonical digest 和显式依赖引用。未知字段、未来版本、悬空或替换依赖、混合 profile 及重复身份 MUST 被拒绝；P1–P4 与 A1 已有协议原义不得修改。

#### Scenario: A report dependency is replaced

- **WHEN** 报告引用的 source facts、BC/P1 或下游产物 digest 与提供文件不一致
- **THEN** 消费者拒绝报告或标记陈旧，不把新旧证据拼接成一种模式

#### Scenario: Existing analysis is used without degraded mode

- **WHEN** 调用方继续使用既有 P1–P4 或 AST-assisted 请求且未提供新协议
- **THEN** 旧 schema、默认行为、cache identity 和退出语义保持兼容

### Requirement: Classify evidence availability per translation unit and candidate
系统 SHALL 分别记录每个 bundle 计划 TU 的可信 AST、外部 BC/P1 ingestion 和所需下游阶段状态，并为 TU 与候选计算 `ast-ir`、`ir-only`、`ast-only` 或 `failed`；同一请求包含多类时 SHALL 报告 mixed 和每类 hit/total，不得选择最乐观模式覆盖外部 missing/failed 或 source 缺口。分析器不得通过现场生成 BC 改变分类。

#### Scenario: AST succeeds while external IR is unavailable
- **WHEN** 一个 TU 形成可信 SourceSemanticFacts，但 bundle 将 BC 记录为 missing/failed，或 ingestion verify/reader 失败
- **THEN** 该 TU 为 ast-only，保留 source digest 与外部 IR 缺口，不调用 emission 且不声称 P1 或 P4 已运行

#### Scenario: One unrelated TU is ast-only
- **WHEN** 一个正式 P4 候选的依赖闭包全部为 ast-ir，而 scope 中另一个可证明无关 TU 仅有 AST
- **THEN** 该候选仍可按 ast-ir 评价，请求顶层保持 mixed/partial并保留外部计划分母

#### Scenario: Neither AST nor external IR is trustworthy
- **WHEN** 源码/profile 不可信且对应外部 record missing、failed 或无效
- **THEN** TU 为 failed，不把错误恢复 AST、debug path 或同名 BC 提升为可信候选

### Requirement: Publish stable stage-specific failure classifications
系统 SHALL 至少区分 `frontend-invalid`、`profile-replay-incompatible`、`external-artifact-missing`、`external-build-failed`、`artifact-format-unsupported`、`reader-incompatible`、`artifact-validation-failed`、`worker-budget` 和 `analysis-stage-failed`，并记录 stage、deterministic/transient、受限原始诊断、中英文 detail 及已完成产物。历史 `ir-generation-failed` MAY 仅用于读取旧报告，不得描述当前分析器执行了 BC emission；分类 MUST NOT 把上游构建失败、输入损坏、source worker、资源截断和语义 unsupported 合并为同一 compile failure。

#### Scenario: GCC record cannot be replayed by source worker
- **WHEN** GCC-only 扩展或关键 ABI/profile 选项无法由锁定 Clang source worker 等价解析，但外部 BC 可读
- **THEN** 记录 profile-replay-incompatible 和 AST 缺口，保留 IR-only，不伪造 AST 与 BC 同 profile

#### Scenario: External build reports a missing TU
- **WHEN** bundle record 状态为 failed 且包含上游受限诊断
- **THEN** 记录 external-build-failed、stage=upstream-build，并保持 planned TU，不由分析器重试编译

#### Scenario: P3 exceeds its output budget
- **WHEN** AST、外部 BC、P1/P2 可用但 P3 worker 达到输出预算
- **THEN** 记录 worker-budget、stage=P3 和既有证据，相关候选为 partial/unknown 而非上游构建或 ingestion failure

### Requirement: Keep AST-only source candidates below the memory-model proof boundary

AST-only 模式 SHALL 仅发布 `evidence_level=source-only`、`verdict=unknown`、`safety=not-established` 的 SourceCandidate，列出源实体、对象/调用/控制候选、假设、依赖闭包及缺失的 IR memory effect、ordering、访问范围、线程实例、RF/SW/HB 证据。SourceCandidate MUST NOT 使用 P4 finding identity，不得单独生成或提升 sequenced-before、reads-from、synchronizes-with、happens-before、risk、discharged 或安全结论。

#### Scenario: Source shows a relaxed atomic publication shape

- **WHEN** AST 识别 `_Atomic`/`std::atomic`、pthread callback 和消费者条件，但相关 TU 无可信 IR
- **THEN** 输出 source-only candidate 和缺失证据，不输出 publication-order-risk 或 potential-data-race

#### Scenario: Source order resembles payload before publication

- **WHEN** AST 存在受限 source sequence 但任一端没有唯一真实 IR memory effect
- **THEN** 只保留源码关系候选，不建立 must-before、RF、SW、HB 或 discharge

### Requirement: Slice degradation by candidate dependencies

系统 SHALL 以 TU、source entity、binding、object、call、thread instance、memory effect、synchronization gap 和 protocol candidate 构建传递依赖切片。缺口与候选可证明无关时不得清空候选；缺口可能相关且无法证明无关时 MUST 降级该候选。计划、完成、失败、source candidate、P4 candidate、finding、discharged、unknown、unsupported 和 excluded SHALL 分别计数。

#### Scenario: A failed helper is on the candidate call path

- **WHEN** flag 或 payload wrapper 依赖一个只有 AST 或完全失败的 TU
- **THEN** 相关候选降为 ast-only/unknown 并列明缺失依赖，不能借用其他 TU 的 IR

#### Scenario: A failed utility TU is outside the slice

- **WHEN** 失败 TU 与候选线程、对象、调用、同步和控制闭包均可证明无关
- **THEN** 正式 assessment 保留，顶层报告仍反映失败 TU 和非完整 scope

### Requirement: Expose bounded degraded analysis with deterministic cache and exit semantics
系统 SHALL 提供 `analyze-degraded-source --request --artifact-store --output --source-worker --ir-worker`，要求新建空输出目录并只消费已完成 external ingestion 的 artifact store；禁止扫描最新产物、扩大 scope、生成/链接 BC、运行构建或目标。source、availability、candidate 和组合报告 SHALL 使用包含 schema/policy、bundle/record、scope/profile、源码/include、artifact/依赖 digest、预算类别和工具链的分层 cache；cold/warm semantic digest MUST 一致，瞬态 timeout/crash 和 partial ingestion 不得作为长期 complete cache hit。

#### Scenario: Usable AST-only evidence remains
- **WHEN** 请求有效且存在 source candidate、unknown、partial、预算截断或不能完整评价的 mixed 模式
- **THEN** 命令发布合法报告并退出 2，source candidate 不触发风险退出 3，也不现场生成 BC

#### Scenario: A formal P4 risk is complete
- **WHEN** 至少一个 ast-ir/ir-only 候选由既有 P4 输出正式 risk，且没有优先级更高的 candidate-relevant incomplete
- **THEN** 新命令引用该 P4 证据并退出 3，不把 source candidate 或 ingestion 成功计为 risk

#### Scenario: All requested evidence is unavailable
- **WHEN** 请求/schema 无效、输出目录非空或所有 bundle 计划 TU 均 failed 且没有可信 source/IR 事实
- **THEN** 命令退出 1 并尽力输出最小中英文失败报告，不调用 compiler/linker恢复输入

### Requirement: Propagate candidate-relevant C++ lifecycle gaps conservatively

A2 编排 SHALL 将标准库 profile 不支持、ABI wrapper mismatch、callable/object/handle/move provenance ambiguous、构造/join/detach 结果未知、异常路径、scope definition 缺失和 A3 预算 frontier 建模为候选相关 gap，并纳入 TU/entity/object/call/thread/protocol 传递依赖切片。只有可证明与目标候选无关的 A3 gap 才不阻断该候选正式评价；顶层完整性仍须保留。

#### Scenario: An unknown std thread carries the publication worker
- **WHEN** 发布候选依赖的 worker 只能从 AST 识别而 ABI broker 或对象 lineage 未证明
- **THEN** 相关候选降为 partial/unknown，不借用同名 pthread 或其他 TU 的线程实例继续判定风险

#### Scenario: An unsupported std thread is outside the candidate slice
- **WHEN** 依赖切片证明该 A3 gap 的线程、对象、调用和路径与一个完整 C pthread 候选无关
- **THEN** C pthread 候选保留既有评价，顶层报告仍记录非完整 scope 与 A3 gap

### Requirement: Keep AST-only C++ thread candidates below execution proof

AST-only 模式 SHALL 可保存 `std::thread` 构造、callable、对象操作和源码控制候选，但 MUST 保持 `evidence_level=source-only`、`verdict=unknown`、`safety=not-established`，不得建立动态 ThreadInstance、thread-start/exit、join-complete、MHP、RF、SW、HB、risk 或 discharged。

#### Scenario: Source contains a direct lambda thread and join
- **WHEN** AST 可信地识别 lambda 构造与 join 语句但相关 IR/ABI 证据不可用
- **THEN** 输出 source candidate 及缺失证据并退出 partial，不产生已启动或已 join 的线程关系

### Requirement: Resolve synchronization gaps only with candidate-equivalent A4 proof

A2 `SynchronizationGap` SHALL 按候选依赖切片与 A4 mutex/owner/path/profile identity 关联。只有 A4 为同一候选提供完整替代 proof 时，才可关闭 `unmodeled-raii-lifetime`、`mutex-kind-unknown` 或 wrapper gap；无关 proof、may-alias、AST-only 或 partial A4 MUST NOT 消除 gap。

#### Scenario: Archived safe mutex case has a complete A4 proof
- **WHEN** 本地锁定的 `safe/03_pthread_mutex.cpp` 候选具有完整同 mutex RAII proof
- **THEN** 对应未知 RAII gap 被有依据地关闭，候选可在受限模型内消解，但报告不宣称程序安全

#### Scenario: A proof belongs to another mutex
- **WHEN** A4 proof 完整但 mutex/object/thread/path 与待评估候选不同
- **THEN** 原 gap 保留且候选继续 partial/unknown

### Requirement: Preserve AST-only and failure semantics for A4

当 BC、SourceIRBinding、profile 或 A4 worker 不可用时，A2 MAY 保留 AST mutex/RAII source candidate，但 SHALL 输出 partial/unknown 和缺失证据；AST 单独 MUST NOT 建立 acquire/release、held-region、SW、HB、risk 或 discharged。

#### Scenario: A4 worker budget is exhausted for one TU
- **WHEN** 一个相关 TU 的 source facts 可用但 A4 IR/状态机预算耗尽
- **THEN** 依赖该 TU 的候选降级，已证明无关的其他候选可继续分析，顶层记录不完整
### Requirement: 零 BC 和部分 BC 必须保留完整源码分母
分析器 SHALL 为每个可重放 compile entry 接收 SourceSemanticRequest。无 BC 时全部记录进入 AST-only；部分 BC 时按 TU 混合 AST-only 与 AST/IR。AST-only 结论只能进入 source candidate、frontier 或 unknown，MUST NOT 被提升为已证明 runtime risk 或无风险结论。

#### Scenario: BC 全部不可用
- **WHEN** external bundle 中所有记录均为 missing 或 failed，但存在源码请求
- **THEN** 分析器继续源码辅助并发布有 evidence break 的候选和 unknown

### Requirement: 旧标准源码辅助必须使用显式协议版本边界

系统 SHALL 对发生语言上下文扩展的 source profile、source request、external bitcode record 和统一分析 request 按 kind 发布 v2；未改变语义的相关 kind SHALL 保持 v1。消费者 SHALL 继续读取合法历史 v1 文档，但 MUST 拒绝 v1 携带 v2 字段、v2 缺少标准上下文、嵌套版本不一致以及未知未来版本，不得把旧标准静默解释为 C17 或 C++17。

#### Scenario: 新请求引用旧标准源码上下文

- **WHEN** `SourceSemanticRequest v2` 使用 C89、C99、C++98/C++03 或 compiler-default profile
- **THEN** 请求和 profile 均显式使用 v2，并保留基础标准、方言、来源和原始标准参数

#### Scenario: 历史请求保持原义

- **WHEN** 消费者读取合法 `SourceSemanticRequest v1` 和对应 v1 profile
- **THEN** 按历史四标准语义读取，且不允许通过附加 v2 字段改变旧文档含义

### Requirement: 源码请求必须按物理翻译单元稳定编排

统一协调器 SHALL 按 `physical_tu_id`、`record_id` 的稳定顺序处理源码请求，并 SHALL 使用 `physical_tu_id` 命名请求文件。source request reference 与 IR request reference MUST 分别按自身路径和摘要稳定排序，不得交叉复用排序结果。

#### Scenario: record 顺序与物理翻译单元顺序不同

- **WHEN** 输入中的 record ID 顺序与 `physical_tu_id` 顺序不同
- **THEN** 写入和分析顺序以物理翻译单元为主，并且每个请求文件仍可唯一追溯到对应 TU

### Requirement: 降级候选必须接受合法旧语言标准

`SourceCandidate` 校验 SHALL 接受统一语言标准模型中与候选语言一致的全部合法 C/C++ 基础标准，包括 C89/C90、C99、C++98/C++03；语言与标准不匹配或未知标准 MUST 被拒绝。

#### Scenario: C89 AST-only 候选进入降级报告

- **WHEN** C89 profile 产生语言一致且其余字段合法的 source candidate
- **THEN** 候选通过协议校验并保持 source-only/unknown 语义，不因标准早于 C11 而失败

### Requirement: 区分完整源码事实与面向用户的相关候选
系统 SHALL 保留内部 SourceSemanticFacts、原始 SourceCandidate 及计划分母。统一报告面向用户的源码候选 SHALL 经过内存序相关性准入，并保存准入依据、原始引用及未准入原因。普通读写或控制关系本身 MUST NOT 被投影为用户可操作的内存序问题。

#### Scenario: 普通向量计算与局部控制流
- **WHEN** 源码只提供普通局部/参数访问、空指针判断、算术循环或向量操作，没有可引用的线程、原子或同步相关性依据
- **THEN** 原始事实保留在审计产物中，不逐关系生成对外内存序候选；缺失 BC 仍使相关分析不完整，不能以候选为零宣称安全

#### Scenario: AST-only 原子发布形状
- **WHEN** AST 显示有引用可追溯的原子/线程/同步操作及其有界源码关系切片，但缺少 IR 证明
- **THEN** 系统保留带相关性解释和适用缺口的 source-only 候选，不能要求完整 IR 才准入，也不能提升为正式风险

#### Scenario: 未验证同步 wrapper
- **WHEN** 存在需要核实的同步 wrapper 线索，但锁对象或模型无法确认
- **THEN** 候选明确线索强度与未知原因，不把名称匹配当成已建立的同步或共享关系

### Requirement: 对候选准入与去重保留可审计分母
系统 SHALL 分别统计原始事实/候选、准入候选、未准入项及预算截断，保留原因和来源引用。候选归并 SHALL 基于同一 Scope/profile 内的稳定语义关系与位置身份，并保留相关 occurrences；MUST NOT 仅按行号或标题合并不同问题。

#### Scenario: 同行存在多个关系
- **WHEN** 一个源码位置包含不同对象或不同配置的候选，而同一关系也被重复发现
- **THEN** 相同关系可稳定去重，不同对象/配置不被误合并，各自来源可追溯

#### Scenario: 准入预算耗尽
- **WHEN** 有界切片或候选输出达到预算
- **THEN** 报告记录截断及未完成边界，不能将尚未评价的事实计为已证明无关或安全

### Requirement: 候选缺口与适用模型相匹配
源码候选 SHALL 根据实际形状、证据等级和依赖切片列出适用的缺口及双语建议，MUST NOT 对所有读写或同步候选机械附加相同的原子 RF/MO/SW/HB 清单。

#### Scenario: mutex 候选不依赖原子通信模型
- **WHEN** 待核实项涉及锁对象/持锁区间且没有原子通信证明需求
- **THEN** 缺口描述锁身份、线程/生命周期与所需 IR 证据，不无条件要求原子 RF/MO assignment

#### Scenario: 相关性或对象身份不可确定
- **WHEN** 有合理源码线索但无法解析对象或调用关系
- **THEN** 明确保留未知和实际缺失信息，不伪造具体共享对象、线程对或访问顺序
