## Context

R1 `RootDrivenAnalysisPlan v1` 已把分析范围从“scope 内所有事实”收敛为由 `ExecutionRoot` 驱动的 reachable function/context/TU demand；R1.1 `ThreadEntryRootOverlay v1` 又补齐 canonical AST type/constructor、C11 `thrd_create`、`std::jthread`、`std::async` 和调用点级 root overlay。P2 `EffectSummary v1` 保存参数化内存 effect，P3 `ThreadContextGraph v1` 保存 pthread 实例、生命周期和局部 MHP，A3 保存经 profile 验证的 C++ 线程生命周期，A4 保存受限 mutex/RAII held-region，A5 保存 must/may/unknown 对象 provenance。现阶段缺少的不是更多 load/store 扫描，而是一个稳定层将上述事实投影到同一执行实例与对象空间，再形成可审计的并发访问候选。

现有产物不能直接拼接：R1 为每个 root 生成独立 P3 请求，而 P3 的 MHP 关系只在同一 `root_id` 内比较；A3 的部分生命周期关系使用自身根身份，尚未统一到 R1 root；R1.1 能发现 `std::jthread`/`std::async`，但没有完整生命周期图；A4 当前只有在访问、owner、held-region 和 mutex provenance 全部闭合时才足以证明受限保护；A5 的 must/may/unknown 候选也不能退化为字符串 `object_key` 比较。若直接对所有 effect 做全局二次配对，不仅复杂度不可控，还会把未知地址和不相关 roots 制造成大量伪候选。

本 change 因此实现 R2 sidecar。它消费既有版本化产物，不升级 P1–P4、A1–A5、R1 或 R1.1；输入限定 GCC/Clang 用户态 C11、C17、C++17、C++20，Windows、MSVC 和 clang-cl 排除。`compile_commands.json` 仍只提供 TU 编译配置，scope/linkage/call/thread 关系必须来自显式 scope 与版本化证据。R2 只回答“哪些访问对值得后续并发风险消费者检查，以及为什么无法判断其他对”，不回答是否构成 data race、是否存在 happens-before 或程序是否安全。

目标数据流为：

```text
RootDrivenAnalysisPlan v1 + ThreadEntryRootOverlay v1
                         │
              reachable demand denominator
                         │
      P2 effects + optional R2 local projection facts
                         │
              access instances and byte ranges
                         │
 P3 pthread + A3 lifecycle + R1.1 entry semantics
                         │
              ExecutionInstanceBindingOverlay v1
                         │
       A5 object candidates ── A4 held-region proofs
                         │               │
                  bucketed pairing       │
                         ├───────────────┘
                         ▼
          ConcurrentAccessCandidateGraph v1
                         ▼
          ConcurrentAccessCandidateReport v1
          safety=not_evaluated, findings=null
```

## Goals / Non-Goals

**Goals:**

- 新增内容寻址、版本化且与旧协议隔离的 R2 请求、局部投影、实例绑定、保护 overlay、候选图和双语报告。
- 只在 R1/R1.1 可达需求切片内实例化 P2 memory effects，并以可追溯引用绑定线程实例、对象候选、字节范围、guard、调用上下文和证据完整性。
- 在 scope 级统一不同 root、pthread、`thrd_create`、`std::thread`、`std::jthread` 和显式 async 的执行实例身份与可能并行关系。
- 对 must/may overlap、write/read 类别、single/merged/repeated cardinality 和受限 mutex 保护给出确定、可测试的候选、排除、保护或 frontier 语义。
- 通过多维分桶、显式预算、缓存和候选相关完整性，避免全局笛卡尔积并使规模行为可审计。
- 为 C11、C17、C++17、C++20 分别建立人工 truth、单元测试和至少 90% 的项目整体、实现语言及逐受影响模块行/分支覆盖率门禁。

**Non-Goals:**

- 不实现通用 data-race、通用 happens-before/synchronizes-with 求解、可执行调度枚举或全程序安全证明。
- 不改变 P4 风险规则、finding/discharged 语义或风险退出码，也不把 R2 candidate 直接发布为 P4 finding。
- 不实现 A6 fence、RMW/CAS release sequence、通用原子 modification order 或 lock-free 算法语义；RMW/CAS 只作为冲突访问类别保留。
- 不实现 R3 按函数/上下文懒提取，不重写 P1 全量事实采集，也不从不可达函数创建候选。
- 不支持线程池、executor、自定义异步框架自动识别、通用函数指针、虚调用、通用 points-to 或未知同步的乐观消解。
- 不从函数名、类型名、源码词法作用域、`EffectSummary.order`、P3 reads-from candidate 或调试行号单独推导并行、互斥、SW/HB 或安全结论。

