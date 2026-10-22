## ADDED Requirements

### Requirement: C/C++ Frontend 必须结构化保留宏参数与 replacement token
正式 Tree-sitter C/C++ Frontend SHALL 在保留现有 `macro_definition.value` 和 `macro_expansion.value` 兼容语义的同时，为函数式宏参数和 replacement body 中有意义的 token 产生带精确项目相对 SourceSpan、所属 definition Evidence ID、稳定序号和 token role 的 scanner-owned Evidence；macro definition MUST NOT 被表达为 call expression 或 macro invocation。

#### Scenario: 解析函数式宏定义
- **WHEN** `preproc_function_def` 包含参数列表和 replacement body
- **THEN** Frontend SHALL 产生一个 `macro_definition`、逐参数 `macro_parameter` 和逐 token `macro_replacement_token` Evidence
- **AND** 附属 Evidence SHALL 可由 definition Evidence ID 确定性关联并保持源码顺序

#### Scenario: replacement body 调用 intrinsic
- **WHEN** 函数式宏 replacement 中出现形如 identifier 后接调用括号的 intrinsic 引用
- **THEN** identifier token SHALL 具有独立 SourceSpan 和 token role
- **AND** Frontend MUST NOT 把宏定义节点本身计为 call expression

#### Scenario: 宏使用出现在定义之外
- **WHEN** 已知宏名称在非 definition ancestor 的源码位置被使用
- **THEN** Frontend SHALL 继续产生独立 `macro_expansion` Evidence
- **AND** definition、replacement token 与 expansion 的 Evidence kind 和 ID SHALL 互不混淆

#### Scenario: replacement 使用不支持的预处理语义
- **WHEN** replacement 包含 token pasting、stringification、可变参数或 parser 恢复节点
- **THEN** Frontend SHALL 保留能够准确定位的原始 token 并产生 partial Diagnostic 或 metadata
- **AND** Frontend MUST NOT 猜测完整展开结果

### Requirement: 宏结构化 Evidence 必须由 Normalizer 无损承接
CppEvidenceNormalizer SHALL 将 `macro_parameter` 和 `macro_replacement_token` 转换为稳定 `macro_parameter` 与 `macro_replacement` NormalizedFact，并 SHALL 保留原 definition Evidence 引用、token 序号、role、producer、compilation context、confidence 和 SourceSpan。

#### Scenario: 两个 producer 提供同一 replacement token
- **WHEN** Tree-sitter 与 Clang 对同一 definition、位置和 canonical token 提供 Evidence
- **THEN** Normalizer SHALL 合并为一个稳定事实并保留全部 Evidence/producer provenance
- **AND** 可选 Clang 是否存在 MUST NOT 改变该事实的语义 identity

#### Scenario: replacement Evidence 引用未知 definition
- **WHEN** 一个 macro parameter/replacement Evidence 引用 FrontendSnapshot 中不存在的 definition Evidence ID
- **THEN** Normalizer SHALL 返回 failed Diagnostic
- **AND** 无效事实 MUST NOT 进入 NormalizedSnapshot
