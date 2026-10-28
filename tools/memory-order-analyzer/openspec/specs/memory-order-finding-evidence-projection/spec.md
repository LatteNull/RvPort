# Memory Order Finding Evidence Projection Specification

## Purpose

定义面向后端与前端的自包含内存序 Finding、证据链、源码上下文与不可变 provenance 投影合同，使展示层无需理解内部分析阶段即可审计结论。

## Requirements

### Requirement: Publish a self-contained memory-order Finding projection
系统 SHALL 定义独立版本化的 `MemoryOrderFindingProjection`。每个投影 MUST 自包含 `id`、`fact`、`conclusion`、`occurrences`、`primaryOccurrenceId` 和 `evidenceChain`，使后端和前端无需读取或拼接 P1–P4、A1–A6、R1–R3 内部产物即可展示结论和完整依据。

#### Scenario: Frontend opens a finding detail
- **WHEN** 消费者取得一个 `MemoryOrderFindingProjection`
- **THEN** 它可以从同一对象展示主事实、结论、所有位置、默认位置、证据主路径、分支、断点和代码上下文
- **AND** 不需要按内部 stage ID 查询其他业务协议

#### Scenario: Projection references detailed artifacts
- **WHEN** Finding 需要支持离线审计或扩大上下文
- **THEN** 投影以稳定 kind、ID、producer 和 digest 引用内部产物及源码快照 artifact
- **AND** 这些引用不得替代投影自身的首屏证据和代码窗口

### Requirement: Keep the structure compatible with KB Scanner v2 consumption without sharing domain semantics
Finding、source location、evidence chain、step、edge、break 和 budget 的结构 SHALL 借鉴 KB Scanner `scan-result-v2` 的消费形状，使通用列表、证据链和代码上下文组件可以复用。memory-order schema MUST 使用独立 `$id`、tool/domain、fact/step/edge/break/verdict/reason-code 枚举和 `org.rvport.memory-order-analyzer.*` 扩展命名空间，不得直接引用 sibling tool 的运行时代码或迁移语义。

#### Scenario: Generic evidence renderer consumes both tools
- **WHEN** 通用渲染器只依赖 Finding、source 和 evidence-chain 的共享结构字段
- **THEN** 它可以展示 KB Scanner v2 与 memory-order Finding
- **AND** 领域专用标签从各自枚举和本地映射获得

#### Scenario: KB-specific field is encountered
- **WHEN** producer 尝试使用 `archReachability`、RISC-V readiness、`knowledge_match` 或 KB Scanner 专用 fact 作为内存序核心语义
- **THEN** memory-order schema validation 失败
- **AND** 实现必须使用内存序专用执行可达性、证据和结论字段

### Requirement: Separate formal findings, source candidates and bounded discharges
统一报告 SHALL 将 formal risk Findings、source-only candidates 和 `discharged-within-bounded-model` assessments 放在独立集合中，但三者 MAY 使用相同投影结构。`conclusion.verdict`、`conclusion.status` 和完整性 MUST 与所属集合一致；unknown candidate 或 bounded discharge 不得计入 formal risk 数量。

#### Scenario: Formal publication risk is projected
- **WHEN** P4 或 A6 在受限模型内产生完整 formal risk
- **THEN** 投影进入 formal findings，保留原规则版本、严重性、假设、Scope 和内部 assessment 引用

#### Scenario: AST-only source candidate is projected
- **WHEN** A2 或统一入口仅具有可信源码形状而缺少正式 IR 证明
- **THEN** 投影进入 source-only candidates，verdict 为 `source-candidate` 或 `inconclusive`
- **AND** 不得使用 formal risk 严重性或计入 TP/risk 计数

#### Scenario: Bounded pattern is discharged
- **WHEN** P4、A4 或 A6 在其声明的受限模型内完成消解
- **THEN** 投影进入 discharged assessments，verdict 为 `discharged-within-bounded-model`
- **AND** 文案必须说明它不是全程序安全证明

