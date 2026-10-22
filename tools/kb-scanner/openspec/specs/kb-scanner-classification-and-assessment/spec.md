# KB Scanner Classification and Assessment Specification

## Purpose

定义 KB Scanner 在纯静态分析边界内识别测试资产、判断测试选择与覆盖，并基于可追溯证据完成迁移问题分类和项目级 RISC-V 适配评估，同时保持现有输出兼容。

## Requirements

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
本 capability 的每个新增或实质修改业务模块 SHALL 映射到隔离单元测试，并 SHALL 在唯一 `kb-scanner-test` 容器中通过逐模块至少 90% line / 80% branch 门禁、测试选择/分类/评估 component tests、无副作用测试和完整回归。Default staged profile SHALL 把 Classification/Assessment 交给正式 Compatible Report Projector，并 SHALL 保持 `schemaVersion: "1.0"`、既有顶层字段、三个 artifact、Finding/summary 兼容语义及 Clang/GCC 两份事实 JSON 不变；Legacy YAML/`generatedSet` SHALL 只作为冻结 oracle 资产而不得被新分类、评估或投影读取。

#### Scenario: 审计测试清单
- **WHEN** 新增、删除或重命名 test analyzer/detector、classifier、assessor、policy/lattice、projection 或组合 profile 模块
- **THEN** 机器可读 inventory SHALL 同步映射隔离 unit suite、fake/mock 边界和适用高层测试
- **AND** 缺失映射、未执行模块或覆盖不足 SHALL 使容器门禁失败

#### Scenario: 验证恶意测试命令
- **WHEN** fixture 含 CTest command、Make test recipe、RPM `%check`、wrapper、plugin、response file 或其他可执行文本
- **THEN** scanner 和测试 SHALL 只恢复静态 Evidence 并保持 marker/workspace/外部状态不变
- **AND** 它们 MUST NOT 启动 compiler、build tool、test runner、项目命令或网络访问

#### Scenario: default profile 产生分类和评估
- **WHEN** 新 Classifier/Assessor 在 default staged profile 中运行
- **THEN** Compatible Report Projector SHALL 将 Classification 投影为现有 Finding，并将项目 Assessment 投影到可选 `summary.readiness`
- **AND** 它 MUST NOT 写入第二套主结果、把 provisional/unknown 升级为 ready 或声称已真实编译/测试

#### Scenario: qualification 保持无副作用
- **WHEN** 同一 Classifier/Assessor 在 qualification profile 中运行
- **THEN** recording/no-op Projector SHALL 观察内部 Classification/Assessment 且返回零 artifact
- **AND** qualification MUST NOT 覆盖 default scan 的正式输出

### Requirement: x86 可达性、替代实现和 portability gap 必须一致分类
Migration Classifier SHALL 对同一语义根因共同考虑 selected source/build proof、knowledge-backed x86 dependency 与 RISC-V/generic/portable alternative proof。完整 proof 证明 x86 dependency 对目标可达时 SHALL 产生相应 blocking/actionable Classification；只有适用输入范围完整且没有有效 alternative 时 SHALL 产生 portability gap，输入不完整时 MUST 保持 unknown。

#### Scenario: selected 源码依赖 AVX 且无替代实现
- **WHEN** 完整 build/source proof 证明目标选择 AVX 依赖，且完整 alternative 分析证明不存在 RISC-V/generic/portable 实现
- **THEN** Classifier SHALL 产生引用完整 proof 的 blocking/actionable Classification 和 portability gap
- **AND** summary、Finding 与 Assessment SHALL 对该根因使用一致状态

#### Scenario: alternative 枚举不完整
- **WHEN** selected x86 dependency 已证明但 sibling/alternative 输入范围不完整
- **THEN** x86 dependency Classification SHALL 保留，alternative/portability 维度 SHALL 为 unknown
- **AND** `portabilityGaps=0` MUST NOT 被用来暗示已经证明没有 gap

#### Scenario: x86 路径被完整排除
- **WHEN** 完整互斥 proof 证明含 x86 dependency 的 source/target 对目标 inactive/not_selected
- **THEN** Classification SHALL 为 guarded/inactive、non-blocking 和 non-actionable
- **AND** 该局部结论 MUST NOT 单独升级整个项目为 ready

