## 1. 统一协议与 Schema 基础

- [x] 1.1 定义并实现 `UnifiedMemoryOrderAnalysisRequest`、`UnifiedAnalysisPlan`、`ScopeAnalysisExecutionRecord`、`UnifiedMemoryOrderAnalysisReport` 及其独立 schema/policy 版本、规范化序列化、semantic digest 和双语诊断基础类型。
- [x] 1.2 为请求补齐 bundle 引用、`all`/显式 Scope 选择、source assistance、显式 root、policy preset、预算、cache/resume、deadline/cancel 字段和严格交叉字段验证，拒绝 Windows、MSVC、clang-cl 与内部 stage 开关。
- [x] 1.3 增加统一协议 JSON Schema、协议描述文件和正反 fixture，验证未知字段、重复 Scope、版本/profile 冲突、非法预算、路径逃逸及稳定 digest。
- [x] 1.4 为 1.1–1.3 的所有正常、边界、异常和双语分支编写单元测试，并将新模块纳入逐模块覆盖率枚举。

## 2. Scope 选择与声明式分析计划

- [x] 2.1 实现 bundle preflight 和 Scope selector：以 planned artifact/TU 分母选择全部或显式 Scope，验证 target、DataLayout、ABI、profile、source lineage 和 generation failure，同时保持单个 BC/TU 输入原子身份。
- [x] 2.2 实现版本化 stage registry，登记输入/输出 kind、依赖、适用条件、预算、缓存策略、失败分类、降级规则和 producer/version，不复制既有语义规则。
- [x] 2.3 实现确定性 `AnalysisPlanBuilder`，按 Scope 生成 ingestion、source/IR、R1/R1.1/R3、P2/P3/A3–A5、R2、P4/A6 和 projection 节点及依赖边，并记录 `skipped-not-applicable` 原因。
- [x] 2.4 实现 root/direct-call/callback/递归 SCC demand 的有界单调 worklist 计划节点，保证超预算形成非空 frontier 且不得回退到 all-defined 扫描。
- [x] 2.5 增加多 Scope、Scope 子集、不兼容配置、递归、条件 stage 和 cold/warm 计划确定性的单元测试，断言绝对路径、task ID、时间和调度顺序不进入语义身份。

## 3. 协调器、隔离执行、缓存与恢复

- [x] 3.1 实现 `AnalysisCoordinator`、artifact resolver 和原子输出目录生命周期，生成 request、plan、Scope execution、stage artifact 和统一 artifact index。
- [x] 3.2 实现按 Scope 隔离和确定性有限并行调度；一个 Scope/stage 失败时保留其他 Scope 的有效产物，并维护项目、Scope、TU、stage 和候选相关分母。
- [x] 3.3 实现既有 stage 的只读 adapter 接口和 typed artifact handoff，校验 schema/version/digest/dependency closure，禁止 adapter 改写 P1–A6/R1–R3 产物或风险语义。
- [x] 3.4 实现只复用完整且依赖闭合节点的 coordinator cache/resume；损坏、版本冲突、输入变化、partial 和 transient failure 必须重算或形成 frontier，cache hit 不进入 semantic digest。
- [x] 3.5 实现 deadline、协作式取消、worker crash、时间/内存/输出预算处理，停止调度新节点并原子发布可审计的 partial/cancelled 报告；未完成节点不得进入成功缓存。
- [x] 3.6 为原子发布、失败隔离、并发调度、恢复、缓存损坏、取消、deadline、worker crash 和预算路径增加有效单元测试并达到受影响模块行/分支覆盖率至少 90%。

## 4. AST/IR 可用性与自动降级

- [x] 4.1 从 bundle planned TU、source lineage 和可选 compilation profile 构造独立 source work item，使 AST 事实准备不依赖 BC 成功且不调用 GCC/Clang driver 补产 BC。
- [x] 4.2 集成 A2 可用性协议，按 TU 自动形成 `ast-ir`、`ir-only`、`ast-only`、`failed`，统一分类 BC generation、ingest、parse/verify、SourceIRBinding、P1/下游 IR、source/profile 和 worker 失败。
- [x] 4.3 实现 `source_assistance=auto|required|disabled`，确保 fatal diagnostic、error-recovery、profile 冲突或 source digest 不匹配的 AST 不可用于候选和源码位置。
- [x] 4.4 将 AST-only 事实只投影为 source-only candidate 和同步/证明缺口，禁止建立 runtime object、alias/noalias、byte overlap、ThreadInstance、RF/MO/release sequence/SW/HB、formal risk 或 bounded discharge。
- [x] 4.5 实现候选依赖切片完整性传播：无关失败 TU 不降低独立候选，相关或相关性未知的失败必须降级且不得以零候选掩盖。
- [x] 4.6 增加 C11、C17、C++17、C++20 的四种模式、AST 与 BC 独立失败、source assistance、候选切片和 formal risk 与 AST-only 并存的单元测试。

