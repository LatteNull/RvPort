# 结果协议与源码上下文

[English](MEMORY_ORDER_FINDING_SCHEMA.md) | 简体中文

<a id="doc-memory-order-finding-schema"></a>

`MemoryOrderFindingProjection` 为后端/前端提供自包含展示对象。它借鉴 KB Scanner scan-result v2 的 `fact + conclusion + occurrences + evidenceChain` 消费形状，使通用列表、详情、证据图和代码上下文组件可以复用；但本项目使用独立 schema、`org.rvport.memory-order-analyzer.*` provenance 和内存序枚举，不引用 KB Scanner 包，也不包含 RISC-V、archReachability、knowledge-match 或迁移语义。

## 三类集合

统一报告将相同投影结构放入互斥集合：

- `findings[]`：`conclusion.verdict=risk`，只来自 P4/A6 在证据闭合时采用的正式风险；
- `source_candidates[]`：`verdict=source-candidate/inconclusive`、`status=unknown/partial`，用于源码候选或证据不足的评估，必须有非空 break；
- `discharged_assessments[]`：`verdict=discharged-within-bounded-model`，只说明受限模式内消解，不代表安全。

证据层缺失时，上游 risk/discharge 产生 projection frontier，并作为 `inconclusive` 待核实项保留；不能继续作为正式风险或受限消解发布。

## 顶层结构

每项包含：

- `id`、`schemaVersion=3.0`、`scopeId`、`semanticDigest`；
- `fact`：实际观察、双语描述、typed provenance；
- `conclusion`：verdict/status/severity/confidence/evidenceLevel，以及 `title/title_en`、`reason/reason_en`、`detail/detail_en`、`suggestion/suggestion_en`；
- `occurrences[]` 与存在于数组中的 `primaryOccurrenceId`；
- `evidenceChain`：`rootStepId`、连通 `primaryPath`、完整 `steps/edges`、一等 `breaks`、`impactStepIds` 和预算。

semanticDigest 覆盖完整投影内容，任何字段变更后均须重新计算；源码路径须为项目内相对路径。每个 provenance 固定 `kind/id/producer/schemaVersion/digest`；producer 必须位于本工具命名空间。引用不存在的 step、occurrence 或 artifact 会被 schema/semantic validator 拒绝。

## 证据节点、边与断点

节点覆盖 `thread-creation`、`callback-binding`、`execution-root`、`call-path`、`thread-instance`、`mhp`、`memory-access`、`object-provenance`、`byte-range-overlap`、`mutex-region`、`atomic-event`、`reads-from`、`modification-order`、`release-sequence`、`synchronization-proof`、`synchronization-gap`、`source-fact` 和 `conclusion`。

边只表达实际采用关系，例如 callback/root 绑定、reachable、instance-of、may-happen-in-parallel、accesses、overlaps、protected-by、reads-from、precedes-in-mo、extends-release-sequence、synchronizes-with、supports 或 `supports-candidate`。P2 order、P3 RF candidate、R2 candidate、源码词法邻近或 MemorySSA 不能单独升级为 SW/HB。

`primaryPath` 必须从 `rootStepId` 沿真实边连到结论；相关分支仍保存在 steps/edges。complete 链不得包含已知 break；partial/unknown/ambiguous/source-candidate 必须至少包含一个 break。预算截断本身是 break，不得用截断后的空图声称完整。

## 源码位置和代码窗口

源码型 fact、occurrence 和 step 使用：

- 项目相对 POSIX path，拒绝绝对路径、`..`、反斜杠和 symlink/解析后越界；
- 一基、end-exclusive span 与精确 highlights；
- `sourceSha256` 和 snapshot artifact reference；
- `context.lines[]` 中的真实行号和原始文本。

默认窗口为命中前后各 20 行，每位置最多 256 行和 65536 字符，优先保留命中。投影只读与 fact digest 匹配的分析时 snapshot；当前工作区文件即使同名也不回退读取。无 debug、IR-only、SourceIRBinding 缺失、digest mismatch、无效 span、读取失败或截断分别输出 `partial/unavailable` 和 break，不伪造源码、行列或高亮。完整 snapshot 按 SHA-256 去重，后端可据 artifact index 提供扩大上下文接口。

## 前端消费示例

