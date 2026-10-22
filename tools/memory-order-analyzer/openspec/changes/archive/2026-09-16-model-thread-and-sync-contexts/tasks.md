## 1. 冻结基线与定义 P3 协议

- [x] 1.1 固化 `ModuleFacts v2`、`RunReport v2`、`LocalAnalysisFacts v1`、`LocalEvaluationResult v1`、`EffectSummary v1` 和既有 CLI 的黄金输入/输出，增加逐字节及语义兼容单测，证明 P3 不修改 P1/P2 身份或格式。
- [x] 1.2 定义 `ThreadAnalysisRequest`、`ThreadLocalFacts`、`ExecutionOrderFacts`、`ThreadContextGraph`、`ThreadAnalysisReport` v1 schema，以及 `analysis_version=0.1.0`、`thread-sync-contexts-v1` 协议；补齐合法、缺字段、未知字段/kind、未来版本和双语字段成对校验单测。
- [x] 1.3 实现 P3 canonical identity、SourceRef/AnalysisRef/Object/Value/Guard/Effect/Invocation 跨层引用与 digest/归属闭包校验，覆盖悬空、跨函数/线程、陈旧 P2、混合 profile、伪造角色和循环引用单测。
- [x] 1.4 为 P3 定义上下文/实例/生命周期/顺序/MHP/mutex/reads-from/frontier 的稳定 ID、枚举和排序，增加确定性、重复 ID、无序输入及 merged/unknown 非单例语义单测。
- [x] 1.5 扩展 worker 协议协商和批处理操作，保持原 P1/P2 操作不变；测试旧 worker、新旧 policy、请求调包/遗漏/重复、stdout/stderr 隔离、超时与输出上限。

## 2. LLVM 局部线程事实

- [x] 2.1 在只读且 hash/parse/verify 校验的模块上登记 pthread 候选调用、精确符号/接口/calling convention/属性和参数角色，补充 direct、间接、相似名称、ABI 不兼容及跨 profile 单元测试。
- [x] 2.2 使用 LLVM API 提取 callback metadata 和直接函数地址，并实现受限 bitcast/select/phi 回调候选；测试 metadata 一致、缺失、冲突、超预算及 unknown wrapper，不通过调试名或 `.ll` 正则推断入口。
- [x] 2.3 提取 call entry、normal-exit、unwind、no-return anchor 并绑定 P2 invocation，测试 call/invoke、nounwind、noreturn、异常路径、跨 TU 被调和缺失被调结果。
- [x] 2.4 登记 create 输出位置、handle load/store/copy、join 输入和 mutex 对象/范围/initializer/clobber 的局部 provenance 节点，覆盖局部/全局精确槽、phi/select、覆盖、逃逸、未知别名和未支持转换。
- [x] 2.5 为新增原始节点与 LLVM 生成证明使用分离的 SourceRef/AnalysisRef 命名空间，验证函数归属、输入引用和最小证据闭包；失败或超预算不得发布悬空、截断但标 complete 的事实。

## 3. 独立执行顺序证明

- [x] 3.1 实现同基本块指令顺序和 CFG 可达性关系，使用 DominatorTree/PostDominatorTree/LoopInfo 生成 must-before、may-before、互斥或 unknown；为直线、菱形、多后继、共享后继和不可达块补单测。
- [x] 3.2 实现循环与重复发生语义，覆盖回边、循环内外事件、多迭代次序反转、nested loop 和未知 multiplicity，禁止仅凭支配关系输出错误 must-before。
- [x] 3.3 使用调用 anchor、invocation 和出口事实组合跨调用顺序，测试调用前/入口/退出/调用后、异常/不返回、递归和合并实例，确保未证明正常返回时不串接后继。
- [x] 3.4 增加 P2 `EffectSummary.order` 隔离回归：仅有 P2 order、分支遍历顺序或摘要拼接时不得产生 P3 must-before/HB；同时验证合法 ExecutionOrderFacts 可以产生对应边。
- [x] 3.5 接入局部候选/工作项/输出/墙钟预算及非空 frontier，单测边界值、显式收紧、确定性计数、部分可用和全部失败。

## 4. pthread 模型注册与采用

