# clang-source-semantic-facts

## Purpose

定义在精确翻译单元编译配置下提取、版本化并审计 Clang 源语义事实的要求，保留声明、引用、控制、profile、预算和失败完整性证据。

## Requirements

### Requirement: Extract source semantics from the exact translation-unit profile

系统 SHALL 使用锁定的 Clang 21.1.8 LibTooling worker，按与 BC 生成一致的 `CompilationProfileIdentity` 逐 TU 提取 `SourceSemanticFacts v1`。profile MUST 覆盖编译器来源、Clang 重放版本、language standard、target/ABI、sysroot/resource-dir、include、宏、强制 include、工作目录、路径映射、主文件/include hash 和规范化 argv digest；AST 与 BC profile 不一致时不得建立绑定。

#### Scenario: Clang compilation record is replayed consistently

- **WHEN** 一个 Clang C/C++ TU 的 AST 与 BC 请求引用相同完整 profile 且语义分析成功
- **THEN** worker 输出带该 profile/TU identity 和全部输入 digest 的合法 SourceSemanticFacts

#### Scenario: A GCC-only extension cannot be replayed

- **WHEN** GCC 编译记录包含锁定 Clang 无法等价解析的扩展或产生不可接受诊断
- **THEN** 该 TU 标为 partial/failed 并保存中英文原因和原始 GCC/重放身份，不删参伪造成功

### Requirement: Preserve declaration, reference and source-control evidence

`SourceSemanticFacts` SHALL 为函数、变量、字段、参数及相关表达式保存 TU-local node identity、canonical declaration/definition、USR、qualified/mangled name、language linkage、storage/linkage/TLS/visibility、canonical type、直接引用/调用、初始化/赋值、atomic/pthread 源调用、受限消费者分支线索、spelling/expansion range、宏栈和所属控制上下文。原始 AST 节点 MUST NOT 在本产物中跨 TU 合并。

#### Scenario: A macro-expanded atomic load controls a branch

- **WHEN** atomic load 经宏、有限 cast/compare 后控制一个消费者分支
- **THEN** facts 分别保存 spelling/expansion 位置、表达式依赖、直接被调实体和分支关系，不把它声明为 IR reads-from 或 happens-before

#### Scenario: Two files define different static objects with one spelling

- **WHEN** 两个 TU 各自声明同名 internal-linkage 对象
- **THEN** 两个节点拥有不同 physical-TU identity，SourceSemanticFacts 不因名称或 USR 相似而合并

#### Scenario: Adjacent expression statements have language-level sequencing

- **WHEN** 同一 `CompoundStmt` 中两个相邻 expression statement 均有稳定 source range，且没有跨越 declaration、control、loop、return、异常或宏歧义边界
- **THEN** facts 可登记独立的精确 source `sequenced-before` 关系及两端 statement node；该关系本身不声明对应 IR effect、reads-from、synchronizes-with 或 happens-before

### Requirement: Bound extraction and publish exact completeness

worker SHALL 限制 wall time、节点、引用、诊断和输出字节预算，并分别记录 planned/visited/emitted/skipped/failed 的 TU、文件、节点和关系分母。预算耗尽、fatal diagnostic、缺失 include 或损坏输入 MUST 保留已知事实与 frontier，且完整性不得为 complete。

#### Scenario: Node budget is exhausted after useful facts exist

- **WHEN** worker 在一个 TU 中达到节点预算且已提取部分声明与引用
- **THEN** 输出可验证的 partial 产物、准确 hit/total 和未处理 frontier，而不是丢弃结果或标 complete

#### Scenario: A request has a future schema version

- **WHEN** worker 收到未知字段、未来 schema 或不匹配的 source/profile digest
- **THEN** 拒绝请求并产生确定诊断，不尝试宽松解析

+### Requirement: Preserve trustworthy source facts when IR is unavailable

SourceSemanticFacts SHALL 独立于 BC 是否成功发布，只要同一编译 profile 已验证、没有使语义不可信的 fatal diagnostic、请求/schema/预算合法且提取引用闭合；产物 SHALL 明确记录 usable/partial/failed、diagnostics 和缺失 IR，不得把“有 AST 节点”本身当作可信。

#### Scenario: IR worker crashes after valid source extraction

- **WHEN** source worker 已发布引用闭合的事实，而 IR worker 随后崩溃
- **THEN** source facts 保持可用且引用原 profile，报告单独记录瞬态 IR 失败

#### Scenario: Clang recovers nodes after a fatal source error

