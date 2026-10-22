## Context

阶段 1—6 已建立 scanner-owned core、正式 C/C++ 与 Build Frontend、generated/curated knowledge、Evidence Graph、Build Selection Analyzer 和 Local/Build Detector。staged qualification 能产生可追溯 Observation、Relation 与 ProofPath，但 Classifier 仍只是透传 Observation，Assessor 为空，因而无法回答两个关键问题：原项目测试中的 x86 依赖是否真的进入 RISC-V 测试路径，以及项目在当前静态输入范围内处于什么迁移状态。

本 change 是默认 CLI 切换前的最后一个分析能力阶段。它必须只消费已存在的静态事实和图关系，不运行测试、不编译 RISC-V、不调用构建工具；任何输入缺口都必须成为 completeness/unknown，而不是“没有发现问题”。默认 Legacy CLI、schema 1.0、三个 artifact、YAML/`generatedSet` 和两份 Clang/GCC 编译器事实 JSON 保持不变。分类和评估先在 staged qualification 中验收，阶段 8 才负责兼容投影与默认路径切换。

## Goals / Non-Goals

**Goals:**

- 识别原项目已有的测试源码、目录、target、CTest/RPM check section 和相关构建角色，并区分确定角色与仅凭命名得到的候选角色。
- 建立 test asset → build selection → x86 dependency/implementation 的有界 proof，区分未选中的 x86 测试、进入 RISC-V 路径的 x86 测试和缺少可证明等价覆盖的 RISC-V/portable 实现。
- 使用 scanner-owned、code-owned、确定性分类策略，把 Observation 分类为 blocking、actionable non-blocking、guarded/inactive、hint 或 unknown。
- 产生多维 Assessment 和审慎的项目状态，显式携带输入完整性、静态范围限定、未知项和支持结论的引用。
- 为所有新增/修改业务模块提供隔离 unit mapping、fake/mock 边界和逐模块 90% line / 80% branch 容器门禁。

**Non-Goals:**

- 不生成测试、不修改测试、不运行项目测试，也不把测试文件存在等同于测试通过。
- 不进行真实 RISC-V 编译、链接、运行或性能验证；不复刻 `memory-model-ir-checker` 的 RVWMO 分析。
- 不按文件名相似度猜测实现与测试的等价覆盖，不把缺少 x86 命中直接解释为 `riscv_ready`。
- 不修改 Legacy parser/evaluator 来适配新管线，不在本阶段切换默认 CLI 或实现最终兼容 Report Projector。
- 不分析 OS、内核、系统调用、驱动和板级迁移。

## Decisions

### 1. 测试识别分为角色证据和选择证据

新增 scanner-owned test role vocabulary 和 `TestAssetAnalyzer`。测试角色来源按证据强度分层：已有 CTest metadata、Make/CMake/Meson test target、RPM `%check`、显式 source-to-target 关系属于确定角色；`tests/`、`test_*.c`、`*_test.cpp` 等路径/名称只产生 candidate role。每个 test asset 保留 producer、SourceSpan/JSON pointer、target/configuration 和 confidence。

不采用“扫描到 test 名称就视为真实测试”的方案，因为示例、benchmark 和生产工具经常使用相同命名。Classifier 只有在角色和目标选择都有完整 proof 时才能产生确定测试结论；candidate role 传播 unknown。

### 2. Test Selection Analyzer 扩展同一 Evidence Graph

`TestSelectionAnalyzer` 复用阶段 6 的 build/source Entity、Relation 与 ProofPath，在同一 scanner-owned AnalysisSnapshot 中增加 test suite、test target、test source 和 coverage candidate Entity，以及 `contains_test`、`selects_test`、`exercises`、`covers_candidate` 和 `alternative_test_for` Relation。它只消费已归一化 Fact 和已有关系，不重读源码或构建文件。

测试进入 RISC-V 路径必须由 selected build/test proof 支持；inactive/not_selected proof 表示测试被隔离；缺少 target、动态命令、candidate role、冲突 configuration 或预算截断一律 unknown。实现到测试的 `covers_candidate` 只有在显式 target/source/调用/metadata 关联存在时建立，名称相似最多作为低置信候选，不能证明覆盖。

