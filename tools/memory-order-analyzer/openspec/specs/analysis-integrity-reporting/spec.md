# analysis-integrity-reporting

## Purpose

规范版本化数据契约、完整计划集统计、分层状态和退出码，确保缺失输入、失败与不支持能力可追溯，明确基础设施完成不等于并发安全验证。

## Requirements

### Requirement: Publish versioned and deterministic artifact contracts

系统 SHALL 为 manifest、facts、scope/index 和 RunReport 提供可校验的版本化 schema、显式对象引用及确定性排序；消费者 SHALL 按 kind 验证主 schema 版本：ModuleFacts 与 RunReport 使用 v2，其他已有 kind 保持 v1。消费者 SHALL 拒绝 v1 ModuleFacts/RunReport 和不支持的未来版本，不以填默认值伪造新事实或历史报告的提取状态。相同输入、extractor 和 policy 的语义事实及引用 SHALL 稳定，时间戳等运行字段 SHALL 与语义身份分离；机器输出不得混入日志文本。

#### Scenario: A consumer receives a future schema version

- **WHEN** worker 或编排层输入不支持的主 schema 版本
- **THEN** 输出版本不兼容诊断而非按旧字段静默解析

#### Scenario: Repeat fact extraction for the same artifact

- **WHEN** 相同 BC、extractor 版本和配置被重复读取
- **THEN** 事件/符号身份、语义内容和排序一致，运行时间等字段不改变 artifact 引用

#### Scenario: Old facts and unchanged manifests are consumed

- **WHEN** 输入 v1 ModuleFacts 及仍合法的 v1 BCArtifact/ScopeManifest
- **THEN** 拒绝旧 facts 并提示从 BC 重提取，不对合法未升级 kind 一律要求 v2；保留旧文件且不虚构缺失字段

### Requirement: Separate infrastructure completion from safety evaluation
既有 RunReport SHALL 继续独立表达 build_status、ir_status、source_mapping、scope_status 和各阶段执行状态；外部 ingestion SHALL 使用独立 `ExternalBitcodeIngestionReport` 表达 upstream/ingestion/fact/scope 完整性，不向 RunReport v2 静默加字段。两类基础设施报告均 SHALL 保存缺口原因，并在未执行风险规则时声明 semantic_analysis=not_run、safety=not_evaluated、findings=null，不输出“已确认安全”或用空 finding 暗示已完成风险扫描。

#### Scenario: All requested external BC files are processed successfully
- **WHEN** 所有 bundle 计划 BC 完成内容、parse/verify、facts 和 scope 校验
- **THEN** ingestion 报告对应基础设施阶段完成，但并发安全仍为 not_evaluated，既有 RunReport schema 不变

#### Scenario: A module lacks debug information
- **WHEN** IR 读取成功但无源码定位信息
- **THEN** 分别报告 IR 成功和 source mapping unavailable/partial，不将映射失败掩盖为全阶段完整

### Requirement: Account for the full planned input set
外部 ingestion 报告 SHALL 以 bundle records/scopes 为分母记录 planned、produced、missing、upstream-failed、hash/format/parse/verify、published、facts、source binding、scope、cache、未知调用及可定位事件比例，并说明每项分母。失败、不支持或未产出的 TU/artifact SHALL 不从计划集合消失；分母为零的比例 SHALL 为 null 而非 100%。既有单文件 import 和历史 RunReport 保持原计数语义，但不得冒充完整 bundle。

#### Scenario: Only part of the external build is available
- **WHEN** bundle 计划 10 个 TU，仅 8 个 produced 且有效
- **THEN** 报告计划 10、可用 8 及另 2 个 missing/failed 原因，ingestion 为 partial，不以成功集合重算完整率

#### Scenario: There are no planned external artifacts
- **WHEN** bundle 没有合法计划 record
- **THEN** 请求失败、比例为 null 且不发布空 scope或显示全程序无风险

### Requirement: Return exit statuses consistent with requested operations
CLI SHALL 使用退出码 0 表示请求的基础设施操作完成且无该操作完整性缺口，2 表示有可用结果但部分失败/降级，1 表示非法请求、全失败或不可继续；SHALL 尽力为非零结果生成结构合法的诊断报告。`ingest-bc-bundle` SHALL 按完整 bundle 分母应用 0/2/1；`import-bc`、`index` 及既有分析命令保持各自既有语义。已移除的 `collect`/`link` MUST 作为未知命令失败，不得以兼容别名继续执行 compiler/linker。

