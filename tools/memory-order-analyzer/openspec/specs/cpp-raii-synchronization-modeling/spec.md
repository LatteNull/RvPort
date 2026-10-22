# cpp-raii-synchronization-modeling

## Purpose

定义独立、版本化且证据受限的 C++ RAII mutex 同步分析协议、所有权状态机、证明边界、缓存和报告语义。

## Requirements

### Requirement: Publish an independent versioned RAII synchronization protocol

系统 SHALL 定义 `CppRaiiSynchronizationRequest v1`、`CppRaiiLocalFacts v1`、`CppRaiiSynchronizationGraph v1` 和 `CppRaiiSynchronizationReport v1`，通过内容摘要显式引用 scope、编译 profile、A1/A2、P1/P3、A3 及可选 P4 产物；A4 产物 MUST 使用独立 schema、缓存身份和节点命名空间，不得修改或重解释既有协议。

#### Scenario: A4 is not requested
- **WHEN** 调用方只运行 P1–A3 或 P4 且没有 A4 request/artifact
- **THEN** 既有输出和缓存语义保持不变，缺少 A4 不得解释为不存在 mutex 或同步

#### Scenario: A dependency digest is stale
- **WHEN** request 引用的 source、IR、thread、lifecycle 或 profile 摘要与实际 artifact 不一致
- **THEN** 验证器拒绝组合并输出稳定的中英文引用错误，不搜索目录中的替代产物

### Requirement: Separate mutex, owner and proof identities

系统 SHALL 分离 `MutexInstance`、`RaiiOwnerInstance`、acquire/release attempt、held-region 和 synchronization proof identity。mutex identity SHALL 由显式 scope、canonical object/entity、TU/profile、对象路径/常量字段偏移和有界调用上下文组成；owner move SHALL 只转移 ownership token，不改变底层 mutex identity。

#### Scenario: A guard is moved
- **WHEN** 唯一 owner 从对象 A move 到对象 B 且 AST/IR 转移和源 mutex 绑定均完整
- **THEN** B 继承 ownership token，A 标记 moved-from，最终 release 仍引用原 `MutexInstance` 且不会重复 unlock

#### Scenario: A mutex field has ambiguous bases
- **WHEN** 同一字段路径可能来自多个对象基址或动态 GEP 无法有界解析
- **THEN** 保留有限 may 候选或 `mutex-provenance-ambiguous` frontier，不生成 must-same-mutex 或 must-held 证明

### Requirement: Model RAII ownership with path-sensitive state transitions

系统 SHALL 使用至少 `uninitialized`、`owns`、`deferred`、`moved-from`、`released`、`unknown` 的条件化状态机组合构造、析构、显式 lock/unlock、move 和异常 cleanup。AST lifetime 仅可产生候选；acquire、release 和 held-region MUST 同时具有实际 IR wrapper/摘要、CFG 路径和对象绑定证据。

#### Scenario: Lock guard exits normally and exceptionally
- **WHEN** `lock_guard` 构造成功，正常和异常出口均可绑定到同一 mutex 的实际 unlock cleanup
- **THEN** 图分别记录带 guard 的 held-region 与 release，并允许闭合路径参与受限同步证明

#### Scenario: Construction may throw before ownership
- **WHEN** 构造调用存在未解析失败/异常路径且不能证明获得锁
- **THEN** 该路径不得进入 `owns` 或生成 release/HB，相关候选变为 partial/unknown

### Requirement: Support a bounded C++17 and C++20 RAII subset

在 verified libstdc++/libc++ profile 下，系统 SHALL 支持 `std::mutex`、`std::lock_guard`，并仅在 owns-lock 状态和对象 lineage 完整时支持 `std::unique_lock` 与固定小规模 `std::scoped_lock`。`adopt_lock`、`try_to_lock`、`release`、`swap`、重复 lock/unlock、try/timed/recursive/robust mutex 或超预算多锁组合 MUST 保守进入 unknown，除非完整状态机能够证明其语义。

#### Scenario: Deferred unique lock later locks successfully
- **WHEN** `unique_lock` 以 `defer_lock` 构造，随后唯一成功 `lock()` 且析构前没有未知 ownership 操作
- **THEN** held-region 从成功 lock 开始，并在唯一 release 结束

#### Scenario: Scoped lock contains an unresolved mutex
- **WHEN** `scoped_lock` 的任一 mutex identity、获取成功或释放次序证据缺失
- **THEN** 整个多锁组合不得用于 must-held/互斥证明并产生候选相关 frontier

### Requirement: Bound mutex synchronization proofs

系统 MUST 仅在同一规范化普通非 robust mutex、成功 acquire、成对 release、访问落入闭合 held-region、线程实例可能并行且所有相关证据完整时发布互斥或同步 proof。系统 MUST NOT 从类型/函数名、词法 scope、P2 order、候选 reads-from、A3 join/detach 或 AST-only 事实单独生成 synchronizes-with、happens-before 或安全结论。

#### Scenario: Two accesses use the same proven mutex
- **WHEN** 两个可能并行 `ThreadInstance` 的冲突访问分别位于同一 mutex 的完整临界区中
- **THEN** 输出可审计的受限互斥证明，引用双方 acquire/release、对象、路径和 profile，但保持全程序安全未建立

#### Scenario: Two guards use different mutexes
- **WHEN** 两个 held-region 的 mutex identity 不同或只满足 may-alias
- **THEN** 不生成互斥或同步 proof，候选继续按既有风险/unknown 规则处理

### Requirement: Preserve completeness under budgets and caching

请求 SHALL 对 TU、节点、profile、mutex/owner、wrapper、上下文、状态转换、held-region、关系、递归轮次、输出和时间设置资源预算；耗尽时 SHALL 保留已知事实、hit/limit 与非空 frontier，并按候选依赖切片传播 partial。缓存键 MUST 包含协议/schema、全部依赖、profile/model、工具链、预算类别和实现 identity，cold/warm semantic digest MUST 一致。

#### Scenario: A wrapper recursion budget is exhausted
- **WHEN** 递归 mutex wrapper 摘要未在预算内收敛
- **THEN** 已有 may facts 保留、相关证明不可完成且报告为 partial，不以空效果表示无锁

#### Scenario: Cached profile eligibility changed
- **WHEN** 缓存内容结构有效但标准库 fingerprint 或依赖摘要已变化
- **THEN** 拒绝命中并重新分析或返回明确失败，不复用旧同步 proof

### Requirement: Expose deterministic CLI and bilingual reporting

A4 CLI SHALL 接受显式 request/artifact store/output，输出确定排序的 graph/report；`0` 表示 A4 请求完整、`2` 表示 partial/unknown/frontier、`1` 表示无效或全部不可用，A4 自身 MUST NOT 使用风险退出码 `3`。面向用户的 detail、limitation、suggestion SHALL 同时提供中文和英文，机器 identity 不依赖翻译。

#### Scenario: A complete bounded proof is reported
- **WHEN** A4 在受限模型内完整建立 mutex proof 且没有相关 frontier
- **THEN** CLI 返回 0，报告说明“受限模型内证明”及其英文对应，并明确不代表全程序安全

#### Scenario: Evidence is partial
- **WHEN** profile、异常路径、对象 lineage 或预算任一候选相关证据不完整
- **THEN** CLI 返回 2 并同时输出中文和英文缺失证据及可复现建议
