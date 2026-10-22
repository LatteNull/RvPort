## MODIFIED Requirements

### Requirement: Staged qualification 必须能真实运行到 Local Detection
StagedPipelineRunner SHALL 允许 qualification profile 注入真实 Project Workspace Collector、组合 C/C++/Build Frontend、Knowledge Provider、组合 Normalizer、源码/Build/Test Selection Graph Analyzer、组合 Local/Build/Test Detector、Migration Classifier 和 Migration Assessor，同时使用 recording/no-op Report Projector；在兼容投影和默认切换完成前默认 CLI MUST 继续使用 legacy-compatible runner。

#### Scenario: 执行知识、源码关系、构建/测试选择、分类与评估 qualification
- **WHEN** fixture 包含有效 C/C++、受支持构建/打包/测试输入、compilation context 和 RISC-V porting 知识包
- **THEN** 同一个只读 ScanContext SHALL 沿固定阶段顺序产生 WorkspaceSnapshot、FrontendSnapshot、KnowledgeSnapshot、NormalizedSnapshot、AnalysisSnapshot、DetectionSnapshot、ClassificationSnapshot 和 AssessmentSnapshot
- **AND** recording Projector SHALL 能观察真实 selector、Relation、ProofPath、Observation、Classification、Assessment 及其引用

#### Scenario: qualification 存在尚未覆盖的能力
- **WHEN** 输入完整性显示真实编译/测试、兼容 Projector 或其他外部能力仍未执行
- **THEN** qualification SHALL 保留 partial/provisional/unknown Diagnostic 和 scope metadata
- **AND** pipeline MUST NOT 把该运行呈现为经过真实构建验证的 RISC-V readiness 扫描

#### Scenario: 默认应用运行现有 CLI
- **WHEN** 用户执行当前 `kb-scanner scan`
- **THEN** ScanApplication SHALL 继续选择 legacy compatibility profile
- **AND** 新 Test Selection、Classifier 和 Assessor MUST NOT 提前替换现有 Finding、summary、退出码或 artifact 行为
