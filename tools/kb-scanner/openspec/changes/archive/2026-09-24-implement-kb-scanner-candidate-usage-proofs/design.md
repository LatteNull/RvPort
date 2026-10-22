## Context

当前实现的缺口是 producer，不是重新设计候选识别：

- `classifiers/semantic_admission.py` 已消费 `has_semantic_role` 与 ProofPath；`MigrationClassifier` 只省略 Classification，保留 Observation。
- `LocalX86Detector` 已给 identifier/enum candidate 携带 `factId`、`subjectId`、`matchedEvidenceIds` 和 `configuration`。用途证明必须严格使用同一身份约定，尤其不能把 `default` 与 `source-unconfigured` 任意混用。
- C/C++ frontend 有宏、枚举引用和条件结构，但没有完整的一般读写/逃逸记录。函数多版本 inventory 只在相关属性存在时工作，不能直接当作所有函数的用途分析入口。
- 固定 libarchive 审校中 26 项人工数据用途仍是 unknown；其中 `_7Z_X86` 被用于多个 codec 分发分支，`CKSUM_SHA512` 出现在算法调用选择中，`BOOT_PLATFORM_X86` 被赋给对象字段。名称、整数值、字段名或“有 generic 文件”都不足以证明这些 occurrence 可排除。
- 当前准入的 `_complete` 主要检查路径连通性，自动 producer 接入前需补齐 `truncated`、空路径、精确 role relation、引用、计数及作用域摘要验证。不能让生成器的 `scopeComplete=true` 成为未经核查的安全声明。

操作根为 `tools/kb-scanner`。现有正式输出为默认 V2、显式 V1，早期配置中 V1/YAML 背景不是本轮目标。

## Goals / Non-Goals

**Goals:**

- 自动产出可审计的局部用途图，分开记录 data、execution、escape/unknown；原 fact 永远保留。
- 首版至少有真实 parser→normalization→analyzer→classifier 的正例闭环，而非只用手工注入 proof 的单元测试冒充完成。
- 仅对完整局部纯数据闭包生成排除证明；既有确认执行依赖保持原风险，其他情况保持 unknown。
- 兼容报告并提供被排除候选的有界审计入口；统计、原因、真实源码位置与双语说明可复核。

**Non-Goals:**

- 不保证消除 libarchive 的 26 项，不把旧人工标签导入运行时，不通过减少 Finding 数验收。
- 不做完整 C/C++ CFG/SSA、任意宏展开、指针别名、模板实例化、跨函数/跨 TU 值流、通用调用图、外部 API 语义识别或 codec 实现等价证明。
- 不判断存在 RISC-V 机器码/通用实现就等价于目标已选中；已有家族、函数多版本和构建 proof 继续独立负责。
- 不新增 schema 版本、核心字段/枚举、后端输入、前端页面或第二主结果文件。
- 不涉及 CC-0006、OS/ARM 迁移、其他 scanner、生产容器或真实编译。

## Decisions

### 1. 复用已有技术，新增 scanner-owned 局部使用摘要

复用锁定的 Tree-sitter C/C++ 作为语法来源、现有 `SourceByteIndex` 提供字节位置；可选 Clang 提供同配置的声明绑定补充。继续使用现有 GraphStore 和 core DTO，不引入 CodeQL、LLVM 执行管线或新第三方依赖。

在一次 native tree 有效期内建立轻量索引，采集候选相关 owner、声明、读取、赋值、比较、控制体、取址、调用参数、return、指针/字段写入及不支持语法标记；只输出 Python 标量、稳定引用与 source span。不能从 `.start_point` 恢复曾导致原生崩溃的路径，也不能把 Node/Tree 保存到后续阶段。无函数属性的普通函数也必须覆盖；不放宽旧多版本分组规则。

前端负责语法而非“数据格式”业务标签。局部重名按词法作用域绑定；Clang 补充不能用裸 USR、机器路径或同名字符串跨配置连接，冲突保留 unknown。normalization 对 owner、声明、引用、span 与配置校验，原 Evidence/Fact 的 ID、值和知识来源不重写，新记录追加。

