# scanner-failure-semantics Specification

## Purpose

定义无效输入、翻译单元失败、资源预算耗尽、内部错误和诊断聚合的保守处理语义，确保任何未完成、未知或失败的分析范围都不会被下游误解为“扫描成功且没有浮点风险”。

## Requirements

### Requirement: 输入错误在分析前失败
扫描器 SHALL 在启动分析前验证 scan schema、源码和 artifact 路径边界、profile、规则配置、抑制语法、资源预算、artifact-set manifest schema/摘要以及 source revision、compile database、context、target/ABI 的跨输入一致性。输入错误或确定冲突 MUST 聚合为结构化诊断并返回 `invalid_request`；不得启动 Clang/LLVM worker或创建看似完整的空结果。共享 artifact 尚未就绪属于可重试外部依赖失败，不得误分类为 schema 输入错误。

#### Scenario: 项目根或 artifact root 越界
- **WHEN** 源码、manifest、BC 或 sidecar 路径解析后位于其允许根之外
- **THEN** 扫描器拒绝请求或对应 artifact，返回路径越界诊断且不读取越界文件

#### Scenario: 多个配置错误
- **WHEN** 请求同时包含无效 profile、负资源预算和未知规则 code
- **THEN** 扫描器在安全可行时一次返回全部配置诊断，状态为 `invalid_request`

#### Scenario: 没有 C/C++ 输入
- **WHEN** 输入选择器解析后不存在任何 C 或 C++ 翻译单元
- **THEN** 扫描器返回 `invalid_request` 和 `no_supported_translation_units` 诊断，不尝试分析其他源语言或孤立 BC

#### Scenario: source revision 与 artifact-set 冲突
- **WHEN** 两个输入包含完整但不同的 source revision 或 compile database SHA-256
- **THEN** 扫描器返回 `invalid_request` 和跨输入冲突诊断，不启动任何 facts 提取

### Requirement: 翻译单元失败产生保守的部分结果
当部分翻译单元因 AST 解析、缺失头文件、artifact 缺失/损坏、LLVM 不兼容、verifier/worker 失败、不支持语义或必需 evidence 无法绑定而失败时，扫描器 SHALL 保留其他成功翻译单元的 source facts、IR facts 和 evidence，状态为 `partial`，并分别公开各层 planned、completed、failed 和 unknown 分母。任一失败范围 MUST NOT 被解释为无 finding、无浮点操作或不受架构影响。

#### Scenario: 单个 AST 翻译单元解析失败
- **WHEN** 十个计划翻译单元中九个 source facts 成功、一个因缺失头文件失败
- **THEN** 扫描器保留九个单元事实，状态为 `partial`，并为失败单元输出包含阶段和原因的诊断

#### Scenario: 单个 BC verifier 失败
- **WHEN** source facts 全部成功但一个必需 BC 成员 verifier 失败
- **THEN** 成功的 source/IR facts 被保留，IR failed 分母增加且整体状态至少为 `partial`

#### Scenario: 所有必需事实提取失败
- **WHEN** 没有任何计划翻译单元产生请求所需的可用 source/IR 事实
- **THEN** 扫描器状态为 `failed` 而非 `partial`，且摘要不会声明工程无浮点风险

### Requirement: 资源预算耗尽可区分
扫描器 SHALL 支持 wall time、CPU、内存、文件数、artifact/BC 总字节、单 BC 字节、worker 输出、IR facts、evidence candidates 和诊断数预算。预算耗尽时 MUST 停止新增工作、终止或隔离受影响 worker、完成可安全落盘的已有结果，并以 `budget_exceeded` 诊断说明具体预算、已用值、profile/TU 和未分析范围；存在可用结果时状态为 `partial`，否则为 `failed`。

#### Scenario: 达到翻译单元时间预算
- **WHEN** 分析在部分翻译单元完成后达到请求 wall time 限制
- **THEN** 扫描器发布确定的部分结果与未完成清单，返回退出码 `4`

#### Scenario: BC 总字节超过预算
- **WHEN** manifest 声明的必需 BC 总大小超过请求允许值
- **THEN** 扫描器在读取 BC 前拒绝新增 worker 工作，并公开受影响成员和预算差额

