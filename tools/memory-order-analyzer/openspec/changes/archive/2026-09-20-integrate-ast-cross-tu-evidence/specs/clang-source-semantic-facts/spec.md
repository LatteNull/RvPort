## ADDED Requirements

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
