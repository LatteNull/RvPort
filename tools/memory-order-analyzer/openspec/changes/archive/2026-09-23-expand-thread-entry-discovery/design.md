## Context

当前线程入口证据分布在三个层次：P3 识别直接 POSIX pthread 调用，A3 以 Clang AST 与已验证的 libstdc++/libc++ ABI broker 组合建模 `std::thread` 生命周期，R1 再对 P3/A3 候选做创建点对齐和 ExecutionRoot 规划。这个结构已经避免了纯 BC 反向猜测，但仍有以下缺口：

- `SourceSemanticFacts` 在访问 `CXXConstructExpr` 时会检查 constructor parent 的 canonical record，却把表达式节点的 `canonical_type` 输出为通用的 `expression`，下游无法审计实际选择的类型、构造函数与别名展开证据。
- R1 v1 的创建机制集中于 `pthread_create` 和 A3 `std::thread`，没有真正 C11/C17 `thrd_create`、C++20 `std::jthread` 或带 launch policy 的 `std::async` 入口模型。
- 归档 `memory-model-ir-checker` 通过类型 basename、API 名称和 receiver 名称启发式识别入口，会重复登记 `std::async`、把 `boost::thread` 当作标准线程，并把 `submit`/`post` 一类普通方法误当作调度入口的风险。其样例分类可复用，但实现不能成为依赖或正确性依据。
- “对象的类型是 `std::thread`”与“当前表达式创建了新线程”并不等价：默认构造不创建线程，move 只转移所有权，工厂返回可能转移已有对象；反之 `new std::thread` 和临时对象仍可能真实创建线程。

本 change 在 GCC/Clang 的 C11、C17、C++17、C++20 范围内增加独立线程入口发现层。AST 负责回答源码实体和语义类型“是什么”，BC/ABI 负责回答实际编译产物中是否存在相容的创建 broker、callback 和成功条件。两层证据通过显式 binding 组合，任何一层的缺失都不能被解释为不存在入口。

## Goals / Non-Goals

**Goals:**

- 发布独立 v1 请求、局部事实、创建点索引、root overlay 和双语报告，不修改 P1–P4、A1–A5、A3、R1 v1 的 schema 或语义。
- 将 spelled type、canonical semantic type、canonical record/entity、constructor declaration/kind、alias chain、声明来源及标准库 profile 保存为可审计证据。
- 正确区分默认构造、callable construction、move、工厂/返回值和真实线程创建，并在物理调用点级去重。
- 统一复用现有 `pthread_create`/`std::thread` 证据，新增 `thrd_create`、`std::jthread` 和有 launch-policy 语义的 `std::async` 入口发现。
- 保持 C 与 C++ profile、事实、truth 分母和诊断独立；C 路径不依赖 C++ AST 或标准库模型。
- 用新 overlay 扩展 root-driven 深度分析的输入视图，同时保留原始 R1 artifact 和报告不变。
- 对预算、缓存、失败、歧义、unsupported 和候选相关完整性给出确定、非空、可追溯的 frontier。

**Non-Goals:**

- 不扩展 A3 的 join/detach/析构状态机，不建模 `std::jthread` stop/join 生命周期或 `std::future` 的 wait/get 生命周期。
- 不从入口发现直接产生 MHP、sequenced-before、synchronizes-with、happens-before、风险或安全结论。
- 不支持 Windows、MSVC、clang-cl、`std::async` 的实现无关完整调度语义、Boost 生命周期、任意 executor/线程池、Linux `clone` flags 语义或自定义调度框架推断。
- 不引入通用函数指针/虚调用解析、通用 points-to、fence、RMW/CAS、通用 data-race 或通用 happens-before 求解。
- 不读取兄弟归档项目作为运行时或测试依赖，也不要求 SSH、ARM DevKit、网络、链接或运行目标程序。

## Decisions

### 1. 新能力使用 sidecar 与 overlay，而不是升级 R1 v1

新增 artifact 为：

