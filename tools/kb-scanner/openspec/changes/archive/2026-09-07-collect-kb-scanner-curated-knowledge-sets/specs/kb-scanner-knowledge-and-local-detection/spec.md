## ADDED Requirements

### Requirement: Knowledge Provider 必须兼容加载版本化的多来源知识 Manifest
Knowledge Provider SHALL 继续接受阶段 3 的 v1 generated-only manifest，并 SHALL 通过显式版本化的新 manifest 加载既有 generated facts、新增 generated sources 和 accepted curated sources。每个 source SHALL 由显式 kind、逻辑相对 JSON 路径和 SHA-256 声明；Provider MUST NOT 扫描目录、根据文件名猜测来源类型或加载 decision ledger。

#### Scenario: 加载既有 v1 Manifest
- **WHEN** Provider 接收只声明 `clang-x86-entries.json` 和 `gcc-x86-entries.json` 的有效 v1 manifest
- **THEN** Provider SHALL 产生与阶段 3 相同的 KnowledgeSource、KnowledgeEntry 和 KnowledgeSnapshot identity
- **AND** 两份现有数据的内容、格式、哈希和 provenance SHALL 保持不变

#### Scenario: 加载包含新增来源的 Manifest
- **WHEN** 新版本 manifest 声明有效的新 generated 和 curated sources
- **THEN** Provider SHALL 按严格 source-specific schema 加载 accepted facts并保留 source kind/provenance
- **AND** 相同 fact kind、architecture family 和 canonical value SHALL 合并全部来源

#### Scenario: 单个新增来源无效
- **WHEN** 一个新增 source 不可读、摘要不匹配、schema 无效或引用不存在但其他来源有效
- **THEN** Provider SHALL 保留其他有效知识并返回指向逻辑 source 的 partial Diagnostic
- **AND** 无效来源 MUST NOT 被静默解释为空事实集

#### Scenario: Manifest 尝试加载审计记录
- **WHEN** manifest 声明 decision ledger、rejected/deferred candidates 或含执行语义的数据
- **THEN** strict schema SHALL 拒绝该来源
- **AND** Provider MUST NOT 将其转换为 KnowledgeEntry

### Requirement: 新增知识只能按事实语义提升局部 Observation
Local Detector SHALL 通过 code-owned DetectorDefinition 和 matcher 使用新增 knowledge kind。明确的 x86 instruction/register、CPU/compiler API、target feature 或 architecture alias 可在对应有界 Evidence 上形成 knowledge-backed `confirmed_local`；非 x86 专属的 fixed vector width 只能形成 `candidate`。缺少权威知识、Frontend Evidence 或 token 边界时 SHALL 保持 hint/candidate/unknown/deferred。

#### Scenario: Inline asm 包含已知 x86 指令或寄存器
- **WHEN** inline asm Evidence 在语法边界内命中 accepted instruction/register KnowledgeEntry
- **THEN** Detector SHALL 产生引用该 Evidence 和全部适用 KnowledgeEntry 的 `confirmed_local` Observation
- **AND** Detector MUST NOT 因 asm 节点存在而把未知指令猜成 confirmed

#### Scenario: 调用已知 x86 CPU API
- **WHEN** symbol/call fact 精确命中 accepted x86 CPU/compiler API knowledge
- **THEN** Detector SHALL 产生可追溯 `confirmed_local` Observation
- **AND** API 名称的相似普通函数 MUST NOT 被命中

#### Scenario: Attribute 包含已知 x86 target feature
- **WHEN** declaration attribute Evidence 有界命中 accepted x86 target feature
- **THEN** Detector SHALL 产生 knowledge-backed `confirmed_local` Observation
- **AND** 普通 attribute 或未知 feature SHALL 保持 candidate/unknown

#### Scenario: 固定向量宽度出现
- **WHEN** declaration attribute 或 type fact 命中 accepted vector-width marker
- **THEN** Detector SHALL 最多产生引用知识的 `candidate` Observation
- **AND** 它 MUST NOT 仅凭 16、32、64 字节宽度声明 x86-only、blocking 或 readiness

#### Scenario: 架构别名只出现在注释
- **WHEN** accepted x86 architecture alias 只在 comment Evidence 中出现
- **THEN** Detector SHALL 最多产生 `hint`
- **AND** 同一知识词条 MUST NOT 越过 Evidence kind 的语义升级为 confirmed

### Requirement: Curated knowledge 必须通过独立生产和审校流程接入
Curated knowledge SHALL 由 `collect-kb-scanner-curated-knowledge-sets` 建立的来源审计、逐条审校、版本化和数据质量门禁产生。Manifest SHALL 只接入 accepted runtime source；空集合、示例数据、旧 YAML 自动转换或隐藏在 Detector 中的人工词表 MUST NOT 被用来宣称 curated 能力已完成。

#### Scenario: 当前 Manifest 接入 curated source
- **WHEN** schema、provenance、review 和 deterministic lint 全部通过
- **THEN** manifest SHALL 以显式 source kind、路径和摘要声明该 curated source
- **AND** Provider SHALL 保留其权威 reference 与 review policy provenance

#### Scenario: 候选尚未完成审校
- **WHEN** candidate 为 rejected、deferred 或缺少稳定权威引用
- **THEN** 它 SHALL 留在 non-runtime decision ledger
- **AND** behavior acceptance matrix SHALL 保留对应缺口而不是标记为已支持

### Requirement: 多来源知识接入不得改变兼容和执行边界
本 change SHALL 保持默认 legacy CLI、`schemaVersion: "1.0"`、既有顶层字段、Finding 关键语义和 `scan-result.json`、`scan-report.html`、`scan.log`，并 SHALL 保持两份既有 compiler facts 及 legacy YAML/`generatedSet` 行为不变。Provider 和 Detector MUST NOT 在扫描时联网、启动 toolchain、执行项目代码或扩展到 OS/内核/系统调用/驱动/板级迁移。

#### Scenario: 默认 CLI 扫描现有 fixture
- **WHEN** 新增知识数据和 staged matcher 已存在
- **THEN** 默认 compatibility profile SHALL 继续产生现有结果合同和 artifact
- **AND** 新内部 Knowledge/Observation MUST NOT 自动形成第二套主结果

#### Scenario: Qualification 使用新增知识
- **WHEN** staged qualification 加载多来源 manifest
- **THEN** 它 SHALL 只执行 C/C++ 静态知识匹配并保留 deferred 的图、构建和分类能力
- **AND** recording/no-op Projector SHALL 不写正式 artifact

## REMOVED Requirements

### Requirement: Knowledge Provider 必须加载 generated-facts-only JSON Manifest

**Reason**: v1 generated-only 合同需要保留，但正式 Provider 现在还必须通过显式新版本加载新增 generated 与 accepted curated source，原要求无法表达版本兼容的多来源行为。

**Migration**: 由“Knowledge Provider 必须兼容加载版本化的多来源知识 Manifest”替代；v1 输入及两份旧 facts 的 identity 保持不变。

### Requirement: Curated knowledge 收集必须由后续独立 Change 完成

**Reason**: 该后续独立 change 已建立，主规格需要从“尚未收集”推进为可审计的生产、审校和接入合同。

**Migration**: 由“Curated knowledge 必须通过独立生产和审校流程接入”替代；未审校候选继续 deferred，不创建空占位。
