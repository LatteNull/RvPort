## Context

当前公共 CLI 直接暴露外部 BC 导入、源码证据、ExecutionRoot、ThreadEntry、按需函数分析、效果摘要、线程/同步、C++ 生命周期、RAII、对象 provenance、并发访问候选、P4 和 A6 等独立命令。`model-threads` 与 `detect-publication-risks` 只编排了部分历史链路，`validate-analysis` 面向固定真值集而非生产调用，因此后端若直接集成，必须理解内部协议、依赖顺序、缓存、降级和失败传播。

生产输入已经改为外部 `ExternalBitcodeBundleManifest`。manifest 以 planned artifact/TU 为输入分母，并按 `target_id` 声明 Scope；单个 BC 是 TU 输入原子，Scope 才是跨 TU 正式分析边界。一个后端 Project/Build Artifact Set 可以包含多个不同 target、ABI、profile 或配置的 Scope，不能把全部 BC 无条件合并成一个程序。

A2 已将 AST 保存为独立事实层，并定义 `ast-ir`、`ir-only`、`ast-only`、`failed`。但当前没有生产级统一入口根据外部 bundle 和每个 TU 的阶段结果自动选择模式，也没有把 P1–A6/R1–R3 的产物投影成前端可直接消费的自包含证据链。

KB Scanner v2 已验证一种合适的外部展示模式：每个 Finding 自包含 `fact`、`conclusion`、`occurrences` 和 `evidenceChain`，证据链具有确定性主路径、完整图、断点和有界源码上下文。本 change 复用这种结构思想和字段形状，但不依赖 sibling tool 的 Python 包或 schema，也不复用其 RISC-V 迁移枚举。

调用者包括后端任务运行器、前端 Finding 列表/详情/代码上下文，以及离线审计和测试工具。实现范围限定 GCC/Clang 用户态 C11、C17、C++17、C++20；Windows、MSVC 和 clang-cl 排除。

## Goals / Non-Goals

**Goals:**

- 提供单一、版本化的 `analyze-project` 入口，使调用者只提交外部 bundle、Scope 选择、可选源码输入、分析策略和预算。
- 将既有分析能力组织为分析器内部的版本化依赖 DAG；按 Scope 隔离执行并输出一个项目级聚合结果。
- 对每个计划 TU 自动记录 AST/IR 可用性，BC 或 IR 阶段失败时保留可信 AST-only 证据，并按候选依赖切片传播完整性。
- 保持 P1–P4、A1–A6、R1、R1.1、R2、R3 的协议、缓存身份和风险语义不变，通过只读适配器生成内部请求和消费产物。
- 输出面向后端/前端的自包含内存序 Finding 投影，包含完整证据图、默认展示路径、断点、来源引用和分析时源码代码窗口。
- 支持确定性缓存、完整阶段恢复、deadline、协作式取消、预算、失败隔离、原子发布和审计 artifact 索引。
- 为全部新增或修改的自有代码提供单元测试，并使项目整体、实现语言和每个受影响模块的行/分支覆盖率至少 90%。

**Non-Goals:**

- 不增加新的内存模型、通用 data-race、通用 happens-before、通用 points-to、线程池或自定义同步规则。
- 不修改既有 ModuleFacts v2、EffectSummary v1、ThreadContextGraph v1、P4、A1–A6 或 R1–R3 产物。
- 不把零 Finding、完整执行或 bounded discharge 表述为全程序安全。
- 不执行 GCC/Clang driver、BC emission、linker、CMake configure/build、网络、SSH 或目标程序；AST 提取只允许调用锁定版本的分析器自有 source worker。
- 不在本 change 中修改后端数据库、API 或前端页面；仅冻结可供后续集成使用的外部契约和 fixture。
- 不直接 `$ref` sibling `tools/kb-scanner` 的 schema，不建立运行时或发布依赖。

## Decisions

### 1. 外部只有一个公共入口，内部保留既有高级命令

新增：

```text
python -m memory_order_analyzer analyze-project \
  --request <UnifiedMemoryOrderAnalysisRequest.json> \
  --artifact-store <store> \
  --output <fresh-output> \
  --llvm-worker <worker> \
  --source-worker <worker>
```

请求引用一个外部 bundle manifest，选择 `all` 或显式 `scope_ids`，声明 source assistance 策略、显式程序/框架入口、分析 policy、预算、cache/resume 和 deadline。后端不得提交 P2/P3/P4 等阶段开关或内部请求路径。