- `ThreadEntryDiscoveryRequest v1`
- `ThreadEntryLocalFacts v1`
- `ThreadEntrySiteIndex v1`
- `ThreadEntryRootOverlay v1`
- `ThreadEntryDiscoveryReport v1`

request 通过 kind、schema、canonical digest 引用 scope、编译 profile、P1/A1 binding、P3、A3、A5 及适用的标准库/API model profile。`ThreadEntryRootOverlay` 引用而不重写 `ExecutionRootIndex v1` 和 `RootDrivenAnalysisPlan v1`，只保存新增或规范化的 root、它们的父创建点以及可达分析 demand。下游在显式启用本能力时消费 `R1 base + overlay` 复合视图；原 R1 命令、artifact、cache key、退出码和报告保持原样。

选择该方案是为了避免把新增 root kind 静默塞进既有 R1 enum。替代方案是发布 R1 v2，但当前变化主要是入口证据模型，不需要复制整个 reachable-plan 协议；若未来多个消费者都要求原生 root kind，再以单独 change 升级 R1。

### 2. AST 使用“已解析语义身份”，不使用类型字符串作为证明

Clang source worker 从 `CXXConstructExpr`、外层 `CXXNewExpr`、materialized temporary 和对应 `TypeLoc` 提取：

- 源码 spelling、canonical `QualType` 与去引用/去 cv 后的 record；
- canonical record declaration、USR/ODR 身份、声明来源、system-header/module 边界；
- 实际选中的 canonical constructor declaration、specialization、`default`/`callable`/`move`/`copy-or-deleted`/`other` kind；
- typedef/using/elaborated/inline-namespace alias chain；
- 对象表达式、callable、实参、receiver、宏 spelling/expansion 与异常/控制 guard；
- 编译 profile、标准库 vendor/version/ABI/target 与 model id。

标准类型采用由已验证 profile 登记的 canonical entity、声明来源和 ABI 指纹，qualified name 仅作诊断；不能只硬编码 `std::thread` 或 `std::__1::thread` 字符串。这样既能识别 `using Worker = std::thread` 和非限定名，也能拒绝 `foo::thread`、同名用户类型及未经登记的 `boost::thread`。

当前调用点只有在 AST 节点本身是受支持的 callable constructor 时才是 source create candidate。默认构造、move 和仅返回 `std::thread` 类型的调用记录为非创建操作；工厂内部若存在真实构造，应在其内部物理调用点单独发现。类型相同只是资格证据，不是创建证明。

### 3. AST 与 BC 独立发现，使用二维状态而非单一枚举压平语义

每个规范化 site 分别保存：

- `evidence_status`: `dual-exact`、`ir-exact`、`source-candidate`、`ir-candidate`、`ambiguous`、`unsupported`、`failed`；
- `execution_semantics`: `creates-thread`、`may-create-thread`、`does-not-create-thread`、`unknown`；
- `root_disposition`: `adopted`、`conditional-frontier`、`excluded`、`frontier`。

这避免把“证据精确”和“运行时一定并发”混为一谈。例如显式 `launch::deferred` 可以具有 `dual-exact` 证据，但语义是 `does-not-create-thread`；默认 `std::async` 也可以 `dual-exact`，但只能是 `may-create-thread` 和 `conditional-frontier`。

AST 与 BC 候选先取并集。对齐键以 physical TU/profile、SourceIRBinding、source/IR call identity、canonical callable、ABI/target/DataLayout、模型和 wrapper/broker role 为基础，不使用行号或 mangled name 单独对齐。相同物理表达式被 declaration、constructor、new/temporary 多条事实命中时按 canonical callsite identity 去重；不同调用点即使 callable 相同也不得合并。

### 4. C API 和 C++ 标准库采用不同的精确规则

