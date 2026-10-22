## 1. 人工验收矩阵与合同基线

- [x] 1.1 建立版本化 test-selection/classification/assessment 行为矩阵，列出确定 test role、candidate role、selected/inactive/unknown、coverage candidate/gap 和项目状态的充分证据与拒绝边界。
- [x] 1.2 添加 `x86_test_guarded`、`riscv_test_blocker`、`riscv_test_coverage_gap`、`test_selection_unknown` 的人工 fixture/oracle，逐项记录 Evidence、Relation、ProofPath 和期望分类。
- [x] 1.3 添加 architecture-independent、x86-only、multiarch-without-riscv、partial-riscv、riscv-ready、provisional/unknown 项目 oracle，并记录每个维度和否决原因。
- [x] 1.4 添加测试目录/名称近似但非测试、同名实现与测试但无关系、多 configuration 冲突、缺失构建/测试 metadata 和 proof 预算截断的负例。
- [x] 1.5 添加包含 Make/CTest/RPM `%check`/wrapper/plugin/response file/网络文本的恶意 fixture 与 marker oracle，明确所有命令只作为静态输入。
- [x] 1.6 为全部人工 baseline/schema/lint 添加隔离单元测试，验证重复身份、非法路径/引用、unknown 缺少 reason、readiness 缺少 scope metadata 和计数漂移均失败。

## 2. Core 分类、评估与测试词汇

- [x] 2.1 新增 scanner-owned test role/selection/coverage 词汇，定义 test suite、target、source、candidate、confidence 和 selected/inactive/not_selected/unknown 状态，不导入 Legacy DTO。
- [x] 2.2 为 test vocabulary 添加隔离单元测试，覆盖有效/无效角色、稳定身份、metadata freeze、排序、跨 checkout 根确定性和 candidate 不可升级合同。
- [x] 2.3 新增稳定 `Classification` 领域对象，承载 impact class、reason、Observation/Evidence/Knowledge/Relation/Proof 引用和 confidence。
- [x] 2.4 向 ClassificationSnapshot 追加向后兼容的默认空 classifications 字段，并保持既有 observations 构造和 protocol 调用有效。
- [x] 2.5 扩展 Assessment/AssessmentSnapshot 表达维度、项目状态、scope/completeness 和上游引用，同时保持现有空构造兼容。
- [x] 2.6 为 Classification、Assessment 和 snapshot 扩展添加纯单元测试，覆盖无效 SHA-256、悬空引用、不可变 JSON metadata、默认兼容、确定排序与稳定 ID。

## 3. 测试资产识别

- [x] 3.1 实现 TestAssetAnalyzer，从 CTest/CMake/Meson/Make/RPM/compilation context 与 source/build Entity 恢复 test suite、target、source 和 role candidate。
- [x] 3.2 实现 test role 证据强度策略：显式 metadata/build relation 为确定角色，路径/文件名模式仅为 candidate，并保留 producer/configuration/location。
- [x] 3.3 为 TestAssetAnalyzer 添加 recording/fake 隔离单元测试，覆盖显式 target、RPM `%check`、多个 source、重复 producer、无测试输入和确定排序。
- [x] 3.4 为 role policy 添加表驱动单元测试，覆盖 `test/tests`、`test_*`、`*_test`、benchmark/example/tool 近似项、大小写和路径边界。
- [x] 3.5 验证 test asset 身份复用既有 source/build Entity，未知 subject/Evidence/target 引用返回 failed Diagnostic 且不进入 AnalysisSnapshot。
- [x] 3.6 添加单元测试断言 TestAssetAnalyzer 不读取源码/构建文件、不加载测试框架、不导入 Legacy 或进程执行模块。

## 4. Test Selection Graph Analyzer

