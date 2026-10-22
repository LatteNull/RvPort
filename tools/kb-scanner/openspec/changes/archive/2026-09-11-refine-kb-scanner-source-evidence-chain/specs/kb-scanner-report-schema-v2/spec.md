## MODIFIED Requirements

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

## ADDED Requirements

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
