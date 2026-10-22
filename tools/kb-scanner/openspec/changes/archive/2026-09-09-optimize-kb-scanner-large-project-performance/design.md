## Context

候选噪声修复已归档，基线提交为 `6c4b02c6c364a99133f1ed909a213a5871a3ffec`。2026-09-09 对 libarchive 的验证分为两个输入，不能混用结论：

| 输入 | 环境与范围 | 结果 |
|---|---|---|
| 报告预览 | 9 个源码文件 | 约 42.47 秒，exit 0，0 findings，readiness provisional |
| 全项目快照 | 默认收集 810 个文件：802 个 C/C++ 输入、8 个构建输入；无 compilation database | 2 CPU / 2 GiB，300.04 秒超时，包装器记录 124，没有正式报告 |

源码来源为 https://github.com/DinghaoJoe/libarchive ，commit `c4cfba676d2b86d6a2a7c508cd90a75c4dfaa1d9`。完整快照位于仓库根的 `.codex-tmp/kbscanner-sources-clean-20260909/libarchive`，原始超时日志位于 `.codex-tmp/kbscanner-noise-fixed-20260909/libarchive-full/execution.log`。这些路径仅供本机调查；后续验收必须由固定 provenance 和输入 manifest 验证，不能依赖临时路径长期存在。

四次 60 秒间隔的 faulthandler 栈均停在 `kb_scanner/normalization/cpp.py:72`。现有代码在每个 macro parameter/replacement token 上重建整个 Evidence 的 macro definition ID set。设 Evidence 数量为 E、宏附属数量为 M，该引用校验产生 O(E×M) 扫描。只把集合移到循环外可使这部分变为 O(E+M)；整个 normalize 仍包含排序和身份构造，不承诺整个阶段 O(E)。

这次没有观察到 SIGSEGV 或 OOM。采样时约 212.5 MiB 的内存不是峰值，不能据此认定整个扫描的内存上界。后续阶段尚未完成，不能断言 Normalizer 是唯一瓶颈。

## Goals / Non-Goals

**Goals:**

- 消除已证实的重复全量扫描，固定引用校验复杂度与失败语义。
- 获取同一全项目输入的分阶段耗时、数量、峰值资源和超时位置，再按证据优化必要的下游查找。
- 完整 libarchive 默认 V2 在原有 300 秒 / 2 CPU / 2 GiB 条件下完成并发布有效报告。
- 保持所有阶段的语义、证据闭包、确定性及显式 V1 兼容；每个实际修改模块具备隔离单元门禁。

**Non-Goals:**

- 不建设分布式/多进程扫描、跨扫描缓存、数据库、全局可变 registry 或新的任务调度系统。
- 不更换 Tree-sitter/Clang/NetworkX，不增加原生依赖，不恢复 Node/Tree 的跨阶段持有。
- 不删除宏 token、候选、基础关系或 source context，不提高 proof budgets/调整排除项来换取速度；允许不物化与任何候选无关的源码 proof，预算计数按第 7 节隔离。
- 不改变正确性规则、默认 V2、显式 V1 或三 artifact 合同；不修改后端、生产容器、根 Compose 或宿主机依赖。
- 不运行目标项目的编译、配置和测试，不分析操作系统迁移；缺少证据继续是 unknown/provisional。

## Decisions

### 1. 单次阶段调用内构建索引，不做持久缓存

在派生 compiler argument Evidence 合并后，为 macro definition ID 构建一次只读语义的 set/frozenset，作用域仅为本次 normalize。原有 enum declaration/member 集合已经在循环外，沿用同样的模式。排序、非法引用检查顺序、Diagnostic 内容、fatal 行为、canonical value、scope、producer/context 聚合均不改变。

不按文件名或宏名称代替 Evidence ID，也不让上一次 scan 的索引参与下一次调用。无效、缺失或错误类型的 `macroDefinitionEvidenceId` 仍产生 `normalization.invalid-macro-definition-reference`，失败时不发布无效 NormalizedSnapshot。

备选：依赖 LRU/global cache 可降低重复扫描但存在跨项目污染与失效问题；此处无需跨调用复用。把校验删掉虽快但破坏引用完整性，明确不采用。

### 2. 测试侧包装现有 PipelineProfile，复用标准库观测

