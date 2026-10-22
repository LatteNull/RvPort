## MODIFIED Requirements

### Requirement: Local Detector 必须消费可追溯图关系而不执行图推理
Local/Build Selection Detector SHALL 在既有 NormalizedSnapshot 与 KnowledgeSnapshot 之外消费组合 Graph Analyzer 产生的 AnalysisSnapshot，并 SHALL 仅从已验证的 Relation/ProofPath 引用补充 macro reachability、guard、alternative、target selection 和 build argument/dependency 上下文；Detector MUST NOT 自行读取源码/构建文件、构建第二套图、调用 Legacy evaluator 或把 partial/unknown 关系升级为确定结论。

#### Scenario: 局部 intrinsic 位于宏 replacement path
- **WHEN** macro replacement fact 精确命中 x86 KnowledgeEntry，且 AnalysisSnapshot 提供从调用点到定义和终端 symbol 的完整 proof path
- **THEN** Detector SHALL 产生或补充引用该 fact、knowledge 和 proof relation IDs 的可追溯 Observation
- **AND** macro definition 自身 MUST NOT 被报告为 call Observation

#### Scenario: 构建 proof 选择 x86 参数或源码
- **WHEN** AnalysisSnapshot 提供从 RISC-V selector/configuration 到 x86 knowledge-backed 参数或源码的完整 selected proof
- **THEN** Detector SHALL 产生引用 Fact、KnowledgeEntry 和 Relation/ProofPath 的 build selection Observation
- **AND** 最终 blocker、severity 和 readiness SHALL 留给后续分类与评估阶段

#### Scenario: 宏或构建路径不完整
- **WHEN** x86 fact 存在但 include、definition、traversal 或 build selection 关系为 partial/unknown
- **THEN** Detector SHALL 保留局部 Observation 和未知原因
- **AND** Detector MUST NOT 声称目标可达、不可达、非阻断或 RISC-V ready

#### Scenario: sibling 或 build alternative 已被识别
- **WHEN** AnalysisSnapshot 包含 x86 implementation 到 RISC-V/generic/portable/scalar/fallback sibling 的 `alternative_to` 或完整 build inactive relation
- **THEN** Detector MAY 把 relation ID、role 与 selection status 作为 Observation 上下文
- **AND** 最终 active、blocking 和 readiness SHALL 留给后续 classification 阶段

### Requirement: 未支持的知识和关系能力必须显式延后
行为验收矩阵 SHALL 覆盖已确认的 C/C++ 迁移能力；Detector SHALL 只执行有当前事实、明确结构依据或 Graph Analyzer Relation/ProofPath 支持的 matcher。已实现的宏链、include、sibling/alternative 和 build selection SHALL 标记为 graph-backed；仍需要测试选择、测试覆盖、最终分类或项目评估的能力 SHALL 标记为对应 deferred/unknown，MUST NOT 被当作未命中即安全。

#### Scenario: 规则依赖已支持的源码或构建关系
- **WHEN** 一个迁移行为可由完整的 include/macro/guard/alternative 或 selector/condition/source/argument/dependency/target proof 支持
- **THEN** Detector SHALL 使用关系引用产生或补充可追溯 Observation
- **AND** Analyzer/Detector MUST NOT 在本阶段生成最终 blocking、severity 或 readiness

#### Scenario: 规则仍依赖测试或分类能力
- **WHEN** 一个行为需要 test selection/coverage、最终 Classifier 或 Assessor 才能成立
- **THEN** staged qualification SHALL 输出包含 capability identity 和 deferred reason 的 Diagnostic
- **AND** Detector MUST NOT 使用源码或构建关系替代缺失的测试/分类证据

#### Scenario: 当前能力和延后能力同时存在
- **WHEN** acceptance matrix 同时包含 build-graph-backed 项与尚未实现的 test/classification 项
- **THEN** Detector SHALL 返回可确认的局部/关系/选择 Observation 并保留 deferred 状态
- **AND** 部分能力缺失 MUST NOT 删除已经恢复的 Knowledge、Fact、Relation、ProofPath 或 Observation
