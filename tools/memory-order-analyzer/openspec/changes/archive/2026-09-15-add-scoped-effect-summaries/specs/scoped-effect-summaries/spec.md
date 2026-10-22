## ADDED Requirements

### Requirement: Schedule immutable local evaluation dependencies conservatively

调度器 SHALL 按 D2b 提交独立局部求值快照；只有合法采用且依赖齐备的直接调用才可利用被调返回与效果。未就绪调用 SHALL 产生 call_requests 和未知前沿，不伪造完整空摘要。缓存与重绑定 SHALL 区分模板上下文和包含实例/绑定/依赖的局部请求 hash；候选相关性丢失及递归/预算 unknown SHALL 传播完整性。

#### Scenario: A callee snapshot is not ready

- **WHEN** 本轮已到达调用但尚无稳定且合法采用的被调结果
- **THEN** 保存调用位置、实参域及 guard 的求值需求与非 complete 状态，后续依赖变化重新求值，不把内部 bottom 当成无效果返回

### Requirement: Separate reusable summaries from abstract activation identities

系统 SHALL 区分可复用 context_id 与有限 invocation/allocation 身份，保留原始 SourceRef。实例表 SHALL 记录父调用、调用位置、目标函数、上下文及 single/merged/unknown cardinality；值、guard、返回、escape 和诊断解释 SHALL 使用正确实例。模板命中 SHALL 重绑定局部分配和条件，不改变来自调用者的实参对象身份。

#### Scenario: Two callsites reuse the same argument summary

- **WHEN** 同一函数在两个不同调用位置以相同抽象实参调用
- **THEN** 可复用同一个 context，但局部分配和 guard 使用不同 invocation；不能仅凭相同 raw alloca/terminator 将存储或条件相关性合并

#### Scenario: Recursion or a budget merges activation instances

- **WHEN** 循环、递归 SCC 或预算使多个激活/分配合并为有限桶
- **THEN** 显式记录 merged/unknown 及原因，不由 ID 相等证明 must-alias、不由 ID 不同证明 noalias，不强更新、不跨激活消去 guard、不提升 must；丢失相关性以 partial 和非空未知前沿传播

#### Scenario: A cached template is rebound for another caller

- **WHEN** 新调用者命中已缓存的参数化摘要
- **THEN** 模板 key 可保持不变，而实例化产物的根及实例身份更新，返回和 escape 中原有调用者对象仍保留其分配归属，P1 v2 不变

#### Scenario: A condition repeats within one invocation

- **WHEN** 单一调用内部的循环在不同迭代执行同一 terminator
- **THEN** guard 的条件观察 multiplicity 为 repeated/unknown，不只凭 invocation=single 就将不同后继效果判为互斥；只有单次条件观察的独立证明才允许互斥消除

### Requirement: Represent parameterized effects with conditions and provenance

EffectSummary SHALL 描述普通/volatile/atomic 读写、RMW、CAS、fence、对象/范围、值关系、order/syncscope、返回、逃逸和未知效果，保留函数/调用点/原始事件、guard、出口及已知顺序。SHALL 区分 local 与可跨调用观察效果、may 与有证明且量化范围明确的 must，循环/递归重复不得变成恰好一次。

#### Scenario: Effects occur on mutually exclusive branches

- **WHEN** 函数不同分支分别包含读写或不同内存序的原子事件
- **THEN** 摘要保留分支条件和 may 语义，不把事件并集排列成一条必然执行序列

#### Scenario: A function can throw or not return

- **WHEN** 某个效果只在正常返回路径出现，另有异常/不返回出口
- **THEN** 不声明该效果在所有调用上必然发生；任何 must 标记都携带适用出口/路径范围和证明

### Requirement: Compose only eligible direct calls across explicit translation units

系统 SHALL 仅沿经过 scope/配置/profile/lineage 和接口/函数体采用复核的直接调用边，替换实际参数对象和值并传播返回关系、效果及 unknown。SHALL 不要求先 llvm-link，不自动组合目录或编译数据库中的全部 BC；同名 static 保留 artifact 身份，extern 不创建重复存储。

#### Scenario: A call chain spans three physical translation units

- **WHEN** 三个实际独立编译的 TU 在同一合法 scope 中通过确定直接调用传递对象指针、值和 order
- **THEN** 最外层摘要关联最终对象与效果并保留三层调用证据，无须原生链接或 llvm-link

#### Scenario: Internal symbols and scope boundaries differ

- **WHEN** 两个 TU 含同名 static，或另一个 scope 含同名外部符号
- **THEN** 不跨内部身份或 scope 合并函数/全局，不把另一目标的定义用于当前调用

### Requirement: Specialize contexts and propagate supported returns

系统 SHALL 按有界实际对象/值绑定生成调用上下文摘要，支持返回参数、参数加常量偏移、确定全局地址和受支持常量，并将关系传给调用者；SHALL 保留通用参数化摘要，不以函数名作为全部上下文缓存键。失效局部地址和未支持 heap 返回 SHALL 保持诊断/unknown。

#### Scenario: The same callee receives different actual arguments