既有命令继续作为开发、诊断和协议兼容入口；统一入口不会删除或改变它们。选择增加 facade 而不是把所有旧命令合并，是为了保持既有协议可独立验证并降低迁移风险。

### 2. 项目运行是聚合单元，Scope 是语义单元

协调器先校验 bundle 的 planned 分母和 Scope 声明，再为每个选中 Scope 创建独立 `ScopeAnalysisExecutionRecord`。不同 target triple、DataLayout、ABI、语言/profile 或 Scope 不共享语义结论；相同内容可以通过内容寻址缓存复用，但复用不会合并身份。

项目状态由所有选中 Scope 聚合：一个 Scope 失败不会丢弃其他 Scope 的有效结果；只有全部相关 Scope 和候选依赖闭合时，项目才可为 `complete`。跨 Scope 关系只有在 manifest 显式声明且既有协议可以验证时才允许生成，否则进入 frontier。

选择按 Scope fan-out 而不是全局 BC 笛卡尔积，可以保持目标配置身份、控制候选配对规模，并避免把不同构建配置误认为同一运行程序。

### 3. 使用声明式版本化 DAG，而不是硬编码脚本

新增内部 `AnalysisCoordinator`、`AnalysisPlanBuilder`、stage registry 和 artifact resolver。registry 为每个节点登记：stage/version、输入/输出 kind、前置依赖、适用条件、预算、缓存策略、失败分类和降级规则。`UnifiedAnalysisPlan` 是可审计产物，包含实际展开后的 Scope 节点和依赖边，但不是要求后端理解的输入。

计划按以下逻辑波次执行：

```text
bundle preflight / content-addressed ingest
  ├─ AST source facts（按 TU 独立）
  └─ LLVM module/lightweight indexes
          ↓
ExecutionRoot + ThreadEntry bootstrap
          ↓
R3 demand worklist 与确定 direct-call/callback 扩展
          ↓
P2 effects + P3/A3 lifecycle + A4 synchronization + A5 provenance
          ↓
R2 concurrent-access candidates
          ↓
P4 publication + A6 fence/RMW overlay
          ↓
Finding projection + Scope/project aggregation
```

既有实现间的递归、root 扩展或 demand 扩展由有界单调 worklist 节点解决，不在 DAG 中制造运行时循环。条件不适用的节点记录 `skipped-not-applicable`；证据不足的节点记录 `partial/unknown`，不得静默跳过。

选择 DAG 而不是线性 shell orchestration，是为了使依赖、恢复、失败切片和预算可验证，并允许后续增加分析策略而不改变后端接口。

### 4. AST 是并行事实层，AST-only 是自动降级而非补跑

协调器先从 manifest 的 planned TU、source lineage 和可选 compilation profile 生成 source work item；AST source worker 与 BC 是否成功相互独立。每个 TU 最终模式为：

- `ast-ir`：可信 AST 与相容 IR/P1 都可用；
- `ir-only`：AST 不可信或不可用，但 IR 可用；
- `ast-only`：AST 可信，但 BC 缺失、校验失败或相关 IR 阶段失败；
- `failed`：AST 与 IR 均不可用或不可信。

AST-only 只投影 source-only candidate、源码实体、控制和同步缺口；缺少的 IR binding、运行时对象、byte range、ThreadInstance、RF/MO/SW/HB 必须进入 evidence break。候选依赖切片证明失败 TU 无关时，其他候选可以继续正式分析。

`source_assistance=auto` 为默认；`required` 在任一相关 TU 缺失可信 AST 时使其切片 partial/failed；`disabled` 不执行 source worker并明确形成 IR-only。禁止在 BC 失败后调用编译器补产 BC。

### 5. 外部报告和内部事实分层

内部产物继续是分析真相和缓存边界；统一报告只是稳定外部投影。输出目录原子发布以下内容：

```text
request.json
plan.json
report.json
scopes/<scope-id>/execution.json
findings/<finding-id>.json
candidates/<candidate-id>.json
discharged/<assessment-id>.json
source-snapshots/<sha256>/...
artifacts.json
stages/<scope-id>/<stage-id>/...
```

`report.json` 包含项目摘要、Scope/TU 状态、正式 Findings、source-only candidates、bounded discharged assessments、diagnostics、frontier、abstention 和 artifact 索引。三类项目都使用同一个 `MemoryOrderFindingProjection` 结构，但存放在不同数组并使用不同 `verdict`，避免把 unknown candidate 或受限消解混成风险 Finding。

