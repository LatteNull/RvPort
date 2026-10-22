## Context

KB Scanner 的 staged pipeline 已经具备正式 Workspace Collector、C/C++ Frontend、Knowledge Provider、Normalizer 和 Local Detector，并在真实 AVX/AVX2 项目上稳定地产生局部 Evidence、NormalizedFact 与 Observation。当前 `Analyzer` 仍是空实现，`AnalysisSnapshot` 也只预留了 `Relation` 容器，因此下游只能知道“某个文件局部出现了 x86 事实”，不能回答以下问题：

- 一个宏调用是否通过同项目头文件中的定义最终引用 x86 intrinsic；
- include、宏定义、宏调用、预处理分支和实现之间如何关联；
- x86 分支旁是否存在 RISC-V、generic、portable、scalar 或 fallback sibling；
- 一条结论的 proof path 是否完整，还是因为 include、宏展开或遍历预算而只能标记为 partial/unknown。

现有 `kb_scanner/technology/graph_store.py` 已证明 NetworkX `MultiDiGraph` 能提供有向平行边和有界路径查询，但该模块使用的是 spike DTO，不能直接成为正式领域合同。正式实现必须复用已存在的 core `Entity`、`Evidence`、`Relation` 与稳定 SHA-256 身份，并把 NetworkX 隔离在 adapter 后。

staged pipeline 的固定顺序是 Knowledge → Frontend → Normalizer → Analyzer → Local Detector。Graph Analyzer 因此不能依赖尚未产生的 Observation；它使用 NormalizedSnapshot 和 KnowledgeSnapshot 构图，Local Detector 随后同时消费 normalized facts、graph analysis 和 knowledge。默认 CLI 在本 change 中仍运行 legacy compatibility profile，正式 graph 只进入 qualification profile。

真实 AVX/AVX2 项目的人工审计事实是本 change 的 correctness baseline：37 个 C/C++ 文件中有 39 个 x86 header 引用、362 个 x86 vector type 出现、360 个普通源码 intrinsic call、45 个 comment hint；两个本地头文件另有 12 个函数式宏定义，其 replacement body 中共有 18 个终端 intrinsic 引用。Legacy 的 838 条 Finding 包含已知漏报和把宏定义当调用的误判，不能作为新实现的正确性标准。4 个 Makefile 中的 24 个 x86 编译参数属于后续 Build Selection change。

约束如下：

- 只做 C/C++ 静态分析，不执行预处理器、编译器、构建、测试或项目代码；
- 不分析 OS、内核、系统调用、驱动和板级迁移；
- 不实现 Make/Autoconf/CMake/RPM 选择，不判定 blocking、severity 或 readiness；
- 不修改两份既有 Clang/GCC compiler-derived JSON，也不把 legacy YAML/DTO/evaluator 引入新模块；
- 内部新增对象必须保持默认空值构造兼容，并且不产生第二个主结果文件；
- 所有依赖安装、测试和基准只发生在独立 `kb-scanner-test` 容器。

## Goals / Non-Goals

**Goals:**

- 建立 scanner-owned、可替换且确定性的 GraphStore 合同，并提供首个 NetworkX adapter。
- 扩展 Frontend/Normalizer，结构化保留函数式宏的参数、replacement token 和精确 SourceSpan。
- 从 normalized facts 和 knowledge 建立 include、宏、调用、条件分支、sibling alternative 与 source reachability 关系。
- 提供有界 proof path，并把循环、截断、歧义和缺失输入显式表达为 partial/unknown。
- 在 staged qualification 中用真实 Graph Analyzer 替代 empty analyzer，同时保持默认 CLI 与三类 artifact 不变。
- 用人工审计的 AVX 关系事实、隔离单元测试、架构边界测试和容器基准验收实现。

**Non-Goals:**

