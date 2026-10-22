## ADDED Requirements

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