不建立第二套测试图或引入测试框架运行时。GraphStore 仍只存储关系，不决定 active、blocking 或 readiness。

### 3. 测试 Observation 保持事实层，Classifier 单独产生分类对象

新增 `TestSelectionDetector` 产生四类非最终 Observation：

- `x86_test_guarded`：x86 测试依赖存在，但完整 proof 表明测试对 RISC-V inactive/not_selected；
- `riscv_test_blocker`：完整 proof 表明 RISC-V test target 选择了 knowledge-backed x86 源码、参数、调用或依赖；
- `riscv_test_coverage_gap`：RISC-V/portable 实现已证明进入目标构建，但在完整测试输入中没有可证明的关联测试；
- `test_selection_unknown`：测试角色、选择或覆盖 proof 不完整。

Classifier 不改写或删除 Observation。core 新增稳定 `Classification`，引用 observation/evidence/knowledge/relation/proof，包含 impact class、reason code、confidence 和非报告级建议元数据；`ClassificationSnapshot` 以向后兼容的默认空 tuple 承载它，同时保留现有 `observations` 字段以兼容 recording tests。

### 4. 分类使用显式决策表和“未知优先”原则

统一 `MigrationClassifier` 使用 code-owned decision table，而不是 YAML severity/blocking 或散落 if/else。优先级为：引用不完整/冲突/unknown → `unknown`；完整 RISC-V selected x86 dependency 或 `riscv_test_blocker` → `blocking_issue`；明确迁移缺口但非当前 selected blocker → `actionable_non_blocking`；完整 inactive/not_selected x86 路径或 `x86_test_guarded` → `guarded_inactive`；comment-only → `hint`。同一根因的多 producer Observation 合并全部 provenance，但不同配置/状态不相互覆盖。

没有完整 proof 的 selected/inactive 结论不得进入确定分类。Classifier 验证所有引用均存在，不自行查知识文件、源码或构建输入，也不产生项目状态。

### 5. Assessor 先形成维度，再按保守格合成项目状态

`MigrationAssessor` 产生至少六个维度：input completeness、target reachability、x86 dependency、RISC-V/generic alternative、test selection/coverage、packaging constraint。每个维度为 satisfied、issue、unknown 或 not_applicable，并引用支持它的 Classification/Observation/Relation/Evidence。

聚合状态采用保守格，而非分数平均：

- `architecture_independent`：输入完整且没有架构专属事实；
- `x86_only`：完整 proof 表明所选实现/构建/测试依赖 x86，且没有 RISC-V 或通用替代路径；
- `multiarch_without_riscv`：存在多个可证明架构路径但没有 RISC-V/generic 目标路径；
- `partial_riscv`：存在 RISC-V/generic 路径，同时仍有 blocker、coverage gap 或未完成迁移维度；
- `riscv_ready`：所有适用输入维度完整、RISC-V/generic 路径可证明、没有 blocker/unknown，且适用实现具有可证明测试选择/覆盖；
- `provisional`/`unknown`：输入、关系、测试或分类不完整，无法安全进入以上确定状态。

`riscv_ready` metadata 必须写明 `staticScopeOnly=true`、`compiled=false`、`testsExecuted=false` 和 completeness summary。真实编译/测试结果未来可作为外部阶段输入，但不是本模块当前结论的替代品。

### 6. staged qualification 接入真实分类评估但不投影报告

qualification profile 替换 recording Classifier 和 empty Assessor，接入 Composite Analyzer/Detector、`MigrationClassifier` 与 `MigrationAssessor`，Projector 仍为 recording/no-op 并保证零 artifact。Pipeline 阶段顺序和对象身份不变；partial/unknown Diagnostic 继续向下游传播。

本阶段不修改 `scan-result.json`。阶段 8 的兼容 Projector 将把 Classification 映射到既有 Finding 的 rule/category、severity、blocking、reason、suggestion、trace，把项目 Assessment 映射到可选的 `summary.readiness`；顶层结构、schemaVersion 1.0 和三个 artifact 不变。现在先用 projection contract fixture 固化该映射意图，但不发布第二套结果。

