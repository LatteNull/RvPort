# KB Scanner Report Schema v2 Specification

## Purpose

定义 KB Scanner schema 2.0 的 Finding-centric 自包含结果、可展示证据链、代码上下文、完整性状态、静态分析边界、确定性序列化以及设计合同门禁。

## Requirements

### Requirement: schema v2 必须提供 Finding-centric 且自包含的扫描结果
KB Scanner schema v2 SHALL 使用 `schemaVersion: "2.0"`，并 SHALL 使每个 Finding 直接包含 `fact`、`conclusion`、`occurrences[]` 和 `evidenceChain`。`evidenceChain` SHALL 携带解释该 Finding 所需的完整相关 step、edge、主路径、分支和断点；消费者 MUST NOT 依赖顶层 Explanation/Catalog、scanner 内部 snapshot 或自由形态 `trace` 才能解释单个 Finding。

#### Scenario: 消费者离线读取完整结果
- **WHEN** scanner 产生一个引用完整的 schema v2 artifact
- **THEN** 消费者 SHALL 能仅凭单个 Finding 读取事实、全部 occurrence、主证明链、底层 Evidence 投影、知识 provenance、conclusion 中的分类理由及 summary 中的项目评估；evidenceChain 不含分析阶段节点
- **AND** Finding 内每个 step、edge、path、occurrence 和 typed provenance reference SHALL 在该 Finding 中完整且类型匹配

#### Scenario: 多个 Finding 共用同一证据
- **WHEN** 多个 Finding 引用相同 Evidence、KnowledgeEntry 或 ProofPath
- **THEN** 每个 Finding SHALL 各自携带与自身有关的紧凑 step projection，并对相同底层对象使用相同稳定 provenance ID
- **AND** 单个 Finding MUST NOT 携带与自身无关的项目图；后端 MAY 按稳定 ID 缓存重复对象但不得要求消费者额外查询

### Requirement: 每个 Finding 必须直接包含可展示的 evidenceChain
每个 schema v2 Finding SHALL 直接包含 evidenceChain，其 status、reasonCodes、rootStepId、primaryPath、steps、edges、breaks 和 budget SHALL 表达当前命中的相关源码/构建子图。生产 primaryPath SHALL 仅包含有可追溯关系的代码/构建节点，MUST NOT 包含 classification、assessment 或 knowledge_match；生产 steps/edges MUST NOT 生成 classification/assessment 及 classified_as/impacts_assessment。knowledge_match SHALL 作为同一 Finding 中与真实命中关联的旁支依据保留，impactStepIds SHALL 保留字段并输出空数组；内部分类和项目评估 SHALL 继续分别输出到 conclusion 和 summary。

#### Scenario: selected 源码调用 AVX intrinsic
- **WHEN** 完整静态 proof 连接配置参数、target/source、条件及 intrinsic Evidence
- **THEN** primaryPath SHALL 沿有依据的连通源码/构建路径展示，并包含当前命中锚点，知识匹配留在旁支
- **AND** conclusion 和 summary SHALL 保留分类/评估结果，消费者无需自行拼装内部 snapshot

#### Scenario: 用户展开宏调用 Finding
- **WHEN** Finding 根因是经本地宏定义和 replacement 到终端 x86 intrinsic 的调用
- **THEN** 主链 SHALL 保留实际调用、定义、replacement、终端关系和多级同 kind 节点，知识匹配不插入代码主路径
- **AND** 每个代码型 step SHALL 直接包含自己的完整 source span、逐行代码上下文和命中高亮

#### Scenario: x86 路径对目标 inactive
- **WHEN** 完整互斥 proof 表明 x86 source 或 build item 未被目标配置选中
- **THEN** evidenceChain SHALL 明确标记 inactive/guarded 并展示排除它的 selector/condition 链
- **AND** Finding MUST NOT 被展示为 actionable blocker

#### Scenario: 找到局部命中但上游缺失
- **WHEN** intrinsic 或宏命中可定位而所需构建作用或定义关系缺失
- **THEN** primaryPath SHALL 保留可验证的局部连通路径和锚点，相关缺失 SHALL 表达为 break
- **AND** Projector MUST NOT 按 kind 排序或任意取第一条 Relation 拼造完整链，也不得以缺少上游推断 ready

### Requirement: 每个代码型 fact、occurrence 和 chain step 必须携带可定位上下文
schema v2 SHALL 为每个有源码或构建文件依据的 fact、occurrence 和 evidenceChain step 提供项目相对文件路径、完整 start/end span、`context.lines[]` 中的真实行号与文本，以及 `highlights[]` 中的命中行列范围。代码上下文 SHALL 默认提供命中范围前后各 20 行，按文件边界与显式硬预算裁剪；命中和高亮 SHALL 优先于普通上下文保留。没有源文件的 knowledge 旁支以及兼容读取的历史非代码 step MUST 保留 provenance/reason/status 且不得伪造位置。

#### Scenario: 详情页展示 intrinsic 命中
- **WHEN** Finding 表示源码中的 `_mm256_add_ps` 调用
- **THEN** fact 和对应 chain step SHALL 给出实际文件、命中 token 的起止行列、带真实行号的上下文行和精确高亮范围
- **AND** 前端 MUST NOT 重新读取项目源码才能展示命中位置

#### Scenario: 宏调用与定义位于不同文件
- **WHEN** 调用点、宏定义和 replacement token 分别具有不同 SourceSpan
- **THEN** 三个 chain step SHALL 分别携带自己的文件、上下文行和命中高亮
- **AND** 任一 step MUST NOT 复制其他 step 的位置或上下文

#### Scenario: 上下文不可读取或超过预算
- **WHEN** Evidence 位置存在但上下文读取失败或超过行数/字符预算
- **THEN** source SHALL 保留 span 并把 context 标记为 partial/unavailable 及稳定 reason
- **AND** Finding 和已验证链路 MUST NOT 因缺少上下文被删除

#### Scenario: 单行与多行默认窗口
- **WHEN** 文件足够长且所需窗口未超过硬预算
- **THEN** 单行命中 SHALL 返回 41 行，多行命中 SHALL 返回全部命中行加前后各 20 行
- **AND** fact、occurrence 和每个代码 step SHALL 使用相同窗口规则，原始 span/highlight 不因扩展上下文改变