- 不求值 Make、Autoconf、CMake、RPM 或测试目标，不分析 RISC-V 构建选择。
- 不执行真实 RISC-V 编译、交叉编译、项目测试或动态预处理。
- 不推导最终 Finding 的 blocking、severity、portable 状态或项目 readiness。
- 不支持完整 C/C++ 预处理器语义，例如 token pasting、stringification、可变参数重写和任意 include 搜索路径求值。
- 不切换默认 CLI，不删除 Legacy，不修改现有报告 schema。

## Decisions

### 1. 正式 GraphStore 使用 scanner-owned protocol，NetworkX 只作为 adapter

在 `kb_scanner/graph` 中定义只接受 core `Entity`、`Relation` 和新的 core `ProofPath`/`PathSearchResult` 的 GraphStore protocol。首个 `NetworkXGraphStore` 内部使用 `MultiDiGraph`，支持同一端点间不同 kind 或不同 evidence 的平行关系。adapter 返回排序后的 scanner 领域对象，不返回 NodeView、EdgeView、图对象或 NetworkX exception。

GraphStore 的最小职责是：注册/查询 Entity，注册 Relation，按方向和 kind 查询关系，以及在显式预算下查询 proof path。关系语义、宏解析、alternative 判断和 Diagnostic 全部属于 Graph Analyzer，不下沉到图库 adapter。

选择 NetworkX 是因为现有容器 spike 已验证其有向平行边和路径能力，且本阶段图规模适合内存实现。没有选择自研 adjacency graph，是因为它会重复成熟基础设施；没有把 NetworkX 类型直接作为合同，是为了后续在资源预算变化时可替换实现。

### 2. 扩展 core AnalysisSnapshot，而不建立第二套结果模型

新增以下 scanner-owned、冻结且默认可空的内部合同：

- `ProofPath`：稳定 ID、source/target Entity ID、按顺序排列的 Relation ID、`complete|partial|unknown` 状态以及可选 reason；
- `PathSearchResult`：一次有界查询的路径、visited 数量、是否截断和未完成原因；
- `AnalysisSnapshot.entities`：Normalizer 原实体与 Analyzer 合成实体的确定性并集；
- `AnalysisSnapshot.relations`：排序后的 core Relation；
- `AnalysisSnapshot.proof_paths`：已物化、供 Detector/后续 Classifier 使用的关键路径。

现有空构造继续有效。`StageResult.status` 表示整个 Analyzer 阶段的完整性，单条 relation/path 的 `status` 和 metadata 表示局部完整性。缺少路径只能表示“在当前证据和预算内未证明”，不得转换为安全或 ready。

这些对象本阶段只存在于 staged qualification。未来兼容 Projector 需要保留关系时，应把 proof path 投影到既有 Finding `trace`，并保持 `condition_macros`、`alternative_impl`、`build_context` 的既有名称和语义；不得直接序列化 `AnalysisSnapshot` 或新增主 JSON。

### 3. Analyzer 显式接收 KnowledgeSnapshot，但不依赖 Observation

将 `Analyzer.analyze` 调整为 `analyze(context, facts, knowledge)`，orchestrator 在 Normalizer 后把已加载的 KnowledgeSnapshot 传给 Analyzer。qualification profile 使用真实 Graph Analyzer，Local Detector 仍在其后执行并消费 AnalysisSnapshot。

Knowledge 用于识别已审校的架构 family/alias、target feature 和终端 x86 symbol 角色；关系端点和证据仍来自 NormalizedSnapshot。Analyzer 不读取 JSON manifest、YAML 或 parser 对象，只读取 core KnowledgeEntry。Detector 负责把局部事实和关系合成为 Observation；Analyzer 不伪造或提前产生 Observation。

没有把 Detector 调到 Analyzer 前，是因为这会破坏已经固化的阶段顺序并让关系正确性依赖检测策略。没有把 Knowledge 藏入 Analyzer 构造函数，是因为同一次 ScanContext 对应的知识快照必须显式可追溯并可在测试中替换。

### 4. 宏 replacement 使用附属 Evidence，而不是把定义伪装成 call