## Decisions

### 1. R2 使用加法式 sidecar，并冻结所有上游协议

新增六类公开产物：

- `ConcurrentAccessCandidateRequest v1`：显式引用 scope、R1 plan、R1.1 overlay、P2/P3/A3/A4/A5 产物、模型、预算和可选 worker。
- `ConcurrentAccessProjectionFacts v1`：仅补充 R2 必需但旧事实无法无损表达的访问局部投影；保存原始 effect/event/value 引用，不复制整个 IR 图。
- `ExecutionInstanceBindingOverlay v1`：把 root/context/invocation/create site 与 single/merged/repeated thread instance 关联，并保存 MHP disposition。
- `AccessProtectionOverlay v1`：把具体 access instance 与 held-region、mutex instance、owner 和证据闭包关联。
- `ConcurrentAccessCandidateGraph v1`：保存 access、instance、object domain、候选 pair、显式 exclusion、protection、atomic handoff 与 frontier。
- `ConcurrentAccessCandidateReport v1`：保存分母、完整性、预算、缓存、双语诊断和退出语义。

选择独立 sidecar 而不是升级 `EffectSummary v1` 或 `ThreadContextGraph v1`，是因为实例化访问对、跨 root MHP 和对象配对有独立分母、预算及失效条件；升级上游协议会使 P4 和历史缓存被迫迁移。若旧事实已足够，`ConcurrentAccessProjectionFacts` 可以是合法的空补充产物，但请求仍记录其 producer/schema identity；若实现审计发现必须修改冻结协议，应先修订本 change，不得隐式加字段。

### 2. 分母以 root demand 为主，入口 overlay 只做确定扩展

R2 先验证 `RootDrivenAnalysisPlan` 与 `ThreadEntryRootOverlay` 的 scope、profile、target、DataLayout、source/BC lineage 和 dependency digest。分析分母是 base plan demanded contexts 与 overlay adopted roots 的规范化并集；相同 physical creation site、model 和 callback identity 去重，不按 callable 名称合并。`source-candidate`、conditional、ambiguous、unsupported 或 failed 入口不生成正式执行实例，但必须进入候选相关 frontier。

每个访问只从 demanded function/context 的 P2 effect 或受支持局部投影实例化。observed-but-not-demanded 事实可以计数审计，但不能参与候选。该选择避免再次从所有 BC load/store 反向猜测线程入口；代价是 root/overlay 不完整会使相关候选分母 partial，而不是自动扩大到全定义扫描。

### 3. AccessInstance 与原始 effect、IR 节点和线程实例分离

`AccessInstance` 身份至少包含 scope/profile、root、reachable context、function invocation、P2 effect 或 R2 projection 引用、执行实例 binding、operation kind、atomicity、guard、对象候选域、半开字节范围和实例 cardinality。原始 IR instruction 或 AST expression 是证据节点，不是动态访问实例；同一 effect 在两个创建点或两个调用上下文必须形成不同 access instances，同一动态访问经多个证据路径观察则按 canonical identity 去重。

operation kind 规范化为 read、write、rmw、cas-success、cas-failure 或 unknown；RMW/CAS 同时含读写冲突面，但 R2 不解释其原子同步语义。volatile、atomic、普通访问属性保留，不能仅凭 atomic 排除配对。guard 以合取/析取引用表达；不可证明的路径可行性保留 may，不任选某条路径。

### 4. 建立 scope 级 ExecutionInstanceBindingOverlay，修复跨 root 空洞

overlay 不复用 P3 “相同 root 才比较”的局部假设，而是在同一显式 scope 下构造 execution family。身份层级严格分开：

1. `ExecutionRoot`：外部/main/library/framework 或创建点派生分析根；
2. `ThreadContext`：可复用 callback/callable 与抽象参数上下文；
3. `ThreadInstance`：父实例、创建点、guard、handle/object lineage 和 cardinality；
4. `Invocation`：在线程实例内执行的普通函数调用。