### Requirement: 不完整与歧义链路必须显式保留断点
schema v2 Projector SHALL 将缺失输入、引用类型冲突、多个非等价候选、循环和预算截断表达为 evidenceChain `partial`、`ambiguous` 或 `unknown` 及结构化 `breaks`。它 MUST NOT 输出悬空内部引用，也 MUST NOT 把未知表达为空数组、零值或 RISC-V ready。

#### Scenario: 宏定义无法唯一解析
- **WHEN** 调用点存在多个可见且非等价的宏定义候选
- **THEN** evidenceChain SHALL 标记 ambiguous、在 steps/edges 中保留全部可验证候选并记录无法选择的 reason
- **AND** 它 MUST NOT 按输入顺序伪造 complete 主链

#### Scenario: 内部 proof 引用对象缺失
- **WHEN** snapshot 中的 ProofPath 引用不存在或类型冲突的对象
- **THEN** v2 SHALL 保留仍可验证的局部 Finding，并以 break 和 Diagnostic 表达断裂位置
- **AND** 无效 step、edge 或 path 引用 MUST NOT 进入序列化 Finding

#### Scenario: closure traversal 超过预算
- **WHEN** 展开所需路径超过 depth、visited 或 path 数预算
- **THEN** evidenceChain SHALL 标记 partial/truncated，保留已验证 step、edge 和预算计数
- **AND** 截断 MUST NOT 被解释为未发现风险或替代实现

### Requirement: occurrence 必须是一等且可无损聚合
schema v2 SHALL 在每个 Finding 的 `occurrences[]` 中为源码、构建参数和测试资产 occurrence 保留稳定 ID、完整 span、逐行代码上下文、configuration、selection status、Evidence provenance 和 completeness。Finding SHALL 使用 `primaryOccurrenceId` 选择主位置，summary SHALL 明确以 Finding 而非 occurrence 为计数单位。

#### Scenario: 四个构建 Finding 聚合二十四个参数位置
- **WHEN** 4 个 Makefile 根因包含 24 个 x86 flag occurrence
- **THEN** 结果 SHALL 保持 4 个 Finding，且这些 Finding 的 `occurrences[]` 合计恰好恢复 24 个 occurrence
- **AND** path、span、flag、configuration 和 selection status MUST 无缺失或相互覆盖

### Requirement: Diagnostic 必须结构化且保持聚合可追溯
schema v2 Diagnostic SHALL 以字段表达 code、stage、severity、status、reason codes、count、代表位置和 typed refs；相同聚合键的 Diagnostic MAY 合并，但 MUST 保留全部稳定引用和最严重状态，且不得把 details 编码进用户文案字符串。

#### Scenario: 七十四个 include 使用相同 unresolved reason
- **WHEN** 74 个 unresolved-include Diagnostic 具有相同 code、stage、severity、relation kind 和 reason
- **THEN** v2 MAY 输出一条 count 为 74 的聚合 Diagnostic，并保留全部相关引用
- **AND** renderer SHALL 从结构化数据生成人类可读摘要

#### Scenario: 原因或严重性不同
- **WHEN** 两个 Diagnostic 的 reason、stage、relation kind 或 severity 不同
- **THEN** 它们 SHALL 保持为不同记录
- **AND** failed MUST NOT 与 warning/partial 聚合

### Requirement: v2 必须声明静态范围并保留知识来源
schema v2 顶层 scan scope SHALL 明确声明 `staticAnalysisOnly=true`、`compiled=false`、`linked=false` 和 `testsExecuted=false`。被引用的 Clang/GCC 或 curated KnowledgeEntry SHALL 保留 category、symbol、producer、source identity、digest 和 provenance；报告设计 MUST NOT 转换或修改原始事实数据。

#### Scenario: Finding 来源于 compiler-derived x86 fact
- **WHEN** Evidence 命中现有 Clang 或 GCC x86 KnowledgeEntry
- **THEN** 对应 Finding 的 knowledge step SHALL 包含足以追溯原事实来源的紧凑 projection
- **AND** `clang-x86-entries.json` 与 `gcc-x86-entries.json` 的内容、分类和 generated provenance SHALL 保持不变

#### Scenario: 项目被评估为 x86-only
- **WHEN** 完整静态 proof 支持 x86-only Assessment
- **THEN** summary、conclusion 与 evidenceChain SHALL 仍声明这是静态范围结论
- **AND** 结果 MUST NOT 声称真实 RISC-V 编译成功或失败、链接完成或测试已执行

### Requirement: v2 必须确定性序列化并限制扩展
schema v2 SHALL 定义 Finding、occurrence、step、edge、primaryPath 和 Diagnostic 的稳定排序、内部引用形状、ID 材料、链路/上下文预算和封闭对象字段。相同 scanner/knowledge 版本、ScanContext 和输入 SHALL 产生字节一致 JSON；未来非破坏性扩展 SHALL 进入命名空间化 `extensions`，不得恢复无约束 `trace`。

#### Scenario: 输入和遍历顺序扰动
- **WHEN** 同一语义输入以不同文件系统、字典、Evidence 或 Relation 顺序提供
- **THEN** v2 artifact 的对象顺序、ID、主链和字节内容 SHALL 相同
- **AND** ID MUST NOT 包含绝对根路径、随机值、当前时间或对象地址

#### Scenario: 未知扩展出现
- **WHEN** 消费者遇到合法命名空间下不认识的 extension
- **THEN** 消费者 MAY 忽略该 extension 并继续验证核心对象
- **AND** extension MUST NOT 改变核心字段或引用语义