替代方案：只做正则名称识别成本低，但无法证明使用范围；重新解析每个 Finding 或构造全程序值流成本过大。2026-09-23 用户确认后改为候选驱动采集及查询：管线把已经加载的 KnowledgeSnapshot 传给支持该能力的 frontend；在单个 native tree 有效期内先产生旧 Evidence，以正式 CppEvidenceNormalizer 和 CandidateUsageDemand 得到同身份候选根，再只采集根所在函数的完整用途记录。知识索引在本次扫描内复用，候选名不另建规则。临时归一化结果仅用于需求选择，正式阶段仍统一产生最终快照；原 Evidence/Fact 不修改。可选 Clang 后续新增但本次语法未覆盖的需求保持 unknown，不借用配置。

这一阶段协作通过可选 analyze_with_knowledge 入口接入，不改变现有两参数 frontend 协议或 V2 输出。纯语法 adapter 独立调用仍可提供全锚点 inventory 用于组件验证；默认管线必须使用正式知识需求。任何语法/规范化失败均关闭对应用途采集资格。无需求函数不生成用途记录且不消耗扫描级记录预算；函数内必须完整采集受支持及不支持语法，不能只提取命中行来伪造完整闭包。

### 2. 候选需求复用原匹配规则，不依赖最终 Finding

提供 `CandidateUsageDemand`，复用现有 matcher/definition/知识索引确定 identifier 与 enum 候选根，不复制架构词正则。Analyzer 在 source/build/test/family/multiversion 之后、Detector/Classifier 之前工作；不能以最终检测输出反向调用整条管线。

统一 demand 与 Local Detector 的身份构建：`factId + subjectId + configuration + 原始 matchedEvidenceIds`。配置缺失保留原约定而非自动提升完整性；多配置事实拆分作用域或 unknown，不借用另一个配置的证明。

原 FactProofDemand、confirmed/hint 事实和既有图保持。新增 uses/binding/control/escape 关系仅服务用途查询，不成为 selected、inactive、alternative 或调用执行证据。

### 3. 首版证明范围是完整的局部纯数据使用闭包

新增内部 `non_execution_data` 角色，避免仅凭赋值语法把用途硬称为 algorithm/data_format/output_platform。既有三种业务角色消费合同保留，但本轮默认不自动赋予这些领域标签。

首版正例限于：局部枚举/简单整型常量或可唯一绑定的对象式整数字面宏，沿无重载的标量复制/比较，进入局部无逃逸标量或固定数组的字面数据处理，所有相关读写和控制后果都能穷尽且不涉及调用、返回逃逸、外部状态或未知操作。仅支持明确列出的语法白名单；其他语法均关闭排除资格。

例如，函数内声明的 `enum { FORMAT_X86 = 1 };` 只参与局部变量比较、选择字符字面量并写入未逃逸的本地固定数组，可形成局部纯数据证明。将相同数组传入未知函数，或在同一条件体加入 `_mm256_*` 调用，必须分别变成 unknown 或执行冲突。示例中的名称可随机替换，结果应只取决于结构与已有候选根。

闭包的起点决定证明责任：

- 使用 occurrence：追踪该值的后续 def-use、受它控制的分支和写入对象的后续使用，不能只看一条赋值。
- 声明/宏定义 occurrence：需要定义可见范围内全部使用闭合。头文件、外部可见枚举、跨 TU 宏、未完整纳入的 include、条件重定义、生成输入缺失均不能宣称定义级闭合。
- 同一候选 fact 聚合多个 matched Evidence：全部匹配根及同配置的相关使用必须满足，不能只证明其中一个。

循环、goto、异常控制、未知调用、return、取址/引用逃逸、指针/对象字段或全局写入、volatile/atomic、重载运算、类型不明、token paste/stringification、模板依赖均保守 unknown。函数中与值流或控制依赖无关的完整已知语句不应污染当前闭包；无法证明无关时按未知处理。

