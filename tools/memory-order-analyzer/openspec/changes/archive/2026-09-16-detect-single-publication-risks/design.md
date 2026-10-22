## Context

P1 `ModuleFacts v2` 保存值图、CFG、内存事件、原子 order、初始化器和源码位置；P2 `EffectSummary v1` 在显式 scope 内补充对象/范围、调用实例、guard、效果和值；P3 `ThreadContextGraph v1` 将效果绑定到 `ThreadInstance`，生成独立执行顺序、MHP、mutex 和 atomic reads-from 候选。P3 有意不求解 reads-from、synchronizes-with 或 happens-before，且其报告始终保持 `safety=not_evaluated`、`findings=null`。

P4 要识别的证明链为 `W(payload) → S(flag) → L(flag) → R(payload)`。其中 P2 对共享/atomic load 的结果保守为 unknown，P3 的 guard 只保存身份，循环中的 load 也可能因重复执行而只有 may-before。因此不能靠筛选现有图中同对象的 release/acquire 得出结论，必须新增局部“观察结果如何选择成功控制边”的证明，以及代表成功动态观察的独立分析节点。

输入继续限定 GCC/Clang 用户态 C/C++、compile-only、显式 scope 和直接 POSIX pthread 模型。`compile_commands.json` 仍只描述逐 TU 编译上下文；最终目标成员和边界来自 scope。现有 `doc/experiments/publication.cpp` 使用 `std::thread`，适合核对 IR 表达但不满足 P3 线程模型，因此 P4 端到端真值需使用新的直接 pthread C/C++ 固定输入。

## Goals / Non-Goals

**Goals:**

- 保持 P1 v2、P2 v1、P3 v1 原始文件、身份、缓存和报告语义逐字节不变，增加独立 P4 v1 sidecar、协议图和报告。
- 对精确的一次发布、唯一发布写者和可识别成功 gate，建立候选级、条件化且可审计的 reads-from 唯一化与发布证明链。
- 区分 ordinary data race、跨对象 publication ordering 风险、受限模式内消解和 unknown/unsupported，保存线程、对象、事件、路径、缺失边和假设。
- 支持 C11/C17/C++17/C++20、直接 pthread、有限 compare/cast/return wrapper、单 TU/跨 TU 和无 debug IR 证据。
- 提供严格 schema、跨层引用校验、确定性身份、资源预算、传递缓存、双语诊断、明确分母和可用于 CI 的退出码。
- 为全部新增、修改和复用的自有逻辑提供正常、边界、异常及 unknown 单元测试，并实际执行整体、语言和受影响模块行/分支至少 90% 的质量门槛。

**Non-Goals:**

- 不实现完整 C/C++ 内存模型、通用 reads-from/modification-order 求解器或通用 data-race 检测器。
- 不支持 `std::thread`/RAII、condition variable、semaphore、rwlock、线程池、自定义同步、try/timed/robust/recursive mutex。
- 不解释 consume、fence 协议、RMW/CAS release sequence、自旋锁、多写者、重复发布、ABA、对象回收或通用 points-to。
- 不从名称、源码邻近、成功生成 BC、DevKit 零建议或零 P4 finding 推导安全；不自动修改源码或统一升级为 seq_cst。
- 不合并开发与生产 Dockerfile，不引入 DevKit、SSH、SVF、PhASAR、GenMC 或网络作为 P4 运行依赖。

## Decisions

### D1. P4 使用独立 v1 协议和 sidecar，不升级 P1/P2/P3

新增 `PublicationRiskRequest v1`、`PublicationLocalFacts v1`、`SinglePublicationProtocolGraph v1` 和 `PublicationRiskReport v1`，初始 `analysis_version=0.1.0`、`policy_id=single-publication-risks-v1`、`model_id=c-cpp-single-publication-v1`。P4 引用 P1/P2/P3 digest、SourceRef、AnalysisRef、Effect、Invocation 和 ThreadInstance，不向旧产物附加字段。

选择独立 sidecar 而不是升级 `ThreadContextGraph`，因为“成功观察”、谓词约束和风险 verdict 是新的证明域；P3 宽松候选仍可供其他规则复用。旧消费者遇到 P4 kind 必须拒绝，缺少 P4 产物不能解释为已扫描。

### D2. CLI 显式复用 P3 请求并在同一次运行中绑定精确依赖

新增拟议命令：

