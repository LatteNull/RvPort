## MODIFIED Requirements

### Requirement: 稳定且双语的结果协议
扫描结果 SHALL 只发布 `schemaVersion: "2.0"` 的 JSON 文档，顶层 MUST 包含 `scan`、`project`、`summary`、`findings` 和 `diagnostics`，并 MAY 包含 `extensions`。公共字段 SHALL 使用 camelCase；`scan` MUST 公开稳定 scan ID、工具/分析版本、请求协议版本、分析范围和 `complete|partial|invalid_request|failed|internal_error` 执行状态；`project` MUST 公开可得的源码版本、文件/翻译单元覆盖状态和 reason codes；summary MUST 公开 assessment 的 planned/completed/matched/notMatched/unknown/skipped/failed 分母、finding/suppression/diagnostic 数量，以及 artifact、source facts、IR facts、evidence binding 和 rules 各层分母。facts-only 请求 MUST 明确规则未请求。所有用户可见的 finding 标题、说明、影响、修复建议和测试建议，以及需要动作的 suppression/diagnostic 信息，MUST 同时提供非空中文与英文字段。

扫描器 MUST NOT 生产旧 `kind/schema_version/analysis_version/request_id/status/metadata` 顶层形状，不得提供旧 serializer、双写、转换器或结果版本选择参数。所有受支持的 scan request 版本均 SHALL 产生同一种 v2 结果；invalid request、failed 和 internal error 也必须通过同一 v2 Schema。

#### Scenario: 完整十规则结果
- **WHEN** 所有计划 facts/evidence 和启用规则的必需 assessments 均完成，且不存在阻断判断的 unresolved unknown
- **THEN** `scan.status` 为 `complete`，各层分母与 findings/suppressions/diagnostics/unknown 计数一致，extensions 公开使用的 artifacts、profiles、build contexts 和规则版本摘要

#### Scenario: 部分规则证据不可用
- **WHEN** 至少一个启用规则完成 assessment，但另一个规则因必需类型、控制流、循环、IR、binding、profile 或 build-context 字段缺失而 unknown/failed
- **THEN** `scan.status` 为 `partial`，保留已完成 findings，并明确未评估 rule/scope，不能把空缺计为 notMatched 或 suppressed

#### Scenario: 无效请求也符合 v2
- **WHEN** 请求 JSON、Schema、规则、profile、build context 或 suppression 在分析前无效
- **THEN** 扫描器输出 `scan.status=invalid_request` 的最小 v2 文档、稳定 reason code 和双语 diagnostic，不输出旧形状或未校验的临时结构

#### Scenario: 双语字段完整
- **WHEN** 任意 finding、可审计 suppression 或需要用户动作的 diagnostic 被发布
- **THEN** 其用户可见内容同时包含非空中英文字段，且两种语言描述同一证据与结论

### Requirement: Finding 结构可定位且可去重
每条 finding SHALL 包含稳定 `id`、`fact`、`conclusion`、非空 `occurrences`、可解析的 `primaryOccurrenceId`、`evidenceChain` 和可选 namespaced `extensions`。`fact` MUST 表达稳定主事实、matched text、主位置和 typed provenance；`conclusion` MUST 表达 finding/rule code、rule version、category、severity、定性 confidence、evidence origin、requiresHumanConfirmation、状态、固定 rationale、完整双语展示字段和结构化 validation plan；occurrences MUST 保存主位置及有界相关位置、configuration、状态、reason codes 和 provenance。validation plan MUST 表达适用 input classes、absolute/relative/ULP/classification/errno/exceptions error metrics、`standard|profile|project-policy|user-provided|unknown` threshold source 及平台/选项/舍入/顺序/repeat strategy；扫描器 MUST NOT 为 unknown 或业务阈值臆造数值。

finding ID MUST 在 suppression 前由规则 code/version、规范化 scope/位置、排序后的语义 evidence refs、evidence origin 和适用 profile/build-context fingerprints 稳定生成，且不得依赖扫描顺序、双语展示文本、suppression 理由、绝对工作区路径或 artifact materialization 根。跨 TU 配置风险 SHALL 依据规则定义的 semantic aggregation key 合并，并以 occurrences 和受影响数量保存全部已确认范围。