不使用“没有命中 intrinsic”作为充分条件；完整性来自受支持语法、绑定、范围与全部使用统计。算法/codec 分支中的普通函数调用即使名字看起来通用，也属于本轮未知调用，不产生完整数据排除证明。

### 4. 用途、执行依赖与替代实现分别判定

优先级：既有 confirmed 执行事实及完整选择 proof > 执行/数据冲突 > 不完整/逃逸 > 完整纯数据用途。数据来源到 selector 的部分链可以保留为上下文，但不能代表受控算法实现已证明可移植。

- selector 对应分支已有 x86 依赖：保留原 high/blocker，不用数据角色撤销；新增使用关系本身也不把普通未知候选升级 high。
- selector 对应分支只有未知调用：候选保留 unknown，记录待补调用语义；不猜 RISC-V 或 generic 实现是否存在。
- 纯数据闭包完整：只排除精确候选 Classification，保留 Observation、fact、proof 和审计，不删除其他 occurrence、confirmed Finding 或 comment hint。
- 少了一个候选 Finding 不构成项目 ready 依据。Assessor 继续要求独立输入/构建/选择/替代证明；排除用途关系不得充当这些维度的 satisfied 证据。

### 5. 自动证明必须含可核查闭包，准入仍 fail-closed

`has_semantic_role` 的端点、fact/configuration、scope、原始 matchedEvidenceIds 沿用旧合同。自动 producer 附版本化内部 `usageProof` 摘要：查询根、作用域身份、supporting evidence/relation IDs、预期/已解析使用数、未决/冲突/逃逸数、预算计数与截断原因；各明细必须可从同快照索引解析。

证明只有所有相关使用解析成功、无未知/冲突/逃逸、未超预算时才允许 `scopeComplete=true`。ProofPath 必须非空、含对应 role relation、连续、有合法端点，status=complete 且 truncated=false。为满足旧合同可保留一条 summary role edge，但它必须引用真实使用闭包，不能只连 source_file→role 就视为充分证据。准入消费者验证摘要与引用的一致性，不重新执行源代码分析。

执行冲突检查既看 observation 现有 metadata，也检查该闭包中同配置的已知依赖；proof 的非执行角色不能被 Local Detector 的全关系关联误当执行连线。设计覆盖同一个 fact 的多角色、部分数据/部分执行、重复 producer 和无效 summary。

### 6. 报告兼容与可见性

既有 V2 `extensions` 下使用 `org.rvport.kb-scanner.candidate-usage`：

- 尚有 Finding：在 `fact.extensions` 自包含当前根、用途状态、真实来源、未知/冲突原因及预算摘要。已有 evidenceChain 只展示有端点的源码关系；语义 role、classification、assessment 不是代码 step。
- 被排除的候选没有 Finding：顶层 extension 提供有界 `excludedCandidates` 审计记录及总数/省略数，包含原始 fact 根、配置、判定原因和紧凑源码来源；不得制造 low Finding 凑展示，不暴露无法闭合的内部 typed refs。
- 多 occurrence/多根不聚合丢失范围。HTML 默认中文并转义；新增可展示说明提供中英文。真实源码来源继续默认上下各 20 行，仍受全局字符/行数硬预算。
- V1 保留既有结构及聚合 INFO 诊断，可用既有 trace 表达保留项；不增加必填字段。默认 V2、显式 V1、三个工件与静态声明保持。

更新命名空间说明、合同示例、引用验证和人工差异 ledger；不改核心 JSON Schema 枚举/required。无候选的固定输入不应因本能力改变报告；有候选的变化逐条按 occurrence/provenance 审校。

### 7. 确定性与资源边界

一次建立声明/引用/入出边索引，按 `(fact, configuration, scope)` 缓存查询；相同作用域只解析一次，不逐 Finding 重扫源码或遍历全图。不对全部 root×terminal 组合求路径。