已有 `PipelineProfile` 提供独立的 collect/load/analyze/normalize/detect/classify/assess/project 接口。benchmark 用测试侧 decorator 包装各实例，在调用前写 stage-start，返回/异常时写 stage-end、elapsed 和可用的输入/输出数量；透传同一个参数与返回对象，不修改 Diagnostic 或 CompletionStatus。使用 `perf_counter`、Linux `resource`/进程资源统计及可选 cProfile、faulthandler，不引入新运行时依赖。

性能工件放在专用测试输出目录，包含 scanner commit/源码 digest、image ID、Python/parser 版本、知识 digest、fixture digest、参数、资源上限、总耗时、逐阶段状态及数量、峰值 RSS 和退出分类。正式报告目录仍只有固定 artifact；时间、资源和绝对机器路径不进入 Evidence ID、snapshot 或 scan-result.json。

记录 start 后即 flush，阶段未完成也能识别最后进入的阶段。计时/超时/资源采集的测试 fake clock、process 和 writer。带 cProfile 的诊断运行与无 profiler 的验收运行分别标记，不比较两者墙钟来宣称性能提升。

备选：直接向 core DTO 或正式 V2 schema 增加 timing 会改变结果合同；本 change 不需要用户面监控，因此采用测试侧包装。仅打印总耗时无法定位阶段，故不采用。

### 3. 后续优化必须有 profile 证据并保持查询语义

先完成宏索引修复，再对同一全量输入做有界分析。重点检查现有 graph 中按 Evidence ID 的线性查找、关系生成中的全量过滤，以及 Detector 的重复 relation/knowledge 查找，但这些目前只是待验证的候选热点，不预先宣布必须修改。

如果 profile 证明它们阻止验收，优先复用已有 index，或在单次 analyzer/detector/projector 调用内构建 by-ID、by-subject、by-kind、adjacency 索引。多值索引保留所有关联与稳定顺序，不用单值 dict 覆盖合法多 producer/context/occurrence。不扩展新检测语义，不提高 traversal budget。用户确认的 fact 驱动反查见第 7 节；详细路径搜索算法仍保留。每项优化记录原热点、复杂度变化、额外内存和语义对照。

若剩余瓶颈需要超出局部索引/重复工作消除的架构重写或新依赖，保持任务未完成并说明新证据，先调整设计/获取方向，不能擅自扩展到并行服务。

### 4. 固定全项目输入，设独立性能入口

计划增加 `tests/run_performance_tests.py`（独立于日常 full regression）及 `tests/performance/` 支撑模块；复用/组合现有 `tests/tree_sitter_native_support.py` 的子进程退出分类思路，避免更改历史缩减样例的用途。独立入口要求显式传入完整 libarchive 只读 mount，缺失/摘要不符时非零退出，不下载、不 skip 后宣称通过。

持久化 `tests/fixtures/large-project-performance/PROVENANCE.json` 与排序后的项目相对输入 manifest：upstream URL、commit、每文件内容 SHA-256、集合 digest、language/exclude/comment/schema 参数、802+8 的预期分布。digest 在 apply 的基线阶段根据现有快照核验后生成，proposal 不编造哈希。来源获取是显式准备步骤；benchmark 与 scanner 执行期间网络关闭。现有 native crash 的单文件 fixture 和 9 文件预览不可以代替它。

复用唯一测试镜像；以独立 `docker run --rm` 或专用测试启动脚本施加 `--cpus 2 --memory 2g --memory-swap 2g`（禁止 swap 逃避内存上限）、network none、只读 code/fixture、cap-drop 和 no-new-privileges。可写报告挂载与输入分离，tmpfs 仍有固定上限。测试启动器不得控制其他任务的容器。镜像构建、fixture 哈希预检和 Docker 启动时间单列，不计入 scanner 的 300 秒；Python scanner 子进程启动至三个 artifact 发布均计入。

验收运行关闭 coverage/cProfile，用两个连续、独立的新 scanner 进程验证默认 V2；每次 <300 秒、exit 0、无 timeout/native crash/OOM，完整 810 输入不变，三个 artifact 和 V2 schema/引用闭包有效。主机页缓存可能热，不称为“冷磁盘基准”。记录两次总耗时和峰值，不仅挑最好的一次；主机争用必须记录，失败不能通过临时加资源或减少输入改成通过。