### Requirement: 项目 Assessment 必须使用闭合 proof 而非报告计数
Migration Assessor SHALL 从有效 Classification、Observation、Relation 和 ProofPath 组合 target reachability、x86 dependency、alternative 与 portability gap 维度，并 SHALL 使 `summary.readiness` 和兼容 summary 计数反映同一状态。它 MUST NOT 从 Finding 总数、未命中或聚合方式反推项目结论。

#### Scenario: AVX-only 项目证据完整
- **WHEN** selected build/source 路径完整覆盖项目输入、依赖 x86/AVX 且没有有效 RISC-V/generic alternative
- **THEN** Assessment SHALL 产生 `x86_only` 并列出对应 blocking dimensions 与稳定引用
- **AND** metadata SHALL 保持 `staticScopeOnly=true`、`compiled=false`、`testsExecuted=false`

#### Scenario: 可达性或输入完整性不足
- **WHEN** build/source reachability、alternative 或测试选择任一适用维度为 partial/unknown
- **THEN** Assessment SHALL 保持 provisional/unknown 并列出阻塞更高结论的维度
- **AND** 它 MUST NOT 声称真实编译成功、测试通过或 RISC-V ready

### Requirement: 分类评估修正必须通过隔离单元与字段级 AVX 门禁
本 change 修改的 classification decision table、portability-gap policy、assessment dimension reducer 和 summary mapping SHALL 分别映射到隔离单元测试，并 SHALL 在 `kb-scanner-test` 容器中达到每模块至少 90% line / 80% branch；之后 SHALL 运行 AVX 字段级人工对照、schema 1.0 consumer contract 和完整回归。

#### Scenario: 运行分类评估单元门禁
- **WHEN** 独立容器执行 classification/assessment unit inventory
- **THEN** 合成 Observation/Proof 测试 SHALL 覆盖 complete、inactive、alternative-present、alternative-absent、unknown 和冲突输入并满足覆盖门槛
- **AND** 真实 scanner 端到端结果 MUST NOT 替代隔离单元覆盖

#### Scenario: AVX 人工对照验证结论而非只验证数量
- **WHEN** scanner 扫描修正后的 AVX fixture
- **THEN** 回归 SHALL 同时验证 symbol、span、macro definition closure、build occurrences、reachability、portability gap、Assessment 和聚合 diagnostics
- **AND** 任一缺失、额外或状态不一致 SHALL 使门禁失败

### Requirement: 架构枚举候选必须按关系证明进行保守分类
Classifier SHALL 结合 enum candidate Observation、member binding、selection condition、下游 x86 dependency 和目标可达性 proof 决定影响；名称命中本身 SHALL 保持 `unknown`，只有完整关系证明才可升级。Assessor SHALL 将 unresolved/ambiguous enum selection 计入输入完整性，MUST NOT 因零 blocker 或零其他 Finding 推导 RISC-V ready。

#### Scenario: 孤立架构枚举成员
- **WHEN** enum member 名称匹配 x86 architecture/feature knowledge但没有 reference 或 guarded dependency proof
- **THEN** Classification SHALL 为 unknown、non-blocking、non-actionable，并使用稳定的 candidate-insufficient reason
- **AND** Finding SHALL 仍可展示声明位置和 Knowledge provenance

#### Scenario: 枚举条件保护真实 x86 依赖但选择未知
- **WHEN** complete proof 表明 enum condition 保护 knowledge-backed x86 dependency，但没有证明 RISC-V 选择或排除该条件
- **THEN** Classification SHALL 为 actionable non-blocking，并说明目标选择仍未知
- **AND** 它 MUST NOT 声称该分支已被 RISC-V 构建选中

#### Scenario: RISC-V 选择 x86 枚举分支
- **WHEN** complete target/build proof 连接 RISC-V selector 到保护 x86 dependency 的 enum member condition
- **THEN** Classification SHALL 为 blocking issue，并引用完整 selection 与 dependency proof
- **AND** blocker MUST NOT 仅由 enum 名称或模板声明产生

#### Scenario: RISC-V 排除 x86 枚举分支
- **WHEN** complete proof 表明 RISC-V 选择 RISC-V/generic/portable sibling 并排除 x86 enum branch
- **THEN** Classification SHALL 为 guarded inactive、non-blocking、non-actionable
- **AND** 原 x86 Evidence 和排除它的 condition/alternative chain SHALL 保留

#### Scenario: 枚举关系歧义或输入不完整
- **WHEN** member binding、condition、downstream dependency 或 selection proof 为 ambiguous、partial、dynamic 或 truncated
- **THEN** Classification 与 Assessment SHALL 保持 unknown/provisional 并保留 blocking dimension/reason
- **AND** 系统 MUST NOT 选择最乐观分支或从没有命中推导 ready

