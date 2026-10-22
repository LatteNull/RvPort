## ADDED Requirements

### Requirement: 正式输入阶段必须可组合 C/C++ 与构建 Frontend
Project Workspace Collector、Composite Frontend 和 Composite Normalizer SHALL 通过现有 WorkspaceSnapshot、FrontendSnapshot 和 NormalizedSnapshot 合并 C/C++ 与构建输入结果，并 SHALL 确定性验证 Entity/Evidence/Fact 引用、排序、Diagnostic 和 completion status；组合器 MUST NOT 把第三方 parser 类型、Legacy DTO 或新的外部报告结构引入核心合同。

#### Scenario: 两类 Frontend 均成功
- **WHEN** workspace 同时包含 C/C++ 与受支持构建输入
- **THEN** 同一个 FrontendSnapshot SHALL 保留两个正式 producer 的全部 scanner-owned Entity/Evidence
- **AND** Composite Normalizer SHALL 产生可由统一 Analyzer 消费的源码与构建 NormalizedFact

#### Scenario: 一个可选 Build adapter 部分失败
- **WHEN** C/C++ Frontend 成功但某构建输入不支持或机器产物缺失
- **THEN** 组合阶段 SHALL 保留 C/C++ 与其他构建结果并传播 partial/unavailable Diagnostic
- **AND** 缺失维度 MUST NOT 被转换为空成功或 RISC-V ready

#### Scenario: 现有独立 C/C++ profile
- **WHEN** 单元测试或旧 qualification 只注入既有 C/C++ Collector/Frontend/Normalizer
- **THEN** 现有 protocol、snapshot 构造和稳定身份 SHALL 继续有效
- **AND** 它 MUST NOT 被迫提供虚假的构建 Evidence

## MODIFIED Requirements

### Requirement: Staged qualification 必须能真实运行到 Local Detection
StagedPipelineRunner SHALL 允许 qualification profile 注入真实 Project Workspace Collector、组合 C/C++/Build Frontend、Knowledge Provider、组合 Normalizer、源码/Build Selection Graph Analyzer 和组合 Local/Build Selection Detector，同时使用 recording/no-op Classifier、Assessor 和 Report Projector；在后续正式分类、评估与兼容投影完成前默认 CLI MUST 继续使用 legacy-compatible runner。

#### Scenario: 执行知识、源码关系、构建选择与检测 qualification
- **WHEN** fixture 包含有效 C/C++、受支持构建/打包输入、compilation context 和 RISC-V porting 知识包
- **THEN** 同一个只读 ScanContext SHALL 沿固定阶段顺序产生包含源码与构建内容的 WorkspaceSnapshot、FrontendSnapshot、KnowledgeSnapshot、NormalizedSnapshot、AnalysisSnapshot 和 DetectionSnapshot
- **AND** recording downstream SHALL 能观察真实 selector、Relation、ProofPath、Observation 及其 Evidence/Knowledge 引用

#### Scenario: qualification 存在尚未覆盖的能力
- **WHEN** 行为验收矩阵显示某项能力仍需要 Test Selection、Classifier、Assessor 或兼容 Projector
- **THEN** qualification SHALL 保留 partial/deferred Diagnostic
- **AND** pipeline MUST NOT 把该运行呈现为完整 RISC-V readiness 扫描

#### Scenario: 默认应用运行现有 CLI
- **WHEN** 用户执行当前 `kb-scanner scan`
- **THEN** ScanApplication SHALL 继续选择 legacy compatibility profile
- **AND** 新组合 Frontend、Build Selection Analyzer 和 Detector MUST NOT 提前替换现有 Finding、退出码或 artifact 行为