### Requirement: 规则证据缺失和冲突必须逐 assessment 保守传播
每条启用规则 SHALL 在执行前验证其 scope 所需的 AST facts、IR facts、evidence bindings、profile 字段和有效编译选项。缺失、unsupported、ambiguous、摘要不一致或相互冲突的决定性证据 MUST 产生 `unknown` 或 `failed` assessment 及稳定双语诊断，不得降级为 `not_matched`。若至少一个 assessment 可用但任一必需 assessment 被阻断，整体状态 SHALL 至少为 `partial`；若所有启用规则均没有可用 assessment，整体状态 SHALL 为 `failed`。

#### Scenario: FMA binding ambiguous
- **WHEN** 乘加候选对应多个无法唯一验证的 IR facts，且没有有效显式 sidecar
- **THEN** `fma-contraction` assessment 为 `unknown`，诊断记录候选数和 frontier，不任选一个 IR fact 生成或排除 finding

#### Scenario: 一个规则缺少 profile 字段
- **WHEN** `long-double-abi` 因目标 profile ABI class unknown 无法判断，但其他启用规则完整完成
- **THEN** 保留其他规则 findings，整体结果为 `partial`，summary 将该 scope 计入 unknown 而非 not_matched

#### Scenario: 所有启用规则都不可评估
- **WHEN** 每个启用规则都因必需 facts/evidence/profile 缺失或失败而没有 matched/not_matched assessment
- **THEN** 整体结果为 `failed`，退出码为 3，且摘要不得声明未发现核心迁移风险

### Requirement: 规则异常必须按可隔离范围处理
规则实现抛出的已分类输入/证据异常 SHALL 只使对应 rule/scope assessment 为 `failed`，其他规则和 scope MUST 继续；registry 损坏、身份算法不一致、结果 schema 无法满足或其他无法安全隔离的错误 SHALL 升级为 `internal_error`。默认诊断 MUST 移除堆栈、环境变量值、凭据和根外绝对路径。

#### Scenario: 单条规则对一个翻译单元失败
- **WHEN** `x87-excess-precision` 在一个 TU 的规范化事实上遇到可隔离的非法组合，而其他 TU 和规则输入有效
- **THEN** 仅该 rule/TU assessment 计入 failed，其他结果被保留，整体状态按部分完成语义聚合

#### Scenario: registry identity 不一致
- **WHEN** 同一 rule code/version 在一次运行中解析出两个不同实现摘要或依赖声明
- **THEN** 扫描器停止规则执行并返回 `internal_error`，不发布可能由错误 registry 生成的 finding

### Requirement: 规则预算耗尽必须记录稳定 frontier
扫描器 SHALL 对总 assessment 数、单规则候选数、证据引用数、聚合相关位置数、诊断数和规则 wall/CPU 预算设置显式上限。候选 MUST 在截断前按稳定键排序；预算耗尽时 SHALL 停止受影响范围，记录预算名称、限制、已用值、rule/scope 和最后完成的稳定 frontier。已有可用 assessments 被保留，未处理范围 MUST 计入 unknown/failed，且不得因不同并发完成顺序改变结果。

#### Scenario: FMA 候选数达到预算
- **WHEN** `fma-contraction` 在处理完稳定排序的部分候选后达到单规则候选上限
- **THEN** 已完成 assessment 保留，剩余 scope 记录 `budget_exceeded` 和 frontier，整体结果至少为 `partial`

#### Scenario: 聚合位置超过输出上限
- **WHEN** 一个 `unsafe-fp-optimization` aggregation key 关联的位置数量超过配置上限
- **THEN** finding 保存确定性选择的有界位置、总受影响数和截断标记，不因输入或线程顺序选择不同代表位置

### Requirement: 内部错误不伪装成规则结论
未预期异常 SHALL 转换为 `internal_error`，默认仅输出稳定错误 code、失败阶段、关联请求和安全摘要。堆栈、绝对路径、环境变量与源码内容 MUST NOT 在默认模式泄露；显式诊断模式可以写入受控本地日志。

