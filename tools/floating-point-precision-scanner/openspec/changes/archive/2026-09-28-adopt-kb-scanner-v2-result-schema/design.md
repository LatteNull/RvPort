## Context

浮点精度扫描器当前将 `summary`、`assessments`、`findings`、`suppressions`、`diagnostics`、`facts`、`ir_facts`、`evidence` 和 `metadata` 平铺在 `FloatingPointPrecisionScanResult@1.4` 中。KB Scanner 已采用 v2 的 `scan/project/summary/findings/diagnostics/extensions` 报告骨架，并以 `fact/conclusion/occurrences/evidenceChain` 表达 finding 的事实、判断、位置和推导关系。

旧浮点结果协议尚无外部消费者，但项目内 CLI、协议校验、validation corpus、benchmark、fixtures 和测试均依赖其字段。本变更因此可以直接切换唯一输出协议，但必须原子迁移全部项目内消费者，并保持现有十类规则、unknown/failure 分母、稳定 ID、双语诊断、suppression、预算、缓存和确定性语义不退化。

## Goals / Non-Goals

**Goals:**

- 将唯一生产结果切换为 `schemaVersion: "2.0"`，采用 KB Scanner v2 风格的公共骨架和 camelCase 字段。
- 通过 finding 内的 typed references 和 evidence chain 直接表达 AST、IR、binding、profile、build context、assessment 与结论的关系。
- 保留完整浮点语义、双语展示、失败分母、suppression 审计、稳定身份、确定性排序和原子输出。
- 为正常、partial、invalid request、failed 和 internal error 产生同一 Schema 下可验证的结果。
- 在一个变更中切换全部项目内生产者、消费者、fixtures、corpus、benchmark 和文档。

**Non-Goals:**

- 不保留 v1.4 输出、不提供双写、兼容 serializer、转换 CLI 或版本选择参数。
- 不修改 scan request、canonical AST facts、LLVM facts、AST↔IR evidence、共享 BC manifest、cache entry 或 validation result 协议。
- 不修改后端、前端、共享 BC 生产逻辑、任务编排和其他分析工具。
- 不照搬 KB Scanner 的 knowledge source、fact kind、reason code、step kind 或业务词汇表。

## Decisions

### 1. 采用相同骨架而不是直接复用 KB Scanner Schema

结果顶层固定为：

```text
schemaVersion
scan
project
summary
findings[]
diagnostics[]
extensions?
```

`schemaVersion` 固定为 `2.0`。`scan` 保存请求/分析版本、工具身份、分析范围和执行状态；`project` 保存源码版本、文件/翻译单元完成状态和 reason codes；`summary` 保存 finding、suppression、diagnostic、assessment 和各分析层的完整分母。

不直接引用 KB Schema，因为其 `tool.name=kb-scanner`、knowledge sources、fact/step/reason enums 和 readiness 语义属于 KB Scanner。浮点结果定义自己的词汇表，同时保持对象层次、引用方式和扩展机制一致。

### 2. 直接替换唯一输出，不建立兼容层

实现删除旧结果 Schema 及旧生产/消费路径，CLI 始终输出 v2。请求协议仍可接受当前支持的 request schema 版本，但所有请求版本均得到同一种 v2 结果；不增加 `--result-schema-version` 或类似开关。

这样避免维护双序列化和等价性分支。代价是项目内所有旧字段读取必须一次性迁移，不能遗留 fallback。

### 3. 在独立 projector 中将内部分析模型投影为 v2

规则、facts、IR worker、evidence builder 和 suppression engine 继续使用现有内部语义模型。新增单一 v2 projector/serializer 边界，负责：

1. 生成 `scan/project/summary`；
2. 将 finding candidate 投影为 `fact/conclusion/occurrences/evidenceChain`；
3. 投影聚合 diagnostics 和 namespaced extensions；
4. 执行引用闭合、计数一致性、路径边界、双语完整性和确定性排序校验；
5. 产生用于原子写出的最终 JSON。

不得由 CLI、后端或每条规则分别拼接公开协议。异常和无效请求也通过同一 projector 的最小失败模型输出，从而保证失败结果仍通过 v2 Schema。

### 4. Finding 使用 KB v2 的六段式结构

每条 finding 必须包含：

- `id`：现有稳定 finding 身份的 camelCase 投影；
- `fact`：一个稳定主事实锚点，包含浮点 fact kind、matched text、主位置和 typed provenance；
- `conclusion`：规则、类别、严重性、定性 confidence、evidence origin、人工确认要求、状态、双语标题/说明/影响/建议/测试建议和 validation plan；
- `occurrences`：主位置及有界相关位置，保留 configuration、状态、reason codes 和 provenance；
- `primaryOccurrenceId`：必须解析到同 finding 内唯一 occurrence；
- `evidenceChain`：从事实/配置/profile/IR/binding 到 assessment/conclusion 的 steps、edges、primary path、breaks 和预算。

confidence 继续使用 `high|medium|low`，不为对齐 KB Schema 而伪造未校准的数值分数。启发式 finding 必须继续显式输出 evidence origin 和人工确认要求。

### 5. Evidence chain 使用浮点专属引用词汇并要求闭合