#### Scenario: One record fails while others produce usable facts
- **WHEN** ingestion 中部分外部 record 失败而其余 record 产生可用事实
- **THEN** 保存成功事实和失败诊断，退出 2，不仅透传最后一个 worker 的状态

#### Scenario: A caller invokes a removed producer command
- **WHEN** 用户调用生产 CLI 的 `collect` 或 `link`
- **THEN** 参数解析失败并返回结构化请求错误，不执行 compile database、compiler 或 llvm-link

### Requirement: Distinguish new reports from historical v1 reports

新输出 RunReport SHALL 使用 schema v2 且包含 fact_extraction；新消费者 SHALL 明确拒绝将 v1 历史报告按 v2 解释，不自动填入 complete/not_run 伪造未记录的状态，历史文件 SHALL 保留不变。

#### Scenario: A historical report lacks extraction information

- **WHEN** 新消费者收到未记录 fact_extraction 的 v1 RunReport
- **THEN** 返回版本不兼容诊断，不升级或覆盖该历史文件；新运行生成独立 v2 报告

### Requirement: Validate semantic references at every consumption boundary

系统 SHALL 在 worker 输出和磁盘事实消费入口执行结构及引用校验，验证唯一 ID、被引用节点存在、参数/指令所属函数、phi 前驱及 CFG 边一致性。unknown 节点 SHALL 是合法可引用对象，不等于悬空引用；结构不合法 SHALL 拒绝而非降级为空图。

#### Scenario: An index input has a dangling or foreign value reference

- **WHEN** index/link 读取的事实含悬空引用、重复 ID、错误函数归属或与 CFG 不一致的 phi/边
- **THEN** 返回 invalid_reference 或对应结构错误，不输出成功 index/link，不依赖该文件过去曾通过 collect 的假设

#### Scenario: An unsupported node has a valid identity

- **WHEN** 值图引用一个具有合法 ID 与原因的 unsupported 节点
- **THEN** 引用校验允许保留此节点，同时内容完整性仍为 partial，不将它伪装成已知值

### Requirement: Isolate extractor generations across artifact paths
系统 SHALL 以一致的 facts/extractor/policy 元数据驱动 worker 协议检查与 `ingest-bc-bundle`、`import-bc`、`index` 身份。旧 worker 或不同 policy SHALL 不因 LLVM 版本相同而被接受。版本变化 SHALL 隔离缓存与输出；迁移 SHALL 通过对不变外部 BC 重新提取 facts 完成，不覆盖旧产物、不抬高 provenance、不丢失已有 lineage。重键后的 record/scope 成员 SHALL 通过显式映射供用户更新，不能自动猜目标范围。

#### Scenario: A worker has the right LLVM but the wrong protocol
- **WHEN** worker 使用锁定 LLVM 却不支持 ModuleFacts v2 或预期 extractor/policy
- **THEN** reader readiness 与实际 ingestion 均报告协议不兼容，不发布伪装新版本事实

#### Scenario: External bitcode is re-extracted under a new protocol
- **WHEN** 相同 bundle/BC 曾由旧 extractor 生成 facts
- **THEN** 新 ingestion 使用不同内部 artifact/facts identity 且不计为旧命中，旧文件不删除并保留 record/TU/profile lineage

#### Scenario: A bare import changes extractor generation
- **WHEN** 无 bundle 的单文件 import 在新 extractor 下运行
- **THEN** 身份包含当前 facts/extractor/policy，provenance/scope 仍为 unknown，重复导入不无限增长 lineage

### Requirement: Report fact extraction completeness without semantic verdicts

ModuleFacts SHALL 记录 extraction policy、complete/partial 状态、所需根/节点/unknown 计数及可定位诊断。RunReport SHALL 增加独立 fact_extraction 状态 complete/partial/failed/not_run、模块计数与原因，区分 parse/verify、源码映射和事实解释完整性；分母 SHALL 明确且零分母不为 100%。有可用但部分事实的请求 SHALL 退出 2，全部不可用或非法请求退出 1，无相关缺口退出 0；语义分析 SHALL 仍为 not_run，safety 为 not_evaluated，findings 为 null。

