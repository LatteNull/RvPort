## ADDED Requirements

### Requirement: C/C++ Frontend 必须提供有界且可定位的 enum 语义 Evidence
正式 Tree-sitter C/C++ Frontend SHALL 为 enum/enum class 声明、单个枚举成员声明、可由语法和局部符号唯一绑定的枚举成员引用产生项目相对、精确 token span 的 scanner-owned Evidence，并 SHALL 将 constexpr/switch/case 选择上下文与成员引用关联。可选 Clang enrichment SHALL 在 compilation context 可用时使用 compiler cursor reference 补充跨文件 binding；Frontend MUST NOT 为此生成所有 identifier Evidence、读取 knowledge 或判断迁移影响。

#### Scenario: C++ scoped enum 用于 if constexpr
- **WHEN** C++ 源码声明 `enum class Backend { scalar, avx2 }` 并在 `if constexpr` 中引用 `Backend::avx2`
- **THEN** Frontend SHALL 分别产生 enum declaration、两个 member declaration、精确的 member reference 和 condition Evidence
- **AND** reference SHALL 可追溯到唯一 declaration，且每个对象保留自己的 token span、producer、language 和 binding status

#### Scenario: C enum 用于 switch case
- **WHEN** C 源码声明 enum member 并在 switch/case 中使用该成员
- **THEN** Frontend SHALL 产生 unscoped member declaration/reference Evidence，并标记 `switch_case` reference context
- **AND** 它 MUST NOT 把同名普通变量、函数调用或字符串解释为 enum reference

#### Scenario: 枚举引用跨文件或重名
- **WHEN** Tree-sitter 基线看到跨文件或多个非限定同名 member，且无法建立唯一 declaration binding
- **THEN** Frontend SHALL 保留可定位 reference candidate 并标记 partial/ambiguous 及全部可验证候选
- **AND** 它 MUST NOT 按文件或遍历顺序选择一个 declaration

#### Scenario: Clang 提供枚举语义绑定
- **WHEN** compilation context 可用且 Clang cursor 将 `DECL_REF_EXPR` 解析到 `ENUM_CONSTANT_DECL`
- **THEN** Clang enrichment SHALL 产生带 compilation context 和 declaration identity 的高置信 member reference Evidence
- **AND** Clang 不可用或 TU 有错误时 SHALL 降级为已有 Tree-sitter Evidence，而不是丢弃或伪造绑定

#### Scenario: 普通代码不产生 identifier sweep
- **WHEN** 普通声明、变量、注释或字符串包含 x86/AVX 样式文本但不位于 enum declaration/reference 语义中
- **THEN** enum Frontend MUST NOT 为其产生 enum Evidence
- **AND** 现有 comment hint 与其他结构 Evidence SHALL 继续走各自独立路径

#### Scenario: 枚举或条件语法不完整
- **WHEN** parser recovery 得到缺失 member、condition 或无法闭合的 enum 节点
- **THEN** Frontend SHALL 保留能够准确定位的局部 Evidence并降低 confidence、产生结构化 Diagnostic
- **AND** 缺失名称、声明绑定或条件值 MUST NOT 被补猜