### Requirement: schema 设计必须由机器合同和代表性示例冻结
schema v2 capability SHALL 继续以 JSON Schema 2020-12、引用完整性规则、字段词汇表、v1/v2 合同差异与消费者迁移清单，以及 complete、partial、ambiguous、inactive、unknown 和 AVX explanation 示例作为规范合同。生产 v2 Projector SHALL 直接消费同一次 staged pipeline 的 context、workspace、knowledge、frontend、normalized facts、analysis、detection、classification、assessment 和 diagnostics snapshots，MUST NOT 读取、转换或补全 schema v1 JSON、v1 Finding、自由形态 `trace` 或字符串 Diagnostic。Projector SHALL 在序列化和 artifact 发布前构造封闭 v2 model、投影有界源码上下文、验证 Finding 内引用完整性，并只在全部请求 artifact 成功生成后原子发布；所有实现与合同资产 SHALL 在唯一 `kb-scanner-test` 容器中验证。

#### Scenario: 执行 schema v2 运行时合同门禁
- **WHEN** 独立测试容器用生产 v2 mapper/projector 处理设计正例、定向反例和合成 staged snapshots
- **THEN** 所有有效结果 SHALL 通过 JSON Schema 与引用完整性验证，所有无效引用、状态、上下文或排序输入 SHALL 因预期 reason 失败
- **AND** schema、example、reference rules、vocabulary、production model 或 serializer 漂移 SHALL 使门禁失败

#### Scenario: 从真实 AVX snapshots 生成 explanation
- **WHEN** 完整 staged pipeline 以默认 schema `2.0` 扫描人工审计的 AVX fixture
- **THEN** 生产 v2 Projector SHALL 在单个 Finding 内投影 build/source、macro 或 intrinsic Evidence 的真实链路及每个代码型 step 上下各 20 行上下文，knowledge 作为旁支保留，Classification 和 Assessment 仍在 conclusion/summary 中表达
- **AND** AVX 回归 SHALL 校验 symbol、span、occurrence、primaryPath、edge、break、knowledge provenance 及保留在 conclusion/summary 的分类评估结果，不得以 Finding 总数代替字段与引用正确性

#### Scenario: v2 直接投影且不依赖 v1
- **WHEN** 测试向 v2 Projector 提供 staged snapshots，同时使 v1 mapper 不可用或令任何 v1 访问立即失败
- **THEN** v2 Projector SHALL 仍能生成合法 schema 2.0 result 和请求的 renderer 内容
- **AND** 生产依赖图 MUST NOT 包含 v1 payload、v1 Finding、兼容 `trace` 或 v1 Diagnostic parser

#### Scenario: 上下文文件不可用或越界
- **WHEN** Evidence 具有合法 span，但文件已消失、无法解码、超过上下文预算或解析路径位于项目根外
- **THEN** Projector SHALL 保留可验证 Finding 与 span，使用稳定 reason 将 context 和 chain 标记为 partial/unavailable
- **AND** 它 MUST NOT 读取项目根外文件、复制其他 step 的上下文或把缺失上下文解释为没有风险

### Requirement: schema v2 运行时模块必须具有隔离单元测试与容器覆盖门禁
result version selector、v2 report model、Finding mapper、evidence-chain builder、source-context projector、Diagnostic projector、summary reducer、referential-integrity validator、serializer、renderers 和 artifact publisher 的每个新增或实质修改业务模块 SHALL 登记到机器可读 test inventory，并 SHALL 具有直接实例化该模块的隔离 unit suite。第三方 JSON Schema validator、文件读取、文件 replace 和 pipeline/projector 边界 SHALL 使用 fake、mock 或临时目录；component、contract、AVX 和端到端测试 MUST NOT 替代单元测试。

#### Scenario: 执行逐模块覆盖门禁
- **WHEN** `kb-scanner-test` 容器运行 schema v2 projection unit inventory
- **THEN** inventory 中每个业务模块 SHALL 被对应 isolated unit suite 执行并达到至少 90% line 和 80% branch coverage
- **AND** 缺失模块映射、未执行测试、覆盖不足或只由高层测试间接覆盖 SHALL 使门禁失败

#### Scenario: 验证投影无副作用
- **WHEN** fixture 包含可执行 build/test 文本、路径穿越候选、恶意 renderer 内容或失败的 artifact replace
- **THEN** 单元与 component tests SHALL 证明 v2 投影只读 snapshots 和项目根内源码上下文，并在失败时回滚 artifact
- **AND** scanner MUST NOT 执行项目命令、访问网络、修改输入、安装本机依赖或发布半套结果

### Requirement: Schema V2 必须在 Finding 内自包含展示架构枚举链路
Schema V2 Projector SHALL 将架构枚举结论投影为 `fact.kind=architecture_probe`，并 SHALL 使用现有 `source_evidence` step 与 `defines`、`contains`、`selects`、`guarded_by`、`matches_knowledge` edge 表达 enum declaration、member、reference、condition 和 downstream dependency。enum 特有字段 SHALL 位于合法 `org.rvport.kb-scanner.architecture-enum` extension；Projector MUST NOT 增加未经 schema 定义的核心 fact/step/edge kind 或要求消费者读取内部 snapshots。

#### Scenario: 用户查看 constexpr 架构枚举 Finding
- **WHEN** v2 Projector 接收完整 enum selection Classification
- **THEN** 单个 Finding SHALL 展示 enum 定义、member declaration/reference、condition、下游 x86 Evidence 的真实源码关系，Knowledge 留在旁支，分类评估留在 conclusion/summary
- **AND** 每个代码 step SHALL 携带自己的完整 span、真实行号上下文和命中高亮

#### Scenario: 枚举链路只有候选证据
- **WHEN** enum member/reference 可验证但 downstream 或 target selection 仍未知
- **THEN** Finding conclusion 与 evidenceChain SHALL 标记 unknown/partial，包含指向具体缺失证据而非分析阶段伪节点的稳定 break 和 reason
- **AND** summary MUST NOT 将其计为 blocking 或从其缺失推断 ready

#### Scenario: 旧 V2 consumer 忽略 enum extension
- **WHEN** consumer 不认识 `org.rvport.kb-scanner.architecture-enum` extension
- **THEN** consumer SHALL 仍能依据 Schema V2 核心 `architecture_probe`、`source_evidence`、source/context 和既有 edges 验证并展示 Finding
- **AND** extension MUST NOT 覆盖或改变核心字段、引用与状态语义

