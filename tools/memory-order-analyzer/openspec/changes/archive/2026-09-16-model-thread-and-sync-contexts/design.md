## Context

P1 `ModuleFacts v2` 保存原始值、控制流、调用接口、内存事件与定位事实；P2 `LocalAnalysisFacts v1`、`LocalEvaluationResult v1` 和 `EffectSummary v1` 在显式 scope 内补充对象/范围、条件、调用实例、跨 TU 效果与 unknown。它们为线程建模提供必要输入，但不提供线程身份、生命周期、MHP 或可直接用于 HB 的顺序证明。

现有 `EffectSummary.order` 由 P2 局部解释和摘要组合产生，适合保存效果摘要中的已知相对关系，但它没有完整表达 CFG 多路径、循环执行次数及跨调用 entry/exit 边。因此 P3 不能把该字段升格为 `sequenced-before` 或 `happens-before`。P3 必须生成独立证据，并在无法证明时保留 may/unknown。

本项目限定 GCC/Clang 用户态 C/C++、compile-only 和显式分析 scope；`compile_commands.json` 只提供逐 TU 编译上下文，不是链接图或线程图。首版运行环境沿用已锁定的 LLVM 21.1.8 开发容器，离线验收不依赖 SSH、ARM DevKit 或外部服务。当前 P2 已实现、质量验证、同步并归档；OpenSpec 配置中的早期进度描述不作为本 change 的运行时基线。

## Goals / Non-Goals

**Goals:**

- 在保持 P1 v2、P2 v1 原始契约不变的条件下，定义并实现 P3 独立版本化协议和派生产物。
- 从 LLVM API 与已校验 P1/P2 输入生成调用锚点、回调目标、受限线程句柄来源和可审计的线程内顺序证明。
- 建模直接 POSIX pthread 创建、连接和普通非 robust mutex 操作，区分成功、失败和未知路径。
- 区分可复用线程上下文和抽象线程实例，建立生命周期、MHP、mutex 同步候选与原子 reads-from 候选。
- 对递归、循环、未知回调、未知句柄、未知同步对象及预算耗尽执行有限合并和完整性传播。
- 提供显式 CLI、缓存、双语诊断、分层状态和可复现的 90% 行/分支覆盖率质量验收。

**Non-Goals:**

- 不实现 `std::thread`、RAII 锁、try/timed/robust/recursive mutex、condition variable、semaphore、rwlock、线程池或自定义线程/锁模型。
- 不实现通用函数指针/points-to、完整 reads-from、modification order、C/C++ 内存模型求解、风险判定或自动修复。
- 不因成功生成 BC、线程图为空、零 suggestions 或零 findings 宣称程序安全。
- 不合并开发与生产 Dockerfile，不修改 archived 兄弟项目，也不要求原生链接、llvm-link 或运行目标程序。

## Decisions

### D1. P3 使用独立协议和 sidecar，不升级 P1/P2

新增以下 v1 kind，并以 `analysis_version=0.1.0`、`policy=thread-sync-contexts-v1` 协商：

- `ThreadAnalysisRequest`
- `ThreadLocalFacts`
- `ExecutionOrderFacts`
- `ThreadContextGraph`
- `ThreadAnalysisReport`

JSON Schema 放入独立线程分析 schema/协议文件；每个产物保存 kind/schema version、分析版本、策略、scope/profile、LLVM、P1/P2 依赖 digest、实际预算和 canonical identity。P3 引用原始 SourceRef、AnalysisRef、Object/Value、Guard、Effect 和 Invocation，但不向 P1/P2 文件补字段或重写其 hash。

选择独立 sidecar 而不是 `EffectSummary v2`，原因是执行顺序和线程生命周期是新的证明域，且 P2 效果集合仍可独立复用。旧消费者遇到 P3 kind 时明确拒绝，不把缺少 P3 文件解释为“单线程”。

### D2. `model-threads` 以显式根和显式 scope 编排分析

新增拟议 CLI：

```text
python3 -m memory_order_analyzer model-threads --request <request.json> --artifact-store <store> --output <fresh-directory> --worker <worker>
```

请求必须选择非空具体根函数 ID，可包含多个程序/库入口，但不得省略后默认扫描全部定义。CLI 复用或按需生成经过 digest 校验的 P2 摘要，把实际消费的 P2 根、局部事实和依赖闭包登记在 P3 输出中；不会修改或覆盖 P2 产物。输出目录必须为新的空目录，缓存另按内容身份管理。

