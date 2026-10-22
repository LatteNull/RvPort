## Why

`demo-test1` 的真实浮点分析虽然任务成功，但因旧版 BC manifest 被新版后端错误重算摘要、Clang 虚拟/系统节点越过项目边界，以及非标量转换被误归类，最终退化为 `AST_ONLY/PARTIAL` 并产生并非由真实源码证据不足导致的 unknown。需要修复证据生产、校验和规则传播链，使系统只对真正缺失或冲突的证据保守降级，同时继续拒绝不可信 BC、保留 AST-only 能力和 source-preserving/build-faithful 边界。

## What Changes

- 后端按 manifest schema 版本校验 canonical identity：读取 `2.0` 时不得把 `2.1` 新增的空字段加入摘要，读取 `2.1` 时继续严格验证语言标准上下文；摘要、bundle、路径或引用确实不一致时仍拒绝消费。
- 后端保存并公开脱敏、双语且可操作的 BC 校验根因，包括失败阶段、稳定原因码、artifact 身份、schema、producer 和安全摘要；不再把所有异常压缩成 `BITCODE_WORKER_VALIDATION_FAILED`，但继续在 compile database 可用时安全降级为 AST-only。
- 将 compile database 原始命令数、C/C++ 候选数、项目翻译单元数及 BC produced/failed/missing 分母分开统计；CMake 探针、编译器识别文件、生成文件和非 C/C++ 命令不得污染项目证据覆盖率。
- 修复扫描器项目源码边界，显式排除 `<scratch space>`、`<built-in>`、`<command line>` 等 Clang 虚拟文件和系统声明；只允许真实项目源码/头文件形成 source facts，必要的外部声明只能形成有界摘要。
- 建立统一 canonical scalar type 解析，优先使用 `desugaredQualType` 并保留可靠的 `qualType` provenance；指针、函数、数组、引用包装和容器不得仅因类型文本包含 `float`/`double` 而形成标量 conversion fact。
- 将 mixed-precision 的缺失类型和 unsupported 传播限制到真正相关的候选；确定命中的损失转换使用直接证据发布，真正无法恢复源/目标标量类型时才返回 candidate-local unknown，无关结构节点不得把整个翻译单元降级。
- 将 `long-double-abi` 限定为真实项目 `type` fact 和可证明 ABI/持久化边界，按声明身份去重，并以确定性有界直接证据表达聚合结果；不得通过增大 128 条协议上限解决错误收集。
- 提升 canonical facts producer/schema 版本并使旧缓存安全降级为 miss；结果协议、稳定排序、原子发布、双语诊断和历史结果不可变语义保持不变。
- 同步 `tools/floating-point-precision-scanner` 的 OpenSpec 主 specs、总体设计、shared-bitcode 文档和 roadmap；不修改 frontend 或其他分析工具。
- 在 Linux Docker 中增加正常、边界、异常、旧协议兼容、损坏制品、AST-only、缓存失效和证据预算单元测试，外部服务使用 mock；项目整体及受影响模块行覆盖率、分支覆盖率均至少 90%。
- 修复后通过 `demo-test1` 真实 API 重跑，保留 analysis `aee4ef66-6d81-4e88-afd7-606cc7d6cc9a` 的修复前审计和新的修复后审计，不重写历史结果。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `shared-llvm-bitcode-artifacts`：增加 manifest schema 版本感知的身份校验、项目 TU 分母口径和可审计校验根因要求。
- `floating-point-analysis-runtime`：收紧项目 source facts、canonical scalar conversion、候选级 unknown、long-double 直接证据及 AST/BC 降级状态传播要求。

## Impact

- 后端受影响区域：共享 BC manifest/bundle 模型与校验器、canonical identity、专项分析 capability resolver、输入物化、任务诊断和运行摘要。
- 工具受影响区域：Clang 位置归一化、项目成员判定、canonical type/conversion facts、long-double 与 mixed-precision 规则、unknown/unsupported 聚合、facts 缓存身份及相应 schemas/tests/docs。
- 对外结果继续使用现有 KB Scanner v2 结构，不新增 frontend API；旧分析记录保持不可变。
- source-preserving BC 仍不得冒充 build-faithful IR；FMA、fast-math 等缺少决定性 IR 时继续保守返回 unknown。