#### Scenario: 规则实现抛出未预期异常
- **WHEN** 某规则执行期间出现未分类异常
- **THEN** 扫描器停止或隔离该分析单元，结果不包含由异常路径构造的 finding，并返回 `internal_error` 或保守的 `partial`

### Requirement: 诊断必须可操作且双语
每条诊断 SHALL 包含 `diagnostic_code`、`stage`、`severity`、中文与英文消息、可选规范化源码或 artifact 身份、可重试性和建议动作。共享制品未就绪、摘要不符、LLVM 版本不兼容、verifier 失败、debug/source mapping 不足等 MUST 使用不同稳定 code；相同根因的大量重复诊断 MUST 被聚合，并保留出现次数、受影响 profile/TU 和代表性位置或 artifact key。

#### Scenario: 重复缺失同一系统头文件
- **WHEN** 多个翻译单元因同一缺失头文件失败
- **THEN** 扫描器输出聚合诊断、受影响数量和代表位置，而不是无上限重复消息

#### Scenario: artifact-set 正在生成
- **WHEN** 共享 artifact 状态为 `MISSING`、`QUEUED` 或 `GENERATING`
- **THEN** 扫描器输出 `artifact_not_ready` 双语诊断、`retryable=true` 和 artifact-set 身份，不在诊断中暴露对象存储凭据或临时路径

### Requirement: 共享制品失败与 x86 构建结果必须分离
扫描器 SHALL 将 artifact 未就绪、损坏或 LLVM 提取失败描述为分析输入/执行失败，不得改写或推断上游 x86 构建状态。结果 MAY 引用 build run identity，但 MUST NOT 将“BC 失败”等价为“项目构建失败”。

#### Scenario: x86 构建成功但 BC 成员损坏
- **WHEN** manifest 引用成功 build run，而一个 BC 文件摘要不符
- **THEN** 扫描结果报告该 artifact 分析失败，且不声称上游 x86 构建失败

### Requirement: 表达式规则缺失上下文必须按声明依赖传播
六条表达式风险规则 SHALL 在每个 scope 执行前校验 descriptor 声明的 canonical types、control-flow/use、loop/recurrence、call/environment summary、IR capability/evidence、profile 和 build-context 字段。缺失、unsupported、ambiguous、budget frontier 或事实冲突 MUST 使受影响 assessment 为 `unknown` 或 `failed`，并输出稳定双语 reason code；与规则无关的 unknown 字段 MUST NOT 阻断该 assessment。

#### Scenario: conversion 类型缺失
- **WHEN** `mixed-precision-conversion` 候选缺少 source 或 destination canonical type
- **THEN** 该候选 assessment 为 `unknown`，不按字面量后缀或变量名判断损失

#### Scenario: libm build context 缺失
- **WHEN** `math-library-variance` 需要比较两端库行为但任一 build context 的 libm identity/capability unknown
- **THEN** 该 assessment 为 `unknown`，其他不依赖 libm 的规则继续执行

#### Scenario: IR 与 AST 归约证据冲突
- **WHEN** AST 表示固定顺序累加，而 verified build-faithful IR 表示无法解释的不同 recurrence 或 flags
- **THEN** `reduction-reassociation` assessment 为 `unknown` 并报告 evidence conflict，不任选一侧生成确定 finding

#### Scenario: 无关 profile 字段未知
- **WHEN** architecture API 所需 declaration/target feature 完整，但数学库字段 unknown
- **THEN** `architecture-specific-fp-api` 按自身依赖完成，不因无关字段降级

### Requirement: 启发式规则失败不得伪装为确定性或无风险
启发式候选生成、rationale 选择、confidence 计算或 suppression 匹配失败时 SHALL 产生 `failed`/`unknown` assessment 或 suppression diagnostic，不得回退为 deterministic finding、`not_matched` 或静默删除。任何 heuristic finding MUST 保持人工确认标记；无法满足输出协议时不得发布该 finding。

#### Scenario: heuristic rationale 无模板
- **WHEN** 比较或归约规则命中一个未注册 rationale code
- **THEN** 对应 assessment 为 `failed` 或运行时安全失败，且不构造缺少中英文解释的 finding

