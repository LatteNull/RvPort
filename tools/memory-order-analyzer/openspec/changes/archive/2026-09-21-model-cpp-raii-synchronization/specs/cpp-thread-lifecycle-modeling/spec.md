## ADDED Requirements

### Requirement: Compose A4 synchronization without changing A3 lifecycle semantics

A4 SHALL 只通过稳定引用消费 A3 `ThreadContext`、`ThreadInstance`、start/join/detach 和对象 lineage，不得修改 A3 graph、状态机、cache identity 或报告含义。mutex owner identity MUST 与线程对象 identity 分离；join/detach 或线程析构不得单独产生 mutex acquire/release。

#### Scenario: A joined thread contains a lock guard
- **WHEN** A3 已证明线程实例和 join-complete，A4 又在 worker 内识别完整 guard 临界区
- **THEN** 两组关系按显式引用组合但各自保留来源，join 不能替代 mutex 证明，mutex 也不能改写 join

#### Scenario: A detached thread has an RAII guard
- **WHEN** A3 只证明 detach，A4 识别线程内 guard
- **THEN** A4 可保留局部临界区候选，但 detach 不生成 join/HB 或扩大 guard lifetime
