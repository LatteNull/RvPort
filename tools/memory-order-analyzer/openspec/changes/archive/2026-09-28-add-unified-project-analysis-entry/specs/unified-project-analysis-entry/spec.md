## ADDED Requirements

### Requirement: Provide one versioned production analysis entry
系统 SHALL 提供版本化 `UnifiedMemoryOrderAnalysisRequest`、`UnifiedAnalysisPlan`、`ScopeAnalysisExecutionRecord`、`UnifiedMemoryOrderAnalysisReport` 和单一 `analyze-project` CLI。调用者 SHALL 只需提供外部 LLVM BC bundle manifest、Scope 选择、可选源码/profile 输入、显式入口、分析 policy、预算、cache/resume 与 deadline，不得被要求构造 P1–P4、A1–A6 或 R1–R3 的内部请求或决定执行顺序。

#### Scenario: Backend submits one project request
- **WHEN** 调用者提交一个合法 bundle、选择的 Scope 和统一请求
- **THEN** 系统执行内部计划并在一个新输出目录中生成 request、plan、Scope execution records、统一报告和 artifact index
- **AND** 调用者无需调用任何内部阶段命令

#### Scenario: Existing advanced commands remain available
- **WHEN** 新统一入口加入项目
- **THEN** 既有 ingestion、P1–P4、A1–A6 和 R1–R3 CLI 及其协议继续保持兼容
- **AND** 新入口不得改变其规范化语义、缓存身份或退出码

### Requirement: Treat Scope as the semantic analysis boundary
系统 SHALL 将单个 BC/TU 视为输入原子，将 manifest 中显式 Scope 视为正式跨 TU 分析边界，并将一次 Project 运行实现为一个或多个相互隔离的 Scope 分析。系统 MUST NOT 将不同 target triple、DataLayout、ABI、编译 profile、配置或未声明关联的 Scope 合并形成语义结论。

#### Scenario: Analyze all declared scopes
- **WHEN** 请求选择 bundle 中全部可分析 Scope
- **THEN** 系统为每个 Scope 生成独立计划、执行记录、完整性分母和结果
- **AND** 项目报告聚合但不混合各 Scope 的线程、对象和事件身份

#### Scenario: Analyze an explicit subset
- **WHEN** 请求显式列出合法且唯一的 `scope_ids`
- **THEN** 系统只分析所选 Scope并在报告中保存计划分母与选择依据
- **AND** 未选择 Scope 不得被当作失败或无风险

#### Scenario: Scope identities conflict
- **WHEN** 两个输入成员的 target、ABI、profile 或 Scope 身份冲突且 manifest 未提供可验证关系
- **THEN** 系统拒绝合并并产生双语诊断及非空 frontier
- **AND** 不得通过同名 symbol、TU 文件名或项目 ID 推断它们属于同一程序

### Requirement: Build a deterministic versioned analysis DAG
系统 SHALL 根据请求、bundle、Scope、policy 和已有证据构建版本化依赖 DAG。DAG SHALL 登记每个 stage 的版本、输入/输出 kind、依赖、适用条件、预算、缓存策略、失败分类、降级规则和预期产物，并以确定性顺序执行外部导入、AST/IR 证据、root/entry、demand、effect/thread/lifecycle/synchronization/provenance、concurrent candidate、P4/A6 及投影节点。

#### Scenario: Plan is reproducible
- **WHEN** 相同 bundle、语义请求、policy、worker/schema 版本和预算在不同输出目录执行
- **THEN** 两次 `UnifiedAnalysisPlan` 的 semantic digest、stage 身份和依赖关系一致
- **AND** 时间、后端 task ID、绝对路径和调度顺序不进入语义身份

#### Scenario: Stage is not applicable
- **WHEN** 某 Scope 不包含相应语言构造或 policy 不需要某个既有分析层
- **THEN** 计划将节点记录为 `skipped-not-applicable` 并保存可验证原因
- **AND** 不得把未运行写成 complete empty

#### Scenario: Demand expansion is recursive
- **WHEN** root、direct-call、callback 或递归 SCC 产生新的函数/context demand
- **THEN** 系统使用有界单调 worklist 扩展计划并保存 frontier/预算证据
- **AND** 不得退化为扫描全部已定义函数或在 DAG 中形成无界运行循环

### Requirement: Preserve existing semantic protocols through read-only adapters
统一入口 SHALL 通过只读适配器调用或消费 P1–P4、A1–A6、R1、R1.1、R2 和 R3 的正式实现和产物，不得复制一套不同的线程、对象、同步、原子或风险判定逻辑。每个统一结论 MUST 引用其实际依赖的内部产物 kind、稳定 ID 和 digest。

#### Scenario: Unified and direct stage results agree
- **WHEN** 一个固定 Scope 同时通过统一入口与相同输入的既有直接命令执行
- **THEN** 对应内部产物的规范化语义和 formal risk/discharge 结果一致
- **AND** 统一入口只增加计划、完整性和展示投影