保留现有 `macro_definition.value = macro name` 与 `macro_expansion.value = macro name` 兼容语义，并新增：

- `macro_parameter` Evidence：每个函数式宏参数一条，带参数序号、所属 macro definition Evidence ID 和精确 SourceSpan；
- `macro_replacement_token` Evidence：replacement body 中每个有意义 token 一条，带 token 序号、token role、所属 definition Evidence ID 和精确 SourceSpan。

Tree-sitter baseline 负责从 `preproc_function_def`/`preproc_def` 的字段范围提取这些 Evidence。Normalizer 将它们分别归一为 `macro_parameter` 与 `macro_replacement` facts，并保留 definition Evidence 引用。Clang 若能稳定提供同类位置可作为额外 producer；不能稳定提供时不猜测，由 baseline 保底。

`macro_definition` 永远表示定义，不进入 `call_expression`；replacement token 只有在语法上构成 `identifier (...)` 时才形成宏体 `calls`/`expands_to` 关系。宏参数替换、token pasting、stringification、可变参数与嵌套动态拼接不做完整展开，相关路径标记 partial/unknown。

选择附属 Evidence 而不是把整个 body 放入一个字符串 metadata，是因为每个终端 intrinsic 必须有自己的 SourceSpan 和稳定 provenance；也没有生成所有普通 identifier Evidence，避免扩大内存和误报面。

### 5. Graph Analyzer 分为确定性的索引、建边和路径物化三步

正式模块按以下职责拆分：

1. `GraphEntityIndexer`：把 project、source file、macro definition、macro invocation、condition group、branch、symbol/call site 和 implementation 映射为稳定 Entity；合成 ID 只使用 identity version、项目相对路径、语义 kind/name、source span 和 compilation context identity。
2. `RelationBuilder`：基于索引和 normalized facts 建立直接关系并校验所有端点/evidence 引用；重复关系按稳定语义 ID 合并 evidence provenance。
3. `ProofPathResolver`：从关键宏调用/实现端点执行有界查询并物化 ProofPath，汇总局部 completion reason。

关系方向和含义固定为：

| Relation | source → target | 含义 |
|---|---|---|
| `defines` | source file → macro/symbol/implementation | 文件定义目标 |
| `includes` | including file → included file/header | 文件静态包含目标 |
| `invokes_macro` | macro invocation → macro definition | 调用点解析到定义 |
| `expands_to` | macro definition → referenced macro/symbol | replacement body 静态引用目标 |
| `calls` | call site/implementation → symbol | 源码或宏体存在调用语法 |
| `has_branch` | condition group → branch | 同一条件结构拥有分支 |
| `guarded_by` | implementation/call/include → branch | 目标位于该分支范围内 |
| `alternative_to` | x86 implementation/branch → alternative implementation/branch | 有 sibling 证据的替代路径 |
| `reachable_from` | project/file/macro invocation → implementation/symbol | 由已证明的关系路径派生的静态可达性 |

输出按 Entity ID、Relation kind/source/target/ID 和 ProofPath ID 排序。GraphStore 中的插入或图库遍历顺序不得影响 snapshot。

### 6. include、宏与 sibling alternative 只实现有证据的有限语义

本地 quote include 先按 including file 的父目录解析，再按 workspace root 解析；恰好命中一个 workspace source file 时建立 complete `includes`。未命中、命中多个、system include 或需要未支持 include path 求值时，可建立外部/歧义 Entity 以保留事实，但关系/path 为 partial/unknown 并产生稳定 Diagnostic。

宏调用按名称、文件/include 可见性和位置建立候选。唯一可证明定义形成 complete `invokes_macro`；多定义、条件定义、重定义或缺失定义保留所有有证据候选并标记 ambiguous/partial。replacement 中对另一个宏的引用可继续链接，直到终端 symbol、循环或预算边界。