### Requirement: Model facts and conclusions with bilingual user-visible fields
`fact` SHALL 表达分析器实际观察到的线程、访问、对象、同步或原子事实及主位置，不承担风险分类。`conclusion` SHALL 表达 verdict、finding type、severity、confidence/evidence level、actionability、blocking、status、假设、限制、原因和建议。所有用户可见 title、reason、suggestion、detail 和诊断 MUST 同时提供中文与英文版本。

#### Scenario: Finding is rendered in Chinese or English
- **WHEN** 消费者选择中文或英文界面
- **THEN** 每个 Finding、step、break 关联诊断和 suggestion 都有对应语言文本
- **AND** 翻译文本不参与稳定 ID 或 semantic digest

#### Scenario: Fact and conclusion responsibilities are validated
- **WHEN** producer 将 severity、risk verdict 或 safety assertion 写入 fact，或将伪造源码证据写入 conclusion
- **THEN** schema/semantic validator 拒绝该投影

### Requirement: Preserve every relevant occurrence and one deterministic primary occurrence
每个投影 SHALL 列出与结论相关的全部 source/IR occurrences、配置、Scope/TU/function/context/ThreadInstance 身份、状态和 provenance，并选择一个稳定的 `primaryOccurrenceId`。primary occurrence MUST 引用数组中实际存在的 occurrence，选择规则不得依赖遍历顺序。

#### Scenario: Risk involves producer and consumer locations
- **WHEN** 一个 publication Finding 由 producer payload/write、publication event、consumer observation 和 payload read 共同支持
- **THEN** occurrences 保留所有相关位置并为每个位置声明角色
- **AND** primary occurrence 按版本化规则稳定选择，而不是丢弃其他位置

#### Scenario: Location exists only in IR
- **WHEN** 某 occurrence 只有 IR event 身份且没有可信 SourceIRBinding
- **THEN** 投影保留 IR provenance 和角色并将源码位置标为 unavailable
- **AND** 不得复制另一 occurrence 的源码位置

### Requirement: Publish a connected, deterministic evidence chain
`evidenceChain` SHALL 包含 `status`、`reasonCodes`、`rootStepId`、`primaryPath`、`steps`、`edges`、`breaks`、`impactStepIds` 和显式预算。`primaryPath` MUST 是从 root 到结论的确定性已连接路径，所有 step/edge/break 引用 MUST 在 Finding 内闭合；相关分支保留在完整图中，不得用同名或无关 occurrence 拼接证据。

#### Scenario: Complete publication chain
- **WHEN** 一个受支持 publication risk 的线程、对象、访问、MHP、RF/MO/SW/HB 或缺失顺序反例证据闭合
- **THEN** primaryPath 按真实采用关系连接线程创建、入口、调用、访问、原子通信、同步判断和结论
- **AND** status 为 complete、reasonCodes 为空且 breaks 为空

#### Scenario: Evidence chain has multiple candidates
- **WHEN** callback、对象、reads-from 或 modification-order 存在多个无法唯一选择但可验证候选
- **THEN** steps 和 edges 保留候选分支，status 为 ambiguous
- **AND** breaks 至少包含一个 `multiple-candidates` 断点及 candidateStepIds

#### Scenario: Edge endpoint is missing
- **WHEN** edge、primaryPath、impactStepIds、rootStepId 或 break 引用不存在的 step
- **THEN** reference validator 拒绝整个投影

### Requirement: Represent memory-order proof steps and relations explicitly
证据链 SHALL 使用内存序专用 step 和 edge，至少可表达 thread creation、callback binding、ExecutionRoot、call path、ThreadContext/ThreadInstance、MHP、memory access、object provenance、byte range/overlap、mutex/RAII held region、atomic event/order/scope、reads-from、modification order、release sequence、synchronization proof/gap 和 conclusion。P2 order、P3 RF candidate、R2 candidate、AST 形状或源码词法顺序不得被投影成未由原分析产物建立的 SW/HB 边。

#### Scenario: Mutex protection discharges a candidate
- **WHEN** A4/R2 具有完整的同对象普通 mutex、held-region、线程实例、访问和依赖证据
- **THEN** 证据链展示两侧访问、mutex identity、持锁区间和保护关系
- **AND** 不得仅因源码中出现 mutex 类型或函数名建立保护边

