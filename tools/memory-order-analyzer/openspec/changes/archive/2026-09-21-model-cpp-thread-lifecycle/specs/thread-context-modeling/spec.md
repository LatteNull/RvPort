## ADDED Requirements

### Requirement: Adopt verified C++ lifecycle overlays into thread identities

线程建模 SHALL 可从合法 `CppThreadLifecycleGraph v1` 引用已验证 callback、构造实例、对象/handle lineage 和 guard，按既有身份边界建立或关联 C++ `ThreadContext` 与 `ThreadInstance`。采用 MUST 保持 P3 pthread 实例、普通 invocation 和 C++ thread object 相互独立；A3 图缺失、partial 或依赖失配不得被解释为单线程。

#### Scenario: One verified C++ construction starts a worker
- **WHEN** A3 图包含 profile 匹配、callback 唯一、构造成功且依赖完整的 construct/start 关系
- **THEN** 建立对应 ThreadContext/ThreadInstance 关联并保存 A3、AST、IR、profile 与父实例证据

#### Scenario: The same callable is constructed twice
- **WHEN** 两个构造点采用同一 callback/context
- **THEN** 保留两个 ThreadInstance 及各自对象/handle/guard，不因 context cache 合并动态实例

### Requirement: Preserve conservative repeated and recursive C++ instances

循环构造、递归/互递归 worker、重复 move lineage 和实例预算 SHALL 使用既有 merged/repeated/unknown 规则并登记 A3 对象状态与未展开 frontier。合并实例 MUST NOT 被解释为一个具体线程、确定不并行或可被一次 join 全部终止。

#### Scenario: A loop constructs and joins an uncertain sequence
- **WHEN** 构造与 join 位于可重复循环且动态配对无法有界证明
- **THEN** 生成 merged/repeated 实例和 handle 配对 unknown，不用一个 join-complete 消解全部实例的 MHP
