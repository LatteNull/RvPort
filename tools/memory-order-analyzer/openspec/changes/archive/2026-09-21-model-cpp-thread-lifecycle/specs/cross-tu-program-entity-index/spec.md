## ADDED Requirements

### Requirement: Resolve C++ thread callables across translation units precisely

ProgramEntityIndex SHALL 对 A3 自由函数、成员函数、lambda call operator 和 functor `operator()` 应用现有 linkage/ODR/ABI 精确规则，区分 declaration、inline/template instantiation、COMDAT/weak 候选、internal linkage 和外部系统实体。只有显式 scope 内 compatible definition 集合可唯一化时才能提供 exact callback target；系统标准库 broker SHALL 通过 library profile 边界引用而不是冒充用户定义。

#### Scenario: A header-defined functor is instantiated in several TUs
- **WHEN** 多个 compatible COMDAT 实例对应同一已验证 program entity 且 target/ABI/profile 一致
- **THEN** 索引按既有精确规则去重 definition target 并保留每个物理 TU 证据，不制造多个用户 callback

#### Scenario: A callable definition is outside explicit scope
- **WHEN** 构造点可见 declaration 但唯一 definition 不在 scope 且不能由系统 profile 边界解释
- **THEN** callback 为 unresolved/external frontier，不从目录或同名符号补选 definition