#### Scenario: 数据角色证明驱动排除
- **WHEN** 候选具有满足同 fact/subject/configuration/occurrence 合同的完整数据角色 proof 且没有执行角色冲突
- **THEN** Classifier SHALL 保留 Observation 但省略其迁移 Classification，记录 INFO 排除审计
- **AND** 没有证明的候选 MUST 保持 unknown 或已有执行 proof 结论，不强制过滤或强制报告全部候选

#### Scenario: Identifier 未决完整性
- **WHEN** 非 enum 的 candidate 被分类为 unknown
- **THEN** Classification completeness SHALL 同样为 unknown
- **AND** Assessment MUST NOT 从过滤后计数或缺少 RISC-V 数据格式名称推导 ready 或迁移缺口

### Requirement: Candidate evidence insufficient 只能表示真正未决的架构相关性
Migration Classifier SHALL 仅在 Observation 为有明确候选依据的 `candidate`、架构归属为 unknown 且引用完整有效时返回 `unknown / candidate-evidence-not-sufficient`。已证明 foreign、与架构无关或由重复子节点产生的输入 MUST NOT 形成该 Classification；遇到这种输入 SHALL 返回结构化合同 Diagnostic，而不是影响项目迁移结论。

#### Scenario: 未知 inline asm candidate
- **WHEN** Detector 提供 `unclassified_inline_asm` candidate 且没有 x86/foreign/portable 完整 proof
- **THEN** Classifier SHALL 返回非阻断、非操作的 unknown classification，reason 为 `candidate-evidence-not-sufficient`
- **AND** Assessment SHALL 保持 provisional 而不是 RISC-V ready 或 blocking

#### Scenario: 已证明 ARM 分支的汇编到达 Classifier
- **WHEN** 一个 Observation 标记为 foreign/arm 但仍被错误传入 Migration Classifier
- **THEN** Classifier SHALL 产生输入合同 Diagnostic 且不得生成 x86 migration Classification
- **AND** 该输入 MUST NOT 增加 finding、blocking、issue 或 candidate 计数

#### Scenario: 通用 attribute 到达 Classifier
- **WHEN** `no_sanitize` 等无架构语义 attribute 被错误标为 candidate
- **THEN** Classifier SHALL 拒绝将其解释为 `candidate-evidence-not-sufficient`
- **AND** Assessment MUST NOT 因该属性变为 provisional 或问题状态

#### Scenario: 确认 x86 Evidence 不降级
- **WHEN** Observation 引用完整 x86 KnowledgeEntry 并为 `confirmed_local`
- **THEN** Classifier SHALL 按现有 reachability/proof 规则产生 blocking、inactive 或 actionable non-blocking 分类
- **AND** 候选过滤 MUST NOT 把它降级为 unknown

### Requirement: 候选噪声修复必须具有逐模块单元覆盖门禁
本 change 实质修改的 branch attribution、Normalizer、Local Detector、Classification Policy 和 Assessment 输入聚合模块 SHALL 各自登记隔离单元测试，并 SHALL 在独立 `kb-scanner-test` 容器中达到每模块至少 90% line 和 80% branch 覆盖率。zlib、AVX 或全量回归 MUST NOT 替代该门禁。

#### Scenario: 审计测试清单
- **WHEN** 候选资格或架构归属业务模块新增、删除或重命名
- **THEN** 机器可读 inventory SHALL 同步记录 unit suite、fake/mock 边界和高层回归
- **AND** 缺失映射、模块零执行行或覆盖不足 SHALL 使容器门禁失败

### Requirement: 局部风险与影响完整性必须独立判定
Classification SHALL 分开表达已确认执行架构依赖、目标可达性、结论完整性和迁移优先级。完整互斥排除 SHALL 保持 guarded_inactive；未排除的确认 intrinsic/向量类型/x86 指令或参数/精确知识专用头文件 SHALL 支持 high 风险，即使目标影响仍 unknown/partial。纯架构候选 SHALL 保持未决而非确认为依赖；unknown MUST NOT 自动表示低风险或 complete。Classification MUST NOT 改写或丢弃原始事实。

