## ADDED Requirements

### Requirement: Resolve synchronization wrappers and object entities across explicit scope

实体索引 SHALL 在显式 scope 内按 language linkage、canonical identity、ABI、definition strength、ODR 和 profile 区分用户 mutex wrapper、RAII helper、全局/静态 mutex 及对象字段。只有唯一合法 declaration/definition 和对象绑定才可参与 A4 摘要；scope 外、系统外部、weak/COMDAT 歧义或同名实体 SHALL 保留 frontier。

#### Scenario: A user wrapper is defined in another TU
- **WHEN** C++ 调用点的 wrapper 在 scope 内另一 TU 有唯一兼容 definition，mutex 参数可精确绑定
- **THEN** 索引连接 declaration/definition 和对象实体，并允许 A4 参数化摘要在调用点实例化

#### Scenario: A declaration has no in-scope definition
- **WHEN** wrapper declaration 可见但 definition 不在 scope 且不属于 verified system profile
- **THEN** 记录 external/unresolved frontier，不从目录、同名符号或 sibling archive 选择定义

### Requirement: Keep C and C++ synchronization entities distinct

索引 MUST 保持 C linkage pthread wrapper 与 C++ mangled RAII wrapper 的实体、ABI 和语言身份，除非显式绑定证明它们通过同一参数化 mutex 对象组合；不得因最终都调用 pthread ABI 而合并源实体。

#### Scenario: C and C++ wrappers share a basename
- **WHEN** C17 和 C++20 TU 各有同名 lock helper
- **THEN** 两者按 linkage/profile 分离，只有各自唯一绑定参与对应语言路径
