## MODIFIED Requirements

### Requirement: 覆盖迁移相关浮点风险类别
扫描器 SHALL 使用稳定 finding code 和独立 rule version 检测并分类十类 x86→RISC-V 浮点迁移风险：`long-double-abi`、`x87-excess-precision`、`fma-contraction`、`unsafe-fp-optimization`、`floating-environment`、`mixed-precision-conversion`、`fragile-fp-comparison`、`reduction-reassociation`、`math-library-variance` 和 `architecture-specific-fp-api`。registry MUST 明确每条规则的 source/IR fact kinds、profile/build-context 字段、IR capability、assessment scope、evidence mode、默认启用状态、预算键和确定性排序；请求未注册 code 或不受支持 rule version MUST 返回 `rules_not_available`，不得被静默接受或产生占位结论。

#### Scenario: 使用默认完整规则集合
- **WHEN** schema 1.3 请求省略规则选择
- **THEN** 扫描器按 registry 稳定顺序启用十条规则，并在结果 metadata 中记录 code、rule version、dependency 摘要和 registry digest

#### Scenario: 旧版本请求保持既有默认规则
- **WHEN** 受支持的 schema 1.0-1.2 请求省略规则选择
- **THEN** 扫描器按该协议版本锁定的四条核心规则解释请求，不因工具升级静默增加 findings

#### Scenario: 选择规则子集
- **WHEN** 请求只选择 `mixed-precision-conversion` 和 `fragile-fp-comparison`
- **THEN** 扫描器只规划这两条规则的 assessment，其他规则为未请求且不影响整体状态

#### Scenario: 请求未知或不兼容规则
- **WHEN** 请求启用未注册 code 或指定不受支持的 rule major version
- **THEN** 扫描器在事实提取前返回 `invalid_request/rules_not_available`，并列出当前支持的稳定 code/version

## ADDED Requirements

### Requirement: floating environment 风险必须绑定状态操作、作用域和有效语义
`floating-environment` SHALL 结合解析后的 fenv API、`#pragma STDC FENV_ACCESS` 作用域、有效编译选项、constrained FP/IR behavior、source/target environment profiles 和有界函数摘要，判断 rounding mode、异常标志或环境保存/恢复依赖是否在迁移后可能改变。仅包含头文件、未调用 API 或完整保存并恢复且两端语义一致 MUST NOT 命中；间接调用、外部调用、线程边界、pragma 作用域或 profile 能力无法确定时 MUST 返回 unknown。

#### Scenario: 动态舍入与优化假设冲突
- **WHEN** 源码在有效 fenv-access 范围修改 rounding mode，而 build-faithful IR 或有效选项假定默认 rounding，且证据绑定唯一
- **THEN** 扫描器发布 deterministic `floating-environment` finding，引用状态操作、作用域、选项/IR 和 source/target profiles

#### Scenario: 环境完整保存和恢复
- **WHEN** 函数摘要证明环境在所有已解析正常出口恢复，且调用范围内没有冲突优化或未解析调用
- **THEN** 对该 scope 的 assessment 为 `not_matched`

#### Scenario: 函数指针穿过环境边界
- **WHEN** 状态影响可能通过无法解析的间接调用或线程入口传播
- **THEN** assessment 为 `unknown`，诊断公开稳定 frontier，不假定调用无副作用

### Requirement: mixed precision conversion 必须按类型和可表示性判断
`mixed-precision-conversion` SHALL 分析隐式浮点窄化、整数转浮点、常量类型、usual arithmetic conversions、混合精度表达式和最终存储/use 边界。规则 MUST 报告源/目标 canonical type、precision/range 关系以及可确定时的常量精确可表示性；仅因出现 `auto`、显式 cast 或不同类型而不得命中。显式 cast 默认视为意图证据，除非其外层仍存在独立隐式损失转换。

#### Scenario: 非常量 double 隐式存入 float
- **WHEN** `double` 值在没有显式 cast 的情况下转换并存入 `float`，且目标 precision/range 小于源类型
- **THEN** 扫描器发布 deterministic finding，区分 precision loss、range loss 或值域未知，并引用 conversion/storage facts

#### Scenario: 精确可表示整数常量转 float
- **WHEN** 整数常量的规范值可由目标浮点类型精确表示
- **THEN** assessment 为 `not_matched`，不因类型类别不同发布 finding

#### Scenario: auto 推导显式转换结果
- **WHEN** `auto result = static_cast<float>(double_value)` 的 AST 明确包含显式 cast 且没有后续隐式窄化
- **THEN** 该候选为 `not_matched` 或意图信息，不把 `auto` 误判为未知或隐式转换

#### Scenario: 模板实例类型恢复失败
- **WHEN** 转换位于宏/模板实例中且 canonical source 或 destination type 无法可靠恢复
- **THEN** assessment 为 `unknown`，不得按源码 token 推断类型

### Requirement: fragile floating-point comparison 必须分离模式事实与业务容差
`fragile-fp-comparison` SHALL 识别计算所得浮点值的精确 `==`/`!=`、近零绝对/相对 epsilon 组合、NaN/Inf 语义错误及比较的控制流用途。可由语言语义证明的 NaN 错误模式 MAY 产生 deterministic finding；仅能推断比较对舍入敏感时 MUST 产生 heuristic finding，使用固定 rationale、`confidence=medium|low` 和 `requires_human_confirmation=true`。扫描器 MUST NOT 发明、替换或宣称唯一业务 epsilon。

