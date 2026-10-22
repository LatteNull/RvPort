## Why

当前浮点精度分析和强弱内存序分析把可用 LLVM BC 当作任务创建的硬前置条件，导致 BC 副产物生成失败时，即使源码和真实 `compile_commands.json` 已就绪，也无法执行工具已经具备的 AST-only 分析；`PARTIAL` BC 场景还会遗漏未生成 BC 的翻译单元。与此同时，共享 BC 协议、生产脚本和内存序分析器只接受 C11、C17、C++17、C++20，并会把 C89/C99 等真实标准错误改写为较新标准，造成旧代码无法分析或分析语义失真。

## What Changes

- 将 LLVM BC 从专项分析的硬前置条件改为可选增强证据：源码、成功的 x86 构建和真实 `compile_commands.json` 就绪后即可启动分析。
- 根据 BC 可用性明确选择 `AST_ONLY`、`AST_BC_MIXED` 或 `AST_BC_COMPLETE`；`READY` 使用完整 AST+BC，`PARTIAL` 对有 BC 的翻译单元使用 AST+BC、其余翻译单元回退 AST-only，无可用 BC 时执行纯 AST 分析。
- 调整专项分析 readiness、创建校验、任务输入、运行记录和 API 响应，返回分析模式、BC 状态、覆盖分母及降级原因；BC 缺失或损坏不得被伪装为完整分析。
- 使浮点和内存序适配器从完整 `compile_commands.json` 规划 AST 输入，不再只保留成功生成 BC 的翻译单元；内存序分析在无 BC 时仍生成可信 source request。
- 扩展共享 BC 协议和生产逻辑，保留每个翻译单元真实的 C/C++ 语言标准及 GNU/ISO 方言，不再把旧标准静默改写为 C17 或 C++17。
- 扩展专项分析对 C89/C90、C99、C11、C17/C18、C++98/C++03 及现有较新标准和常见 GNU 别名的支持；没有显式 `-std` 时记录编译器默认语义，不伪造标准版本。
- 对工具无法可靠支持的单个编译上下文返回可审计的 `unknown`、`unsupported` 或部分结果，不因一个翻译单元阻断整个项目；规则按语言能力适用，不把 AST-only 候选提升为已证明的运行时风险。
- 为正常流程、异常流程和边界条件补充单元测试，并对后端、浮点扫描器和内存序分析器执行覆盖全部项目自有生产源码的行/分支覆盖率门禁；未被测试加载的生产源码按 0 命中计入分母，测试代码和 fixture 不进入分母，项目整体及受影响模块均不低于 90%。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `floating-point-analysis-runtime`: 浮点分析允许 AST-only 和按翻译单元混合 AST+BC，并公开实际证据模式及降级信息。
- `memory-order-analysis-runtime`: 内存序统一入口允许无 BC 的 AST-only 分析，并保留候选、证据断点和不确定性语义。
- `shared-llvm-bitcode-artifacts`: 共享 BC 协议保留真实语言标准，允许消费者在 BC 缺失、失败或部分可用时安全降级。
- `backend-api-design`: 专项分析 readiness、创建和查询 API 不再将 BC 作为硬门槛，并返回分析模式、BC 覆盖和降级原因。

## Impact

- 后端：专项分析 readiness、创建服务、任务输入、运行时 materializer/adapter、运行记录 schema、响应 DTO、共享 BC schema 与生产脚本。
- 工具：`tools/floating-point-precision-scanner` 的旧标准验证和 AST/BC 混合覆盖；`tools/memory-order-analyzer` 的语言标准合同、source profile、统一请求及 AST-only 执行。
- 数据：`specialized_analysis_runs.artifact_set_id` 需要允许为空，并需要持久化或可稳定投影分析模式、BC 状态与覆盖统计。
- 兼容性：已有完整 BC 任务继续按 AST+BC 运行；旧任务保持可查询。新增字段为向后兼容扩展，但共享 BC schema 和工具输入协议需要版本化演进，禁止无版本地改变既有 v2 语义。
