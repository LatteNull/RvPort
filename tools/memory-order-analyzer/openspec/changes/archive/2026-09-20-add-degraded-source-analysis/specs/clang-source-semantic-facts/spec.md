## ADDED Requirements

### Requirement: Preserve trustworthy source facts when IR is unavailable

SourceSemanticFacts SHALL 独立于 BC 是否成功发布，只要同一编译 profile 已验证、没有使语义不可信的 fatal diagnostic、请求/schema/预算合法且提取引用闭合；产物 SHALL 明确记录 usable/partial/failed、diagnostics 和缺失 IR，不得把“有 AST 节点”本身当作可信。

#### Scenario: IR worker crashes after valid source extraction

- **WHEN** source worker 已发布引用闭合的事实，而 IR worker 随后崩溃
- **THEN** source facts 保持可用且引用原 profile，报告单独记录瞬态 IR 失败

#### Scenario: Clang recovers nodes after a fatal source error

- **WHEN** 编译诊断表明缺失声明、类型错误或 fatal include 失败但 AST 中仍有恢复节点
- **THEN** 事实不得标为 usable AST-only 证据，恢复节点只可用于失败诊断

### Requirement: Extract C degradation evidence without C++ semantic dependencies

C11/C17 source facts SHALL 保留 C linkage、tentative/common/static、struct/union 字段、宏 spelling/expansion、直接 pthread 调用、`_Atomic` 与 `<stdatomic.h>` 操作及控制关系；提取和校验 MUST NOT 依赖 C++ class、template、RAII 或标准库类型匹配。

#### Scenario: A C17 macro wraps an atomic load

- **WHEN** C17 TU 通过宏调用 `<stdatomic.h>` load 并以结果控制 payload 路径
- **THEN** source facts 保存 C 原子构造、宏栈、对象、控制候选和 C17 profile，即使后续 BC 不可用