#### Scenario: 计算结果精确相等
- **WHEN** 两个非同源计算浮点表达式使用精确相等控制关键分支，且没有领域容差证据
- **THEN** 扫描器发布 heuristic finding，说明模式与证据，并建议由领域测试确定绝对、相对或 ULP 策略

#### Scenario: 通过等号测试 NaN
- **WHEN** 代码使用 `x == NAN`、`x != NAN` 或等价可证明永真/永假的 NaN 比较
- **THEN** 扫描器发布 deterministic finding，并建议使用标准分类 API

#### Scenario: 明确的领域比较 helper
- **WHEN** 比较调用解析到项目配置的领域 tolerance helper，且语义/参数完整
- **THEN** 规则不把该调用当作裸精确比较；若 tolerance 合理性无法证明，不生成确定安全结论

#### Scenario: 比较用途不可恢复
- **WHEN** 比较存在但控制流用途、operand provenance 或 NaN guard 因 unsupported AST/evidence 不完整
- **THEN** assessment 为 `unknown`，不得按同一行文本拼接推断

### Requirement: reduction reassociation 必须结合递推形态和实际 lowering
`reduction-reassociation` SHALL 从 AST facts 识别浮点 sum、product、dot-product、并行/向量归约与受支持补偿算法，并在可用时通过 source-preserving/build-faithful IR 验证 phi recurrence、vector reduction、reassociation flags 和实际顺序。仅有归约形态但缺少敏感度或 lowering 差异时最多产生 heuristic finding；IR/profile/option 证明一端重结合或向量化且另一端语义不同 MAY 提升证据强度。单元素、固定无重排小表达式或已验证补偿算法 MUST NOT 被当作普通未补偿归约命中。

#### Scenario: build-faithful IR 发生向量归约
- **WHEN** AST 证明浮点累加，verified evidence 将其绑定到带重结合语义的向量归约，且 source/target policy 不同
- **THEN** 扫描器发布引用 AST recurrence、IR group、flags 和 profiles 的 finding，并建议病态输入和跨平台顺序测试

#### Scenario: 只有 AST 求和循环
- **WHEN** 可识别长浮点求和但没有可靠 build-faithful IR 或输入敏感度证明
- **THEN** 规则仅发布需要人工确认的 heuristic finding，或按配置保留候选 assessment，不宣称已发生重排

#### Scenario: Kahan 补偿求和
- **WHEN** AST/IR facts 完整证明受支持的 Kahan 更新关系且没有证据显示优化破坏补偿步骤
- **THEN** 普通归约风险为 `not_matched`；若 fast-math 可能破坏关系，由相应优化证据单独评估

#### Scenario: 循环递推歧义
- **WHEN** 多个 phi/update 候选无法由 evidence 唯一绑定到 accumulator
- **THEN** assessment 为 `unknown`，不任选递推链发布 finding

### Requirement: math library variance 必须绑定调用、输入域和 build context
`math-library-variance` SHALL 识别解析后的标量/向量数学调用，并比较 source/target `FloatingPointBuildContext` 中的 libm identity、version、errno、exception、special-value 和已验证能力。只有调用语义与 profile/context 差异共同支持风险时才能发布 finding；仅看到 `sin`、`exp` 等函数名不得命中。输入域未知时 MAY 给出适用的特殊值/极值测试建议，但 MUST NOT 断言业务路径一定覆盖该域。

#### Scenario: 两端 libm 特殊值语义不同
- **WHEN** 解析后的数学调用可达，参数域可能包含相关特殊值，且经过验证的 source/target build contexts 对 errno/exception/special-value 行为不同
- **THEN** 扫描器发布 deterministic context-difference finding，引用调用、域线索和两个 context fingerprints

#### Scenario: 精确函数且语义一致
- **WHEN** 调用解析到标准要求精确的受支持函数，且两端 context 对依赖语义一致
- **THEN** assessment 为 `not_matched`

#### Scenario: libm 身份未知
- **WHEN** 调用事实存在，但任一端 libm implementation/version 或依赖能力为 unknown
- **THEN** assessment 为 `unknown`，不得使用扫描器宿主 libm 代替

### Requirement: architecture-specific API 必须绑定声明身份和目标保护
`architecture-specific-fp-api` SHALL 根据解析后的 declaration/builtin/intrinsic identity、头文件、required target features、模板/宏 provenance 和有效条件编译分支识别 x86 SIMD intrinsic、专用向量数学入口及其他架构限定浮点 API。字符串名称相似不得单独命中；已验证只在 x86 分支编译且目标有独立实现的可移植 wrapper MUST NOT 作为无保护调用报告。finding SHALL 给出 RISC-V 替代调查和语义对比清单，但不得自动声明某替代完全等价。

#### Scenario: 无保护使用 x86 intrinsic
- **WHEN** C/C++ 表达式解析到 x86-only floating-point intrinsic，当前编译路径可达且 target profile 不支持所需 feature
- **THEN** 扫描器发布 deterministic finding，引用 declaration、header、feature、guard 和 source/target profiles

#### Scenario: 可移植 wrapper 具有目标分支
- **WHEN** wrapper 的 x86 intrinsic 位于验证过的 x86 分支，RISC-V 分支解析到独立受支持实现，且对外调用不泄露架构类型
- **THEN** x86 分支自身不产生无保护 API finding，相关语义等价性仍可作为人工验证建议

#### Scenario: 宏分支 provenance 不完整
- **WHEN** intrinsic 位于宏/条件编译中但 active guard 或 expansion provenance 无法确定
- **THEN** assessment 为 `unknown`，不得仅按头文件或函数名称报告确定风险