#### Scenario: 多个成员引用聚合为一个根因
- **WHEN** 同一 enum member 根因在多个 condition/case 位置被引用
- **THEN** Finding SHALL 无损保留全部 occurrences，确定性选择 primary occurrence，并在 chain 中保留各自上下文
- **AND** Finding 计数与 occurrence 计数 MUST 保持区分

#### Scenario: 枚举引用闭包无效
- **WHEN** declaration/member/condition/downstream 任一引用缺失、类型冲突或超过预算
- **THEN** Referential Integrity Validator SHALL 阻止无效 step/edge/path 进入序列化结果，并保留可验证局部 Finding 与 Diagnostic
- **AND** Projector MUST NOT 回退到 V1、Legacy 或字符串 trace 补造链路

### Requirement: Unknown candidate 必须在结论和链路中一致表达
V2 SHALL 对所有未决 candidate（包括 identifier 与 enum）一致表达 unknown completeness/conclusion/chain，并以语义一致的中文 suggestion 与英文 suggestion_en 提示当前无法确定执行架构依赖，可由后续分析补齐。schemaVersion 与 V1 合同 SHALL 保持不变；suggestion_en SHALL 依本 capability 的双语合同作为历史读取可省略、当前生产必填的字段。

#### Scenario: codec 名称只有候选证据
- **WHEN** Classifier 对 identifier candidate 返回 unknown
- **THEN** V2 conclusion 与 chain SHALL 保持 unknown，且 suggestion 与 suggestion_en MUST NOT 宣称已确认需要替换实现
- **AND** fact、occurrence、上下文和知识来源 SHALL 保留

### Requirement: Intrinsic 与替代标签必须具有对应证据
V2 SHALL 只将对应 symbol/call Evidence 精确命中的适用 intrinsic/builtin 知识标为 intrinsic_call；普通调用 SHALL 为 source_evidence。相同 kind 或 _mm 前缀 MUST NOT 构成 intrinsic/alternative_to 证明。

#### Scenario: 普通函数与真实 intrinsic 混合
- **WHEN** 同链有普通 checksum 函数、伪 _mm 名称与知识确认调用
- **THEN** 仅适用精确知识调用 SHALL 标 intrinsic，辅助调用不能抢占主 fact
- **AND** 真实行号/context/highlight 与引用 SHALL 保持

#### Scenario: 相同 kind 和真实 alternative relation
- **WHEN** 同链多个代码节点具有相同 kind
- **THEN** 节点 SHALL 保持独立位置和身份；没有实际关系的节点之间 MUST NOT 生成 contains、alternative_to 或其他伪 edge，只有可定位两端的 Analysis alternative_to relation 才可生成相应替代 edge
- **AND** 不新增核心 kind/必填字段、候选选项 extension 或第二主结果

### Requirement: 源码主链边必须具有实际端点与稳定来源
V2 SHALL 从 matched Evidence 和 occurrence/configuration 驱动闭包，primaryPath SHALL 包含当前锚点并由真实关系连通。每条代码 edge SHALL 对应实际 Relation 端点或可验证的连续结构关系折叠；方向变换 SHALL 使用显式语义映射并保留完整来源，MUST NOT 用任意 relation ID、节点类型排序或名称相似代替证明。

#### Scenario: 同类宏连续展开
- **WHEN** 两层以上 macro definition 经真实 expansion 连接到同一 intrinsic
- **THEN** 链 SHALL 保留所有层及其独立位置，不按 kind 去重
- **AND** 输入 Evidence/Relation 顺序变化 SHALL 不改变 primaryPath 和稳定 ID

#### Scenario: 保护关系方向映射
- **WHEN** 底层 guarded_by 由被保护对象指向条件，而展示按条件到命中排列
- **THEN** 投影 SHALL 通过规定的映射表达条件到对象的 selects，并保留原始 Relation 及端点方向依据
- **AND** 条件是否 selected/unknown SHALL 取自分析证据，不能由展示方向推断

#### Scenario: 多条非等价上游
- **WHEN** 相同 occurrence 存在多个无法静态消歧的上游
- **THEN** steps/edges SHALL 保留预算内的候选并标记 ambiguous/unknown
- **AND** primaryPath SHALL 是确定性选取的可验证局部路径，不能拼接无连接候选或声称唯一启用来源

### Requirement: 上下文预算必须保护命中并有界缓存
source context SHALL 默认使用 beforeLines=20、afterLines=20、maxLines=256、maxCharacters=65536，字符数按输出文本字符计算。读取/拆行 SHALL 按文件缓存，重复 span/window SHALL 复用结果；缓存不得跨扫描复用过期源码。裁剪 SHALL 优先命中再分配邻近前后文，超过预算 SHALL 保留原始 span 并显式 partial/unavailable，MUST NOT 输出越界高亮或静默裁掉命中后声称 complete。

#### Scenario: 接近文件首尾
- **WHEN** 命中前后不足 20 行
- **THEN** 返回窗口 SHALL 只包含实际存在的行，不补空行也不越界
- **AND** 仅因文件首尾自然收缩 MUST NOT 标记预算截断

#### Scenario: 多行命中或单行超长
- **WHEN** 命中范围或某条文本超过硬预算
- **THEN** 输出 SHALL 有界、保留完整原始 span 并给出截断原因，无法显示的命中不得伪造 highlights
- **AND** 普通上下文 MUST NOT 挤掉在预算内可显示的命中，单条超长行不得绕过字符上限

#### Scenario: 同一位置被多个对象引用
- **WHEN** fact、occurrence 和多个 step 重复投影相同文件/span
- **THEN** 每文件 SHALL 至多一次读取/拆行，相同 span/window SHALL 共享内部缓存而输出仍自包含
- **AND** 不同 span 的高亮 MUST NOT 相互污染，根外路径 MUST NOT 触发读取

### Requirement: 源码链修订必须原子迁移 V2 合同
本修订 SHALL 保留 schemaVersion 2.0、默认 V2/显式 V1、Finding 核心结构和三个 artifact，SHALL 同步模型、Schema、reference rules、vocabulary、examples 和迁移文档。impactStepIds SHALL 接受空数组，历史非空值仍须正确引用历史 classification/assessment step；生产输出 SHALL 无这些阶段节点。旧严格 V2 validator 的预算和非空约束不兼容 SHALL 在文档中明确，不得声称完全向后兼容。

