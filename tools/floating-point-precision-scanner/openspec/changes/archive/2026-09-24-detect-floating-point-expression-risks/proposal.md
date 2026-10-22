## Why

扫描器目前只覆盖 `long double`、x87、FMA 和 unsafe floating-point optimization 四类核心迁移风险，尚不能判断更常见的表达式级精度损失、浮点环境依赖、顺序敏感归约、数学库差异及架构专用 API。现有 canonical facts、LLVM facts 和结果协议也不足以表达这些规则需要的控制流、循环、调用边界、libm build context、启发式证据与可审计抑制，因此需要在继续集成前补齐这一层能力。

## What Changes

- 将规则 registry 从四条核心规则扩展为十条稳定规则，新增 `floating-environment`、`mixed-precision-conversion`、`fragile-fp-comparison`、`reduction-reassociation`、`math-library-variance` 和 `architecture-specific-fp-api`，并声明每条规则的 AST、IR、profile、build context、聚合范围与确定性等级依赖。
- 扩展 C/C++ canonical facts，表达隐式/显式转换及可表示性、比较用途和 NaN/epsilon guard、函数级浮点环境摘要、归约递推与补偿算法、解析后 API 声明/头文件/目标保护以及数学调用参数域线索。
- 扩展 LLVM BC facts 与 AST↔IR evidence，表达转换 opcode、`fcmp`、phi/use-chain、标量及向量归约、constrained FP/浮点环境调用和函数摘要；缺失、冲突或歧义继续保守传播为 `unknown`。
- 将 libm 身份、版本、能力和 provenance 建模为构建/运行镜像选择的 build-context overlay，而不是仅按 x86 或 RISC-V 架构静态推断。
- 明确 deterministic 与 heuristic finding 的边界；启发式结论必须包含 `evidence_origin=heuristic`、confidence、稳定理由和 `requires_human_confirmation=true`，不得覆盖确定性事实或臆造业务容差。
- 对扫描请求/结果协议进行向后兼容的次版本演进，补齐 `evidence_origin`、可审计 suppression、suppressed 分母、build-context 指纹、稳定 finding ID、确定性排序和中英文诊断/建议。
- 为六条新规则及公共事实/协议层补充正常、边界、异常、`unknown` 和 suppression 单元测试；覆盖率统计纳入全部项目自有源码，项目整体及受影响模块行覆盖率、分支覆盖率均至少 90%。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `canonical-floating-point-facts`: 增加转换、比较用途、浮点环境、归约、解析后 API 与数学调用域的版本化 canonical facts。
- `llvm-floating-point-facts`: 增加表达式级转换、比较、归约、constrained FP 和函数摘要事实及其预算/unknown 语义。
- `ast-ir-floating-point-evidence`: 增加新事实族的多对多绑定、控制流/归约关联和确定性、启发式证据边界。
- `floating-point-target-profiles`: 增加可由请求绑定的 libm/build-context overlay、能力 provenance 与指纹规则。
- `floating-point-risk-detection`: 注册并规范六条新规则的命中、非命中、unknown、严重性、启发式与 suppression 行为。
- `scanner-io-contract`: 演进请求和结果协议，加入 build context、evidence origin、suppression、suppressed 分母和十条规则元数据。
- `scanner-runtime-foundation`: 执行十条规则及其显式依赖，保持 facts-only、隔离失败、稳定排序和原子输出。
- `scanner-failure-semantics`: 规定类型、控制流、循环、调用边界、libm/profile 和 evidence 缺失或冲突时的保守传播。

## Impact

- 影响 `facts.py`、Clang AST helper、LLVM worker、evidence binder、profiles、rules、application/CLI、diagnostics、output 与版本常量。
- 需要演进 scan request/result、canonical facts、LLVM facts、evidence 与 profile/build-context JSON Schema，并更新固定 fixtures 和兼容性测试。
- 继续只分析 C/C++，继续消费而不生成共享 LLVM BC；不引入运行时差分执行、AI 决策或业务容差推断。
- 新增规则会影响默认规则集合、registry digest、analysis scope、结果计数和下游报告消费者，但旧协议版本仍按既有四规则语义验证。
