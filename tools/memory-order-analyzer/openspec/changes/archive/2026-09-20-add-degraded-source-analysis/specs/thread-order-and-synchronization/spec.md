## ADDED Requirements

### Requirement: Represent candidate-relevant unknown synchronization explicitly

P3 或其 additive 适配层 SHALL 为未识别 mutex kind、RAII lifetime、同步 wrapper、锁对象、平衡关系、失败路径和同步分析预算生成结构化 `SynchronizationGap`，包含调用/对象/线程/路径候选、来源、原因和依赖 digest。gap MUST NOT 自行建立 mutex、SW 或 HB 边，也不得被解释为已证明没有同步。

#### Scenario: A C++ lock guard lowers through an unknown wrapper

- **WHEN** IR 中存在 `__gthread_mutex_lock/unlock` 等未建模 wrapper，AST 表明可能为 RAII mutex，但锁对象/lifetime 未证明
- **THEN** 记录 candidate-relevant SynchronizationGap，不建立同步边，也不把访问标成确定无锁

#### Scenario: Direct C pthread mutex is fully modeled

- **WHEN** C11/C17 直接调用受支持的同对象普通 pthread mutex 且 lock/unlock 路径证据完整
- **THEN** 继续使用既有 mutex synchronization candidate，不因存在降级协议而转成 unknown wrapper

### Requirement: Slice unknown synchronization by affected evidence

系统 SHALL 仅在可证明 gap 与候选线程、对象、路径和调用闭包无关时忽略其局部阻断作用；无法证明无关时 SHALL 把 gap 传播到候选完整性。全局报告仍保存所有 gap。

#### Scenario: Unknown mutex protects the conflicting accesses

- **WHEN** 未建模 lock/unlock 可能围绕候选的一个或两个冲突访问且对象关系未能排除
- **THEN** 相关候选同步状态为 unknown，不得根据缺少已建模 mutex 边断言无同步

#### Scenario: Unknown synchronization is in an unrelated utility thread

- **WHEN** 依赖切片证明 gap 的线程、对象、调用和路径均不属于目标候选
- **THEN** 目标候选关系可继续计算，但顶层完整性保留该 gap
