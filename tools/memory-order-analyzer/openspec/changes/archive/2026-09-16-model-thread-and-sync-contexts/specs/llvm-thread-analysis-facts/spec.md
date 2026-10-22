## ADDED Requirements

### Requirement: Produce independent versioned thread-local facts

系统 SHALL 从已校验 BC、P1 `ModuleFacts v2` 和所需 P2 依赖生成独立 `ThreadLocalFacts v1` 与 `ExecutionOrderFacts v1`，记录 LLVM/worker/analysis/policy、scope/profile、输入 digest、预算和能力；SHALL 复用原始 SourceRef/AnalysisRef 而不修改 BC、P1/P2 产物或其身份。缺少 P3 sidecar MUST NOT 被解释为单线程或无同步。

#### Scenario: Repeated extraction uses unchanged inputs

- **WHEN** 同一 BC、P1/P2 digest、请求、模型和预算再次执行且未触发墙钟限制
- **THEN** P3 局部产物的语义内容、身份、排序和证据引用稳定，原始产物保持逐字节不变

#### Scenario: Bitcode or a dependency changes during extraction

- **WHEN** BC hash 在分析前后变化，或请求引用的 P1/P2 digest 与实际文件不符
- **THEN** 系统拒绝发布可消费的局部事实并报告输入变化，不把旧 sidecar 当作缓存命中

### Requirement: Recognize pthread primitives and callbacks conservatively

worker SHALL 输出 pthread 候选调用的直接符号、调用接口、calling convention、参数角色、返回值及 callback metadata；模型采用 SHALL 同时满足版本化 `posix-pthread-v1` 的 ABI/profile/边界规则。callback metadata 只能作为辅助证据，冲突、间接 API、相似名称或未知 wrapper MUST 保持 unknown。

#### Scenario: A direct create call has a supported callback

- **WHEN** 直接 `pthread_create` 调用的接口与 profile 匹配，callback metadata（若存在）与模型参数位置一致，入口为可解析直接函数地址且 worker 参数可绑定
- **THEN** 产物登记可采用 create 调用、入口候选、参数绑定和全部证明来源，不以调试名称代替函数身份

#### Scenario: Metadata and the registered model disagree

- **WHEN** callback metadata 的 broker/argument 映射与 `posix-pthread-v1` 冲突，或调用 ABI/边界不可验证
- **THEN** 系统拒绝确定采用并输出可定位 unknown，不任选一个参数作为线程入口

#### Scenario: A similarly named wrapper is encountered

- **WHEN** 调用目标为间接值、自定义 wrapper 或仅名称类似 pthread API 的函数
- **THEN** 系统不套用 pthread 语义模型，保留调用、候选或 unknown 供完整性传播

### Requirement: Derive execution order from LLVM control-flow evidence

`ExecutionOrderFacts v1` SHALL 使用指令位置、CFG 可达性、DominatorTree、PostDominatorTree、LoopInfo 及调用 anchor 表达 `must-before`、`may-before`、互斥或 unknown；跨块 must 证明 MUST 排除循环重复导致的动态次序反转。SHALL 不复制 P2 `EffectSummary.order` 作为顺序证明。

#### Scenario: Instructions are ordered in a non-repeating region

- **WHEN** 两个相关事件在同一基本块有确定指令序，或在无重复歧义的 CFG 区域由支配/后支配和可达性共同证明先后
- **THEN** 输出带原始节点、LLVM 分析证据、适用 guard 和 invocation/thread 归属的 must-before 边

#### Scenario: A loop can reverse dynamic occurrences

- **WHEN** 源码/IR 中相同节点可在循环多次执行，使后一次 A 发生在前一次 B 之后，或路径证明不足
- **THEN** 不输出无条件 must-before，改为 repeated/may/unknown 并保存原因

#### Scenario: Ordering crosses a call boundary

- **WHEN** caller、callee invocation 及正常/异常/不返回出口均可验证
- **THEN** 输出独立的 call-entry/call-exit anchor 和条件化边；未证明正常返回时不得把 callee 效果串接到调用后路径

### Requirement: Track bounded handle and mutex provenance

局部事实 SHALL 为 create 输出 handle token、受支持的精确 load/store/cast/phi/select 传播、join 输入以及 mutex 对象/范围/初始化指纹登记 provenance。确定关联 MUST 要求有限候选、兼容范围和无相关 clobber；共享、逃逸、覆盖、未知别名及未支持转换 SHALL 降为候选或 unknown。

#### Scenario: A handle is copied through exact storage

- **WHEN** create 的输出槽产生唯一 token，该 token 经受支持的精确存储读取/复制到 join，期间无可能别名覆盖
- **THEN** 输出可回溯 create、对象范围、复制节点和 join 输入的唯一关联证据

#### Scenario: A handle slot is overwritten or escapes

- **WHEN** token 槽被另一次 create、未知调用或可能别名写覆盖，或传播超过候选预算
- **THEN** 保留有限候选或 unknown 及 clobber/frontier，不继续声明 join 唯一关联原线程

#### Scenario: A mutex initializer is not recognized

- **WHEN** mutex 对象可解析但其初始化不匹配锁定 libc/target 的普通非 robust 静态 initializer 指纹
- **THEN** 保留 lock/unlock 调用和对象证据，但 mutex kind 与同步语义保持 unknown

### Requirement: Bound local thread evidence without publishing dangling facts

worker SHALL 对候选、工作项、输出和时间应用请求中的实际预算，并为 LLVM 生成节点使用独立 AnalysisRef。任何成功发布的局部产物 MUST 通过函数归属、引用闭包、角色、digest 和预算校验；超限 SHALL 保留已知结果与非空 frontier，或在无法形成合法闭包时使该 job failed。

#### Scenario: Candidate expansion exceeds a local limit

- **WHEN** callback、handle、mutex 或顺序候选扩展超过显式预算
- **THEN** 系统不截取后宣称 complete，而是报告实际计数、已知候选、未处理前沿及 partial/failed

#### Scenario: An analysis reference is forged or stale

- **WHEN** P3 产物引用不存在、错误函数归属、错误输入 digest 或上一代 LLVM 分析节点
- **THEN** 消费者拒绝该产物，不将悬空证据用于线程或同步关系
