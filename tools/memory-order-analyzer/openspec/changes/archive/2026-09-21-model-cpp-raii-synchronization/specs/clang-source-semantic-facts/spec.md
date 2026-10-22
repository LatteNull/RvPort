## ADDED Requirements

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
