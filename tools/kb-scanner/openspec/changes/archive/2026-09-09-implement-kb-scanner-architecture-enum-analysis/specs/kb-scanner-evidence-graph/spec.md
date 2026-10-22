## ADDED Requirements

### Requirement: 枚举选择必须形成有界的声明—引用—守卫证据链
Evidence Graph Analyzer SHALL 为可验证 enum declaration、member、reference 和 selection condition 建立稳定 Entity 与 `defines`、`contains`、`selects`、`guarded_by` 关系，并 SHALL 将条件保护的下游 call/type/include/asm Evidence 纳入同一有界 proof closure。Analyzer MUST NOT 求值任意常量表达式、实例化模板或从成员名称猜测目标选择状态。

#### Scenario: if constexpr 保护 x86 调用
- **WHEN** enum member reference 出现在 if constexpr condition 中且 consequence 包含 knowledge-backed x86 调用
- **THEN** Graph SHALL 连接 file、enum type、member、condition 和 x86 call，并产生可解析 proof path
- **AND** 若模板参数取值未知，condition 到目标选择的状态 SHALL 保持 unknown

#### Scenario: switch case 选择不同后端
- **WHEN** switch/case 分别引用 x86、RISC-V 或 generic enum member并保护不同实现
- **THEN** Graph SHALL 为各 case 建立独立 selection predicate、guarded implementation 和 sibling/alternative role
- **AND** ARM-only case MAY 作为上下文保留，但 MUST NOT 单独形成 x86-to-RISC-V Finding

#### Scenario: declaration binding 唯一
- **WHEN** Tree-sitter 局部索引或 Clang semantic reference 唯一连接 member use 与 declaration
- **THEN** 对应 relation SHALL 为 complete，并保留 declaration/reference Evidence IDs
- **AND** 输入与文件遍历顺序改变 MUST NOT 改变 Entity、Relation 或 ProofPath ID

#### Scenario: declaration binding 歧义或缺失
- **WHEN** 非限定 member reference 对应多个声明、声明位于不可解析外部头文件或引用类型冲突
- **THEN** Graph SHALL 保留全部可验证候选并将 relation/proof 标记为 ambiguous、partial 或 unknown，附稳定 reason
- **AND** 它 MUST NOT 输出悬空引用或伪造 complete primary path

#### Scenario: 未实例化模板
- **WHEN** enum member 出现在依赖模板参数的 constexpr condition 中但没有可验证实例化或 build selection
- **THEN** Graph SHALL 证明语法 guard 和下游依赖关系，但 selection status SHALL 保持 unknown
- **AND** 未出现实例化 Evidence MUST NOT 被解释为 RISC-V 不会进入该分支

#### Scenario: enum graph 超过资源预算
- **WHEN** enum declaration/reference/condition closure 出现循环或超过 depth、visited、path budget
- **THEN** Analyzer SHALL 确定性截断并产生 partial proof 与结构化 Diagnostic
- **AND** 已验证局部链路 SHALL 保留，截断 MUST NOT 被解释为没有迁移风险
