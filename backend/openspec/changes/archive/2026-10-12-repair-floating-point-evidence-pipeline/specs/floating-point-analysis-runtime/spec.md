## ADDED Requirements

### Requirement: Clang 虚拟位置和系统声明不得成为项目 source facts
浮点扫描器 SHALL 根据可验证的物理 spelling/expansion 文件、include provenance 和 main-file 省略规则确定项目归属。`<scratch space>`、`<built-in>`、`<command line>` 及等价 Clang 虚拟来源 MUST NOT 相对于编译目录解析为项目文件；项目根外系统声明 MUST NOT 形成独立 source facts。无法证明物理归属时 SHALL 保守记录 unknown，而不得默认继承为项目成员。

#### Scenario: 系统数学声明来自 scratch space
- **WHEN** 项目测试包含系统数学头且 Clang 将系统函数位置报告为 `<scratch space>`
- **THEN** 这些函数声明 MUST NOT 形成项目 type、call 或 long-double ABI 候选
- **AND** 项目源码中的实际调用节点仍可形成有界的外部声明摘要

#### Scenario: 项目头文件和宏
- **WHEN** 浮点表达式位于项目头文件或项目宏的 spelling/expansion 位置
- **THEN** 扫描器 SHALL 保留真实项目相对路径和宏 provenance
- **AND** 不得因排除虚拟位置而丢弃可证明的项目事实

#### Scenario: 位置归属无法证明
- **WHEN** 节点既没有可验证物理文件，也不能通过受控 main-file 省略规则确定归属
- **THEN** 扫描器 SHALL 记录脱敏的归属 unknown
- **AND** MUST NOT 将节点默认为主源码或 `build/<scratch space>`

### Requirement: Conversion facts 必须只表达 canonical 标量数值转换
扫描器 SHALL 通过统一 canonical type 解析器识别浮点和整数标量，优先使用 `desugaredQualType` 并保存原始 `qualType` provenance。conversion fact SHALL 由数值 cast kind 和规范化端点类型共同决定；指针、函数、成员指针、数组、record/container 或其他复合类型 MUST NOT 仅因类型文本包含 `float`、`double` 或 `_Float` 而进入 mixed-precision 标量候选。

#### Scenario: 隐式 double 到 float
- **WHEN** Clang AST 表示 `double` 值隐式转换并存入 `float`
- **THEN** mapper SHALL 生成包含 canonical source/destination scalar type、cast kind 和存储用途的 conversion fact
- **AND** mixed-precision 规则 SHALL 按实际 precision/range 判断

#### Scenario: typedef 和 auto 推导
- **WHEN** 浮点标量通过 typedef、cv 修饰或 `auto` 推导表达
- **THEN** mapper SHALL 使用可验证的脱糖类型恢复 canonical scalar type
- **AND** SHALL 保留原始类型拼写用于审计而不把 `auto` 当成 unknown

#### Scenario: 函数和浮点指针转换
- **WHEN** AST 包含 FunctionToPointerDecay、数组到指针、空指针到 `float*` 或 `const float*` 的 LValueToRValue
- **THEN** 这些节点 MUST NOT 形成 mixed-precision conversion 候选
- **AND** 不得产生 `conversion_type_unknown`

#### Scenario: 浮点容器类型
- **WHEN** 声明或转换类型为 `std::array<float, N>`、浮点数组或其他包含浮点元素的 record/container
- **THEN** 类型本身 MUST NOT 被当成浮点标量
- **AND** 容器元素发生真实标量转换时仍 SHALL 对该元素生成 conversion fact

#### Scenario: 数值 cast 端点确实缺失
- **WHEN** cast kind 明确表示数值转换但 source 或 destination canonical scalar type 无法可靠恢复
- **THEN** mapper SHALL 生成候选级 unknown 和类型 provenance
- **AND** MUST NOT 按变量名、字面量后缀或类型子字符串猜测

### Requirement: Unknown 和 unsupported 必须按候选与规则依赖传播
扫描器 SHALL 区分已由子事实表达的结构节点、与启用规则无关的非阻断 unsupported 和缺失规则必需语义的 blocking unknown。blocking 记录 MUST 标识受影响候选、scope、fact kind 或 rule dependency；规则 MUST NOT 因无关节点或同 TU 的无关候选而整体降级。

#### Scenario: 数组下标和赋值包装已被子事实表达
- **WHEN** `output[i] = left[i] + right[i]` 的加法和标量操作数已生成完整 arithmetic/conversion facts
- **THEN** 外层 ArraySubscriptExpr 和赋值 BinaryOperator MUST NOT 单独产生 blocking unknown

#### Scenario: 初始化列表包含精确整数常量
- **WHEN** `std::array<float, N>` 的初始化列表包含可精确表示的整数常量
- **THEN** 相关标量转换 SHALL 被正常评估
- **AND** InitListExpr 或 ImplicitValueInitExpr 包装节点不得使整个 TU 为 unknown

#### Scenario: 同一 TU 同时包含确定损失和未知转换
- **WHEN** 一个候选具有可证明的隐式精度损失，另一个真正缺少 canonical endpoint type
- **THEN** 确定候选 SHALL 保留 matched assessment/finding 和直接证据
- **AND** 未知候选 SHALL 独立计入 unknown，不得删除或覆盖已确定结论