如果失败，父进程在 300 秒边界终止并回收本次 scanner 子进程，记录 timeout=124 或实际 signal/OOM 证据。真实 OOM 可能杀死容器，启动器须保留 Docker exit/OOMKilled 状态；不把所有非零码叫 OOM。使用全新输出目录避免把旧报告误认成成功。该预算是测试门禁，不给正式 CLI 新增全局 300 秒超时。

### 5. 语义与性能使用不同断言

- 宏密集 synthetic snapshot 同时扩大 E/M，以受控 Evidence 属性读取/集合构建计数证明全量定义枚举次数不随 M 增长；拒绝只检查源码有没有某行或只用易抖动的耗时比例。
- 小规模 reference/golden 对照覆盖有效/无效宏引用、多个 producer/context、乱序、无宏、连续扫描不同项目和派生 Evidence。比较整个 NormalizedSnapshot 与 StageResult 的 status/Diagnostic，而不只比较 Fact 数量。
- 保持已有 V1/V2、AVX、架构 enum、ARM/no_sanitize 排除、unknown asm、三个原生崩溃缩减 fixture 和完整回归。输出对照仅规范化既有机器路径等非语义差异，不忽略 ID、source span、reason、引用、数量和 readiness。
- 全量旧版本超时、没有旧报告，不能伪造其 finding baseline。优化后首次完整结果需通过 schema/reference、文件覆盖及代表性源码人工抽查，再审校冻结为回归基线，不能自动把当前输出批准为 golden。

### 6. 单元测试映射与资产边界

| 实际修改范围 | 隔离测试与门禁 |
|---|---|
| `normalization/cpp.py` | 复用 knowledge_detection unit 支撑，增加 macro index/reference/复杂度测试；fake compiler-context 派生边界，无 parser/文件系统 |
| 可选 graph/guard/detector/projection 模块 | 对应单元目录增加内存多值索引、完整/未知 proof、乱序、失效引用和跨调用隔离测试；仅实质修改时纳入 inventory |
| 新 benchmark/provenance/process 支撑 | fake clock、process、resource、writer、文件系统，覆盖超时/异常/OOM区分、缺失输入、摘要不符、stage透传和结果验证失败 |
| 独立性能入口和容器启动脚本 | 临时目录/假 Docker 调用或命令构造断言，验证资源/只读/退出传播，不启动生产服务 |

所有新增或实质修改的业务/支撑 Python 模块进入 `tests/large-project-performance-test-inventory.json`，单独统计 >=90% line / >=80% branch；launcher 的运行接线另做组件验收。真实解析、full project、coverage 下的运行不替代隔离模块覆盖，也不用其耗时作为正式性能结果。

两份 compiler fact JSON 内容与现有 hash 完全不变；curated/manifest、Legacy 冻结 oracle 不改。索引是内部查询结构，不进入报告；默认 V2 与显式 V1 都从原有 snapshots 投影，所有合法 Finding/trace/evidenceChain 语义不变。

### 7. Fact 驱动的按需源码 proof（2026-09-09 用户确认）

完整图包含 36,304 个起点、3,737 个目标，旧实现需要 135,668,048 对查询。只读可达性实验表明，8 层内只有 37,059 对可达组合，候选统计约 0.64 秒；这不是完整扫描性能验收。

1. 原始/Normalized facts 与基础图完整保留。新增纯内存需求选择器，复用 DetectorDefinition、KnowledgeIndex、match_fact；所有确定命中、疑似 candidate、hint 的 evidence_ids 都进入请求，不重新解析、不创建第二份词表、不做最终 ARM 排除/分类。主体、位置、producer/context 仍通过原始 Evidence ID 区分。
2. CompositeAnalyzer 为源码分析注入需求选择器，顶层 pipeline 和最终 Detector 顺序不变。独立分析器/假 GraphStore 可保留无请求的全量查询接口，便于差分 oracle 与自定义注入，不做 legacy schema 转换。
3. 需求按关系 provenance 传播，而不只认同名 symbol 终点。候选 Evidence 所关联关系的下游目标构成保守目标集合，再沿反向邻接寻找现有深度内的起点。索引不按 status、关系类型、架构或置信度删边。只作可达性预筛选；实际详细搜索仍读取完整图，保留路径顺序、并行边、cycle、visited/truncated、max-depth/max-visited/max-paths 和原 proof ID 计算。
4. 对每个候选起终点运行原搜索后，只物化至少经过一个需求 Evidence 的路径；同一对中所有需求相关路径及其原搜索状态保留。无可达路径的候选仍进入最终检测，不能当作排除或 ready。guarded_by、alternative_to、构建和测试关系完整保留，不以只沿 incoming 取代上下文补链。
5. 单次图内缓存排序后的邻接，add_relation 时按端点失效；候选计划每次查询构建，不跨扫描缓存。没有可靠候选索引能力的注入 store 回到原详细查询，不把 unavailable 当空集合。
6. 构建/测试分析继续完整运行，不要求 intrinsic 命中才执行。已有 len(proofs)/len(relations) 含继承图，容易被无关源码 proof 挤占；改为相应阶段新增数量，4096 等原上限不变。预算隔离会使曾被继承数量错误压制的链路恢复，这一差异必须显式测试/记录，不自动批准 golden。
7. 原全目标实现作为小图差分 oracle：比较所有需求相关 ProofPath 的全部字段、排序、非法/缺失引用、空请求、零长路径、并行边、环、预算边界与跨调用；保留全部事实和基础关系，增加继承大量无关 proof 不改变构建/测试局部预算的测试。逐修改模块 90% line / 80% branch。既有 V1/V2 golden 不自动更新，预算隔离之外的外部差异逐项调查。

