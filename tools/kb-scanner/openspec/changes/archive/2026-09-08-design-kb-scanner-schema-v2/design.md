## Context

KB Scanner 的 staged pipeline 已经拥有结构化 Evidence、Entity、Relation、ProofPath、Observation、Classification、Assessment、occurrence 和引用闭包，但 schema 1.0 仍以扁平 Finding 为中心。为了兼容旧后端，新增语义被逐步放入自由形态 `trace`，产生三个问题：消费者无法依赖稳定类型；同一对象在多个 Finding 中重复；“为什么得到这个结论”的顺序链路必须由前端猜测。

schema v2 的主要消费者包括扫描后端、离线 JSON/HTML renderer，以及用户点击 Finding 后查看证明链的前端。它必须支持大项目、部分分析、引用断裂和预算截断，并严格表达“静态分析结论”，不能暗示真实 RISC-V 编译或测试已经发生。

本 change 只冻结设计和可验证合同，不修改运行时默认输出。当前 schema 1.0、`scan-result.json`、`scan-report.html`、`scan.log` 以及两份 compiler-derived x86 事实文件继续保持不变。

## Goals / Non-Goals

**Goals:**

- 定义一个规范化、自包含、可确定性验证的 `schemaVersion: "2.0"` 结果。
- 让每个 Finding 直接内嵌适合详情页展示的完整证据链、代码上下文、主路径、其他分支和 occurrence。
- 一致表达 `complete`、`partial`、`ambiguous`、`inactive`、`unknown`，包括断点、候选和预算信息。
- 消除 `trace` 自由字段和顶层 Catalog 拼装对新消费者的依赖；每个 Finding 只携带与自身有关的有界子图，而不是整张项目图。
- 给 v1/v2 共存、后端迁移、前端接入、默认版本切换和回滚提供明确阶段。
- 为后续实现定义逐模块隔离单元测试、JSON Schema contract 和容器门禁。

**Non-Goals:**

- 本 change 不实现 serializer、CLI 参数、后端 API 或前端图形界面。
- 不移除 schema 1.0，不在本 change 中切换默认输出版本。
- 不修改 Clang/GCC compiler facts、curated knowledge 或 detector/classifier 判定策略。
- 不执行或描述真实编译、链接、测试；不覆盖 OS、内核、系统调用、驱动或板级迁移。
- 不重新实现 RVWMO 分析；需要时只引用 memory-model-ir-checker 的外部结果。

## Decisions

### 1. v2 使用自包含的 Finding 详情合同

顶层采用以下逻辑结构，最终字段名称由本 change 的 JSON Schema 冻结：

```text
scan-result 2.0
├─ scan / project / summary
├─ findings[]
│  ├─ fact
│  │  ├─ kind / symbol / matchedText
│  │  └─ primaryLocation
│  │     ├─ file / span
│  │     └─ context.lines[] / highlights[]
│  ├─ conclusion
│  ├─ occurrences[]
│  └─ evidenceChain
│     ├─ status / reasonCodes
│     ├─ primaryPath[]
│     ├─ steps[]
│     ├─ edges[]
│     └─ breaks[]
└─ diagnostics[]
```

Finding 是详情读取边界：`fact` 表达 scanner 实际找到的静态事实，`conclusion` 表达严重性、actionability 和迁移判断，`occurrences[]` 保存全部命中位置，`evidenceChain` 保存从构建选择、源码/宏证据、knowledge match 到 Classification/Assessment 的完整相关子图。读取单个 Finding 时不需要再查询顶层 Explanation、Catalog 或内部 snapshot。

替代方案是继续扩展 v1 `trace`。它兼容成本低，但无法约束对象类型、代码上下文和链路顺序，因此不适合作为 v2。另一方案是 Finding 只持有 `explanationId`，再通过全局 Catalog 拼装；它能减少重复，却把索引、引用解析和缺失对象处理推给每个消费者，不符合详情页一次取得完整数据的目标，故不采用。底层存储仍可按稳定对象 ID 去重或缓存，但这些优化不改变对外自包含合同。

### 2. evidenceChain 显式提供有序主路径和完整分支

每个 Finding 的 `evidenceChain` 至少包含：

