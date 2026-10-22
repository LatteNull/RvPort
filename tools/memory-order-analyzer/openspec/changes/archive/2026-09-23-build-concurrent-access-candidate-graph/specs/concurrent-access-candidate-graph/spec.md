## ADDED Requirements

### Requirement: Publish additive versioned concurrent-access artifacts
系统 SHALL 新增独立版本化、内容寻址的 `ConcurrentAccessCandidateRequest v1`、`ConcurrentAccessProjectionFacts v1`、`ExecutionInstanceBindingOverlay v1`、`AccessProtectionOverlay v1`、`ConcurrentAccessCandidateGraph v1` 和 `ConcurrentAccessCandidateReport v1`。请求 MUST 显式引用 scope、R1 plan、R1.1 overlay 及所需 P2/P3/A3/A4/A5 artifact 的 kind、id、digest、schema 和 producer identity，并验证 profile、target、ABI、DataLayout、physical TU、source/BC lineage 与引用闭包；实现 MUST NOT 修改 P1–P4、A1–A5、R1 或 R1.1 的既有 schema、缓存和报告语义。

#### Scenario: All upstream artifacts are compatible
- **WHEN** 请求引用的 scope、profile、target、DataLayout、lineage、schema 和 digest 完整一致
- **THEN** 系统创建独立 R2 artifact 闭包，并保留每条派生事实到上游 artifact 的稳定引用

#### Scenario: An upstream digest or ABI conflicts
- **WHEN** 任一依赖 digest、profile、target、ABI、DataLayout 或 physical TU identity 不一致
- **THEN** 系统拒绝相关组合并生成 dependency-mismatch 诊断，不读取同目录其他产物代替，也不改写上游 artifact

### Requirement: Use root-driven reachable demand as the analysis denominator
系统 SHALL 以 `RootDrivenAnalysisPlan v1` demanded functions/contexts/TUs 与 `ThreadEntryRootOverlay v1` adopted roots 的规范化并集作为 R2 分母，只实例化该可达需求切片内的内存 effects。相同 physical creation site、model 和 callback identity MUST 去重；observed-but-not-demanded facts不得参与候选。source-candidate、conditional、ambiguous、unsupported 和 failed 入口 MUST 进入候选相关 frontier，系统 MUST NOT 回退到 all-defined 或全 BC load/store 扫描并宣称完整。

#### Scenario: A demanded worker has memory effects
- **WHEN** exact root/overlay 将 worker context 列入 demand，且 P2 effect 引用完整
- **THEN** 系统实例化该 context 的访问并把它纳入访问分母

#### Scenario: An unreachable function contains a store
- **WHEN** scope 内函数含有 IR store，但不属于任何正式 root 的 demanded slice
- **THEN** 系统不从该 store 生成 R2 access/candidate，并在审计计数中将其标为 observed-but-not-demanded

#### Scenario: A related conditional async site exists
- **WHEN** demanded slice 包含默认或 async|deferred `std::async` site
- **THEN** 系统生成 conditional frontier，不能通过扫描其 callback 或假定 async 来形成正式并发实例

### Requirement: Project effects into execution-specific access instances
系统 SHALL 将 P2 effect 或 R2 独立局部投影事实实例化为 `AccessInstance`，其身份 MUST 区分 scope/profile、root、reachable context、function invocation、原始 effect/event、执行实例、operation kind、atomicity、guard、对象候选域、半开字节范围和 cardinality。原始 AST/IR 节点 MUST 与分析生成的 access instance 分离；同一 effect 在不同创建点或调用上下文不得合并，同一动态访问的重复证据观察必须规范去重。

#### Scenario: One summary is used by two thread sites
- **WHEN** 两个创建点复用同一 callback 与 `EffectSummary`
- **THEN** 系统复用效果模板但生成不同 execution-bound access instances，并保留各自 root、site、guard 和实例来源

#### Scenario: One IR access is observed through two evidence paths
- **WHEN** P2 与局部投影都引用同一 invocation 中的同一原始访问
- **THEN** 系统按 canonical identity 生成一个 access instance并合并证据引用，不重复增加候选分母

### Requirement: Bind execution roots, contexts, instances and invocations without conflation
`ExecutionInstanceBindingOverlay` SHALL 分开表达 `ExecutionRoot`、`ThreadContext`、`ThreadInstance` 和普通 function invocation，并在显式 scope 内组合多 root P3 图、R1.1 入口及 A3 生命周期。`pthread_create`、`thrd_create`、经验证的 `std::thread`/`std::jthread` 和显式 `std::launch::async` MUST 保留各自模型与证据；`std::launch::deferred` MUST 不生成并发实例，默认或组合 policy MUST 进入 conditional frontier。函数名、类型名、mangled symbol 或底层 broker 名称不得单独建立实例。

