## ADDED Requirements

### Requirement: Canonical facts 必须表达表达式风险的语义上下文
`FloatingPointFactBundle` SHALL 以版本化、与 Clang 原始节点解耦的 facts 表达六条表达式风险规则需要的语义上下文。转换 fact MUST 包含源/目标 canonical type、隐式或显式、cast kind、常量规范值与可表示性（可确定时）、整数位宽/符号和存储/use 边界；比较 fact MUST 包含 operand 来源、常量/零/epsilon 形态、NaN/Inf guard 与控制流用途；归约 fact MUST 包含 accumulator、递推操作、循环/算法范围、并行/向量提示与已识别补偿形态。缺失的语义 MUST 显式 unknown，不得由源码文本推断。

#### Scenario: 隐式 double 到 float 窄化
- **WHEN** C/C++ AST 将 `double` 表达式隐式转换并存储到 `float`
- **THEN** bundle 记录源/目标精度与范围、implicit cast kind、表达式及存储位置，并提供稳定 fact refs

#### Scenario: auto 接收显式 float cast
- **WHEN** C++ 表达式为 `auto result = static_cast<float>(double_value)` 或等价 C 风格显式转换
- **THEN** bundle 记录显式 cast 和 Clang 推导后的 `result` canonical type，不把 `auto` 或源码拼写当作未知类型

#### Scenario: 比较结果进入控制流
- **WHEN** 浮点比较用于 `if`、循环条件或断言，且周围存在 NaN/epsilon guard
- **THEN** bundle 保存比较、用途和 guard 之间的稳定关系，不在 facts 层判断容差是否合理

#### Scenario: 识别补偿求和
- **WHEN** 支持的循环形态包含 Kahan 或 Neumaier 补偿变量与更新关系
- **THEN** bundle 记录 accumulator、compensation、递推边和循环范围，使规则能区别普通归约与补偿算法

### Requirement: Canonical facts 必须表达浮点环境和解析后 API 身份
bundle SHALL 记录 `#pragma STDC FENV_ACCESS` 的有效作用域、解析后的 fenv 调用及读取/修改/清除/保存/恢复动作，并为每个函数生成有界浮点环境摘要。调用 fact SHALL 记录 canonical declaration identity、namespace、builtin/intrinsic family、定义头文件、required target features、模板实例、宏 spelling/expansion 和已生效 target/preprocessor guard；数学调用 SHALL 额外记录参数类型以及可静态证明的常量/区间/特殊值域线索。名称文本 MUST NOT 单独构成已解析 API 身份。

#### Scenario: 函数修改并恢复舍入模式
- **WHEN** 函数通过解析后的 fenv API 保存环境、修改 rounding mode 并在所有已解析正常出口恢复
- **THEN** facts 记录各动作、控制流位置和 `restores_environment` 函数摘要

#### Scenario: 间接调用阻断环境摘要
- **WHEN** 浮点环境影响可能穿过无法解析的函数指针、虚调用或外部函数
- **THEN** 函数摘要记录 `unknown_effect` 和 frontier，不假定调用无影响

#### Scenario: x86 intrinsic 位于条件分支
- **WHEN** 解析后的 x86 intrinsic 只出现在已验证的 x86 预处理分支中
- **THEN** fact 同时记录 declaration/intrinsic identity、头文件、target feature 和条件分支 provenance

#### Scenario: 数学调用参数域不可恢复
- **WHEN** libm 调用参数来自无法有界分析的数据流
- **THEN** 调用本身仍形成确定 fact，参数域以 unknown 表达且不伪造边界值
