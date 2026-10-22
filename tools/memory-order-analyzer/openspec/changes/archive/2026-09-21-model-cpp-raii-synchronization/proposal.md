## Why

当前分析器已经能够解析直接 pthread mutex 候选和 `std::thread` 生命周期，但 C++17/C++20 中常见的 `std::mutex`、`std::lock_guard`、`std::unique_lock` 与 `std::scoped_lock` 仍只会形成 `SynchronizationGap`。这使证据完整、实际受同一 RAII mutex 保护的访问只能降级为 unknown；A2/A3 已经提供按候选传播缺口、标准库 profile、线程实例和生命周期基础，现在适合增加独立且保守的 RAII 同步证明层。

这是运行时分析能力、协议、测试与文档的实现变更，不是纯文档 change。

## What Changes

- 新增独立版本化的 `CppRaiiSynchronizationRequest v1`、LLVM/AST 局部补充事实、标准库同步 profile、`CppRaiiSynchronizationGraph v1` 和双语报告；保持 `ModuleFacts v2`、`EffectSummary v1`、`ThreadContextGraph v1`、`PublicationRiskReport`、A1、A2 与 A3 既有协议及报告语义不变。
- 在身份完全匹配且经过实际编译验证的 libstdc++/libc++ profile 下，支持 C++17/C++20 `std::mutex`、`std::lock_guard`，并受限支持能够证明 owns-lock 状态和对象 lineage 的 `std::unique_lock`、`std::scoped_lock`。C11/C17 直接 `pthread_mutex_lock`/`pthread_mutex_unlock` 路径继续独立运行和回归，不依赖 C++ AST 或标准库模型。
- 组合 AST canonical entity、RAII 构造/析构作用域、异常清理边、对象 move、跨 TU definition、SourceIRBinding 与实际 LLVM lock/unlock wrapper，建立规范化 mutex 对象、guard/owner 实例、条件化 acquire/release 和持锁区间；不得仅凭类型名、函数名、mangled symbol、源码词法范围或 P2 `EffectSummary.order` 生成 synchronizes-with、happens-before 或互斥证明。
- 将 RAII 图与 A3 `ThreadInstance`、MHP、join/detach 生命周期以及 P3 直接 pthread mutex 事实按显式 adapter 组合。只有同一规范化普通非 robust mutex、成功 lock、成对 unlock/析构、路径和实例证据完整时，才允许在受限 mutex 模型内生成互斥/同步证据；析构、异常、move、defer/adopt/try-to-lock 状态不明确时必须进入 partial/unknown。
- 增加标准库种类/版本、ABI、target、编译 profile、wrapper 指纹与模型版本绑定的独立同步摘要注册表及系统边界。profile 失配、wrapper 漂移、对象 provenance 歧义、跨 TU 不完整、递归或预算耗尽必须产生候选相关 frontier，不能解释为不存在同步。
- 允许 P4 在不改变 finding、discharged、unknown、退出码和安全边界的前提下消费经验证的 A4 互斥证据；AST-only 或不完整 RAII 事实不得单独消解风险。`memory-model-ir-checker/samples/safe/03_pthread_mutex.cpp` 的本地锁定副本只有在完整证据链成立时才可在受限 mutex 模型内消解，不能宣称全程序安全。
- 增加版本化缓存、资源预算、确定性、CLI、退出码、中英文字段和候选相关完整性传播；明确排除 Windows、MSVC、clang-cl、try/timed/recursive/robust mutex、condition variable、semaphore、rwlock、自定义同步、通用指针分析、通用 happens-before、fence 和 RMW/CAS。
- 增加 C++17/C++20 单 TU、物理跨 TU、全局/结构体/对象字段 mutex、异常退出、对象 move、`lock_guard`、受限 `unique_lock`/`scoped_lock`、无 debug、开放 scope、ABI/profile 失配和预算用例；分别保持 C11/C17 直接 pthread mutex 的正反例、跨 TU wrapper 和未知 mutex kind 回归。
- 所有新增、修改或复用的自有可执行代码同步增加正常、边界、异常和 unknown 单元测试；项目整体、C++、Python 以及每个受影响模块的行覆盖率和分支覆盖率均至少 90%，并分别报告 C11、C17、C++17、C++20 的语义分母。