#### Scenario: Pthread instances originate in different root plans
- **WHEN** 两个 exact 创建点位于同一 scope 的不同 R1 root plan且可能同时存活
- **THEN** overlay 在 scope 级保留两个 root 和实例身份，并可建立跨 root MHP disposition，而不是因 root_id 不同忽略比较

#### Scenario: A C11 thrd_create site is exact
- **WHEN** R1.1 以 C API profile、callback SSA 与 source binding 精确采用 `thrd_create`
- **THEN** overlay 建立独立 C thread instance并保留其模型，不要求或伪造 pthread identity

#### Scenario: Async execution is deferred
- **WHEN** launch policy 被证明仅为 `std::launch::deferred`
- **THEN** overlay 保存 deferred exclusion且不创建可并行 thread instance

#### Scenario: Jthread lifecycle is incomplete
- **WHEN** `std::jthread` 创建精确但自动 join 或 stop 生命周期证据不足
- **THEN** overlay 只保留已证明的 may-parallel 区间和 lifecycle frontier，不猜测 join-complete 或 HB

### Requirement: Model possible parallelism and dynamic cardinality conservatively
系统 SHALL 为可比较执行实例发布 `parallel-possible`、`not-parallel` 或 `unknown` MHP disposition及其 proof/limitation。只有 `parallel-possible` 可进入候选配对；`not-parallel` MUST 形成显式排除；`unknown` MUST 形成 frontier。不同 root 缺少关系不得解释为 `not-parallel`。同一 `single` 动态实例与自身 MUST 排除；`merged`/`repeated` 抽象实例 MUST 保留与自身其他潜在动态实例并行的语义。

#### Scenario: Join proves two accesses cannot overlap
- **WHEN** 完整生命周期证明 worker 已退出且 join 成功后父实例才执行第二个访问
- **THEN** pair 记录 `not-parallel` exclusion及生命周期证据，不生成并发候选

#### Scenario: One loop creates repeated workers
- **WHEN** 创建点位于循环且只能形成 merged/repeated 实例桶
- **THEN** 系统允许该桶形成 self-concurrency 比较，并保存 cardinality 与未展开动态实例限制

#### Scenario: Cross-root MHP evidence is missing
- **WHEN** 两个实例属于不同 root且没有足够生命周期证据判断是否并行
- **THEN** 系统输出 MHP unknown frontier，不默认为并行候选或不并行排除

### Requirement: Compare object candidates and byte ranges using bounded provenance
系统 SHALL 消费 A5 `must` singleton、有限 `may` candidates 或 `unknown` 对象域，并以 storage instance、subobject path、union overlap group、address space、lifetime、guard 和半开字节范围发布 `must-overlap`、`may-overlap`、`must-disjoint` 或 `unknown`。must/may overlap 可参与候选；must-disjoint MUST 显式排除；unknown MUST 进入 frontier。字段声明、同名字段、类型名、显示字符串 key、局部 AA 结果或 AST-only path不得单独建立跨实例 must-alias/noalias。

#### Scenario: Two ranges overlap on one exact object
- **WHEN** 两个 access 绑定同一 exact storage且半开字节范围相交
- **THEN** 系统发布 must-overlap及 A5/layout/range 证据

#### Scenario: Different objects use the same mutex field declaration
- **WHEN** 两个 C++ 对象引用相同 `FieldDecl` 但 storage instances 不同
- **THEN** 系统不得因字段声明相同而合并对象或 mutex identity

#### Scenario: Union members have different names
- **WHEN** 两个 access 指向同一 union storage 的不同成员
- **THEN** 系统依据 overlap group保留重叠，不用成员名或类型证明 disjoint

#### Scenario: AST-only provides a source path
- **WHEN** 相关 TU 只有 AST member path而没有运行时 IR/provenance 绑定
- **THEN** 系统保存 source object candidate和 object-unknown frontier，不发布 runtime overlap/disjoint 结论

### Requirement: Generate candidate pairs only from parallel overlapping conflicts
`ConcurrentAccessCandidateGraph` SHALL 只在两个 demanded access 的执行实例为 `parallel-possible`、对象为 must/may overlap且至少一侧为 write/rmw/cas时生成规范化候选 pair。系统 MUST 显式记录 `same-single-instance`、`proven-not-parallel`、`read-read`、`must-disjoint` 和 `deferred-execution` 排除理由；对象或 MHP unknown 不得伪装为排除。候选 MUST 保存左右 access、root/context/instance、object/range、guard、operation、atomicity、证据等级和依赖切片。

#### Scenario: Parallel write and read overlap
- **WHEN** 两个不同可能并行实例访问 must/may overlap 对象且一侧 write、另一侧 read
- **THEN** 系统生成一个规范化 candidate pair并保留 overlap/MHP/effect 证据