选择投影而不是改造每个既有协议，可以保持缓存与语义兼容，也能让前端只依赖一个稳定合同。

### 6. Finding 结构兼容 KB Scanner v2 的消费模式，但拥有独立 schema

每个投影固定包含：

- `id`：由规则版本、Scope、主事实和规范化证据身份生成，不含绝对路径、时间或调度顺序；
- `fact`：实际观察到的内存序事实及主位置；
- `conclusion`：`risk`、`source-candidate`、`discharged-within-bounded-model` 或 `inconclusive`，含严重性、置信边界、状态、原因和建议；
- `occurrences[]` 与 `primaryOccurrenceId`：全部相关源码/IR 出现位置；
- `evidenceChain`：`rootStepId`、`primaryPath`、`steps`、`edges`、`breaks`、`impactStepIds` 和预算。

内存序 step 至少覆盖 thread creation、callback binding、execution root、call path、thread instance、MHP、memory access、object provenance、byte-range overlap、mutex/RAII region、atomic event、RF、MO、release sequence、synchronization proof/gap 和 conclusion。edge 表达真实采用的绑定、可达、访问、重叠、并行、保护、通信和支持关系。每个节点或边通过带 digest 的 typed provenance 引用内部产物。

主路径是前端默认顺序，必须从 root 连通到结论；`steps/edges` 保存相关分支。`partial`、`ambiguous` 或 `unknown` 的链必须至少含一个 break；`complete` 链不得含已知 break。完整只表示该 Finding 在受限模型内的证据闭合，不表示全程序安全。

不直接复用 KB schema，是因为其 domain、枚举和结论字段服务于 x86→RISC-V 迁移。保持外形兼容，可让后续前端抽取通用 evidence-chain renderer，而不污染任一工具的领域合同。

### 7. 源码上下文绑定分析时快照

所有源码型 fact、occurrence 和 step 使用项目相对 POSIX 路径、一基位置、end-exclusive span、`context.lines[]`、`highlights[]`、`sourceSha256` 和 snapshot artifact reference。默认窗口为命中前后各 20 行；每个位置上限 256 行和 65536 字符。优先保留命中行，再按距离分配上下文。

source worker 产生事实时登记源码 digest；投影阶段只从匹配 digest、位于声明 source boundary 内的文件或已保存快照读取内容。文件变化、路径逃逸、读取失败、行列越界和预算截断分别产生 `partial/unavailable` 与 break，禁止回退读取当前同名文件或伪造列号。

内嵌窗口满足 Finding 详情首屏；完整文件快照按 digest 去重保存，后端后续可基于 artifact 提供扩大 code-context。IR-only 且没有可信 SourceIRBinding 时保留 IR provenance，并将 source context 标记 unavailable，而不是把反汇编当源码。

### 8. 双语、状态与退出码是外部稳定语义

用户可见的 title、reason、suggestion、detail 和诊断必须同时提供中文与英文。内部稳定 ID、枚举和 digest 不依赖翻译文本。

统一入口退出码：

- `0`：所有选中相关切片完成且没有 formal risk；仅表示 `no-finding-within-supported-model`；
- `3`：所有选中相关切片完成且至少存在 formal risk；
- `2`：存在 partial/unknown/ambiguous、AST-only、开放 Scope、预算、取消或可保留结果的阶段失败；即使同时存在 risk 也返回 2；
- `1`：请求无效、bundle 无法建立任何选中 Scope，或没有任何可用证据。

取消与 deadline 采用协作式检查；已原子发布的完整 stage 和缓存可保留，未完成 stage 不作为可复用语义成功。最终报告必须能区分 cancelled、deadline、budget 和 worker failure。

### 9. 缓存和恢复由语义身份控制

项目运行身份由规范化请求语义、bundle digest、选中 Scope、policy、worker/schema 版本和预算组成；后端 task ID、输出路径、时间和调度顺序不进入 semantic digest。stage cache 继续使用既有安全键；协调器只缓存完整且依赖摘要闭合的 stage record 和 Finding projection。

`resume` 只复用同一 semantic request 下已经原子发布且通过 schema、digest 和依赖验证的节点。损坏、版本冲突、依赖变化或 transient failure 必须重算或形成 frontier，不允许把旧的空结果当作完成。

### 10. 后端集成采用报告适配，不把内部阶段公开为 API

后续后端 change 只需：解包或定位 Shared LLVM Bitcode Artifact Set、生成统一请求、运行一次命令、按退出码和报告状态结束任务、保存完整报告/源码快照 artifact，并逐条持久化 Finding 投影。列表读取结论摘要；详情读取完整投影；扩大代码窗口读取 snapshot artifact。

