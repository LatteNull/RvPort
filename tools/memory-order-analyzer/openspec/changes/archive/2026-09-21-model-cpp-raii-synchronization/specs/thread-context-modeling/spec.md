## ADDED Requirements

### Requirement: Bind RAII mutex activity to existing thread instances

线程组合器 SHALL 将 A4 acquire/release、owner 和 held-region 绑定到既有 P3/A3 `ThreadInstance` 与 MHP 候选，保持 `ThreadContextGraph v1` 的 identity、版本和完整性语义不变。无法唯一确定实例、重复循环实例合并或 callback/lifecycle 不完整时 MUST 保留 may/merged 关系和 frontier，不得生成 must 互斥。

#### Scenario: Two known worker instances use one mutex
- **WHEN** A3/P3 唯一识别两个可能并行线程实例，A4 将双方临界区绑定同一 mutex
- **THEN** A4 graph 可记录实例化互斥候选及完整来源，不向 P3 根图写入新节点

#### Scenario: One callback represents repeated unknown instances
- **WHEN** 线程在循环中重复创建且 A3 只能形成 merged/repeated 实例
- **THEN** mutex activity 保留实例不确定性，不能用一次 acquire/release 证明全部实例互斥或顺序

### Requirement: Preserve C pthread thread contexts independently

C11/C17 直接 pthread mutex 事实 SHALL 继续绑定 P3 线程实例，不要求 A3 lifecycle 或 A4 C++ owner；混合 C/C++ scope 中每个关系 MUST 保留语言/profile 来源。

#### Scenario: C worker and C++ worker coexist
- **WHEN** 同一 scope 同时含 C pthread worker 与 C++ `std::thread` worker
- **THEN** 两者分别使用 P3/A3 入口，只有可证明的共同 mutex identity 才允许 A4 adapter 组合
