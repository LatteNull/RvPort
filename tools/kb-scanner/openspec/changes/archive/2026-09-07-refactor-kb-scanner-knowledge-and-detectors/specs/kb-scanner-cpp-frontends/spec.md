## ADDED Requirements

### Requirement: C/C++ Frontend 必须提供可定位的 declaration attribute Evidence
正式 Tree-sitter C/C++ Frontend SHALL 为可稳定识别的 GNU、MSVC 或 C++ declaration/target/vector-size attribute 产生有界、带项目相对 SourceSpan 的 `declaration_attribute` Evidence，并 MUST NOT 在 Frontend 中判断其架构影响、严重程度或阻断状态。

#### Scenario: 声明包含 x86 target attribute
- **WHEN** C/C++ 声明包含可由 grammar 定位的 target、target_clones、vector_size 或同类 attribute
- **THEN** Frontend SHALL 产生包含语法文本、node type、language、producer/version、parse mode 和 confidence 的 declaration attribute Evidence
- **AND** Local Detector SHALL 能在不重新读取源码的情况下消费该 Evidence

#### Scenario: attribute 节点不完整
- **WHEN** parser 恢复出 attribute 但对应语法树包含 ERROR 或 MISSING
- **THEN** Frontend SHALL 保留可定位的 partial Evidence 并降低 confidence
- **AND** 缺失内容 MUST NOT 被补猜为特定 x86 target 或固定向量宽度

#### Scenario: 普通声明没有架构 attribute
- **WHEN** declaration 不包含可稳定识别的 attribute 节点
- **THEN** Frontend MUST NOT 为了 Local Detector 方便而生成整文件或所有 identifier 的宽泛 Evidence

#### Scenario: 超长单行语法节点需要稳定 SourceSpan
- **WHEN** Tree-sitter 节点跨越普通或超长源码行，且原生 Point 属性在连续访问间不保证稳定对象生命周期
- **THEN** Frontend SHALL 在构造 SourceLocation 前各读取一次 start/end Point 并复制为普通整数
- **AND** SourceSpan 的行列 SHALL 与该次 Point 快照一致，不得因重复访问原生属性而崩溃或产生异常列号