本 change 提供 schema、固定 fixture 和 consumer contract 测试，但不改后端。选择先冻结 producer 合同再接后端，避免后端代码成为分析器内部阶段的事实标准。

### 11. 文档和验收映射

- `README.md`：唯一生产入口、退出码和最小调用示例。
- `doc/UNIFIED_PROJECT_ANALYSIS.md`：Scope 模型、DAG、降级、恢复和后端责任边界。
- `doc/MEMORY_ORDER_FINDING_SCHEMA.md`：Finding/证据链/源码上下文语义和 KB v2 的兼容边界。
- `doc/IMPLEMENTATION_ROADMAP.md`：登记该 change 状态，并保持 B1/B2 与新语义能力未授权边界。
- validation/acceptance 文档：四语言、单/跨 TU、多 Scope、四种证据模式、风险/候选/消解、取消/预算/cache、代码上下文和覆盖率结果。

验收必须从外部 bundle 经统一入口生成最终报告，验证后端无需构造内部阶段请求；同时保留既有命令和 P1–A6/R1–R3 回归的规范化语义不变。

## Risks / Trade-offs

- [统一入口容易演变成另一套语义实现] → 所有语义节点只调用既有生产函数或只读适配器；协调器只负责计划、传输、完整性和投影，并对原始产物 digest 建立引用。
- [不同阶段存在历史输入方向，DAG 难以一次展开] → 将 root/demand 扩展建模为有界单调 worklist，DAG 记录 worklist 节点而非制造循环；超预算形成非空 frontier。
- [项目级状态掩盖单个 Scope 缺口] → 报告同时保留项目、Scope、TU 和候选切片分母；项目 complete 必须由所有相关 Scope 闭合，聚合计数不得覆盖分项。
- [AST-only 被前端误认为正式风险] → source-only candidate 使用独立数组、verdict、颜色/状态和必需 break；schema 禁止 AST-only 使用 formal risk 或 discharge。
- [内嵌代码使报告过大或泄漏路径] → 仅保存有界项目相对上下文，按 digest 去重完整快照，执行路径边界检查、输出预算和绝对路径扫描。
- [源码快照和 AST/IR 事实不一致] → 每个 source location 携带 source digest，投影只接受与事实依赖一致的快照；不一致降级而非读取当前文件。
- [缓存恢复复用部分或过时产物] → 只发布完整 stage，校验 schema/version/digest/dependencies，transient failure 不作为成功缓存。
- [结构兼容被误解为 KB schema 完全兼容] → 使用独立 `$id`、工具名、枚举和版本；合同测试只冻结共享结构，不允许 memory-order producer 引用 sibling 运行时代码。
- [报告 complete 或 exit 0 被误读为安全] → schema、文档、CLI 和 fixture 固定 bounded wording，并测试禁止 `safe`/`thread-safe` 等无边界结论。

## Migration Plan

1. 先添加新协议、schema、样例和纯构造/验证代码，不改变现有 CLI 默认行为。
2. 实现 Scope 计划器、stage registry、执行记录、缓存恢复和取消接口，通过 fake stage 单元测试验证调度语义。
3. 逐步接入外部 bundle、A1/A2、R1/R1.1/R3、P2/P3/A3–A5、R2、P4/A6 适配器，每接一层保持旧协议回归不变。
4. 实现 Finding、证据链和源码快照投影，使用固定内部产物 fixture 验证引用闭包和确定性。
5. 加入 `analyze-project` CLI、完整集成真值、文档与质量门禁；旧命令继续可用。
6. 后续独立 backend change 采用统一合同。若需要回滚，只停止调用新入口并继续使用既有命令；不会迁移或破坏旧产物。

## Open Questions

- 首个后端集成默认分析 artifact set 中全部可分析 Scope，还是由后端显式选择一个主 Scope？本设计同时支持两者，建议 CLI 默认 `all`，后端生产任务显式记录实际选择。
- 后端扩大 code-context 最终复用通用源码 artifact 服务还是新增内存序专用接口？本 change 只保证 snapshot artifact、digest 和位置合同，不决定后端路由。
- 后续是否抽取 KB Scanner 与 memory-order-analyzer 的共享 Finding schema 包？首版保持结构兼容但物理独立，待两个 consumer 稳定后再单独评估，避免跨工具耦合阻塞当前入口。
