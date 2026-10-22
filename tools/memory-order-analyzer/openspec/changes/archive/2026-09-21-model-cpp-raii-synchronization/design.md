## Context

P3 已能为直接 POSIX `pthread_mutex_lock`/`pthread_mutex_unlock` 建立受限候选，A2 会把未知 RAII、mutex kind、wrapper 或预算缺口传播为候选相关 `SynchronizationGap`，A3 又补充了 `std::thread` 的 callback、对象和 `ThreadInstance` 生命周期。但是 C++ RAII mutex 的真正 lock/unlock 往往分布在模板构造/析构、异常清理、libstdc++/libc++ wrapper 和底层 pthread ABI 中；AST 只说明源构造，IR 只看到展开后的调用，两者任何一方都不足以证明持锁区间或跨线程同步。

本 change 必须同时服务两条线程来源：C11/C17 的直接 pthread 路径继续作为独立基线；C++17/C++20 在经验证的标准库 profile 下增加 RAII overlay。它不能升级 `ModuleFacts v2`、`EffectSummary v1`、`ThreadContextGraph v1`、P4、A1、A2 或 A3 的既有协议，也不能把“识别到锁类型”提升为通用 happens-before 或程序安全证明。

## Goals / Non-Goals

**Goals:**

- 定义独立、版本化、可缓存的 A4 请求、局部事实、标准库同步 profile、RAII 同步图和双语报告。
- 以 AST 实体/lifetime、SourceIRBinding、实际 LLVM wrapper、对象 lineage、路径和线程实例的联合证据，规范化 `std::mutex` 与底层普通非 robust pthread mutex 身份。
- 精确支持 `std::lock_guard`，受限支持证据完整的 `std::unique_lock` 与 `std::scoped_lock`，覆盖构造、析构、move、异常清理、单 TU、跨 TU wrapper 和对象字段。
- 在条件、对象和实例均闭合时，为 P3/A3/P4 提供受限 mutex acquire/release、持锁区间和互斥证明；证据缺失时保留 partial/unknown/frontier。
- 保持 C11/C17 直接 pthread mutex 语义、profile、fixture 和验收分母独立，防止 C 路径依赖 C++ AST 或标准库模型。
- 为全部自有实现补齐有效单元测试，并强制项目整体、实现语言和每个受影响模块行/分支覆盖率至少 90%。

**Non-Goals:**

- 不支持 Windows、MSVC、clang-cl、`std::recursive_mutex`、timed/try/robust mutex、condition variable、semaphore、rwlock、自定义同步原语、线程池或 executor。
- 不实现通用 points-to、通用 happens-before、通用 data-race、fence、RMW/CAS release sequence 或全程序安全证明。
- 不把 AST-only、类型名、函数名、mangled symbol、源码词法顺序、P2 `EffectSummary.order`、P3 reads-from candidate 或 A3 生命周期关系单独当作同步证明。
- 不执行目标程序、用户 CMake、网络服务、SSH、ARM DevKit、GenMC 或 herdtools7；生产 Dockerfile 整合仍属独立 change。

## Decisions

### 1. A4 使用独立 sidecar，不修改 P1–A3/P4 根协议

新增 `CppRaiiSynchronizationRequest v1`、`CppRaiiLocalFacts v1`、`CppRaiiSynchronizationGraph v1` 和 `CppRaiiSynchronizationReport v1`。请求按内容摘要显式引用 source facts、SourceIRBinding、ModuleFacts、P3 graph、A3 lifecycle graph、scope/profile 和可选 P4 请求；旧产物既不内嵌 A4 字段，也不因缺少 A4 被解释为“没有同步”。

选择独立 sidecar 而不是升级 `ThreadContextGraph v1`，因为 RAII lifetime、标准库 profile 和 owner 状态有独立失效条件；这也能保持 P1–A3 缓存命名空间及调用方兼容。代价是需要显式 adapter 和引用校验，但比隐式改写 P3 语义更可审计。

### 2. 原始节点、分析节点和证明实例保持三个命名空间

`CppRaiiLocalFacts` 只登记实际 AST/IR 观察：mutex/owner 构造、析构、move、lock/unlock wrapper、cleanup edge、返回值和异常出口。规范化 mutex、RAII owner、acquire/release attempt、held-region 和互斥证明是 A4 分析节点，使用独立稳定 identity，并引用全部来源、绑定和 profile 证据。

禁止把 AST `VarDecl`、IR call、标准库摘要节点或某个 owner 实例互相冒充。这样可避免一个模板展开或缓存摘要被错误复用为多个动态 mutex/owner，也能在无 debug 时保留 IR 级位置和证据链。

### 3. 标准库同步 profile 独立于 A3 线程 profile，但复用共同编译身份

建立 `CppRaiiSynchronizationProfile` 注册表，键至少包含 compiler family/version、language standard、standard-library kind/version、C++ ABI、target triple、data layout、异常/RTTI 选项、相关头文件或 wrapper 指纹、模型版本。profile 可引用 A3 共同 fingerprint，但 mutex/RAII wrapper eligibility、系统边界和摘要摘要值独立版本化。

