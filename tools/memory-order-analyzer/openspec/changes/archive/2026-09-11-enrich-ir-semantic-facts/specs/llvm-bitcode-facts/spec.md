## MODIFIED Requirements

### Requirement: Extract structured memory and control-flow facts

C++ 核心 SHALL 使用 LLVM API 导出 ModuleFacts v2，包括模块身份、函数/全局定义声明、linkage、CFG、调用、内存事件及来源，并增加有类型值引用、条件边、调用实参/返回、静态初始化与 DataLayout 范围事实。事件 SHALL 区分普通/volatile/atomic load-store、RMW 类型、CAS 成功/失败序及 weak、fence order/syncscope、内存 intrinsic。未知 intrinsic/inline asm SHALL 标记 opaque effect，不能作为无效果调用。地址解析 SHALL 仅声明已实现的确定对象/GEP能力，其他地址保持 unknown。结构提取 SHALL 不执行值传播、调用点特化、别名/效果/线程或内存模型推理，不混合不同 profile 事件。

#### Scenario: CAS has distinct success and failure orders

- **WHEN** IR 包含 weak cmpxchg，成功序 acq_rel、失败序 acquire
- **THEN** 结构化事件保留两种 ordering 和 weak 属性，不压缩为单个 atomic 标记

#### Scenario: Signal fence is limited to one thread

- **WHEN** IR 包含 syncscope singlethread 的 fence 和普通 fence
- **THEN** 输出不同 scope 的事件，不将前者解释为通用跨线程同步

#### Scenario: Atomic operations remain inside a C++ wrapper

- **WHEN** O0 调用的标准库包装体含按形参选择 memory order 的多个分支
- **THEN** 保留调用实参、形参、局部值/存储关系、条件 CFG 和原始事件，声明尚未进行调用点特化，不将每个分支当作调用者必然执行的同步

#### Scenario: Rich facts are extracted without debug information

- **WHEN** 有效 BC 缺少 debug 元数据但包含调用参数、条件和内存操作数
- **THEN** 仍输出对应 v2 事实和原始事件身份方式，仅按已有约定降低源码定位状态，不猜源码变量或位置