退出码沿用派生分析约定：0 表示声明范围和策略内 complete；2 表示存在可用图但有 unknown、partial、定位/输入缺口或截断；1 表示请求非法或全部不可用。stdout 只输出最终报告 JSON，日志进入 stderr。

### D3. LLVM worker 只生成局部线程补充与顺序证据

在 C++ worker 增加批处理操作，复用 BC hash、parse/verify、函数归属和输出限制。它使用 LLVM CFG、DominatorTree、PostDominatorTree、LoopInfo、AA/MemorySSA 以及 callback metadata，产生：

- 调用指令的 entry/normal-exit/unwind/no-return anchor；
- pthread 候选调用的精确符号、函数类型、calling convention、参数、返回值及属性证据；
- 直接函数地址及受限 bitcast/select/phi 候选，未知转换保持 unknown；
- create 输出位置、handle load/copy/join 输入的受限 provenance；
- mutex 对象地址、范围、初始化指纹和可能 clobber；
- 独立的局部执行顺序边、循环/重复标记、互斥路径和证明引用。

同基本块指令序号可以产生确定局部先后；跨块的 must-before 必须结合支配、后支配、可达性与 LoopInfo，且排除会改变动态发生次序的重复执行。不能完成该证明时只输出 may-before/unknown。跨调用顺序由调用 anchor、P2 invocation 及正常/异常出口显式组合，不能复用 P2 `order` 充当证明。

没有必要把完整 LLVM 图复制到 Python；worker 输出最小可验证事实及 AnalysisRef。正则解析 `.ll`、源代码行号或遍历顺序不能替代 LLVM API 证据。

### D4. POSIX pthread 模型采用版本化注册表和严格资格检查

`posix-pthread-v1` 模型注册表描述 `pthread_create`、`pthread_join`、`pthread_mutex_lock` 和 `pthread_mutex_unlock` 的符号、参数角色、返回成功条件及语义事件。采用一个调用前必须验证：

- 直接外部符号和支持的 C calling convention；
- 返回/参数数量及已保留的 ABI 信息兼容；
- 调用属于同一 target/profile，且无 interposition/别名冲突证据；
- callback metadata（存在时）与注册表入口/参数位置一致；冲突时拒绝采用；
- 回调目标和 worker 参数绑定属于受支持候选域。

仅有相似函数名、调试名称或 wrapper 名称不触发模型。callback metadata 是辅助证据而非唯一真相；没有 metadata 时可由严格的注册表签名和直接函数地址建模，同时明确记录模型假设。未知包装器、间接 API 调用和不兼容 ABI 保留为 unknown。

### D5. 创建成功条件和线程句柄使用受限 token provenance

每个可采用的 create 调用产生一个抽象 handle token 和条件化 spawn 事件。仅返回值等于零的路径为成功；显式失败路径不创建 worker。返回值未检查时不假定成功，而是保存合成的 API-success guard、may-spawn 与失败可能性。

handle token 可沿精确大小的 load/store、受支持 cast、phi/select 有界传播。create 输出地址到 join 输入的确定关联要求同一规范化对象/范围、唯一候选 token、期间无可能别名 clobber，且线程实例未被另一次 create 覆盖或合并。局部或全局精确槽均可作为候选，但共享/逃逸/重复写会降级。无法唯一关联时 join 保留候选集合或 unknown，不能任选一个线程。

join 只有在句柄唯一/有限关联且返回成功条件成立时，才产生 worker-exit 到 join-normal-successor 的条件化完成边；未知或失败 join 不抑制 MHP。首版不支持 detach、cancel、join-self 及重复 join 的精确语义，这些情况诊断为 partial/unknown。

### D6. 线程上下文与线程实例是两层身份

`ThreadContext` 由 entry function、抽象 worker 参数、scope/profile 和分析策略决定，可复用函数效果与局部线程事实。`ThreadInstance` 由分析根、父线程实例、create 调用实例/位置、上下文及 cardinality 决定；同一入口在两个创建点或同一创建点的两个可区分执行中不得合并为同一实例。

实例 cardinality 为 `single`、`merged` 或 `unknown`。循环、递归 SCC、重复创建和预算合并使用稳定有限桶，保存原因和未展开前沿；合并 ID 不证明同一动态线程，不同 ID 也不能在对象证据不足时证明独立。main/显式根也建成根实例，使主线程访问与 worker 进入统一关系图。

生命周期事件至少包括 root-start、create-attempt、thread-start、thread-exit、join-attempt 和 join-complete，并引用相应调用、guard、线程/调用实例与证据。调用上下文和线程上下文不混用：一个函数 invocation 可以属于某个 ThreadInstance，但二者身份分别保存。

