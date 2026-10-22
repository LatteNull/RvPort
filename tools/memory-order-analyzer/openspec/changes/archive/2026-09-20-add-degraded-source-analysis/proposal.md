## Why

当前分析器在 TU 无法生成 BC、IR 后续阶段失败或相关同步无法解释时，尚缺少统一、可审计的证据可用性与降级协议；实测还发现未知 RAII mutex 被当成“没有同步”而产生误报。现在需要先建立 C 与 C++ 并列的 AST-only 兜底和保守完整性边界，避免单个 TU 失败清空全 scope，也避免低等级源码证据被提升为内存模型证明。

## What Changes

- 这是运行时实现 change：新增独立、版本化的降级分析请求、TU 证据可用性、源码候选和报告协议，统一表达 AST+IR、IR-only、AST-only、failed 四种模式。
- AST 源事实成为每个计划 TU 的独立事实层；BC 或后续 IR 阶段失败时保留可用 AST 实体、跨 TU 关系、控制事实和 source candidate，而不是把整个 scope 视为无结果。
- 对 frontend-invalid、profile-replay-incompatible、IR-generation-failed、worker-budget、artifact-validation-failed 等失败进行稳定分类；缺失头文件、宏、生成物、语法或类型错误导致 AST 也不可信时保持 failed。
- AST-only 结果严格为 partial/unknown/source candidate，不得输出 P4 同等级 risk/discharged，不得单独生成或提升 sequenced-before、reads-from、synchronizes-with、happens-before 或安全结论；IR-only 保持现有语义边界。
- 修复候选相关完整性：`mutex-kind-unknown`、未知 RAII、未知同步 wrapper 和相关预算缺口不得解释成同步不存在，必须阻止受影响候选产生确定 finding 或 discharge；无关 TU 缺口不阻止独立候选继续分析。
- 编译器限定 GCC/Clang，语言矩阵并列覆盖 C11、C17、C++17、C++20；排除 Windows、MSVC、clang-cl。C 路径独立覆盖 pthread、C linkage、全局/struct/union、宏、`_Atomic` 与 `<stdatomic.h>`，不得依赖 C++ AST 或标准库模型。
- 新增中英文字段、预算、缓存、确定性与退出语义；AST-only 可用结果沿用 partial/unknown 类退出，不与风险退出码混淆。
- 纳入归档 samples 的 `safe/03_pthread_mutex.cpp` 误报回归并增加等价 C pthread mutex 正反例；分别报告四种语言 profile 的计划/完成、TP/FP/FN 和 abstention。
- 暂不实现 `std::thread`、完整 RAII mutex 语义、通用指针分析、fence、RMW/CAS、通用 happens-before、Windows API 或线程池。
- 所有新增、修改或复用的自有代码同步提供正常、边界、异常和 unknown 单元测试；项目整体、实现语言及每个受影响模块的行/分支覆盖率均至少 90%。

## Capabilities

### New Capabilities

- `degraded-source-analysis`: 定义按 TU 的 AST/IR 可用性、失败分类、四种分析模式、AST-only source candidate、候选相关降级、版本化请求/报告、缓存、预算和退出语义。

### Modified Capabilities

- `gcc-clang-compilation-context`: 将 AST 与 BC 作为同一编译 profile 下可独立完成的计划产物，并分类保存 C/C++ 前端、IR 生成及依赖失败。
- `clang-source-semantic-facts`: 明确 C11/C17 与 C++17/C++20 的独立源语义、错误恢复可信边界，以及 BC 不可用时 SourceSemanticFacts 的可保留条件。
- `ast-assisted-analysis-reporting`: 增加 AST+IR、IR-only、AST-only、failed 分层分母、证据缺失、中英文诊断、缓存与退出状态。
- `thread-order-and-synchronization`: 将相关未知 mutex、RAII、同步 wrapper 和预算缺口作为未解释同步传播，不得当作已证明无同步。
- `single-publication-protocol-modeling`: 以候选依赖切片阻止 AST-only 或未知同步产生确定 finding/discharge，同时保留无关 TU 候选。
- `publication-risk-reporting`: 分离正式 P4 assessment 与 source-only candidate，保持风险和 partial/unknown 退出码边界。
- `analysis-validation-corpus`: 增加四语言降级矩阵、C pthread mutex 对照及归档 sample 误报回归，且不把 Windows 或无效源码计入准确率。
- `analysis-validation-reporting`: 分模式、分语言报告完整性、TP/FP/FN、strict 指标、abstention、性能和缓存，不以合并指标掩盖单语言缺口。
- `analyzer-unit-test-quality`: 将降级协议、失败分类、保守同步传播和各语言 fixture 纳入离线单元/集成及整体、语言、逐模块 90% 行/分支门禁。

## Impact

主要影响 compile-only/source indexing 编排、SourceSemanticFacts 消费、P3 mutex/synchronization 完整性、P4 候选与报告、validation runner、CLI/schema/cache、双语诊断、固定 C/C++ fixture 和质量入口。P1 `ModuleFacts/RunReport v2`、P2 `EffectSummary v1`、P3/P4 既有原始协议保持可读且默认行为兼容；新增依赖通过独立协议或 additive wrapper 显式引用。无新增在线服务或 SSH 依赖，不运行被分析程序，不修改生产 Dockerfile，不依赖归档 sibling checker 的实现代码。