typed reference kinds 至少覆盖 `sourceFact`、`irFact`、`binding`、`profile`、`buildContext`、`compileOption` 和 `assessment`。step kinds 与 edge kinds 使用浮点扫描词汇，例如 source/IR observation、profile/build context、binding、assessment，以及 `supports`、`derivedFrom`、`binds`、`mapsTo`、`assessedAs`。

所有 finding、occurrence、step、edge、primary path、impact step、diagnostic finding reference 和 extension reference 必须在文档内解析或显式指向带 producer/digest 的外部审计对象。重复 ID、悬空引用、循环 primary path、主 occurrence 不存在或 complete chain 含 break 均使结果构建失败，不得发布半合法 JSON。

unknown/partial 的断点必须通过 `breaks` 和 reason codes 表达，不能把缺失路径伪装成完整 evidence chain。

### 6. 浮点专属数据进入受约束的命名空间扩展

公共 `extensions` 的键必须匹配 `org.rvport.floating-point-scanner.*`。预定义扩展至少包括：

- `analysis`：全部 assessments、规则 registry digest、规则版本/依赖、analysis scope 和 layer/bundle 摘要；
- `profiles`：source/target profile 与可选 build-context fingerprints；
- `artifacts`：共享 BC artifact-set 身份、bundle digests、IR 能力和 source mapping 状态；
- `suppressions`：applied/expired/unmatched/budget-unrecorded 审计记录；
- `runtime`：稳定预算 limits、logical usage、frontiers 和 cache 计数。

旧顶层 raw facts/IR facts/evidence 不再作为无约束公共数组存在。finding 所需证据通过 evidence chain 引用；完整审计数据需要保留时，放入受 Schema 约束的 `analysis` 扩展或以 producer、schema、digest 引用独立既有 bundle。不得将实际 wall/CPU/RSS 样本、系统时间或绝对路径写入语义结果。

### 7. 双语内容在 v2 中仍为核心必填字段

`conclusion` 必须同时提供 `title/titleEn`、`message/messageEn`、`impact/impactEn`、`suggestion/suggestionEn` 和 `testSuggestion/testSuggestionEn`。需要用户动作的 diagnostic 和所有 suppression 审计必须提供等价的中英文 message/reason/suggestion。

语言字段不进入稳定 finding ID、step/edge ID 或 semantic digest。仅展示文本变化不得改变身份和证据关系。

### 8. 状态、退出码和风险策略保持分离

执行状态移入 `scan.status`，继续使用 `complete|partial|invalid_request|failed|internal_error`，退出码仍为 `0|4|2|3|5`。`project.status` 和 evidence chain status 表达分析覆盖完整性，不替代执行状态。

finding 的严重性或数量不得改变退出码，v2 Schema 不引入后端 CI blocking 策略。`summary` 只报告可验证计数和风险分类。

### 9. 以语义规范化结果驱动确定性和大小预算

projector 在所有候选稳定排序后生成 occurrences、steps、edges、breaks、diagnostics 和 extensions。semantic digest 排除展示文本、物理根目录、实际资源采样和 cache 热冷差异。输出大小预算在稳定顺序上执行；截断必须产生 frontier、partial 状态和完整引用闭合，不能留下悬空边或引用。

最终文档必须先通过 JSON Schema、引用规则和跨字段不变量校验，再通过现有临时文件、fsync 和原子 replace 发布。

## Risks / Trade-offs

- **[破坏性切换导致项目内脚本遗漏]** → 全仓搜索旧字段和 `schema_version=1.4` 结果断言，增加禁止旧结果生产/消费的 contract test。
- **[公共骨架与 KB v2 逐渐漂移]** → 固定结构契约 fixtures，并明确共享的是组织模式而非 KB 专属词汇；后续共用基础 Schema 需另行 change。
- **[Evidence chain 使结果显著增大]** → 复用 typed refs、聚合 occurrence、限制上下文和 related locations，并以 digest 引用完整 facts/evidence bundle。
- **[把 raw facts 移出顶层后降低调试便利]** → 在受约束的 analysis/artifacts 扩展中保留 bundle 摘要和可验证引用，测试工具按引用读取，不在生产结果重复无限数据。
- **[invalid request 时项目身份不完整]** → project 允许显式 unknown/sourceRevision 缺失状态，但仍要求稳定 scan ID、reason codes 和双语 diagnostic；不得伪造项目标识。
- **[定性 confidence 与 KB 数值 confidence 不同]** → 明确词汇差异，保留现有可审计语义；未建立校准 corpus 前不输出伪精度分数。

## Migration Plan

1. 固定 v2 JSON Schema、浮点词汇表、reference rules 和最小正常/partial/失败 contract fixtures。
2. 建立内部模型到 v2 的 projector、引用校验器和 serializer，并让 CLI 正常及异常路径统一调用。
3. 将 rules、diagnostics、suppression、summary、预算和 cache 元数据投影到新结构，删除旧结果构建路径和旧 Schema。
4. 原子迁移 validation corpus/oracle、benchmark、fixtures、文档和全部项目内字段读取，不提供 fallback。
5. 运行单元、contract、完整 corpus、benchmark、Python/C++ 覆盖率、lint/typecheck 和严格 OpenSpec 校验；只有全部门禁通过才视为切换完成。

回滚只能整体回退本变更提交；不保留运行时协议开关或双版本发布路径。

## Open Questions

无。共享骨架、浮点专属词汇、直接破坏性替换和仅工具内修改的边界均已确定。
