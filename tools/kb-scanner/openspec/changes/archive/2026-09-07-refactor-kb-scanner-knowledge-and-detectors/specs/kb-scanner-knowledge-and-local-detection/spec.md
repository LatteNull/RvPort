## ADDED Requirements

### Requirement: Knowledge Provider 必须加载 generated-facts-only JSON Manifest
正式 Knowledge Provider SHALL 安全读取具有 schemaVersion 的严格 JSON manifest 以及 Clang/GCC 两份编译器派生 JSON，SHALL 将严格验证的 generated source 和事实条目转换为 scanner 自有不可变 Knowledge 类型，并 MUST NOT 执行知识文件、项目命令或 legacy evaluator。v1 manifest MUST NOT 包含 `curatedSets`、detector recipe 或可执行匹配语义。

#### Scenario: 加载完整 RISC-V porting Manifest
- **WHEN** JSON manifest 及其声明的生成事实文件均有效
- **THEN** KnowledgeSnapshot SHALL 包含确定排序的六类生成事实、知识包 identity/version 和全部逻辑 source
- **AND** Provider MUST NOT 修改、转换或重生成输入文件

#### Scenario: 单个 Generated Source 无效
- **WHEN** 一个 source 不可读、shape 无效或摘要不匹配但其他 source 和 manifest 有效
- **THEN** Provider SHALL 返回其他有效知识和指向该逻辑 source 的 partial Diagnostic
- **AND** 无效 source MUST NOT 被静默解释为空事实集

#### Scenario: 核心知识输入不可用
- **WHEN** manifest 无法读取、schemaVersion/知识 identity/version 缺失或全部 generated source 不可用
- **THEN** Provider SHALL 返回 failed StageResult 和结构化 Diagnostic
- **AND** pipeline MUST NOT 把空 KnowledgeSnapshot 当作成功加载

#### Scenario: Manifest 尝试定义当前不存在的数据或执行语义
- **WHEN** manifest 包含 `curatedSets`、detectors、operator、任意字段表达式、regex 或 classification/presentation 字段
- **THEN** strict schema SHALL 拒绝该 manifest 并产生 Diagnostic
- **AND** manifest MUST NOT 把尚未采集的数据伪装成现有知识或成为通用规则 DSL

### Requirement: 新知识路径必须独立于 Legacy YAML
现有 24 个 YAML rule SHALL 保持原文件与默认 legacy CLI 行为；正式新 Provider 和 Detector MUST NOT 读取、导入、包装或转换 legacy Rule，也 MUST NOT 建立逐 YAML rule migration inventory，或将动态 `match.any`、`text.scan` 正则、severity、blocking 和本地化 message 作为内部知识合同。

#### Scenario: 检查行为验收矩阵
- **WHEN** 测试读取 C/C++ 迁移能力验收矩阵
- **THEN** 每项行为 SHALL 标记为 generated-fact-local、structural-candidate、needs-curated-knowledge、needs-graph、needs-build、needs-packaging 或 needs-classification
- **AND** 矩阵 SHALL 由需求和代表性 fixture 标识行为，不要求与 YAML rule ID 一一映射

#### Scenario: 默认 CLI 仍使用 Legacy Rules
- **WHEN** 用户在本 change 后执行当前默认扫描
- **THEN** legacy loader/evaluator SHALL 继续读取现有 YAML 并产生兼容 Finding
- **AND** 新 JSON manifest MUST NOT 要求原地改写 legacy YAML

#### Scenario: Staged Qualification 加载知识
- **WHEN** qualification profile 调用正式 Knowledge Provider
- **THEN** Provider SHALL 只加载 JSON manifest 和原样生成 JSON
- **AND** Provider MUST NOT 通过包装或转换 legacy Rule 来构造 KnowledgeSnapshot

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

### Requirement: 未支持的知识和关系能力必须显式延后
行为验收矩阵 SHALL 覆盖已确认的 C/C++ 迁移能力；Local Detector SHALL 只执行有当前事实或明确结构依据的局部 matcher。需要 curated knowledge、宏链、include 可达性、alternative、sibling branch、构建选择、测试选择或目标可达性的能力 SHALL 标记为对应 deferred/unknown，MUST NOT 被当作未命中即安全。

#### Scenario: 规则依赖跨文件关系
- **WHEN** 一个现有 rule 需要 `expands_to`、`includes`、`guarded_by`、`alternative_to` 或 `reachable_from` 关系才能成立
- **THEN** Local Detector SHALL 不生成伪造的 confirmed Observation
- **AND** staged qualification SHALL 输出包含 capability identity 和 deferred reason 的 Diagnostic

#### Scenario: 当前能力和延后能力同时存在
- **WHEN** acceptance matrix 同时包含 generated-fact-local 项与尚未实现的 curated/关系项
- **THEN** Detector SHALL 返回可确认的局部 Observation并保留 deferred 状态
- **AND** 部分能力缺失 MUST NOT 删除已经恢复的 Knowledge、Fact 或 Observation

### Requirement: Curated knowledge 收集必须由后续独立 Change 完成
本 change SHALL 明确记录 `curatedSets` 当前尚未收集，并 SHALL 将其选源、采集、审校、溯源、版本化和 Provider 接入留给 `collect-kb-scanner-curated-knowledge-sets`；本 change MUST NOT 创建空集合、示例数据或隐藏人工词表来宣称具备该知识。

#### Scenario: 当前 Manifest 被检查
- **WHEN** schema 或 component test 验证本 change 的 JSON manifest
- **THEN** manifest SHALL 只声明现有 Clang/GCC generated sources
- **AND** `curatedSets` 或等价人工数据字段 MUST NOT 存在

#### Scenario: 后续计划被检查
- **WHEN** 开发者查看 KB Scanner 重写开发计划和本 change 设计
- **THEN** SHALL 能找到独立 change `collect-kb-scanner-curated-knowledge-sets` 的范围、顺序和验收边界
- **AND** 当前 deferred capability SHALL 能区分“缺少 curated knowledge”和其他关系/分类缺口

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

### Requirement: 新知识与检测阶段不得改变兼容和执行边界
本 change SHALL 保持默认 legacy CLI、`schemaVersion: "1.0"`、既有顶层字段、Finding 关键语义和三个 artifact，SHALL 保持 Clang/GCC 事实 JSON 的内容、六类计数、source、SHA-256 及 legacy 路径中的全部 `generatedSet` 引用，并 MUST NOT 扩大到动态执行或操作系统迁移；新 Provider MUST NOT 消费 `generatedSet`。

#### Scenario: 运行 staged qualification
- **WHEN** 真实 Knowledge Provider、Normalizer 和 Local Detector 接入 qualification profile
- **THEN** recording/no-op Projector SHALL 返回空 artifact 且不写文件
- **AND** 默认 CLI SHALL 继续由 legacy compatibility profile 产生现有报告

#### Scenario: 验证静态分析边界
- **WHEN** 知识或 fixture 包含 command、plugin、response file、构建脚本、测试目标或 RISC-V 编译参数
- **THEN** scanner 和测试 SHALL 只把它们作为静态数据处理
- **AND** 本 change MUST NOT 执行项目 compiler、构建、配置、plugin、测试或真实 RISC-V 编译

#### Scenario: 输入包含非 C/C++ 迁移领域
- **WHEN** 项目或知识包含 OS、内核、系统调用、驱动或板级迁移内容
- **THEN** 新 Provider 和 Detector MUST NOT 将其纳入本模块权威 Observation
