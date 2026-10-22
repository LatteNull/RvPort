## ADDED Requirements

### Requirement: Use source evidence only for verified direct pthread identities

在显式 AST-assisted 请求中，线程建模 SHALL 可使用 exact/resolved source entity 和 SourceIRBinding 补充直接 `pthread_create` callback、`pthread_join` handle 以及受限 `pthread_t` 声明/初始化/直接赋值 provenance。callback/handle 证据 MUST 回溯到 AST 节点、canonical entity、IR call/value 和 profile；间接函数指针、逃逸 handle 或 ambiguous binding 仍为 unknown。

#### Scenario: A cross-TU wrapper passes one direct callback

- **WHEN** wrapper 的 direct callee、callback 实体和对应 IR call 均唯一绑定，且 scope 内定义完整
- **THEN** P3 可建立条件化 ThreadContext/ThreadInstance 关系并登记 source-assisted evidence

#### Scenario: A pthread handle escapes through an unknown call

- **WHEN** handle 虽有 AST 声明但经未知指针或调用逃逸
- **THEN** provenance 为 partial/unknown，不用声明同一性补造 join 关系

### Requirement: Keep source thread relations separate from execution-order proof

AST callback、调用和源码控制关系 MUST NOT 直接产生 sequenced-before、synchronizes-with、happens-before 或 MHP 消解。P3 SHALL 继续要求现有 LLVM 局部事实和生命周期/同步规则建立执行关系，并在证据不足时传播完整性。

#### Scenario: Source order places join after a call

- **WHEN** AST 显示 join 语句书写在另一调用之后但 IR order proof 缺失
- **THEN** P3 只登记源关联候选，不把源码顺序当作已证明 join ordering