- **WHEN** 编译诊断表明缺失声明、类型错误或 fatal include 失败但 AST 中仍有恢复节点
- **THEN** 事实不得标为 usable AST-only 证据，恢复节点只可用于失败诊断

### Requirement: Extract C degradation evidence without C++ semantic dependencies

C11/C17 source facts SHALL 保留 C linkage、tentative/common/static、struct/union 字段、宏 spelling/expansion、直接 pthread 调用、`_Atomic` 与 `<stdatomic.h>` 操作及控制关系；提取和校验 MUST NOT 依赖 C++ class、template、RAII 或标准库类型匹配。

#### Scenario: A C17 macro wraps an atomic load

- **WHEN** C17 TU 通过宏调用 `<stdatomic.h>` load 并以结果控制 payload 路径
- **THEN** source facts 保存 C 原子构造、宏栈、对象、控制候选和 C17 profile，即使后续 BC 不可用

### Requirement: Extract source candidates for supported C++ thread operations

A3 source extraction SHALL 在精确 C++17/C++20 profile 下保存 `std::thread` 构造、move construction/assignment、`join`、`detach`、`joinable`、析构、线程对象声明/引用、构造实参和异常/控制上下文。事实 SHALL 保留 canonical entity/type、模板 specialization、source range、宏栈、对象表达式和 profile，但 MUST NOT 单独产生 ThreadInstance、执行顺序、SW、HB 或安全结论。

#### Scenario: A thread is constructed from a lambda
- **WHEN** AST 中 `std::thread` 构造接收一个 lambda closure 与有界实参
- **THEN** 保存构造点、closure 类型、call operator、capture/参数初始化和线程对象候选，不声明线程已成功启动

#### Scenario: An AST-only TU contains std thread
- **WHEN** 源事实可信但 BC/IR 不可用
- **THEN** 保留 source-only C++ 生命周期候选和缺失 IR/ABI 证据，不生成正式 start/join 关系

### Requirement: Preserve callable and object evidence without guessing invocation

source facts SHALL 区分自由函数、lambda、成员函数指针及简单 functor `operator()`，保存 receiver/capture/实参关系、重载与虚调用状态、对象生命周期候选和直接/间接调用证据。重载未消解、虚调用、复杂 `std::bind`、通用函数指针或对象逃逸 MUST 保持候选/unknown。

#### Scenario: A member function has one receiver expression
- **WHEN** 构造实参包含唯一成员函数实体和一个可追踪 receiver
- **THEN** 保存 member/receiver 的独立身份与绑定候选，后续仍需 IR broker 证据才能采用 callback

#### Scenario: A functor has overloaded call operators
- **WHEN** functor 类型存在多个无法在构造点唯一消解的 `operator()`
- **THEN** 保存全部有限候选或 unknown，不按声明顺序选择一个入口

### Requirement: Extract RAII mutex and ownership source candidates

C++17/C++20 source facts SHALL 登记 `std::mutex` 对象/字段、`lock_guard`、`unique_lock`、`scoped_lock` 的 canonical declaration/type、构造/析构、move、显式 lock/unlock、owns-lock 查询、异常 cleanup、词法 lifetime 和对象/参数关系。事实 MUST 保留 spelling/expansion、模板实例、源位置及 profile identity，但 MUST NOT 从 AST 单独产生动态 acquire/release、SW、HB 或安全结论。

#### Scenario: A lock guard has an implicit destructor
- **WHEN** AST 以隐式析构表达 guard 的 scope exit
- **THEN** source facts 保存 owner、mutex、lifetime 和 cleanup 候选，并要求 IR/摘要绑定后才能形成 release

#### Scenario: Recovery AST contains a guard
- **WHEN** frontend 报错恢复节点看似包含 `lock_guard` 或 mutex 构造
- **THEN** 节点仅用于失败诊断，不成为 usable AST-only 同步证据

### Requirement: Preserve C mutex facts without C++ dependencies

C11/C17 source facts SHALL 继续独立记录直接 pthread mutex、C linkage、全局/静态对象、struct/union 字段、参数、宏和控制关系；提取、校验与降级 MUST NOT 依赖 C++ class/template/RAII 类型。

#### Scenario: C mutex is stored in a struct field
- **WHEN** C17 TU 将同一可证明结构体字段传给 `pthread_mutex_lock` 和 `pthread_mutex_unlock`
- **THEN** 保存 C 对象/字段和调用关系，不创建任何 C++ owner 或标准库 profile 依赖
