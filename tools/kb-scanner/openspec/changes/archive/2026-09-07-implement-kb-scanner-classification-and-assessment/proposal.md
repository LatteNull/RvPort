## Why

阶段 1—6 已能恢复 C/C++ 局部事实、知识命中、源码关系和构建选择，但当前输出仍停留在非最终 Observation：它不能区分“只存在于未选择的 x86 测试”与“会进入 RISC-V 测试路径的阻断依赖”，也不能基于输入完整性给出审慎的项目级静态迁移状态。现在需要用统一 Classifier、测试选择分析和 Assessor 消费已有 Evidence/Relation/ProofPath，形成可解释、可审计但仍不替代真实编译与测试的结论。

## What Changes

- 新增静态测试资产与测试选择分析，识别原项目中的测试源码、目录、构建 target/section 和测试依赖，并复用现有源码及 Build Selection 关系判断它们是否进入目标 RISC-V 测试路径。
- 对测试中的 x86 依赖区分 `x86_test_guarded`、`riscv_test_blocker`、`riscv_test_coverage_gap` 和 unknown；缺少测试映射或不完整 proof 时不猜测覆盖关系。
- 实现 code-owned 统一 Classifier，把已有局部与构建 Observation 分类为 blocking issue、actionable non-blocking issue、guarded/inactive、hint 或 unknown，每个确定结论必须引用有效 Evidence/Knowledge/Relation/ProofPath。
- 实现项目级多维 Assessor，组合源码可达性、构建选择、架构依赖、替代实现、测试覆盖和输入完整性，产生 `architecture_independent`、`x86_only`、`multiarch_without_riscv`、`partial_riscv`、`riscv_ready` 或 provisional/unknown 状态。
- `riscv_ready` 只表示当前静态输入范围内没有未解决阻断证据，并明确保留输入范围、unknown/deferred 和“未进行真实编译/测试”的限定；不得由“未发现命中”直接推导。
- staged qualification 接入真实 Test Selection Analyzer、Classifier 和 Assessor；默认 CLI 与兼容 Projector 仍留在 Legacy 路径，阶段 8 前不切换正式报告。
- 为每个新增或实质修改的测试选择、分类、评估和组合业务模块建立隔离单元测试清单，在独立 `kb-scanner-test` 容器内执行逐模块至少 90% line / 80% branch 门禁、无副作用测试和完整回归。
- 保持 `scan-result.json` schema 1.0、既有顶层字段、三个 artifact、YAML/`generatedSet` 以及 Clang/GCC 两份事实 JSON 原样兼容；不引入第二套主结果结构。
- 继续只处理 C/C++ 软件、汇编、构建、RPM 和项目测试的静态迁移问题，排除操作系统、内核、系统调用、驱动和板级迁移。

## Capabilities

### New Capabilities

- `kb-scanner-classification-and-assessment`: 定义静态测试选择、统一 Finding 分类、项目级迁移评估、输入完整性和 readiness 限定合同。

### Modified Capabilities

- `kb-scanner-core-pipeline`: staged qualification 从 Detection 继续运行真实 Classifier/Assessor，同时保持默认 Legacy CLI 和 recording/no-op 兼容 Projector。
- `kb-scanner-build-selection-analysis`: 扩展现有 build graph 以表达测试 target/source/section 的静态选择，并为测试分类提供可追溯 proof。
- `kb-scanner-evidence-graph`: 增加测试资产、测试覆盖候选和实现到测试的有界关系，同时继续只存储 scanner-owned 静态关系。
- `kb-scanner-knowledge-and-local-detection`: 更新行为验收与 deferred 边界，使已实现的 build/test/classification 能力被消费，而未知输入仍不得升级为安全结论。

## Impact

- 主要影响 `kb_scanner/analyzers/`、`kb_scanner/classifiers/`、`kb_scanner/assessors/`、pipeline 组合/profile、测试角色词汇及 scanner-owned core snapshot/assessment 类型；不会修改 Legacy parser/evaluator 来迁就新管线。
- 新分析只消费已存在的源码、构建 Evidence、Knowledge、Relation 和 ProofPath，不执行项目测试、真实 RISC-V 编译、CMake/Meson/Make/RPM 命令或网络访问。
- 新增人工 test-selection/assessment oracle、恶意测试命令 fixture、逐模块 unit inventory、component/staged/compatibility 回归；所有依赖与执行仅进入独立测试容器，不污染宿主机、生产镜像或根 Compose。
- 本 change 的结果保持 scanner 内部或由 recording downstream 验证；将 Classification/Assessment 投影到既有 Finding/summary 的兼容切换属于阶段 8。