#### Scenario: suppression 解析失败
- **WHEN** 源码 suppression 语法存在但 code、理由或范围不可验证
- **THEN** suppression 不生效，候选 finding 保留并输出可操作的双语诊断

### Requirement: 预算和资源故障必须保留稳定未分析分母
任一 wall、CPU、RSS、文件、字节、输出、facts、evidence、rule、diagnostic、suppression 或结果大小预算耗尽时，扫描器 SHALL 停止新增受影响工作、终止或隔离相关 worker、保留已安全完成结果，并公开稳定 frontier 与未分析 planned 分母。存在可用结果时状态 MUST 为 `partial`，没有任何请求所需可用结果时 MUST 为 `failed`；不得以空 findings 表示安全。

#### Scenario: 全局 wall budget 在部分完成后耗尽
- **WHEN** 部分 source/evidence/assessment 已完成后共享 deadline 到期
- **THEN** 已完成结果原子发布、剩余范围计入 unknown/failed、状态为 partial 且退出码为 4

#### Scenario: 输出大小预算在发布前耗尽
- **WHEN** 完整结果超过允许的结果字节数
- **THEN** 既有正式结果保持不变，扫描器发布安全的失败状态或旁路最小诊断，不能截断 JSON 冒充完整结果

### Requirement: 缓存故障必须与分析输入故障分离
缓存 miss、损坏、不兼容、路径越界和发布失败 SHALL 使用独立稳定 diagnostic code。可以从可信输入重新计算时，缓存故障 MUST NOT 单独把扫描状态降为 partial/failed；无法重新计算时，状态由缺失的 source/IR/evidence 决定，而不是把缓存视为真值来源。

#### Scenario: 损坏缓存可重新计算
- **WHEN** 缓存摘要无效但源码、编译上下文和工具链有效
- **THEN** 扫描器诊断 cache corruption、重新计算并可返回 complete

### Requirement: 诊断预算必须保留根因和可操作性
重复诊断 SHALL 按稳定 code、stage、profile/TU 和安全根因聚合。达到诊断预算时 MUST 保留各阻断 stage 的代表根因、总出现数、受影响分母和一个预算终止记录；路径、源码、环境变量、凭据、堆栈和缓存根必须按现有脱敏规则处理。

#### Scenario: 大量 TU 缺少同一头文件
- **WHEN** 缺失头文件产生的原始诊断数超过上限
- **THEN** 输出一个或有界代表诊断及总计数，并保留 diagnostic budget 终止记录

### Requirement: 故障注入不得进入生产协议
测试 SHALL 通过可注入 clock、resource sampler、process runner、cache store、serializer、fsync 和 replace 精确触发异常。生产 scan request/schema MUST NOT 提供随机故障开关、任意异常类型或测试路径注入字段。

#### Scenario: 单元测试注入 fsync 失败
- **WHEN** 测试适配器在缓存或结果 fsync 阶段抛出错误
- **THEN** 原子恢复和状态映射可被独立断言，生产请求协议不包含该注入配置

**候选级 unknown 与上游 BC 根因**

### Requirement: unrelated unknown 不得降低规则或翻译单元状态
unsupported 记录 MUST 声明受影响的 fact kind、rule dependency 和 candidate/scope。数组下标、
初始化列表、隐式值初始化、赋值与临时对象等已由子 facts 完整表达的结构节点 SHALL 为 handled
或非阻断；只有真正缺失规则必需语义的候选才能形成 blocking unknown。上游 BC 降级诊断 SHALL
区分 manifest parse/schema/identity、bundle layout/member integrity、source binding、materialization
和 LLVM worker，不得统称为 worker validation failed。

#### Scenario: 非标量 cast 与有效归约并存
- **WHEN** TU 同时包含指针/容器 cast 和可证明的浮点归约
- **THEN** 非标量节点不产生 mixed-precision unknown，归约 assessment 保持完成
- **AND** 若 BC 真正无效，扫描仍可 AST-only 并保留具体 BC 根因
