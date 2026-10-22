## Why

分析器已经具备外部 BC 导入、AST/IR 降级、线程入口、按需函数分析、对象来源、并发访问候选以及发布协议风险等独立能力，但生产调用者仍需了解并拼接内部阶段、请求和产物，无法通过稳定入口完成一次项目分析。与此同时，现有报告没有提供类似 KB Scanner v2 的 Finding 自包含证据链和分析时源码上下文，后端和前端无法在不理解内部协议的前提下持久化、查询和展示完整依据。

这是一个运行时实现 change：在保持既有 P1–P4、A1–A6、R1、R1.1、R2、R3 语义不变的前提下，新增统一编排和外部展示投影，不扩展新的内存模型规则。

## What Changes

- 新增一个版本化统一分析请求和公共 CLI：接收外部 LLVM BC bundle、可选源码/profile 输入、Scope 选择、显式入口、策略和预算，一次完成项目级调度。
- 在分析器内部以版本化依赖 DAG 按 Scope 隔离执行既有 ingestion、AST/IR 证据、ExecutionRoot、ThreadEntry、R3、P2/P3、A3–A5、R2、P4 和 A6 适配，确定性生成内部请求、支持缓存、恢复、取消、deadline、失败隔离和候选相关完整性传播。
- 将单个 TU/BC 保持为输入原子，将显式 Scope 保持为正式分析边界；一次项目运行可选择一个或多个 Scope，但不得混合不兼容 target、ABI、profile 或 Scope 形成结论。
- 自动按 TU 形成 `ast-ir`、`ir-only`、`ast-only`、`failed` 模式。BC 生成、导入或 IR 阶段失败时保留可信 AST 事实和源码候选；AST-only 始终为 `partial/unknown`，不得建立运行时 RF/MO/SW/HB、正式风险、受限消解或安全结论。
- 新增统一项目、Scope 和 TU 执行记录以及双语聚合报告，区分 formal finding、source-only candidate、bounded discharge、unsupported、frontier、abstention 和失败分类。
- 新增独立的内存序 Finding 投影，借鉴 KB Scanner `scan-result-v2` 的 `fact`、`conclusion`、`occurrences`、`primaryOccurrenceId` 和 `evidenceChain` 结构，但使用内存序专用枚举、语义和扩展命名空间。
- 每个 Finding 自包含确定性主路径、证据节点、关系、断点、预算、内部产物引用及分析时源码代码窗口；源码不可用、映射不完整或预算截断必须显式标为 `partial/unavailable`，不得伪造位置或代码。
- 报告内嵌有界代码上下文并引用内容寻址源码快照，允许后端逐 Finding 持久化并提供列表、详情和扩大 code-context；完整原始报告和内部产物仍可独立审计。
- 生产入口继续只消费外部 BC，不执行 compiler、linker、configure、build、网络、SSH 或目标程序。
- 更新 CLI、README、架构文档和实现路线图；为全部新增、修改或复用的自有代码增加单元测试，并强制项目整体、实现语言和各受影响模块行/分支覆盖率至少 90%。

## Capabilities

### New Capabilities

- `unified-project-analysis-entry`: 定义外部 bundle 到多 Scope 分析的统一请求、依赖 DAG、调度、AST-only 自动降级、缓存恢复、完整性聚合、退出码和公共入口。
- `memory-order-finding-evidence-projection`: 定义面向后端/前端的 Finding 自包含事实、结论、出现位置、证据链、断点、双语诊断和分析时源码上下文投影。

### Modified Capabilities

无。既有 P1–P4、A1–A6、R1、R1.1、R2、R3、外部 BC 导入和降级源码分析协议保持不变，由新入口通过只读适配器消费。

## Impact

- 影响 `python/memory_order_analyzer` 的 CLI、统一调度、请求/报告契约、缓存与投影模块，以及相应 JSON Schema、固定 fixture、单元和集成测试。
- 新增稳定的后端集成面：后端只需提交 bundle/request、跟踪一次执行并消费统一报告，不再负责编排分析阶段；本 change 不直接修改后端或前端代码。
- 新增面向前端的结构化 Finding 和源码快照产物；完整报告仍为离线审计真相源，Finding 可单独持久化和查询。
- 不新增外部编译、链接、网络、SSH、目标程序执行或新的第三方运行时依赖，也不改变既有语义产物、缓存身份和风险判定。
