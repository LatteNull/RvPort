# thread-order-and-synchronization

## Purpose

定义从独立 LLVM 执行顺序、调用锚点和线程生命周期证据组合线程关系的规则，约束 MHP、普通 mutex 同步候选与原子 reads-from 候选的保守语义，并明确禁止仅凭 P2 顺序或候选关系生成确定 happens-before 与安全结论。

## Requirements

### Requirement: Compose conditional execution order from independent evidence

系统 SHALL 仅从已校验 `ExecutionOrderFacts`、调用 anchor 和线程生命周期组合线程内/跨调用/创建/连接顺序，并为每条关系保存强度、guard、端点、线程/调用实例及证明。P2 `EffectSummary.order` 可以作为待核对的摘要信息，但 MUST NOT 单独产生 must-before、synchronizes-with 或 HB。

#### Scenario: P2 order exists without P3 proof

- **WHEN** EffectSummary 含一条 order 边，但 P3 CFG、调用 anchor 或实例证据缺失/冲突
- **THEN** 系统不得据此输出 must-before 或 HB，报告缺少独立执行顺序证明

#### Scenario: A callee returns normally between caller effects

- **WHEN** 调用前事件、callee entry/exit、正常返回和调用后事件均由同一线程实例下的独立证据证明
- **THEN** 系统组合条件化顺序边并保留调用边界；异常或不返回路径不继承调用后顺序

### Requirement: Derive conservative may-happen-in-parallel relations

系统 SHALL 对同一分析根中的 ThreadInstance pair 输出 `may_parallel`、`not_parallel` 或 `unknown`，并保存生命周期区间、guard、推导规则和完整性。只有顺序及生命周期足以排除重叠时才能输出 not_parallel；MHP MUST NOT 被解释为已发生调度、冲突或缺陷。

#### Scenario: Parent continues after creating a worker

- **WHEN** create 可能成功且父线程在 join-complete 之前继续执行相关事件
- **THEN** 父线程和 worker 在对应区间为 may_parallel，关系引用 create/start 和适用成功条件

#### Scenario: Parent code follows a proven successful join

- **WHEN** 唯一 worker 的 exit 和 join 成功边均可证明，父事件严格位于 join 成功后继
- **THEN** 对该 worker 与父事件输出 not_parallel，并保留 join/顺序证据

#### Scenario: Join or lifecycle evidence is incomplete

- **WHEN** join 失败/未知、handle 多候选、实例合并或线程退出不确定
- **THEN** 系统保持 may_parallel/unknown，不通过缺失证据推导 not_parallel

### Requirement: Model ordinary mutex synchronization candidates by object

系统 SHALL 只对直接、ABI 合格、同一规范化对象/范围且被锁定 profile 识别为普通非 robust mutex 的 lock/unlock 建模。成功 acquire、持有状态、release、失败和不平衡路径 SHALL 分开表达；跨线程关系只输出带条件的同步/互斥候选，不因函数内出现锁而把全部效果视为受保护。

#### Scenario: Two threads use the same supported mutex

- **WHEN** 两个可能并行线程对同一已识别 mutex 分别执行成功 lock、临界区和匹配 unlock
- **THEN** 输出对象限定的 acquire/release、临界区和 synchronizes-with/mutual-exclusion 候选及成功条件，不伪造全局锁顺序

#### Scenario: Threads use different mutex objects

- **WHEN** 两组 lock/unlock 的对象身份可证明不同
- **THEN** 系统不在它们之间生成同步或共同保护候选，即使调用的是同一 pthread 函数

#### Scenario: Lock can fail or unlock is unbalanced

- **WHEN** lock 返回失败/未知，或 unlock 在支持路径上没有匹配持有状态、发生过对象 clobber
- **THEN** 相应路径不建立确定临界区/同步，保留诊断和 partial/unknown

### Requirement: Preserve atomic reads-from candidates without inventing happens-before

系统 SHALL 将 P2 原子 read/write/RMW/CAS/fence 绑定到 ThreadInstance，并按对象/范围、值候选、order、failure order、syncscope、guard、生命周期和 MHP 构造或排除有限 reads-from 候选。release/acquire 共存、同对象或相邻源码位置 MUST NOT 单独生成确定 synchronizes-with/HB。

#### Scenario: A release write may feed an acquire read

- **WHEN** 两个线程中的原子写/读对象范围兼容、值域未排除、scope 兼容且可能并行
- **THEN** 输出带完整资格与未知条件的 reads-from 候选，不声明该读取实际观察到该写

#### Scenario: Candidate objects or scopes are incompatible

- **WHEN** 对象范围可证明不重叠，或 syncscope/生命周期明确排除该读取来源
- **THEN** 候选被排除并记录可审计理由，不保留虚假同步边

#### Scenario: A fence or CAS protocol is encountered

- **WHEN** 输入包含 fence、CAS 自旋或需要 modification order/release sequence 才能解释的协议
- **THEN** 保存原始 P2 效果和可知候选，未支持部分进入 unknown，不在 P3 完成发布协议或风险判定

