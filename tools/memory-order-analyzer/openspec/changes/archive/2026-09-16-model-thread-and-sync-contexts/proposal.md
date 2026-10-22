## Why

P2 已能在显式 scope 内生成带对象、条件、调用实例与未知影响的跨 TU 效果摘要，但尚不能回答哪些效果属于不同线程、哪些线程可能并行以及哪些同步操作能够形成有条件的执行顺序。为落实 `doc/IMPLEMENTATION_ROADMAP.md` 的 P3，需要在不改变 P1 `ModuleFacts v2` 和 P2 `EffectSummary v1` 原始语义的前提下，建立独立且可审计的线程、顺序和基础同步建模层，为后续 P4 风险判定提供可靠输入。

## What Changes

- 这是**运行时实现 change**；本次 propose 只定义实施契约，不表示线程或同步分析能力已经可用。
- 新增独立、版本化的线程分析请求、LLVM 局部线程补充事实、执行顺序证明、线程上下文图和线程分析报告；新产物引用而不改写 P1/P2 原始产物。
- 使用 LLVM CFG、DominatorTree/PostDominatorTree、LoopInfo、AA/MemorySSA 和 callback metadata 等现有能力，自研调用锚点、回调入口校验、受限线程句柄 provenance、条件化顺序和完整性传播；不得将 P2 `EffectSummary.order` 直接解释为 `sequenced-before` 或 `happens-before`。
- 区分可复用的 `ThreadContext` 与由父线程、创建点和抽象次数限定的 `ThreadInstance`；支持同一入口多次创建、main/worker 关系、递归或循环创建的有限合并和预算降级。
- 首版只建模 GCC/Clang 用户态 C/C++ 中可验证的直接 `pthread_create`、`pthread_join`、`pthread_mutex_lock`、`pthread_mutex_unlock`，并把创建、连接和锁操作的成功条件保留在生命周期及同步边上。
- 构造 may-happen-in-parallel（MHP）关系、同一普通非 robust mutex 对象上的同步候选，以及带对象、值、order、scope 和 guard 的原子 reads-from 候选；仅有 release/acquire 共存不得生成确定 HB。
- 新增显式入口的线程分析 CLI、派生缓存和分层报告；输入缺失、回调/句柄/同步对象不确定、预算合并及未支持语义必须成为可定位的 partial/unknown，不得以空关系或零 findings 冒充完整或安全。
- 人类可读的诊断和建议同时提供中文与英文，例如 `detail`/`detail_en`、`suggestion`/`suggestion_en`，稳定机器码与枚举保持语言无关。
- 增加全部新增、修改及复用自有代码的单元测试，覆盖正常、边界、失败和 unknown 路径；项目整体、每语言及受影响模块的行覆盖率和分支覆盖率均至少 90%，集成测试不能替代单元测试。
- 暂不实现 `std::thread`/RAII、try/timed/robust/recursive mutex、condition variable、semaphore、rwlock、线程池、自定义线程/同步封装、通用指针分析、完整 reads-from 求解、风险判定或自动修复。

## Capabilities

### New Capabilities

- `llvm-thread-analysis-facts`: 从已校验 BC 生成独立局部线程补充事实，覆盖回调入口、调用锚点、顺序证明、线程句柄与同步对象来源，并保留 LLVM 证据和未知边界。
- `thread-context-modeling`: 建立可复用线程上下文、抽象线程实例、父子关系、创建/开始/退出/连接生命周期、递归预算及受限句柄关联。
- `thread-order-and-synchronization`: 构造独立于 P2 `order` 的条件化执行顺序、MHP、普通 mutex 同步候选和原子 reads-from 候选，不提前执行 HB 风险判定。
- `thread-analysis-reporting`: 定义版本化请求、上下文图、报告、缓存、CLI、退出状态、双语诊断及完整性统计契约。

### Modified Capabilities

- `analysis-integrity-reporting`: 将 P3 独立产物、跨层依赖、计划分母、未知前沿和缓存隔离纳入完整性要求，同时保持 P1/P2 既有状态语义不变。
- `analyzer-unit-test-quality`: 增加线程实例、生命周期、MHP、顺序证明、同步候选和保守降级的单元/集成验收，继续执行整体、语言及受影响模块行/分支至少 90% 的门槛。

## Impact

- 预计影响本项目 `src/` 的 LLVM 局部线程事实 worker，`python/memory_order_analyzer/` 的协议、模型注册、线程调度、句柄关联、MHP/同步、缓存、CLI 和报告逻辑，以及 `schemas/`、构建配置、`tests/` 和 `doc/`。
- 复用现有显式 scope、ArtifactKey、SourceRef/AnalysisRef、对象/范围、guard、invocation、效果摘要和依赖 digest；不修改 `ModuleFacts v2`、`RunReport v2`、`LocalAnalysisFacts v1` 或 `EffectSummary v1` 的既有格式与含义。
- 使用项目现有 LLVM 21.1.8 开发依赖，不强制引入 SVF、PhASAR、模型检查器、DevKit、SSH 或网络服务；离线质量验收必须可重复执行。
- `compile_commands.json` 继续负责 TU 编译输入发现，不被解释为完整目标/链接图或线程调用图；P3 从显式 scope、P1/P2 产物及新增局部证据建立关系。
- 本阶段只输出线程、顺序和同步候选及其完整性，始终保持 `safety=not_evaluated`、`findings=null`；发布/消费风险及其他缺陷判定留给 P4。