- [x] 4.1 实现版本化 `posix-pthread-v1` 注册表，描述 `pthread_create`、`pthread_join`、`pthread_mutex_lock`、`pthread_mutex_unlock` 的 ABI、参数角色、返回成功条件和语义事件；为模型 schema、版本及非法定义补单测。
- [x] 4.2 实现 pthread 调用采用器，联合直接符号、接口、calling convention、target/profile、边界和 callback metadata 复核；测试合法采用、interposition/别名冲突、metadata 冲突、未知属性和相似自定义 API 拒绝。
- [x] 4.3 实现普通非 robust 静态 mutex initializer 的锁定 libc/target 指纹模型，记录模型假设；测试支持指纹、不同 target/libc、未知/动态初始化及不得推导 `pthread_mutex_init` 属性。
- [x] 4.4 为未支持 `std::thread`/RAII、try/timed/robust/recursive mutex、condition variable、semaphore、rwlock、detach/cancel 和自定义封装生成稳定双语 unknown 诊断，确保不误用邻近 pthread 模型。

## 5. 线程句柄与条件化生命周期

- [x] 5.1 实现 create 成功时产生的抽象 handle token 和 API-success guard，测试显式返回零、失败分支、返回值未检查、结果经 phi/select 传播及没有成功证明时不得无条件 spawn。
- [x] 5.2 实现 handle token 的受限精确槽 load/store/copy/cast 传播和 clobber 失效，测试唯一 token、有限多候选、另一次 create 覆盖、未知调用、共享/逃逸槽和候选预算。
- [x] 5.3 实现显式根的 root-start，以及 create-attempt、thread-start、thread-exit 生命周期事件和条件边；测试 main-like 根、多根隔离、无根/非成员根拒绝和跨 TU worker。
- [x] 5.4 实现 join handle 到 ThreadInstance 的有限关联及 join-attempt/join-complete，测试唯一成功 join、多候选、失败/未检查返回、self/detached/重复 join unknown 和 join 不得错误终止 MHP。

## 6. 线程上下文、实例与递归预算

- [x] 6.1 实现由 entry/抽象参数/scope/profile/policy 构成的 `ThreadContext` 模板和缓存键，补充相同/不同入口、参数、profile 和策略的复用/隔离单测。
- [x] 6.2 实现由根、父实例、create invocation/callsite/context/cardinality 构成的 `ThreadInstance`，测试同入口两个调用点、同调用点可区分执行、main/worker 及 invocation/thread identity 不混用。
- [x] 6.3 将 P2 效果和普通函数 invocation 绑定到所属 ThreadInstance，递归重绑定 guard、调用路径和对象归属；测试调用者对象不被重归属、模板命中不泄漏旧实例。
- [x] 6.4 实现循环 create、递归/互递归 SCC 的稳定 fixed-point 与 merged/unknown 实例桶，测试正常收敛、自并行可能性、cardinality 降级和不得把合并桶当作单个动态线程。
- [x] 6.5 执行每请求 4096 context、16384 instance、100000 图节点/边、每候选域 8 项、SCC 16 轮及 worker/请求资源预算，覆盖边界、显式收紧、非空 frontier、partial/failed 和确定性。

## 7. 生命周期顺序与 MHP

- [x] 7.1 实现线程内、跨调用、create/start 和 exit/join 的条件化顺序组合，保留 guard、边强度、端点和证明；单测成功/失败路径、异常出口及证据缺失降级。
- [x] 7.2 实现稳定无向 ThreadInstance pair 和 `may_parallel`/`not_parallel`/`unknown` 推导，测试父线程 create 后继续、worker 间重叠、同入口多实例和不同分析根不混合。
- [x] 7.3 实现成功唯一 join 后的 not-parallel 区间限制，测试 join 前/后事件、多候选/失败 join、合并实例和未知退出不得错误排除 MHP。
- [x] 7.4 为 MHP 关系保存生命周期区间、条件、推导规则和完整性，并增加“可能并行不等于实际调度、冲突或风险”的 schema/report 回归。

## 8. mutex 与原子同步候选

- [x] 8.1 实现同一 ThreadInstance 内普通 mutex 的成功 may-acquire、持有、release 和不平衡状态机，测试返回零、未检查/失败 lock、提前/重复 unlock、路径合流、循环及对象 clobber。
- [x] 8.2 实现规范化同一 mutex 对象上的跨线程 synchronizes-with/mutual-exclusion 候选，测试相同/不同对象、未知 initializer、非普通类型、可能别名和不得用“函数中有锁”保护全部效果。
- [x] 8.3 将 P2 atomic read/write/RMW/CAS/fence 绑定到 ThreadInstance，并按对象/范围、值、order/failure order、syncscope、guard、生命周期和 MHP 构造/排除 reads-from 候选；为各事件类型补单测。
- [x] 8.4 增加 release/acquire 同对象但来源未定、fence、CAS 自旋、release sequence/modification order 未支持反例，断言 P3 不生成确定 synchronizes-with/HB 或风险 findings。

