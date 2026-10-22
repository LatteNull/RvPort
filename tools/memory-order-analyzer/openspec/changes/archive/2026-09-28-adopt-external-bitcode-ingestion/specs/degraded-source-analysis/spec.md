## MODIFIED Requirements

### Requirement: Classify evidence availability per translation unit and candidate
系统 SHALL 分别记录每个 bundle 计划 TU 的可信 AST、外部 BC/P1 ingestion 和所需下游阶段状态，并为 TU 与候选计算 `ast-ir`、`ir-only`、`ast-only` 或 `failed`；同一请求包含多类时 SHALL 报告 mixed 和每类 hit/total，不得选择最乐观模式覆盖外部 missing/failed 或 source 缺口。分析器不得通过现场生成 BC 改变分类。

#### Scenario: AST succeeds while external IR is unavailable
- **WHEN** 一个 TU 形成可信 SourceSemanticFacts，但 bundle 将 BC 记录为 missing/failed，或 ingestion verify/reader 失败
- **THEN** 该 TU 为 ast-only，保留 source digest 与外部 IR 缺口，不调用 emission 且不声称 P1 或 P4 已运行

#### Scenario: One unrelated TU is ast-only
- **WHEN** 一个正式 P4 候选的依赖闭包全部为 ast-ir，而 scope 中另一个可证明无关 TU 仅有 AST
- **THEN** 该候选仍可按 ast-ir 评价，请求顶层保持 mixed/partial并保留外部计划分母

#### Scenario: Neither AST nor external IR is trustworthy
- **WHEN** 源码/profile 不可信且对应外部 record missing、failed 或无效
- **THEN** TU 为 failed，不把错误恢复 AST、debug path 或同名 BC 提升为可信候选

### Requirement: Publish stable stage-specific failure classifications
系统 SHALL 至少区分 `frontend-invalid`、`profile-replay-incompatible`、`external-artifact-missing`、`external-build-failed`、`artifact-format-unsupported`、`reader-incompatible`、`artifact-validation-failed`、`worker-budget` 和 `analysis-stage-failed`，并记录 stage、deterministic/transient、受限原始诊断、中英文 detail 及已完成产物。历史 `ir-generation-failed` MAY 仅用于读取旧报告，不得描述当前分析器执行了 BC emission；分类 MUST NOT 把上游构建失败、输入损坏、source worker、资源截断和语义 unsupported 合并为同一 compile failure。

#### Scenario: GCC record cannot be replayed by source worker
- **WHEN** GCC-only 扩展或关键 ABI/profile 选项无法由锁定 Clang source worker 等价解析，但外部 BC 可读
- **THEN** 记录 profile-replay-incompatible 和 AST 缺口，保留 IR-only，不伪造 AST 与 BC 同 profile

#### Scenario: External build reports a missing TU
- **WHEN** bundle record 状态为 failed 且包含上游受限诊断
- **THEN** 记录 external-build-failed、stage=upstream-build，并保持 planned TU，不由分析器重试编译

#### Scenario: P3 exceeds its output budget
- **WHEN** AST、外部 BC、P1/P2 可用但 P3 worker 达到输出预算
- **THEN** 记录 worker-budget、stage=P3 和既有证据，相关候选为 partial/unknown 而非上游构建或 ingestion failure

### Requirement: Expose bounded degraded analysis with deterministic cache and exit semantics
系统 SHALL 提供 `analyze-degraded-source --request --artifact-store --output --source-worker --ir-worker`，要求新建空输出目录并只消费已完成 external ingestion 的 artifact store；禁止扫描最新产物、扩大 scope、生成/链接 BC、运行构建或目标。source、availability、candidate 和组合报告 SHALL 使用包含 schema/policy、bundle/record、scope/profile、源码/include、artifact/依赖 digest、预算类别和工具链的分层 cache；cold/warm semantic digest MUST 一致，瞬态 timeout/crash 和 partial ingestion 不得作为长期 complete cache hit。

#### Scenario: Usable AST-only evidence remains
- **WHEN** 请求有效且存在 source candidate、unknown、partial、预算截断或不能完整评价的 mixed 模式
- **THEN** 命令发布合法报告并退出 2，source candidate 不触发风险退出 3，也不现场生成 BC

#### Scenario: A formal P4 risk is complete
- **WHEN** 至少一个 ast-ir/ir-only 候选由既有 P4 输出正式 risk，且没有优先级更高的 candidate-relevant incomplete
- **THEN** 新命令引用该 P4 证据并退出 3，不把 source candidate 或 ingestion 成功计为 risk

#### Scenario: All requested evidence is unavailable
- **WHEN** 请求/schema 无效、输出目录非空或所有 bundle 计划 TU 均 failed 且没有可信 source/IR 事实
- **THEN** 命令退出 1 并尽力输出最小中英文失败报告，不调用 compiler/linker恢复输入
