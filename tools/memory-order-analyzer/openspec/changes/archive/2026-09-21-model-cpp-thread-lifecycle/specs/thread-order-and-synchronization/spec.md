## ADDED Requirements

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