#### Scenario: 相同输入重复扫描
- **WHEN** 相同源码、编译上下文、profiles/build contexts、facts/evidence 与规则版本被重复扫描
- **THEN** assessments、finding candidates、finding/occurrence/evidence-chain IDs 和规范化排序保持一致，不受并发调度或 suppression 是否展示该候选影响

#### Scenario: 启发式 finding
- **WHEN** 规则只能根据比较、归约或输入域线索推断风险
- **THEN** conclusion 包含 `evidenceOrigin=heuristic`、`confidence=medium|low`、固定 rationale、`requiresHumanConfirmation=true`，且 validation plan 的业务阈值来源为 `project-policy`、`user-provided` 或 `unknown` 而非扫描器生成值

#### Scenario: 特殊值验证计划
- **WHEN** finding 涉及 libm、fenv 或 NaN/Inf 语义
- **THEN** validation plan 包含适用特殊值/边界 input classes、classification/errno/exceptions metrics 和明确的平台、rounding 或重复策略

#### Scenario: 同一配置跨多个翻译单元
- **WHEN** 多个翻译单元具有相同的有效危险语义和相同规则 aggregation key
- **THEN** 结果发布一个主 finding，使用 occurrences 和受影响数量保存全部已确认范围，避免按原始命令文本重复报告

#### Scenario: 语义证据变化
- **WHEN** profile/build-context fingerprint、rule major version、effective semantics 或关联 IR evidence 发生变化
- **THEN** assessment/finding identity 或 semantic fingerprint 相应变化，不与旧结论错误去重

### Requirement: 明确状态与退出码映射
CLI SHALL 使用固定退出码：`0` 表示 `scan.status=complete`，`2` 表示 `scan.status=invalid_request`，`3` 表示无可用结果的 `scan.status=failed`，`4` 表示 `scan.status=partial`，`5` 表示 `scan.status=internal_error`。发现任意数量的浮点风险本身 MUST NOT 改变退出码；CI 是否因风险失败由独立策略层决定。`project.status`、assessment status 和 evidence-chain status 只表达覆盖完整性，不得覆盖 scan 执行状态。

#### Scenario: 扫描发现高风险项
- **WHEN** 扫描完整结束且存在 `critical` 或 `high` finding
- **THEN** `scan.status` 仍为 `complete` 且退出码为 `0`，风险数量通过 summary 和 findings 表达

#### Scenario: 部分扫描
- **WHEN** 至少一个翻译单元或必需 assessment 完成，且至少一个计划翻译单元或启用规则的必需 assessment 未完成
- **THEN** `scan.status` 为 `partial`、退出码为 `4`，并公开 planned/completed/failed/unknown 分母和 evidence-chain breaks

### Requirement: Suppression 必须有理由且可审计
扫描器 SHALL 在 finding candidate 和稳定 finding ID 生成后应用 request 或源码 suppression。每条有效 suppression MUST 在 `org.rvport.floating-point-scanner.suppressions` 扩展中精确记录 rule code、规范化路径/范围、双语理由、来源、candidate finding ID 和匹配结果；被抑制候选不得出现在 `findings`，但 MUST 出现在有界 suppression audit records 并计入 `summary.suppressed`。无理由、未知 code、范围歧义、越界路径或全规则通配 MUST NOT 隐藏结果。

#### Scenario: 请求抑制匹配单个 finding
- **WHEN** 有效 request suppression 的 code、路径和行范围唯一匹配 finding candidate
- **THEN** candidate ID 保持稳定、finding 不发布、suppression audit record 和 suppressed 计数增加

#### Scenario: 带理由的源码抑制
- **WHEN** 严格格式的 `fp-precision-scanner: ignore <code> -- <reason>` 注释可唯一绑定相邻声明或表达式
- **THEN** 只抑制该范围对应 code，并记录 spelling/expansion provenance 和双语理由

#### Scenario: 源码抑制范围歧义
- **WHEN** 宏、模板或同位置多个表达式导致注释无法唯一绑定
- **THEN** suppression 不生效，输出双语 diagnostic 且候选 finding 仍发布