#### Scenario: Parsing succeeds with unsupported semantic operands

- **WHEN** BC parse/verify 成功且部分所需值被表示为 unknown
- **THEN** 保留可用事件/引用，fact_extraction 为 partial、提供原因并退出 2，不把 IR 读取成功等同于事实全部可解释

#### Scenario: One translation unit exceeds the extraction budget

- **WHEN** 多 TU 请求中一个 TU 因预算失败而其他 TU 产生可用事实
- **THEN** 保留完整计划分母、失败原因及成功事实，报告 partial 并退出 2，不将失败 TU 从统计中移除

#### Scenario: Complete facts still do not constitute a safety scan

- **WHEN** 所需范围内所有支持的 v2 事实提取完成，或仅运行 doctor
- **THEN** 前者 fact_extraction 为 complete、后者为 not_run；两者均保持 semantic_analysis not_run、safety not_evaluated、findings null，过程间/线程/内存模型能力不启用

### Requirement: Validate local evaluation snapshots and bound payloads

系统 SHALL 独立协商 LocalEvaluationRequest/Result v1，拒绝旧四 kind 握手；SHALL 校验请求/结果完整快照、函数和当前/祖先实例、参数类型、原始/分析引用角色、所有摘要与补充依赖 digest、scope/profile/预算及表达式结构上限。结果 request_hash SHALL 与调度器实际提交请求一致，不能仅信任结果自述。P1 v2 与模块元数据缓存不迁移。

#### Scenario: A worker substitutes the request or a dependency

- **WHEN** worker 返回不同实参/实例的请求快照或陈旧/缺失补充及 callee 摘要
- **THEN** 拒绝消费及缓存命中，不将该结果当作当前上下文的 complete 或可用空图

#### Scenario: A candidate carries an invalid binding

- **WHEN** 候选含未绑定参数、外来分配/guard、错误参数数目/位宽/地址空间、重复条目或非法 bottom
- **THEN** 明确拒绝；合法祖先实例的对象保留原归属，不套用仅允许外层入口全局对象的限制

### Requirement: Bind local evidence to its supplement generation

摘要和报告 SHALL 通过 local_dependencies 的 artifact_key/canonical digest 引用经过 origin、schema、预算和节点登记校验的 LocalAnalysisFacts。SourceRef 与 AnalysisRef SHALL 使用不同键和角色；SHALL 拒绝重复登记、悬空输入、跨函数证据、IR/分析命名空间混用及与原始节点冲突的 owner/opcode。身份校验 SHALL 不被表述为语义证明。

#### Scenario: A consumer lacks or substitutes the referenced supplement

- **WHEN** 补充产物缺失、digest 陈旧、预算不同或证据不属于对应函数
- **THEN** 拒绝消费，不通过添加 P1 节点、忽略引用或降成空证明来接受摘要

### Requirement: Version P2 products independently from P1 contracts

系统 SHALL 为 EffectAnalysisRequest、LocalAnalysisFacts、LocalEvaluationRequest、LocalEvaluationResult、EffectSummary 和 EffectAnalysisReport 提供独立 v1 schema 及分析协议，初始 analysis_version 为 0.1.0、policy_id 为 scoped-effects-v1；SHALL 保持 ModuleFacts/RunReport v2、其他已有 kind v1 和 P1 extractor 语义不变。SHALL 按 kind 协商支持版本，不以静默附加字段、填默认值或覆盖旧文件迁移。

#### Scenario: New analysis reads existing P1 facts

- **WHEN** 合法的 ModuleFacts v2 和原始 BC 被用于 P2
- **THEN** 新建独立补充/摘要/报告，原始 ID、extraction、capabilities、ArtifactKey 和历史 RunReport 保持不变

#### Scenario: A consumer receives an unsupported derived version

- **WHEN** 输入未知 kind、未来派生 schema 或不兼容分析 worker/policy
- **THEN** 明确拒绝并报告协议错误，不因 LLVM 主版本相同而接受，也不将缺少摘要解释为无效果

### Requirement: Validate derived references and preserve evidence generations