`pthread_create` 和 `thrd_create` 使用锁定目标 ABI 的直接调用或已采用受限 wrapper、唯一 callback SSA、参数位置、handle/result 与成功条件。无 AST/no-debug BC 在 ABI、target、scope 和 callback 均唯一时可为 `ir-exact`。`thrd_create` 使用真正 C11/C17 `<threads.h>` fixture、C linkage、`thrd_t` 和 `int (*)(void *)` callback，不从旧 `.cpp` 样例推断 C 支持。

`std::thread`、`std::jthread` 和 `std::async` 必须同时具有相容 AST 语义事实、SourceIRBinding 和已验证 libstdc++/libc++ broker profile；单一符号、底层 `pthread_create` 或 IR-only mangled name不能成为精确采用依据。`std::thread` 可引用 A3 已验证 profile，但新增模型记录仍独立版本化，不修改 A3 profile。

`std::jthread` 入口解析记录普通 callable 与 profile 允许的隐式 `stop_token` 注入形式、实参映射和 constructor success guard；本 change 不建立 request-stop、析构 join 或 stop callback 生命周期关系。无法唯一判断选中的 invocable 形式时保持 ambiguous。

`std::async` 必须从 AST 恢复选中的 overload 和 launch-policy 值流：

- 已证明仅 `launch::async`：在 broker/callback 证据完整时采用线程入口；
- 已证明仅 `launch::deferred`：记录为非并发 site，不生成 root；
- 默认 policy 或同时允许 async/deferred：记录为可能创建线程并生成 conditional frontier，不作为确定 MHP/root 证明；
- policy 值不明、operator 组合超出预算或 profile 失配：unknown/unsupported。

### 5. 自定义 API 只允许显式模型，不做名称启发式

首版协议允许 request 引用显式版本化 framework descriptor，但内置 adoption 仅限本 change 明确支持的 API families。descriptor 至少绑定 canonical receiver/API entity、callable/receiver/argument role、同步或异步保证、实例 cardinality、library/version/ABI/target 和 broker digest。没有 descriptor 时，`submit`、`enqueue`、`post`、`boost::thread`、`clone` 等只可形成 unsupported/frontier，不能产生 root。普通 `Form.submit` 是强制负例。

该接口用于证明“不按名称猜测”的边界，不在本 change 内承诺任何第三方框架 profile。

### 6. Root overlay 保留上下文与动态实例分离

overlay 中的 `ExecutionContext` 由 canonical callable、抽象参数、scope/profile 和 model policy 标识；创建点 root 由 base root/外部父实例、physical callsite、对象/handle lineage、guard 和 cardinality 标识。同一 callable 在两个 site 可共享 context，但必须有两个 root origin；循环、递归或无法枚举的创建使用 repeated/merged cardinality 并产生 frontier。

`source-candidate`、`ir-candidate`、`conditional-frontier`、ambiguous、unsupported 或 failed site 不生成正式 ThreadInstance。它们仍进入 root coverage 和候选相关依赖切片，防止“未采用”被解释为“没有线程”。

### 7. 完整性、预算和缓存按候选依赖切片传播

request 限制 TU、source/IR facts、类型/alias 深度、site/binding/callback 候选、profile、wrapper 深度、root/context、递归/SCC、frontier、诊断、输出字节、worker 和 wall-clock。命中预算时发布已知事实、hit/limit 和非空 frontier，不返回空集合冒充完成。

缓存键包含 schema/producer/policy、Clang/LLVM、scope/profile、源与 BC digest、所有依赖 digest、标准库/API model、descriptor、预算类别和显式 root 配置。损坏、陈旧、failed、timeout 或 wall-clock partial 不作为成功缓存命中；cold/warm semantic digest 必须一致。

与某个 site/root 无关的 TU 失败不强制降级该 site，但顶层报告保存 scope failure；相关 AST、IR、binding、profile 或 broker 缺失则使对应 slice 和报告 partial。零候选必须同时报告扫描分母和失败分母，不能解释为程序没有线程或安全。

### 8. 归档样例转为本项目内、可编译、人工真值 fixture

