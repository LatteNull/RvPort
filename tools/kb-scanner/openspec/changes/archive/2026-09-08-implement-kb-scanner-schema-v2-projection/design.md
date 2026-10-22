## Context

当前 staged pipeline 已经产生稳定的 Workspace、Knowledge、Frontend、Normalized、Analysis、Detection、Classification 和 Assessment snapshots，并由 `CompatibleReportProjector` 投影为 schema 1.0。Schema v2 的 JSON Schema 2020-12、词汇表、Finding 内引用规则、状态样例和 AVX explanation 示例已经在前一 design change 中冻结，但尚无生产运行时能够从这些 snapshots 直接生成 v2。

本 change 位于 scanner 投影边界，不改变证据采集、知识加载、检测、分类或评估语义。Scanner 默认进入新的 v2 Projector；依赖旧合同的调用方可显式选择 `1.0` 进入原有 v1 Projector。所有实现与验证只在 `kb-scanner-test` 容器中执行，不向本机或生产 Compose 安装依赖。

## Goals / Non-Goals

**Goals:**

- 从 staged snapshots 直接生成符合已冻结合同的 schema 2.0，绝不以 v1 JSON、v1 Finding 或自由形态 `trace` 为中间表示。
- 让每个 Finding 自包含 fact、conclusion、全部 occurrence、可直接展示的主证据链、其他分支、断点、代码上下文、knowledge provenance 和 assessment impact。
- 提供默认 v2、显式 v1 兼容、单次扫描单版本输出、固定 artifact 名称、v2 失败不回退和原子发布。
- 使 v2 JSON、HTML 和 log 来源于同一个 v2 report model，并保持确定性和相互一致。
- 通过模块级隔离单元测试、JSON Schema/引用合同、AVX 字段级 oracle、v1 字节/字段回归和无副作用测试建立实现门禁。

**Non-Goals:**

- 不删除或弃用 v1，不修改后端/前端消费者；这些消费者的 v2 接入属于后续 change。
- 不修改 schema v2 的核心语义；实现发现矛盾时只允许提交最小、向后兼容的合同勘误及对应测试。
- 不修改 Clang/GCC compiler facts、curated knowledge、detector/classifier/assessor policy，也不恢复 Legacy/YAML 运行路径。
- 不执行真实编译、链接或测试；不处理 OS、内核、系统调用、驱动、开发板迁移，也不实现 RVWMO 分析。

## Decisions

### 1. 版本选择进入 ScanRequest/ScanContext，但两个 Projector 保持独立

CLI 增加 `--schema-version {1.0,2.0}`，默认值为 `2.0`；该值经 `ScanRequest` 和 `ScanContext` 传递到投影边界。默认 profile 使用一个薄的 `VersionedReportProjector`，它只校验版本并把同一组 snapshots 原样委托给现有 `CompatibleReportProjector` 或新的 `SchemaV2ReportProjector`。

选择器不得持有字段映射或进行 v1/v2 数据转换。未指定版本与显式 `2.0` 必须走同一个 v2 Projector；显式 `1.0` 必须走现有 v1 Projector，作为旧消费者的兼容与回滚路径。

替代方案是在 CLI 中创建两套完整 pipeline profile。这样会复制装配逻辑，并可能令分析阶段因版本不同而漂移，因此不采用。另一方案是先生成 v1 再转 v2；它会永久丢失 typed references、结构化 Diagnostic 和完整链路，明确禁止。

### 2. v2 使用独立、封闭的 report model

在 `kb_scanner/projection/v2/` 中建立只面向输出合同的不可变 view model，覆盖 result、scan scope、project、summary、finding、fact、conclusion、occurrence、source context、evidence chain、step、edge、break、typed provenance 和 Diagnostic。构造器负责枚举值、必填字段和封闭对象形状；跨对象引用由独立 validator 负责。

内部 snapshots 保持 scanner 的事实来源，v2 model 只是投影结果，不反向写入或修改任何 snapshot。Knowledge step 只复制当前 Finding 实际引用的紧凑 identity/category/symbol/producer/source digest/provenance，不复制完整事实集；现有 Clang/GCC 文件及其哈希保持不变。

替代方案是直接拼装任意字典。它容易再次形成无约束 `trace` 并把字段错误推迟到序列化阶段，因此不采用。

### 3. Finding mapper 以 Classification 的语义根因为聚合边界

