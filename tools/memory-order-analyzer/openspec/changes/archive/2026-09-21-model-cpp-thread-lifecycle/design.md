## Context

P3 已用 `ThreadLocalFacts v1`、`ExecutionOrderFacts v1` 和 `ThreadContextGraph v1` 建模直接 POSIX pthread 生命周期；A1 提供精确源实体、跨 TU 索引和 SourceIRBinding；A2 提供逐 TU AST/IR 可用性、候选相关依赖切片和 unknown 降级。现有边界刻意不识别 `std::thread`：标准库通过模板、closure、成员函数和 ABI wrapper 将一个源级构造展开为多层调用，单靠 AST 类型、mangled name 或 IR 中出现 `pthread_create` 都不足以证明用户 callback、线程对象和动态线程实例之间的关系。

A3 必须在不改变 P1–P4、A1、A2 已发布 schema 和报告含义的前提下增加 C++17/C++20 能力；未请求 A3 时现有结果逐字义兼容。C11/C17 仍走直接 pthread 模型。分析继续限定 GCC/Clang、显式 scope、compile-only、离线运行；不执行用户程序、构建脚本、SSH、DevKit 或网络操作。

主要消费方是线程关系与后续发布风险分析，但 A3 自身仍只输出生命周期和执行关系证据，`safety=not_evaluated`、`findings=null`。成功解析 `std::thread` 不等于程序安全，缺少 A3 sidecar 也不等于不存在 C++ 线程。

## Goals / Non-Goals

**Goals:**

- 定义独立版本化的 A3 请求、标准库 profile、局部事实、生命周期 overlay 和报告，以引用方式复用既有产物而不改写它们。
- 对 C++17/C++20 的受限 `std::thread` 构造、move、`join`、`detach`、`joinable` 和析构建立 AST 与 ABI/IR 双证据。
- 解析自由函数、lambda、成员函数和简单 functor callback，保持 callable、参数、对象、线程上下文与动态线程实例的独立身份。
- 仅在 profile、对象 provenance、唯一目标、成功 guard 和执行顺序完整时建立 start/join 生命周期关系；其余情况给出可定位 unknown/frontier。
- 让 A2 能按候选依赖切片传播标准库失配、wrapper 漂移、callable 歧义、对象逃逸和预算缺口。
- 为 C11、C17、C++17、C++20 提供独立回归分母、单元测试、离线语义矩阵、缓存/预算和至少 90% 行/分支覆盖率门禁。

**Non-Goals:**

- 不实现 `std::jthread`、`std::async`、线程池、任意 executor、自定义调度框架或未知线程 wrapper。
- 不实现完整 RAII mutex、condition variable、semaphore、rwlock、通用指针分析、fence、RMW/CAS 或 release sequence。
- 不建立通用 C++ happens-before 求解器，不输出风险、discharged、零 finding 安全结论，也不改变 P4 判定语义。
- 不支持 Windows、MSVC、clang-cl，不把 sibling archive、ARM DevKit、GenMC 或 herdtools7 作为运行依赖或正确性 oracle。
- 不从 `compile_commands.json` 推断完整链接图，不自动运行 CMake 或原生链接目标程序。

## Decisions

### 1. 采用独立 A3 协议和 overlay，不升级 P3 v1

新增以下严格、版本化产物：

- `CppThreadLifecycleRequest v1`：显式 scope、root、profile、依赖、模型选择和预算。
- `CppThreadLibraryProfile v1`：标准库/ABI/target/wrapper 模型身份和采用证据。
- `CppThreadLocalFacts v1`：逐 TU 源构造、ABI wrapper、线程对象操作、callable 与 handle 候选。
- `CppThreadLifecycleGraph v1`：线程对象状态、所有权转移、callback/context/instance、start/exit/join/detach 条件关系和 frontier。
- `CppThreadLifecycleReport v1`：分母、完整性、缓存、预算、双语诊断和既有产物引用。

所有引用均携带 schema、producer、policy、scope/profile 和 dependency digest。图中可以引用既有 `ThreadContext`/`ThreadInstance` 身份规则，但不重写 `ThreadContextGraph v1`；组合视图由 A3 adapter 显式产生。这样旧 P3 缓存和消费者不需要把缺失字段解释成新语义，回滚时可直接停用 A3 sidecar。

备选方案是把 P3 schema 升级为 v2。该方案会迫使所有 pthread 消费者和 P4 一起迁移，容易把 C++ 标准库模型错误变成基础线程事实，因此不采用。

### 2. 标准库模型按精确 profile 注册，不做符号名启发式

`CppThreadLibraryProfile` 的采用键至少包含：编译上下文/analysis profile、C++ 标准、标准库 vendor 与版本、C++ ABI、target triple、DataLayout/指针宽度、异常/RTTI 配置、线程后端、关键头文件与 wrapper 签名 digest、模型版本。首版在开发镜像中锁定并验证至少一个 libstdc++ profile 和一个 libc++ profile；其他版本只有全部资格匹配时才能采用同一模型。

