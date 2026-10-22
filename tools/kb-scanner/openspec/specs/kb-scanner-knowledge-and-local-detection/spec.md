# KB Scanner Knowledge and Local Detection Specification

## Purpose

定义 KB Scanner 的知识加载、事实归一化和局部检测合同，使新管线能够安全消费现有编译器事实、产生可追溯 Observation，并明确尚待 curated knowledge、关系分析和分类阶段补齐的能力边界。

## Requirements

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

### Requirement: 重复知识事实必须合并并保留全部来源
同一 category 和 canonical value 的编译器派生事实 SHALL 具有稳定 KnowledgeEntry identity，重复条目 SHALL 合并为单一知识事实并保留每个来源，稳定身份 MUST NOT 包含机器绝对路径、遍历顺序或 JSON `source` 中的主机路径。

#### Scenario: Clang 与 GCC 包含同一条目
- **WHEN** 两份生成 JSON 的相同 category 包含相同 canonical value
- **THEN** KnowledgeSnapshot SHALL 只建立一个对应 KnowledgeEntry
- **AND** 该 entry SHALL 同时引用 Clang 和 GCC 的可追溯 source identity

#### Scenario: 在不同机器根加载相同知识
- **WHEN** 规则包字节、逻辑相对路径和内容相同但 checkout 根目录不同
- **THEN** KnowledgeSource、KnowledgeEntry 和 KnowledgeSnapshot identity SHALL 保持一致
- **AND** 既有 JSON `source` metadata MAY 原样保留但 MUST NOT 进入稳定 ID

### Requirement: Evidence Normalizer 必须产生稳定事实且保留原始 provenance
正式 Normalizer SHALL 把 Frontend Entity/Evidence 和只读 CompilationUnitContext 转换为 scanner 自有 NormalizedFact，SHALL 保留全部原 Entity/Evidence、producer、source span、confidence 和 compilation context provenance，并 MUST NOT 通过重新解析源码或执行 command 补猜缺失事实。

#### Scenario: 多个 producer 报告等价事实
- **WHEN** Tree-sitter 与 Clang 对同一 subject、canonical value 和语义位置产生等价 Evidence
- **THEN** Normalizer SHALL 建立稳定 NormalizedFact 并保留所有原 Evidence ID与 producer
- **AND** 可选 Clang 是否可用 MUST NOT 改变该局部事实的语义 identity

#### Scenario: compilation context 包含 x86 参数
- **WHEN** CompilationUnitContext tokens 包含 compiler flag、define、include 或 target 参数
- **THEN** Normalizer SHALL 从已分词 token 产生带 context identity 和 token index 的派生 Evidence/NormalizedFact
- **AND** Normalizer MUST NOT 重新执行 raw command、读取 response file、加载 plugin 或启动 compiler

#### Scenario: 遇到未知 Evidence kind
- **WHEN** Frontend 提供当前 Normalizer 尚不支持的 Evidence kind
- **THEN** Normalizer SHALL 保留原 Evidence 并产生 partial/unknown Diagnostic
- **AND** scanner MUST NOT 把该缺口解释为不存在迁移风险

### Requirement: Local Detector 必须只从标准事实产生可追溯 Observation
正式 Local Detector SHALL 只消费 ScanContext、NormalizedSnapshot、AnalysisSnapshot 和 KnowledgeSnapshot，通过 code-owned DetectorDefinition 和显式 matcher registry 产生 Observation；confirmed Observation SHALL 引用有效 Evidence 和适用 KnowledgeEntry identity，纯结构 candidate/hint SHALL 引用有效 Evidence 并明确匹配依据。Detector MUST NOT 读取源码、JSON/YAML schema model、catalog recipe、parser 对象或 legacy DTO。

#### Scenario: 精确局部 x86 命中
- **WHEN** normalized include、symbol/call、type、macro或 compiler argument 与两份生成事实中已加载的知识精确匹配
- **THEN** Detector SHALL 产生 `confirmed_local` Observation，保留 rule/category、Evidence 和 Knowledge provenance
- **AND** Observation MUST NOT 直接声明 blocker、最终 severity 或 RISC-V readiness

#### Scenario: 相同事实由多个来源支持
- **WHEN** 一个 NormalizedFact 聚合多个 producer Evidence 或一个知识条目聚合多个 compiler source
- **THEN** 单一 Observation SHALL 保留全部适用引用并确定性去重
- **AND** 输出顺序和 ID SHALL 不依赖输入遍历顺序

#### Scenario: 引用不存在的事实
- **WHEN** matcher 尝试生成包含未知 Evidence、Knowledge 或 subject identity 的 Observation
- **THEN** Detector SHALL 拒绝该 Observation 并返回 failed Diagnostic
- **AND** 无效引用 MUST NOT 进入 DetectionSnapshot

