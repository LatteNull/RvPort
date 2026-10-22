## 1. 协议、契约与兼容基线

- [x] 1.1 审计 R1/R1.1、P2/P3、A3/A4/A5 实际 schema、artifact identity、CLI 与缓存边界，形成 R2 字段映射和“已有字段／需独立补充事实／禁止推断”清单。
- [x] 1.2 在协议清单和 JSON Schema 中增加 `ConcurrentAccessCandidateRequest v1`、`ConcurrentAccessProjectionFacts v1`、`ExecutionInstanceBindingOverlay v1`、`AccessProtectionOverlay v1`、`ConcurrentAccessCandidateGraph v1` 与 `ConcurrentAccessCandidateReport v1`，保持既有版本不变。
- [x] 1.3 实现六类 artifact 的规范化序列化、内容摘要、稳定排序、引用闭包与 kind/id/digest/schema/producer 校验，覆盖损坏、未知版本、陈旧 digest 和循环引用。
- [x] 1.4 实现 scope/profile/target/ABI/DataLayout/physical-TU/source-BC-lineage 相容性检查，并为每类拒绝原因提供稳定 code 及中英文 detail/limitation/suggestion。
- [x] 1.5 增加旧 P1–P4、A1–A5、R1/R1.1 schema、golden artifact、命令和缓存兼容回归，证明未请求 R2 时历史行为和 semantic digest 不变。
- [x] 1.6 为本组全部新增、修改或复用的 Python/C++ 自有逻辑增加正常、边界、异常和 unknown 单元测试，并将所有新模块纳入覆盖率源码枚举。

## 2. Root demand 与访问投影

- [x] 2.1 实现 `RootDrivenAnalysisPlan` 与 `ThreadEntryRootOverlay` 适配器，以 physical creation site、model 和 callback identity 规范去重 base/overlay roots，并保留 adopted-from、冲突和 conditional frontier。
- [x] 2.2 建立 demanded root/context/function/TU 分母，只允许 demanded P2 effects 进入 R2；记录 observed-but-not-demanded 计数且禁止回退到 `all-defined`。
- [x] 2.3 定义 `AccessInstance` identity 和 read/write/rmw/cas-success/cas-failure/unknown operation lattice，严格区分原始 AST/IR/effect 节点、invocation 和分析生成的动态访问实例。
- [x] 2.4 实现 P2 effect 到调用上下文、执行实例、guard、atomicity、对象候选和半开字节范围的投影，覆盖同一摘要多创建点实例化和多证据路径去重。
- [x] 2.5 仅在既有事实不能无损表达所需局部信息时实现独立 `ConcurrentAccessProjectionFacts` worker/adapter，并确保空补充事实也是合法、可验证且内容寻址的产物。
- [x] 2.6 对 AST-only、IR-only、no-debug、source/IR conflict、缺失 effect 和访问投影预算耗尽实现非空依赖 frontier，不用空访问集冒充完成。
- [x] 2.7 为 demanded slicing、访问 identity、operation、guard/range、重复观察、不可达 store 和所有降级路径增加有效单元测试。

## 3. 执行实例绑定与 scope 级 MHP

- [x] 3.1 实现 `ExecutionInstanceBindingOverlay`，分别保存 `ExecutionRoot`、`ThreadContext`、`ThreadInstance` 和普通 invocation，禁止 context cache 复用动态实例 identity。
- [x] 3.2 组合多个 root 的 P3 pthread 实例、create/join/handle/lifecycle 证据并建立 scope 级 execution family，修复“不同 root 未比较即被忽略”的空洞。
- [x] 3.3 采用 R1.1 exact `thrd_create` 创建独立 C thread instance，保留 C API/profile/callback SSA 证据且不依赖 C++ 模型或伪造 pthread identity。
- [x] 3.4 组合 A3 的 `std::thread` callback、对象、move、join/detach 和 lifecycle；不同创建点复用 context但保持不同 instance及 guard/cardinality。
- [x] 3.5 对 exact `std::jthread` 和 `std::launch::async` 只建立证据支持的 may-parallel 区间；排除 deferred，令默认/组合 async policy 进入 conditional frontier，不猜测 future wait或自动 join。
- [x] 3.6 实现 `parallel-possible`、`not-parallel`、`unknown` MHP disposition；同一 single 实例自配对排除，merged/repeated 实例保留 self-concurrency 和未展开 cardinality。
- [x] 3.7 实现实例、MHP、生命周期、递归/SCC 与 repeated cardinality 独立预算及未处理 frontier，缺失跨 root 关系不得默认 `not-parallel`。
- [x] 3.8 增加 pthread、`thrd_create`、`std::thread`、`std::jthread`、async/deferred、跨 root、join/detach、merged/repeated、profile失配和预算单元测试。