从 `memory-model-ir-checker/samples` 只复制并最小化用例思想，在本项目记录原相对路径、内容摘要和改写原因。测试不得读取兄弟目录。旧样例中无正确头文件、错误语言或仅能被宽松 parser 接受的片段必须修复为 GCC/Clang 可编译输入后才进入 truth；Windows 样例只登记排除原因。

四语言分别报告 planned、completed、failed、expected/actual sites、exact match、TP、FP、FN、abstention 和 frontier。C11/C17 覆盖 pthread、`thrd_create`、宏、跨 TU、no-debug 和 C linkage；C++17/C++20 覆盖现有 `std::thread` 形式，C++20 额外覆盖 `std::jthread`，两者按可用标准库 profile 覆盖 `std::async` policy。`foo::thread`、`boost::thread`、默认/move/factory-return、`Form.submit`、callback 冲突、重复 AST 节点、开放 scope、profile 失配与预算是强制负例/unknown。

### 9. CLI、报告和文档不宣称安全

新增 `discover-thread-entries --request --artifact-store --output --source-worker --ir-worker`，要求输出目录不存在且只读取显式引用，不扫描“最新”产物、不执行构建/链接/目标程序。退出码 `0` 表示入口发现和 overlay 在请求范围内 complete，`2` 表示 partial/unknown/unsupported/frontier，`1` 表示请求无效或全部 failed；不返回风险码 `3`。

报告固定 `safety=not_evaluated`、`findings=null`，中英文字段至少覆盖 detail、limitation 和 suggestion，机器 code/identity 不依赖翻译。README、架构文档、线程入口设计/验证文档和路线图分别说明使用方式、证据边界、truth 结果与后续生命周期/并发访问图关系。

## Risks / Trade-offs

- [Clang canonical name 在不同标准库 inline namespace 下变化] → 采用 profile 登记的 canonical declaration、USR/来源/ABI 指纹，qualified name 只用于展示。
- [优化后 C++ broker 被内联或无法与 source site 唯一对齐] → 保留 source candidate 和明确 IR frontier；不以底层 pthread 符号或调试行号猜测。
- [`std::async` 默认 policy 造成假并发或漏并发] → 分离 evidence status 与 execution semantics，默认 policy 只进入 conditional frontier。
- [`std::jthread` callable 的 stop-token 重载选择复杂] → 仅采用 profile 验证且 invocable 形式唯一的候选，歧义时不任选 callback。
- [新 overlay 与 R1 base 出现重复 root] → 以 physical callsite、model 和 callback identity 进行跨 artifact 去重，并保留 adopted-from 引用；冲突时 ambiguous 而非覆盖。
- [保存 alias/type/constructor 证据增加 artifact 体积] → 使用独立预算、canonical identity 去重和系统头边界，只保存入口相关切片。
- [归档样例经过修复后不再与旧 parser 结果一一对应] → 保存 provenance manifest 和改写说明，新的人工 truth 只对当前可编译 fixture 生效。
- [90% 覆盖率掩盖语义错误] → 覆盖率门禁与四语言人工 truth、负例、unknown/frontier 断言分开报告。

## Migration Plan

1. 先增加 schema/contract、profile/model registry 和不改变现有调用路径的读写校验。
2. 扩展 source/IR local facts，并用独立命令生成新 artifact；旧 P3/A3/R1 命令继续原样运行。
3. 建立 site index 和 root overlay，验证与 R1 base 的确定组合及重复 root 消除。
4. 导入本项目内 fixture、运行四语言 truth、完整质量门禁和 cold/warm 缓存验证。
5. 更新文档后再同步主规格。回滚只需停用新 CLI/overlay；既有 artifact 和消费者不需要迁移。

## Open Questions

- 实施阶段需要在锁定开发容器中测量可用 libstdc++/libc++ 版本的 `std::jthread`/`std::async` broker 指纹；只有实际验证通过的组合进入 profile registry，其余组合按 `unsupported` 处理，不阻塞协议实现。
- framework descriptor 在首版只验证拒绝名称启发式及 schema 边界；首个真实线程池 profile 留待独立 change 决定。
