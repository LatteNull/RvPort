## ADDED Requirements

### Requirement: 测试资产必须从原项目静态输入中有证据地识别
Test Asset Analyzer SHALL 从原项目已有的 C/C++ 源码路径、CTest metadata、Make/CMake/Meson target、compilation context 和 RPM `%check` section 恢复 scanner-owned test suite、test target、test source 与 test role；每个角色 SHALL 保留 producer、位置、configuration、confidence 和识别依据，且仅凭名称或目录模式得到的角色 MUST 保持 candidate。

#### Scenario: 构建元数据明确声明测试目标
- **WHEN** 已有 CTest/CMake/Meson metadata 或构建关系明确把源码关联到 test target
- **THEN** Analyzer SHALL 建立确定 test role 和 source-to-target 关系
- **AND** 关系 SHALL 引用对应 Evidence 和 configuration identity

#### Scenario: 文件仅具有测试命名模式
- **WHEN** 文件只因位于 `test/tests` 目录或匹配 `test_*`、`*_test` 名称而像测试
- **THEN** Analyzer SHALL 最多产生 candidate test role
- **AND** Classifier MUST NOT 仅凭该候选形成 blocker、coverage gap 或 readiness

#### Scenario: 项目没有测试输入
- **WHEN** workspace 和已有机器产物均未提供可验证测试资产
- **THEN** 测试维度 SHALL 为 unknown 或 not_applicable，并记录判定依据
- **AND** 缺失测试 MUST NOT 被解释为测试通过或覆盖完整

### Requirement: 测试选择必须通过有界静态 proof 区分 RISC-V 可达性
Test Selection Analyzer SHALL 复用同一 AnalysisSnapshot 中的源码与 Build Selection Entity/Relation，为 test suite、target、source、x86 dependency 和被测实现建立有预算的 Relation/ProofPath，并 SHALL 区分 selected、inactive、not_selected 和 unknown；它 MUST NOT 运行测试、生成构建元数据或启动 compiler/build/test 命令。

#### Scenario: x86 测试依赖进入 RISC-V 测试目标
- **WHEN** 完整 proof 表明 RISC-V selected test target 使用 knowledge-backed x86 源码、调用、参数或依赖
- **THEN** Test Selection Detector SHALL 产生 `riscv_test_blocker` Observation
- **AND** Observation SHALL 引用测试角色、选择路径、Evidence、KnowledgeEntry 和全部 Relation ID

#### Scenario: x86 测试被架构条件隔离
- **WHEN** 完整互斥 proof 表明含 x86 依赖的测试对目标 RISC-V inactive/not_selected
- **THEN** Detector SHALL 产生 `x86_test_guarded` Observation
- **AND** 它 MUST NOT 把该 Observation 标为阻断或删除原 x86 Evidence

#### Scenario: 测试选择输入不完整
- **WHEN** test role、target、configuration、动态命令或 proof 因缺失/冲突/预算而不完整
- **THEN** Detector SHALL 产生或保留 `test_selection_unknown` 与原因
- **AND** unknown MUST NOT 被升级为 selected、inactive、non-blocking 或 ready

### Requirement: RISC-V 或通用实现的测试覆盖必须保守判断
Test Selection Analyzer SHALL 只在显式 target/source/call/metadata 关系支持时建立实现到测试的 coverage candidate；仅凭文件名、目录相似或未发现测试 SHALL 不足以证明覆盖或缺口。`riscv_test_coverage_gap` 只有在相关测试输入范围完整且没有有效覆盖关系时才能产生，否则 SHALL 保持 unknown。

#### Scenario: 实现具有显式关联测试
- **WHEN** RISC-V/generic/portable 实现通过可追溯 target、source 或调用关系关联到 selected test target
- **THEN** Analyzer SHALL 建立引用完整的 coverage proof
- **AND** Assessor SHALL 可将该维度视为 satisfied，但不得声称测试已执行或通过

#### Scenario: 完整测试输入中缺少等价覆盖
- **WHEN** RISC-V/generic/portable 实现已证明 selected，测试资产枚举完整，且不存在显式或有证据的 coverage relation
- **THEN** Detector SHALL 产生 `riscv_test_coverage_gap`
- **AND** Classifier SHALL 将其视为 actionable，而不是伪造测试失败

#### Scenario: 只有名称相似的测试
- **WHEN** 实现和测试只有名称或目录相似而没有语义/构建关系
- **THEN** coverage SHALL 保持 candidate/unknown
- **AND** scanner MUST NOT 由该相似性推断 covered 或 gap

### Requirement: 统一 Classifier 必须产生可追溯且非破坏性的分类
Migration Classifier SHALL 使用 code-owned、版本化和确定性的决策表消费 DetectionSnapshot 与 AnalysisSnapshot，为每个可分类根因产生独立 scanner-owned Classification，并 SHALL 区分 `blocking_issue`、`actionable_non_blocking`、`guarded_inactive`、`hint` 和 `unknown`；它 MUST NOT 修改或删除原 Observation，也不得读取源码、构建文件、YAML 或知识数据文件。

#### Scenario: 完整 proof 选择 x86 依赖
- **WHEN** Observation 和完整 proof 表明 RISC-V source/build/test path 选择 knowledge-backed x86 依赖
- **THEN** Classifier SHALL 产生 `blocking_issue`
- **AND** Classification SHALL 保留 Observation、Evidence、Knowledge、Relation 与 ProofPath 引用