## 9. 缓存、CLI 与报告

- [x] 9.1 实现 P3 派生缓存 key、上下文模板/实例图分离和 P1/P2/worker/模型/scope/profile/root/budget 传递失效，测试 callee-only 变化、模型升级、损坏/未来版本缓存及无关 BC 不重编译。
- [x] 9.2 实现 `model-threads --request --artifact-store --output --worker`，按需复用/生成 P2 摘要并记录精确依赖；测试新空输出目录、非空目录拒绝、无根、非成员根、非法 scope 及不隐式 all-defined/llvm-link/运行应用。
- [x] 9.3 实现 `ThreadAnalysisReport v1` 的 input_integrity、effect_analysis、local_thread_analysis、thread_modeling、synchronization_analysis、source_mapping 状态及根/成员/候选/上下文/实例/frontier 明确分母，覆盖部分成员失败与零分母 null。
- [x] 9.4 实现稳定 code 与 `detail`/`detail_en`、`suggestion`/`suggestion_en` 双语诊断，测试成对缺失、排序/去重、文案变化不影响机器判定和所有 unknown 路径可定位。
- [x] 9.5 实现 0/2/1 退出码、stdout 报告/stderr 日志隔离和失败时小型合法报告，回归旧 collect/index/link/doctor/summarize 行为；所有结果保持 `safety=not_evaluated`、`findings=null`。

## 10. 固定编译与语义验收

- [x] 10.1 增加至少三个物理 TU 的 pthread compile-only C/C++ 夹具，覆盖两个 create 复用同一 entry、不同实例、main/worker 和跨 TU 参数/效果绑定；无需原生链接、llvm-link、SSH 或网络。
- [x] 10.2 增加 create 成功/失败/未检查、handle copy/phi/overwrite/clobber、唯一/多候选/失败 join 和 join 前后访问的固定语义断言。
- [x] 10.3 增加普通静态 mutex 的相同/不同对象、成功/失败 lock、提前 unlock、未知 initializer/类型和未支持同步 API 对照，验证候选、unknown 与完整性状态。
- [x] 10.4 增加 atomic read/write/RMW/CAS/fence、release/acquire 来源未定、scope/范围排除及无确定 HB 的固定断言；P3 不输出风险结论。
- [x] 10.5 增加循环/递归 spawn、未知 callback/间接 API/自定义 wrapper、无 debug、损坏依赖和 budget 截断集成，断言保留图、frontier、双语诊断与正确退出码。
- [x] 10.6 回归 GCC/Clang C11/C17/C++17/C++20 原有 compile-only 矩阵和 P1/P2 质量输入，验证不支持组合不伪装成功且离线无需 ARM DevKit。

## 11. 覆盖率、文档与最终一致性

- [x] 11.1 将所有新增/修改/复用 C++、Python、worker、schema、模型注册、质量脚本和可执行头文件纳入源码/构建/coverage 枚举；测试未加载 Python、未调用 C++、新增子目录和缺失 coverage 文件会使质量入口失败。
- [x] 11.2 维护质量入口及自测，验证整体 hit/total、Python、C++ 和每个受影响模块行/分支均至少 90%，覆盖 89.99%/90% 边界；集成 profile 不混入单元覆盖率，排除项仅限第三方、生成文件和纯夹具并说明理由。
- [x] 11.3 在独立开发容器中使用新的持久输出目录实际运行全部单元、集成与覆盖率入口，记录命令、版本、测试数、整体/语言/逐模块 hit/total 和报告位置；任一测试失败或任一门槛不足均不得勾选，修复后换新目录复验。
- [x] 11.4 编写 `doc/THREAD_AND_SYNC_CONTEXTS.md`，说明协议/CLI/数据流、LLVM 与自研边界、pthread/mutex 支持矩阵、ThreadContext/ThreadInstance、顺序/MHP/候选语义、unknown/预算、双语诊断和无安全结论边界。
- [x] 11.5 编写 `doc/THREAD_AND_SYNC_CONTEXTS_VALIDATION.md`，建立全部 requirement/scenario 到单元/集成断言的映射，记录工具与 libc/target initializer 指纹、输入 hash、预算/确定性、完整性和覆盖报告；更新 README、路线图及 OpenSpec 项目上下文的真实阶段状态。
- [x] 11.6 校验新增文档/OpenSpec 相对链接、kind/schema/analysis/model/预算/退出码/支持边界一致性，运行严格 OpenSpec 校验和文档测试；全部实现及质量任务通过后才提示 sync/archive，并提供下一阶段完整命令。