#### Scenario: Fence or RMW communication is used
- **WHEN** A6 结论依赖 fence、atomicrmw、cmpxchg、RF/MO assignment 或 release sequence
- **THEN** 对应事件、outcome、order、对象和采用的 assignment 分别成为可追溯 step/edge
- **AND** R2 candidate 本身不得替代 A6 通信证明

### Requirement: Make evidence breaks first-class and mandatory for incomplete chains
`partial`、`ambiguous` 或 `unknown` evidence chain MUST 至少包含一个 break 和 reason code；`complete` chain MUST 不含已知 break。break SHALL 记录阶段、状态、原因、起始 step、候选 steps、期望证据、缺失引用及可用的中英文 detail/suggestion。空数组、零候选、字段缺失或截断不得被解释为没有问题。

#### Scenario: AST-only chain lacks runtime proof
- **WHEN** Finding 仅由 AST/source facts 支持
- **THEN** breaks 明确列出缺失 BC/IR binding、运行时对象、ThreadInstance、RF、MO、SW 或 HB 中的适用项
- **AND** chain 不能为 complete

#### Scenario: Budget truncates evidence traversal
- **WHEN**证据搜索达到 depth、visited、path、output 或时间预算
- **THEN** chain 为 partial，budget.truncated 为 true，并保存预算断点
- **AND** 截断后的空分支不得被当作 must-disjoint、not-parallel、protected 或无风险

### Requirement: Embed bounded source context from the analyzed snapshot
每个源码型 fact、occurrence 和 evidence step SHALL 使用规范化项目相对 POSIX 路径、一基且 end-exclusive 的完整 span、`sourceSha256`、内容寻址 snapshot reference、`context.lines`、精确 `highlights` 和上下文预算。默认上下文为命中前后各 20 行；单位置 MUST 不超过 256 行和 65536 字符，并优先保留命中范围。

#### Scenario: Source context is available and unchanged
- **WHEN** 源码快照 digest 与产生事实时的 source digest 一致且 span 有效
- **THEN** context 标记 complete，lines 携带真实行号和代码文本，highlights 精确覆盖命中

#### Scenario: Source file changed after analysis
- **WHEN** 当前工作区同名文件内容与事实中的 digest 不一致
- **THEN** 系统只使用匹配 digest 的已保存快照，或将上下文标记 unavailable
- **AND** 不得读取变化后的文件冒充原分析代码

#### Scenario: Context exceeds budget
- **WHEN** 请求窗口超过行数或字符上限
- **THEN** 系统保留命中行并按距离选择上下文，标记 partial/truncated 并给出 reason code
- **AND** 不得修改原 span 或伪造列号

#### Scenario: Path escapes the declared source boundary
- **WHEN** source path 为绝对路径、包含 `..`、反斜杠逃逸或解析后位于声明边界之外
- **THEN** 系统拒绝读取内容并输出 path/source-context break
- **AND** 报告不得泄漏 checkout、用户目录或临时输出绝对路径

### Requirement: Preserve content-addressed source snapshots for expanded context
系统 SHALL 将分析所引用的完整源码快照作为独立、内容寻址、去重且有预算的 artifact 保存，并在统一 artifact index 与 location 中登记 digest、相对路径、大小和可用状态。报告内嵌窗口 SHALL 足够完成 Finding 首屏展示；消费者 MAY 使用 snapshot artifact 提供扩大后的 code-context，但不得绕过 digest 和路径边界。

#### Scenario: Multiple findings use the same file
- **WHEN** 多个 Finding 引用同一 digest 的源码文件
- **THEN** 输出只保存一个完整快照 artifact，各 Finding 保留自己的 span、窗口和引用

#### Scenario: Full snapshot cannot be retained
- **WHEN** 源文件缺失、超出 artifact 预算或违反路径边界
- **THEN** artifact index 和相关 locations 明确标记 unavailable/partial 及原因
- **AND** 已有合法内嵌代码窗口仍可保留但不得宣称支持扩大上下文

### Requirement: Bind projection provenance to immutable internal evidence
每个 fact、occurrence、step 和 edge SHALL 至少包含一个 typed provenance reference，记录 kind、ID、producer、schema/version 和 digest。投影 validator SHALL 验证引用的内部 artifact 存在、内容 digest 匹配、Scope/profile 身份相容，并验证 Finding 使用的结论确实由引用产物支持。