- **WHEN** 两个调用向相同函数传入不同对象或不同常量 order
- **THEN** 生成不同上下文和筛选结果，既不混合对象/事件，也不复用第一个调用的确定值

#### Scenario: A returned field pointer is used by the caller

- **WHEN** 被调函数返回参数加已知常量字段偏移，调用者随后访问该指针
- **THEN** 摘要传播原始对象和精确偏移/范围及返回证据，不创建新的独立对象

#### Scenario: A function returns an expired local address

- **WHEN** 返回值来自已经结束生命周期的局部存储或未支持的堆分配关系
- **THEN** 不宣称获得有效确定存储对象，保留生命周期或 heap unknown

### Requirement: Derive atomic wrapper effects from reachable body semantics

系统 SHALL 在锁定且记录版本的 Clang 21.1.8/libstdc++ 13 C++17/20 组合下，通过实际编译的 O0 包装体、合法采用边、实参绑定、局部传播和路径筛选推导可达原子效果。SHALL 不以函数名、固定源枚举值或函数体全部 order 的并集替代分析；helper/ABI/异常缺口与 order 已知状态分开记录。

#### Scenario: Release is passed through an O0 wrapper

- **WHEN** publish 调用 wrapped(&x,1,memory_order_release)，且相关局部语义和辅助调用满足支持规则
- **THEN** publish 上下文的可达原子写针对 x、值为 1、order 为 release，不含仅由其他 order 分支产生的 monotonic/seq_cst 写；原始函数事实仍保留全部分支

#### Scenario: A different library or unresolved helper is encountered

- **WHEN** 库组合未验证且可达函数体不能解释，或 order 可筛选但 helper/异常效果仍未知
- **THEN** 保留已知原子效果及相关 unknown，摘要 partial，不以看到 release 或调用名匹配宣称完整支持

### Requirement: Propagate unknown effects and escape conservatively

未解析间接调用、缺失函数体、不合格 ABI/ODR、opaque 操作及相关局部 unknown SHALL 传播到调用者摘要和报告。未知调用 SHALL 对可能触及/别名的内存产生保守未知读写/逃逸影响，不等同无效果，也不无依据使无关私有对象全部逃逸。部分已知效果 SHALL 与 unknown 并存。

#### Scenario: An external call receives an object address

- **WHEN** 未提供函数体的外部调用获得对象指针
- **THEN** 摘要保存可能的读写/逃逸和未知返回/控制影响，后续不能依赖该对象旧值做确定转发

#### Scenario: An unknown callee is nested under known wrappers

- **WHEN** 已知调用链深处存在相关未知效果
- **THEN** 每个依赖它的调用上下文保留原因和调用路径，不在跨 TU 组合时丢弃或提升为完整

### Requirement: Bound recursive and context-sensitive analysis without dropping effects

系统 SHALL 使用 SCC 固定点及有界上下文/值/路径域，执行 `scoped-effects-v1` 默认预算：每上下文 100000 局部节点、32 条件状态、每值 8 候选；每函数 32 上下文、每请求 4096 上下文；SCC 16 轮；每摘要效果节点/顺序边合计 10000。worker 每批 SHALL 限 60 秒/16 MiB 输出，请求限 300 秒/64 MiB 派生产物；请求可显式收紧且生效预算纳入身份。超限 SHALL 保留已知效果、未知前沿与截断原因，禁止发布不完整 JSON 或未收敛空摘要冒充完成。

#### Scenario: Recursive summaries converge

- **WHEN** 直接或互递归在有限抽象域内达到固定点
- **THEN** 稳定输出已知效果、递归/重复语义和依赖，不无限展开调用链或错误声明单次执行

#### Scenario: A local loop repeatedly visits the same instructions

- **WHEN** 局部迭代持续处理已有 IR 节点而没有增加不同节点数量
- **THEN** 每次工作项处理仍消耗局部节点预算，超限保守降级，不绕过预算无限执行

#### Scenario: A recursion or context budget is exhausted

- **WHEN** 任一 SCC/上下文/候选/路径/输出/时间预算被耗尽
- **THEN** 未处理前沿标为 unknown，保留可用结果并报告 partial 或全部不可用时 failed，不过滤未完成项使完整率提高

### Requirement: Cache derived summaries with transitive semantic dependencies

派生缓存 SHALL 依赖 BC/facts digest、extractor/LLVM/analysis/policy、scope/边界/profile、入口/上下文、实际预算和被调摘要；递归依赖使用稳定 SCC 组身份，调用者随依赖传递失效。SHALL 消费前验证缓存结构/引用/身份，不因分析规则变化重编译未变 BC 或修改 P1 ArtifactKey。

#### Scenario: A callee changes while a caller bitcode stays unchanged

- **WHEN** 被调函数内容或摘要策略改变而调用者 BC 未变
- **THEN** 重算相关 SCC/调用者派生摘要，不复用旧效果；不要求无关原始 TU 重新编译

#### Scenario: Cached output is corrupt or belongs to another profile

- **WHEN** 缓存有悬空引用、错误 hash、不同 scope/profile 或未来版本
- **THEN** 拒绝作为有效命中并给出原因，不混合不同构建变体的事件或覆盖原缓存伪装修复
