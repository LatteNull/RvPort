# publication-risk-reporting

## Purpose

规范 P4 发布风险分析的版本化请求、显式命令行入口、分层完整性与精确分母、双语诊断、传递缓存身份、语言配置证据，以及仅限受支持模型范围的风险结论和退出码语义。

## Requirements

### Requirement: Define strict versioned P4 request, graph and report contracts
系统 SHALL 为 `PublicationRiskRequest`、`PublicationLocalFacts`、`SinglePublicationProtocolGraph` 和 `PublicationRiskReport` 定义严格 v1 schema、kind、analysis/policy/model 版本、确定性排序和跨产物引用。未知字段/kind、未来版本、悬空引用、错误线程/调用/对象角色、混合 profile 或 digest 不一致 MUST 被拒绝，不得填默认值接受。

#### Scenario: A complete P4 product set is consumed
- **WHEN** 四类 P4 产物及 P1/P2/P3 依赖的版本、scope/profile、预算、身份和引用闭包一致
- **THEN** 消费者接受并在报告中登记每项依赖及 digest

#### Scenario: A graph cites another thread analysis generation
- **WHEN** 协议候选引用的 ThreadInstance 或 effect 来自不同 request/hash 的 P3 图
- **THEN** 拒绝该图，不把不同代际关系拼成风险证明

### Requirement: Expose an explicit detect-publication-risks CLI
系统 SHALL 提供 `detect-publication-risks --request --artifact-store --output --worker`，从风险请求显式解析并校验完整 P3 请求，生成或复用其精确依赖；SHALL 要求新输出目录，不扫描目录选择最新图，不隐式扩大 roots/scope，不 llvm-link、不原生链接且不运行目标程序。stdout 只输出最终合法报告 JSON，stderr 用于日志。

#### Scenario: A valid complete request has findings
- **WHEN** 所有计划层 complete 且至少一个 P4 finding
- **THEN** 命令发布 request、sidecar、协议图、依赖和报告到新目录并退出 3

#### Scenario: A usable request is incomplete
- **WHEN** 有可用候选或 finding 但任一相关层 partial、unknown、unsupported 或定位不完整
- **THEN** 命令尽力发布合法报告并退出 2，不能因同时有 finding 改为 3

#### Scenario: The request is invalid or wholly unavailable
- **WHEN** 请求/依赖/schema 无效、输出目录非空或全部必要输入不可用
- **THEN** 命令退出 1 并尽力输出小型合法失败报告，不删除历史结果

#### Scenario: A complete request has no supported finding
- **WHEN** 全部计划项 complete 且 finding 数为零
- **THEN** 命令退出 0，但报告 safety 保持 `not_established`

### Requirement: Report layered completeness and exact denominators
报告 SHALL 分开保存 input、P1、P2、P3、publication-local、candidate-modeling、risk-evaluation 和 source-mapping 的 complete/partial/failed/not_run 状态，并为成员、根、局部事实、协议计划、candidate、evaluated、finding、discharged、unknown、unsupported、excluded 和 frontier 提供明确 hit/total。失败、截断和未运行项 MUST 留在分母；零分母比例为 null。

#### Scenario: Candidate expansion stops at a budget
- **WHEN** 已生成部分候选后达到协议或 assessment 上限
- **THEN** 报告已知结果、未处理计划、实际预算和非空 frontier，risk-evaluation 不为 complete

#### Scenario: There are zero protocol candidates
- **WHEN** 所有输入完整但候选计划为空
- **THEN** candidate ratio 为 null，verdict 只表示没有受支持风险，不显示 100% 安全

### Requirement: Separate supported-scope verdicts from safety
`PublicationRiskReport` 顶层 `safety` SHALL 固定为 `not_established`，`verdict` 仅允许 `risks_found`、`no_supported_risk_found`、`inconclusive` 或 `failed`。discharged SHALL 明确限定到规则/模型/候选条件；零 finding、完整运行、缓存命中或正确对照 MUST NOT 被描述为全程序安全。

#### Scenario: Every recognized candidate is discharged
- **WHEN** 全部候选在受限 release/acquire 或 seq_cst 条件下消解且分析完整
- **THEN** verdict 可为 no_supported_risk_found，但 safety 仍 not_established，并列出模型边界

#### Scenario: Relevant evidence is unknown
- **WHEN** 候选的写者、gate、reads-from、同步或对象证据不完整
- **THEN** verdict 为 inconclusive，不能通过丢弃候选得到零 finding 结论

### Requirement: Publish explainable bilingual findings and diagnostics
每个 assessment SHALL 保存稳定 code、规则/模型版本、protocol ID、语言/编译配置、线程实例、flag/payload 对象范围、事件、成功谓词、关键路径、已有/缺失同步、假设、限制、证据等级和 IR/source 位置。所有面向用户字段 SHALL 成对提供 `detail/detail_en`；存在建议时 SHALL 成对提供 `suggestion/suggestion_en`。机器排序、去重、缓存和退出码 MUST 不依赖翻译文本。

#### Scenario: A relaxed publication is reported without debug info
- **WHEN** IR 证据完整但 BC 没有源码定位
- **THEN** finding 保留事件 ID、对象、线程、缺失边和中英文说明，source mapping 单独 unavailable/partial