#### Scenario: 专用头文件内容未解析
- **WHEN** immintrin.h 已精确命中 x86 知识，但 include 内容或目标选择尚未解析
- **THEN** 已确认架构依赖 SHALL 保留，局部风险 SHALL 为 high，适用性缺失 SHALL 明确 partial/unknown 且不宣称 blocking
- **AND** 无关 unresolved include 不得抹掉此知识匹配或其他独立完整 proof

#### Scenario: 架构名称和注释
- **WHEN** 只有宏/枚举/identifier 候选，或只有注释线索
- **THEN** 未决候选 SHALL 为 medium 待核查且 unknown/ambiguous，纯注释 SHALL 保持 info
- **AND** MUST NOT 因同名或附近存在 x86 实现将其直接升级为 blocker

#### Scenario: 排除证据完整
- **WHEN** 当前 occurrence/configuration 的完整 proof 证明 x86 路径被目标互斥排除
- **THEN** SHALL 保持 low/inactive 且非 actionable、非 blocking
- **AND** 不得用项目配置提前失败代替此排除证明

### Requirement: 显式配置拒绝只有闭合且必需才构成阻断
Classifier SHALL 对具有完整入口、目标条件、执行顺序、终止依据和必需范围的 CMake 拒绝 proof 给出该范围 blocking_issue/high；其他 missing_riscv_selection_path、软依赖和可选模块 MUST NOT 被一律升级。Assessment SHALL 按 proof 范围汇总，不以 high 数量替代 blocker/readiness 证明，不因缺失证明推断 ready。

#### Scenario: 必需入口拒绝目标
- **WHEN** 完整 CMake proof 表明项目必需入口对 RISC-V 到达 FATAL_ERROR
- **THEN** Classifier SHALL 产生 complete 的配置阻断，Assessment SHALL 记录其配置范围及依据
- **AND** 结论 SHALL 声明静态配置拒绝，不宣称执行过编译

#### Scenario: 高风险但未证明必选
- **WHEN** 局部 AVX 执行依赖确认而 target/source 关系未闭合
- **THEN** SHALL 保持 high 和可核查处理的 actionable，同时 blocking=false，status 为 partial/unknown
- **AND** summary MUST NOT 将其单凭 severity 计为已确认阻断

### Requirement: 路径家族候选不得独立改变迁移风险结论

Classifier 和 Assessor SHALL 保持路径角色提示与执行依赖证明分离。纯路径候选 MUST NOT 创建迁移 Classification、增加问题或阻断计数、证明 portability gap、撤销已有 blocker 或提升 readiness；已有 source/build proof 继续按既有规则分类。家族发现完整性 MUST NOT 替代功能或目标选择完整性。

#### Scenario: 已有 blocker 旁边出现 generic 文件

- **WHEN** selected x86 dependency 已有闭合阻断 proof，但同家族 generic 成员没有被证明选择或可替代
- **THEN** SHALL 保留原 blocker，候选信息仅作为待核查补充

#### Scenario: 路径-only 家族

- **WHEN** 只有 `foo_x86.cpp` 等路径提示，没有真实架构依赖事实
- **THEN** SHALL 不因路径创建新的迁移 Finding 或更高 readiness
- **AND** 家族仍 SHALL 在支持的结构化候选输出中可见

#### Scenario: 既有互斥排除证明完整

- **WHEN** 真实 proof 已证明目标选中通用路径并排除 x86 occurrence
- **THEN** SHALL 保持既有 inactive、非阻断结论，并可展示关联家族上下文
- **AND** 其他家族的 unknown 或裁剪 MUST NOT 抹掉此独立完整 proof

### Requirement: 多版本 default 缺口必须有适用语义和范围闭合证据

Classifier SHALL 仅在机制确认为多版本、适用 compiler/language/target 规则要求 default、相关局部输入完整且同配置内证明未提供时形成 default 缺口分类，默认 actionable_non_blocking/medium。孤立 target 特化、声明-only、未知规则、条件未决和截断 SHALL 不被当作完整缺失证明。default 缺口 MUST NOT 自动表示全项目 portabilityGap 或真实编译失败。

#### Scenario: 缺口证据完整但无目标阻断证明
- **WHEN** 完整规则及范围证明缺少所需 default，但没有独立闭合的目标阻断 proof
- **THEN** SHALL 输出带范围/规则来源的可核查非阻断问题
- **AND** blocking SHALL 为 false，MUST NOT 声称执行过编译或整个项目不可迁移

