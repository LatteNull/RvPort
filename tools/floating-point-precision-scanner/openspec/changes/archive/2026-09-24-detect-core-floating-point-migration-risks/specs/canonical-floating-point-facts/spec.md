## MODIFIED Requirements

### Requirement: Canonical fact bundle 与 Clang 原始节点解耦
每个成功翻译单元 SHALL 生成符合版本化 schema 的 `FloatingPointFactBundle`，包含 producer/profile 版本、稳定翻译单元 ID、规范化编译上下文、浮点类型、字面量、算术与比较表达式、显式/隐式转换、函数与内建调用、源码/宏位置、浮点相关选项以及 unknown/unsupported 记录。为支持核心迁移规则，bundle 还 SHALL 规范化表达 `long double` 的精确 canonical 类型属性、声明 linkage/visibility/语言链接、参数与返回边界、可变参数、记录字段与布局/持久化边界标记、乘加/乘减候选、运算链、赋值/volatile/显式 cast 等存储舍入边界，以及按命令行覆盖顺序计算的有效浮点语义选项。规则层 MUST NOT 接收 Clang 原始 JSON 节点、进程对象或未归一化命令行文本。

#### Scenario: 最小 C 翻译单元
- **WHEN** C11/C17 fixture 包含基本浮点声明、算术和隐式转换
- **THEN** bundle 以 canonical 类型和 fact kinds 表达相应事实，并通过 schema 校验

#### Scenario: 最小 C++ 翻译单元
- **WHEN** C++17/C++20 fixture 包含重载调用、显式转换和浮点表达式
- **THEN** bundle 保留解析后的被调用声明、转换种类和标准版本，不暴露 Clang 节点 ID

#### Scenario: long double 出现在公开边界
- **WHEN** C 或 C++ 声明通过外部 linkage、`extern "C"`、可变参数或外部可见记录字段暴露 `long double`
- **THEN** bundle 记录 canonical 类型、边界种类、linkage/visibility、语言链接、声明位置和完整 provenance

#### Scenario: 识别乘加和存储舍入边界
- **WHEN** 表达式包含浮点乘加链，并通过赋值、volatile 对象或显式 cast 形成可观察存储/截断边界
- **THEN** bundle 分别记录运算候选和边界事实及其稳定引用，不在 facts 层判断是否构成风险

#### Scenario: 浮点选项具有覆盖顺序
- **WHEN** 编译命令先启用 `-ffast-math`，后用更具体的否定选项恢复部分 IEEE 语义
- **THEN** bundle 保存规范化的最终有效语义及 option provenance，而不是仅保存原始 token 是否出现