模型只把已验证的标准库边界归约为规范化角色，例如 `construct-attempt`、`thread-entry-broker`、`join-attempt`、`detach-attempt`、`native-handle-transfer`；系统头内部节点保留证据引用但不无界展开。任何 wrapper 符号、参数角色、calling convention、异常出口或结构布局漂移均使采用失败并产生 `library-profile-unsupported` 或 `abi-wrapper-mismatch` gap。

备选方案是检测 `_M_start_thread`、`__thread_proxy` 或底层 `pthread_create` 名称。该方案无法区分 ABI 版本、参数 broker 和用户自定义同名 wrapper，会制造错误 callback 与 join 证明，因此禁止。

### 3. callback 采用 AST canonical callable 与 IR broker 的交集

源 worker 扩展但不改变 `SourceSemanticFacts v1` 原义：以 A3 独立 local facts 保存 `std::thread` 构造、模板实参、closure/functor 类型、`operator()`、成员函数指针、对象表达式、capture/参数初始化和线程对象操作。跨 TU 实体继续由 ProgramEntityIndex 唯一化，表达式/实体到 IR 的关系继续使用 SourceIRBinding 的 exact/candidate/ambiguous 等级。

正式 callback 目标必须同时满足：

1. 源端 callable canonical entity 和构造实参角色可解析；
2. IR 端标准库 broker/profile 被采用且 caller/callsite/object 绑定兼容；
3. 跨 TU definition、linkage、mangling、类型/ABI 与 scope 证据一致；
4. 候选集合在预算内唯一，或以有限 may-target 集合保守表达而不生成 must 关系。

自由函数直接绑定其 definition；lambda 绑定 closure 类型与 `operator()`，capture 只支持可绑定的按值/按引用有限字段；成员函数同时绑定 member entity 和对象候选；简单 functor 要求唯一可调用 `operator()` 且对象字段不逃逸。重载/模板歧义、虚调用、通用函数指针、复杂 `std::bind`、对象生命周期不明或候选超限进入 unknown。

### 4. 用线程对象所有权状态机表达 move、join、detach 和析构

每个线程对象实例有有界状态格：`empty`、`construction-pending`、`joinable`、`joined`、`detached`、`moved-from`、`failed`、`terminated-path`、`unknown`。状态转移带 AST/IR anchor、guard、异常/返回出口和 provenance：

```text
construct attempt ──success──▶ joinable ──join success──▶ joined
        │                         │  └────detach success──▶ detached
        └────throw/fail──▶ failed │
                                  └────move──▶ destination joinable
                                                source moved-from
```

move construction/assignment只有在源/目标对象、所有权和路径可证明时转移 native handle token；目标已 joinable、self move、覆盖、phi/select、多候选或逃逸按标准语义和证据能力进入 terminated/unknown，不任选实例。`joinable()` 只作为状态查询/guard，不等于 join 成功。join/detach 的异常或错误路径不产生完成边。joinable 对象析构只记录可能 terminate 的路径，绝不隐式 join/detach，也不产生 HB。

### 5. ThreadContext 与 ThreadInstance 继续分离，join 只补充条件化完成关系

可复用 `ThreadContext` 由 callback、抽象参数、profile/scope 和策略决定；`ThreadInstance` 由 root、父实例、构造调用实例、对象/handle lineage、guard 和 cardinality 决定。相同 lambda/functor 在两个构造点必须产生不同实例；循环、递归和重复构造使用 merged/repeated 实例桶并保留可能自并行语义。

只有 callback、构造成功、唯一/有限 handle 所有权、worker exit、join 成功和父线程 join 后继执行顺序均完整时，A3 才生成 worker-exit → join-complete → parent-successor 的条件边。`detach` 只切断 join 所有权并保持潜在并行；对象析构、`joinable()`、源码顺序、P2 `EffectSummary.order` 或仅存在底层 pthread 调用都不能生成完成、SW 或 HB。

### 6. A2 按候选依赖切片吸收 A3 gap

A3 gap 至少包括 profile 不支持、ABI wrapper 不匹配、callable ambiguous、object/handle provenance unknown、move ownership unknown、construct/join/detach outcome unknown、exception path unknown、scope definition missing、budget frontier。每个 gap 引用 TU、实体、对象、调用、线程候选、路径、依赖 digest 和中英文原因。

与候选可证明无关的 A3 gap 不抹除既有 pthread 或 P4 assessment，但顶层完整性仍记录；可能相关时，A2 将目标候选降为 partial/unknown。AST-only 只能保留 `std::thread` source candidate，不能建立动态线程实例、start/join、MHP、RF/SW/HB、risk 或 discharged。

### 7. CLI、缓存与退出语义保持分析型而非风险型

提供 `model-cpp-thread-lifecycle --request --artifact-store --output --source-worker --ir-worker`。输出目录必须新建且为空，不扫描“最新”产物，不扩大 scope。分层缓存键包含协议/策略、全部依赖 digest、profile/model、标准库/ABI、预算类别和工具链；wall-clock timeout/crash 不作为长期语义 cache hit。相同输入的 cold/warm `semantic_digest` 必须一致。