```text
memory-order-analyzer detect-publication-risks \
  --request <PublicationRiskRequest.json> \
  --artifact-store <store> \
  --output <new-empty-directory> \
  --worker <moa-worker>
```

`PublicationRiskRequest` 引用一份完整 `ThreadAnalysisRequest`；路径相对风险请求解析，实际文件内容和 digest 纳入 request identity。编排层通过现有 P2/P3 内容缓存生成或复用精确线程图，并把实际消费的 thread request、P1/P2/P3 产物和局部 sidecar 登记为依赖。不能从目录选择“最新图”，不能省略根后扫描全部定义，也不能隐式 llvm-link、原生链接或运行被分析程序。输出目录必须全新，历史输出不覆盖。

### D3. LLVM worker 生成最小、独立的发布局部事实

每个 scope 成员从只读且 hash/parse/verify 校验的 BC 生成 `PublicationLocalFacts`，至少包含：

- 对可解析 flag 访问范围的静态/常量初始化值及 DataLayout 证明；
- atomic/plain read 的原始事件、结果位宽、对象范围和 syncscope；
- 从 read 到有限 `icmp`、布尔反转、整数等宽/安全窄化 cast、phi/select、直接 return 和 caller 结果的值依赖；
- branch/switch 成功谓词、成功/失败边、循环重试形态、边支配和被成功边控制的消费区域；
- wrapper 的返回依赖接口、原始 SourceRef、LLVM 分析生成的 AnalysisRef、输入证明和 unknown frontier。

首版谓词域限定精确整数 `eq`、`ne`、zero/nonzero 和有限布尔反转；可能改变比较含义的算术、未知 cast、内存暂存、间接调用和候选爆炸降级。MemorySSA/AA 可以用于局部 clobber 排除，但不能被当作跨线程 HB。

直接使用 P1 JSON 在 Python 中重写支配和循环分析的替代方案被拒绝：P1 值图适合引用和校验，但边支配、循环动态发生次序、initializer 字节切片及 wrapper 证据更适合由同版本 LLVM API 生成。

### D4. 成功观察是独立分析实例，不等同于原始 load 节点

对通过成功 gate 的动态读取建立 `SuccessfulObservation` 分析节点，其身份包含原始 read、invocation、ThreadInstance、谓词、成功边和策略。原始 read 仍保持 repeated/may 语义；成功观察只表示“若沿该成功边到达消费，则本次观察满足谓词”，不表示运行时一定发生或读取来源已经确定。

该分离使轮询中的重复 load 可以和退出后的 payload read 建立条件化顺序，又不会把静态 load 误称为只执行一次。跨调用 wrapper 只能沿 P2 已采用的确定直接调用和 P4 return dependency 组合；多候选、递归未收敛或间接 wrapper 保持 unknown。

### D5. 候选发现使用对象、值流和控制流，不使用名称启发式

协议候选由以下元素组成：publisher/consumer ThreadInstance、payload 写/读、flag 发布写/观察读、成功观察、精确对象范围、谓词、路径 guard、执行顺序和 MHP。`ready`、`signal` 或函数名称均不参与判定。

候选要求 payload 写与读范围重叠、flag 写与读范围重叠、线程可能并行、成功观察控制 payload 使用，并有可审计的同线程顺序。不同 flag、不同 payload、join 已证明不并行、单线程或成功边不控制 payload 的组合被排除而非报风险。MHP unknown、对象可能别名或顺序仅 may 时保留 unknown。

### D6. 受限 reads-from 唯一化使用值排除而非候选共存

`S(flag) → SuccessfulObservation` 只有在以下条件同时成立时才能从 candidate 提升为受限模式的唯一读取来源：

1. flag 初值精确且被成功谓词拒绝；
2. 发布写值精确且被成功谓词接受；
3. 相关 closed scope 和实例内不存在另一个可接受值写、重复发布、RMW/CAS、unknown clobber 或外部边界；
4. 写/读范围、位宽和 system syncscope 兼容；
5. 线程关系和 gate 证据完整，相关预算未截断。

该推导只对当前受限候选成立，不向 P3 写入通用 reads-from 或 modification order。初值与发布值相同、谓词接受多个不可区分写、开放 scope、多写者、ABA、release sequence 或相关 unknown 调用均阻止唯一化。

### D7. 发布证明链按语言语义资格逐边建立

受限模式中的完整同步链要求：

- payload 写 must-before flag 发布写；
- flag store 为 `release` 或 `seq_cst`；
- 成功 flag load 为 `acquire` 或 `seq_cst`；
- store/load 均为 compatible system scope；
- D6 已唯一化该 reads-from；
- 成功观察必须在 payload 使用之前并控制该使用。