实现不需要改变 NormalizedFact/AnalysisSnapshot 或 V1/V2 schema，不修改宿主依赖、后端和生产服务。消除 proof 热点后继续对正式各阶段观测；未通过两次 300 秒全量验收不得归档。

### 8. 构建源码知识匹配按已证明的文件成员关系延迟执行

fact 驱动 proof 后的 120 秒采样中，BuildSourceReachabilityResolver 的全量 fact × knowledge 匹配占 54.38 秒，且尚未结束。改为先保留全部 fact 的 subject 多值索引、x86 knowledge 的 kind 多值索引，再仅对已通过原有 Make target/pattern/include 静态检查的 reachable 文件执行原 matcher；匹配结果只在单次 resolve 内按 subject 缓存。所有匹配 ID 排序、多种 fact kind 的原边界/大小写规则、包含链和选中/未知配置不变。没有源文件成员关系时不做无用匹配，但不省略基础图或构建事实。构建诊断的 inherited relation ID 集合也改为单次建立，避免逐关系重复枚举。

## Risks / Trade-offs

- [去掉首个热点后暴露更多热点] → 分阶段记录与有界 profile；把通过全量门禁作为完成条件，而不是只提交一个 hoist。
- [索引换取额外内存] → 只保存 ID/引用与必要多值映射，不复制源码/整张 snapshot，记录峰值并遵守 2 GiB 容器上限。
- [重排或覆盖多值关系使结果漂移] → reference/golden、乱序和多 producer/context 单元测试逐字段检查。
- [全项目第三方输入不易在 CI 获得] → 显式 mount + 固定 manifest，离线合成测试进入日常回归；独立真实性能 gate 缺失 fixture 必须失败，本 change 不得据此勾选完成。
- [旧配置文案仍提 YAML/V1] → 本 change 以已同步的正式默认 V2/显式 V1 和 JSON knowledge 合同为准，不恢复历史运行路径，也不顺手修改无关配置。
- [测量干扰及宿主机资源争用] → 分离 profiler/coverage 与验收运行，保留环境记录和两次独立进程结果，预算不随失败临时放宽。

## Migration Plan

1. 核验固定完整 fixture/manifest、保存已有超时证据，建立合成失败用例、性能支撑测试和 unit inventory。
2. 在测试侧接入 stage 观测及父进程超时，记录可复现环境。
3. 实现单次 normalize 宏定义索引，完成引用与复杂度单元验证。
4. profile 同一全项目，对确有必要的后续重复查找做局部优化并逐模块补测。
5. 独立容器运行隔离覆盖、既有全量兼容回归，以及两个默认 V2 全项目性能验收；记录报告语义审校和前后数据。
6. 验收全部闭合后再 sync/archive。回滚只需回退本 change 的代码和性能门禁接入，不需要数据或 schema 迁移。

## Open Questions

- 首个热点消除后，图构建/检测/投影各占多少成本？apply 时通过 phase profile 决定实际修改文件，不能预先声称已解决。
- 完整 libarchive 结果中有哪些 findings/unknown？目前超时没有报告，apply 阶段进行代表性人工审校；性能优化不得据预览零命中预设全项目为零。
