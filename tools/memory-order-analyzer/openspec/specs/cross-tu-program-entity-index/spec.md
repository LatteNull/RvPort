# cross-tu-program-entity-index

## Purpose

定义显式 scope 内跨翻译单元程序实体的索引、身份、linkage/ABI 解析、定义选择、系统外部边界以及歧义和冲突的保守处理要求。

## Requirements

### Requirement: Build a strict entity index only inside explicit scope

系统 SHALL 从显式 `ProgramEntityIndexRequest v1`、已验证的 SourceSemanticFacts 和 scope 成员生成确定排序的 `ProgramEntityIndex v1`，并引用每个输入 canonical digest。`compile_commands.json` MUST 只作为 TU 重放来源，不得被解释为完整 target/link 图；scope 外实体不得被自动纳入。

#### Scenario: Compilation database contains an out-of-scope definition

- **WHEN** 数据库中存在可解析定义但请求 scope 未包含其 TU
- **THEN** index 保留 unresolved/out-of-scope 证据，不擅自扩大 scope 或选择该定义

#### Scenario: An indexed dependency is replaced

- **WHEN** 请求引用的 SourceSemanticFacts 内容与已登记 digest 不同
- **THEN** index 请求被判陈旧或无效，不混合新旧事实

#### Scenario: A modeled system API has no in-scope definition

- **WHEN** source facts 包含直接 pthread 模型已识别的系统头声明，或标准库枚举/实体，且该实体的定义按 scope 边界本就不应位于用户 TU
- **THEN** index 将其登记为可审计 external boundary，不将其 `missing-definition` 计入无关用户 program object 的 relevant completeness；未识别外部声明仍保持 unresolved

### Requirement: Resolve program entities using linkage, ABI and definition evidence

实体候选 SHALL 使用 language/profile、USR、mangled name、canonical type、entity kind、language linkage、visibility、TLS、definition role 和 ABI 属性组合解析。external entity 只有唯一兼容定义或规则允许的等价定义集才能 resolved；internal linkage、`static` 和匿名 namespace MUST 加入 physical TU identity 且不得跨 TU 合并。

#### Scenario: One extern declaration has one compatible definition

- **WHEN** 多个 TU 的 extern 声明在同一 ABI/profile 下对应唯一兼容定义
- **THEN** index 产生一个 canonical entity/object key，并保存所有声明、定义和选择证据

#### Scenario: Static objects share a name across translation units

- **WHEN** 两个 physical TU 各自定义同名 static 对象
- **THEN** index 产生两个 TU-local program entities，即使名称和 canonical type 相同

### Requirement: Treat ODR, weak and common cases conservatively

系统 SHALL 显式分类 C tentative/common definition、C++ inline/template/ODR、weak/linkonce/COMDAT、TLS 和冲突定义。只有白名单规则证明等价时才能形成 resolved definition set；无定义为 unresolved，多定义冲突、profile/类型不兼容或链接选择未知为 ambiguous/conflict，MUST NOT 任取一个候选。

#### Scenario: Compatible C tentative definitions form one object

- **WHEN** 同一 C external object 仅有兼容 tentative/common declarations 且规则允许合并
- **THEN** index 输出一个带 `tentative-common` 解析依据的 canonical object

#### Scenario: Two incompatible C++ definitions violate the supported ODR rule

- **WHEN** 相同候选实体具有不兼容类型、profile 或定义内容身份
- **THEN** index 输出 conflict、全部候选和 frontier，不建立精确 program object

### Requirement: Keep entity, object and runtime-instance identities separate

Program entity、abstract object、P2 摘要复用上下文、LLVM object、调用实例和线程实例 SHALL 使用不同命名空间并通过显式关系关联。canonical object overlay MUST 记录 resolution evidence 和来源，不能把源码实体相等直接解释为运行时分配或线程实例相等。

#### Scenario: One function summary is reused by two calls

- **WHEN** 两个调用实例引用同一 canonical function entity 和 EffectSummary template
- **THEN** index/overlay 保持两个调用实例身份，仅共享声明/定义和摘要复用关系

### Requirement: Resolve C++ thread callables across translation units precisely

ProgramEntityIndex SHALL 对 A3 自由函数、成员函数、lambda call operator 和 functor `operator()` 应用现有 linkage/ODR/ABI 精确规则，区分 declaration、inline/template instantiation、COMDAT/weak 候选、internal linkage 和外部系统实体。只有显式 scope 内 compatible definition 集合可唯一化时才能提供 exact callback target；系统标准库 broker SHALL 通过 library profile 边界引用而不是冒充用户定义。

#### Scenario: A header-defined functor is instantiated in several TUs
- **WHEN** 多个 compatible COMDAT 实例对应同一已验证 program entity 且 target/ABI/profile 一致
- **THEN** 索引按既有精确规则去重 definition target 并保留每个物理 TU 证据，不制造多个用户 callback

#### Scenario: A callable definition is outside explicit scope
- **WHEN** 构造点可见 declaration 但唯一 definition 不在 scope 且不能由系统 profile 边界解释
- **THEN** callback 为 unresolved/external frontier，不从目录或同名符号补选 definition

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