只有在锁定开发镜像中实际编译 profile probe，并观察到声明的 AST/IR wrapper 形状后才能标记 `verified`。合成 JSON、相邻版本、符号近似或只验证 libstdc++ 后推断 libc++ 均不能通过 required gate。失配时产生 `library-profile-mismatch` frontier，不回退到名称猜测。

### 4. mutex identity 与 owner identity 分离

`MutexInstance` 表示规范化同步对象；`RaiiOwnerInstance` 表示 guard/lock wrapper 的所有权状态。身份由 scope、canonical source entity/object path、TU/profile、调用/分配上下文、字段偏移和有界 SourceIRBinding 共同构成。owner 的 move 只转移 ownership token，不改变底层 mutex identity；moved-from owner 不再产生 release。

全局对象、静态对象、直接参数、返回绑定和可证明的常量字段路径进入首版。结构体/对象字段仅在对象基址和字段偏移唯一时采用；有限多候选保留 may 集合但不能建立 must-held 或同 mutex 证明。需要通用 `this`/堆 points-to 的情况交给 A5，当前输出 `mutex-provenance-ambiguous`。

### 5. RAII 使用条件化状态机和 CFG/cleanup 证明

owner 状态至少为 `uninitialized`、`owns`、`deferred`、`moved-from`、`released`、`unknown`。`lock_guard` 只有构造成功、唯一 mutex 和正常/异常 cleanup 可闭合时生成 acquire/release；构造抛出前不得产生 owns。析构只有从 `owns` 状态且实际 IR unlock/summary 绑定成立时产生 release。

`unique_lock` 首版仅支持：默认立即加锁构造、`defer_lock` 后有唯一成功 `lock()`、已知 move 转移，以及可证明的 `owns_lock()` 控制；`adopt_lock`、`try_to_lock`、`release()`、`swap()`、重复 lock/unlock 或复杂循环若不能闭合即 unknown。`scoped_lock` 仅支持固定小规模、全部 mutex 身份唯一且 profile 能证明成功获取/逆序释放的构造；任一元素未知使整个组合不可用于 must 证明。

选择显式状态机而不是“构造到析构即持锁”的词法规则，因为提前 unlock、构造失败、move 和异常清理会改变动态所有权。AST scope 只提供 lifetime 候选，CFG、IR wrapper 与状态转换共同决定 held region。

### 6. 同步证明限定为普通非 robust mutex 的闭合链

A4 输出 `may-acquire`、`acquire-success`、`release`、`held-region`、`mutual-exclusion` 和 `mutex-synchronizes-with-candidate` 等带 guard 关系。只有以下条件同时成立时，adapter 才可采用确定互斥/同步证据：

1. 两侧唯一绑定同一 `MutexInstance`；
2. profile 证明普通、非 recursive、非 robust、阻塞式 mutex 语义；
3. acquire 成功且 release 配对，路径、异常和 owner 状态闭合；
4. 访问唯一落在相应 held region 中，并绑定到可能并行的明确 `ThreadInstance`；
5. 没有相关 scope、wrapper、对象、预算或未知同步缺口。

模型可证明两个受支持临界区互斥，并将 unlock→后续成功 lock 作为受限同步候选，但不构造全程序 HB 闭包。不同 mutex、未平衡操作、未知 kind、失败/异常路径或 may-alias 不能消解候选。

### 7. 跨 TU wrapper 只通过精确实体、参数绑定和摘要组合

用户 wrapper 必须在显式 scope 内有唯一合法 definition、精确 linkage/ABI、参数到 mutex 的有界绑定和可组合的 A4 摘要。系统 wrapper 只可来自已验证 profile 的系统边界；同名函数、目录邻近定义、weak/COMDAT 歧义或 scope 外 definition 均进入 frontier。

摘要参数化描述 mutex 参数、owner 转换、acquire/release、异常出口和 unknown effect；调用点实例化后重新绑定对象与 guard。递归使用 SCC/迭代预算，未收敛摘要为 partial，不以空效果代表无锁。C linkage wrapper 继续走 C/P3 事实，不能因为被 C++ TU 调用而强制套用 RAII profile。

### 8. P3、A3、A2 与 P4 通过显式 adapter 组合

A4 graph 引用 P3 `ThreadContext`/`ThreadInstance` 与 A3 生命周期，但不改变其 identity 或 join/detach 关系。A2 对 `unmodeled-raii-lifetime` 等 gap 的处理改为：只有 A4 对同一候选依赖切片提供完整替代证明时，才关闭对应 gap；不相关 gap 不阻塞候选，相关未解决 gap 必须继续令结果 partial/unknown。

P4 只消费 A4 adapter 发布的、引用完整证据链的 mutex proof。结果类别、严重度、退出码和 `safety=not_established` 不变；受 mutex 保护的候选可在限定模型内从 risk/unknown 转为已有类别中的消解结果，但报告必须说明模型、mutex、线程、持锁区间和限制。AST-only 事实、零候选或零 finding 不能产生消解。

