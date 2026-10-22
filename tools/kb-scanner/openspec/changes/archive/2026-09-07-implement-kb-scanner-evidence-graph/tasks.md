## 1. 基线与不可变边界

- [x] 1.1 新增版本化 AVX evidence-graph 人工审计 baseline，逐项记录 37 个 C/C++ 文件、39 个 x86 header、362 个 vector type、360 个普通源码 intrinsic call、45 个 comment hint、12 个函数式宏定义、18 个 replacement-body 终端 intrinsic 引用及代表性 source span；baseline MUST NOT 由 scanner 输出自动生成或覆盖。
- [x] 1.2 为 AVX baseline 增加 schema/lint 单元测试，验证重复项、无效相对路径、越界位置、类别计数和审计说明，并明确将 4 个 Makefile 的 24 个 x86 flag 标记为 `deferred-build-selection`。
- [x] 1.3 固化两份既有 `clang-x86-entries.json`、`gcc-x86-entries.json` 的内容/哈希/六类计数及 legacy YAML `generatedSet` 引用回归，确保本 change 不重写这些事实数据。
- [x] 1.4 新增 Legacy import boundary inventory/AST 测试，禁止新 graph、analyzer、macro frontend/normalization 模块导入 legacy adapter、旧 parser/models/rules/report 或 YAML runtime，同时允许默认 CLI 继续只经 compatibility adapter 使用 Legacy。

## 2. Core 图合同与 Pipeline 接口

- [x] 2.1 在 core 中新增冻结、稳定身份的 `ProofPath` 与 `PathSearchResult`，并以默认空 tuple 扩展 `AnalysisSnapshot.entities`/`proof_paths`，保持 `AnalysisSnapshot()` 现有构造兼容。
- [x] 2.2 为 ProofPath、PathSearchResult 和扩展 AnalysisSnapshot 编写隔离单元测试，覆盖合法/非法 SHA-256 引用、complete/partial/unknown、不可变 tuple/metadata、默认值和确定性身份。
- [x] 2.3 将 `Analyzer.analyze` 合同改为显式接收 `ScanContext + NormalizedSnapshot + KnowledgeSnapshot`，更新 orchestrator、recording/no-op analyzer 与全部 profile/test doubles，但不改变固定阶段顺序。
- [x] 2.4 为 orchestrator 协议变更编写隔离单元测试，验证同一扫描 knowledge/facts 身份传递、Analyzer 位于 Normalizer 与 Detector 之间、partial/failed Diagnostic 传播和 projector 唯一写 artifact 的边界。

## 3. 宏参数与 Replacement Evidence

- [x] 3.1 扩展 C/C++ Evidence vocabulary，加入 `macro_parameter` 与 `macro_replacement_token` 的值、metadata、definition Evidence 引用、token ordinal/role、SourceSpan 和稳定排序/身份规则。
- [x] 3.2 为 vocabulary 编写隔离单元测试，覆盖同名不同位置、参数顺序、token role、不同 producer/context、非法 definition 引用材料和重复运行稳定性。
- [x] 3.3 扩展 Tree-sitter baseline，从 `preproc_def`/`preproc_function_def` 字段范围提取函数式宏参数与有意义的 replacement token，识别 token-pasting/stringification/variadic/recovery 为 partial，且不得把 definition 节点产生为 `call_expression`/`macro_expansion`。
- [x] 3.4 使用 fake parser/tree/node/bytes 为宏提取编写隔离单元测试，覆盖 object-like/function-like、零/多参数、intrinsic 调用 token、嵌套宏、`##`/`#`/variadic、ERROR/MISSING、超长行 Point 快照和 definition ancestor 排除。
- [x] 3.5 评估锁定 libclang detailed preprocessing record 是否能稳定提供 replacement token extent；仅在可复现时补充 Clang producer，否则记录拒绝证据并保持 Tree-sitter baseline 为正式来源。
- [x] 3.6 为 Clang 选择结果补充相应 adapter 单元测试：若接入则 fake cursor 覆盖 token extent/provenance/降级；若不接入则测试现有 definition/expansion 行为不伪造 replacement Evidence。

## 4. 宏结构事实归一化

- [x] 4.1 扩展 `CppEvidenceNormalizer`，把 macro parameter/replacement Evidence 归一为稳定 facts，保留 definition Evidence ID、ordinal、role、SourceSpan、confidence、producer 和 compilation context，并校验附属引用存在。
- [x] 4.2 为 macro normalization 编写隔离单元测试，使用纯 core fixtures 覆盖跨 producer 合并、同 token 不同 definition/位置不合并、非法引用失败、unsupported token partial 和确定性排序。
- [x] 4.3 更新 normalization/knowledge acceptance inventory，使 replacement token 只在有界 token fact 上参与现有 compiler-derived/curated knowledge 匹配，不回退为整文件 regex 或修改两份事实 JSON。
- [x] 4.4 为新增 matcher 输入编写隔离单元测试，验证已知 intrinsic token 精确匹配、宏参数同名不误匹配、普通 identifier 不升级以及全部 Evidence/Knowledge provenance 保留。

