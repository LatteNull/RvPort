## Why

当前生产入口仍由分析器重放 `compile_commands.json`、执行依赖发现并调用 Clang 生成 BC，这与实际部署中“x86 构建系统已经产出 BC、分析器只消费产物”的职责边界不一致，也让纯 BC 分析不必要地依赖编译器、SDK 和 `llvm-link`。本 change 将输入面改为显式、可校验的外部 BC bundle，在不改变 P1–A6、R1–R3 分析语义的前提下，把构建完整性和分析完整性分开。

这是运行时实现、协议、CLI、测试和文档变更，不是纯文档 change。

## What Changes

- 新增版本化 `ExternalBitcodeBundleManifest`、`ExternalBitcodeArtifactRecord` 和双语 `ExternalBitcodeIngestionReport`，以显式 planned TU/artifact 分母、producer、LLVM/Clang 版本、target/DataLayout/ABI、语言 profile、源码/编译记录摘要、scope 成员及上游失败描述外部输入。
- 新增 `ingest-bc-bundle` 生产入口：只做路径边界、内容稳定性、SHA-256、raw LLVM bitcode 格式、parse/verify、reader 兼容性、身份、target/profile/scope 和 lineage 校验，再把通过校验的 BC 发布到内容寻址 artifact store，并生成既有 `BCArtifact` 与 `ModuleFacts v2`。
- **BREAKING**：生产 CLI 不再提供 `collect` 和 `link`，也不再执行依赖发现、Clang `-emit-llvm`、compile-only 编译或 `llvm-link`；跨 TU 继续使用显式 scope 和 `ScopeIndex`。
- 保留 `import-bc` 作为单文件、低完整性兼容入口，但它不能提供 bundle 或 scope 完整性；无外部 provenance 时必须维持 unknown/partial。
- `compile_commands.json` 仅作为可选 AST `CompilationProfileIdentity`、SourceIRBinding 和外部 record 对齐证据，禁止触发 BC 生成，也不得推断完整 target/link scope。
- 拆分环境检查：纯 BC ingestion 只要求 LLVM reader/worker 和协议匹配；AST 路径单独检查 source worker。生产分析不得要求 GCC/Clang driver、`llvm-link`、configure/build、网络、SSH 或执行目标程序。
- 明确 x86 host 与 BC target 的区别，拒绝 GCC LTO/GIMPLE、ELF 内嵌 bitcode、不可读/不兼容 BC、未声明 linked/LTO 输入和目录猜测；x86_64 target 证据不得声明覆盖 ARM/RISC-V 配置。
- 更新 README、BC 流水线、构建上下文、架构和路线图；测试 fixture 可在分析器外预生成 BC，但需验证生产分析进程不执行编译或链接工具。
- 为全部新增、修改和复用的自有代码补齐单元测试，并要求项目整体、Python、C++ 及每个受影响模块行覆盖率和分支覆盖率均至少 90%。

## Capabilities

### New Capabilities

- `external-bitcode-ingestion`: 定义外部 BC bundle 协议、批量导入、内容与 provenance 校验、完整性分母、artifact-store 发布、CLI、缓存和双语报告。

### Modified Capabilities

- `gcc-clang-compilation-context`: 将编译数据库职责收缩为可选 AST/profile 与外部 BC 对齐，不再由分析器适配命令并生成 BC。
- `bc-build-context-documentation`: 将 BC 生成说明改为外部构建责任，补充 bundle、逐 TU raw BC、x86 host/target 和优化证据边界。
- `analysis-integrity-reporting`: 用 ingestion 完整性替代 analyzer-side generation 计数，删除 collect/link 生产语义并保持下游事实和风险报告不变。
- `degraded-source-analysis`: 将 IR generation failure 重新解释为外部 artifact 缺失、无效或不兼容，同时保留 AST-only 保守边界。
- `analyzer-development-container`: 将生产运行时 readiness 与 fixture/开发编译工具分离，更新离线 ingestion/index 冒烟验收。
- `analyzer-unit-test-quality`: 增加外部 BC ingestion、禁止执行边界、兼容适配和逐模块双 90% required gate。

## Impact

- 主要影响 `python/memory_order_analyzer/cli.py`、`pipeline.py`、`context.py`、`toolchain.py`、`report.py`、`scope.py`、基础 contracts/schema、相关测试和文档。
- `collect`/`link` 的调用方必须改为由外部构建生产 bundle，再调用 `ingest-bc-bundle`；这是有意的生产 CLI 破坏性变更。
- P1 `ModuleFacts v2`、`RunReport v2`、P2–P4、A1–A6、R1/R1.1、R2、R3 的现有协议、缓存身份和报告语义保持不变；新增 ingestion sidecar 负责适配到既有 artifact store。
- 开发镜像仍可包含编译测试 fixture 所需的 Clang/LLVM，但生产 ingestion 路径不得调用它们；生产 Dockerfile 整合仍留给独立 change。