#### Scenario: 无法验证定义或工具链
- **WHEN** 只有 default 声明、未知 compiler profile 或不完整版本绑定
- **THEN** SHALL 使用 unknown/medium 及明确 reason，保留原 fact 供后续分析补齐
- **AND** MUST NOT 输出 low/complete 或因零问题把项目评为 ready

### Requirement: 多版本补充不得掩盖原 x86 风险或重复同一事实

Detector/Classifier SHALL 保留已有 x86 dependency 与 Knowledge provenance，按精确 Evidence/group/configuration 合并同根因未决候选并区分独立依赖。default 存在与运行时未选中 MUST NOT 撤销原 blocker 或改变编译期依赖；Assessor SHALL 使用相同范围与完整性，不从版本数量推导 readiness。

#### Scenario: Default 或共享体含 intrinsic
- **WHEN** default 定义或 target_clones 共用体含确认 AVX intrinsic
- **THEN** SHALL 保持原 high 局部风险或独立闭合 proof 的 blocker，关联版本上下文
- **AND** 不得因 clone 数量重复生成该 intrinsic occurrence

#### Scenario: 完整排除与候选合并
- **WHEN** 同一 occurrence 被现有互斥目标 proof 完整排除，或旧 generic attribute candidate 与新组观察对应同一根因
- **THEN** 前者 SHALL 保持 inactive/low，后者 SHALL 合并解释并保留原始 provenance
- **AND** MUST NOT 跨 configuration 合并、删除独立 feature fact 或让成员边代替排除 proof

### Requirement: 测试结论必须区分编译选择与内容证明

测试检测与分类 SHALL 分开使用编译成员、注册/运行选择和内容关系。完整的测试构建链与 knowledge-backed x86 依赖可以证明编译阻断；“测试入口使用/断言验证某 fact”的说明 SHALL 另外要求具体 occurrence 的受支持内容关系，不能由同文件共现推出。命名角色或未知 runtime 条件 MUST NOT 作为完整选择证明。

#### Scenario: 未调用辅助函数含 intrinsic

- **WHEN** 测试 source 的未调用函数含 intrinsic
- **THEN** SHALL 保留普通源码事实及其独立编译风险，不声称测试入口已经调用或验证它
- **AND** 若有完整测试编译阻断 proof，建议 SHALL 明确是编译问题而非运行失败

#### Scenario: 完整目标选择但局部条件未知

- **WHEN** 测试 target 已选中，但相关内容条件、调用或 assert 生效状态未知
- **THEN** 内容关系 SHALL 保持 unknown，不借 target selected 补齐局部执行证明
- **AND** 未知 MUST NOT 被静默降为 low、guarded 或 ready

#### Scenario: 真实互斥测试路径

- **WHEN** 同一配置下完整 proof 排除了对应 x86 注册/内容路径，且编译成员状态独立可判
- **THEN** SHALL 仅对被证明隔离的路径表达 guarded
- **AND** 其他配置、未排除编译依赖或未知路径 SHALL 继续独立保留

### Requirement: 测试内容证明必须非破坏性且不夸大覆盖

新增测试用途 SHALL 不删除 Fact/Observation，不将断言形态自动提升为执行依赖，不修改已有纯数据排除的证据门槛。相同根因/occurrence/configuration 的源码与测试语境 SHALL 合并 provenance，避免重复 Finding 与风险计数。内容清单 SHALL 不自动设置测试枚举完整或证明 RISC-V/generic 测试等价、通过、覆盖完整。

#### Scenario: 同一 intrinsic 具有源码与测试来源

- **WHEN** 源码检测与测试内容检测描述同一 occurrence/configuration 的 x86 依赖
- **THEN** SHALL 合并对应语境与来源而非重复计数
- **AND** 不同配置的未知与确定状态 MUST NOT 相互覆盖

#### Scenario: 只有通用测试或数据断言

- **WHEN** 找到 scalar 测试名称，或者含 X86 数据枚举的断言
- **THEN** SHALL 根据显式关联与既有用途 proof 表达候选/数据用途/unknown
- **AND** MUST NOT 由此宣布覆盖 x86 实现、缺少 RISC-V 等价测试、执行阻断或整体 ready

#### Scenario: 存在不完整或冲突 proof

- **WHEN** 同配置相关关系出现截断、缺失引用或冲突，即使另有一条 complete proof
- **THEN** SHALL 保留对应 unknown 原因和真实事实，不用局部 complete 标签隐藏必要断点
- **AND** 未解析的测试输入 MUST NOT 支持 riscv_test_coverage_gap 的完整枚举前提
