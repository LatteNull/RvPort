## ADDED Requirements

### Requirement: Analyzer 必须显式接收同一扫描的知识快照
核心 `Analyzer` protocol SHALL 从 orchestrator 显式接收 ScanContext、NormalizedSnapshot 和同一次扫描加载的 KnowledgeSnapshot，并 SHALL 返回只包含 scanner-owned Entity、Relation、ProofPath 与 Diagnostic 的 AnalysisSnapshot/StageResult；Analyzer MUST NOT 通过全局状态、文件重读或 Legacy rule loader 获取知识。

#### Scenario: Pipeline 执行关系分析
- **WHEN** Knowledge Provider、Frontend 和 Normalizer 成功完成
- **THEN** orchestrator SHALL 把同一个 KnowledgeSnapshot 与 NormalizedSnapshot 传入 Analyzer
- **AND** Local Detector SHALL 在 Analyzer 之后接收该 AnalysisSnapshot

#### Scenario: 测试替换 Analyzer
- **WHEN** pipeline 单元测试注入 recording Analyzer
- **THEN** 测试 SHALL 能验证 knowledge/facts 的身份和确定调用顺序
- **AND** recording stage MUST NOT 读取 manifest、YAML 或源码

### Requirement: AnalysisSnapshot 扩展必须保持内部与输出兼容
AnalysisSnapshot SHALL 以默认空 tuple 承载 Analyzer 合成 Entity、Relation 和 ProofPath，现有空构造 SHALL 继续有效；这些内部对象 MUST NOT 自动序列化为第二个主结果，未来需要持久化的 proof SHALL 投影到现有 Finding `trace` 或其他既有兼容字段。

#### Scenario: 现有测试构造空分析结果
- **WHEN** recording/no-op Analyzer 或旧 component test 使用 `AnalysisSnapshot()`
- **THEN** 构造 SHALL 保持有效且表示没有已物化关系

#### Scenario: Qualification 产生图关系
- **WHEN** staged qualification 返回非空 Entity、Relation 和 ProofPath
- **THEN** recording/no-op Projector SHALL 不写 artifact
- **AND** 默认 CLI 的 `schemaVersion: "1.0"`、顶层字段和三个 artifact SHALL 保持不变

## MODIFIED Requirements

### Requirement: Staged qualification 必须能真实运行到 Local Detection
StagedPipelineRunner SHALL 允许 qualification profile 注入真实 Workspace Collector、C/C++ Frontend、Knowledge Provider、Normalizer、Graph Analyzer 和 Local Detector，同时使用 recording/no-op Classifier、Assessor 和 Report Projector；在后续正式阶段完成前默认 CLI MUST 继续使用 legacy-compatible runner。

#### Scenario: 执行知识、关系与检测 qualification
- **WHEN** fixture 包含有效源码、compilation context 和 RISC-V porting 知识包
- **THEN** 同一个只读 ScanContext SHALL 沿固定阶段顺序产生 WorkspaceSnapshot、FrontendSnapshot、KnowledgeSnapshot、NormalizedSnapshot、AnalysisSnapshot 和 DetectionSnapshot
- **AND** recording downstream SHALL 能观察真实 Relation、ProofPath、Observation 及其 Evidence/Knowledge 引用

#### Scenario: qualification 存在尚未覆盖的能力
- **WHEN** 行为验收矩阵显示某项能力仍需要 Build Selector、Classifier、Assessor 或兼容 Projector
- **THEN** qualification SHALL 保留 partial/deferred Diagnostic
- **AND** pipeline MUST NOT 把该运行呈现为完整 RISC-V readiness 扫描

#### Scenario: 默认应用运行现有 CLI
- **WHEN** 用户执行当前 `kb-scanner scan`
- **THEN** ScanApplication SHALL 继续选择 legacy compatibility profile
- **AND** 新 Graph Analyzer 和 Local Detector MUST NOT 提前替换现有 Finding、退出码或 artifact 行为