`V2FindingMapper` 以发布 Classification 及其根 Observation 为起点，使用稳定 semantic root、rule/detector identity、conclusion 状态和 configuration 形成 Finding identity。与同一语义根因有关的 Evidence location 聚合为 `occurrences[]`，但不同 conclusion、selection status 或非等价 configuration 不得被错误合并。

`primaryOccurrenceId` 使用确定性 policy 选择；summary 始终按 Finding 计数，occurrence 只反映底层位置数。Fact 只表达扫描到的内容，severity、blocking、actionability、reason 和 suggestion 只进入 conclusion，避免事实与判断混写。

### 4. evidence-chain builder 构造每个 Finding 的有界闭包和语义主路径

`EvidenceChainBuilder` 预先为 Entity、Evidence、KnowledgeEntry、Relation、ProofPath、Observation、Classification 和 Assessment 建立只读 ID 索引，然后从 Finding 根引用执行有预算的闭包展开。它只投影实际相关对象，并将底层对象映射为已冻结的 step/edge kind。

主路径不是前端图搜索结果，而是按已验证 proof 和语义阶段确定：architecture/build selector → target/source selection → source/build evidence → macro/call terminal → knowledge match → classification → assessment。存在多条等价完整路径时按规范化 ID 和路径元组稳定选择；非等价候选全部保留在 steps/edges，并产生 `ambiguous` break。缺失引用、类型冲突、循环和预算截断产生结构化 break，绝不通过删除链路伪装为 complete。

`inactive` 只在完整 proof 表明 x86 路径被目标配置排除时使用；`partial`、`ambiguous`、`unknown` 必须至少有一个 break。没有证据不能推断 RISC-V ready。

### 5. source-context projector 只读项目根内文件并使用固定预算

`SourceContextProjector` 接受项目相对 SourceSpan，解析后的绝对路径必须仍位于 `ScanContext.input_root` 内。它按文件缓存只读文本，使用冻结的默认窗口：命中前后各 2 行、单 location 最多 16 行和 4096 字符，并生成一基、end-exclusive highlights。

代码型 fact、occurrence 和 step 分别使用自身 Evidence 的 span，禁止复制其他 step 的位置。路径越界、文件消失、解码失败或预算不足时保留 span，并返回 `partial`/`unavailable` context 和稳定 reason；不得删除 Finding。测试使用临时目录和 fake reader 覆盖文件边界，生产代码不执行项目命令。

### 6. 结构化 Diagnostic 和 summary 由 v2 model 独立归约

`V2DiagnosticProjector` 将 pipeline Diagnostic 映射为 code、stage、severity、status、reasonCodes、count、代表位置和 typed refs。只有聚合键完全相同的记录可以合并，并保留全部稳定引用与最严重状态；人类文案不再承载机器 JSON details。

`V2SummaryReducer` 从最终 v2 Findings、Assessment 和完整性状态归约计数与 readiness，不读取 v1 summary，也不从零命中推断 ready。顶层 scope 固定声明 `staticAnalysisOnly=true`、`compiled=false`、`linked=false`、`testsExecuted=false`。

### 7. 运行时验证分为封闭模型验证和引用完整性验证

`V2ReferentialIntegrityValidator` 在序列化前检查 Finding/occurrence/step ID 唯一性、primary occurrence、root step、primaryPath、edge 端点、impact step、break candidate、code/non-code source 约束、complete/incomplete 状态和稳定排序。发现无效引用时 Projector 失败，不发布 artifact，也不回退 v1。

JSON Schema 2020-12 的完整形状验证继续在容器 contract suite 中使用现有 `jsonschema` 测试依赖；运行时不为此新增依赖，封闭 model 与专用引用 validator 保证生产路径。这样保持 runtime.lock 不变，同时仍由机器合同阻止实现漂移。

### 8. JSON、HTML 和 log 从同一个 v2 report model 渲染

v2 JSON serializer 使用固定 UTF-8、字段别名、排序和换行策略；相同 scanner/knowledge 版本、ScanContext 和输入必须产生字节一致 JSON。HTML renderer 从同一 model 展示 summary、Finding 主位置、conclusion、primaryPath、occurrence、break 和结构化 Diagnostic；log renderer 输出确定性的人类摘要和 reason code，不重新计算分类。

renderer 不定义前端产品布局，只验证 v2 自包含 Finding 已足以支撑后续详情页。`extensions` 只接受已冻结的命名空间，不允许恢复自由字典字段。

### 9. 三个 artifact 使用共享的窄原子发布边界