条件预处理结构按 source range 建立 condition group 和有序 branch。只有属于同一 group 的 sibling 才可比较。Knowledge 与规范化条件 token 用于给分支标注 `x86`、`riscv`、`generic`、`portable`、`scalar`、`fallback` 或 `unknown` role；有且仅有 x86 branch 与非 x86 sibling 的结构证据时建立 `alternative_to`。本阶段只记录替代关系，不判定它是否被目标构建选中，也不把存在 sibling 自动等价为完成迁移。

### 7. proof path 必须有界，失败原因是分析结果的一部分

首个实现采用 breadth-first search，默认 `maxDepth=8`、`maxVisited=10000`、每个 source/target 最多物化 4 条确定性路径；预算作为 Graph Analyzer 的显式不可变配置，可由测试 profile 注入但不通过全局状态修改。

遇到循环时使用 `(entity_id, depth)`/best-depth 去重并记录 cycle reason；超过深度、visited 或路径数预算时返回 partial/truncated；缺失 include、歧义宏定义、未支持预处理语义或不完整 parse 时返回 partial/unknown。只有端点、全部中间关系和解析语义均完整时，ProofPath 才能为 complete。

不存在路径与 unknown 必须区分：前者仅说明当前完整图中没有找到目标，后者说明输入或算法覆盖不足。Detector 和未来 Classifier 不得用 unknown 证明 RISC-V ready。

### 8. AVX 人工事实而非 Legacy Finding 数量是验收 oracle

新增版本化的 AVX evidence-graph baseline，记录 fixture identity、人工审计范围、事实计数和关键路径断言。验收至少验证：

- 37 个 C/C++ 文件的 39 个 header、362 个 vector type、360 个普通源码 intrinsic call 和 45 个 comment hint 不退化；
- 两个本地头文件的 12 个函数式 macro definition 被识别为定义而非调用；
- replacement body 的 18 个终端 intrinsic 引用具有独立 SourceSpan；
- 代表性调用点形成 `invokes_macro → expands_to/calls` 的跨文件 proof path；
- 同一输入重复运行产生相同 Entity、Relation 和 ProofPath ID/排序；
- 4 个 Makefile 的 24 个 x86 flag 明确记为 deferred build evidence，不纳入 graph 完整性结论。

Legacy 结果只用于说明兼容 CLI 仍未变化，不允许用 `legacy finding count == new observation/relation count` 作为断言。任何人工 baseline 变更必须带审计说明，不能由当前 scanner 输出自动重写。

### 9. Legacy 采用进口边界隔离，不在本 change 物理删除

新 `graph`、`analyzers`、相关 core/frontend/normalization 单元测试不得导入 `kb_scanner.adapters.legacy`、`kb_scanner.compile_commands`、`kb_scanner.cpp_frontend`、`kb_scanner.models`、`kb_scanner.rules` 或 `kb_scanner.report`。以 AST/import inventory 测试固化该规则。

默认 `kb-scanner scan` 继续使用 `create_legacy_application()`，legacy 文件保持只读。qualification 通过独立 factory 创建真实 staged profile，不复用 legacy parser/evaluator/YAML。物理删除 Legacy 和默认入口切换留给最终 cut-over change。

### 10. 每个业务模块具有隔离单元测试，并只在测试容器安装依赖

建立/扩展机器可读 test inventory，使以下模块分别映射到 unit suite：

- Frontend macro extraction/vocabulary → fake Tree-sitter nodes/bytes，不加载真实 grammar；
- macro normalization → core Entity/Evidence fixtures，不读取真实文件或 manifest；
- GraphStore protocol/NetworkX adapter → 小型领域图，不读取项目；
- entity index/relation builder/alternative resolver → fake NormalizedSnapshot/KnowledgeSnapshot；
- proof resolver → fake GraphStore，覆盖 cycle、ambiguous、not-found 和 budget truncation；
- qualification profile/orchestrator glue → recording stages，不写 artifact；
- legacy isolation → AST/import inventory，不执行 legacy scanner。

