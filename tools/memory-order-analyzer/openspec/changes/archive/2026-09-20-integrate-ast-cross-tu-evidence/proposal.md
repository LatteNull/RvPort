## Why

P5 离线真值结果显示 `8/8` abstention、strict FN=7，主要原因不是缺少更多风险规则，而是当前分析无法稳定把源码声明、跨 TU 实体、LLVM 全局对象和调用点组成同一条可审计证明链。仅靠 `compile_commands.json` 与 BC 中的局部身份不足以处理跨 TU 声明/定义、内部链接、C++ mangling/ODR 和缺失 debug 映射，因此需要引入受限的 Clang AST 语义层，并与现有 IR 事实互补而非替代。

## What Changes

- 这是 runtime implementation change：新增基于锁定 Clang/LibTooling 的逐 TU 源语义提取器，复用与 BC 生成一致的编译记录、宏、include、语言标准、target 和路径映射；GCC 编译记录只在 Clang 兼容重放成功时进入 AST 分析，失败必须显式保留。
- 新增独立、严格版本化的 `SourceSemanticFacts v1`、`ProgramEntityIndex v1`、`SourceIRBinding v1`、请求和报告产物，不原地改写 P1 `ModuleFacts/RunReport v2`、P2 `EffectSummary v1`、P3 `ThreadContextGraph v1`、P4 风险报告及 P5 真值/验证报告的既有语义。
- 使用 USR、语言/编译 profile、linkage、规范类型、mangled name、定义身份和 TU 身份建立跨 TU 实体索引；内部链接、匿名 namespace、C tentative definition、C++ inline/template/ODR、weak/COMDAT/TLS 等必须按明确规则解析为唯一、歧义或未解析，禁止按名称直接合并。
- 建立 AST 实体/表达式与 LLVM function/global/instruction 的证据绑定，允许一对多、多对一和候选映射；debug/source range 只作为证据之一，所有绑定均保留 exact/candidate/ambiguous/unresolved、置信依据、依赖和完整性。
- 以独立 canonical-object overlay 向现有 P2–P4 提供可选源语义证据，优先修复跨 TU flag/payload、直接 wrapper、pthread callback/handle provenance 和候选相关完整性；AST 不得被用来证明实际 IR memory order、sequenced-before、reads-from、synchronizes-with 或 happens-before。
- 扩展 P5 固定真值集与分层指标，量化 AST+IR 模式对跨 TU exact match、strict recall、abstention、绑定完整性、性能和缓存的影响；不修改既有 truth 来迎合输出，也不把结果表述为全程序安全证明。
- 所有面向用户的新增诊断、原因和建议同时提供中文与英文字段；新增、修改或复用的自有 C++/Python 代码同步提供正常、边界、异常和 unknown/partial 单元测试，项目整体、各语言及每个受影响模块的行覆盖率和分支覆盖率均至少 90%。
- 首版不实现 CMake target/link 图导入、通用指针分析、`std::thread`/RAII、fence/RMW/release-sequence 语义、通用 data-race 检测、巨型合并 AST 或将 Clang Static Analyzer 作为核心分析器；这些边界进入 unknown/frontier。
- 2026-09-20 验收后审计发现，`c11-risk-multi` 与 `cpp20-risk-multi` 这两个本 change 明确应支持的直接 pthread 跨 TU 样本仍返回 unknown。本 change 因此重新打开：修复 overlay target 重复、源声明/唯一 LLVM 定义的集合级绑定、系统外部实体边界、候选相关完整性和零协议候选诊断；不把这两个 FN 误归类为 fence/RMW 或通用指针分析边界。

## Capabilities

### New Capabilities

- `clang-source-semantic-facts`: 定义逐 TU Clang AST 提取、编译上下文一致性、源实体/引用/控制语义和失败完整性。
- `cross-tu-program-entity-index`: 定义 USR/linkage/ABI/profile 驱动的跨 TU 实体解析、定义选择、歧义处理和 canonical object identity。
- `source-ir-evidence-binding`: 定义 AST 与 LLVM function/global/instruction 的版本化绑定、证据等级、映射基数和完整性边界。
- `ast-assisted-analysis-reporting`: 定义 AST 辅助分析请求、独立补充产物、CLI、缓存、预算、双语诊断和分层报告。

### Modified Capabilities

- `scoped-module-association`: 在显式 scope 内可选消费 canonical entity/object overlay，同时保持 compilation database 不是 target/link 图的边界。
- `thread-context-modeling`: 允许使用已验证的 AST 实体和调用证据补充直接 pthread callback 与受限 handle provenance，不提升为通用线程模型。
- `single-publication-protocol-modeling`: 允许用 AST–IR 绑定统一跨 TU flag/payload 与 wrapper 证据，并按候选相关依赖传播 unknown，而非用全请求缺口一律清空候选。
- `analysis-validation-corpus`: 增加 AST+IR 单/跨 TU、linkage/ABI、宏/profile、debug/no-debug、歧义和不可解析的人工真值矩阵。
- `analysis-validation-reporting`: 增加源事实、实体解析和 AST–IR 绑定层的精确分母及与既有 P4/P5 指标的隔离比较。
- `analyzer-unit-test-quality`: 把新增 C++ 提取器、Python 索引/绑定/编排及所有受影响模块纳入整体、语言和逐模块行/分支覆盖率至少 90% 的离线门禁。
- `memory-order-evidence-documentation`: 记录 AST 与 IR 的权威边界、跨 TU 证据链、已知限制、复现命令和实际验证结果。

## Impact

- 影响 `src/`、`include/`、`python/`、CLI、schemas、缓存/产物存储、`Dockerfile.dev`、CMake、测试语料、覆盖率门禁和 `doc/`；生产 Dockerfile 合并仍由后续独立 change 处理。
- 新增锁定版本的 Clang/LLVM LibTooling 构建依赖；不依赖 SSH、ARM DevKit、GenMC 或 herdtools7，日常验收保持离线。
- 默认旧命令和既有 P1–P5 产物继续可读；AST 辅助路径必须显式启用或通过新请求进入，任何协议升级均采用新版本并保留旧版本读取/验证。
- 主要兼容风险是 GCC 扩展无法由锁定 Clang 等价解析、不同 LLVM/Clang ABI、C++ ODR/weak/COMDAT 歧义和缺失 debug 映射；这些情况必须报告 partial/unknown，不能静默降级为精确关联。
- 修复不放宽语义门槛：只对完全相同的 artifact-local target 去重，且只在 resolved source entity、唯一 distinct LLVM definition、相容声明和无冲突证据时建立 exact overlay；任何真实多定义、ABI/profile/linkage 冲突仍保持 ambiguous/conflict。