#### Scenario: Internal artifact changes
- **WHEN** 被引用的内部产物 digest 与投影中的 provenance 不一致
- **THEN** 投影缓存失效且 Finding 必须重建或降级
- **AND** 不得继续提供 complete 链

#### Scenario: Finding combines incompatible profiles
- **WHEN** steps 引用不同 target、ABI、profile 或未声明相关 Scope 的证据
- **THEN** validator 拒绝该 Finding 并产生 configuration-conflict 诊断

### Requirement: Produce deterministic IDs, ordering and bounded output
Finding、occurrence、step、edge、break、diagnostic、context line 和 highlight 的 ID 及排序 SHALL 由版本化规范规则决定，不得包含绝对路径、时间、随机数、对象地址、cache hit 或调度顺序。报告 SHALL 对 Finding 数量、每链节点/边/路径、源码上下文、snapshot bytes 和总输出设显式预算；超预算时保留代表证据并产生 partial/frontier，不得静默丢弃。

#### Scenario: Cold and warm projections are compared
- **WHEN** 同一语义输入分别 cold 和 warm 执行
- **THEN** 忽略运行统计后的报告、Finding ID、主路径、代码窗口和 semantic digest 完全一致

#### Scenario: Finding output budget is exhausted
- **WHEN**候选或 Finding 数量超过输出预算
- **THEN** 系统确定性保留预算允许的条目，记录 planned/emitted/omitted 分母和非空 frontier
- **AND** 不得将 omitted 计为无问题

### Requirement: Support independent backend persistence and detail retrieval
完整统一报告 SHALL 是离线审计 artifact；每个 `MemoryOrderFindingProjection` SHALL 同时可独立序列化、校验和持久化。结构 MUST 支持后端提供 Finding 摘要列表、完整详情和基于 snapshot 的 code-context，而无需保存内部 Python 对象或调用分析 stage。

#### Scenario: Backend stores each finding separately
- **WHEN** 后端解析统一报告
- **THEN** 它可以用 Finding ID、类型、severity、status、Scope、主位置和结论建立列表记录
- **AND** 将完整投影作为详情证据保存，不丢失 occurrences、chain 或代码窗口

#### Scenario: Backend only has the raw report artifact
- **WHEN**逐 Finding 持久化失败但完整报告已经原子保存
- **THEN** 原始报告仍包含完整投影并可用于离线恢复和审计

### Requirement: Validate projection semantics and quality independently in four languages
项目 SHALL 为 C11、C17、C++17、C++20 分别维护固定、人工复核的 Finding/chain/source-context truth，覆盖单 TU、跨 TU、多 Scope、formal risk、source-only candidate、bounded discharge、AST+IR、IR-only、AST-only、failed、no-debug、路径变化、上下文截断、断链、歧义、预算和缓存。所有新增、修改或复用的投影代码 MUST 有单元测试，项目整体、实现语言和每个受影响模块行/分支覆盖率 MUST 至少 90%。

#### Scenario: Four-language projection truth runs
- **WHEN** required validation 执行四个语言 profile 的固定用例
- **THEN** 分别报告 planned、emitted、exact、invalid、risk、candidate、discharged、partial 和 abstention
- **AND** 聚合结果不得掩盖任一语言 profile 的失败

#### Scenario: Reference or context invariant is untested
- **WHEN** 新增 step/edge/break、AST-only、digest mismatch、path escape 或 context budget 分支没有有效单元断言
- **THEN** 投影质量门禁失败，即使集成样例能够生成 JSON

### Requirement: Resolve referenced source locations without changing verdicts
投影 MUST 在当前 Scope 和 TU 内沿候选节点或评估事件引用解析源码位置，保留 expansion、spelling 和多个访问位置。绝对路径 MUST 按声明的源码根映射，缺文件身份或根外路径 MUST NOT 推断为主翻译单元。没有直接源码引用的分析层 MUST NOT 复制其他步骤的位置。