系统 SHALL 在 worker 输出、磁盘和缓存消费处验证派生产物结构/唯一 ID/原始引用/函数和上下文归属，以及 artifact/BC/facts digest、scope/profile、策略和依赖摘要身份。SHALL 将原始诊断的解释结果与对应原始 ID 和证据关联，不删除 raw unknown、不抬高 unknown provenance；无效结构拒绝而不是作为正常 partial 空图。

#### Scenario: A summary references another context or missing event

- **WHEN** 派生效果含悬空原始事件、错误 artifact、跨函数/上下文对象或不一致的依赖 hash
- **THEN** 返回 invalid_reference 或对应身份错误，不消费该摘要、不发布成功分析结果

#### Scenario: A supplement explains a raw diagnostic

- **WHEN** 有限 ABI 解释或路径证明消除了某原始 unknown 对一个上下文的影响
- **THEN** 新产物保存原始诊断 ID、策略及证明，原始文件和其他上下文的诊断不变，来源可信度不自动升级

#### Scenario: An instance table or binding is forged

- **WHEN** 实例 parent 悬空/成环、调用位置不属于父函数、guard 属于其他函数、分配声称比调用更精确的单例性，或实例化结果仍有未绑定局部模板槽
- **THEN** 拒绝 invalid_reference，不把结构有效的错误身份解释为完整摘要，亦不修改 P1 原始 ID

### Requirement: Isolate analysis cache generations from compilation artifacts

P2 SHALL 将局部/上下文/SCC 派生身份与原始编译/extractor 身份分离；版本、策略、预算、scope/边界或依赖摘要变化 SHALL 使相关派生缓存失效，不无故重编译或重键未变原始 BC。缓存失效与迁移 SHALL 保留历史产物，不覆盖旧结果或使用陈旧来源。

#### Scenario: Only the effect-analysis policy changes

- **WHEN** 相同 BC 和 P1 facts 使用新的摘要预算或分析策略
- **THEN** 新生成不同派生身份，不计为旧摘要命中，同时原始 BC/facts 可继续复用且历史输出不被覆盖

### Requirement: Validate P3 cross-layer evidence integrity

系统 SHALL 在消费 P3 产物前验证 BC、P1、P2、ThreadLocalFacts、ExecutionOrderFacts、ThreadContextGraph 和报告之间的 digest、scope/profile、版本、函数/调用/线程归属及引用闭包。P3 解释或补充 SHALL 不覆盖 P1/P2 原始诊断；缺少、矛盾、陈旧或伪造证据 MUST 阻止相关关系提升为确定事实。

#### Scenario: An order edge references another invocation

- **WHEN** 执行顺序边的端点属于不同且没有合法调用/生命周期连接的 invocation 或 ThreadInstance
- **THEN** 完整性校验拒绝该边并降低相关阶段状态，不让它参与 must-before、MHP 排除或同步组合

#### Scenario: A P2 summary is replaced after local thread extraction

- **WHEN** ThreadLocalFacts 仍引用旧 EffectSummary digest，而 artifact store 中提供了新摘要
- **THEN** P3 依赖被判陈旧并重算或失败，不把不同代际的效果与线程身份混合

### Requirement: Preserve P3 plans, unknown frontiers and completeness denominators

系统 SHALL 在分析前登记显式根、scope 成员和可见调用计划，并在报告中保留已处理、partial、failed、not_run、合并及未展开项。回调、句柄、线程、MHP、mutex、原子候选和定位统计 SHALL 给出清晰 hit/total；不得通过过滤未知项、超限项或不可读取成员提高完整率。

#### Scenario: A recursive spawn reaches the instance limit

- **WHEN** 已发现部分实例后触发线程实例预算
- **THEN** 报告保留原始入口、已知实例、合并桶、未展开 frontier 和实际预算，thread_modeling 不得为 complete

#### Scenario: Source mapping is unavailable but IR evidence remains usable

- **WHEN** BC 无 debug 信息而线程/顺序 IR 事实可生成
- **THEN** source_mapping 独立为 partial/unavailable，IR 分析结果保留，命令以 2 退出且不伪造源码位置

### Requirement: Isolate P3 policy and cache identities from earlier stages

P3 策略、模型或展示协议变化 SHALL 仅使受影响派生缓存失效，不修改 P1 ArtifactKey 或 P2 EffectSummary 身份；P3 request_hash SHALL 包含实际 roots、模型、预算和依赖，而可复用上下文模板身份 SHALL 排除调用者特有实例字段。

