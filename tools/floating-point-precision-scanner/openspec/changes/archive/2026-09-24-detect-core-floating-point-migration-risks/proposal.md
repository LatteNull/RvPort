## Why

扫描器已经能够从 C/C++ AST、共享 LLVM BC 和 AST↔IR 关联中生成稳定事实，但当前仍停留在 `facts_only`，不能把已验证的架构差异转化为可操作的迁移风险结论。现在需要先实现证据确定、迁移影响大的四类核心规则，让 x86→RISC-V 浮点迁移首次产出可审计 finding，同时保持未知与失败范围的保守语义。

## What Changes

- 增加 `long-double-abi` 规则，识别 `long double` 在公开 ABI、可变参数、记录布局和持久化边界上的表示、位宽、对齐或调用约定差异。
- 增加 `x87-excess-precision` 规则，结合 source profile、有效编译选项、AST 存储边界与 IR 证据识别扩展中间精度、强制舍入和二次舍入风险。
- 增加 `fma-contraction` 规则，通过 AST 乘加表达式、source-preserving/build-faithful IR 和 profile contraction 能力区分融合、未融合、显式 FMA 与证据不足。
- 增加 `unsafe-fp-optimization` 规则，依据规范化有效选项和 IR fast-math flags 报告重结合、忽略 NaN/Inf、无符号零、近似倒数、errno/异常等实际生效语义，不以原始命令行文本直接下结论。
- 建立规则 registry、版本、默认启用集合、显式选择与稳定执行顺序；本阶段仅允许上述四条规则，其他 roadmap 规则继续保持不可用。
- 将运行时从 `facts_only` 演进为 facts/evidence 驱动的首期 risk detection；finding 使用稳定 ID、双语字段、可核验证据、影响说明、人工确认标记和测试建议。
- 对缺失 profile 字段、AST/IR binding 歧义、可选或必需 BC 缺失、规则预算耗尽和证据冲突实施逐规则 unknown/partial 传播，不把未评估范围解释为无风险。
- 同步正常、边界与异常路径单元测试，并将全部项目自有可执行源码纳入覆盖率统计；项目整体和受影响模块的 line/branch coverage 均须至少 90%。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `floating-point-risk-detection`: 明确首期可用规则集合，并增加四条核心迁移规则的命中、非命中、unknown、证据、严重性和人工确认契约。
- `canonical-floating-point-facts`: 补充公开 ABI、记录/持久化边界、存储舍入边界和规范化有效浮点选项等规则输入事实。
- `floating-point-target-profiles`: 明确四条核心规则所需 profile 字段、跨 profile 比较和字段 unknown 的传播要求。
- `scanner-runtime-foundation`: 将 `facts_only` 运行边界演进为可执行已注册规则并发布 finding，同时保持事实提取与规则层解耦。
- `scanner-io-contract`: 增加规则选择、规则版本摘要、逐规则 assessment/unknown 分母以及完整 finding 证据引用的协议要求。
- `scanner-failure-semantics`: 增加逐规则证据缺失、冲突、预算耗尽与部分评估的保守状态和诊断语义。

## Impact

- 影响 `src/floating_point_precision_scanner/` 的协议模型、schema、应用编排、facts 映射、profile 比较、规则 registry、四条规则实现、finding 聚合、诊断和原子输出。
- 需要扩展 C/C++ AST fixtures、共享 BC fixtures、profile fixtures 以及单元/契约/锁定工具链集成测试，但不改变共享 BC 的生产、等待或发布职责。
- scan request/result 与 version 输出进行向后兼容的次版本演进；未显式选择规则时启用本阶段默认规则集合，显式请求尚未实现的规则仍返回 `invalid_request/rules_not_available`。
- 不包含动态执行、跨平台数值对跑、后续表达式/比较/归约/libm/SIMD 规则、AI 判断、自动修复或 RvPort UI 集成。