这些模块各自参加至少 90% line / 80% branch 覆盖门禁；真实 Tree-sitter/libclang、真实 knowledge JSON、AVX baseline、NetworkX 性能测试和 staged integration 作为独立高层测试，不计入隔离单元覆盖数字。NetworkX 只锁定在 `Dockerfile.test`/测试依赖，不在宿主机安装，也不修改生产镜像或根 Compose。

容器基准至少覆盖 1,000 Entity/3,000 Relation smoke graph、预算截断和 AVX fixture。初始验收预算为 graph 阶段单次运行不超过 15 秒且相对进程峰值 RSS 增量不超过 512 MiB；基准输出必须记录 Python/NetworkX 版本、输入规模和预算。若超限，先优化或替换 adapter，不改变领域合同。

## Risks / Trade-offs

- [Tree-sitter 宏字段在 C/C++ grammar 版本间变化] → 锁定测试容器版本，以 fake-node 单测验证字段缺失分支，并用真实 component fixture 验证支持版本。
- [不执行完整预处理器会产生多定义和可见性歧义] → 保留候选关系和 partial/unknown，不任选一个定义制造确定结论。
- [为 replacement token 增加 Evidence 会提高内存占用] → 只保留宏参数和有意义 token，不生成所有源码 identifier，并用 AVX/合成图基准约束。
- [Knowledge 参与 branch role 标注可能随知识版本变化] → Relation/proof 保留 KnowledgeEntry provenance，扫描结果记录既有 knowledge identity/version。
- [NetworkX 对更大项目可能过重] → GraphStore 合同隔离 adapter，资源超限时可换紧凑 adjacency 实现而不改 frontend/analyzer/report。
- [默认 CLI 仍是 Legacy，用户暂时看不到 graph 结论] → qualification 明确标记为内部 staged 验收；等 Build、Classifier、Projector 完成后统一 cut-over，避免半成品报告。
- [人工 AVX baseline 也可能审计错误] → baseline 保存具体文件/span/类别与审计说明，变更必须人工 review，不能由 scanner 自更新。

## Migration Plan

1. 先扩展 core 合同、Analyzer protocol 与 recording stage，保持默认值和现有测试构造兼容。
2. 扩展 Frontend vocabulary/Tree-sitter macro extraction 与 Normalizer，并完成隔离单元覆盖门禁。
3. 将 technology spike 收敛为正式 GraphStore protocol 和 NetworkX adapter；spike DTO 不进入正式模块。
4. 实现 Entity index、Relation builder、alternative resolver 和 bounded proof resolver。
5. 在 qualification profile 中替换 `_EmptyAnalyzer`，更新 behavior acceptance 中 `macro-and-alternative-reachability` 的状态，仍保留 build/classification deferred。
6. 加入 AVX 人工 baseline、架构隔离测试、性能/内存基准和完整容器回归。
7. 保持默认 CLI/Legacy 和报告 artifact 不变；若 staged qualification 失败，只回滚 qualification factory 与新模块，不涉及用户报告数据迁移。

## Open Questions

- `alternative_to` 在后续 Build Selection 接入后是否需要细分为 source alternative、branch alternative 和 implementation alternative；本阶段通过 Entity kind 与 metadata 表达，暂不增加更多 relation kind。
- AVX 之外用于 conditional sibling 的第二个真实项目 fixture 选哪一个；本 change 至少提供合成的 x86/RISC-V、x86/generic 和缺失 sibling 三类 fixture。

## Resolved Decisions

- 2026-09-07 在唯一 `kb-scanner-test` 容器内以锁定的 libclang 18.1.3 和 `PARSE_DETAILED_PROCESSING_RECORD` 验证函数式宏。`MACRO_DEFINITION.get_tokens()` 可重复返回宏名、参数与 replacement token 的逐 token extent，因此 Clang producer 作为 compilation-context enrichment 接入；Tree-sitter 仍是没有 compilation database 时始终存在的正式 baseline。两者通过相同 source span/canonical token 在 Normalizer 合并 provenance，Clang 不取代 baseline，也不执行预处理指令、编译或项目代码。