#### Scenario: Header event is referenced
- **WHEN** AST 或 IR 引用项目头文件中的合法位置
- **THEN** 投影使用该头文件的哈希快照和真实行号，不使用主文件的文本
- **AND** end-exclusive 的下一行第 1 列不计入高亮

#### Scenario: Formal verdict lacks source context
- **WHEN** 正式风险或已消解评估缺少可验证的位置或快照
- **THEN** 保留原始 verdict 并提供中英文源码证据缺口说明
- **AND** 不伪造源码、不将 AST-only 候选提升为正式风险

### Requirement: 版本化表达证据等级与未评估置信度
系统 SHALL 提供 `MemoryOrderFindingProjection 3.0`，在 conclusion 中明确 `evidenceLevel` 为 source-only、incomplete 或 bounded-model，并允许未评估 confidence 为 null。源码候选 MUST 使用提示级严重性、非阻断状态和未知/部分结论；不得使用固定 0.5 或其他数值充当未评估概率。正式风险严重性 SHALL 来源于实际评估。

#### Scenario: 源码候选投影
- **WHEN** 一个已准入候选仅具备源码证据
- **THEN** 新投影为 source-only、severity=info、confidence=null、blocking=false、unknown/partial，verdict 不得为 risk/discharged

#### Scenario: 完整受限模型结果
- **WHEN** 原分析产物支持正式风险或受限消解
- **THEN** 保留实际结论及模型边界，只有存在可解释评估依据时才填数值 confidence，不能以 1.0 表达全程序安全

### Requirement: 生成具体双语说明而非枚举占位
每个对外候选 SHALL 包含可理解的中英文标题、原因、详情和建议，解释已观察形状、相关性依据及不能得出正式结论的原因。MUST NOT 仅用 `source-candidate`、内部 ID 或泛化模板替代业务解释，也不得推断未观察的线程或同步事实。

#### Scenario: 观察到原子与控制关系但无 IR
- **WHEN** 候选有可回溯原子/控制源码形状而 IR 或线程证明缺失
- **THEN** 文案指出所观察操作和适用证据缺口，建议补证/复核；不能直接建议修改确定的错误内存序

#### Scenario: 缺少符号或完整位置
- **WHEN** 可信证据没有符号名或完整源码范围
- **THEN** 文案明确未知且引用可用事实，不伪造名称和代码位置

### Requirement: 新旧投影与结果策略显式兼容
本工具生产者 SHALL 在统一报告中声明实际 finding schema 版本，本工具 validator SHALL 明确区分 2.0、3.0 和不支持版本。3.0 的语义与缓存身份 MUST 不复用 2.0 的固定等级/置信度假设；历史原始制品 MUST 保持不可变。外部消费者的展示适配不属于本规格的实施范围。

#### Scenario: 读取旧版 medium 和 0.5 源码候选
- **WHEN** 合法 2.0 候选包含 medium/0.5，fact.kind 或 conclusion.verdict 表明它是源码候选
- **THEN** 本工具校验器仍接受该历史格式并保留原字段，不写回旧制品；新生成的 3.0 候选仍使用 info/null，不能继承旧固定数值

#### Scenario: 未知投影版本
- **WHEN** 输入声明未支持的投影版本或版本与字段合同不一致
- **THEN** 本工具校验器显式报告不兼容，不能按 2.0/3.0 静默猜测完整结论

### Requirement: 主路径与断点在无序存储下保持独立含义
本工具投影 SHALL 维持 steps 的稳定存储排序与 primaryPath 的逻辑排序，提供关系闭合的 edges、breaks 和截断状态，使 ID 引用能够表达真实主路径及相关分支。本工具 MUST NOT 把 steps 数组顺序当推理顺序；页面渲染由外部项目负责。

#### Scenario: 结论 ID 排在事实 ID 之前
- **WHEN** steps 的稳定排序先存放 conclusion，而 primaryPath 先引用 source-fact
- **THEN** 投影校验确认 primaryPath 为事实到结论，引用与步骤身份一致，不因 steps 数组位置改写主路径

#### Scenario: 缺口没有直接源码
- **WHEN** break 指向推理阶段或全局证据缺失且没有源码位置
- **THEN** break 保留原因、期望证据及建议，不复制其他 occurrence 的位置或删除该缺口