## 4. 对象域、范围与有界候选配对

- [x] 4.1 实现 A5 must singleton、有限 may candidates 和 unknown 对象域适配，保留 storage instance、subobject path、union overlap group、lifetime、guard、address space和范围证据。
- [x] 4.2 实现 `must-overlap`、`may-overlap`、`must-disjoint`、`unknown` 比较，覆盖结构体字段、union重叠、嵌套指针、同名字段不同实例和半开字节边界。
- [x] 4.3 禁止以字段声明、类型名、显示字符串 key、局部 AA `NoAlias` 或 AST-only path单独建立跨实例 must-alias/noalias，并为每种拒绝生成稳定证据。
- [x] 4.4 按 scope/profile、对象候选、address space、byte range、execution family、thread instance和operation class建立有限倒排 bucket。
- [x] 4.5 实现 canonical pair identity、may-candidate 多 bucket去重及左右角色/guard/provenance合并，禁止全局 N² 或 unknown-address × all-access 配对。
- [x] 4.6 只在 MHP=`parallel-possible`、对象 must/may overlap且至少一侧 write/rmw/cas时生成 candidate；显式记录 same-single-instance、proven-not-parallel、read-read、must-disjoint和deferred exclusions。
- [x] 4.7 为 access、object candidate、bucket、alias comparison、MHP query、candidate pair、exclusion和输出分别实施预算，超限保留 hit/limit、已有结果和聚合 frontier。
- [x] 4.8 增加对象 lattice、range/union、字段实例、未知对象聚合、候选/排除、去重、桶边界和预算异常的单元测试及规模断言。

## 5. 受限保护与原子候选边界

- [x] 5.1 实现 `AccessProtectionOverlay`，把具体 access instance绑定到 A4 acquire/release、RAII destruction、owner、held-region和 mutex provenance，而不是按函数或类型抑制候选。
- [x] 5.2 仅在双方访问、实例、guard、成功 held-region、同一 exact 普通非 robust/recursive mutex、lifetime、profile/ABI和依赖切片闭合时标记 `protected-within-bounded-model`。
- [x] 5.3 对锁在访问区间外、异常释放不完整、mutex may/unknown、不同实例同名字段、未知 kind/RAII/wrapper和预算耗尽保留 unprotected candidate或 protection frontier。
- [x] 5.4 保留 ordinary/atomic、atomic/atomic、RMW/CAS 冲突 pair、memory-order和事件引用；禁止由 atomicity、P2 order或P3 reads-from candidate生成 SW/HB 或安全结论。
- [x] 5.5 对 fence、CAS failure order、RMW/CAS release sequence与复杂 modification order生成 `advanced-atomic-semantics-unsupported` frontier，确保 P4 finding/discharged 与风险退出码不变。
- [x] 5.6 增加 mutex内外、C pthread mutex、C++ RAII、异常路径、对象歧义、relaxed atomic、RMW/CAS/fence和P4兼容单元/集成回归。

## 6. 完整性、缓存、CLI 与报告

