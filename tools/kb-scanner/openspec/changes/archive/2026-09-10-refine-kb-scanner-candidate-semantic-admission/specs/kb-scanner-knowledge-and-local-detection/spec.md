## MODIFIED Requirements

### Requirement: 架构相关枚举必须复用现有知识并保持候选语义
Local Detector SHALL 只消费正式 enum member/reference NormalizedFact，并 SHALL 通过确定性 identifier component normalization 与现有 `targetFeatures`、`architectureAliases` 和适用的 `platformMacros` KnowledgeEntry 匹配疑似 x86 架构或特性名称。enum 名称命中 SHALL 产生带 Knowledge provenance 的 `candidate` Observation，MUST NOT 单独产生 confirmed dependency、blocking、severity 或 readiness 结论。

#### Scenario: 枚举成员精确命中 target feature
- **WHEN** enum member 或引用的完整 component 为 accepted `avx2` target feature
- **THEN** Detector SHALL 产生 candidate Observation，并保留 member/reference Evidence 与对应 KnowledgeEntry
- **AND** Observation SHALL 明确名称匹配不是 ISA 使用证明

#### Scenario: 装饰的枚举名称包含架构 component
- **WHEN** member 名称为 `BACKEND_AVX2`、`X86_AESNI` 或等价分隔形式
- **THEN** matcher SHALL 按确定性 component 边界识别现有知识或强 architecture family token
- **AND** 它 MUST NOT 通过任意 substring 使 `avx2_counted`、普通单词或近似 API 名称命中

#### Scenario: 枚举只包含普通业务值
- **WHEN** enum member 均不匹配 accepted architecture/feature knowledge 或受审计强 token
- **THEN** Detector SHALL 不产生 architecture enum Observation
- **AND** enum type 名称为 `Backend`、`Mode` 或 `Type` 本身 MUST NOT 足以形成候选

#### Scenario: reference binding 不完整
- **WHEN** enum reference 的 declaration binding 为 partial、ambiguous 或 unknown
- **THEN** Detector MAY 保留 candidate Observation和全部可验证 Evidence，但 SHALL 保留不完整状态与 reason
- **AND** 它 MUST NOT 将 member 名称或某个候选 declaration 升级为已确认事实

#### Scenario: 架构名称只在注释中出现
- **WHEN** 与 enum member 同名的架构词只存在于 comment Evidence
- **THEN** 现有 comment detector SHALL 最多产生 hint
- **AND** enum matcher MUST NOT 消费 comment 或让 hint 升级为 candidate/confirmed

#### Scenario: compiler fact 数据保持冻结
- **WHEN** enum matcher 使用 Clang/GCC generated 或 curated knowledge
- **THEN** Knowledge references SHALL 继续指向现有 source identity、digest、category 和 producer
- **AND** `clang-x86-entries.json` 与 `gcc-x86-entries.json` 的 bytes、SHA-256、分类和加载路径 MUST 保持不变

#### Scenario: 分类排除不删除事实
- **WHEN** 后续分类以完整语义证据排除算法/数据格式用途的迁移候选
- **THEN** 前序 Evidence、NormalizedFact、基础关系和检测 Observation SHALL 保留
- **AND** FactProofDemand MUST NOT 根据最终 Finding 是否保留来决定采集需求