- `status` 与稳定 `reasonCodes`；
- `rootStepId`；
- `primaryPath[]`，按“构建/配置选择 → 源码或构建 Evidence → knowledge match → Classification → Assessment impact”的语义顺序列出 step ID；
- `steps[]`，包含该 Finding 的全部事实、proof、knowledge、classification 和 assessment step；
- `edges[]`，表达主路径及宏候选、替代实现、歧义等分支关系；
- `breaks[]`，描述缺失输入、歧义候选、冲突、循环或预算截断；
- `impactStepIds`，说明它影响了哪些 classification、assessment 和 readiness dimension。

每个 step 是面向展示的有类型投影，携带稳定 ID、kind、status、reason/provenance 和必要的底层对象 ID。实际分析关系仍由 edge 的 relation/proof provenance 表达，不能为了 UI 伪造因果。前端默认沿 `primaryPath` 渲染，展开时读取同一 `evidenceChain` 中剩余的 step、edge 和 break。

替代方案是让前端从任意 Relation 图自动寻找路径。这会把根因选择、顺序和冲突处理复制到每个消费者，且不同前端可能展示不同结论，因此不采用。

### 3. 每个 Finding 必须自包含且内部引用有效

凡是 Finding 的 fact、occurrence、step、edge、primaryPath 或 impact 声明的内部引用，都必须在同一 Finding 中解析。内部 snapshot 出现悬空或类型冲突时，Projector 不得把无效引用写入 v2；它应保留可验证的 Finding，把 `evidenceChain` 标记为 partial/unknown，并在 `breaks[]` 和结构化 Diagnostic 中记录 expected kind、原始稳定 ID、reason 和 stage。

Finding 内引用统一使用稳定 step/occurrence ID；对底层审计对象的引用使用 `{ "kind": ..., "id": ... }`。JSON Schema 验证形状，专用 referential-integrity validator 验证 primary path、edge 端点、break candidate、primary occurrence 和 impact step 均在当前 Finding 内存在且类型匹配。

### 4. 所有代码型事实和链路步骤必须自带精确上下文

`fact.primaryLocation`、每个 occurrence 以及每个有源码/构建文件依据的 chain step 都必须携带项目相对 `file`、完整 start/end span 和 `context`。`context.lines[]` 逐行保存真实行号与文本，`highlights[]` 保存命中行、起止列并允许跨行；上下文使用有界窗口，不保存整个文件。宏调用、宏定义、replacement、intrinsic、build selector 和 build argument 因而可以分别展示自己的命中位置。

Knowledge、Classification 和 Assessment step 没有源文件时，只携带 producer、事实来源、reason 和 status；Projector 不得复制其他 step 的位置来制造代码上下文。源码不可读取或预算不足时，位置仍保留，context 显式标记 unavailable/partial 和 reason。

### 5. occurrence 在 Finding 内是一等对象，聚合不再丢失位置

每个 source/build/test occurrence 拥有稳定 ID、完整 span、代码上下文、configuration、selection status、Evidence 引用和 completeness，并直接包含在 Finding `occurrences[]` 中；Finding 另有 `primaryOccurrenceId`。summary 按 Finding 计数，不按 occurrence 计数。这样 4 个 build Finding 可以无损还原 24 个 Makefile flag 位置。

### 6. 结构化 Diagnostic 替代字符串编码

v2 Diagnostic 使用稳定的 `code`、`stage`、`severity`、`status`、`reasonCodes`、`count`、代表位置和 typed refs。相同诊断仍可聚合，但不再把 JSON details 编码进字符串。renderer 负责本地化文案；合同保存机器可读事实。

### 7. 每条 Finding 链路只携带实际引用的知识投影

Knowledge step 只序列化当前 Finding 实际引用的 KnowledgeEntry identity、category、symbol、producer、source digest 和 provenance，不复制完整 Clang/GCC 数据集。多个 Finding 可重复携带相同的紧凑 knowledge projection，以换取详情对象自包含；底层后端可按稳定 ID 缓存。现有 `clang-x86-entries.json`、`gcc-x86-entries.json` 继续由 Knowledge Provider 加载，字节和分类不变；v2 仅改变报告投影。

### 8. 完整性和静态范围是强制合同

顶层 `scan.scope` 必须明确 `staticAnalysisOnly: true`、`compiled: false`、`linked: false`、`testsExecuted: false`。Finding、evidenceChain、step、proof 和 conclusion 均使用共享的完成状态词汇；未知输入不得通过空数组、零计数或缺失字段表达为“没有问题”。

### 9. 确定性、预算和扩展方式