从现有 v1 Projector 抽取或复用一个只负责 staging、replace、rollback 和 ArtifactRef digest 的 `AtomicArtifactPublisher`；v1/v2 mapper 和 renderer 保持独立。Projector 先完成 report model、引用验证和所有请求格式渲染，之后一次性发布固定名称 artifact。任一渲染、验证或 replace 失败时恢复旧 artifact，并返回 failed Diagnostic 与非零退出结果。

共享发布器不得改变 v1 内容、默认格式判断或 artifact 名称。文件系统 replace 使用可注入边界，单元测试通过 fake/temporary directory 模拟中途失败和回滚。

### 10. 每个业务模块都有独立单元测试映射

| 业务模块 | 隔离单元测试 | fake/mock 边界 |
|---|---|---|
| result version value/selector | `tests/unit/schema_v2_projection/test_version_selector.py` | fake v1/v2 projector |
| v2 report model 与 Finding mapper | `test_models.py`、`test_finding_mapper.py` | 合成 snapshots |
| evidence-chain builder | `test_evidence_chain_builder.py` | 合成 graph/proof 索引 |
| source-context projector | `test_source_context.py` | fake reader、临时项目根 |
| Diagnostic projector | `test_diagnostics.py` | 合成 Diagnostic |
| summary reducer | `test_summary.py` | 合成 Finding/Assessment |
| reference validator | `test_reference_validator.py` | 正反例内存 model |
| serializer 与 renderers | `test_serializer.py`、`test_renderers.py` | 固定 clock 禁用、内存 model |
| atomic publisher 与 v2 Projector | `test_projector.py` | fake replace、临时输出目录 |
| CLI/request adapter | `test_cli_schema_version.py` | fake application/projector |

上述模块分别进入机器可读 test inventory，并在独立容器达到每模块至少 90% line、80% branch；component、contract、AVX 或全量回归不能替代这些隔离单元测试。

## Risks / Trade-offs

- [Finding 自包含导致 JSON 体积增长] → 每个 Finding 只投影相关闭包，Knowledge 使用紧凑投影，source context 和链路遍历均有固定预算；不引入顶层 Catalog 依赖。
- [主路径选择与底层 ProofPath 漂移] → primaryPath 只能由实际 proof/relation provenance 构成，validator 检查相邻节点连通、状态和底层引用，AVX oracle 检查字段而非只检查数量。
- [抽取原子发布器导致 v1 回归] → 保持 v1 mapper/renderer 不变，建立显式 v1 字节与 artifact 回归，并通过故障注入覆盖发布回滚。
- [源码上下文读取带来路径穿越或不稳定] → 只接受规范化项目相对路径、解析后校验 root containment、缓存一次读取，并把不可用内容显式降级而非访问根外文件。
- [v2 合同与实际 snapshot 表达能力存在缝隙] → 不伪造 step；缺口通过 break/Diagnostic 暴露。只有合同自身矛盾才作最小勘误，且必须附迁移说明和正反例。
- [默认切换为 v2 会改变未指定版本调用的结果合同] → 在 CLI help、README 和迁移清单中明确标记 breaking default；保留显式 `1.0` 选择和完整 v1 contract suite，消费者接入在后续 change 中完成。
- [两种版本长期共存增加维护成本] → 共用分析 pipeline 和窄发布边界，投影/合同完全隔离；v1 停用必须由后续独立 change 决定。

## Migration Plan

1. 建立 v2 model、稳定 ID/排序 helper、source context 和引用 validator，并让现有 schema/examples 作为可执行合同。
2. 实现 Finding mapper、evidence-chain builder、Diagnostic projector 和 summary reducer，使用合成 snapshots 完成模块级门禁。
3. 实现 v2 JSON/HTML/log renderers 与 `SchemaV2ReportProjector`，完成验证后原子发布。
4. 增加 `--schema-version` 及 request/context 字段，装配薄版本选择器；默认和显式 v2 进入新 v2 Projector，只有显式 `1.0` 进入现有 v1 Projector。
5. 在 `kb-scanner-test` 容器运行模块覆盖、全部 schema v2 正反例、真实 AVX 字段级对照、v1 consumer contract、故障回滚和完整回归。
6. 发布后 Scanner 默认输出 v2；需要旧合同或回滚时显式选择 `1.0`，无需修改知识、Evidence Graph 或事实数据。后端接入和前端详情由后续独立 change 完成。

## Open Questions

- 无。本 change 沿用已冻结的上下文预算、extension namespace 和单次扫描单版本输出，并采用 v2 默认、v1 显式兼容决策；消费者适配留给后续 backend/frontend change。