退出码定义为：完整合法生命周期结果 `0`；partial/unknown/unsupported/预算截断 `2`；请求或依赖无效、输出目录冲突、所有计划项均 failed `1`。A3 不使用风险退出码 `3`。报告保持 `safety=not_evaluated`、`findings=null`，并同时提供中文字段与对应英文说明字段。

### 8. 测试按语言与证据模式分层

单元测试覆盖协议、验证、profile 采用/拒绝、callable 解析、对象状态机、move、实例化、join/detach、递归/预算、缓存、CLI 和双语诊断。离线语义矩阵包含 C++17/C++20 的单 TU/跨 TU、自由函数、lambda、成员函数、functor、move、join、detach、无 debug、开放 scope、构造失败、异常路径、ABI/profile mismatch 和预算；至少分别验证锁定 libstdc++ 与 libc++ profile。C11/C17 继续运行直接 pthread create/join 基线，证明 A3 未使 C 依赖 C++ 模型。

生命周期 truth 统计预期 context、instance、callback、start/join/detach relation 和 unknown，不把它混成风险 TP/FP/FN；若同时运行旧 P4 truth，风险指标仍由既有人工真值独立报告。整体、C++、Python/C++ 实现语言及每个受影响自有模块的单元行/分支覆盖率均至少 90%，集成 profile 不合入单元覆盖率。

### 9. 文档与可观察验收

新增 `doc/CPP_THREAD_LIFECYCLE.md` 描述协议、CLI、支持矩阵、证据链、退出码和边界；新增 `doc/CPP_THREAD_LIFECYCLE_VALIDATION.md` 与机器可读 acceptance JSON 记录实际命令、锁定标准库 profile、测试数、四语言分母、关系 truth、cold/warm、预算和覆盖率；更新 `doc/IMPLEMENTATION_ROADMAP.md` 与 `doc/README.md`。文档不得把成功解析、零关系或 P4 零 finding 表述为线程安全。

## Risks / Trade-offs

- [标准库实现和 ABI 易漂移] → profile 采用绑定版本、target、ABI、头文件和 wrapper digest；漂移立即失效并降级，不靠宽松符号匹配继续分析。
- [AST callable 与 IR broker 多对多] → 仅取兼容证据交集并保留基数；不唯一时输出有限候选/unknown，禁止任意选取。
- [模板/系统头展开导致时间和体积增长] → 用系统边界摘要、节点/候选/输出/墙钟预算与 frontier；缓存按模型和预算类别隔离。
- [move 与异常路径造成所有权错误] → 使用带 guard 的对象状态格和 native handle lineage；覆盖、逃逸、目标 joinable 或异常未解析时不生成 must join。
- [底层 pthread 调用被双重计数] → 标准库边界内的 broker 调用标记为 A3-owned implementation evidence，不作为独立用户 pthread create；跨模型去重保留来源。
- [A3 gap 使既有正式结果过度降级] → 依赖切片证明相关性；无关 gap 只影响顶层完整性，C pthread 基线有独立回归。
- [libc++ 环境不可复现] → 将开发镜像依赖、版本和 profile 固定；若无法实际安装并验证，相关验收保持未完成，不能以合成 fixture 宣称支持。
- [覆盖率达标但语义错误] → 单元覆盖率、生命周期人工 truth、负向采用用例和旧 P1–A2/P4 回归分别验收，不以编译成功替代语义断言。

## Migration Plan

1. 先增加 schema、模型注册与验证器，旧 CLI 和缓存完全不读取 A3 产物。
2. 增加 source/IR 局部事实提取和 profile 探测，以 report-only 模式验证，不接入 ThreadInstance。
3. 增加 callable 绑定、线程对象状态机和生命周期图，再接入 P3 identity adapter 与 A2 gap adapter。
4. 增加 CLI、分层缓存、双语报告、四语言 fixture 和旧协议回归。
5. 在锁定开发容器全新目录运行全量质量、语义 truth、libstdc++/libc++ profile、cold/warm 和文档门禁；所有 required gate 通过后才同步/归档。

回滚时停用 A3 CLI/adapter 并删除 A3 cache namespace；P1–P4、A1、A2 产物和缓存无需迁移或重写。未来 schema 升级必须使用新版本和显式转换/拒绝，不能把缺失 A3 字段解释为无 C++ 线程。

## Open Questions

- 实施时需要从锁定开发镜像实测并记录首批 libstdc++ 与 libc++ 的精确版本、ABI fingerprint 和 wrapper 签名；在实测完成前不把具体版本号写成已支持事实。
- `std::thread` move assignment 在目标对象仍 joinable 时涉及 terminate 路径；首版是否能证明该路径取决于 IR/异常出口质量，不能证明时固定降级而不扩展成通用异常分析。
- 捕获 lambda 和成员函数对象 provenance 的首版候选上限需要通过 fixture 与性能基线确定；无论阈值为何，超限语义固定为 partial/unknown。