#### Scenario: Two parallel reads overlap
- **WHEN** 两个可能并行实例只执行 read且范围重叠
- **THEN** 系统记录 read-read exclusion而不生成冲突候选

#### Scenario: One pair is discovered from multiple buckets
- **WHEN** may object candidates使同一 access pair出现在多个有限 bucket
- **THEN** 系统按 canonical pair identity 去重并合并各 bucket/provenance 证据

### Requirement: Require complete access-level evidence for bounded mutex protection
`AccessProtectionOverlay` SHALL 仅在双方 access instance、执行实例、成功 acquire/release 或 RAII destruction、held-region、同一 exact 普通非 robust mutex、owner、对象 lifetime、profile/ABI、guard和依赖切片均完整时，将候选标记为 `protected-within-bounded-model`。P3 mutex candidate、函数内出现 lock、源码词法作用域、类型名、字段名或不完整 A4 owner不得单独保护候选；证据不足 MUST 保留 unprotected candidate 或 protection frontier。保护标记 MUST NOT 表示函数或程序安全。

#### Scenario: Both accesses are inside complete same-mutex regions
- **WHEN** A4 将两个 access 精确绑定到各自成功持有同一受支持 mutex 的 held-region，且异常/释放路径完整
- **THEN** pair 标记 `protected-within-bounded-model` 并保存双方 region、mutex、owner 与依赖证据

#### Scenario: A lock exists outside one access region
- **WHEN** 函数含同一 mutex lock但至少一个 access 不在已证明 held-region 内
- **THEN** 系统不得保护该 pair，并保留 unprotected candidate或具体 protection frontier

#### Scenario: Mutex provenance is ambiguous
- **WHEN** 任一侧 mutex 对象只有 may/unknown provenance或指向不同实例的同名字段
- **THEN** 系统生成 protection-unknown frontier，不任选一个 mutex 进行抑制

### Requirement: Preserve atomic pairs without inventing advanced atomic semantics
系统 SHALL 保留涉及 atomic、rmw 或 cas 的并发重叠 pair及 memory-order/event 引用，供 P4/A6 消费；atomicity本身不得排除候选。`EffectSummary.order`、P3 reads-from candidate、源码顺序或同对象 release/acquire 不得单独建立 synchronizes-with、happens-before 或安全结论。涉及 fence、RMW/CAS release sequence、CAS failure-order、复杂 modification order 的语义 MUST 标记 `advanced-atomic-semantics-unsupported` frontier，R2 MUST NOT 修改 P4 finding/discharged。

#### Scenario: Two relaxed atomic accesses overlap
- **WHEN** 两个可能并行实例对同一 atomic object执行冲突访问
- **THEN** R2 保留 atomic candidate和 order证据，但不输出 publication risk、data race 或安全结论

#### Scenario: A CAS may participate in a release sequence
- **WHEN** candidate证据包含 CAS/RMW且判定需要 release-sequence 语义
- **THEN** 系统保留 pair并生成 A6-oriented unsupported frontier，不在 R2 内补造 SW/HB

### Requirement: Bound pairing without global Cartesian expansion
系统 SHALL 按 scope/profile、对象候选、address space、byte range、execution family、thread instance 和 operation class建立有限 bucket，只在可比较 bucket 内枚举 pair。完全 unknown 对象或实例域 MUST 生成按候选依赖切片聚合的 frontier，不得与全部 access进行全局笛卡尔积。请求 MUST 分别限制 access、instance、object candidate、bucket、alias comparison、MHP query、candidate pair、exclusion、protection query、frontier、递归/SCC、诊断、输出字节、worker/request CPU 和 wall time；耗尽 MUST 保留已知结果、hit/limit 和未处理域。

#### Scenario: Unknown addresses occur in many roots
- **WHEN** 多个 root 含无法建立有限对象候选的访问
- **THEN** 系统按相关 root/context/object-domain 生成聚合 frontier，不生成 unknown-access × all-access pairs

#### Scenario: Pair budget is exhausted
- **WHEN** 已达到 candidate-pair limit且仍有可比较 bucket未处理
- **THEN** 系统保留已有 candidates/exclusions、准确 hit/limit 和非空 budget frontier，报告为 partial且退出码为 `2`

### Requirement: Propagate candidate-related completeness by dependency slice
报告 SHALL 分别记录 roots、contexts、TUs、effects、accesses、instances、MHP、object bindings、buckets、candidate pairs、exclusions、protection queries和 frontier 的 planned/completed/partial/failed 分母。AST-only、开放 scope、缺失 definition、profile/ABI冲突、unknown external/synchronization、conditional async、依赖失败和预算耗尽 MUST 关联到受影响候选切片；不相关失败不得降低独立 slice，但必须保留顶层诊断。零候选只有在全部相关分母闭合时可记录 complete empty，且不得表示无 data race 或安全。

