## ADDED Requirements

### Requirement: Inline asm Evidence 必须以完整最外层语句为边界
正式 Tree-sitter C/C++ Frontend SHALL 为每条可定位的 inline asm 源码语句最多产生一个 `inline_asm` Evidence，value 和 SourceSpan SHALL 覆盖完整最外层 asm 构造。具有 inline asm ancestor 的 qualifier、input/output operand、clobber、constraint 或其他嵌套 asm node MUST NOT 独立产生 `inline_asm` Evidence。

#### Scenario: GNU asm 包含多个 operand
- **WHEN** 一条 GNU asm 同时包含 `volatile`、输出 operand、输入 operand 和 clobber
- **THEN** Frontend SHALL 产生一个覆盖完整语句的 `inline_asm` Evidence
- **AND** `__asm__`、`volatile`、constraint 和单个 operand MUST NOT 形成额外 inline asm Evidence

#### Scenario: 同一行包含两条独立 asm
- **WHEN** 同一源码行存在两个具有不同 byte span 的独立 asm 语句
- **THEN** Frontend SHALL 为两个最外层语句分别产生 Evidence
- **AND** 去重 MUST NOT 只按行号或文本合并它们

#### Scenario: asm 节点发生错误恢复
- **WHEN** grammar 返回可定位但包含 ERROR/MISSING 的最外层 asm 构造
- **THEN** Frontend SHALL 保留至多一个 partial Evidence 并产生结构化 Diagnostic
- **AND** 它 MUST NOT 恢复对所有名称包含 `asm` 的节点进行宽泛遍历

### Requirement: Declaration attribute Evidence 必须保留属性语义边界
Frontend SHALL 只把 grammar 明确认定的完整 declaration attribute 构造表达为 `declaration_attribute` Evidence，并 SHALL 保留完整属性文本和 byte-derived SourceSpan；它 MUST NOT 为属性名称、参数或嵌套表达式分别生成同 kind Evidence。Frontend 不负责判断属性是否与 x86 有关。

#### Scenario: target attribute 包含 feature
- **WHEN** 声明包含 `target("avx2")` 或等价完整 target attribute
- **THEN** Frontend SHALL 产生一个完整 declaration attribute Evidence
- **AND** feature token SHALL 由后续 Detector 在该 Evidence 内匹配

#### Scenario: 通用 no_sanitize attribute
- **WHEN** 声明包含 `no_sanitize("memory")`
- **THEN** Frontend MAY 产生一个语法正确的完整 declaration attribute Evidence
- **AND** 它 MUST NOT 在 Frontend 被标记为架构候选或 x86 依赖