### D7. MHP 由生命周期区间和条件保守推导

对任意两个线程实例输出 `may_parallel`、`not_parallel` 或 `unknown` 关系以及方向无关的稳定 pair identity。不同 root 默认不互相推导；父线程 create 成功之后到成功 join 完成之前与 worker 可能并行。同一 worker 在成功 join 之后与该 join 后的父线程事件不并行，但 join 前、失败/未知 join、合并实例和未知退出保持 may/unknown。

MHP 表示存在重叠执行的可能性，不枚举具体调度，也不等价于冲突或缺陷。线程实例、生命周期或顺序证据不完整时不得输出 `not_parallel`。关系图保存适用 guard、区间端点、推导规则和 unknown 原因。

### D8. mutex 只生成可验证普通锁语义和同步候选

首版 mutex 只接受同一规范化对象/范围、已支持的普通非 robust 初始化指纹和直接 lock/unlock。默认静态 initializer 仅在锁定 libc/target 模型下按版本化指纹识别；无法识别 mutex kind 时保留调用事件，但同步关系为 unknown。

lock 返回零才视为首版成功 acquire；未检查返回值保存 may-acquire guard。unlock 只在当前线程沿支持路径持有同一对象时产生 release 候选；提前 unlock、对象不同、重复/合并路径、未知 clobber 或不平衡状态不得建立确定保护。跨线程 unlock/lock 仅形成带同对象和成功条件的 `synchronizes-with-candidate`/mutual-exclusion 候选，不求解完整全局锁顺序。

这样可以避免把“函数中出现锁”升级为所有访问受保护。robust mutex 的 `EOWNERDEAD`、recursive/errorcheck、try/timed lock 和 `pthread_mutex_init` 属性推导均不在首版支持范围。

### D9. 原子操作只构造 reads-from 候选，不建立确定 HB

复用 P2 原子 read/write/RMW/CAS/fence 的对象、范围、值、success/failure order、syncscope、guard、occurrence 和线程归属。写与读只有在对象/范围可能重叠、生命周期/MHP 未排除、值域和 scope 未证明不兼容时才进入 reads-from 候选；候选保留 release/acquire 等 order 资格及排除原因。

P3 不求解 modification order，不从相同对象上的 release/acquire 共存直接生成确定 synchronizes-with/HB，也不把 fence 或 CAS 自旋协议解释成完整发布。P4 必须在读取来源、控制依赖、payload 效果和适用模式均满足时才能使用这些候选进行风险判定。

### D10. 完整性、缓存和预算优先于空图便利性

报告分层保存 `input_integrity`、`effect_analysis`、`local_thread_analysis`、`thread_modeling`、`synchronization_analysis` 和 `source_mapping` 状态，均使用 complete/partial/failed/not_run。报告同时保存根计划、scope 成员、调用候选、线程上下文/实例、生命周期、MHP、同步/reads-from 候选、unknown 前沿及明确分母。零分母为 null，不通过过滤失败项显示 100%。

P3 缓存 key 包含全部 P1/P2 digest、scope/profile/boundary、LLVM/worker、线程模型版本、根/绑定、实际预算和依赖图；任一依赖变化传递失效。模板线程上下文与实例化图使用不同 key，缓存命中重新绑定实例。损坏、未来版本、跨 profile 或引用悬空的缓存拒绝，不覆盖历史文件。

`thread-sync-contexts-v1` 初始确定性预算为：每请求最多 4096 个线程上下文、16384 个线程实例/合并桶、100000 个生命周期/顺序/MHP/同步节点与边、每个回调或句柄域 8 个候选、每个递归 SCC 16 轮；局部 worker 每批 60 秒/16 MiB 输出，请求总计 300 秒/64 MiB 派生产物。请求可显式收紧，生效预算进入身份。任何超限保留已有结果、非空 frontier 和 partial/failed，不能输出空图冒充 complete。

所有诊断保存稳定 `code`、中文 `detail`、英文 `detail_en`；存在可操作建议时同时保存 `suggestion` 和 `suggestion_en`。缺少任一语言字段或把翻译文本用于机器判定均为契约错误。

### D11. 模块拆分与现有工具边界

C++ 自研部分负责 `thread_metadata`、`execution_order`、`handle_provenance` 及 worker 操作；Python 自研部分负责协议校验、pthread 模型采用、线程实例调度、生命周期、MHP、mutex/atomic 候选、缓存、报告和 CLI。复用既有 scope/输入、P2 scheduler/summary、contracts、canonical JSON、OutputStore、DerivedCache 和质量入口。

