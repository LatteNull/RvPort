## 1. 协议与兼容性基线

- [x] 1.1 冻结并记录现有 P1–P5 schema、CLI、fixture 和 semantic digest 基线，增加旧请求/产物读取与默认行为回归单元测试。
- [x] 1.2 审核 P2–P4 request/dependency 表达能力，确定 additive 请求版本或包装请求方案，并用 schema compatibility 单元测试证明旧版本语义不变。
- [x] 1.3 定义 `CompilationProfileIdentity v1`、canonical digest、路径规范化和 GCC-to-Clang 重放状态，覆盖宏/include/target/ABI/debug/优化差异的 Python 单元测试。
- [x] 1.4 定义并严格校验 `SourceSemanticRequest/Facts v1` schema、kind、版本、依赖与确定排序，覆盖未知字段、未来版本、重复身份、陈旧 digest 和零分母单元测试。
- [x] 1.5 定义并严格校验 `ProgramEntityIndexRequest/Index v1` schema，覆盖 scope/profile 冲突、悬空引用、歧义和 deterministic digest 单元测试。
- [x] 1.6 定义并严格校验 `SourceIRBindingRequest/Binding v1` schema，覆盖一对多/多对一、候选集合、evidence level、替换依赖和预算 frontier 单元测试。
- [x] 1.7 定义并严格校验 `AstAssistedAnalysisRequest/Report v1` 与 `CanonicalObjectOverlay v1` schema，覆盖双语字段、分层分母、cache metadata 和退出状态单元测试。

## 2. Clang LibTooling 构建与 worker 边界

- [x] 2.1 更新 CMake 与 `Dockerfile.dev`/依赖锁定清单，链接 LLVM/Clang 21.1.8 LibTooling 所需库，并验证不会修改生产 Dockerfile 或现有 worker 链接行为。
- [x] 2.2 新增 `memory-order-source-worker` 入口、stdin/stdout/stderr 边界、严格请求解析和最小失败报告，提供正常、无效 schema、异常与超大输出 C++ 单元测试。
- [x] 2.3 实现逐 TU CompilerInvocation/CompilationDatabase 重放与 profile 一致性校验，提供 Clang、可兼容 GCC、GCC-only 选项、缺失 include 和 fatal diagnostic 单元测试。
- [x] 2.4 实现 wall、节点、引用、诊断和输出字节预算及 frontier，提供边界值、预算耗尽、部分结果和确定排序 C++ 单元测试。
- [x] 2.5 实现 worker 进程失败/诊断的中英文稳定 code/detail/detail_en 映射，提供崩溃模拟、非零退出、stderr 截断和非法 UTF-8 单元测试。

## 3. SourceSemanticFacts 提取

- [x] 3.1 实现 TU-local node identity、canonical declaration/definition、USR、qualified/mangled name 和 physical TU/source file identity，覆盖重复声明、跨文件 include 和空 USR 单元测试。
- [x] 3.2 实现 language linkage、storage/linkage、visibility、TLS、template/inline/weak/COMDAT 分类和 canonical type/ABI facts，覆盖 C tentative/common、static、匿名 namespace 与 ODR fixture 单元测试。
- [x] 3.3 实现 spelling/expansion range、宏栈、include hash、inlined/source anchor 和稳定 ordinal，覆盖嵌套宏、同一行多表达式、路径重映射和无 debug 场景单元测试。
- [x] 3.4 实现变量/字段/参数引用、初始化、直接赋值、直接调用和有限 cast/compare/return value-flow facts，覆盖正常、别名未知、间接调用和未支持表达式单元测试。
- [x] 3.5 实现 C/C++ atomic 源操作及直接 pthread_create/join/mutex 调用、callback/handle 源事实，覆盖 typedef、wrapper、错误原型和 ambiguous callee 单元测试。
- [x] 3.6 实现受限消费者成功分支与 source control-dependency 线索，覆盖 if/while/短路条件、宏比较、反向条件和不可识别控制流单元测试。
- [x] 3.7 生成严格 `SourceSemanticFacts`、精确分母和 partial/failed frontier，并对所有提取器模块达到行/分支覆盖率至少 90%。