#### Scenario: One unrelated TU fails
- **WHEN** 失败 TU 被证明不属于候选 A 的 root/reachable/object/protection 依赖切片
- **THEN** 候选 A 的 slice可保持 complete，同时顶层 scope报告保留该 TU failure

#### Scenario: A relevant external call is unknown
- **WHEN** unknown external可能修改候选对象或影响同步/实例关系
- **THEN** 相关 slice降级为 partial并生成非空 frontier，不把零候选或未保护候选解释为完整结论

#### Scenario: No candidate is produced in a closed request
- **WHEN** root、访问、实例、对象、MHP、保护和预算分母全部完成且候选为零
- **THEN** 报告只说明“请求范围内未形成 R2 候选”，并保持 `safety=not_evaluated`、`findings=null`

### Requirement: Cache and report R2 deterministically through an offline CLI
系统 SHALL 提供 `build-concurrent-access-candidates` CLI，只读取显式 request、artifact store和可选 worker，要求输出目录不存在，且 MUST NOT 配置/构建/链接/运行被分析程序、访问网络或 SSH。缓存 key MUST 包含 schema/producer、工具链、scope/profile/target/DataLayout、全部依赖 digest、模型、预算和实现 identity；损坏、陈旧、failed、timeout 或 wall-clock partial 条目不得作为成功命中，cold/warm semantic digest MUST 一致。报告 SHALL 固定 `safety=not_evaluated`、`findings=null`，为 detail/limitation/suggestion 提供中英文字段，并使用退出码 `0` complete、`2` partial/unknown/unsupported/frontier、`1` invalid/全部不可用，MUST NOT 返回风险码 `3`。

#### Scenario: A valid warm cache entry is reused
- **WHEN** 请求及全部依赖、模型、预算和实现 identity 完全匹配
- **THEN** warm结果与 cold结果的 graph、分类和 semantic digest一致，并仅在观测字段记录 cache hit

#### Scenario: The output directory exists
- **WHEN** CLI输出路径已存在
- **THEN** 命令拒绝覆盖并返回结构化失败及中英文修复建议

#### Scenario: Candidates exist in a complete graph
- **WHEN** R2完整生成一个或多个 candidate pairs且没有 frontier
- **THEN** CLI返回 `0` 而不是风险码，报告仍为 `findings=null` 和 `safety=not_evaluated`

### Requirement: Limit supported compilers, languages and platforms explicitly
R2 SHALL 支持 GCC/Clang profile下的 C11、C17、C++17 和 C++20，并分别保留语言、标准库与 API 模型来源。C pthread/`thrd_create` 路径 MUST NOT 依赖 C++ AST 或标准库 profile。Windows、MSVC 和 clang-cl MUST 明确 excluded；线程池、executor、自定义调度框架、通用函数指针、虚调用和通用 points-to MUST 保持 unsupported/frontier，除非未来独立 change 定义版本化模型。

#### Scenario: A C17 thrd_create program is analyzed
- **WHEN** C17 fixture使用 exact `thrd_create` 且依赖完整
- **THEN** 系统仅使用 C AST/API/profile建立实例与候选，不加载 C++ 标准库模型

#### Scenario: A Windows thread sample is present
- **WHEN** 语料包含 `CreateThread`、`_beginthreadex` 或 clang-cl/MSVC 配置
- **THEN** 系统记录 excluded/unsupported且不纳入支持 truth 分母，不尝试生成 BC/AST 兼容层

### Requirement: Document operation, proof boundaries and observed validation
实现 SHALL 更新 README、架构说明和 `doc/IMPLEMENTATION_ROADMAP.md`，并新增 `doc/CONCURRENT_ACCESS_CANDIDATE_GRAPH.md`、`doc/CONCURRENT_ACCESS_CANDIDATE_GRAPH_VALIDATION.md` 及机器可读 acceptance。文档 MUST 说明协议版本、数据流、身份层、CLI、支持矩阵、candidate/exclusion/protection/frontier、完整性、缓存、预算、退出码和后续 P4/A6/R3 边界；验证文档 MUST 区分设计、实际命令/结果、历史外部证据和 unknown。路线图 MUST 记录 R1.1 已于 2026-09-23 同步归档，并在 required gate完成前不把 R2标记为已实现。

#### Scenario: Documentation is checked at the required gate
- **WHEN** R2实现、truth、性能、缓存和覆盖率验证完成
- **THEN** 文档中的版本、命令、分母、实测结果、限制和状态与 artifact/acceptance 一致，且不把编译成功、exit 0、零候选或 protected 标记描述为并发安全证明