初始上限：每文件扫描 100000 个语法节点、每函数 10000 个 usage record、每扫描 100000 个新增 usage record；每根查询深度 32、访问节点 4096、支持关系 8192；全扫描查询访问计数 1000000。达到任一上限均产生可追溯 partial/unknown，不生成排除。与现有更小硬预算同时生效，不放宽旧阈值。

准入每根最多 64 个 role，超过维持现有 unknown；展示顶层最多 100 条排除审计、每 Finding 最多 64 个来源，同时受现有上下文预算约束。裁剪只影响展示，不改判定；必须显示总数与省略数。

稳定 ID 不含绝对根、时间、遍历顺序和 native 对象地址。性能验收使用固定真实 libarchive 两轮及 10000/20000 个局部引用的稀疏/密集需求样例，记录节点、访问、缓存、时间、RSS、大小和预算触发。2026-09-24 用户确认允许新增扫描能力的合理成本：开启/关闭 producer 是功能不同的成本对照，不再用“同时增加超过 10% 且 1 秒”单独否决；仍原样记录差值、百分比和旧门槛结果，历史失败不改写。固定 822 文件 libarchive 及规模矩阵的每个独立扫描均保持 2 CPU/2 GiB/无额外 swap、300 秒内完成且不得 OOM。超限需优化或请求调整范围，不能靠删事实、提高预算或自动改 golden 通过。

完整四组开关矩阵必须全部执行；扫描失败、缺工件、候选数不符、用途能力未触发、预算失控或阶段记录缺失仍阻止验收。采集、归一化、用途分析（索引/查询合计）、报告构建/校验/发布分段记录，不能把整次扫描差值称为索引耗时。复核作用域索引数、记录数和查询访问量，禁止逐 Finding 重扫、重复建索引及全 root×terminal 扩张。开启功能的通过版本连同源码 digest、资源配置、输入规模和阶段结果保存为后续同功能回归基线；不是删除性能回归要求或为所有未来功能无限放宽成本。本轮不实施此前待确认的“紧凑共享用途表”跨模块重构。

实施阶段已补充局部索引与不可变对象复用：Detector 按 Evidence 查执行关系；原枚举分析按源码区间查包含条件及后继依赖；用途实体/关系在单次 UsageSession 中复用，配置不混用；源码上下文在单次投影中缓存路径校验和内容快照。原判定、稳定 ID、引用完整性、命中范围及预算不变。2026-09-23 用户已明确批准“先根据既有 fact 选择候选作用域，再提取用途”的阶段协作调整。此前失败记录保留；新实现必须重跑单元、报告差异、项目及规模门禁，不能沿用旧验收。

2026-09-23 经用户确认新增 822 文件验收基线：原 810 文件及其哈希全部保留，额外包含当前已支持采集的 12 个 CMake 文件。旧 `large-project-performance` 清单和历史审校不改写；新增 `candidate-usage-performance` 清单通过基础清单加增量哈希表达，不允许覆盖历史路径。性能门槛没有放宽，报告变化继续逐项审校。

密集需求验证还覆盖旧公共消费者：TestSelectionDetector 以 proof.target_id 分组，Classifier 按 relation_id 反查 proof，避免新非执行图放大旧的实体×proof 或观察×proof 扫描；引用校验、推导的 proof 集合与顺序不变。枚举声明区间采用起点和前缀最大终点索引，保留原半开区间包含语义。大于等于 256 个 Finding 的 JSON 按项编码、分块写入原 staging 目录，流式累计 SHA-256 后再原子发布；不是缩短上下文或减少 Finding。小报告保留 bytes 接口，字节排序、Unicode、空值策略和换行与原 serializer 完全一致。块生成异常必须保留旧工件集合，回滚逻辑及质量门槛不变。

投影在本次快照内共享同文件/行的 ContextLine、原 Evidence 步骤与 Arc 边；incoming 扩展复制后缓存，不修改基础步骤。内部对象身份只用于扫描内复用，绝不进入稳定 ID 或输出。引用校验的扩展递归在一次调用内只遍历共享对象一次；每次重新校验都重建 visited，不沿用上次对可变扩展的结果。所有链端点、路径、排序、源码、高亮和 namespace 校验规则仍执行，单测覆盖查询间污染与第二次校验发现新增非法扩展。