#### Scenario: Internal protocol version is unsupported
- **WHEN** adapter 遇到未声明支持的旧版或新版内部产物
- **THEN** 系统拒绝将其提升为正式证据并产生版本冲突 frontier
- **AND** 不得通过忽略未知字段或缺字段继续输出 complete 结论

### Requirement: Classify AST and IR availability independently per TU
系统 SHALL 为每个 planned physical TU 独立保存 AST 与 IR/P1 可用性，并自动形成 `ast-ir`、`ir-only`、`ast-only` 或 `failed`。AST SHALL 是独立事实层，不得只在 BC 失败后临时执行；生产入口不得调用编译器补产 BC。

#### Scenario: BC or downstream IR stage fails with trusted AST
- **WHEN** manifest 声明 BC 生成失败，或 BC 缺失、parse/verify、SourceIRBinding、P1 或候选相关 IR 阶段失败，但该 TU 的 AST 事实可信
- **THEN** 系统保留 AST-only 源码实体、线程入口/访问/原子/控制/同步候选和代码位置
- **AND** 相关候选必须为 `partial/unknown` 并列出缺失 IR 和运行时证据

#### Scenario: AST fails but IR remains usable
- **WHEN** source worker 因 source unavailable、fatal diagnostic、error recovery 或 profile replay 冲突而失败，但外部 BC 与 IR 事实可用
- **THEN** 系统将 TU 记录为 `ir-only` 并继续允许受支持的 IR 分析
- **AND** 不得继承不可信源码实体或源码位置

#### Scenario: Both AST and IR are unavailable
- **WHEN** 一个 TU 没有可信 AST 且没有可用 IR
- **THEN** 系统将其记录为 `failed` 并保存失败阶段、类别、稳定性和中英文诊断
- **AND** 不得产生伪造的 source candidate 或 complete empty

#### Scenario: Source assistance is disabled explicitly
- **WHEN** 请求选择 `source_assistance=disabled`
- **THEN** 系统不调用 source worker并将可用 BC 的 TU 明确记录为 IR-only
- **AND** 由此缺失的源码和绑定证据必须进入相关完整性分母

### Requirement: Enforce AST-only proof boundaries
AST-only 证据 MUST NOT 单独建立运行时对象身份、must/noalias、byte-range overlap、ThreadInstance、reads-from、modification order、release sequence、synchronizes-with、happens-before、正式 risk、bounded discharge 或安全结论。系统 SHALL 将 AST-only 结果保留为 source-only candidate，并为所有缺失证明建立非空 frontier 和 evidence breaks。

#### Scenario: Source shape resembles a publication bug
- **WHEN** AST-only 发现 producer 写 payload/flag 和 consumer load/branch 的源码形状
- **THEN** 系统输出可回溯的 source-only candidate 和代码证据
- **AND** conclusion 为 inconclusive/unknown 而不是 formal risk

#### Scenario: AST-only and formal risk coexist
- **WHEN** 一个完整候选产生 formal risk，另一个候选依赖 AST-only TU
- **THEN** 系统同时保留 formal risk 与 source-only candidate
- **AND** 项目或相关 Scope 状态为 partial，统一退出码为 2

### Requirement: Propagate completeness by candidate dependency slice
系统 SHALL 以 candidate、Finding 和 bounded discharge 的显式依赖切片传播 TU、stage、Scope、开放边界、预算和失败状态。与失败 TU 或 stage 可证明无关的候选 MAY 继续完成；无法证明无关的缺口 MUST 保守关联，且单个失败不得清空其他独立结果。

#### Scenario: Unrelated TU fails
- **WHEN** Scope 中一个 TU 失败且某个候选的闭合依赖切片证明不引用该 TU
- **THEN** 该候选可以保持 formal complete
- **AND** Scope 顶层仍登记失败 TU 和相应分母

#### Scenario: Dependency relevance is unknown
- **WHEN** 间接调用、歧义 callback、开放 Scope 或缺失 binding 使系统无法证明失败 TU 与候选无关
- **THEN** 相关候选降级为 partial/unknown 并列出断点
- **AND** 不得以零候选或其他 TU 的成功证据掩盖缺口

### Requirement: Support bounded failure isolation, cancellation and deadlines
协调器 SHALL 支持 Scope 和 stage 级失败隔离、显式预算、请求 deadline 和协作式取消。已原子发布且依赖闭合的完整 stage 可以保留；运行中、partial 或 transient worker failure 不得作为完整缓存复用。最终报告 MUST 区分 invalid input、cancelled、deadline、budget、worker crash 和 deterministic analysis failure。

#### Scenario: One scope worker crashes
- **WHEN** 一个 Scope 的 worker 崩溃而其他 Scope 已完成
- **THEN** 系统保存其他 Scope 的有效结果并将受影响 Scope 标记 failed/partial
- **AND** 项目报告仍可生成且退出码为 2，除非没有任何可用证据