### 9. 完整性、预算与缓存按候选依赖切片传播

预算至少覆盖 TU、source/IR node、profile probe、mutex/owner、wrapper、call context、state transition、held region、relation、递归轮次、候选、输出字节和 worker/request 时间。超限保留已知事实、hit/limit、frontier 与中英诊断，并将受影响切片标记 partial；无关候选可继续分析，但顶层不得伪装 complete。

缓存键包含协议/schema、工具链、scope、所有依赖摘要、A4 profile/模型、预算类别和实现身份。缓存命中必须重新验证引用、profile eligibility 和候选依赖；损坏、陈旧、失败或 timeout 结果不得作为长期语义命中。cold/warm 必须产生相同 semantic digest。

### 10. CLI 与报告保持结果和过程分离

新增独立 A4 命令，输入显式 request 和 artifact store，输出 graph/report。退出码沿用项目约定：`0` 表示本次 A4 请求完整且没有需要更高优先级表达的正式风险，`2` 表示 partial/unknown/frontier，`1` 表示请求无效或全部不可用；A4 自身不新增风险类别或使用 `3` 宣称风险。P4 组合入口继续按既有 0/3/2/1 语义决定。

报告为每个 mutex/owner/held region/proof 提供稳定 code、证据引用、profile、guard、线程、完整性，以及中文 `detail/suggestion` 和英文 `detail_en/suggestion_en`。机器 identity 与翻译分离；“受限 mutex 模型内消解”不得表述为“线程安全”或“全程序安全”。

### 11. 验收以离线人工真值、四语言回归和双覆盖率为门禁

固定语料分别统计 C11、C17、C++17、C++20 planned/completed/eligible、TP/FP/FN、strict 指标和 abstention。C 覆盖直接 pthread mutex、跨 TU wrapper、结构体字段、未知 kind 和无锁反例；C++ 覆盖两个标准库 profile、RAII 类型、move、异常、字段、开放 scope、no-debug、profile mismatch 与预算。

锁定 `safe/03_pthread_mutex.cpp` 的本地副本和 hash，人工 truth 只要求在 A4 支持边界及证据完整时消解，不把 sibling archive 或历史工具输出当 oracle。所有新增/修改/复用自有执行模块均有正常、边界、异常、unknown 单元断言；项目整体、C++、Python 和逐受影响模块 line/branch 均至少 90%，集成覆盖不得补入单元覆盖率。

## Risks / Trade-offs

- [标准库 wrapper 随版本、优化和异常配置变化] → profile 绑定实际 fingerprint，required libstdc++/libc++ 分别实编验证；失配立即 partial/unknown。
- [析构或异常 cleanup 被错误配对导致虚假同步] → AST lifetime 只生成候选，必须结合 CFG、invoke/landingpad/cleanup 与实际 unlock 证据；任一出口未闭合即不产生 must proof。
- [owner move 或字段 alias 合并不同 mutex] → mutex/owner identity 分离，move 使用显式 ownership token；多候选只保留 may，不提升 must。
- [把互斥关系误作通用 HB 或安全结论] → A4 只发布受限 proof edge，不求全局传递闭包；P4 报告保留 `safety=not_established` 和限制。
- [模板/系统头展开引发规模爆炸] → profile 系统边界和参数化摘要跳过无关系统内部；所有维度设预算并保留 frontier。
- [A4 影响既有 C 或 A3 结果] → sidecar、cache namespace 和 adapter 均独立；缺少 A4 请求时旧输出字节级/语义回归，C 四语言分母独立门禁。
- [样例“消解”被误解为真实工程准确率] → 仅报告锁定 truth 分母和 capability；不外推至未建模 mutex、未知对象或全程序。

## Migration Plan

1. 先增加 schema/protocol、profile probe 和纯验证器，旧 CLI/缓存不读取 A4 产物。
2. 增加 source/IR 局部事实及 AST/IR binding，再实现 mutex/owner 状态机和跨 TU wrapper 摘要。
3. 接入 P3/A3/A2 adapter；在 A4 graph 稳定后才接入 P4 消费，默认缺少 A4 时保持当前 unknown 行为。
4. 扩充四语言 truth、归档样例回归、文档、缓存/预算和 CLI，使用全新报告目录运行完整质量门禁。
5. 若回滚，只移除 A4 CLI/adapter 和独立产物；P1–A3/P4 协议、缓存和直接 pthread 路径无需迁移或重写。

## Open Questions

- `std::scoped_lock` 首版的最大 mutex 数量和状态空间预算在实现时通过 profile probe 与固定 fixture 量化；规格要求固定小规模和超限 unknown，不预设未经测量的默认值。
- libc++/libstdc++ required profile 的精确版本由开发容器实测 fingerprint 决定；在二者均完成实际编译/提取/真值断言前，A4 required gate 不得完成。
- `unique_lock::adopt_lock`、`try_to_lock` 与手工 `unlock()/lock()` 仅在证据链能够满足本设计状态机时才可后续扩展；本 change 默认将未闭合形状保守降级。