满足时只把该候选记为 `discharged-within-single-publication-model`。`monotonic` 解释为 relaxed；`unordered`、consume、非法操作/order 组合和 `singlethread` scope 不参与跨线程证明。RMW/CAS 即使带 acq_rel 也超出首版。

P2 `EffectSummary.order`、P3 原子候选共存、相邻源码位置或硬件上相同指令都不能独立补足上述任一边。

### D8. 风险规则区分 data race 与 publication ordering

每个协议候选可以产生一项或多项通过同一 `protocol_id` 分组的 assessment：

- flag 或 payload 为普通冲突访问、线程可能并行且没有完整 HB 时，产生 `potential-data-race`；该规则只覆盖已识别的一次发布协议，不扩展为全程序 race 扫描。
- flag 为 atomic，但发布 store 缺少 release、成功 load 缺少 acquire，或 acquire 发生在 payload 使用之后，产生 `publication-order-risk`。
- 如果能证明发布 store must-before payload 写，则产生 `publication-order-risk`，原因为 `publication-store-too-early`；仅仅无法证明 payload 写在前时必须 unknown，不能把缺证据当错误。
- payload 全部为 atomic relaxed 时不产生 ordinary data race，但缺少发布链仍产生 `publication-order-risk`。
- 普通 flag 的协议首先报告 flag 冲突 data race；不得假设一个具有未定义行为的普通轮询已形成有效读取来源。

严重性与证据置信度分离。相关同步、边界或 alias 缺口污染候选证明切片时结果为 unknown；与该候选无关的其他 TU 缺口可以使全局报告 partial，但不得抹去已有局部 finding。unknown 同步不能用来抑制 finding，也不能被假设不存在；此时 finding 必须标记条件和限制，不能声称已确认漏洞。

### D9. 完整性状态与安全 verdict 永远分离

报告至少保存 input、P1、P2、P3、publication-local、candidate-modeling、risk-evaluation 和 source-mapping 状态；保存计划成员、根、局部事实、协议候选、已评估、finding、discharged、unknown、unsupported 和未处理项的 hit/total。零分母为 null。

顶层 `safety` 固定为 `not_established`；`verdict` 仅允许 `risks_found`、`no_supported_risk_found`、`inconclusive` 或 `failed`。完整且零候选只能得到 `no_supported_risk_found`，不能显示“程序安全”。每项 finding 保存规则/模型版本、语言 profile、编译配置、线程/对象/事件、路径、已有与缺失同步、源码或 IR 位置、假设、证据等级及中英文说明/建议。

### D10. 风险命令使用独立的 0/3/2/1 退出语义

- `0`：全部计划分析完整，且没有受支持模式内 finding；
- `3`：全部计划分析完整，且至少一个 finding；
- `2`：有可用结果但存在 partial、unknown、unsupported 或定位缺口，无论是否同时有 finding；
- `1`：请求非法、结构/身份校验失败、全部不可用或无法继续。

JSON 报告是 finding 与完整性的权威来源。该语义只属于新命令，不改变 collect/index/link/summarize/model-threads 的既有退出码。

### D11. 语言 profile 和构建身份必须可追溯

每个候选登记 artifact/profile、原编译记录、分析 BC producer、target/layout、C/C++ 语言及标准。显式 `-std` 可直接采用；缺少可验证标准或跨 C/C++ 原子互操作证据时，相应语义降级，不能按当前编译器默认值静默猜测。source-preserving 与 build-faithful 结果不拼接成同一证明。

首版允许同一 scope 含多个 TU，但一个候选的原子协议必须落在兼容语言模型和 ABI 边界内。跨 TU wrapper 仍要求 closed scope、确定定义、接口和 P2/P3 invocation 绑定全部有效。

### D12. 缓存按完整传递依赖和实际预算隔离

P4 缓存 key 包含 BC/P1/P2/P3 digest、thread request、scope/profile/boundary、语言模型、LLVM/worker、P4 policy/model、实际预算、局部事实和全部候选证明依赖。局部事实、协议模板和线程实例化候选使用不同身份；命中模板时重新绑定 ThreadInstance、invocation、guard 和成功观察。

损坏、未来版本、跨 profile、依赖陈旧、引用悬空或展示字段不成对的缓存拒绝，不覆盖历史文件。P4 策略变化只重算派生结果，不重编译未变 BC、不修改 P1 ArtifactKey 或 P2/P3 历史身份。

