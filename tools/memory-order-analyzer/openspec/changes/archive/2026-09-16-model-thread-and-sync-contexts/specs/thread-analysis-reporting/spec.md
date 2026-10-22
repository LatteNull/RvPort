## ADDED Requirements

### Requirement: Define a strict versioned thread analysis protocol

系统 SHALL 为 `ThreadAnalysisRequest`、`ThreadLocalFacts`、`ExecutionOrderFacts`、`ThreadContextGraph` 和 `ThreadAnalysisReport` 定义严格 v1 schema、kind 握手、analysis/policy 版本与跨产物引用。未知字段、未知 kind、未来不兼容版本、悬空引用、错误角色或 hash/profile 不一致 MUST 被拒绝，不得按缺省值解释。

#### Scenario: A complete v1 product set is consumed

- **WHEN** 五类产物的 schema、身份、依赖、引用闭包、scope/profile 和实际预算一致
- **THEN** 消费者可构造 P3 图并在报告中登记每个产物及其 digest

#### Scenario: A future or mixed generation is supplied

- **WHEN** 请求混入未知版本、不同 policy、旧 P2 digest 或另一 profile 的 P3 sidecar
- **THEN** 消费者明确拒绝或把相关计划项标为 failed，不静默忽略字段或混合代际

### Requirement: Expose explicit model-threads CLI behavior

系统 SHALL 提供显式 `model-threads` CLI，要求 request、artifact store、新输出目录和 worker，并禁止省略根后隐式扫描。CLI SHALL 在 stdout 只写最终合法报告 JSON、stderr 写日志；退出码 0 表示 complete，2 表示有可用结果但 partial/unknown/定位或输入缺口，1 表示非法请求或全部不可用。

#### Scenario: A valid request completes

- **WHEN** 显式 scope/根和全部依赖有效，所有计划项在预算内完成
- **THEN** 命令以 0 退出并把图、sidecar 和报告发布到新目录，不覆盖历史输出

#### Scenario: Useful results contain unknowns

- **WHEN** 部分线程、join、mutex、原子或 source mapping 未解释，但仍有可消费关系图
- **THEN** 命令尽力输出合法报告并以 2 退出，unknown 仍计入计划和分母

#### Scenario: The request is invalid

- **WHEN** 根为空、scope 非法、输出目录非空、协议不兼容或全部输入不可用
- **THEN** 命令以 1 退出并尽力输出小型合法失败报告，不执行隐式目录扫描或删除旧输出

### Requirement: Report layered completeness and explicit denominators

报告 SHALL 分开保存 input_integrity、effect_analysis、local_thread_analysis、thread_modeling、synchronization_analysis 和 source_mapping 的 complete/partial/failed/not_run 状态，以及根/scope 计划、调用候选、上下文、实例、生命周期、MHP、同步/reads-from、unknown/frontier 的 hit/total。零分母 SHALL 为 null；失败、未运行和过滤项 MUST 留在原始计划分母中。

#### Scenario: One scope member cannot be analyzed

- **WHEN** scope 中一个 TU 的 P3 局部事实失败而其他成员成功
- **THEN** 报告列明计划成员和失败原因，相关阶段不为 complete，成功成员的图仍可用但整体退出为 2

#### Scenario: No candidate exists for a valid empty category

- **WHEN** 有效程序没有 mutex 或原子事件，因此对应候选总数为零
- **THEN** 相关比例为 null 并解释零分母，不显示 100% 或把空类别当作安全结论

### Requirement: Provide bilingual human-facing diagnostics

所有面向用户的 P3 诊断 SHALL 使用稳定、语言无关的 `code`，并成对提供中文 `detail` 与英文 `detail_en`；存在建议时 SHALL 同时提供中文 `suggestion` 与英文 `suggestion_en`。排序、去重、缓存和退出判断 MUST 使用 code/结构化字段而非翻译文本。

#### Scenario: An unresolved thread handle is reported

- **WHEN** join 的 handle provenance 无法唯一确定
- **THEN** 报告包含稳定错误码、含义一致的中英文详情以及成对建议，不只提供一种语言

#### Scenario: A translated string changes

- **WHEN** 文案修订但机器 code、结构化参数和语义输入不变
- **THEN** 规则判定不改变；语义缓存是否重键按版本化展示策略明确处理，不以某一语言文本作为身份

### Requirement: Cache P3 outputs with transitive dependencies

P3 派生缓存 SHALL 包含 BC/P1/P2 digest、scope/profile/boundary、LLVM/worker、线程模型、根/绑定、actual budget 和依赖图；ThreadContext 模板与 ThreadInstance 图 SHALL 使用不同身份。任何被调摘要、局部事实、模型、预算或 scope 变化 MUST 传递失效；损坏/未来版本缓存不得覆盖后伪装修复。

#### Scenario: A worker summary changes without caller BC changing

- **WHEN** worker 的 P2 摘要或 P3 局部事实变化而 root BC 不变
- **THEN** 相关线程上下文、实例、MHP 和报告缓存失效，无关原始 BC 不必重新编译

#### Scenario: A reusable context is instantiated from cache

- **WHEN** 相同 entry/抽象参数命中 ThreadContext 模板但 create 点或父线程不同
- **THEN** 重新生成实例和生命周期身份，不复用旧调用者的 ThreadInstance、handle 或 guard

### Requirement: Never report safety findings during P3

`ThreadAnalysisReport v1` SHALL 始终输出 `safety=not_evaluated` 和 `findings=null`，并明确 complete 仅表示声明 scope、模型和预算内完成关系建模。成功退出、零候选、完整定位或缓存命中 MUST NOT 被表述为并发安全证明。

#### Scenario: Analysis is complete with no unknown frontier

- **WHEN** 所有 P3 阶段 complete 且关系图完全生成
- **THEN** 报告仍保持 safety 未评估和 findings 为空值，仅陈述线程/同步建模完整性