#### Scenario: 新旧 V2 校验
- **WHEN** 更新后的校验器接收新源码链或有效历史阶段链
- **THEN** 两者 SHALL 依各自合法形状被接受，悬空 impact/edge/primaryPath 引用仍 SHALL 被拒绝
- **AND** 生产回归 SHALL 单独断言不再生成分类评估节点及连线，不能以历史读入兼容放过旧生成行为

#### Scenario: 纯投影变更与新增证据分别审校
- **WHEN** 同一 staged snapshots 使用新旧投影，或新的宏作用证明改变了分析结果
- **THEN** 前者 SHALL 保持事实、classification/conclusion 与 assessment/summary 语义，后者 SHALL 逐项记录有依据的结论变化
- **AND** 两份 compiler JSON 哈希、V1 字段合同和静态边界 SHALL 保持不变，人工 oracle MUST NOT 自动重写

### Requirement: V2 新生成结果必须包含成对的中文和英文建议
V2 Projector SHALL 在每个新生成 Finding 的 conclusion 中输出非空中文 `suggestion` 和同级非空英文 `suggestion_en`，两者 SHALL 表达同一建议及相同的证据确定程度。语言字段含义 MUST NOT 随 locale 交换或只输出其中一种语言；建议 SHALL 在展示层由确定性成对模板生成，不调用网络翻译、V1 mapper 或重新执行分析。

#### Scenario: 默认与非默认 locale 均输出固定语言字段
- **WHEN** 同一 snapshots 分别通过默认 locale、en-US 或其他现有可接受 locale 生成 V2 报告
- **THEN** 每个 conclusion SHALL 同时包含中文 suggestion 与英文 suggestion_en，两字段的文案选择 SHALL 一致
- **AND** status、findingType、ID、reason、源码符号和其他机器字段 MUST NOT 因建议语言发生变化

#### Scenario: 新生产结果遗漏英文建议
- **WHEN** 生产映射遗漏 suggestion_en，或任一新建议为空白
- **THEN** 生产边界 SHALL 拒绝发布该无效报告并沿既有错误处理返回失败
- **AND** reader 允许历史省略字段的规则 MUST NOT 被用来接受该新生产缺陷

### Requirement: 双语建议必须服从已有结论并保持静态边界
建议策略 SHALL 使用已有 classification impact、conclusion status 和 findingType 选择措辞，unknown/partial/ambiguous SHALL 优先给出补证据建议，inactive SHALL 保留排除条件，hint SHALL 提醒核实事实，已确认依赖或缺口 SHALL 给出相应迁移建议。策略 MUST NOT 改变分析结论、把候选升级为确定依赖、把非阻断项称为确定阻断，或声明真实编译/测试已执行。

#### Scenario: 证据不足或者存在歧义
- **WHEN** 结论为 unknown、partial 或 ambiguous，包括非 candidate 状态但证据仍不足的项目
- **THEN** 两种建议 SHALL 要求保留事实并补齐证据后再判断，不直接断言必须替换实现
- **AND** 文案 MUST NOT 把所有未知项默认称为 codec 或数据格式名称

#### Scenario: 路径已被排除
- **WHEN** 已有结论为 inactive 或 guarded_inactive
- **THEN** 双语建议 SHALL 说明当前路径由静态证据排除、保留相关条件并在配置变化时复核
- **AND** 建议 MUST NOT 要求无条件替换该路径，也 MUST NOT 声称项目整体已就绪

#### Scenario: 提示和非阻断局部依赖
- **WHEN** Finding 为 hint 或已确认局部但未证明目标必选的 actionable_non_blocking
- **THEN** 建议 SHALL 分别要求结合源码核实线索或核查目标适用性，按需处理依赖
- **AND** 两种语言 SHALL 均不声称已确定阻断或已完成目标编译

#### Scenario: 已确认依赖和迁移缺口
- **WHEN** 完整结论为 blocking_issue，或已有 findingType 表示目标选择/测试覆盖缺口
- **THEN** 建议 SHALL 分别指向处理已选中的 x86 依赖、核查目标选择分支或测试资产/选择路径
- **AND** 测试覆盖建议 MUST NOT 声称测试已经运行或通过

#### Scenario: 缺失 observation 或未知 findingType
- **WHEN** 可投影 Finding 缺少 observation 或其 findingType 不在已知模板特例中
- **THEN** 策略 SHALL 根据已有结论采用保守、非空的双语兜底
- **AND** 它 MUST NOT 丢弃 Finding、伪造新分析结论或回退到仅英文模板

### Requirement: 双语建议合同必须区分历史读取与当前生产
V2 SHALL 保持 schemaVersion 2.0，并在 Conclusion 模型和 JSON Schema properties 声明 suggestion_en 为可省略的非空英文建议字段；通用 reader SHALL 接受历史缺失，但显式 null、空白或非字符串 SHALL 被拒绝。新 producer SHALL 始终填充双语字段。迁移文档 SHALL 明确旧封闭 Schema 对新增字段的不兼容，不得声称旧严格消费者无需升级。

#### Scenario: 历史报告只有 suggestion
- **WHEN** 更新后的 reader 读取合法旧 V2 报告，suggestion 仍为英文且缺少 suggestion_en
- **THEN** 读取 SHALL 成功，原文和字段缺失语义 SHALL 保持，往返序列化不添加伪造英文或 null
- **AND** 新 producer 的中文要求 MUST NOT 被用于拒绝合法历史英文建议

#### Scenario: 新字段类型或内容不合法
- **WHEN** suggestion_en 被显式设置为 null、空字符串、纯空白或非字符串
- **THEN** 更新后的模型和 Schema 合同 SHALL 一致拒绝该输入
- **AND** 合法历史省略字段与显式非法值 SHALL 被区分

#### Scenario: 旧严格消费者接收新结果
- **WHEN** 消费者仍使用不含 suggestion_en 且 additionalProperties=false 的旧 V2 conclusion Schema
- **THEN** 迁移记录 SHALL 明确要求先升级 Schema/模型
- **AND** 本 change MUST NOT 自动修改后端、前端或持久化结果以绕过该边界