P3 pthread 实例通过创建点/callback/handle 证据采用；`thrd_create` 通过 R1.1 exact site 与 C API profile 补充实例语义，不伪装为 pthread；A3 提供已验证 `std::thread` 构造/join/detach/move；R1.1 exact `std::jthread` 和显式 `std::async` 可建立候选执行实例，但缺少完整 join/future 生命周期时只发布能够证明的 may-parallel 区间。`launch::deferred` 明确不生成并发实例；默认或 async|deferred policy 产生 conditional frontier，不建立正式 MHP pair。

MHP disposition 为 `parallel-possible`、`not-parallel` 或 `unknown`，并附 proof/limitation。只有 `parallel-possible` 进入候选配对；`not-parallel` 形成显式 exclusion；`unknown` 形成 frontier。不同 root 没有 P3 关系不是 `not-parallel` 证明。`single` 同一具体实例与自身排除；`merged`/`repeated` 同一抽象桶代表多个潜在动态实例，必须保留 self-concurrency pair 和 cardinality 限制。

### 5. 对象配对消费 A5 lattice，不比较显示字符串

每个 access 的对象域来自 A5 `must` singleton、有限 `may` candidates 或带原因的 `unknown`，并保留 storage instance、subobject path、union overlap group、byte range、guard 和 dependency slice。对象 overlap disposition 为：

- `must-overlap`：同一 exact storage 且范围确定相交，或 union overlap 规则要求相交；
- `may-overlap`：有限候选至少有一组可能相交，但不能唯一化；
- `must-disjoint`：同一可比较 storage/layout 下的范围被证明不相交，或其他受支持 no-overlap proof 完整；
- `unknown`：对象、layout、范围、lifetime、clobber、scope 或预算不足。

must/may overlap 都可生成候选，并保留证据等级；must-disjoint 形成排除；unknown 形成聚合 frontier。不同对象的同名字段、相同 `FieldDecl`、类型不兼容、AA 的局部 `NoAlias` 或不同字符串 key 均不能单独建立跨实例 disjoint。AST-only 只提供 source candidate/path，不建立运行时 alias/noalias。

### 6. 候选条件是 MHP、overlap 与冲突访问类别的交集

候选 pair 必须同时满足：

1. 两个 access 均在 demanded 可达切片且绑定受支持执行实例；
2. MHP 为 `parallel-possible`；
3. object/range 为 must-overlap 或 may-overlap；
4. 至少一侧为 write、rmw 或 cas；
5. 未因同一 single instance、read/read 或其他已证明规则排除。

pair 使用规范化无向 identity 去重，但保存左右角色、root/context/instance、guard、访问顺序证据和全部 provenance。显式 exclusion 至少区分 `same-single-instance`、`proven-not-parallel`、`read-read`、`must-disjoint`、`deferred-execution`；排除是 R2 局部配对结论，不是全程序安全结论。对象/MHP 未知不能伪装为 exclusion，也不能用全局 unknown 地址与所有 access 做笛卡尔积；它们进入按 root/context/object-domain 聚合的 frontier。

### 7. 受限保护必须通过独立 AccessProtectionOverlay 闭合

A4 的函数或类型级 mutex 事实不能直接抑制候选。只有以下条件全部满足时，pair 才可标记 `protected-within-bounded-model`：

- 双方具体 access instance 唯一绑定各自执行实例与控制区间；
- A4 held-region 证明 access 位于成功 acquire 与对应 release/RAII destruction 之间，异常路径亦被覆盖；
- 双方 mutex provenance 归一化到同一 exact `MutexInstance`，且对象 lifetime/profile/ABI 一致；
- mutex 为首版支持的普通、非 robust、非 recursive 类型，lock/unlock 成功条件和 owner 证据完整；
- MHP、guard、依赖切片和预算均完整，无相关 opposed evidence。

不满足时保留 unprotected candidate 或 `protection-unknown` frontier，不能把“函数中存在锁”“词法作用域内有 lock_guard”“P3 mutex candidate”或相同字段名当作保护证明。`protected-within-bounded-model` 仍保留在 candidate graph 供审计和后续消费者选择，不解释为函数/程序安全。

### 8. atomic pair 与高级原子语义分离

