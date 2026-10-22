## ADDED Requirements

### Requirement: Define independent degraded source analysis contracts

系统 SHALL 定义严格、版本化的 `DegradedSourceAnalysisRequest v1`、`TUEvidenceAvailability v1`、`SourceCandidate v1` 和 `DegradedSourceAnalysisReport v1`，包含 kind、schema/producer/policy identity、scope/profile、预算、确定排序、canonical digest 和显式依赖引用。未知字段、未来版本、悬空或替换依赖、混合 profile 及重复身份 MUST 被拒绝；P1–P4 与 A1 已有协议原义不得修改。

#### Scenario: A report dependency is replaced

- **WHEN** 报告引用的 source facts、BC/P1 或下游产物 digest 与提供文件不一致
- **THEN** 消费者拒绝报告或标记陈旧，不把新旧证据拼接成一种模式

#### Scenario: Existing analysis is used without degraded mode

- **WHEN** 调用方继续使用既有 P1–P4 或 AST-assisted 请求且未提供新协议
- **THEN** 旧 schema、默认行为、cache identity 和退出语义保持兼容

### Requirement: Classify evidence availability per translation unit and candidate

系统 SHALL 分别记录每个计划 TU 的可信 AST、BC/P1 和所需下游阶段状态，并为 TU 与候选计算 `ast-ir`、`ir-only`、`ast-only` 或 `failed`；同一请求包含多类时 SHALL 报告 mixed 和每类 hit/total，不得选择最乐观模式覆盖其他失败。

#### Scenario: AST succeeds while IR generation fails

- **WHEN** 一个 TU 在同一 profile 下形成可信 SourceSemanticFacts，但 BC emission、verify 或序列化失败
- **THEN** 该 TU 为 ast-only，保留 source digest 与 IR 失败原因，不声称 P1 或 P4 已运行

#### Scenario: One unrelated TU is ast-only

- **WHEN** 一个正式 P4 候选的依赖闭包全部为 ast-ir，而 scope 中另一个无关 TU 仅有 AST
- **THEN** 该候选仍可按 ast-ir 评价，请求顶层保持 mixed/partial 并保留无关 TU 分母

#### Scenario: Neither AST nor IR is trustworthy

- **WHEN** 缺失必需 include、宏或生成物，或 fatal 语法/类型错误使 AST 不可信且 BC 不可用
- **THEN** TU 为 failed，不把错误恢复 AST 提升为 source candidate

### Requirement: Publish stable stage-specific failure classifications

系统 SHALL 至少区分 `frontend-invalid`、`profile-replay-incompatible`、`ir-generation-failed`、`worker-budget`、`artifact-validation-failed` 和 `analysis-stage-failed`，并记录 stage、deterministic/transient、受限原始诊断、中英文 detail 及已完成产物。分类 MUST NOT 把用户源码无效、工具失败、资源截断和语义 unsupported 合并为同一 compile failure。

#### Scenario: GCC record cannot be replayed by Clang

- **WHEN** GCC-only 扩展或关键 ABI/profile 选项无法由锁定 Clang 等价解析
- **THEN** 记录 profile-replay-incompatible 和受影响阶段，不伪造 Clang AST 与 GCC BC 同 profile

#### Scenario: P3 exceeds its output budget

- **WHEN** AST、BC、P1/P2 可用但 P3 worker 达到输出预算
- **THEN** 记录 worker-budget、stage=P3 和既有证据，相关候选为 partial/unknown 而非 frontend 或 compile failure

### Requirement: Keep AST-only source candidates below the memory-model proof boundary

AST-only 模式 SHALL 仅发布 `evidence_level=source-only`、`verdict=unknown`、`safety=not-established` 的 SourceCandidate，列出源实体、对象/调用/控制候选、假设、依赖闭包及缺失的 IR memory effect、ordering、访问范围、线程实例、RF/SW/HB 证据。SourceCandidate MUST NOT 使用 P4 finding identity，不得单独生成或提升 sequenced-before、reads-from、synchronizes-with、happens-before、risk、discharged 或安全结论。

#### Scenario: Source shows a relaxed atomic publication shape

- **WHEN** AST 识别 `_Atomic`/`std::atomic`、pthread callback 和消费者条件，但相关 TU 无可信 IR
- **THEN** 输出 source-only candidate 和缺失证据，不输出 publication-order-risk 或 potential-data-race

#### Scenario: Source order resembles payload before publication

- **WHEN** AST 存在受限 source sequence 但任一端没有唯一真实 IR memory effect
- **THEN** 只保留源码关系候选，不建立 must-before、RF、SW、HB 或 discharge

### Requirement: Slice degradation by candidate dependencies

系统 SHALL 以 TU、source entity、binding、object、call、thread instance、memory effect、synchronization gap 和 protocol candidate 构建传递依赖切片。缺口与候选可证明无关时不得清空候选；缺口可能相关且无法证明无关时 MUST 降级该候选。计划、完成、失败、source candidate、P4 candidate、finding、discharged、unknown、unsupported 和 excluded SHALL 分别计数。

#### Scenario: A failed helper is on the candidate call path

- **WHEN** flag 或 payload wrapper 依赖一个只有 AST 或完全失败的 TU
- **THEN** 相关候选降为 ast-only/unknown 并列明缺失依赖，不能借用其他 TU 的 IR

#### Scenario: A failed utility TU is outside the slice

- **WHEN** 失败 TU 与候选线程、对象、调用、同步和控制闭包均可证明无关
- **THEN** 正式 assessment 保留，顶层报告仍反映失败 TU 和非完整 scope

### Requirement: Expose bounded degraded analysis with deterministic cache and exit semantics

系统 SHALL 提供 `analyze-degraded-source --request --artifact-store --output --source-worker --ir-worker`，要求新建空输出目录，禁止扫描最新产物、扩大 scope、原生链接或运行目标。source、availability、candidate 和组合报告 SHALL 使用包含 schema/policy、scope/profile、源码/include、依赖 digest、预算类别和工具链的分层 cache；cold/warm semantic digest MUST 一致，瞬态 timeout/crash 不得作为长期语义 cache hit。

#### Scenario: Usable AST-only evidence remains

- **WHEN** 请求有效且存在 source candidate、unknown、partial、预算截断或不能完整评价的 mixed 模式
- **THEN** 命令发布合法报告并退出 2，source candidate 不触发风险退出 3

#### Scenario: A formal P4 risk is complete

- **WHEN** 至少一个 ast-ir/ir-only 候选由既有 P4 输出正式 risk，且没有优先级更高的请求级 incomplete
- **THEN** 新命令引用该 P4 证据并退出 3，不把 source candidate 计为 risk

#### Scenario: All requested evidence is unavailable

- **WHEN** 请求/schema 无效、输出目录非空或所有计划 TU 均 failed 且没有可信事实
- **THEN** 命令退出 1 并尽力输出最小中英文失败报告