### Requirement: 建议汉化必须保持现有报告其余内容与默认中文展示
同一 snapshots 的新旧 V2 JSON SHALL 仅允许 conclusion.suggestion 文案变化和新增 conclusion.suggestion_en，其他结论字段、ID、facts、occurrences、evidenceChain、summary 和 diagnostics MUST 保持不变。HTML SHALL 默认展示 suggestion 的中文内容并继续安全转义；显式 V1、scan.log、三个 artifact 名称及 GCC/Clang 事实数据 MUST 保持现有合同。

#### Scenario: JSON 与 HTML 建议一致
- **WHEN** 新 V2 结果输出 JSON 和 HTML，建议中含中文、技术标识或 HTML 特殊字符
- **THEN** JSON SHALL 保留语义一致的双语字段，HTML SHALL 正确显示中文 suggestion 并安全转义
- **AND** HTML MUST NOT 用 suggestion_en 替换默认建议，也不要求新增英文列或语言切换 UI

#### Scenario: 对比双语修订前后报告
- **WHEN** 固定 snapshots 或固定输入完成双语修订前后对照
- **THEN** 仅移除允许变化的两个建议字段后，V2 报告 SHALL 全字段相等，V1 与知识哈希 SHALL 不变
- **AND** 回归账本 SHALL 记录允许的文案/字段变化，不能自动重写无法解释的 golden 或修改原始源码

### Requirement: 双语建议必须通过独立单元覆盖与兼容合同验收
每个新增/实质修改的建议策略、mapper、model、producer validator/projector 或 renderer 业务模块 SHALL 登记隔离 unit suite，覆盖正常、边界和异常路径，并在独立 kb-scanner-test 容器达到项目整体及每个受影响模块至少 90% 行/90% 分支覆盖率。统计 SHALL 包含未加载的 kb_scanner/scripts/tools 自有可执行源码，排除项必须有明确理由，合同/组件测试 MUST NOT 替代隔离单元覆盖。

#### Scenario: 执行建议模块门禁
- **WHEN** 容器运行默认自动化与本 change 的受影响模块单元门禁
- **THEN** 全部语言对、优先级、兜底、新 producer 必填和历史 reader 缺省反例 SHALL 有有效断言且满足覆盖门槛
- **AND** 未加载源码 SHALL 纳入分母，真实 parser/pipeline 组件结果 MUST NOT 被计为隔离单元数字

#### Scenario: 验收合同与差异回归
- **WHEN** 执行新旧 V2、中文 HTML、V1、AVX/enum/RPM/候选及既有完整回归
- **THEN** 结果 SHALL 有可复跑命令、测试记录、整体/逐模块覆盖、统计范围和持久报告路径
- **AND** 验证失败或覆盖不足 SHALL 保持任务未完成；所有测试 MUST NOT 安装本机依赖、执行被扫描项目命令或更新生产容器

### Requirement: 风险投影必须保留不确定性而不修改结果结构
V2 SHALL 使用统一内部决策投影 severity、status、actionable、blocking 与 archReachability，不再仅按 impact 将 actionable_non_blocking 固定映射 medium 或把 unknown 兜底为 low/complete。高风险且上游部分缺失 SHALL 可以 actionable=true、blocking=false、status=partial/unknown。SchemaVersion 2.0、既有核心字段/枚举、默认 V2/显式 V1 和三个 artifact SHALL 保持；V1 SHALL 从同一内部风险策略适配既有字段，V2 MUST NOT 依赖 V1 payload。

#### Scenario: 局部依赖高风险但目标未知
- **WHEN** Classification 确认局部 x86 依赖但目标适用性未闭合
- **THEN** V2 SHALL 输出 high、partial/unknown、actionable=true、blocking=false，并用已有 reason/chain break 表达缺口
- **AND** 双语建议 SHALL 区分依赖已确认和目标适用性待核查，不声称已验证阻断

#### Scenario: 未决候选和未知枚举值兜底
- **WHEN** 候选分类未决或生产映射无法识别内部风险决策
- **THEN** 未决候选 SHALL 输出 medium 待核查与未知状态；无效内部决策 SHALL 产生明确诊断或按既有发布边界拒绝
- **AND** MUST NOT 静默以 low/complete 发布无依据的结论

### Requirement: CMake 证据链必须显示真实上游且保持兼容
V2 SHALL 使用现有 source/build step、edge、上下文和命名空间 extensions 表达 CMake 条件、变量、目标、源码和参数作用，不新增核心必填字段或 kind；代码节点 SHALL 有自己的 span、高亮和默认上下各 20 行。配置拒绝 SHALL 展示条件到实际 fatal 的链；后续声明不得拼造为该次配置 selected。classification/assessment MUST NOT 回到 evidenceChain。

#### Scenario: 展开 CMake 参数驱动的命中
- **WHEN** 参数到 target/source、条件宏和 intrinsic 关系完整
- **THEN** 单个 Finding SHALL 自包含展示真实连通链与知识旁支
- **AND** 关系不完整时 SHALL 保留可验证局部链及明确断点，不按节点种类拼接

#### Scenario: 固定首次扫描审校
- **WHEN** 对 demo-test1 首次源码版本执行新旧审校及 V1/V2/HTML/log 合同测试
- **THEN** SHALL 逐项记录原 19 项及新增 CMake 事实的风险/状态/依据变化，而非要求全部为 high/blocking
- **AND** 两份 compiler JSON 哈希、既有字段合同、静态范围及中文/英文建议合同 SHALL 保持，历史数据不得自动改写

### Requirement: 架构家族必须通过既有 extension 自包含展示且不伪造源码

V2 SHALL 使用现有 `extensions` 合同及 `org.rvport.kb-scanner.architecture-family` namespace 输出有界候选目录，并在相关 Finding 的 fact.extensions 内嵌必要家族上下文。核心 schemaVersion、必填字段和枚举 MUST 保持不变；单个 Finding 的解释 MUST NOT 依赖顶层目录或内部 snapshot。纯路径成员 MUST NOT 伪装成代码 fact、occurrence 或 step。

#### Scenario: 用户仅打开一个 intrinsic Finding