- [x] 4.1 实现 TestSelectionAnalyzer，在同一 AnalysisSnapshot/GraphStore 注册 test suite、test target、test source 和 coverage candidate Entity。
- [x] 4.2 实现 `contains_test`、`selects_test`、`exercises`、`covers_candidate` 和 `alternative_test_for` Relation builder，保留 selection/configuration/provenance。
- [x] 4.3 实现 RISC-V selector 到 test target/source/x86 dependency 的有界 ProofPath，复用阶段 6 的 build/source relations 和 Knowledge-backed Observation 引用。
- [x] 4.4 实现 selected、inactive/not_selected、conflicting configuration、candidate role 和 missing target 的确定状态传播；没有 proof 时保持 unknown。
- [x] 4.5 实现测试关系预算，限制 asset、relation、max depth、visited 和 paths；cycle/截断保留已有路径并输出稳定 reason。
- [x] 4.6 为 Entity/Relation builder 添加 fake GraphStore 单元测试，覆盖稳定 ID、平行 configuration、复用源码实体、未知 endpoint/evidence 拒绝和确定排序。
- [x] 4.7 为 Proof resolver 添加表驱动单元测试，覆盖完整 selected 链、inactive 链、not_found/unknown 区分、cycle 与各项预算。
- [x] 4.8 添加单元测试证明只有名称相似时不产生确定 coverage relation，也不会把缺失测试解释为 coverage gap。

## 5. 测试覆盖与 Observation

- [x] 5.1 实现显式 coverage candidate 规则，只接受 target/source/call/metadata 关系，不以名称相似作为充分证据。
- [x] 5.2 实现 TestSelectionDetector，产生 `x86_test_guarded`、`riscv_test_blocker`、`riscv_test_coverage_gap` 和 `test_selection_unknown` Observation。
- [x] 5.3 为 coverage 规则添加隔离单元测试，覆盖显式覆盖、完整枚举下缺失覆盖、输入不完整、名称近似和多个测试 target。
- [x] 5.4 为 TestSelectionDetector 添加纯单元测试，覆盖四类 Observation、去重、完整引用、unknown 不升级和无最终 severity/readiness。
- [x] 5.5 扩展 CompositeDetector 合并 Local、Build 与 Test Observation，并以 recording/fake 测试验证调用顺序、Diagnostic 去重、状态传播和既有 Observation identity 不变。

## 6. 统一 Migration Classifier

- [x] 6.1 实现 code-owned、版本化 ClassificationDecision/Policy 表，定义 blocking_issue、actionable_non_blocking、guarded_inactive、hint 和 unknown 的充分条件与优先级。
- [x] 6.2 实现 MigrationClassifier，只消费 DetectionSnapshot/AnalysisSnapshot 并为每个语义根因产生独立 Classification，不修改原 Observation。
- [x] 6.3 实现 selected x86 source/build/test dependency 与 missing target path 的 blocking/actionable 分类，并要求完整 Relation/ProofPath。
- [x] 6.4 实现 inactive/not_selected、comment-only、candidate 和 unknown/conflict 的 guarded/hint/unknown 分类，unknown 优先于确定结论。
- [x] 6.5 实现相同根因同状态的多 producer provenance 合并，同时保持不同 configuration/状态并列且不互相覆盖。
- [x] 6.6 为 policy 表添加纯单元测试，覆盖每条规则、边界/近似输入、优先级冲突、缺少 proof、unknown 污染和确定性。
- [x] 6.7 为 MigrationClassifier 添加 recording/fake 隔离单元测试，覆盖引用验证、合并/不合并、输入排序、failed/partial 状态和不读取 YAML/源码/知识文件。

## 7. 多维 Migration Assessor

- [x] 7.1 实现 assessment dimension vocabulary，定义 input completeness、target reachability、x86 dependency、alternative、test selection/coverage 和 packaging constraint 的 satisfied/issue/unknown/not_applicable。
- [x] 7.2 实现每个维度的 reducer，保留 Classification/Observation/Evidence/Relation/Proof 和 configuration provenance，不使用 Finding 数量平均。
- [x] 7.3 实现保守 project-state lattice，产生 architecture_independent、x86_only、multiarch_without_riscv、partial_riscv、riscv_ready、provisional 或 unknown。
- [x] 7.4 实现 `riscv_ready` 完整性守卫，强制所有适用维度闭合且无 blocker/unknown，并写入 staticScopeOnly/compiled/testsExecuted/completeness metadata。
- [x] 7.5 实现 configuration conflict 和 partial input 降级，禁止 producer 优先级覆盖冲突或由“零 x86 命中”推导 ready。
- [x] 7.6 为维度 reducer 添加表驱动隔离单元测试，覆盖 satisfied/issue/unknown/not_applicable、多引用、冲突和缺失维度。
- [x] 7.7 为 project-state lattice 添加穷举/属性式单元测试，验证状态优先级、单调降级、readiness 守卫和输入顺序确定性。
- [x] 7.8 为 MigrationAssessor 添加 recording/fake 单元测试，覆盖所有项目状态、引用完整性、partial/failed 传播和零外部执行。

