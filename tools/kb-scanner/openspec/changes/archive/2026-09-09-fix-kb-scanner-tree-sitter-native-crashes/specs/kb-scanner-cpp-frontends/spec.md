## ADDED Requirements

### Requirement: Tree-sitter 源位置必须只由稳定字节偏移计算
正式 C/C++ Frontend SHALL 为每个源文件从原始 bytes 一次构建可复用的位置索引，并 SHALL 仅使用 Tree-sitter Node 的 `start_byte`/`end_byte` 计算 SourceLocation、SourceSpan、枚举 guard metadata 与 partial-parse Diagnostic 位置。生产扫描路径 MUST NOT 读取 `start_point` 或 `end_point`，行号和列号 SHALL 保持 1-based，列号 SHALL 表示 UTF-8 字节列。

#### Scenario: 普通节点与超长单行节点定位
- **WHEN** Tree-sitter 节点位于普通或超长单行源码中
- **THEN** Frontend SHALL 由 byte offset 得到确定的起止行列并产生 Evidence
- **AND** fake Node 的 Point getter 即使抛出异常也 MUST NOT 被访问

#### Scenario: 多行与多字节源码定位
- **WHEN** 源码包含 LF、CRLF、UTF-8 多字节字符、空行或 EOF 边界
- **THEN** SourceSpan SHALL 使用 `\n` 建立行边界并按原始 bytes 计算 1-based 列号
- **AND** 相同 bytes 与 byte range SHALL 始终得到相同位置

#### Scenario: 错误恢复节点定位
- **WHEN** grammar 返回具有合法 byte range 的 ERROR 或 MISSING node
- **THEN** Frontend SHALL 由 byte offset 产生 partial Diagnostic 和可恢复 Evidence 的位置
- **AND** 它 MUST NOT 读取 Point 或因错误节点终止整个扫描进程

#### Scenario: 无效字节范围
- **WHEN** adapter 收到负数、逆序或超出 source 长度的 byte range
- **THEN** Frontend SHALL 产生结构化 Diagnostic 或受控失败
- **AND** 它 MUST NOT 静默截断为看似有效的位置或导致原生进程崩溃

### Requirement: Tree-sitter 原生对象必须限制在单文件解析会话内
Tree-sitter adapter SHALL 在单个 parse candidate 的全部遍历期间保持 Tree 有效，但 MUST NOT 将 Parser、Tree 或 Node 写入 FrontendSnapshot、Evidence、Diagnostic、跨阶段 DTO 或 adapter 外缓存。跨遍历保存的数据 SHALL 是 Python 自有的字符串、整数、byte range、稳定 ID 或其不可变集合。

#### Scenario: 枚举分析需要多次遍历
- **WHEN** enum declaration pass 与 reference pass 需要检查同一语法树
- **THEN** adapter SHALL 在 Tree 存活时从 root 重新遍历或消费轻量快照
- **AND** 它 MUST NOT 为后续阶段持有整棵树的 Node tuple

#### Scenario: 文件分析结束
- **WHEN** parse candidate 已转换成 Evidence 与 Diagnostic
- **THEN** 返回值 SHALL 只包含 core 合同和 Python 自有基础数据
- **AND** 任何下游对象 MUST NOT 依赖原生 Node 生命周期

## MODIFIED Requirements

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
- **WHEN** Tree-sitter 节点跨越普通或超长源码行，且原生 Point 字段读取可能破坏进程内存
- **THEN** Frontend SHALL 只从节点的 start/end byte offset 和该文件的位置索引构造 SourceLocation
- **AND** SourceSpan SHALL 保持确定且生产路径 MUST NOT 读取 start/end Point

### Requirement: C/C++ Frontend 必须提供有界且可定位的 enum 语义 Evidence
正式 Tree-sitter C/C++ Frontend SHALL 为 enum/enum class 声明、单个枚举成员声明、可由语法和局部符号绑定的枚举成员引用产生项目相对、精确 token span 的 scanner-owned Evidence。Frontend SHALL 仅在 `if`、`if constexpr`、`switch`/`case` guard 内存在上述 enum member reference 时产生与引用显式关联的 condition Evidence，MUST NOT 将所有 condition clause 或 case statement 宽泛转换为 selection Evidence。可选 Clang enrichment SHALL 在 compilation context 可用时使用 compiler cursor reference 补充跨文件 binding；Frontend MUST NOT 为此生成所有 identifier Evidence、读取 knowledge 或判断迁移影响。

#### Scenario: C++ scoped enum 用于 if constexpr
- **WHEN** C++ 源码声明 `enum class Backend { scalar, avx2 }` 并在 `if constexpr` 中引用 `Backend::avx2`
- **THEN** Frontend SHALL 分别产生 enum declaration、两个 member declaration、精确的 member reference 和 condition Evidence
- **AND** reference SHALL 可追溯到唯一 declaration，condition SHALL 引用该 reference，且每个对象保留自己的 byte-derived token span、producer、language 和 binding status

#### Scenario: C enum 用于 switch case
- **WHEN** C 源码声明 enum member 并在 switch/case 中使用该成员
- **THEN** Frontend SHALL 产生 unscoped member declaration/reference Evidence，并标记 `switch_case` reference context
- **AND** 它 MUST NOT 把同名普通变量、函数调用或字符串解释为 enum reference

#### Scenario: 普通 case 与条件不产生选择 Evidence
- **WHEN** 源码包含 `case '0'`、`case 0`、没有可验证 enum declaration binding 的状态常量或不引用枚举成员的普通 if
- **THEN** Frontend MUST NOT 为这些节点产生 `selection_condition` 或 `constexpr_condition` Evidence
- **AND** 这些节点 MUST NOT 进入架构枚举证据链

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
- **THEN** Frontend SHALL 保留能够由 byte offset 准确定位的局部 Evidence、降低 confidence 并产生结构化 Diagnostic
- **AND** 缺失名称、声明绑定或条件值 MUST NOT 被补猜