- **WHEN** 该 Finding 所在 source file 有架构家族候选
- **THEN** SHALL 在 Finding 内提供成员路径、角色依据、候选/绑定状态及范围，而无需查询顶层 catalog
- **AND** 原始 intrinsic 命中、真实源码链、上下各 20 行及双语 suggestion SHALL 保持

#### Scenario: 只有文件名无命中行

- **WHEN** 成员仅有文件系统路径依据或文件为空
- **THEN** SHALL 在 extension 描述路径，不填写虚假的第 1 行或高亮
- **AND** 不存在迁移 Finding 的家族 SHALL 仍通过有界顶层 extension 可读

#### Scenario: 引用和候选裁剪

- **WHEN** 家族成员或 proof 输出超过预算，或无法在 Finding 内闭合引用
- **THEN** SHALL 记录裁剪/未知原因与计数，仅输出可核查结构描述及有效引用
- **AND** MUST NOT 发布悬空 typed ref 或把未输出成员解释为不存在

#### Scenario: 已有其他 extension

- **WHEN** Finding 同时带有 RPM、Autoconf 或架构枚举补充
- **THEN** 新家族 extension SHALL 合并而非覆盖既有 namespace 内容

### Requirement: 家族展示必须保持双语与既有报告兼容

新增面向用户的候选解释 SHALL 同时提供中文与英文，HTML SHALL 安全转义路径并以中文呈现有界摘要。默认 V2、显式 V1 和 JSON/HTML/log 三个 artifact SHALL 保持；V1 MUST NOT 被强制加入路径-only 代码 Finding 或新增必填字段。

#### Scenario: 旧消费者或显式 V1

- **WHEN** 消费者忽略 extension 或用户选择 V1
- **THEN** 原有 Findings、源码位置和风险结论 SHALL 继续可消费，不要求新后端接入

#### Scenario: 恶意文件名与纯路径摘要

- **WHEN** 家族成员路径包含 HTML 特殊字符且没有代码位置
- **THEN** HTML SHALL 转义展示路径与候选说明，不执行内容、不生成虚假源码链接

### Requirement: 函数多版本必须在既有 extension 内自包含展示

V2 SHALL 通过 `org.rvport.kb-scanner.function-multiversion` 输出有界 catalog 和单 Finding 内的版本上下文，分别展示机制、身份/来源、default 声明/定义状态、局部依赖、选择及适用性。新检查 SHALL 使用已有 architecture_probe 等合法 fact/step/edge kind，不增加核心 schema 必填字段或枚举；原 intrinsic fact SHALL 保持。合法 extension SHALL 与现有 namespace 合并。

#### Scenario: 离线查看一个 Finding
- **WHEN** 用户仅打开一个关联多版本的 intrinsic 或属性检查 Finding
- **THEN** SHALL 无需读取 catalog/内部 snapshot 即可看到相关版本、各自来源及状态原因
- **AND** 引用 SHALL 在本 Finding 内闭合；不能闭合时以真实路径/span 描述和 unknown 表达，不输出悬空 ID

#### Scenario: 没有新增问题但有 default 组
- **WHEN** 组具有可定位结构，但不存在应新增的迁移问题
- **THEN** SHALL 可在顶层有界 extension/HTML 摘要中展示
- **AND** MUST NOT 仅为了展示组而制造 blocker 或复制代码 Finding

### Requirement: 多版本源码链和双语展示必须保持兼容与真实位置

多版本相关链 SHALL 只使用真实属性、声明、定义及有来源的关系，保留每节点 span、高亮和上下各 20 行；生成的 clone/resolver MUST NOT 拥有伪造源码位置。新增用户解释/标题/建议 SHALL 成对提供中文/英文，遵循既有 suggestion/suggestion_en 合同；无核心配对字段的展示数据 SHALL 放入 namespace，不改变核心 schema。默认 V2、显式 V1 与 JSON/HTML/log artifact SHALL 保持。

#### Scenario: Clone 共享源函数体
- **WHEN** 多个版本描述对应一个真实 body
- **THEN** SHALL 以结构描述引用该 body，源码 occurrence 不按版本数倍增
- **AND** classification/assessment SHALL 留在结论及摘要，不能进入 evidenceChain

#### Scenario: 裁剪或恶意源码文本
- **WHEN** 版本/来源超预算或函数名、属性参数含 HTML 特殊字符
- **THEN** SHALL 有界裁剪并标记原因/计数，HTML SHALL 安全转义且默认中文展示
- **AND** MUST NOT 将未显示 default 解释为缺失，或通过新增后端输入才能解释当前 Finding

#### Scenario: 无相关构造的既有报告
- **WHEN** 固定输入没有受支持多版本构造
- **THEN** 除允许的空/缺省 extension 表达外，V1/V2 原始事实、结论、计数和源码链 SHALL 保持
- **AND** 有多版本输入的真实变化 SHALL 有逐字段人工差异记录，不自动改写 oracle

### Requirement: 用途说明与候选排除审计必须使用既有扩展合同

V2 SHALL 在 `org.rvport.kb-scanner.candidate-usage` extension 内提供有界用途摘要。保留的 Finding SHALL 自包含当前事实用途与来源；被排除的候选 SHALL 通过顶层 excludedCandidates 审计表达，不伪造 low Finding。核心 schemaVersion、required 字段和枚举 MUST 保持不变。

#### Scenario: 查看一个未知候选

- **WHEN** 用途闭包有局部数据来源但仍缺调用、配置或逃逸证据
- **THEN** 单个 Finding SHALL 包含可验证的本地来源、unknown 原因和预算信息，而无需另查顶层目录
- **AND** 不增加 classification/assessment/抽象 role 代码节点，不把未知链展示为完整执行证明

#### Scenario: 候选已从迁移分类排除

- **WHEN** 完整纯数据证明使对应 Classification 被省略
- **THEN** 顶层扩展 SHALL 保留有界事实根、配置、原因及真实来源，并区分排除总数、展示数和省略数
- **AND** 原 Observation 与 Fact SHALL 保留，审计不得依赖悬空内部 typed ref 或暗示项目已 ready

### Requirement: 用途展示必须双语有界并保持旧工件兼容

