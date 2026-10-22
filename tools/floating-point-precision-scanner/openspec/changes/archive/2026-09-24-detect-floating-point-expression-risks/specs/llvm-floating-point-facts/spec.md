## ADDED Requirements

### Requirement: LLVM facts 必须表达表达式 use-chain、归约和环境语义
`LLVMFloatingPointFactBundle` SHALL 在既有浮点指令 facts 上增加有界的 operand/use-chain、phi recurrence、scalar/vector reduction group、constrained FP rounding/exception behavior、fenv 相关已解析调用以及函数级浮点环境摘要。facts MUST 保留 opcode/predicate、operand/result types、fast-math flags、intrinsic ID、基本块/函数身份和 debug/inline provenance；use-chain 或循环恢复超出预算时 MUST 记录稳定 frontier，而不是发布不完整的确定关系。

#### Scenario: 浮点转换和比较链
- **WHEN** IR 包含 `sitofp`/`uitofp`、`fpext`/`fptrunc`、`fcmp` 和后续 branch/select use
- **THEN** bundle 记录转换类型、predicate 和有界 use-chain，使 AST 转换/比较可以关联实际 lowering

#### Scenario: phi 形成标量归约
- **WHEN** 循环 header 的浮点 phi 与 back-edge 更新形成可验证递推
- **THEN** bundle 生成稳定 reduction group，引用 phi、更新指令、初始值、循环范围线索和 flags

#### Scenario: 向量归约或重结合生效
- **WHEN** build-faithful IR 使用 `llvm.vector.reduce.*` 或带 `reassoc` 的归约指令链
- **THEN** facts 明确记录实际 lowering、元素类型/lane、初始值和重结合语义，不从源码循环名称猜测

#### Scenario: use-chain 达到预算
- **WHEN** 某函数的相关 uses 或 phi candidates 超过配置预算
- **THEN** 已排序完成的 facts 被保留，剩余范围记录 budget unknown 与最后稳定 frontier

### Requirement: LLVM 函数摘要不得伪造跨过程确定性
worker SHALL 为可验证的直接调用和 constrained/fenv 行为生成函数摘要，并 SHALL 保留递归、间接调用、无 body 外部函数及不完整 debug/source mapping 的 unknown 边界。调用方 MAY 在有界深度内组合摘要，但 MUST NOT 将未知 callee 当作无环境影响或无数学语义影响。

#### Scenario: 直接调用已知环境修改函数
- **WHEN** caller 直接调用同一模块内具有完整摘要的 rounding-mode 修改函数
- **THEN** caller 摘要引用 callee 摘要和调用位置，并保持传播深度 provenance

#### Scenario: 外部数学函数无实现体
- **WHEN** 模块只包含 libm 声明和调用而没有实现 body
- **THEN** bundle 记录解析后的调用/intrinsic 身份，但函数内部行为保持 external/unknown
