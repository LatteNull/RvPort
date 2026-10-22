## ADDED Requirements

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