### D13. 预算保留前沿而不是截断成零风险

初始确定性上限沿用现有量级：每 TU 最多 100000 个局部分析节点、每值/谓词最多 8 个候选、每请求最多 10000 个协议候选及 10000 个 assessment、跨 wrapper/SCC 最多 16 轮；worker 每批 60 秒/16 MiB，P4 请求 300 秒/64 MiB。最终字段名和精确 schema 由实现锁定，但任何请求可显式收紧，生效预算必须进入身份。

达到预算时保存已生成候选、未处理 frontier、实际计数和 partial；不得发布结构不完整 JSON、删除超限计划项或把截断后的零 finding 当作通过。

### D14. 固定语义矩阵独立于 DevKit 和单元覆盖率

新增直接 pthread 的 C11/C17 与 C++17/C++20 单 TU/物理跨 TU 输入，固定覆盖：普通 flag、relaxed+普通 payload、release/acquire、seq_cst、fence unsupported、过晚 acquire、改名 flag、all-atomic relaxed、发布过早、不同 flag、多写者、重复发布、相同初值/发布值、单线程、join 后访问、unknown call、无 debug、开放 scope及 wrapper 可解析/不可解析。

CASE0–CASE7 的语义期望来自语言模型和人工审核，不来自 DevKit 建议数。原 `std::thread` 样例保留为 IR 对照，不偷偷扩展 P3 API 支持。单元覆盖和语义集成分别报告；全部自有 C++/Python/脚本逻辑纳入未加载源码枚举，整体、语言和每个受影响模块行/分支至少 90%。

## Risks / Trade-offs

- [受限模式被误解为完整安全证明] → 顶层 safety 固定 `not_established`，结果命名为模式内 finding/discharged，零候选和零 finding 明确区分。
- [静态 reads-from 唯一化过强] → 同时要求初值排除、发布值接受、唯一写者、无重复/RMW/CAS/clobber、closed scope 和完整 gate；任一缺失降级。
- [轮询重复节点导致伪 must-before] → 原始 load 保持 repeated/may，新建条件化成功观察实例并绑定成功边，不修改 P3 order。
- [跨 TU wrapper 丢失观察依赖] → 使用独立 return dependency 与 P2/P3 invocation 组合；间接、多候选和递归超限保持 unknown。
- [未知同步造成误报或错误抑制] → 对候选证明切片传播 unknown，finding 保留明确条件/证据等级；未知既不当同步也不当不存在。
- [优化删除源码事件] → 记录 profile/优化/producer；无相应 IR 证据时报告限制，不把 O0/O2 指令拼为同一路径。
- [普通 flag 的 UB 被误当作发布通信] → 首先分类 data race，不为普通 flag 构造 synchronizes-with 或安全消解。
- [候选组合爆炸] → 先按线程根、MHP、对象范围、gate 和值域剪枝，再应用确定性候选/SCC/输出预算并保留 frontier。
- [退出 3 与旧命令冲突] → 只在新命令启用，partial 优先返回 2；报告字段而非单一进程码承载全部状态。

## Migration Plan

1. 冻结 P1/P2/P3 黄金输入与命令回归，新增 P4 schema、worker 协商和拒绝旧/未来版本测试。
2. 实现并校验 `PublicationLocalFacts`，先覆盖初值、直接 atomic/plain observation、谓词和成功 edge，再加入确定 direct-return wrapper 组合。
3. 实现协议候选、成功观察实例、受限 reads-from、风险规则和候选级完整性；所有中间产物先通过引用闭包校验再缓存。
4. 接入 CLI、分层报告、退出码和固定 pthread 矩阵，使用新的持久输出目录执行全部单元、集成及覆盖率验收。
5. 更新 P4 实现/验证文档、README 和路线图；只有任务与质量门槛全部完成后才同步并归档。

回退时停用 P4 worker 操作和新命令即可；P1/P2/P3 文件、命令、缓存和历史报告均不迁移、不删除。P4 输出是独立派生物，不被旧命令隐式读取。

## Open Questions

- 无阻塞性产品问题。实现时需以实际编译记录验证未显式给出 `-std` 的语言标准；无法可靠确定时按本设计降级，而不是新增默认猜测。
- fence、RMW/CAS、`std::thread` 和通用 race 扩展必须依据 P4 实测结果另开 change，不能在本 change 中顺带扩大范围。
