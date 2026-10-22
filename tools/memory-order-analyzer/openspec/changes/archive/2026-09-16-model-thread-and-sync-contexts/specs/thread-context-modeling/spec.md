## ADDED Requirements

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