#### Scenario: Only the pthread model version changes

- **WHEN** BC、P1/P2 产物不变而 `posix-pthread` 模型版本变化
- **THEN** 重算 P3 局部采用、上下文和报告，不要求重编译 BC 或重写 P1/P2 历史产物

### Requirement: Validate P4 cross-layer evidence integrity
系统 SHALL 在 worker、磁盘、缓存和报告消费入口验证 PublicationLocalFacts、SinglePublicationProtocolGraph、PublicationRiskReport 与 BC/P1/P2/P3 之间的 schema/policy/model、digest、scope/profile/boundary、语言配置、预算、原始/分析引用、函数/invocation/ThreadInstance、对象范围、guard 和证明闭包。P4 解释 MUST NOT 覆盖或抬高 P1/P2/P3 原始 unknown；结构错误 MUST 被拒绝而非作为正常零候选。

#### Scenario: A successful observation references a stale load
- **WHEN** 成功观察的原始 load、invocation 或 thread effect 与当前 P3/P2 generation 不一致
- **THEN** 拒绝相关产物，不让陈旧节点参与 reads-from 唯一化或 finding

#### Scenario: A valid local interpretation explains a raw unknown narrowly
- **WHEN** P4 局部证明在一个具体候选内解释初值或 gate，但原 P1/P2 仍有更宽 unknown
- **THEN** P4 保存原始诊断、适用上下文和证明，不修改原文件或把该解释推广到其他候选

### Requirement: Preserve P4 plans, findings and unknown denominators
风险分析 SHALL 在执行前登记 scope 成员、根、局部事实和协议候选计划，并在报告中保留 complete、partial、failed、not_run、finding、discharged、unknown、unsupported、excluded 和未展开项。不得通过过滤开放边界、未知同步、超限候选或失败 TU 提高完整率；finding 数与完整率 SHALL 独立统计。

#### Scenario: A partial run already contains a finding
- **WHEN** 一个候选有可报告风险而另一个相关计划项 unknown 或超限
- **THEN** 保留 finding 和 unknown 分母，整体退出 2且 verdict 不伪装为完整

#### Scenario: No findings remain after filtering unsupported inputs
- **WHEN** 所有计划候选都因未支持同步被标记 unsupported
- **THEN** unsupported 仍计入原计划，结果 inconclusive 而不是零风险通过

### Requirement: Isolate P4 risk exit semantics from existing commands
`detect-publication-risks` SHALL 使用 0 表示完整且无 finding、3 表示完整且有 finding、2 表示有可用结果但 partial/unknown/unsupported、1 表示非法或不可继续；partial SHALL 优先于 finding 返回 2。`ingest-bc-bundle`、`import-bc`、`index`、`summarize` 和 `model-threads` 的 0/2/1 语义 MUST 保持与其职责一致，ingestion 状态不得改写 P4 verdict，P4 也不得把输入成功解释为安全。

#### Scenario: Existing P3 analysis completes after external ingestion
- **WHEN** 用户在已导入 artifact store 上只运行 `model-threads`
- **THEN** P3 仍按原 0/2/1 规则退出并保持 findings=null，不因 ingestion 或 P4 可用而运行风险规则

### Requirement: Prohibit analyzer-side bitcode production in production operations
生产 `memory_order_analyzer` CLI、ingestion driver 和 P1–A6/R1–R3 runner MUST NOT 执行编译器、dependency generator、assembler、`llvm-link`、configure/build/install、网络、SSH 或被分析程序，也 MUST NOT 写出经过转换的新 BC。允许的外部进程仅限经协议握手的只读 reader/source analysis worker；测试 fixture 的预生成命令 SHALL 在调用分析器之前执行并明确隔离。

#### Scenario: Ingestion is traced in a compiler-equipped environment
- **WHEN** 测试环境安装了 clang、gcc、llvm-link 和 CMake，并记录 ingestion/analysis 发起的全部 argv
- **THEN** 只观察到 reader/source worker 请求，不出现 compiler/linker/build/target execution

#### Scenario: A malformed BC might be repairable by a tool
- **WHEN** 输入不是受支持 raw LLVM BC或 verify 失败
- **THEN** 系统报告失败，不调用 clang、llvm-dis、llvm-as、objcopy 或 llvm-link 修复