## 5. 正式 GraphStore Adapter

- [x] 5.1 在正式 `kb_scanner/graph` 包定义 scanner-owned GraphStore protocol，覆盖 Entity/Relation 注册、按方向/kind 查询和显式预算的 path search；不得复用 technology spike DTO 或暴露 NetworkX 类型。
- [x] 5.2 将 NetworkX MultiDiGraph 收敛为正式 adapter，校验端点、保留平行边、返回确定性排序、转换第三方异常，并实现 max-depth/max-visited/max-paths 有界查询。
- [x] 5.3 为 GraphStore protocol/NetworkX adapter 编写隔离单元测试，覆盖重复实体、未知端点、同端点平行边、方向/kind 过滤、无路径、循环、深度/访问/路径数截断、稳定排序和无第三方类型泄漏。
- [x] 5.4 仅在 `kb-scanner-test` 容器的锁定依赖中加入正式验证所需 NetworkX 版本，确认宿主机、生产镜像、根 Compose 与现有运行服务不被修改。

## 6. Entity 索引与直接 Relation 构建

- [x] 6.1 实现 `GraphEntityIndexer`，从 NormalizedSnapshot 确定性建立 project、source file、macro definition/invocation、condition group/branch、symbol/call site 和 implementation Entity，并校验项目相对身份材料。
- [x] 6.2 为 GraphEntityIndexer 编写隔离单元测试，使用 fake snapshots 覆盖同名跨文件、同文件重定义、多 compilation context、缺失 span、非法 subject 和跨 checkout 稳定性。
- [x] 6.3 实现本地 include resolver：quote include 按 including-file parent 后 workspace root 有界解析，唯一命中建立 complete `includes`，system/missing/ambiguous/unsupported path 保留 external/candidate Entity 与 partial/unknown Diagnostic。
- [x] 6.4 为 include resolver 编写隔离单元测试，fake workspace index 覆盖父目录命中、root 命中、重复候选、system header、缺失文件、路径逃逸和确定性候选排序，不读取真实项目。
- [x] 6.5 实现 `RelationBuilder` 的 `defines`、`includes`、`invokes_macro`、`expands_to`、`calls` 关系，按宏名称/可见 include/位置保留唯一或歧义定义，并按稳定 Relation ID 合并全部 Evidence provenance。
- [x] 6.6 为宏/调用 RelationBuilder 编写隔离单元测试，覆盖跨文件唯一宏、同名多定义、重定义、definition-only、replacement 调用另一个宏、终端 symbol、未知引用和宏定义不得成为调用。

## 7. 条件分支与替代实现关系

- [x] 7.1 实现预处理 condition group/ordered branch range 索引与 `has_branch`、`guarded_by` 关系，使 include、call 和 implementation 可定位到实际 sibling branch。
- [x] 7.2 为 branch index/builder 编写隔离单元测试，覆盖 if/elif/else、嵌套条件、缺失 endif/partial parse、相邻但非 sibling 分支和稳定 branch ordinal。
- [x] 7.3 实现 branch role resolver，只消费 normalized condition token 与 KnowledgeSnapshot，把有证据的分支标注为 x86、riscv、generic、portable、scalar、fallback 或 unknown，并保留 KnowledgeEntry provenance。
- [x] 7.4 为 role resolver 编写隔离单元测试，覆盖 x86/RISC-V alias、generic/fallback、否定条件、注释词不得定角色、知识缺失 unknown 和不同知识版本 provenance。
- [x] 7.5 实现 sibling `alternative_to` builder，只在同一 condition group 和实现关联证据存在时从 x86 端指向非 x86 sibling，不判定 active、blocking、severity 或 readiness。
- [x] 7.6 为 alternative builder 编写隔离单元测试，覆盖 x86↔RISC-V、x86↔generic/portable/scalar/fallback、只有 x86、名称相似但非 sibling、unknown role 和嵌套 sibling。

## 8. 有界 Proof Path 与 Graph Analyzer