#### Scenario: Request is cancelled
- **WHEN** 协调器在 stage 边界观察到有效取消请求
- **THEN** 系统停止调度新节点、终止可安全终止的子 worker并原子发布 cancelled/partial 报告
- **AND** 未完成 stage 不进入成功缓存

#### Scenario: Deadline expires
- **WHEN** 请求 deadline 在执行期间到期
- **THEN** 系统保存已完成结果、登记 deadline frontier 并返回 partial 退出码 2
- **AND** 不得把未运行节点写成零发现

### Requirement: Cache and resume only verified complete artifacts
系统 SHALL 使用 bundle digest、规范化请求、Scope、policy、schema/worker 版本、target/DataLayout/profile 和语义预算建立缓存及恢复身份。resume MUST 验证 stage schema、内容 digest、依赖摘要和完成状态；损坏、版本失配、依赖变化或 transient failure 必须重算或形成 frontier。

#### Scenario: Warm run reuses complete stages
- **WHEN** 第二次运行具有相同语义身份且缓存中的完整 stage 通过验证
- **THEN** 系统允许复用并产生与 cold run 相同的语义报告和 Finding ID
- **AND** cache hit 统计不进入 semantic digest

#### Scenario: Cached artifact is corrupt
- **WHEN** 缓存内容、digest、schema 或 dependency closure 不匹配
- **THEN** 系统拒绝缓存并重算或输出显式 cache frontier
- **AND** 不得将损坏缓存解释为 empty success

### Requirement: Aggregate bounded outcomes without claiming safety
统一报告 SHALL 分别聚合 formal findings、source-only candidates、bounded discharged assessments、unsupported、frontier、abstention、Scope/TU/stage 分母和 artifact 索引。项目、Scope 和候选状态 SHALL 区分 `complete`、`partial`、`ambiguous`、`unknown` 和 `failed`；零 Finding 只能表述为 `no-finding-within-supported-model`，不得表述为 safe 或 thread-safe。

#### Scenario: Complete run has no formal risk
- **WHEN** 所有选中相关切片闭合且没有 formal risk
- **THEN** 报告结论为 `no-finding-within-supported-model` 且退出码为 0
- **AND** 报告明确该结论不是全程序安全证明

#### Scenario: Complete run has a formal risk
- **WHEN** 所有相关切片闭合且至少一个 formal risk 存在
- **THEN** 报告结论为 `risk` 且退出码为 3

#### Scenario: Partial evidence and risk coexist
- **WHEN** 报告同时包含 formal risk 和任何候选相关 partial/unknown/ambiguous
- **THEN** 系统保留风险但项目结论为 inconclusive/partial 且退出码为 2

#### Scenario: Request cannot establish any usable scope
- **WHEN** 请求无效或所有选中 Scope 均无法建立 AST 或 IR 证据
- **THEN** 报告为 failed 且退出码为 1

### Requirement: Keep production analysis offline and compile-free
统一生产入口 MUST NOT 执行 GCC/Clang driver、`-emit-llvm`、linker、configure、build、网络、SSH 或目标程序。它 MAY 运行锁定版本的分析器自有 LLVM reader/worker 和 source semantic worker；source worker 不得生成或替换外部 BC。

#### Scenario: External BC is missing
- **WHEN** planned TU 没有可用 BC
- **THEN** 系统仅使用已有可信 AST 事实降级或记录 failed
- **AND** 不得调用 compiler 或构建系统补产 BC

#### Scenario: Forbidden executable is requested indirectly
- **WHEN** manifest、compile record 或配置试图触发 compiler、linker、configure、build、网络、SSH 或目标程序
- **THEN** 统一入口拒绝该操作并产生失败诊断

### Requirement: Validate supported languages and quality gates
统一入口 SHALL 限定 GCC/Clang 的 C11、C17、C++17、C++20，明确拒绝 Windows、MSVC 和 clang-cl。项目 MUST 为所有新增、修改或复用的自有代码提供正常、边界、异常、unknown、取消、预算和缓存单元测试，并使项目整体、实现语言和每个受影响模块的行覆盖率及工具支持的分支覆盖率均至少 90%。

#### Scenario: Four language profiles execute through one entry
- **WHEN** 固定离线 fixture 分别提交 C11、C17、C++17 和 C++20 的单 TU、跨 TU、多 Scope 与四种证据模式
- **THEN** 系统分别报告每种语言的 planned、completed、failed、formal finding、candidate、discharged、frontier 和 abstention
- **AND** C 路径不得依赖 C++ AST 或标准库模型

#### Scenario: Unsupported toolchain profile is supplied
- **WHEN** 请求或 manifest 声明 Windows、MSVC 或 clang-cl profile
- **THEN** 系统拒绝该 Scope并提供中英文 unsupported 诊断

#### Scenario: Coverage is below threshold
- **WHEN** 项目整体、实现语言或任一受影响自有模块的行/分支覆盖率低于 90%
- **THEN** required quality gate 失败且 change 不得标记实施完成
