## MODIFIED Requirements

### Requirement: 新知识路径必须独立于 Legacy YAML
现有 24 个 YAML rule 和全部 `generatedSet` 引用 SHALL 保持原文件不变并仅作为冻结 differential/golden oracle 资产；default 与 qualification 新管线的 Knowledge Provider、Detector、Classifier 和 Projector MUST NOT 读取、导入、包装或转换 Legacy Rule，也不得将动态 `match.any`、`text.scan` 正则、severity、blocking 和本地化 message 作为知识合同。正式检测和展示决策 SHALL 分别由 code-owned detector/classification/projection policy 维护。

#### Scenario: 检查行为验收矩阵
- **WHEN** 测试读取 C/C++ 迁移能力验收矩阵
- **THEN** 每项行为 SHALL 标记为 generated/curated-fact-local、structural-candidate、graph-backed、classification-backed 或 external-validation-deferred
- **AND** 矩阵 SHALL 由需求和代表性 fixture 标识行为，不要求与 YAML rule ID 一一映射

#### Scenario: 默认 CLI 加载正式知识包
- **WHEN** 用户在 cut-over 后执行默认扫描
- **THEN** Knowledge Provider SHALL 只加载 `knowledge-manifest.json` 声明的 generated/curated JSON source
- **AND** 默认 scan MUST NOT 加载 Legacy YAML 或因其内容改变扫描行为

#### Scenario: Staged Qualification 加载知识
- **WHEN** qualification profile 调用正式 Knowledge Provider
- **THEN** Provider SHALL 使用与 default profile 相同的 JSON manifest 和原样 generated/curated JSON
- **AND** Provider MUST NOT 通过包装或转换 Legacy Rule 来构造 KnowledgeSnapshot

#### Scenario: 旧 YAML 仍存在于规则包
- **WHEN** 冻结 Legacy YAML 与 `generatedSet` 引用继续保存在仓库用于差异审计
- **THEN** import/runtime boundary SHALL 证明新 Provider、Detector、Classifier 和 Projector 不读取这些文件
- **AND** 它们 MUST NOT 被删除、自动改写或伪装成 accepted knowledge

### Requirement: 多来源知识接入不得改变兼容和执行边界
Default staged profile SHALL 保持 `schemaVersion: "1.0"`、既有顶层字段、Finding 关键语义和 `scan-result.json`、`scan-report.html`、`scan.log`，并 SHALL 直接使用两份既有 compiler facts、新 generated facts 和 accepted curated facts；Legacy YAML/`generatedSet` 只参与冻结 oracle 审计。Provider、Detector 和 Projector MUST NOT 在扫描时联网、启动 toolchain、执行项目代码或扩展到 OS/内核/系统调用/驱动/板级迁移。

#### Scenario: 默认 CLI 扫描现有 fixture
- **WHEN** 正式多来源知识、detector、classifier 和 compatible projector 已接入 default profile
- **THEN** default staged pipeline SHALL 产生现有结果合同和 artifact
- **AND** 新内部 Knowledge/Observation/Classification MUST NOT 自动形成第二套主结果

#### Scenario: Qualification 使用多来源知识
- **WHEN** staged qualification 加载同一多来源 manifest
- **THEN** 它 SHALL 只执行 C/C++ 静态知识匹配、关系、分类和评估并保留 external-validation-deferred 能力
- **AND** recording/no-op Projector SHALL 不写正式 artifact

#### Scenario: 旧消费者读取新默认结果
- **WHEN** compatible projector 把知识 provenance 和分类摘要写入现有 Finding `trace`
- **THEN** 既有消费者 SHALL 能继续读取 schema 1.0 必需字段
- **AND** 知识来源扩展 MUST NOT 改变现有 rulePack 字段类型、Finding 计数语义或 artifact 名称

### Requirement: 新知识与检测阶段不得改变兼容和执行边界
本 capability SHALL 在默认 staged scan 中保持 `schemaVersion: "1.0"`、既有顶层字段、Finding 关键语义和三个 artifact，SHALL 保持 Clang/GCC 事实 JSON 的内容、六类计数、source、SHA-256 及冻结 Legacy YAML 中的全部 `generatedSet` 引用，并 MUST NOT 扩大到动态执行或操作系统迁移；新 Provider MUST NOT 消费 `generatedSet`。

#### Scenario: 运行 default staged scan
- **WHEN** 真实 Knowledge Provider、Normalizer、Detector、Classifier、Assessor 和 Compatible Report Projector 接入 default profile
- **THEN** Projector SHALL 从 scanner-owned snapshots 生成兼容 Finding、summary 和三个 artifact
- **AND** default profile MUST NOT 调用 Legacy compatibility profile 或读取 YAML

#### Scenario: 运行 staged qualification
- **WHEN** qualification profile 使用同一真实 Knowledge Provider、Normalizer、Detector、Classifier 和 Assessor
- **THEN** recording/no-op Projector SHALL 返回空 artifact 且不写文件
- **AND** qualification 与 default profile SHALL 共享相同事实和分析语义而只在投影副作用上不同

#### Scenario: 验证静态分析边界
- **WHEN** 知识或 fixture 包含 command、plugin、response file、构建脚本、测试目标或 RISC-V 编译参数
- **THEN** scanner 和测试 SHALL 只把它们作为静态数据处理
- **AND** 本 change MUST NOT 执行项目 compiler、构建、配置、plugin、测试或真实 RISC-V 编译

#### Scenario: 输入包含非 C/C++ 迁移领域
- **WHEN** 项目或知识包含 OS、内核、系统调用、驱动或板级迁移内容
- **THEN** 新 Provider、Detector、Classifier、Assessor 和 Projector MUST NOT 将其纳入本模块权威结论