## Capabilities

### New Capabilities

- `cpp-raii-synchronization-modeling`: 定义独立 RAII 同步请求、局部事实、mutex/owner 身份、持锁区间、同步补充图、报告、缓存、预算与证明边界。
- `cpp-raii-synchronization-profiles`: 定义 libstdc++/libc++ mutex/RAII wrapper 的版本、ABI、target、指纹、摘要注册、采用、失效和系统边界。

### Modified Capabilities

- `gcc-clang-compilation-context`: 将 A4 标准库同步模型身份纳入 C++ profile 与缓存，同时保持 C11/C17 编译 profile 独立。
- `clang-source-semantic-facts`: 增加 mutex、RAII owner、构造/析构、move、异常清理和受限 owns-lock 源事实，但禁止 AST 单独生成动态同步证明。
- `cross-tu-program-entity-index`: 增加用户 mutex wrapper、RAII helper 和对象字段在显式 scope 内的精确 declaration/definition 关联及系统外部边界。
- `source-ir-evidence-binding`: 增加 mutex/owner 操作、异常清理与底层 lock/unlock wrapper 的基数化 AST/IR 绑定，拒绝名称猜测和不完整绑定。
- `llvm-thread-analysis-facts`: 增加普通 mutex、C++ ABI wrapper、owner token、构造/析构/move 与异常出口的独立局部候选事实，不改变既有 pthread 事实语义。
- `cpp-thread-lifecycle-modeling`: 规定 A4 只能引用 A3 `ThreadInstance` 与生命周期关系，不能改变 A3 join/detach、对象状态或报告含义。
- `thread-context-modeling`: 允许将经验证的 A4 mutex/owner 实例绑定到既有线程实例和 MHP 候选，同时保持线程图版本与完整性语义不变。
- `thread-order-and-synchronization`: 增加受限 RAII acquire/release、同 mutex 互斥与条件化同步组合规则，并明确禁止从词法 scope 或候选关系制造 HB。
- `thread-analysis-reporting`: 增加 A4 overlay、profile、证据链、frontier 和中英文字段的独立报告及对 P3/A3 产物的引用。
- `degraded-source-analysis`: 将 A4 profile、mutex identity、RAII lifetime、owns-lock、异常路径和预算缺口纳入候选相关 `SynchronizationGap` 的保留或消解规则。
- `single-publication-protocol-modeling`: 允许仅以证据完整的 A4 同 mutex 互斥证明补充候选判定，禁止 AST-only 或不完整 RAII 事实直接产生 risk/discharged。
- `publication-risk-reporting`: 在不改变 P4 结果类别和退出码语义的前提下引用 A4 证明或缺口，并区分受限模式内消解与全程序安全。
- `analysis-validation-corpus`: 增加四语言独立 mutex/RAII 真值与回归语料，包括锁定的 `safe/03_pthread_mutex.cpp` 和等价 C pthread 正反例。
- `analysis-validation-reporting`: 分别报告 C11、C17、C++17、C++20 的完成度、TP/FP/FN、abstention、profile、缓存、预算与语义结果，禁止用 C++ 新能力覆盖 C 分母。
- `analyzer-unit-test-quality`: 将 A4 所有新增或修改自有模块纳入整体、实现语言和逐受影响模块行/分支至少 90% 的单元覆盖率与离线验收门禁。

## Impact

- 影响 C++ LibTooling source worker、LLVM thread-local worker、标准库 profile/摘要、跨 TU 实体和绑定、RAII/mutex 图组合、P3/A3/P4 adapter、A2 降级编排、schema/协议、缓存、CLI、报告、质量入口与离线夹具。
- 可能新增对锁定开发镜像中 libstdc++/libc++ 头文件、ABI wrapper 和版本元数据的读取；核心运行、测试和正确性判定不得依赖网络、SSH、ARM DevKit、外部后端或执行被分析程序。
- 现有 C11/C17 pthread 结果以及 P1–P4、A1–A3 产物和缓存不得因未请求 A4 而改变；A4 产物缺失不得解释为不存在 mutex 或同步。
- Windows、MSVC、clang-cl、sibling archive 和生产 Dockerfile 整合不属于本 change 的实现或运行依赖。
