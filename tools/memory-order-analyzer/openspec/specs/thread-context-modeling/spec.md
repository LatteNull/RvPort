# thread-context-modeling

## Purpose

定义显式 scope 与根约束下可复用 ThreadContext 和调用点相关 ThreadInstance 的身份边界，描述条件化 create/join 生命周期、受限句柄关联、递归或循环创建的合并语义，以及预算耗尽时必须保留的 unknown frontier。

## Requirements

### Requirement: Separate reusable thread contexts from thread instances

系统 SHALL 以入口函数、抽象 worker 参数、scope/profile 和策略建立可复用 `ThreadContext`，并以分析根、父线程实例、create 调用实例/位置及 cardinality 建立 `ThreadInstance`。函数 invocation 与 thread instance SHALL 使用不同身份并显式关联；缓存上下文复用不得复用调用者特有的线程实例。

#### Scenario: The same entry is created at two callsites

- **WHEN** 同一入口函数和相同抽象参数在两个 create 调用点启动
- **THEN** 系统可以复用 ThreadContext，但必须生成不同 ThreadInstance，保留各自父线程、创建点、guard 和生命周期

#### Scenario: A worker function calls ordinary functions

- **WHEN** worker 的 P2 摘要包含一个或多个普通函数 invocation
- **THEN** 每个 invocation 关联所属 ThreadInstance，但不得把 invocation_id 当作 thread_instance_id 或反向合并

### Requirement: Model conditional create and thread lifecycle events

系统 SHALL 为显式分析根、create-attempt、thread-start、thread-exit 建立有证据的生命周期事件。`pthread_create` 仅在返回零条件成立时产生成功 spawn/start；未检查返回值 SHALL 表达为带 API-success guard 的 may-spawn，同时保留失败可能性。

#### Scenario: Create success is checked

- **WHEN** CFG 证明 `pthread_create` 返回零的分支到达后续路径
- **THEN** 该路径建立父线程 create 到 worker start 的条件化边，失败分支不包含该 worker 成功生命周期

#### Scenario: Create return is ignored

- **WHEN** 调用结果没有被源程序分支检查且不存在更强成功证据
- **THEN** 系统保留 may-spawn、合成的成功条件和失败可能性，不输出无条件已创建实例

#### Scenario: A callback target cannot be resolved

- **WHEN** create 调用可识别但入口函数为超预算候选或 unknown
- **THEN** 保存未知线程实例/frontier 及父创建点，不把该调用从计划和完整性分母中移除

### Requirement: Associate joins through bounded handle provenance

系统 SHALL 使用 `ThreadLocalFacts` 的 handle token 将 `pthread_join` 输入关联到有限 ThreadInstance 候选。只有目标唯一/有限、join 返回成功且生命周期兼容时，才生成相应 join-complete 和 worker-exit 到父线程后继的条件化边；失败或未知 join MUST NOT 终止 MHP。

#### Scenario: A unique worker is joined successfully

- **WHEN** join 输入唯一关联一个已创建 worker，返回零路径可证明且 join 位于父线程支持路径
- **THEN** 系统建立 worker-exit 到 join 成功后继的完成边，并登记 handle、调用和条件证据

#### Scenario: A join handle has multiple candidates

- **WHEN** handle copy、phi、覆盖或合并使 join 可指向多个 worker
- **THEN** 保留全部有限候选或 unknown，不任选一个实例，也不把 join 后父线程事件声明为已在所有 worker 之后

#### Scenario: Join fails or is unsupported

- **WHEN** join 返回失败、目标为 self/detached/重复 join 或相关语义不可验证
- **THEN** 不产生无条件完成边，报告 partial/unknown 并保持潜在并行关系

### Requirement: Bound recursive and repeated thread creation conservatively

系统 SHALL 对循环 create、递归/互递归 SCC 和重复 worker 启动使用稳定的 `merged`/`unknown` 实例桶及固定点预算，保存 cardinality、合并原因和未展开前沿。合并桶 MUST NOT 被解释为一个具体动态线程或确定不并行。

#### Scenario: A loop repeatedly creates the same entry

- **WHEN** create 调用位于可能重复执行的循环且无法有界枚举所有动态线程
- **THEN** 生成有限合并实例及 repeated/unknown cardinality，保留它可能与自身其他动态实例并行的语义

#### Scenario: Recursive thread discovery reaches a fixed point

- **WHEN** worker 递归或互递归创建线程且有限抽象在预算内稳定
- **THEN** 输出稳定上下文、合并实例、已知生命周期和依赖，不无限展开调用/线程栈

#### Scenario: A thread budget is exhausted

- **WHEN** 上下文、实例、SCC 轮次或图节点预算耗尽
- **THEN** 保留已知线程和非空未知前沿，报告 partial 或全部不可用时 failed，不用空图冒充完成

### Requirement: Require explicit scoped roots for thread analysis

线程分析请求 SHALL 引用一个合法显式 scope 和至少一个具体根函数 ID；每个根 SHALL 建立根 ThreadInstance。系统 MUST 验证 scope/profile/target/layout/lineage 与 P1/P2/P3 依赖一致，且不得从目录、编译数据库或所有已定义函数隐式推断程序入口。

#### Scenario: Main and worker belong to a valid scope

- **WHEN** 请求明确选择 main-like 根且其可达 create/worker 位于同一合法 scope
- **THEN** 系统把根和 worker 纳入同一上下文图并保留跨 TU 采用证据，无需 llvm-link 或原生链接

#### Scenario: Roots are absent or profiles conflict

- **WHEN** 请求没有根、引用非成员函数，或依赖混合 target/profile/lineage
- **THEN** 请求被拒绝并输出稳定错误码与双语说明，不自动选择某个 main 或扫描全部定义

### Requirement: Use source evidence only for verified direct pthread identities

在显式 AST-assisted 请求中，线程建模 SHALL 可使用 exact/resolved source entity 和 SourceIRBinding 补充直接 `pthread_create` callback、`pthread_join` handle 以及受限 `pthread_t` 声明/初始化/直接赋值 provenance。callback/handle 证据 MUST 回溯到 AST 节点、canonical entity、IR call/value 和 profile；间接函数指针、逃逸 handle 或 ambiguous binding 仍为 unknown。

#### Scenario: A cross-TU wrapper passes one direct callback

- **WHEN** wrapper 的 direct callee、callback 实体和对应 IR call 均唯一绑定，且 scope 内定义完整
- **THEN** P3 可建立条件化 ThreadContext/ThreadInstance 关系并登记 source-assisted evidence

#### Scenario: A pthread handle escapes through an unknown call

- **WHEN** handle 虽有 AST 声明但经未知指针或调用逃逸
- **THEN** provenance 为 partial/unknown，不用声明同一性补造 join 关系

### Requirement: Keep source thread relations separate from execution-order proof

AST callback、调用和源码控制关系 MUST NOT 直接产生 sequenced-before、synchronizes-with、happens-before 或 MHP 消解。P3 SHALL 继续要求现有 LLVM 局部事实和生命周期/同步规则建立执行关系，并在证据不足时传播完整性。

#### Scenario: Source order places join after a call

- **WHEN** AST 显示 join 语句书写在另一调用之后但 IR order proof 缺失
- **THEN** P3 只登记源关联候选，不把源码顺序当作已证明 join ordering

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
