# llvm-floating-point-facts Specification

## Purpose

定义锁定 LLVM reader/extractor 从共享 bitcode 提取 canonical IR 浮点事实的版本、范围、身份、provenance、预算和失败隔离要求。

## Requirements

### Requirement: LLVM reader 和 extractor 版本必须固定
扫描器 SHALL 使用独立进程中锁定的 LLVM 21.1.8 reader/extractor 验证并读取 bitcode，MUST NOT 静默调用 PATH 中其他 LLVM 版本。worker 输出 SHALL 回显 reader/extractor 版本、artifact key、module SHA-256、target 和 data layout，调用方 MUST 与 manifest 和实际文件复核。

#### Scenario: 锁定 worker 与模块兼容
- **WHEN** worker 版本正确、bitcode 可由 LLVM 21.1.8 读取且回显身份全部匹配
- **THEN** 对应模块进入 canonical IR facts 映射

#### Scenario: worker 版本不匹配
- **WHEN** 可执行文件报告的 LLVM 或 extractor 版本不符合锁定协议
- **THEN** 扫描器返回 `llvm_reader_version_mismatch`，不调用其他替代工具

#### Scenario: worker 回显错误 artifact key
- **WHEN** worker 输出的 artifact key 或 module SHA-256 与请求不一致
- **THEN** 输出被视为串线或损坏并完全拒绝

### Requirement: LLVM 浮点事实必须覆盖首期 canonical IR 范围
每个成功模块 SHALL 生成版本化 `LLVMFloatingPointFactBundle`，至少表达浮点标量/向量类型，算术和比较，浮点扩展/截断及整数浮点转换，phi/select 浮点值，普通 call、libm 和 LLVM intrinsic，FMA/constrained FP/vector reduction，fast-math flags，function/module 属性、target/data layout 与 debug/inline location。规则层 MUST NOT 直接接收 LLVM C++ 对象、原始打印文本或进程对象。

#### Scenario: 算术、比较和转换模块
- **WHEN** 模块包含 `fadd`、`fcmp`、`fptrunc`、`fpext`、`sitofp` 和 `fptosi`
- **THEN** bundle 以稳定 fact kinds、规范化操作数类型、predicate/flags 和 IR provenance 表达全部受支持事实

#### Scenario: FMA 和 fast-math 模块
- **WHEN** 模块包含 `llvm.fma`、constrained FP 或带 fast-math flags 的浮点指令
- **THEN** bundle 分别记录 intrinsic/约束语义、舍入/异常元数据和每条实际生效的 flag，不从编译命令猜测 IR 结果

#### Scenario: 向量浮点归约
- **WHEN** 模块包含浮点向量操作或 `llvm.vector.reduce.fadd/fmul`
- **THEN** bundle 记录元素类型、lane 数、归约种类、初始值语义和相关 flags

### Requirement: LLVM facts 身份和排序必须确定
IR fact ID SHALL 基于 artifact key、规范化函数身份、确定的基本块/指令位置和语义载荷生成；函数、facts、unknowns、diagnostics 和 locations MUST 使用显式稳定键排序。内存地址、遍历容器偶然顺序、临时路径、时间戳、进程 ID 和并发完成顺序 MUST NOT 影响 semantic digest。

#### Scenario: 同一 BC 重复提取
- **WHEN** 字节相同的 BC 在不同目录和不同进程中重复提取
- **THEN** facts、fact ID、排序和 semantic digest 完全相同

#### Scenario: 模块字节发生语义变化
- **WHEN** 浮点指令、flag、类型、target 或 data layout 发生变化并产生新的 artifact key
- **THEN** 受影响事实身份或 bundle semantic digest 发生变化

### Requirement: 源位置和内联信息必须保留 provenance
IR fact SHALL 在可用时记录 debug file、line、column、scope 和完整 `inlinedAt` 链，并将路径规范化为项目相对形式。缺失、越界或不一致 debug metadata MUST 产生显式 unknown/diagnostic，不得构造虚假源码位置；缺少位置不影响对 IR 操作本身的确定事实。

#### Scenario: 内联函数中的浮点指令
- **WHEN** 浮点指令具有多层 `inlinedAt` debug 链
- **THEN** fact 保留定义位置和按调用顺序排列的内联调用位置

#### Scenario: 模块没有调试信息
- **WHEN** 可验证 BC 包含浮点指令但没有可用 debug location
- **THEN** 指令事实仍被发布，位置为显式 unknown，且 evidence binding 不得宣称 exact

### Requirement: 不支持语义和提取预算必须保守可审计
reader 遇到未知浮点类型、未支持 intrinsic、异常 metadata 或达到指令、facts、unknown、诊断、输出字节、wall time/CPU/内存预算时 SHALL 停止受影响范围并记录 stage、reason、artifact/function 范围和 frontier。未知或预算截断 MUST NOT 被解释为模块不存在其他浮点行为。

#### Scenario: 未支持的浮点 intrinsic
- **WHEN** worker 识别到浮点相关但不在当前 canonical 映射表中的 intrinsic
- **THEN** bundle 添加 `unsupported_intrinsic` unknown 并保留名称、类型和安全 provenance

#### Scenario: facts 数量达到预算
- **WHEN** 模块在部分事实完成后达到配置的最大 facts 数
- **THEN** worker 返回有界 partial bundle、frontier 和预算诊断，调用方将该成员计为 partial 而非 complete

### Requirement: 模块失败必须逐翻译单元隔离
bitcode parse、LLVM verifier、worker 非零退出、超时、崩溃、协议错误或输出超限 SHALL 只使对应 artifact 失败；其他已验证 artifact MUST 继续处理，除非达到请求级预算或发生无法隔离的内部错误。没有任何 artifact 产生可用 IR facts 时整体 MUST 为 `failed`。

#### Scenario: 一个模块 verifier 失败
- **WHEN** 十个计划模块中一个 verifier 失败、九个成功
- **THEN** 九个 bundle 被保留，失败成员计入 failed，整体状态至少为 `partial`

#### Scenario: 所有 worker 调用失败
- **WHEN** 没有计划 artifact 产生可用 `LLVMFloatingPointFactBundle`
- **THEN** 整体状态为 `failed`，结果不得声称完成 LLVM 浮点扫描

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