## 5. 既有分析能力的统一编排适配

- [x] 5.1 接入 `ExternalBitcodeBundleManifest` preflight/ingestion 与既有 BCArtifact/ModuleFacts 产物，保证统一入口不执行 compiler、linker、configure、build、网络、SSH 或目标程序。
- [x] 5.2 接入 A1/A2、R1 ExecutionRoot、R1.1 ThreadEntry 和 R3 demand-driven function 分析，验证 root/entry overlay、source/IR binding、AST-only frontier 和 demanded function/context 身份。
- [x] 5.3 接入 P2、P3、A3、A4、A5 与 R2 adapter，传递 effect、ThreadContext/ThreadInstance、MHP、lifecycle、held-region、对象 provenance、byte range、候选/保护及完整性证据。
- [x] 5.4 接入 P4 和 A6 adapter，分别保留原始 publication risk/discharge 与 fence/RMW/CAS overlay，不把 P2 order、P3 RF candidate、R2 candidate、AST 事实或 MemorySSA 单独提升为顺序证明。
- [x] 5.5 建立 direct-command 与 unified-entry 的规范化语义等价测试，覆盖完整、partial、unknown、风险和受限消解，确认所有既有协议、缓存身份和 CLI 回归不变。

## 6. MemoryOrder Finding 与证据链投影

- [x] 6.1 定义独立的 `MemoryOrderFindingProjection` JSON Schema 与协议，包含 `fact`、`conclusion`、`occurrences`、`primaryOccurrenceId`、`evidenceChain`、typed provenance、内存序专用枚举和 `org.rvport.memory-order-analyzer.*` 扩展命名空间。
- [x] 6.2 实现 formal findings、source-only candidates 和 bounded discharged assessments 的独立 mapper，共用投影结构但强制不同集合、verdict、状态、计数和 bounded wording。
- [x] 6.3 实现 evidence-chain builder，支持 thread creation、callback/root/call path、ThreadInstance/MHP、访问、对象/byte overlap、mutex/RAII、atomic/RF/MO/release sequence、同步证明/缺口和结论节点及真实关系边。
- [x] 6.4 实现确定性 `rootStepId`、连通 `primaryPath`、相关分支 `steps/edges`、`impactStepIds`、预算和一等 `breaks`；partial/ambiguous/unknown 必须有断点，complete 不得含已知断点。
- [x] 6.5 实现严格 reference/semantic validator，验证所有节点引用闭合、primary occurrence 存在、provenance kind/ID/producer/version/digest、Scope/profile 相容性和结论来源，不允许复制无关位置或伪造 SW/HB。
- [x] 6.6 为 projection models、mapper、chain builder、reference validator 和中英文字段编写正常、边界、异常、AST-only、歧义、断链、digest/profile 冲突及预算单元测试，达到各模块行/分支覆盖率至少 90%。

## 7. 分析时源码快照与代码上下文

- [x] 7.1 实现项目相对 POSIX 路径和 source boundary 校验，拒绝绝对路径、`..`、反斜杠逃逸、symlink/解析后越界及 checkout/temp 根泄漏。
- [x] 7.2 实现按 source SHA-256 内容寻址和去重的源码 snapshot store/artifact index，确保只从与事实 digest 匹配的分析时快照读取内容，不回退到已变化的当前工作区同名文件。
- [x] 7.3 实现一基、end-exclusive span 投影、真实行号 `context.lines`、精确 `highlights` 和默认前后各 20 行窗口；每位置强制 256 行/65536 字符上限并优先保留命中范围。
- [x] 7.4 实现 no-debug、IR-only、缺失/变化源码、digest mismatch、无效 span、过长行、读取失败和预算截断的 `complete/partial/unavailable` 状态、break 及中英文 reason/suggestion。
- [x] 7.5 增加同文件多 Finding 去重、宏/多行范围、边界首尾行、Unicode、截断、路径逃逸、文件变化、snapshot 不可用和扩大 code-context 所需 artifact 元数据单元测试。

