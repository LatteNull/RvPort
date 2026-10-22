## ADDED Requirements

### Requirement: schema v2 必须提供 Finding-centric 且自包含的扫描结果
KB Scanner schema v2 SHALL 使用 `schemaVersion: "2.0"`，并 SHALL 使每个 Finding 直接包含 `fact`、`conclusion`、`occurrences[]` 和 `evidenceChain`。`evidenceChain` SHALL 携带解释该 Finding 所需的完整相关 step、edge、主路径、分支和断点；消费者 MUST NOT 依赖顶层 Explanation/Catalog、scanner 内部 snapshot 或自由形态 `trace` 才能解释单个 Finding。

#### Scenario: 消费者离线读取完整结果
- **WHEN** scanner 产生一个引用完整的 schema v2 artifact
- **THEN** 消费者 SHALL 能仅凭单个 Finding 读取事实、全部 occurrence、主证明链、底层 Evidence 投影、知识 provenance 和 Assessment 影响
- **AND** Finding 内每个 step、edge、path、occurrence 和 typed provenance reference SHALL 在该 Finding 中完整且类型匹配

#### Scenario: 多个 Finding 共用同一证据
- **WHEN** 多个 Finding 引用相同 Evidence、KnowledgeEntry 或 ProofPath
- **THEN** 每个 Finding SHALL 各自携带与自身有关的紧凑 step projection，并对相同底层对象使用相同稳定 provenance ID
- **AND** 单个 Finding MUST NOT 携带与自身无关的项目图；后端 MAY 按稳定 ID 缓存重复对象但不得要求消费者额外查询

### Requirement: 每个 Finding 必须直接包含可展示的 evidenceChain
每个 schema v2 Finding SHALL 直接包含 evidenceChain。evidenceChain SHALL 包含 status、reason code、root step、按语义顺序排列的 `primaryPath[]`、全部 `steps[]`、关系 `edges[]`、`breaks[]` 和 Assessment impact step，使前端可以默认展示主链并在同一 Finding 内展开全部相关证据。

#### Scenario: selected 源码调用 AVX intrinsic
- **WHEN** 完整静态 proof 连接配置 selector、target、source、intrinsic Evidence、compiler-derived knowledge、Classification 和 Assessment
- **THEN** evidenceChain primaryPath SHALL 按该因果顺序引用全部 step 并标记 complete
- **AND** 前端 SHALL 无需自行遍历任意关系图来猜测主链

#### Scenario: 用户展开宏调用 Finding
- **WHEN** Finding 根因是经本地宏定义和 replacement 到终端 x86 intrinsic 的调用
- **THEN** 主链 SHALL 包含调用、定义、replacement、终端 symbol 和 knowledge match step
- **AND** 每个代码型 step SHALL 直接包含自己的完整 source span、逐行代码上下文和命中高亮

#### Scenario: x86 路径对目标 inactive
- **WHEN** 完整互斥 proof 表明 x86 source 或 build item 未被目标配置选中
- **THEN** evidenceChain SHALL 明确标记 inactive/guarded 并展示排除它的 selector/condition 链
- **AND** Finding MUST NOT 被展示为 actionable blocker

### Requirement: 每个代码型 fact、occurrence 和 chain step 必须携带可定位上下文
schema v2 SHALL 为每个有源码或构建文件依据的 fact、occurrence 和 evidenceChain step 提供项目相对文件路径、完整 start/end span、`context.lines[]` 中的真实行号与文本，以及 `highlights[]` 中的命中行列范围。代码上下文 SHALL 使用有界窗口；没有源文件的 knowledge、Classification 和 Assessment step MUST 保留 provenance/reason/status 且不得伪造位置。

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
本设计 capability SHALL 提供 JSON Schema 2020-12、引用完整性规则、字段词汇表、v1/v2 合同差异与消费者迁移清单，以及 complete、partial、ambiguous、inactive、unknown 和 AVX explanation 示例。后续 v2 Projector SHALL 直接消费 staged pipeline snapshots，MUST NOT 读取或转换 schema v1 结果。所有资产 SHALL 在唯一 `kb-scanner-test` 容器中验证，且本 change MUST NOT 接线生产 serializer 或改变默认 CLI。

#### Scenario: 执行 schema 设计合同门禁
- **WHEN** 独立测试容器验证 v2 设计资产
- **THEN** 所有正例 SHALL 通过 JSON Schema 与引用完整性验证，所有定向反例 SHALL 因预期 reason 失败
- **AND** schema、example、mapping 或 vocabulary 漂移 SHALL 使门禁失败

#### Scenario: 验证真实 AVX explanation 示例
- **WHEN** 合同测试读取人工审计的 AVX 主链示例
- **THEN** 示例 SHALL 在单个 Finding 内展示 build/source、macro 或 intrinsic Evidence、knowledge、Classification 和 Assessment 的可解析链路及逐行代码上下文
- **AND** 示例 MUST NOT 以 Finding 总数代替字段和引用正确性
