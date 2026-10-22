## ADDED Requirements

### Requirement: Define independent AST-assisted request and report contracts

系统 SHALL 为 `AstAssistedAnalysisRequest`、`AstAssistedAnalysisReport` 和 `CanonicalObjectOverlay` 定义严格 v1 schema、kind、producer/policy version、确定性排序、预算、scope 和跨产物 digest 引用。未知字段、未来版本、混合 profile、重复 identity、悬空或替换依赖 MUST 被拒绝。

#### Scenario: A complete source evidence bundle is consumed

- **WHEN** source facts、entity index、IR binding、P1–P4 dependencies 和 request 的身份/digest 一致
- **THEN** report 接受 bundle，并可从每个 overlay/diagnostic 回溯到源和 IR 证据

#### Scenario: A source fact is replaced after indexing

- **WHEN** report 引用的 source fact digest 与当前提供文件不同
- **THEN** 请求被判陈旧或无效，不把不同代际产物拼接

### Requirement: Expose a bounded source evidence indexing CLI

系统 SHALL 提供 `index-source-evidence --request --artifact-store --output --worker`，要求新且为空的输出目录，按显式 scope 和预算执行逐 TU worker、索引、绑定和 overlay，不扫描目录猜测最新产物、不原生链接且不运行目标程序。stdout 仅输出最终合法报告 JSON，stderr 用于日志。

#### Scenario: Indexing completes without frontier

- **WHEN** 所有计划 TU、实体组和绑定在预算内完成且依赖有效
- **THEN** 命令发布全部产物和完整报告并退出 0

#### Scenario: Useful results remain partial

- **WHEN** 部分 TU 无法重放、存在 binding ambiguity 或预算截断但仍有可用证据
- **THEN** 报告保留结果和 frontier 并退出 2，不把 partial 伪装成成功或风险退出

#### Scenario: The request is invalid or wholly unavailable

- **WHEN** schema/依赖无效、输出目录非空或所有必需输入不可用
- **THEN** 命令退出 1 并尽力输出小型合法失败报告，不删除历史产物

### Requirement: Report layered completeness and bilingual diagnostics

报告 SHALL 分别统计 input/profile、source extraction、entity resolution、entity binding、expression binding、overlay 和 downstream consumption 的 complete/partial/failed/not_run，以及计划/成功 TU、节点、实体、定义、对象、候选、绑定、相关依赖和 frontier 的 hit/total；失败和截断 MUST 留在分母，零分母比例为 null。面向用户的 detail/reason/suggestion SHALL 同时提供中文和英文字段。

#### Scenario: One unrelated translation unit fails

- **WHEN** 某 TU 失败但不在一个已建立 publication candidate 的依赖切片内
- **THEN** 全局 source 完整性仍为 partial，而该 candidate 的相关完整性可按其实际依赖单独计算

#### Scenario: A denominator is zero

- **WHEN** scope 内没有可评价的表达式 binding
- **THEN** 表达式 binding ratio 为 null 并给出中英文原因，不显示 100%

### Requirement: Cache AST-assisted stages without changing semantics

source facts、entity index、binding 和 overlay SHALL 使用独立 cache key，包含 schema/producer/policy、profile、scope、源/include hash、P1 digest 与预算类别；cache hit 时必须重新校验文档和引用。相同输入的 cold/warm semantic digest MUST 一致，时间、路径和 cache counters 不进入 semantic digest。

#### Scenario: A cached binding has a stale dependency

- **WHEN** cache 文档有效但其 ModuleFacts 或 entity index digest 已变化
- **THEN** 拒绝该 cache entry 并确定性重算或报告 partial，不复用陈旧绑定

### Requirement: Preserve legacy protocol and command behavior

P1–P5 已有 artifact schema、reader、CLI 默认语义和退出码 SHALL 保持可读且不被原地改写。AST-assisted 路径必须由显式请求进入；若下游需要新依赖字段，系统 MUST 提供 additive 新版本或包装请求并继续验证旧版本。

#### Scenario: An existing P4 request is rerun without AST evidence

- **WHEN** 用户使用历史合法请求和产物执行原 P4 命令
- **THEN** 行为与 semantic digest 保持既有语义，不隐式扫描或消费 AST 产物
