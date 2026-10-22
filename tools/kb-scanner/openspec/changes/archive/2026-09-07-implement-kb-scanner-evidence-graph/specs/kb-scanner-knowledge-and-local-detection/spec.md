## ADDED Requirements

### Requirement: Local Detector 必须消费可追溯图关系而不执行图推理
Local Detector SHALL 在既有 NormalizedSnapshot 与 KnowledgeSnapshot 之外消费 Graph Analyzer 产生的 AnalysisSnapshot，并 SHALL 仅从已验证的 Relation/ProofPath 引用补充 macro reachability、guard 和 alternative 上下文；Detector MUST NOT 自行读取源码、构建第二套图、调用 Legacy evaluator 或把 partial/unknown 关系升级为确定结论。

#### Scenario: 局部 intrinsic 位于宏 replacement path
- **WHEN** macro replacement fact 精确命中 x86 KnowledgeEntry，且 AnalysisSnapshot 提供从调用点到定义和终端 symbol 的完整 proof path
- **THEN** Detector SHALL 产生或补充引用该 fact、knowledge 和 proof relation IDs 的可追溯 Observation
- **AND** macro definition 自身 MUST NOT 被报告为 call Observation

#### Scenario: 宏路径不完整
- **WHEN** x86 replacement fact存在但 include、definition 或 traversal 关系为 partial/unknown
- **THEN** Detector SHALL 保留局部 Observation 和未知原因
- **AND** Detector MUST NOT 声称调用可达、不可达、非阻断或 RISC-V ready

#### Scenario: sibling alternative 已被识别
- **WHEN** AnalysisSnapshot 包含 x86 implementation 到 RISC-V/generic/portable/scalar/fallback sibling 的 `alternative_to`
- **THEN** Detector MAY 把 relation ID 与 role 作为 Observation 上下文
- **AND** 最终 active、blocking 和 readiness SHALL 留给后续 build/classification 阶段

## MODIFIED Requirements

### Requirement: 未支持的知识和关系能力必须显式延后
行为验收矩阵 SHALL 覆盖已确认的 C/C++ 迁移能力；Local Detector SHALL 只执行有当前事实、明确结构依据或 Graph Analyzer Relation/ProofPath 支持的 matcher。已实现的宏链、include 关系、sibling branch 和 alternative SHALL 标记为 graph-backed；仍需要构建选择、测试选择、目标可达性或最终分类的能力 SHALL 标记为对应 deferred/unknown，MUST NOT 被当作未命中即安全。

#### Scenario: 规则依赖已支持的跨文件关系
- **WHEN** 一个迁移行为可由 `includes`、`invokes_macro`、`expands_to`、`calls`、`guarded_by` 或 `alternative_to` 的完整 proof path 支持
- **THEN** Local Detector SHALL 使用关系引用产生或补充可追溯 Observation
- **AND** Analyzer/Detector MUST NOT 在本阶段生成最终 blocking、severity 或 readiness

#### Scenario: 规则仍依赖构建或分类能力
- **WHEN** 一个行为需要 Make/RPM/test selection、目标构建可达性或最终 Classifier/Assessor 才能成立
- **THEN** staged qualification SHALL 输出包含 capability identity 和 deferred reason 的 Diagnostic
- **AND** Local Detector MUST NOT 使用源码关系替代缺失的构建选择证据

#### Scenario: 当前能力和延后能力同时存在
- **WHEN** acceptance matrix 同时包含 graph-backed 项与尚未实现的 build/classification 项
- **THEN** Detector SHALL 返回可确认的局部/关系 Observation 并保留 deferred 状态
- **AND** 部分能力缺失 MUST NOT 删除已经恢复的 Knowledge、Fact、Relation、ProofPath 或 Observation