## 8. 统一聚合报告、CLI 与消费者合同

- [x] 8.1 实现项目/Scope/TU/stage 聚合器，分别发布 formal findings、source-only candidates、bounded discharged assessments、unsupported、frontier、abstention、失败分类和完整性分母，禁止聚合掩盖分项失败。
- [x] 8.2 实现 `risk`、`inconclusive`、`no-finding-within-supported-model`、`failed` 项目结论和 0/3/2/1 退出码优先级；零 Finding、exit 0 和 bounded discharge 不得输出 safe/thread-safe。
- [x] 8.3 实现 `analyze-project` CLI 参数、stdout 单一协议 JSON、stderr 有界日志、fresh output、schema 错误报告和内部 stage 隔离，保持现有 CLI 不变。
- [x] 8.4 实现完整 `report.json` 与逐 Finding/candidate/discharged 独立原子序列化，固定可供后端列表、详情和 code-context 使用的 consumer fixture 和解析合同。
- [x] 8.5 增加 CLI invalid request、全部失败、完整零风险、完整有风险、风险与 partial 并存、取消、stdout/stderr、独立 Finding round-trip 和 KB v2 风格共享结构兼容单元测试。

## 9. 四语言集成真值与回归

- [x] 9.1 建立 C11、C17、C++17、C++20 独立统一入口 truth，覆盖单 TU、跨 TU、多 Scope、AST+IR、IR-only、AST-only、failed、no-debug 和开放 Scope，并分别报告 planned/completed/failed/risk/candidate/discharged/frontier/abstention。
- [x] 9.2 增加 pthread/thrd、std::thread/std::jthread/async、mutex/RAII、对象字段/指针、普通 publication 与 fence/RMW/CAS 的代表链，人工核对 thread→access→object→MHP→sync/atomic→conclusion 的 Finding 和代码上下文。
- [x] 9.3 增加不兼容 Scope、间接调用、歧义 callback/对象/RF、递归、预算、worker failure、cancel/deadline、cold/warm cache 和 snapshot 变化/截断集成用例，确认缺口始终产生非空 frontier/break。
- [x] 9.4 增加生产禁令测试，拦截并断言统一入口不会执行 compiler、BC emission、linker、configure、build、网络、SSH 或目标程序；测试 fixture 的 BC 只允许在分析器运行外预生成。
- [x] 9.5 全量回归 P1–P4、A1–A6、R1、R1.1、R2、R3 和现有 eager/advanced CLI，记录规范化语义差异为零或逐项审定的展示层差异。

## 10. 文档、质量与验收

- [x] 10.1 更新 README，说明唯一生产入口、外部 bundle、Project/Scope/TU 边界、AST-only 自动降级、退出码、bounded 结论和最小可复制命令。
- [x] 10.2 新增 `doc/UNIFIED_PROJECT_ANALYSIS.md`，记录请求、DAG、Scope 隔离、stage adapters、缓存恢复、取消、失败传播、后端责任边界和禁止操作。
- [x] 10.3 新增 `doc/MEMORY_ORDER_FINDING_SCHEMA.md`，记录与 KB Scanner v2 的结构兼容/领域隔离、Finding 三类集合、证据节点/边/break、源码快照、代码窗口和前端消费示例。
- [x] 10.4 更新 `doc/IMPLEMENTATION_ROADMAP.md` 和协议索引，登记本 change、保持 B1/B2 及未授权语义能力边界，并运行文档链接、schema 示例、路径和禁用安全措辞检查。
- [x] 10.5 运行全部单元测试和独立四语言集成验收，生成项目整体、实现语言和每个受影响自有模块的行/分支覆盖率报告；所有指标必须至少 90%，且统计必须纳入未被测试加载的项目源码。
- [x] 10.6 发布 acceptance/validation 记录，列出精确命令、环境、测试数量、四语言分母、退出码矩阵、cold/warm 语义、性能/RSS/输出大小、覆盖率、报告路径、第三方/生成物排除项和已知 frontier；任何失败或覆盖不足不得标记 required gate 完成。
- [x] 10.7 运行 `openspec validate add-unified-project-analysis-entry --strict`（或当前 CLI 支持的等价严格验证）并核对 proposal、design、specs、tasks 与实际实现/文档一致后，才将所有任务标记完成。