### 7. 现有知识事实通过 Observation 引用继续复用

Classifier 和 Assessor 不直接加载 `clang-x86-entries.json` 或 `gcc-x86-entries.json`；它们沿 Observation 的 KnowledgeEntry ID 使用现有 KnowledgeSnapshot，从而完整保留两份 source provenance、六类事实和 curated/generated 来源。任何缺失 knowledge reference 都是 failed contract，不允许内置未经审校的替代词表。

### 8. 所有业务模块必须有隔离单元测试映射

新增 `tests/classification-assessment-test-inventory.json`，逐项覆盖 test role vocabulary、test analyzer/detector、classification model/policy、assessor/lattice、组合 profile 等业务模块。单元测试使用内存 snapshot、fake GraphStore/上下游 stage、拒绝型 process/runner 和临时只读文件系统；真实 parser、真实 AVX/测试项目、staged integration、Legacy/output compatibility 只属于更高层测试，不计入 unit 覆盖。

唯一 `kb-scanner-test` 容器独立运行本 change 的 unit coverage，逐模块至少 90% line / 80% branch，然后依次运行 frontend、knowledge/detection、evidence graph、build selection 和 full regression。恶意 fixture 用 marker 断言 Make/CMake/Meson/CTest/RPM/compiler/测试命令均未执行；宿主机和生产镜像不安装依赖。

## Risks / Trade-offs

- [Risk] 路径命名可能把示例或 benchmark 误认成测试。 → 路径规则只产生 candidate；确定分类需要 build/CTest/RPM role 与 selection proof。
- [Risk] “缺少等价测试”很难由静态证据完全证明。 → 只有输入完整且显式关系闭合时产生 coverage gap，否则保持 unknown；不使用名称相似度作为充分证据。
- [Risk] 分类优先级可能掩盖并存状态。 → 保留原 Observation，并按根因/配置分别分类；聚合只做确定性展示顺序，不覆盖 provenance。
- [Risk] `riscv_ready` 被误解为实际可构建。 → 要求完整性门槛和强制 scope metadata，文档与未来投影均显示未编译、未执行测试。
- [Risk] 测试/关系组合导致图和 proof 数量增长。 → 对测试资产、关系、路径深度、visited 和 path count 设置独立预算，截断时保留已有证据并降级 unknown。
- [Risk] 新内部 Classification/Assessment 诱发提前输出结构变化。 → 本阶段 Projector 继续 no-op；schema 1.0 兼容由合同测试锁定，正式映射留给阶段 8。

## Migration Plan

1. 固化测试角色、测试选择、分类和项目状态的人工行为矩阵与正反 fixture，明确 complete/unknown 边界。
2. 扩展 scanner-owned core Classification/Assessment 合同和 test relation vocabulary，保持默认空字段兼容。
3. 实现 TestAsset/TestSelection Analyzer 与 Detector，逐层验证 Entity/Evidence/Relation/ProofPath 引用。
4. 实现 MigrationClassifier 决策表和 MigrationAssessor 保守格，加入确定性、冲突与输入完整性测试。
5. 接入 staged qualification，运行独立 unit coverage、安全、测试项目、AVX/build、Legacy/output 和完整回归。
6. 保持默认 Legacy CLI；若 qualification 失败，可移除新 profile 接线而不迁移或回滚现有报告数据。

## Open Questions

- 哪些 CTest/CMake/Meson target 属性足以把路径候选提升为确定 test role？默认只接受显式 test metadata 或已验证构建关系。
- 对没有显式实现—测试映射的传统 C 项目，coverage gap 应保持 unknown 还是允许“完整枚举但无关系”成为 gap？默认保持 unknown，避免名称启发式造成误报。
- `architecture_independent` 与 `riscv_ready` 的展示优先级如何投影到阶段 8 的 `summary.readiness`？本阶段分别保留内部状态，投影时再固定兼容文案。