#### Scenario: A fix suggestion is emitted
- **WHEN** finding 建议调整协议中的 release/acquire 或使用受支持锁
- **THEN** 中英文建议含义一致且与实际对象/操作类型匹配，不对普通 bool 建议调用 atomic `.store()`，不统一建议 seq_cst

### Requirement: Cache P4 outputs with transitive identities
P4 缓存 SHALL 包含 BC/P1/P2/P3 digest、完整 thread request、scope/profile/boundary、语言模型、LLVM/worker、P4 policy/model、实际预算、局部 sidecar 和候选依赖。局部模板与 ThreadInstance/SuccessfulObservation 实例 SHALL 分离；依赖、模型、预算或 scope 变化 MUST 传递失效，损坏/未来版本缓存不得覆盖后伪装修复。

#### Scenario: Only a callee wrapper changes
- **WHEN** caller BC 不变但跨 TU observation wrapper 的摘要或局部事实改变
- **THEN** 相关成功观察、协议图和报告缓存失效，无关原始 BC 不必重编译

#### Scenario: A cached template is bound to another create site
- **WHEN** 局部 observation 模板相同但父线程、create site、invocation 或 guard 不同
- **THEN** 重新生成实例身份，不泄漏旧 ThreadInstance 或成功观察关系

### Requirement: Record language and compilation identity per assessment
系统 SHALL 从已保存编译记录和 artifact/profile 证据登记 GCC/Clang 来源、分析 BC producer、target/layout、C/C++ 语言和 C11/C17/C++17/C++20 profile。无法验证语言标准、跨语言 atomic 互操作或 source-preserving/build-faithful 对应关系时 SHALL 降级，不得采用宿主默认标准或拼接不同配置的指令。

#### Scenario: The compile command names an explicit supported standard
- **WHEN** 候选全部 TU 的记录明确且兼容地指定受支持 `-std`
- **THEN** assessment 保存该 profile 和原始配置身份并按对应语言模型解释

#### Scenario: The standard cannot be verified
- **WHEN** 编译记录缺失、默认标准无法可靠还原或候选跨越不兼容语言边界
- **THEN** 相关评估为 partial/unknown，报告说明限制而非猜测语言语义

+### Requirement: Separate degraded source candidates from P4 risk products

风险报告或其 additive wrapper SHALL 分别引用 SourceCandidate 与 P4 protocol/assessment；source-only 候选不得获得 finding code、severity、discharged 状态或风险计数。面向用户的 mode、evidence、failure、missing evidence、limitation 和 suggestion SHALL 同时提供中文与英文字段，机器 identity 不依赖翻译。

#### Scenario: Archived mutex sample becomes inconclusive

- **WHEN** `safe/03_pthread_mutex.cpp` 的相关 `std::lock_guard` 只形成未知 RAII SynchronizationGap
- **THEN** 报告将原确定风险降为 unknown/partial，说明缺少 RAII mutex 证明，不宣称样例安全

### Requirement: Preserve risk exit codes under degraded orchestration

组合入口 SHALL 保持 0=完整无正式风险、3=存在正式 P4 risk 且请求不因更高优先级缺口而 incomplete、2=存在可用 partial/unknown/source candidate/预算截断、1=无效或全部不可用。SourceCandidate MUST NOT 单独触发 3，零 source candidate 或零 finding MUST NOT 表示安全。

#### Scenario: Formal risk and AST-only candidate coexist

- **WHEN** 一个完整候选产生 P4 risk，另一个计划候选仅为 AST-only
- **THEN** 组合请求按 incomplete 优先退出 2，同时保留正式 risk 和 source candidate 的独立计数

### Requirement: Cite A4 evidence without changing P4 result semantics

PublicationRiskReport 或 additive wrapper SHALL 引用采用或拒绝的 A4 proof、mutex/owner/thread/held-region、profile、完整性和 gap；既有 finding code、severity、discharged、unknown、`safety=not_established` 与 0/3/2/1 退出码语义 MUST 保持不变。面向用户的说明和建议 SHALL 同时提供中文与英文。

#### Scenario: Archived mutex sample is discharged in the bounded model
- **WHEN** `safe/03_pthread_mutex.cpp` 的锁定本地副本通过完整 A4 proof 消解原候选
- **THEN** 报告说明“在受限同 mutex 模型内消解”、证据链与限制，不输出“线程安全”或“全程序安全”

#### Scenario: A4 is unavailable
- **WHEN** 候选依赖 RAII 同步但 A4 未请求、失败或 partial
- **THEN** 保持 unknown/partial 和现有退出码规则，不把零 proof 计作零风险

### Requirement: Preserve candidate-relevant exit-code priority

正式 P4 risk 仅在没有更高优先级候选相关 A4/A2 缺口时触发 `3`；存在相关 partial/unknown/frontier 时 SHALL 返回 `2`，无效或全部不可用返回 `1`，完整无正式风险返回 `0`。A4 自身的完成状态不得覆盖 P4 的风险优先级。

#### Scenario: One candidate is risky and another has an A4 gap
- **WHEN** 报告同时存在正式风险和候选相关 RAII 未决缺口
- **THEN** 依照既有完整性优先规则选择退出码并分别保留两类证据，不用 A4 完成度抹除风险或缺口
