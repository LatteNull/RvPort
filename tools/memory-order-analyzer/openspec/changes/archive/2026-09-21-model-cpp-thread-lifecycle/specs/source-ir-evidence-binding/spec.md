## ADDED Requirements

### Requirement: Bind C++ thread operations and callables with explicit cardinality

SourceIRBinding 的 A3 补充 SHALL 将构造、move、join/detach/joinable/析构表达式、线程对象、callable/receiver/capture 与标准库 wrapper/call/value/object token 建立 exact/candidate/ambiguous/unresolved 绑定，保存一对多/多对一基数、支持与反对证据及 profile/model digest。名称、最近行号、唯一 debug 行或单一 wrapper symbol MUST NOT 自动构成 exact。

#### Scenario: One constructor expands to several wrapper calls
- **WHEN** 一个 `std::thread` 构造在 IR 中包含 allocation、state setup、entry broker 和异常清理调用
- **THEN** binding 保存一对多映射及每个节点角色，不任取一个调用代表全部构造语义

#### Scenario: No-debug IR still has unique entity and ABI evidence
- **WHEN** debug location 缺失，但 caller、线程对象值、callable entity、wrapper 角色和 profile 均能唯一绑定
- **THEN** 可以形成相应 entity/object/call binding；若 callsite 基数仍不唯一则保持 candidate，不因无 debug 强行 exact

### Requirement: Keep C++ source binding below the lifecycle proof boundary

A3 binding SHALL 只关联源构造与 IR/ABI 事实，不得自行声明构造成功、动态线程创建、join 成功、MHP、SW、HB、risk 或安全。生命周期关系必须由 A3 状态机、执行顺序和成功/异常路径规则单独推导。

#### Scenario: Source order places join after construction
- **WHEN** AST 中 join 语句书写在构造之后但 IR 成功路径或对象 lineage 不完整
- **THEN** binding 仅保留表达式关系和缺口，不生成 start 或 join-complete