普通与 atomic access 使用同一实例/对象配对流程。atomic/atomic 或 atomic/ordinary 重叠对按属性保留；R2 不因 atomic 自动抑制 pair，也不从 memory order 直接推导 HB。P3 reads-from candidate、P2 `order` 和源码先后只作为引用证据，不能形成 SW/HB。

对 fence、RMW/CAS release sequence、CAS failure order、复杂 modification-order 需求，R2 保存涉及的 access pair 并增加 `advanced-atomic-semantics-unsupported` frontier，供 A6 消费。这样避免丢失潜在候选，也避免在 R2 中复制 P4/A6 风险语义。

### 9. 多维分桶控制复杂度，未知域采用聚合 frontier

配对先按 scope/profile、execution family、可比较 storage candidate、address space、byte-range bucket 与 operation class 建立倒排索引，再只在可能重叠且实例关系可比较的桶内枚举。may candidate 会进入有限多个桶并以 pair identity 去重；动态/未知范围进入受限 unknown bucket，但只与候选依赖切片内相关对象域关联。

预算至少覆盖 access projection、execution instance、object candidate、bucket、alias comparison、MHP query、candidate pair、exclusion、protection query、frontier、递归/SCC、诊断、输出字节、worker/request CPU 与 wall time。任何维度耗尽都保留已完成结果、hit/limit、未处理域摘要和非空 frontier，不把截断图视为 complete。此方案相比全图 N² 可能漏掉无法建立对象桶的具体 pair，但会以 frontier显式 abstain，不会静默漏报。

### 10. 完整性按候选依赖切片传播

报告分别统计 demanded/completed/partial/failed roots、contexts、TUs、effects、accesses、instances、MHP relations、object bindings、buckets、pairs、protection queries 和 frontier。某个 TU 或 root 的失败只有在候选依赖切片相关时才降低该 slice；无关失败保留在 scope diagnostics。零候选只有在 root、访问、实例、对象、MHP 和预算分母全部闭合时才能表示“此请求范围内未形成 R2 候选”，仍不能表示无 data race 或安全。

AST-only、开放 scope、source/IR conflict、缺失 definition、profile/ABI/DataLayout 冲突、unknown external、conditional async、未知同步和预算耗尽必须映射到具体依赖切片及双语建议。相关 frontier 存在时状态至少 partial、退出码 `2`。

### 11. CLI、缓存与确定性输出保持独立

新增入口建议为：

```bash
python3 -m memory_order_analyzer build-concurrent-access-candidates \
  --request /input/concurrent-access-request.json \
  --artifact-store /artifacts \
  --output /output/concurrent-access
```

CLI 只读取显式 request/artifact store/worker，不扫描“最新”产物，不执行 configure、build、link、目标程序、网络或 SSH，且拒绝覆盖已有输出目录。输出包含 `request.json`、`projection/`、`execution-instance-binding.json`、`access-protection.json`、`candidate-graph.json` 和 `report.json`。

缓存使用 `concurrent-access-candidate-graph-v1` namespace；key 覆盖 schema/producer、工具链、scope/profile/target/DataLayout、全部依赖 digest、模型、预算和实现 identity。缓存命中重新验证引用闭包；损坏、陈旧、failed、timeout 或 wall-clock partial 不得作为成功命中。cold/warm semantic digest 排除路径、耗时、hit count 等观测字段并必须一致。

退出码固定为 `0` complete、`2` partial/unknown/unsupported/frontier、`1` request invalid 或全部不可用；不使用风险码 `3`。报告固定 `safety=not_evaluated`、`findings=null`，detail、limitation 和 suggestion 同时提供中文/英文字段，翻译不参与机器 identity。

### 12. 验证把候选召回、排除精度和 abstention 分开

四语言分别维护单 TU、跨 TU、no-debug、AST+IR、IR-only、AST-only、字段/指针、同名字段不同对象、mutex 内外、single/merged/repeated、open scope、预算和 cache fixture。每个 profile 单列 planned/completed/failed、expected/actual candidate pairs、protected/excluded/frontier、TP/FP/FN/abstention，不把四语言合并后掩盖缺口。

`memory-model-ir-checker/samples` 只作为归档参考；需要的样例必须最小化复制到本项目，记录原路径、内容摘要、许可证/来源和改写原因，并由人工重新标注为 candidate/protected/excluded/frontier。旧目录的 safe/unsafe 标签不是 R2 oracle，因为 R2 不输出 risk/safe。