所有数组采用定义过的稳定排序，ID 只由规范化项目相对路径、语义身份、producer/version 和内容事实构成；不得包含绝对 checkout 根、时间、随机值或遍历顺序。每个 evidenceChain 必须记录 visited/path/depth、代码上下文行数预算及 truncated reason。

核心对象默认封闭字段；未来扩展进入可选、命名空间化的 `extensions`，不得再次引入无约束 `trace`。相同输入和版本必须产生字节一致 JSON。

### 10. v1/v2 以显式版本选择共存，不双写主结果

迁移期默认仍为 v1。后续实现提供显式输出版本选择，同一次 scan 只把所选版本写入固定名称 `scan-result.json`；HTML/log 与所选 JSON 一致。请求 v2 失败时不得静默回退 v1，避免消费者误读。v1 Projector 保留至单独的弃用 change，v2 不承诺保留 v1 Finding 字段或字符串 diagnostics。

替代方案是同时生成 `scan-result-v1.json` 和 `scan-result-v2.json`。这会造成后端选择不一致、artifact 生命周期和退出码含义模糊，因此不采用。

### 11. 本设计 change 的验证资产和未来模块测试

本 change 的 apply 阶段只新增：JSON Schema 2020-12 草案、完整/partial/ambiguous/inactive/unknown 示例、带逐行代码上下文的 AVX Finding 示例、v1/v2 合同差异与消费者迁移清单、Finding 摘要/详情消费示例和 schema/referential-integrity 验证测试，不接线生产运行时。

未来实现 change 至少需要为 version selector、v2 Finding mapper、evidence-chain builder、source-context projector、referential-integrity validator、serializer、summary reducer 和各 renderer 建立独立 unit suite。第三方 schema validator、文件写入和后端边界使用 fake/temporary boundary；每个业务模块在唯一 `kb-scanner-test` 容器中达到至少 90% line / 80% branch，component/E2E 不替代单元覆盖。

## Risks / Trade-offs

- [v2 artifact 因 Finding 自包含而变大] → 每个 Finding 只嵌入自身相关子图，代码上下文使用有界窗口，列表接口只返回摘要，详情接口按 Finding 返回；底层可按稳定 ID 压缩或缓存重复 step。
- [evidenceChain 与底层 proof 漂移] → validator 必须确认 primaryPath、edge、step provenance、root step 与 conclusion 引用一致。
- [部分结果难以展示] → 将断点建模为一等 `breaks[]`，前端显示“链路在此中断”而不是隐藏节点或猜测结论。
- [v1/v2 消费者长期并存] → 明确版本选择、同次扫描单版本输出、独立 contract suites，并把默认切换和 v1 移除拆成后续 change。
- [同一证据在多个 Finding 中重复] → 接受报告层重复以换取自包含详情；使用紧凑 step projection 和后端缓存控制成本，不向消费者暴露全局拼装义务。
- [设计过早绑定 UI] → schema 只定义语义顺序、角色、引用和状态，不定义颜色、布局或具体图形库。

## Migration Plan

1. 本 change 冻结 v2 JSON Schema、示例、引用规则、v1/v2 合同差异与消费者迁移清单和 consumer 查询，不改变运行时。
2. 后续 change 直接从 staged pipeline snapshots 实现独立 v2 projector/validator/serializer 和显式版本选择；v2 不读取、不转换 v1 结果。默认继续 v1，并在独立容器运行双合同测试。
3. 后端增加 v2 解析、Finding 摘要列表和单 Finding 完整详情能力；详情响应直接返回自包含 Finding，不要求二次读取 Catalog。
4. 前端先沿 `evidenceChain.primaryPath` 展示带代码上下文的主链，再展开其他 step、edge、occurrence 和 break；所有 partial/ambiguous 状态必须可见。
5. 使用 AVX 人工基线和现有真实 x86-only fixture 验证字段与链路，不以 Finding 总数代替引用正确性。
6. 后端与前端完成迁移后，由独立 change 决定是否将默认切到 v2；回滚只需恢复显式 v1 选择。
7. v1 停止支持必须另开 change，包含消费者清单、弃用窗口和恢复方案。

## Open Questions

- 代码上下文默认保留命中行前后各几行，以及单个 Finding 的上下文字符/行数上限，需要在 JSON Schema 冻结前通过 AVX 和大型 fixture 确定。
- `extensions` 的命名空间采用反向域名还是项目内 capability ID，需要在 JSON Schema 冻结前确定。
- v2 默认版本切换的验收方和弃用周期由后续集成 change 决定，不在本设计 change 中预设日期。