### Requirement: Local Detector 必须区分确认命中、候选和注释提示
Detector SHALL 将直接知识命中、模糊架构标识和 comment 文本分别表达为 `confirmed_local`、`candidate` 和 `hint` Observation，MUST NOT 在缺少关系与分类证据时把 candidate/hint 升级为阻断结论。

#### Scenario: 注释包含 x86 或 SIMD 名称
- **WHEN** comment Evidence 出现 x86、SSE、AVX 或编译器事实词
- **THEN** Detector MAY 产生可追溯 `hint` Observation
- **AND** 该 Observation MUST NOT 携带 blocker 或最终 severity 语义

#### Scenario: 模糊宏或架构枚举样式名称
- **WHEN** macro/preprocessor Evidence 包含可能表示架构的非权威名称但没有直接知识精确命中
- **THEN** Detector MAY 产生 `candidate` Observation并说明匹配依据
- **AND** 是否为真实选择、调用或类型依赖 SHALL 留给后续关系分析与 Classifier

#### Scenario: 普通变量或枚举缺少 Frontend Evidence
- **WHEN** 当前 Frontend 无法提供可定位的变量或枚举 Evidence
- **THEN** Local Detector SHALL 保持该能力 unknown/deferred
- **AND** Detector MUST NOT 绕过 Frontend 用正则重新扫描源码并宣称完整覆盖

#### Scenario: 结构信号缺少权威知识
- **WHEN** inline asm、declaration attribute、CPU API 样式名称或架构别名没有被现有生成事实覆盖
- **THEN** Detector MAY 只产生可解释的 structural candidate/hint 或明确保持 unknown
- **AND** Detector MUST NOT 通过内置未经审校词表产生 confirmed_local Observation

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
行为验收矩阵 SHALL 覆盖已确认的 C/C++ 迁移能力；Detector/Classifier SHALL 只执行有当前事实、明确结构依据或 Graph Analyzer Relation/ProofPath 支持的 matcher/policy。已实现的宏链、include、sibling/alternative、build selection、test selection 和 classification/assessment SHALL 标记为对应 graph/classification-backed；真实编译、测试执行、兼容投影或输入不完整的能力 SHALL 标记为 deferred/provisional/unknown，MUST NOT 被当作未命中即安全。

#### Scenario: 规则依赖已支持的源码、构建或测试关系
- **WHEN** 一个迁移行为可由完整 include/macro/guard/alternative、selector/condition/source/argument/dependency/target 或 test selection/coverage proof 支持
- **THEN** Detector/Classifier SHALL 使用有效关系引用产生 Observation/Classification
- **AND** Assessor SHALL 只从这些可追溯对象合成项目维度，不得绕过前序阶段扫描文本

#### Scenario: 结论仍依赖真实编译测试或兼容投影
- **WHEN** 一个行为需要真实 RISC-V compile/link/run、测试执行、外部 RVWMO 分析或最终兼容 Projector 才能完整成立
- **THEN** staged qualification SHALL 输出 capability identity、scope 和 deferred/unknown reason
- **AND** Classifier/Assessor MUST NOT 用静态局部或构建关系伪造外部验证结果

#### Scenario: 当前能力和未知输入同时存在
- **WHEN** acceptance matrix 同时包含 classification-backed 项与缺失/冲突/截断输入
- **THEN** pipeline SHALL 返回可确认的 Observation/Classification/Assessment 维度并保留 provisional/unknown 状态
- **AND** 未知能力 MUST NOT 删除已经恢复的 Knowledge、Fact、Relation、ProofPath、Observation 或确定分类

#### Scenario: 更新行为验收矩阵
- **WHEN** 本 change 完成 staged qualification
- **THEN** build source/RPM selection SHALL 不再标为 needs-build/needs-packaging，test selection 与 blocking/readiness SHALL 标记为 classification-backed 或明确的 external-validation-deferred
- **AND** 每个状态 SHALL 具有代表性 fixture 和稳定 reason，不得通过修改 Legacy YAML 伪装完成

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

### Requirement: Knowledge 与 Local Detection 必须具有逐模块单元测试门禁
本 capability 的每个新增或实质修改业务模块 SHALL 在同一 change 中映射到隔离单元测试，测试 SHALL fake/mock 文件系统、外部 schema 输入和上下游阶段，并 SHALL 在唯一 `kb-scanner-test` 容器中执行行覆盖率至少 90%、分支覆盖率至少 80%的独立门禁。

#### Scenario: 检查模块测试清单
- **WHEN** 新增、删除或重命名 core knowledge/fact、knowledge provider、normalizer 或 detector 模块
- **THEN** 机器可读 inventory SHALL 同步映射对应单元测试和适用高层测试
- **AND** 缺失映射或任一模块无 executed lines SHALL 使测试门禁失败