用途扩展的源码 JSON 在同一 CandidateUsageProjection 内按 SourceSpan 复用；重叠窗口的行字典亦复用，投影/渲染期间只读。大报告 HTML 与 JSON 同样逐 Finding 分块写入 staging，保留转义和原字节，不一次性拼接全部源码片段。用途图物化按 scope/configuration/闭包节点/边/uses/status/truncated 缓存相同的非执行子图；根绑定、role/proof 身份及预算判断继续逐根构造，不能以缓存命中放宽完整性。

采集阶段已经明确因 file/scope/scan 记录预算而 partial 的作用域，不继续执行无法证明全使用穷尽的用途查询或物化非执行图。原始 Evidence、NormalizedFact 及其 usage records 不删除；对应候选仍 unknown，保留精确命中、预算原因和 truncated，查询访问数如实为 0，不把未执行查询冒充完整闭包。非预算 partial（如错误解析）继续原断点查询。由此不再输出未查询的 usage_record 来源，但原 Finding 源码链与上下文保持；差异限定为用途 namespace，必须重新审校。

准入消费者按不可变快照、configuration、record/scope/use/relation ID 集合复用支持图校验结果及连通分量；每次仍独立核对 role、fact、subject、matchedEvidenceIds、rootBindings、scope、实际来源和完整性。独立报告消费者不借用分类器的成功结论，仍持有自己的校验器。缓存失效/非法图与跨配置均不能放行；普通独立校验函数保留无缓存行为。原子发布使用 1 MiB 有界写缓冲，哈希、全部字节和失败回滚不变。

文件用途采集先积累未发布的标量结构，在确定文件预算状态后一次性冻结为公开 Evidence，避免预算触发后的重复深复制；暂存结构不含 Node/Tree/Point。HTML 在单次用途审计渲染中复用同一源码对象的已转义片段，不跨调用保存缓存，代码上下文、高亮与最终字节不变。

用途需求索引按实际 DetectorDefinition 的候选输入种类收集所需 knowledge kinds，同时保留同输入的 confirmed matcher 以做完整覆盖检查；执行冲突索引只为同 subject/configuration 的实际依赖事实构建，仍调用正式 matcher。原 KnowledgeSnapshot、规则与两个 compiler facts 不变，自定义规则和完整知识索引结果须等价。用途记录的数字行列范围直接使用 SourceByteIndex 的校验偏移映射，不为每个内部标量行构造 SourceLocation/SourceSpan；公开 Evidence 仍校验路径、范围和端点，UTF-8/CRLF/EOF 与旧映射一致。

### 8. 单元、真实语法与审校分别验收

局部性能修复补充：用途作用域在完成预算状态后深冻结一次，以专用私有只读 Mapping 在 Evidence→NormalizedFact 间共享；仅认可精确内部类型，外部 MappingProxyType 和子类仍重新校验、复制。全部原始记录、不可变性、JSON 字节和稳定身份不变，不调整全局 GC 策略。ScopeIndex 预排序邻接并复用规范边元组；每个根仍独立执行原 BFS 和预算，不共享不同根的深度/访问结论。

同样复用已冻结的用途 summary，避免 role Relation 与审计 Entity 各复制同一闭包 ID 集合。SourceContextProjector 仅在同一次扫描内缓存原路径的规范化结果，以及 truncated 两种状态的不可变 ContextBudget；路径逃逸检查、不同根目录、命中高亮与源码文本不跨扫描借用。

预计模块及隔离测试映射（实际拆分时 inventory 必须同步新增每个自有模块）：