- [x] 8.1 实现 `ProofPathResolver`，使用默认 maxDepth=8、maxVisited=10000、maxPaths=4 的显式不可变配置，物化 ordered Relation IDs、visited/truncated 与 complete/partial/unknown reason。
- [x] 8.2 使用 fake GraphStore 为 ProofPathResolver 编写隔离单元测试，覆盖跨文件宏终端路径、嵌套宏、cycle、not-found、unknown input、三类预算截断、多条等长路径和确定性选择。
- [x] 8.3 实现正式 `EvidenceGraphAnalyzer` 编排 EntityIndexer、RelationBuilder、branch/alternative resolver、GraphStore 与 ProofPathResolver，校验引用并输出排序后的 AnalysisSnapshot/StageResult Diagnostic。
- [x] 8.4 为 EvidenceGraphAnalyzer 编写隔离单元测试，全部下游使用 fake/mock，覆盖完整、partial、unavailable、invalid reference failed、diagnostic merge、knowledge identity 与重复运行稳定性。
- [x] 8.5 仅对已证明的 source/include/macro/implementation 路径派生 `reachable_from`，并保证缺失构建选择时目标可达性保持 unknown 而非 active/inactive。
- [x] 8.6 为 `reachable_from` 派生编写隔离单元测试，覆盖 complete macro path、partial include、ambiguous definition、无 build evidence 和禁止产生 readiness/blocking 字段。

## 9. Detector 与 Qualification 接入

- [x] 9.1 扩展 Local Detector/Observation relation context，使 macro replacement 的知识命中可引用 Relation/ProofPath ID，并让 `alternative_to` 只作为上下文，不在本阶段形成 blocking、severity 或 readiness。
- [x] 9.2 为 Detector graph consumption 编写隔离单元测试，覆盖完整宏路径、partial/unknown path、definition-only 不成 call、alternative role 保留、无效 relation 引用失败和普通局部命中行为不退化。
- [x] 9.3 新增/更新 staged qualification profile factory，用真实 EvidenceGraphAnalyzer 替换 `_EmptyAnalyzer`，继续使用 recording/no-op Classifier、Assessor、Projector，并保持默认 CLI 选择 legacy compatibility profile。
- [x] 9.4 为 qualification wiring 编写 recording-stage 单元/组件测试，验证 Workspace→Knowledge→Frontend→Normalizer→Analyzer→Detector 顺序、真实 AnalysisSnapshot 传播、partial capability Diagnostic 和零 artifact 写入。
- [x] 9.5 更新 `behavior-acceptance.json`，把 macro/include/sibling alternative 的已实现部分标记为 graph-backed，同时继续保留 build source selection、RPM/test selection、blocking/severity/readiness 为 deferred。
- [x] 9.6 为 acceptance matrix 更新 schema/lint 回归，防止 graph-backed 状态误覆盖需要 build/classification 的能力。

## 10. 真实项目、性能与兼容回归

- [x] 10.1 在 AVX/AVX2 真实项目上运行 staged graph qualification，逐条对照人工 baseline 并输出具体 file/span 差异；验证 12 个 macro definition 不计为 call、18 个 replacement terminal intrinsic 可定位且代表性调用形成跨文件 proof path。
- [x] 10.2 增加合成 component fixtures，覆盖 x86/RISC-V sibling、x86/generic fallback、只有 x86、跨文件嵌套宏、宏循环、缺失/歧义 include 和 unsupported replacement semantics。
- [x] 10.3 扩展 machine-readable unit-test inventory 与容器 runner，将每个新增/实质修改业务模块映射到隔离 unit suite，并分别执行至少 90% line / 80% branch 门禁；真实 parser/knowledge/AVX/integration/benchmark 不得计入 unit coverage。
- [x] 10.4 在 `kb-scanner-test` 容器运行 1,000 Entity/3,000 Relation 合成图与 AVX graph 基准，记录 Python/NetworkX 版本、规模、时间、峰值 RSS 和查询预算；graph 阶段 MUST 不超过 15 秒且峰值 RSS 增量不超过 512 MiB。
- [x] 10.5 在唯一测试容器中依次运行 frontend unit、knowledge/detection unit、graph unit、component/integration、AVX baseline、legacy compatibility、后端结果合同和 full regression，确认 `schemaVersion: "1.0"`、顶层字段、Finding 关键语义与三个 artifact 不变。
- [x] 10.6 更新开发计划、模块/测试 inventory 和 qualification 使用文档，说明 Evidence Graph 已完成、Build Selection 与 Classifier/Assessor 仍 deferred、默认 CLI 仍为 Legacy，以及下一 OpenSpec change 的明确边界。
- [x] 10.7 运行 `openspec validate implement-kb-scanner-evidence-graph --strict`、代码格式/静态检查和 `git diff --check`，确认 change artifacts、实现、测试、容器依赖与文档全部一致后再申请 sync/archive。
