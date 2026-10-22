## ADDED Requirements

### Requirement: 核心管线必须承载知识、归一事实和知识引用
核心领域层 SHALL 提供与 JSON schema model、YAML、parser、图库和 legacy DTO 无关的 KnowledgeSource、KnowledgeEntry 与 NormalizedFact，并 SHALL 允许 KnowledgeSnapshot、NormalizedSnapshot 和 Observation 通过默认兼容字段承载这些对象及其引用。Detector definition SHALL 由 detector 模块的代码维护，而 MUST NOT 伪装成知识事实进入 KnowledgeSnapshot。

#### Scenario: Knowledge Provider 向下游传值
- **WHEN** 正式 Provider 成功加载知识包
- **THEN** 下游 SHALL 从 KnowledgeSnapshot 接收 scanner 自有知识类型
- **AND** Detector MUST NOT 接收 Pydantic、JSON/YAML node、catalog recipe 或 legacy Rule 对象

#### Scenario: 现有测试构造空 Snapshot
- **WHEN** 现有 pipeline/component 测试不提供新增知识或归一事实字段
- **THEN** Snapshot 和 Observation SHALL 使用默认空 tuple 保持构造兼容
- **AND** 新内部字段 MUST NOT 自动成为新的主报告结构

### Requirement: Staged qualification 必须能真实运行到 Local Detection
StagedPipelineRunner SHALL 允许 qualification profile 注入真实 Workspace Collector、C/C++ Frontend、Knowledge Provider、Normalizer 和 Local Detector，同时使用 recording/no-op Analyzer、Classifier、Assessor 和 Report Projector；在后续正式阶段完成前默认 CLI MUST 继续使用 legacy-compatible runner。

#### Scenario: 执行知识与检测 qualification
- **WHEN** fixture 包含有效源码、compilation context 和 RISC-V porting 知识包
- **THEN** 同一个只读 ScanContext SHALL 沿固定阶段顺序产生 WorkspaceSnapshot、FrontendSnapshot、KnowledgeSnapshot、NormalizedSnapshot 和 DetectionSnapshot
- **AND** recording downstream SHALL 能观察真实 Observation 与其 Evidence/Knowledge 引用

#### Scenario: qualification 存在尚未覆盖的能力
- **WHEN** 行为验收矩阵显示某项能力仍需要 curated knowledge、Evidence Graph、关系 Analyzer 或 Classifier
- **THEN** qualification SHALL 保留 partial/deferred Diagnostic
- **AND** pipeline MUST NOT 把该运行呈现为完整 RISC-V readiness 扫描

#### Scenario: 默认应用运行现有 CLI
- **WHEN** 用户执行当前 `kb-scanner scan`
- **THEN** ScanApplication SHALL 继续选择 legacy compatibility profile
- **AND** 新 Local Detector MUST NOT 提前替换现有 Finding、退出码或 artifact 行为