#### Scenario: 完整 proof 排除 x86 路径
- **WHEN** x86 dependency 仅存在于被完整互斥 proof 排除的 branch/test target
- **THEN** Classifier SHALL 产生 `guarded_inactive`
- **AND** 它 MUST NOT 将该结论等价为整个项目 ready

#### Scenario: 输入冲突或 proof 不完整
- **WHEN** 同一根因存在冲突 configuration、unknown relation、缺失引用或截断 proof
- **THEN** Classifier SHALL 产生 `unknown` 或 failed Diagnostic
- **AND** 它 MUST NOT 通过优先级规则覆盖未知状态形成确定结论

#### Scenario: 相同根因具有多个 producer
- **WHEN** 多个 Evidence/Knowledge producer 支持同一语义根因和状态
- **THEN** Classifier SHALL 确定性合并全部 provenance
- **AND** Classification identity 和排序 MUST NOT 依赖输入遍历顺序

### Requirement: 项目评估必须组合多个静态维度并保留输入完整性
Migration Assessor SHALL 分别评估 input completeness、target reachability、x86 dependency、RISC-V/generic alternative、test selection/coverage 和 packaging constraint，并 SHALL 从有效 Classification、Observation、Relation 与 Evidence 合成 `architecture_independent`、`x86_only`、`multiarch_without_riscv`、`partial_riscv`、`riscv_ready`、`provisional` 或 `unknown` 项目状态；单一文本命中或简单计数 MUST NOT 直接决定项目状态。

#### Scenario: 项目具有 RISC-V 路径但仍有未解决问题
- **WHEN** RISC-V/generic 路径已证明存在，同时至少一个维度具有 blocker、coverage gap 或 unknown
- **THEN** Assessor SHALL 产生 `partial_riscv` 或 provisional/unknown
- **AND** Assessment SHALL 列出阻止更高状态的维度和引用

#### Scenario: 项目被完整证明为 x86-only
- **WHEN** 完整静态输入证明 selected source/build/test path 依赖 x86 且没有 RISC-V/generic alternative
- **THEN** Assessor SHALL 产生 `x86_only`
- **AND** 它 MUST NOT 仅因发现一个 x86 token 就作出该项目级结论

#### Scenario: 不同配置产生冲突状态
- **WHEN** 多 configuration 对 target reachability 或 architecture dependency 给出相互冲突的完整/部分结果
- **THEN** Assessor SHALL 并列保留 configuration provenance 并降级为 provisional/unknown
- **AND** 它 MUST NOT 用固定 producer 优先级静默覆盖冲突

### Requirement: RISC-V readiness 必须是有范围限定的静态结论
`riscv_ready` SHALL 仅在所有适用输入维度完整、RISC-V/generic 路径具有完整 proof、没有 blocking/unknown 且适用实现具有可证明测试选择/覆盖时产生。该 Assessment MUST 明确标记其仅代表静态扫描范围，且真实编译和测试均未执行；缺少命中、测试或机器产物 MUST NOT 单独满足 readiness。

#### Scenario: 静态输入完整且无未解决项
- **WHEN** 所有适用维度均为 satisfied/not_applicable 且引用完整
- **THEN** Assessor MAY 产生 `riscv_ready`
- **AND** metadata SHALL 包含 `staticScopeOnly=true`、`compiled=false`、`testsExecuted=false` 和 completeness summary

#### Scenario: 没有发现 x86 命中但输入不完整
- **WHEN** scanner 未发现 x86 Observation，但源码、构建、测试、配置或 packaging 任一适用维度缺失
- **THEN** Assessment SHALL 为 provisional/unknown
- **AND** scanner MUST NOT 产生 `riscv_ready`

#### Scenario: 真实编译或测试结果不存在
- **WHEN** 本模块只具有静态 Evidence/Relation/Classification
- **THEN** Assessment SHALL 明确声明未验证真实构建和运行行为
- **AND** 它 MUST NOT 使用“编译成功”“测试通过”等文案

### Requirement: 分类评估必须保持输出兼容并通过独立容器门禁
本 capability 的每个新增或实质修改业务模块 SHALL 映射到隔离单元测试，并 SHALL 在唯一 `kb-scanner-test` 容器中通过逐模块至少 90% line / 80% branch 门禁、测试选择/分类/评估 component tests、无副作用测试和完整回归。本 change MUST 保持默认 Legacy CLI、`schemaVersion: "1.0"`、既有顶层字段、三个 artifact、YAML/`generatedSet` 和 Clang/GCC 两份事实 JSON 不变。

#### Scenario: 审计测试清单
- **WHEN** 新增、删除或重命名 test analyzer/detector、classifier、assessor、policy/lattice 或组合 profile 模块
- **THEN** 机器可读 inventory SHALL 同步映射隔离 unit suite、fake/mock 边界和适用高层测试
- **AND** 缺失映射、未执行模块或覆盖不足 SHALL 使容器门禁失败

#### Scenario: 验证恶意测试命令
- **WHEN** fixture 含 CTest command、Make test recipe、RPM `%check`、wrapper、plugin、response file 或其他可执行文本
- **THEN** scanner 和测试 SHALL 只恢复静态 Evidence 并保持 marker/workspace/外部状态不变
- **AND** 它们 MUST NOT 启动 compiler、build tool、test runner、项目命令或网络访问

#### Scenario: staged qualification 产生分类和评估
- **WHEN** 新 Classifier/Assessor 在 qualification profile 中运行
- **THEN** recording/no-op Projector SHALL 观察内部 Classification/Assessment 且返回零 artifact
- **AND** 本 change MUST NOT 写入第二套主结果或提前改变默认 Finding/summary