## 8. Staged qualification 组合接入

- [x] 8.1 扩展 CompositeAnalyzer，在源码和 Build Selection 后运行 TestAsset/TestSelection Analyzer，并合并/验证测试 Entity、Relation 与 ProofPath。
- [x] 8.2 更新 qualification profile，注入真实 CompositeDetector、MigrationClassifier 和 MigrationAssessor，Report Projector 继续 recording/no-op。
- [x] 8.3 为 CompositeAnalyzer/Detector 添加 recording 隔离单元测试，验证上下游对象身份、固定调用顺序、Diagnostic 去重和 complete/partial/unavailable/failed 传播。
- [x] 8.4 为 qualification profile 添加端到端 recording contract 测试，验证真实 Classification/Assessment、scope metadata、阶段顺序和零 artifact 写入。
- [x] 8.5 添加 default application contract，确认 `kb-scanner scan` 仍选择 Legacy compatibility profile，新的分类评估不会提前进入现有 Finding/summary。

## 9. 单元测试清单与容器门禁

- [x] 9.1 创建 `tests/classification-assessment-test-inventory.json`，逐项映射全部新增/实质修改业务模块、隔离 unit suite、fake/mock 边界和适用高层测试。
- [x] 9.2 实现 inventory 审计测试，使模块新增/删除/重命名、unit 文件缺失、模块无 executed lines、Legacy/执行依赖泄漏或高层测试误计均失败。
- [x] 9.3 更新容器测试 runner，独立运行 classification-assessment unit coverage 并逐模块执行至少 90% line / 80% branch 门禁。
- [x] 9.4 保持唯一 `kb-scanner-test` 服务及只读/network-none/cap-drop/tmpfs 边界；不得在宿主机安装依赖、修改生产镜像或根 Compose。
- [x] 9.5 在专属一次性容器中分别运行 classification/assessment unit、frontend、knowledge/detection、evidence graph、build selection 和 full regression，并保存可审计结果。

## 10. 安全、真实项目与兼容验收

- [x] 10.1 运行 guarded/blocker/coverage-gap/unknown 人工 test-selection fixtures，逐条核对 test role、selection status、proof 和 Classification。
- [x] 10.2 运行全部项目状态 oracle，确认 dimension、lattice、provisional/unknown 和 readiness scope 与人工结果一致。
- [x] 10.3 运行真实 AVX 与至少两个现有 x86-only 项目，确认源码/构建 Observation 保留、测试缺失不会自动成为 ready，且无新增无依据 blocker。
- [x] 10.4 运行恶意测试/构建 fixture，确认 marker、workspace、进程、网络和外部状态不变，未启动 compiler/build/test runner 或项目命令。
- [x] 10.5 更新 behavior acceptance matrix，将 build/RPM/test/classification 状态改为对应 graph/classification-backed 或 external-validation-deferred，并为每项保留稳定 reason/fixture。
- [x] 10.6 运行默认 Legacy CLI、output schema 和高价值 fixture 回归，确认 schema 1.0、顶层字段、退出码、三个 artifact、YAML/`generatedSet` 与 Clang/GCC 两份事实 JSON 内容/哈希/六类计数不变。
- [x] 10.7 更新开发计划阶段 7、分类/评估决策表、测试识别边界、readiness 限定和阶段 8 兼容投影说明。
- [x] 10.8 运行 `openspec validate implement-kb-scanner-classification-and-assessment --strict`，确认 proposal/design/specs/tasks 与实际实现一致且全部任务完成。