#### Scenario: 与规则无关的 unsupported 节点
- **WHEN** 未识别节点不与某条规则声明的 fact/evidence dependency 相交
- **THEN** 该规则 SHALL 继续完成 matched 或 not-matched assessment
- **AND** 可保留非阻断诊断而不降低该规则状态

### Requirement: Long double ABI 必须使用真实边界和有界直接证据
`long-double-abi` SHALL 只消费真实项目物理文件中的 canonical `type` fact，且候选必须属于可证明的公开参数/返回、变参、外部可见布局、持久化或二进制边界。候选 SHALL 按稳定声明身份去重；finding/evidence SHALL 只引用结论直接依赖的边界事实与 source/target profiles，不得引用整个翻译单元的全部浮点或类型事实。

#### Scenario: 系统头包含大量 long double API
- **WHEN** 系统数学库声明数百个 `long double` 函数而项目未声明任何 long-double 边界
- **THEN** 项目 scope 的 assessment SHALL 为 `not_matched/no_abi_boundary`
- **AND** MUST NOT 产生 provenance budget unknown

#### Scenario: 项目公开函数使用 long double
- **WHEN** 项目头声明外部可见的 `long double` 参数或返回值，且 source/target ABI 属性不同
- **THEN** 扫描器 SHALL 发布引用该声明和两个 profile 的 finding
- **AND** 其他无关类型事实不得进入其 evidence

#### Scenario: 多个真实 ABI 边界
- **WHEN** 项目具有多个去重后的 long-double ABI 边界
- **THEN** 扫描器 SHALL 按稳定 declaration/boundary key 评估并使用 occurrence、分组或有界聚合表达
- **AND** 达到既有 provenance 上限时 SHALL 保留稳定 frontier/partial 语义而不得提高上限或静默截断

### Requirement: Facts 和规则语义变化必须版本化并安全失效缓存
canonical type、origin、blocking dependency 或规则候选语义发生变化时，扫描器 SHALL 提升相应 facts producer/schema 与规则实现版本，并使旧内容寻址缓存安全降级为 miss。系统 MUST NOT 就地改写旧缓存、复用旧语义生成新结果或改变历史 Finding。

#### Scenario: 读取旧 facts 缓存
- **WHEN** 缓存条目的 facts schema 或 producer version 早于本 change
- **THEN** 扫描器 SHALL 将其视为 cache miss 并从可信输入重新计算
- **AND** 缓存失效本身不得使扫描状态降为 partial

#### Scenario: 冷热缓存结果等价
- **WHEN** 相同输入在冷缓存和新版本热缓存下重复执行
- **THEN** assessment、finding、diagnostic、稳定 ID、排序和 semantic digest SHALL 一致

#### Scenario: 修正规则候选语义
- **WHEN** long-double 或 mixed-precision 的候选范围、assessment scope 或身份输入发生语义变化
- **THEN** registry SHALL 使用新的实现版本表达该变化
- **AND** 历史结果及其旧 ID SHALL 保持不可变

### Requirement: 证据链修复必须通过独立测试和真实 API 对照
后端与浮点扫描器 SHALL 在 Linux Docker 中分别执行独立单元测试，mock 外部服务，并覆盖正常、边界、异常、unknown、缓存和预算路径。backend 项目以及 scanner 的全部项目自有 Python/C++ 源码均 SHALL 纳入覆盖率统计；各项目整体和受影响模块的行覆盖率、可用分支覆盖率 MUST 分别至少为 90%。修复完成后 SHALL 通过真实 API 重新运行 `demo-test1` 并保留前后审计。

#### Scenario: 固定回归 fixture
- **WHEN** 执行本 change 的 scanner 单元测试和 validation corpus
- **THEN** SHALL 覆盖虚拟位置、系统头、项目宏/头、真实 long-double 边界、typedef/auto、函数指针、浮点指针、容器、确实缺失类型、合法证据超限和 AST-only
- **AND** 对 assessment 状态、直接证据、双语诊断、稳定排序和 v2 引用闭包进行有效断言

#### Scenario: 真实 API 重跑
- **WHEN** 单元测试、覆盖率和协议校验全部通过
- **THEN** 系统 SHALL 使用 project `9915a12c-9338-419e-b589-9a3984d56c62`、source revision `a019391f-89e6-4d8e-8eed-1b7871055541` 和 build run `be53c759-1e2e-459a-9f73-ef8289ecfaf2` 创建新的浮点分析
- **AND** 验证报告 SHALL 与历史 analysis `aee4ef66-6d81-4e88-afd7-606cc7d6cc9a` 对比 BC 状态、各层分母、诊断、finding、证据来源和状态
- **AND** 不得预设新结果必须为 COMPLETE 或删除合法的 reduction heuristic finding

#### Scenario: 覆盖率或真实验证失败
- **WHEN** 任一单元测试失败，项目整体或受影响模块行/分支覆盖率低于 90%，或真实 API 结果不符合证据边界
- **THEN** 本 change 的实现和质量任务 MUST 保持未完成
- **AND** 不得以集成测试、编译成功或隐藏诊断替代门禁