- [x] 6.1 实现按 root/context/TU/effect/access/instance/MHP/object/bucket/pair/protection 依赖切片传播的 planned/completed/partial/failed 分母，不相关失败只保留顶层诊断。
- [x] 6.2 实现 AST-only、开放 scope、缺失 definition、profile/ABI冲突、unknown external/synchronization、conditional async、依赖失败和所有预算类别的非空 frontier。
- [x] 6.3 实现 `concurrent-access-candidate-graph-v1` 独立缓存 namespace、完整 key和引用闭包复验；损坏、陈旧、failed、timeout或wall-clock partial不得作为成功命中。
- [x] 6.4 实现 cold/warm semantic digest 规范化，排除路径、时间和 cache hit观测字段，并断言候选、排除、保护和frontier语义一致。
- [x] 6.5 实现 `build-concurrent-access-candidates --request --artifact-store --output` CLI，要求新输出目录，只读显式输入且不执行 configure/build/link/目标程序、网络或SSH。
- [x] 6.6 实现确定性输出布局、双语报告、`safety=not_evaluated`、`findings=null` 及退出码 `0` complete、`2` partial/unknown/unsupported/frontier、`1` invalid/全部不可用，禁止风险码 `3`。
- [x] 6.7 为零候选闭合分母、存在候选但complete、各类partial/failed、目录已存在、cache损坏和中英文字段增加单元测试。

## 7. 四语言 fixture、人工 truth 与规模验收

- [x] 7.1 建立本项目内 C11、C17、C++17、C++20 独立 fixture和provenance manifest，覆盖单 TU、跨 TU、no-debug、AST+IR、IR-only、AST-only及编译/分析失败。
- [x] 7.2 增加 C pthread/`thrd_create`、全局/struct/union/指针字段、mutex内外和C linkage正反例，确保 C 分析不加载 C++ AST或标准库模型。
- [x] 7.3 增加 C++ `std::thread`/`std::jthread`/async/deferred、对象字段/同名mutex字段、move/join/detach、single/merged/repeated及ABI/profile frontier用例。
- [x] 7.4 从 `memory-model-ir-checker/samples` 选择必要样例进行最小化复制，记录原相对路径、内容摘要、许可证/来源和改写原因，并人工重标 candidate/protected/excluded/frontier，不使用旧 safe/unsafe标签作oracle。
- [x] 7.5 实现四语言 truth runner与断言，分别报告 planned/completed/failed、expected/actual pairs、protected/excluded/frontier、TP/FP/FN/abstention，不合并分母掩盖单语言缺口。
- [x] 7.6 建立固定规模输入的 candidate/bucket/frontier、CPU、wall time、峰值内存、输出大小和cold/warm cache基线，验证无全局笛卡尔积增长。
- [x] 7.7 增加 truth比较、provenance校验、零分母、重复pair、指标聚合、资源采集和失败报告的单元测试；离线门禁不得读取兄弟目录或访问外部服务。

## 8. 文档、质量门禁与交付

- [x] 8.1 新增 `doc/CONCURRENT_ACCESS_CANDIDATE_GRAPH.md`，说明架构、身份层、协议、CLI、支持矩阵、candidate/exclusion/protection/frontier、预算、缓存和证明边界。
- [x] 8.2 新增 `doc/CONCURRENT_ACCESS_CANDIDATE_GRAPH_VALIDATION.md` 与机器可读 acceptance，记录锁定环境、精确命令、版本/hash、测试数、四语言 truth、性能/内存/cache和覆盖 hit/total及报告位置。
- [x] 8.3 更新 README、整体架构文档和 `doc/IMPLEMENTATION_ROADMAP.md`；保留 R1.1 于 2026-09-23 已同步归档的事实，并只在required gate全部通过后将 R2标记为已实现。
- [x] 8.4 在全新开发容器输出目录运行全部 C++/Python 单元测试、集成、四语言 truth、旧协议回归、文档/链接/格式检查和 OpenSpec strict validation，保存完整命令与报告。
- [x] 8.5 验收项目整体、Python、C++及每个受影响自有模块行覆盖率和分支覆盖率均至少 90%，确认未加载源码纳入分母且无无效断言或不当排除。
- [x] 8.6 复核所有 artifact、acceptance和文档中的分母、状态、限制及中英文字段一致，确认编译成功、exit 0、零候选、protected、coverage或exact match均未被描述为 data race消除或程序安全证明。
- [x] 8.7 运行 `openspec validate build-concurrent-access-candidate-graph --type change --strict --no-interactive` 和最终 required gate；只有全部任务与验收通过后才声明具备同步主规格条件。