| 模块/边界 | 隔离测试职责 |
|---|---|
| `frontends/cpp/usage_inventory.py`、adapter/vocabulary 接入 | fake grammar nodes，作用域、字节范围、shadowing、无属性函数、原生对象不外泄、预算和错误节点 |
| normalization 用途校验模块及 `normalization/cpp.py` | 纯 DTO；悬空引用、配置冲突、原事实不变、非法 span |
| `analyzers/candidate_usage/demand.py` | fake knowledge/matcher 边界；与 Detector 身份一致、不复制规则 |
| `analyzers/candidate_usage/index.py`、`closure.py`、`proofs.py` | 合成事实/图；def-use、control、escape、完整性、冲突、稳定 ID、预算和缓存 |
| `pipeline/composite.py`、必要的 Detector 关联适配 | fake stage；顺序、partial/failed、无候选快速路径、原始 Observation 保留 |
| `classifiers/semantic_admission.py`、`migration.py` | 完整自动 proof、截断、无效 role、配置/根不符、执行冲突、只省略 Classification |
| 若修改 `assessors/migration.py` | 合成 snapshot；排除不能替代执行/替代/输入完整性，不自动 ready |
| `projection/v2/candidate_usage.py`、mapper/projector/source_chain/renderers/诊断适配 | fake context、publisher；单 Finding 闭合、排除审计、双语、±20、预算与 HTML 转义 |

在独立测试容器运行现有 `tests/run_source_chain_unit_tests.py --output ...` 并扩充 inventory，使整体与所有受影响模块达到 ≥90% 行/≥90% 分支；统计 `kb_scanner/`、`scripts/`、`tools/` 全部自有可执行代码，包括未加载文件。仅第三方、生成数据、测试资产和不部署 archive 可说明排除，无分支模块明确不适用。

真实 parser/CLI 测试单独覆盖完整正例、仅常量名不能排除、同名遮蔽、宏重定义、模板、跨文件、函数返回/调用逃逸、数据 selector 控制 intrinsic/普通调用、UTF-8/CRLF、原生崩溃缩减、数据/执行混用及 V1/V2/HTML/log。单元覆盖不计真实 parser/项目扫描。

固定 libarchive 的 26 项只是逐项审校对象：至少解释 `_7Z_X86`、`BOOT_PLATFORM_X86`、`CKSUM_SHA512`、CRC32 的已证部分与剩余未知，不要求全部排除；每个排除必须能从源码重放证明。保留旧 ledger，另记新差异；AVX、枚举、架构家族、函数多版本、CMake/RPM/Autoconf 等既有回归均需通过。

## Risks / Trade-offs

- [数据 ID 实际控制 x86 实现] → 闭包包含控制后果，既有执行事实优先；未知调用不排除。
- [局部完整误当全项目完整] → 使用与定义的证明责任分开，开放作用域/跨 TU 保留 unknown；不输出兼容实现已存在。
- [初版真实噪声减少有限] → 接受 unknown，交付可复用生成能力和可解释缺口，不通过白名单凑消除数量。
- [前端枚举绑定或函数 inventory 不够精确] → 只追加必要词法记录，歧义时保守，独立验证旧事实身份与多版本行为。
- [新关系污染源码主链与检测 ID] → 非执行关系显式隔离；报告差异按 occurrence 对齐，而非要求所有 ID 不变。
- [索引与证据展示放大内存] → 共享作用域摘要、全局查询门禁与展示裁剪并记录 omitted；原始事实不截掉。

## Migration Plan

先固定原始报告、事实哈希和人工 oracle，再实现隔离 producer/consumer 门禁，最后接入默认管线与现有 V1/V2 投影。验收全通过后更新文档、同步规范并归档；提交、推送和生产容器更新须另获用户授权。

回退粒度为新增 usage producer 及相应 projection 的接入；旧语义准入维持 unknown 消费边界，不启用 Legacy。不得以回退为由删掉已采集的事实或修改持久历史报告。

## Open Questions

无阻塞性产品选择。具体真实项目能闭合多少项由实施阶段逐项审校得出；跨函数或可信序列化 API 摘要如成为必要条件，记录为后续 change，不在本轮自行扩张范围。