全部新增、修改或复用自有模块都必须有正常、边界、异常和 unknown 单元测试。最终在独立开发容器的新输出目录运行整体 quality、四语言 truth、cache/预算/性能及文档校验，项目整体、Python、C++ 和每个受影响模块行/分支均至少 90%。

### 13. 文档分别说明架构、操作、实测与路线图

新增 `doc/CONCURRENT_ACCESS_CANDIDATE_GRAPH.md` 描述身份、数据流、协议、CLI、候选/排除/保护/frontier 和边界；新增 `doc/CONCURRENT_ACCESS_CANDIDATE_GRAPH_VALIDATION.md` 与机器可读 acceptance 记录环境、命令、truth、性能、内存、缓存和覆盖率；README/架构文档说明推荐流程；路线图将 R1.1 标记为已于 2026-09-23 同步归档，并在 R2 实施完成前保持“已提案/实施中”而非“已完成”。所有文档必须区分设计、实测、历史外部证据和 unknown，不把 exit 0、零候选、编译成功或保护标记写成安全证明。

## Risks / Trade-offs

- [跨 root 实例统一可能错误合并两个动态线程] → identity 必须包含 physical creation site、parent instance、guard、model 和 cardinality；context 可复用但 instance 不复用，冲突降级为 frontier。
- [A3/R1.1 对 jthread/async 生命周期证据少于 std::thread] → 只发布被证明的 may-parallel 区间；deferred 排除，默认 policy conditional，不猜测 future wait/join。
- [A5 may candidates造成配对膨胀] → 使用有限倒排桶、canonical pair 去重和独立预算；超限发布聚合 frontier，不截断成伪精确结果。
- [过度采用 A4 使真实候选被错误保护] → 引入独立 access-level overlay，要求双方访问、实例、held-region、exact mutex 和异常路径闭合；任一缺口保持候选/unknown。
- [只分析 demanded slice 可能遗漏错误配置以外的真实访问] → root/reachable coverage 是正式完整性分母；缺 root、开放 scope 或 overlay candidate 产生 partial，不回退到 all-defined 并宣称完整。
- [candidate 被误解为 data race] → 协议和 CLI 使用 candidate 命名，固定 `findings=null`、`safety=not_evaluated`，文档和测试禁止风险退出码。
- [atomic pair 数量增加但 R2 无法定性] → 保留给 P4/A6并清楚标记高级原子 frontier，不在 R2 内复制不完整的 C/C++ 内存模型。
- [历史样例标签污染 truth] → 复制后保留 provenance并人工重标 R2 语义，测试不得运行时读取兄弟 archive。

## Migration Plan

1. 添加六类 v1 schema、协议清单、引用校验、请求/报告契约和纯合成单元测试；旧 CLI 与缓存不变。
2. 实现 demanded effect 投影和 `ExecutionInstanceBindingOverlay`，先覆盖 pthread/`thrd_create`/`std::thread`，再接入证据受限的 `std::jthread`/`std::async`。
3. 实现 A5 对象域、分桶配对、排除/frontier 和预算/cache；此时尚不启用 protection suppression。
4. 实现 `AccessProtectionOverlay` 与 atomic handoff，增加四语言 truth、归档样例重标和旧协议黄金回归。
5. 接入 CLI、双语报告、README/架构/验证/acceptance/路线图，并在全新输出目录运行 required gate。

回滚只需停用新 CLI、删除 R2 模块/schema和独立缓存 namespace；旧 P1–P4、A1–A5、R1/R1.1 产物无需迁移或重写。若实现必须更改冻结协议或 P4 规则，应暂停并修订 proposal/design/spec，而不是在 apply 中隐式扩大范围。

## Open Questions

- 首版默认的 access、bucket、pair 和 unknown-domain 限额由实施期四语言 truth 与真实工程离线 profile 决定；规格固定预算类别、超限 frontier 和确定性，不预设未经测量的数值。
- `std::jthread` 自动 join 与 `std::async` future wait/get 的完整生命周期不是本 change 的 required 语义；实施若现有 profile 能形成完整证明，可作为受限增强，但不得以此阻塞候选图基础能力或猜测缺失关系。
- R2 完成后的数据将用于决定 R3 懒提取优先级和 A6 原子语义范围；本 change 不提前选择后续顺序。
