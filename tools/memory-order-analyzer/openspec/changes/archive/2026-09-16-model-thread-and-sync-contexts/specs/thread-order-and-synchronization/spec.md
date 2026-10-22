## ADDED Requirements

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