```json
{
  "id": "org.rvport.memory-order-analyzer.finding:...",
  "conclusion": {
    "verdict": "source-candidate",
    "status": "unknown",
    "title": "源码级内存序候选",
    "title_en": "Source-level memory-order candidate"
  },
  "primaryOccurrenceId": "occurrence:...",
  "evidenceChain": {
    "rootStepId": "step:...",
    "primaryPath": ["step:...", "step:..."],
    "steps": [],
    "edges": [],
    "breaks": [{"reasonCode": "missing-ir-binding"}],
    "impactStepIds": [],
    "budget": {"truncated": false}
  }
}
```

前端必须按 verdict/status/breaks 展示受限边界；不得把颜色、exit 0 或零 Finding 映射为“线程安全”。完整机器合同见 `schemas/memory_order_finding.json`，项目聚合合同见 `schemas/unified_project_analysis.json`。

<a id="doc-finding-source-context"></a>

## 源码引用解析

本说明对应统一入口的内存序 Finding 投影，不改变内存序规则或正式证明结论。

## 引用解析

- 源码候选只解析自身 `physical_tu_ids` 与 `node_ids/relation_ids` 引用的事实。
- publication / discharged 只解析评估 `evidence` 指定的 `artifact_key + id` 事件。
- advanced-atomic 沿 `p4_protocol_id` 查找当前 Scope 的 publication graph，再定位对应事件。
  不存在该引用链时明确保留无位置，不扫描无关图来猜测。
- AST 优先展示 expansion，同时保留 spelling；IR 使用调试信息的 inline chain。
- 绝对路径按 manifest 声明源码根转换为相对路径，根外位置拒绝。缺文件名不推断为主 TU；
  同名文件不能按路径后缀匹配。跨文件结束点不组成跨文件范围，退为起点的单字符范围。
- 后端在编译 profile 的 `path_map` 中显式声明本地和远端源码根到 `.` 的映射。
  工具校验主源码摘要后使用唯一的本地根建立快照，恢复项目原始相对路径；有多个根时不猜测。
  Clang 返回起止相同的宏参数单点时保留为单字符高亮，倒置范围仍拒绝。

## 快照和显示

开始分析前保留主源码及项目内 `.h/.hpp/.hh/.hxx/.inc/.inl` 快照。头文件单文件上限
8 MiB，累计 64 MiB，拒绝逃逸符号链接；超限通过快照失败与不可用上下文体现。
扩展名以外或无匹配快照的文件不伪造片段。快照按内容 SHA-256 校验。

每个位置的 `context` 使用请求的 `context_lines/context_characters` 预算，并返回真实行号、
文本、高亮和完整性状态。`span.end` 为 exclusive，下一行第 1 列不高亮下一行。
多位置按 expansion 优先、相对路径、行列和 TU 稳定排序、去重，主位置与 occurrences 保持关联。
关联源码访问步骤分别保存各自位置；其他分析层没有直接源码证据时保留空 source。

位置缺失不能改变风险判断：正式风险/受限消解保留 verdict，证据链标记源码缺口；
AST-only 结果仍为候选。不可用说明提供中英文。JSON schema 不增加必填字段。
Finding 身份的原有语义种子不变，修正位置会改变 occurrence/step 身份。
统一入口缓存加入 `source_projection_revision=2`，避免复用旧的无片段报告。

## 回归

Linux 下独立单测：`PYTHONPATH=python python3 -m pytest -q tests/unit`。
真实 Clang 用例：`PYTHONPATH=python MOA_WORKER=/output/build/moa-worker python3 -m pytest -q tests/integration/test_finding_source_context.py`。
后者要求同目录存在 `memory-order-source-worker`。它验证真实 Clang 绝对头文件路径到快照的映射，
不代替独立单元测试或后端正式 API 验收。

## 3.0 与历史 2.0 的兼容

这里的版本号表示结果数据协议，不是软件或 C/C++ 标准版本。3.0 新输出的 `conclusion.evidenceLevel` 按 verdict 区分 `source-only`、`incomplete`、`bounded-model`；`confidence=null` 表示未评估，不可转换为零概率或固定 0.5。源码候选和 inconclusive 为 info、非阻断、unknown/partial，必须展示为待核实，而非低风险或安全。

验证器仍读取 2.0；2.0 要求数值 confidence，不允许 evidenceLevel。后端按 kind/verdict 对历史候选只读派生展示字段，原始 detail、JSON/HTML 和用户选择不改写。未知版本与顶层/逐项版本冲突显式拒绝。人工纳入只改变报告输入选择，不能升级分析结论。

steps 数组按稳定 ID 存储，显示顺序使用 primaryPath；edges 保存其他分支，breaks 保存缺口。不能把数组排序解释为证明顺序。