LLVM callback metadata、DT/PDT、LoopInfo、AA/MemorySSA 只作为局部事实来源。ThreadSanitizer 是动态执行检测，不能替代静态候选图；SVF/PhASAR/GenMC 等外部后端不成为 P3 依赖，留待 P5 以独立实验决定。

### D12. 测试、文档和可观察验收

每个新增或修改的 C++/Python 模块必须有正常、边界、失败和 unknown 单元测试。特别增加负向回归，证明 P2 `EffectSummary.order` 即使存在也不能独立生成 P3 must-before/HB；分支、循环和跨调用顺序必须来自新的 ExecutionOrderFacts。

固定离线集成输入至少覆盖：两个 create 使用同一入口但实例不同；main/worker 重叠；create 失败和返回未检查；join 前后访问；handle copy/overwrite/unknown；相同/不同 mutex；lock 失败、提前 unlock 和未识别 initializer；递归/循环创建合并；未知 callback/间接 API/自定义 wrapper；原子候选；三个物理 TU、无 debug 及损坏依赖。

质量入口统计所有项目自有可执行源码，包括未被测试加载的 Python、未调用的 C++ 和可执行头文件；整体、每语言和所有受影响模块行/分支均至少 90%。集成测试独立通过但不计作单元测试替代品。第三方、生成文件和纯测试夹具可以排除，但必须列出理由。

实施阶段新增 `doc/THREAD_AND_SYNC_CONTEXTS.md` 和 `doc/THREAD_AND_SYNC_CONTEXTS_VALIDATION.md`，更新 README、路线图以及 P1/P2 文档中的阶段边界。验证文档记录精确命令、工具/库版本和 hash、场景到测试映射、完整性/预算结果、覆盖 hit/total 与报告位置；只有实际实现与质量门槛全部通过才标记 P3 完成。

## Risks / Trade-offs

- [把静态 IR 顺序误当作动态执行顺序] → 使用独立 ExecutionOrderFacts、循环/多路径限制和 must/may/unknown 分层；禁止消费 P2 `order` 作为充分证明。
- [函数名模型误识别自定义 API 或被 interpose 的符号] → 版本化注册表、ABI/profile/边界复核和 callback metadata 一致性检查；不合格调用保持 unknown。
- [句柄在内存中的复制与覆盖导致 join 关联错误] → 有界 token provenance、精确对象/范围和 clobber 检查；多候选不任选线程。
- [忽略返回码错误地假定 create/join/lock 成功] → 无论源码是否检查都保留 API-success guard；失败/未知分支不生成无条件生命周期或同步边。
- [mutex 类型和 libc 表示依赖平台] → 仅对锁定 profile 的普通静态 initializer 指纹提升精度，其他类型/初始化退为 unknown，不宣称跨 libc 通用。
- [线程实例、MHP 和候选边组合爆炸] → 稳定上下文复用、有限候选、SCC 合并、结构预算及非空 unknown 前沿。
- [过度保守使 P4 缺少可用关系] → 用固定 pthread 物理 TU 正例锁定首版精度，但不以弱化完整性或引入名称启发式换取通过。
- [双语文本与机器语义漂移] → 机器逻辑只消费稳定 code/enum，schema 强制成对文本字段并测试缺失/错配。

## Migration Plan

1. 冻结 P1/P2 黄金输入和兼容性断言，新增 P3 schema、协议握手和拒绝旧/未来版本测试。
2. 增加 LLVM 局部线程事实和独立执行顺序 sidecar，不修改现有 BC、ModuleFacts、LocalAnalysisFacts 或 EffectSummary。
3. 接入 pthread 模型、句柄 token、线程上下文/实例、生命周期和 MHP，再增加 mutex/atomic 候选。
4. 接入派生缓存、`model-threads` CLI 和分层报告，使用新输出目录运行全部单元、集成与覆盖率验收。
5. 完成文档、严格 OpenSpec 校验和质量报告后才允许同步/归档。

回退时停用 P3 命令和新 kind 消费即可；P1/P2 产物、旧命令、缓存和历史报告不删除、不迁移。P3 输出不被旧命令隐式读取，因此不存在破坏式数据迁移。

## Open Questions

本 change 没有阻塞实施的开放决策。首版统一采用“返回值未检查即条件化 may-success”、严格 `posix-pthread-v1` 和普通静态 mutex initializer 指纹；是否增加 `pthread_mutex_init`、`std::thread`、RAII、更多同步原语或外部 points-to/backend，均根据 P3 验证数据另起 change，不在实施中暗中扩展。