## 4. Source evidence 编排、缓存与 CLI

- [x] 4.1 实现 Python source worker client、进程隔离、stdout JSON/stderr 日志、timeout/output limit 和最小失败产物，提供正常、超时、崩溃、空输出与损坏 JSON 单元测试。
- [x] 4.2 实现按显式 scope 计划 source TU、拒绝 scope 外自动扩展、保留 planned/failed 分母，覆盖重复 compile record、缺失 TU 和路径别名单元测试。
- [x] 4.3 实现 source-facts cache key、原子发布、重新校验和损坏/陈旧 entry 隔离，覆盖 cold/warm、digest 替换、部分写入和并发读取单元测试。
- [x] 4.4 实现 `index-source-evidence --request --artifact-store --output --worker` CLI 的空输出目录、stdout/stderr、0/2/1 退出码和确定性报告，提供 CLI 单元测试。
- [x] 4.5 集成现有 artifact store 和依赖引用而不扫描“最新”文件，覆盖显式路径、悬空依赖、混合代际和只读历史产物单元测试。

## 5. 跨 TU ProgramEntityIndex

- [x] 5.1 实现 source entity 候选分组，组合 language/profile、USR、mangling、canonical type、entity kind、linkage、TLS、visibility 和 ABI 证据，提供唯一、缺失和冲突候选单元测试。
- [x] 5.2 实现 external declaration/唯一 definition 选择和 scope 外 unresolved 处理，覆盖 C/C++ 跨三 TU 声明/定义与缺失定义单元测试。
- [x] 5.3 实现 internal linkage、file-static 和匿名 namespace 的 physical-TU 隔离，覆盖同名同类型对象/函数不得合并的单元测试。
- [x] 5.4 实现 C tentative/common 白名单解析，覆盖兼容 tentative、强定义覆盖、类型冲突和不同 profile 单元测试。
- [x] 5.5 实现 C++ inline/template/ODR 与 weak/linkonce/COMDAT/TLS 的 resolved-set/ambiguous/conflict 分类，覆盖等价与不等价 fixture 单元测试。
- [x] 5.6 实现 canonical program entity/object key、声明/定义关系、证据和 deterministic ordering，确保与摘要复用、LLVM 对象、调用/线程实例身份分离并提供单元测试。
- [x] 5.7 实现 entity-index 预算、cache、精确分母和 frontier，覆盖截断、冷/热 semantic digest 一致性及损坏 cache 单元测试。

## 6. AST–IR 证据绑定

- [x] 6.1 实现 profile/TU、mangled name、LLVM linkage/visibility/TLS/COMDAT、类型/ABI 和 definition role 的 function/global entity binding，覆盖 exact/candidate/ambiguous/unresolved 单元测试。
- [x] 6.2 实现 debug location、spelling/expansion range、inlined-at、所属函数、object、opcode/atomic ordering 和控制上下文的 expression-to-instruction binding，覆盖一对一、一对多、多对一单元测试。
- [x] 6.3 实现无 debug、优化折叠、同一行多操作和宏展开的保守降级，验证实体级证据可保留但表达式级不得伪 exact。
- [x] 6.4 实现 binding dependency/scope/profile/digest 校验和混合配置拒绝，覆盖替换 ModuleFacts、不同 target、不同宏和悬空 BC artifact 单元测试。
- [x] 6.5 实现 binding 预算、cache、证据排序、精确分母和 frontier，覆盖 cold/warm 语义一致、截断和损坏 cache 单元测试。
- [x] 6.6 增加负向单元测试，证明 SourceIRBinding 不生成或提升 memory order、SB、RF、SW、HB 或安全结论，并使全部受影响 binding 模块行/分支覆盖率至少 90%。

## 7. CanonicalObjectOverlay 与 scope 接入

