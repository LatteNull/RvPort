## MODIFIED Requirements

### Requirement: 覆盖迁移相关浮点风险类别
扫描器 SHALL 使用稳定 finding code 和独立 rule version 检测并分类首期四类 x86→RISC-V 核心迁移风险：`long-double-abi`、`x87-excess-precision`、`fma-contraction` 和 `unsafe-fp-optimization`。registry MUST 明确每条规则的事实/profile/evidence 依赖、默认启用状态和确定性排序；动态舍入与浮点环境、隐式窄化与混合精度、比较、归约、数学库以及 SIMD/架构专用 API 等后续类别在实现前 MUST 返回 `rules_not_available`，不得被静默接受或产生占位结论。

#### Scenario: 使用默认核心规则集合
- **WHEN** 有效请求省略规则选择
- **THEN** 扫描器按稳定顺序启用四条核心规则，并在结果 metadata 中记录 code、rule version 和 registry digest

#### Scenario: 选择核心规则子集
- **WHEN** 请求只选择 `long-double-abi` 和 `fma-contraction`
- **THEN** 扫描器只规划这两条规则的 assessment，其他规则标记为未请求且不影响整体状态

#### Scenario: 请求后续未实现规则
- **WHEN** 请求启用 `floating-environment`、`mixed-precision` 或其他未注册 code
- **THEN** 扫描器在事实提取前返回 `invalid_request/rules_not_available`，并列出当前支持的稳定 code

## ADDED Requirements

### Requirement: long double ABI 风险必须绑定真实边界和 profile 差异
`long-double-abi` 规则 SHALL 比较 source/target profile 中 `long double` 的格式、storage bits、precision、alignment、ABI class、calling convention 和 variadic 语义，并只在 AST facts 证明值穿越公开函数参数/返回、`extern "C"`、可变参数、外部可见记录布局或持久化/二进制边界时发布 finding。纯局部计算、两端相关属性完全一致或边界不含 `long double` MUST NOT 命中；必需 profile 字段或边界分类缺失时 MUST 返回 unknown。

#### Scenario: long double 穿越公开 ABI 且表示不同
- **WHEN** 外部可见 C/C++ 函数参数或返回值包含 `long double`，且 source/target profile 的格式、对齐或 ABI class 存在确定差异
- **THEN** 扫描器发布 `long-double-abi` high finding，要求人工确认，并引用声明事实、边界类型和两个 profile 指纹

#### Scenario: long double 只用于函数内部
- **WHEN** `long double` 只出现在无外部布局影响的局部变量和内部表达式中
- **THEN** 该 scope 的 assessment 为 `not_matched`，不发布 ABI finding

#### Scenario: 目标 profile 缺少 ABI class
- **WHEN** 边界事实存在，但 source 或 target profile 的 `long double` ABI class 为 unknown
- **THEN** assessment 为 `unknown` 并输出缺失字段及 provenance，不假定宿主 ABI

### Requirement: x87 扩展精度风险必须区分中间求值和存储边界
`x87-excess-precision` 规则 SHALL 结合 source/target evaluation method、x87 extended precision、`FLT_EVAL_METHOD`、有效 excess-precision 选项、AST 浮点运算链及赋值、volatile、显式 cast 等存储舍入边界，并在可用时核对 IR 中间类型与 `fpext`/`fptrunc`。只有 source 端可能保留扩展中间精度、target 行为不同且存在可观察运算链时才能命中；明确标准精度求值或每步已强制存储/截断时 MUST NOT 命中。决定性 profile、option 或 IR/evidence 不可用时 MUST 返回 unknown。

#### Scenario: x87 中间精度跨多个运算保留
- **WHEN** source profile/选项允许 x87 扩展中间精度，目标 profile 在声明类型精度求值，且表达式在可观察存储边界前包含连续浮点运算
- **THEN** 扫描器发布 `x87-excess-precision` finding，引用求值策略、运算链、存储边界和可用 IR 事实，并建议边界值差分测试

#### Scenario: 每步结果明确截断到声明类型
- **WHEN** AST 与 IR 证据证明每个相关中间结果在后续运算前已存储或显式截断到相同声明类型
- **THEN** assessment 为 `not_matched`，不因 source profile 支持 x87 就发布 finding

#### Scenario: 缺少决定性 IR 映射
- **WHEN** AST 存在候选运算链，但必需 IR fact 缺失或 AST↔IR binding ambiguous
- **THEN** assessment 为 `unknown`，不得仅按函数名、行号或 x86 profile 推断实际扩展精度

### Requirement: FMA contraction 风险必须比较候选表达式、策略和实际 lowering
`fma-contraction` 规则 SHALL 从 AST facts 识别乘加/乘减候选，并通过 source-preserving/build-faithful IR facts 与 verified evidence 区分独立乘法加法、隐式 contraction、显式 `fma` 调用、优化删除和歧义。只有 source/target contraction policy、有效选项或实际 lowering 表明迁移后可能发生融合或展开差异时才能命中；两端策略与可核验 lowering 一致时 MUST NOT 命中。显式 `fma` MUST NOT 被误报为编译器隐式 contraction。

#### Scenario: build-faithful IR 只在一端形成 FMA
- **WHEN** AST 存在乘加候选，verified evidence 将其绑定到一端的 `llvm.fma`，而另一端策略或事实保持 `fmul` 加 `fadd/fsub`
- **THEN** 扫描器发布 `fma-contraction` finding，并说明一次舍入与两次舍入差异及双平台测试建议

#### Scenario: 显式 fma 调用
- **WHEN** source fact 表明程序显式调用受支持的 `fma`/`std::fma`，且 IR lowering 与显式语义一致
- **THEN** 该候选不因存在 FMA 指令而命中隐式 contraction finding

#### Scenario: build-faithful profile 未提供
- **WHEN** 规则判断依赖实际优化 lowering，但请求没有可用 build-faithful IR 或可靠 evidence
- **THEN** assessment 为 `unknown`，整体状态按启用规则的必需证据保守传播

### Requirement: fast-math 风险必须基于有效语义而非原始文本
`unsafe-fp-optimization` 规则 SHALL 消费按编译器覆盖顺序归一化后的有效浮点选项，并在可用时核对 IR fast-math flags。规则至少 SHALL 表达 reassociation、no-NaNs、no-Infs、no-signed-zeros、reciprocal/approximate functions、finite-math-only、FP contraction、errno 和异常语义；原始命令行包含 `-ffast-math` 或 `-Ofast` 但后续否定选项关闭相应语义时 MUST 以最终有效状态为准。

#### Scenario: 多个危险语义实际生效
- **WHEN** 归一化编译上下文表明 reassociation、no-NaNs 和 reciprocal transformations 生效，且 IR facts 与适用范围一致
- **THEN** 扫描器发布按 TU 或共享配置聚合的 `unsafe-fp-optimization` finding，列出每个有效语义及受影响事实

#### Scenario: 后续选项关闭 fast-math 子语义
- **WHEN** 原始命令包含 `-ffast-math`，但后续选项明确恢复 signed-zero 或 NaN/Inf 语义
- **THEN** finding 只包含最终仍生效的危险语义；全部相关语义均关闭时 assessment 为 `not_matched`

#### Scenario: AST options 与 IR flags 冲突
- **WHEN** 规范化有效选项和 build-faithful IR flags 对同一语义给出不可解释的冲突结果
- **THEN** assessment 为 `unknown` 并输出证据冲突诊断，不任选一侧发布确定性结论