#### Scenario: 运行正式验证
- **WHEN** 独立测试容器验证本 capability
- **THEN** 容器 SHALL 分别报告 knowledge/detection unit、frontend unit 和 full regression 结果
- **AND** 真实 JSON manifest/generated facts、behavior acceptance matrix、Tree-sitter、libclang 与 staged tests MUST NOT 被计入隔离单元覆盖数字

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

### Requirement: X86 Detector 必须按架构归属约束结构候选
Local Detector SHALL 在产生 inline asm 或 declaration attribute Observation 前结合现有 x86 KnowledgeEntry 和 AnalysisSnapshot 中可验证的 branch/selection role 判定候选资格。命中 x86 知识的事实 SHALL 保持 `confirmed_local`；位于已证明非 x86 分支的事实 MUST NOT 产生 x86 Observation；没有足够归属证据但仍具有汇编架构风险的事实 MAY 产生一个 `candidate`。Detector MUST NOT 通过隐藏的 ARM 或其他架构指令黑名单作出排除。

#### Scenario: ARMCRC32 分支包含 AArch64 汇编
- **WHEN** inline asm Evidence 位于可追溯的 ARM/AArch64 branch 且未命中任何 x86 instruction/register KnowledgeEntry
- **THEN** Detector MUST NOT 产生 x86 confirmed 或 candidate Observation
- **AND** 该排除 MUST NOT 被解释为已完成 ARM→RISC-V 迁移分析

#### Scenario: 汇编命中既有 x86 知识
- **WHEN** 完整 inline asm Evidence 命中现有 Clang/GCC/curated x86 instruction 或 register KnowledgeEntry
- **THEN** Detector SHALL 产生一个引用完整 Evidence 和全部适用知识来源的 `confirmed_local` Observation
- **AND** foreign/unknown 兜底 MUST NOT 覆盖该精确知识命中

#### Scenario: 无法归属的汇编
- **WHEN** 完整 inline asm Evidence 未命中 x86 知识且没有完整 foreign、RISC-V、portable 或 inactive branch proof
- **THEN** Detector MAY 产生一个 `candidate` 并记录 `unclassified_inline_asm` 依据
- **AND** 它 MUST NOT 被声明为 confirmed、blocking 或 RISC-V safe

#### Scenario: 混合架构 selector
- **WHEN** 条件同时包含 `__x86_64__` 与 `__aarch64__` 等多个架构分支语义
- **THEN** Analyzer/Detector SHALL 保留 x86 知识命中和可验证的 alternative/branch 关系
- **AND** 它 MUST NOT 因出现非 x86 token 而把整个条件或其 x86 证据直接过滤

### Requirement: 通用 declaration attribute 不得形成架构候选
Local Detector SHALL 仅对具有 target、target_clones、vector width、architecture alias 或已加载 target feature 知识语义的 declaration attribute 产生 Observation。sanitizer、visibility、packing、lifecycle 或其他没有架构选择/特性语义的通用属性 MUST NOT 产生 x86 candidate、hint 或 confirmed Observation。

#### Scenario: no_sanitize memory
- **WHEN** NormalizedFact 来自 `__attribute__((no_sanitize("memory")))`
- **THEN** Detector MUST NOT 产生 `target_attribute_candidate` 或其他 x86 Observation
- **AND** 该属性 MUST NOT 增加 Finding 或迁移问题计数

#### Scenario: target avx2
- **WHEN** declaration attribute 精确包含 `target("avx2")` 且 `avx2` 命中现有 x86 target feature KnowledgeEntry
- **THEN** Detector SHALL 产生 knowledge-backed `confirmed_local` Observation
- **AND** Observation SHALL 保留 KnowledgeEntry、Evidence 和 branch relation provenance

#### Scenario: 未知 target feature
- **WHEN** 属性种类明确为 target/target_clones 但 feature 无法由现有知识归属
- **THEN** Detector MAY 产生一个有明确 attribute-kind 依据的 candidate
- **AND** 普通属性不得借用该兜底路径

### Requirement: 候选去重必须以完整语义根和源码 span 为准
Normalizer 与 Local Detector SHALL 以 producer、source entity、configuration、完整语义 Evidence span 和 detector identity 建立候选根因；同一最外层 Evidence 的嵌套 AST 节点 MUST NOT 形成多个 NormalizedFact 或 Observation，不同源码 span 的独立语句 SHALL 保留为不同 occurrence。

#### Scenario: 九条 ARM 汇编具有嵌套节点
- **WHEN** Tree-sitter 为九条 asm 语句暴露 statement、qualifier 和 operand 子节点
- **THEN** 下游 SHALL 最多接收九个完整 inline asm facts，且 foreign 排除后不得形成 x86 Observation
- **AND** Evidence/Observation 数量 MUST NOT 随 grammar 暴露的嵌套节点数增长