### Requirement: Keep thread relations separate from safety findings

P3 SHALL 输出线程、执行顺序、MHP 和同步候选关系图，不运行数据竞争或发布风险规则。任何 P3 报告 MUST 保持 `safety=not_evaluated`、`findings=null`；关系为空或 complete 只表示声明范围和策略内建模状态。

#### Scenario: The graph contains no parallel pair

- **WHEN** 分析范围内未产生 MHP 或同步候选且全部计划项 complete
- **THEN** 报告可说明关系图为空，但不得转换为“程序安全”或“未发现内存序问题”

#### Scenario: A likely relaxed publication pattern is present

- **WHEN** P3 观察到原子和普通访问可能构成发布/消费模式
- **THEN** 仅保存线程、候选读取来源与顺序证据，风险分类和建议留给后续规则 change

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

### Requirement: Compose std thread join ordering only from complete lifecycle evidence

系统 SHALL 仅从 A3 构造成功、唯一/资格明确的线程实例与对象所有权、worker exit、`join` 成功、调用 anchor 和 `ExecutionOrderFacts` 组合条件化完成顺序。`detach`、`joinable()`、析构、源码顺序、P2 order、wrapper presence 或底层 pthread 名称 MUST NOT 单独生成 join-complete、not-parallel、SW 或 HB。

#### Scenario: Parent code follows a proven C++ join
- **WHEN** worker exit、对象 lineage、join 正常成功和父线程后继均在同一 guard 下得到独立证明
- **THEN** 输出 worker-exit 到 join-complete 和父后继的条件关系，并可在该限定区间推导 not-parallel

#### Scenario: A detached worker outlives its object
- **WHEN** detach 成功且父线程继续执行
- **THEN** 保持 worker 与父后继 may-parallel/unknown，不因线程对象析构或离开作用域生成完成顺序

#### Scenario: Join throws or targets a moved-from object
- **WHEN** join 的异常/错误路径可达或对象状态为 moved-from/unknown
- **THEN** 不生成完成边，传播对象与路径完整性缺口

### Requirement: Keep C++ lifecycle relations separate from synchronization and safety

A3 start/join/detach 关系 SHALL 只补充线程生命周期与 MHP 输入；除语言/库规则和执行证据明确提供的 join 完成外，不得从 callable、对象所有权、标准库 profile 或成功构造推导 mutex 保护、atomic reads-from、发布 SW/HB、risk、discharged 或全程序安全。

#### Scenario: A C++ worker uses an unknown RAII mutex
- **WHEN** A3 已解析线程生命周期但 A4 mutex/lifetime 仍未建模
- **THEN** 线程关系可保留，SynchronizationGap 继续使相关访问 unknown，不把已知 join 或 `std::thread` 支持当作互斥证明

### Requirement: Establish bounded RAII mutual exclusion from complete evidence

同步组合器 SHALL 仅在同一普通非 robust `MutexInstance`、成功 acquire、成对 release、访问包含于闭合 held-region、线程可能并行且候选相关证据完整时建立受限 mutual-exclusion/synchronization proof。proof SHALL 保留 mutex、owner、访问、thread、guard、source/IR/profile 依据；不同 mutex、may-alias、失败路径或未知 kind MUST NOT 被提升。

#### Scenario: Protected conflicting accesses are fully proven
- **WHEN** 两个可能并行线程对同一普通对象的冲突访问均位于同一已证明 mutex 的完整临界区
- **THEN** 输出受限互斥证明供下游消解该候选，并明确不构造通用 HB 或全程序安全证明

#### Scenario: One release path is missing
- **WHEN** 任一异常/正常出口不能证明 owner release 或 mutex 配对
- **THEN** 相关 held-region/proof 为 partial，候选不得因另一条完整路径而整体消解

### Requirement: Prohibit unsound ordering shortcuts

系统 MUST NOT 直接将 AST scope、源代码先后、P2 `EffectSummary.order`、P3 reads-from candidate、A3 join/detach、类型名、函数名或单个 lock/unlock presence 当作 sequenced-before、synchronizes-with、happens-before 或互斥证明。

#### Scenario: Source scope looks balanced but IR diverges
- **WHEN** AST 中 guard 包围访问，而 IR/CFG 显示未知 wrapper、提前退出或对象绑定歧义
- **THEN** 输出候选和 gap，不生成 must-held、SW 或 HB

### Requirement: Keep unsupported synchronization conservative

try/timed/recursive/robust mutex、condition variable、semaphore、rwlock、自定义同步和超出模型的 ownership 操作 SHALL 进入稳定 unknown/frontier；相关 gap MUST 阻断该候选的确定风险或消解，除非被独立完整证据证明无关。

#### Scenario: A recursive mutex protects both accesses
- **WHEN** C++ 类型或 profile 表明使用 `recursive_mutex`
- **THEN** A4 首版不套用普通 mutex 模型，报告 unsupported synchronization 并保持候选 unknown