- [x] 7.1 从 entity index 与 IR binding 派生不可变 `CanonicalObjectOverlay`，保留所有 artifact-local key、resolution/binding evidence 和依赖 digest，覆盖跨 TU external 与 TU-local static 单元测试。
- [x] 7.2 更新 scoped module association 的显式 AST-assisted 路径，消费 overlay 但不推导 target/link 图或纳入 scope 外 TU，提供回归与负向单元测试。
- [x] 7.3 实现 ambiguous/conflict/unresolved overlay 的保守传播，不按名称、输入顺序或 cache 顺序任取候选，覆盖排序扰动单元测试。
- [x] 7.4 实现 overlay 预算/cache/报告并验证 IR-only 默认路径、旧 schema 与 semantic digest 不变。

## 8. P2/P3 source-assisted 组合

- [x] 8.1 在 additive/包装请求中向 P2 直接调用组合提供 verified canonical function/object evidence，保持 EffectSummary v1 原始事实和旧请求语义不变，并提供兼容性单元测试。
- [x] 8.2 实现跨 TU direct wrapper 的参数/返回值特化，只接受唯一 callee/entity/IR binding，覆盖 wrapper 链、递归预算、ambiguous callee 和 unknown 单元测试。
- [x] 8.3 向 P3 补充直接 pthread callback target 与受限 `pthread_t` 声明/初始化/直接赋值 provenance，覆盖 create/join 跨 TU、handle 逃逸和重复实例单元测试。
- [x] 8.4 验证 ThreadContext 与 ThreadInstance、摘要上下文与调用实例仍分离，并覆盖递归/预算合并的保守语义单元测试。
- [x] 8.5 增加负向单元测试，证明 AST callback、调用和源码顺序不直接产生 SB/SW/HB/MHP discharge，相关 IR/order 证据缺失时保持 partial/unknown。

## 9. P4 publication source-assisted 组合

- [x] 9.1 使用 verified overlay 统一跨 TU flag/payload identities，覆盖 extern 声明/定义、同名 static、weak/ODR ambiguity 和 TLS 单元测试。
- [x] 9.2 组合 direct wrapper、有限 compare/cast/return 与 LLVM observation/control-dependency 证据，覆盖消费者成功/失败分支、无 debug 和 source-only binding 单元测试。
- [x] 9.3 实现 candidate-relevant dependency slice 和全请求/逐候选双层完整性，覆盖无关 TU 失败、producer binding 缺失、线程依赖缺失和预算截断单元测试。
- [x] 9.4 保持 P4 既有 risk/discharged/unknown、双语字段和 0/3/2/1 风险退出码；增加旧 IR-only 请求、P3 reads-from candidate 和 EffectSummary.order 不被提升为证明的回归单元测试。
- [x] 9.5 对跨 TU flag/payload、wrapper、pthread callback/handle 的 P1–P4 证据链执行固定集成测试，并保存每层 identity/digest 以供 truth 对照。

## 10. P5 真值、规模与决策证据

- [x] 10.1 创建新的版本化 AST+IR suite/truth，覆盖 C11/C17/C++17/C++20、GCC/Clang、单/三 TU、linkage/ABI、宏/profile、debug/no-debug、歧义和 unsupported 边界，保持历史 truth 不变。
- [x] 10.2 扩展 validation runner/report，分别统计 source extraction、entity resolution、entity/expression binding、overlay 和 candidate slice 分母，覆盖零分母、partial 和陈旧 truth 单元测试。
- [x] 10.3 对相同 reviewed truth 与预算运行 IR-only/AST-assisted 对照，发布 exact match、TP/FP/FN、strict/supported-only、abstention、增量命中和回退 case。
- [x] 10.4 在固定 TinyCThread profile 上执行 AST-assisted cold/warm 规模基线，记录 wall/CPU、峰值 RSS、产物字节、cache hit/miss、完整性和 deterministic semantic digest。
- [x] 10.5 更新 `AnalysisExtensionDecision` 的量化输入，区分 AST 已缓解缺口与仍需 B1 CMake scope、std::thread、通用指针分析、fence/RMW 的 frontier，不自动创建后续 change。

## 11. 单元测试与覆盖率门禁