新增用户可见说明 SHALL 同时提供中文和英文，HTML SHALL 默认中文并安全转义；真实代码来源 SHALL 保持默认上下各 20 行和命中高亮，并受现有硬预算约束。默认 V2、显式 V1 与三个 artifact SHALL 保持，V1 不新增必填字段。

#### Scenario: 多用途或来源裁剪

- **WHEN** 多 occurrence、闭包来源或排除审计超过展示上限
- **THEN** SHALL 显式记录裁剪和计数，保留必要事实锚点，不用展示裁剪改变已验证结论
- **AND** 不得复制其他 Evidence 位置或自动合并不同配置

#### Scenario: 合同与报告差异验收

- **WHEN** 执行固定输入新旧 V1/V2/HTML/log 对照
- **THEN** SHALL 逐字段解释实际分类/证据/审计变化，更新扩展文档和合同示例，保留原人工 ledger
- **AND** 无候选输入报告 SHALL 不因本能力变化，事实资产哈希、静态边界与旧消费者忽略 extension 的能力 SHALL 保持

### Requirement: 宏构建作用链必须展示真实多来源且隔离不同 TU
V2 SHALL 在单个 Finding 的既有 evidenceChain/occurrences 中展示实际构建参数来源、引用/使用点、include、条件、调用/定义、实参与 replacement token，并保留 TU/configuration 区别。每条边 SHALL 有连续可验证的分析来源；primaryPath SHALL 只选择实际连通局部路径，不把多个实参或不同 TU 的路径串成一条执行链。

#### Scenario: 分散参数来源和多层包装
- **WHEN** 一个参数来自两个变量赋值，实际使用后启用经参数传递包装的 intrinsic
- **THEN** Finding SHALL 展示各来源各自的文件/span/context 和真实连接，不伪造拼接 token 的原始行列
- **AND** 所有码型来源 SHALL 默认带上下各 20 行及命中高亮，继续遵守既有行数/字符预算

#### Scenario: 多配置结果相反
- **WHEN** 同一头文件锚点在一个编译使用实例中 selected，在另一个实例中 inactive 或 unknown
- **THEN** V2 SHALL 保留相应分支、来源与状态，不用一个完整 occurrence 掩盖另一个断点
- **AND** 查询预算不足时 SHALL 显式记录裁剪，不能把未展示路径解释为不存在

### Requirement: 宏作用扩展必须保持 V2 核心合同和中英文说明
本轮 SHALL 复用现有源码/build step 与 edge 类型、断点和可选 namespace extensions，不新增核心 required 字段、kind 或 schemaVersion；扩展 provenance SHALL 自包含且有界。新增用户可读说明 SHALL 同时提供中文及英文字段，suggestion/suggestion_en 合同 SHALL 保持。classification/assessment MUST NOT 出现在源码证据链，knowledge SHALL 仍为实际命中的旁支。

#### Scenario: 老消费者与显式 V1
- **WHEN** 默认 V2 或显式 V1 生成 JSON/HTML/log
- **THEN** V2 基本源码链 SHALL 无需后端新接入即可读取，V1 SHALL 不增加 V2 图必填字段，三个 artifact 与原子发布 SHALL 保持
- **AND** 因新证据改变风险/状态的项目 SHALL 有逐项审校记录，不能用兼容名义冻结错误结论或自动改写历史报告

#### Scenario: 原有功能回归
- **WHEN** 运行既有候选用途、函数多版本、架构家族及源码链样例
- **THEN** 不受新证明影响的结论和其他扩展 SHALL 保持；变化 SHALL 区分事实、关系、分类与纯展示并记录依据
- **AND** 不得为减少体积而删除原始事实、缩短正常 20/20 上下文或省略 unknown 原因

### Requirement: 测试内容必须在既有 Finding 合同中自包含展示

V2 SHALL 通过 org.rvport.kb-scanner.test-content 可选 namespace 展示测试身份、编译/注册/内容各自状态、来源、用途、proof 完整性与 unknown 原因。相关 Finding SHALL 自包含，不依赖另读内部快照或顶层目录；核心 schemaVersion、required 字段及 fact/step/edge enum MUST 保持。新 namespace SHALL 与既有扩展合并。

#### Scenario: 打开一个测试相关 intrinsic Finding

- **WHEN** 该 intrinsic 经受支持的注册、构建、入口及断言关联
- **THEN** 单 Finding SHALL 展示真实构建/注册位置、源码条件/调用/断言与命中位置，引用闭合
- **AND** 编译依赖与测试内容关联 SHALL 分别说明，不伪造测试执行结果

#### Scenario: 只有部分链或没有新增迁移问题

- **WHEN** 证据缺注册、调用唯一性、宏环境或达到预算
- **THEN** SHALL 显示具体断点、裁剪及可用来源，不拼接不同配置为完整路径
- **AND** 仅需展示测试摘要时 MUST NOT 为此制造 low Finding 或重复原问题

### Requirement: 测试源码链必须双语有界并兼容旧消费者

源码 evidenceChain SHALL 只包含真实 source/build 位置及可验证连接；抽象测试角色、classification、assessment MUST NOT 伪装成代码步骤。各代码锚点 SHALL 保留上下各 20 行、命中高亮与既有裁剪规则。新增展示说明 SHALL 中英文成对，保持 suggestion/suggestion_en、默认中文和安全转义；默认 V2、显式 V1 及三个工件 SHALL 保持。

#### Scenario: 注册行与断言行跨文件

- **WHEN** add_test、target source、架构条件和断言位于不同文件
- **THEN** SHALL 分别保留真实 span/context，并只连接有真实来源的上游
- **AND** 不同来源 MUST NOT 复用同一伪造位置或强行串成一条 primaryPath

#### Scenario: 兼容、转义与配置差异

- **WHEN** 老消费者忽略 extension、用户选择 V1，或名称包含 HTML 特殊字符
- **THEN** 原有必需结构 SHALL 可消费，HTML SHALL 安全转义并保持默认中文
- **AND** 新旧输出差异 SHALL 有逐项事实/关系/分类/展示审校，变化不得通过自动覆盖 oracle 获得批准