### Requirement: 结果必须公开稳定预算、缓存和 suppression 审计
结果 v2 SHALL 在 `org.rvport.floating-point-scanner.runtime` 扩展中公开预算 limits、稳定逻辑用量、frontiers、cache schema/version 与 hit/miss/corrupt/write 计数，并在 suppressions 扩展中公开 applied、expired、unmatched 或 budgetUnrecorded 状态及双语理由。实际 wall/CPU/RSS telemetry、绝对 cache root 和系统时间 MUST NOT 进入 scan result semantic digest。命名空间扩展键 MUST 匹配 `org.rvport.floating-point-scanner.*`，其值 MUST 通过已注册 Schema 校验；不得使用未命名的任意对象绕过公共协议。

#### Scenario: 热缓存命中
- **WHEN** source facts、IR facts 或 evidence 从有效缓存读取
- **THEN** runtime 扩展增加对应 hit 计数，但 findings、assessments、evidence chains 和 semantic digest 与冷缓存运行相同

#### Scenario: 非法扩展命名空间
- **WHEN** 结果包含未注册、非浮点扫描器命名空间或不符合对应扩展 Schema 的字段
- **THEN** 结果校验失败且不得作为有效产物原子发布

## ADDED Requirements

### Requirement: Evidence chain 引用必须完整闭合
每条 finding 的 evidence chain SHALL 包含稳定 `rootStepId`、非空 `primaryPath`、steps、edges、breaks、impactStepIds 和预算。typed reference kinds MUST 使用浮点专属词汇并至少覆盖 source fact、IR fact、AST↔IR binding、profile、build context、compile option 和 assessment。所有 primary occurrence、step、edge、path、impact、diagnostic finding 和 extension references MUST 在文档内唯一解析，或显式引用具有 producer、schema 和 digest 的外部审计对象。complete chain MUST 不含 breaks；partial/ambiguous/unknown chain MUST 包含稳定 reason codes 和至少一个 break。扫描器不得借用 KB Scanner 的 knowledge、fact、reason 或 step 枚举表达浮点语义。

#### Scenario: 完整 AST 到 IR 证据链
- **WHEN** finding 同时具有 canonical AST fact、LLVM IR fact、可靠 binding、profiles 和 matched assessment
- **THEN** primary path 按稳定顺序连接 source fact、binding、IR observation、profile/build context、assessment 和 conclusion，所有 edge 端点及 provenance references 均可解析

#### Scenario: IR 证据缺失
- **WHEN** 规则需要 IR 证据但对应 artifact、fact 或 binding 不可用
- **THEN** evidence chain 为 partial 或 unknown，包含明确 break/frontier，且不得生成声称 IR 支持完整的 deterministic path

#### Scenario: 悬空引用
- **WHEN** primaryOccurrenceId、edge 端点、primaryPath、impactStepId 或 diagnostic finding ID 无法解析
- **THEN** v2 contract 校验失败且结果不得发布

### Requirement: 浮点专属扩展必须保留审计分母
结果 v2 SHALL 使用 `org.rvport.floating-point-scanner.analysis`、`profiles`、`artifacts`、`suppressions` 和 `runtime` 等受约束扩展保存不属于公共骨架的完整审计语义。analysis 扩展 MUST 保存全部 assessments、规则 registry digest、启用规则/版本/依赖、analysis scope 和各层摘要，使没有 finding 的 notMatched、unknown、skipped 和 failed assessments 仍可审计。profiles/artifacts 扩展 MUST 保存 source/target fingerprints、可选 build-context fingerprints、共享 BC 身份、bundle digests、IR capabilities 和 source mapping 状态。完整 raw facts/evidence MAY 通过 producer、schema 和 digest 引用独立 bundle；不得以无界、无 Schema 的旧顶层数组重新引入。

#### Scenario: 规则未产生 finding
- **WHEN** assessment 为 notMatched、unknown、skipped 或 failed
- **THEN** assessment 仍存在于 analysis 扩展并计入 summary，unknown/failed reason 和 evidence frontier 可审计，不因 findings 为空而丢失

#### Scenario: Facts-only 扫描
- **WHEN** 请求显式不启用风险规则
- **THEN** findings 为空、analysis scope 明确为 factsOnly、assessment 分母为零，并通过 artifact/bundle references 公开已完成 facts/evidence，而不是描述为未发现风险