- [x] 11.1 将全部新增/修改 C++ 源码、头文件和 worker 纳入 LLVM coverage，禁止用集成测试或排除自有业务代码补分母，并使整体 C++ line/branch 至少 90%。
- [x] 11.2 将全部新增/修改 Python 包、CLI、schema/index/binding/overlay/validation 模块纳入 coverage，包含未加载源码并使整体 Python line/branch 至少 90%。
- [x] 11.3 生成并门禁项目整体以及每个受影响 C++/Python 模块的 line/branch hit/total 全清单，全部至少 90%，任一模块不足时非零退出。
- [x] 11.4 在锁定开发容器离线执行全量单元测试，记录测试数、失败/跳过、环境和报告路径；宿主机缺少 pytest 不得替代容器验收。
- [x] 11.5 运行旧 P1–P5 protocol/CLI/cache fixture 的完整回归，确认旧模式 semantic digest、退出码和安全边界未改变。
- [x] 11.6 运行固定 AST+IR 集成矩阵和 deterministic 重跑，验证不原生链接、不运行目标程序、不访问网络/SSH/DevKit/外部后端。

## 12. 文档、最终验收与可归档性

- [x] 12.1 更新 README、`doc/README.md` 和 `doc/IMPLEMENTATION_ROADMAP.md`，登记 P5 已归档、当前 change 状态、AST/IR 边界和仍未授权的 B1/std::thread/pointer/fence/RMW。
- [x] 12.2 新增 `doc/AST_CROSS_TU_EVIDENCE.md`，说明协议、profile identity、实体解析、绑定基数、CLI、cache/预算、完整性、双语诊断和非安全证明边界。
- [x] 12.3 新增 `doc/AST_CROSS_TU_EVIDENCE_VALIDATION.md`，记录实际命令、版本/hash、测试与整体/语言/逐模块覆盖率、truth 对照、TinyCThread 性能/缓存、报告路径和 not_run/限制。
- [x] 12.4 运行文档链接、阶段状态、证据来源、双语示例和禁止性表述自动校验；任何计划或未运行结果不得写成已实现/已验证。
- [x] 12.5 在全新输出目录完成 schema/OpenSpec strict validation、全量单元/覆盖率、离线 truth、旧协议回归、真实工程 cold/warm 和文档门禁，并保存最终 acceptance manifest。
- [x] 12.6 复核全部 task、报告和 coverage 分母；仅在所有必需门禁通过且无未处理实现任务时标记 change 可 sync/archive。

## 13. 2026-09-20 跨 TU false-negative 纠偏

- [x] 13.1 增补审计 fixture 和单元测试，重现相同 artifact-local LLVM target 被多条 source binding 重复收集、`extern` declaration 指向唯一 definition、系统外部声明污染全局完整性和 P4 零协议候选的路径。
- [x] 13.2 修复 `CanonicalObjectOverlay` target 去重和集合级唯一定义规则；保留全部 binding/source evidence，并确保真实多定义、ABI/profile/linkage/TLS/visibility 冲突仍为 ambiguous/conflict。
- [x] 13.3 将已建模 pthread/standard-library 系统声明登记为 external boundary，使其不计入无关用户 program object 的 candidate-relevant completeness；未识别外部声明仍保守 unresolved。
- [x] 13.4 修复 P4 candidate-relevant 完整性与 downstream consumption 分母；当相关 thread/atomic/payload facts 存在但候选为零时，输出稳定中英文 `publication-candidate-unresolved` 诊断和 missing reasons。
- [x] 13.5 运行针对性跨 TU 集成回归，确认 `c11-risk-multi` 与 `cpp20-risk-multi` 在 AST-assisted 模式均产生非零 protocol 候选并输出 risk，无新 FP，fence/CAS unknown 边界不变。
- [x] 13.6 重跑固定 AST/IR truth 矩阵和 TinyCThread cold/warm，更新验收文档、机读 manifest、semantic digest、分层完整性和实际 TP/FP/FN/abstention，不沿用修复前指标。
- [x] 13.7 在全新输出目录重跑 OpenSpec/schema/文档、全量 C++/Python 单元测试与整体/语言/每个受影响模块 line/branch 至少 90% 门禁；全部通过后再标记 change 可 sync/archive。
