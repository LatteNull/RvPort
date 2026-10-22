# KB Scanner Evidence Graph Specification

## Purpose

定义 KB Scanner 在纯静态分析边界内构建 scanner-owned Evidence Graph、跨文件宏与 include proof path、条件分支及替代实现关系的合同，并保持构建选择、最终分类和兼容报告职责在后续阶段。

## Requirements

### Requirement: Evidence Graph 必须使用可替换的 scanner-owned 存储合同
KB Scanner SHALL 通过 scanner-owned `GraphStore` protocol 注册和查询 core Entity、Relation 与 proof path，首个正式 adapter SHALL 使用经容器验证的 NetworkX MultiDiGraph，且任何 NetworkX 私有类型或异常 MUST NOT 泄漏到 frontend、analyzer、detector、projector 或报告合同。

#### Scenario: 同一端点存在平行关系
- **WHEN** 两个 Entity 之间存在不同 kind 或不同 Evidence provenance 的多条 Relation
- **THEN** GraphStore SHALL 完整保留这些有向平行关系
- **AND** 查询结果 SHALL 只包含排序后的 scanner core 对象

#### Scenario: 替换具体图实现
- **WHEN** 后续因资源预算替换 NetworkX adapter
- **THEN** frontend、analyzer、detector 和兼容报告 SHALL 无需改变领域接口
- **AND** Entity、Relation 与 ProofPath 稳定身份 SHALL 保持相同

### Requirement: Evidence Graph 必须产生稳定且引用有效的实体与关系
Graph Analyzer SHALL 为 project、source file、macro definition、macro invocation、condition group、branch、symbol/call site、implementation、architecture selector、build variable、source set、directory、compile/link argument、dependency、target、package 和 package section 建立确定性 Entity，并 SHALL 产生 `defines`、`includes`、`invokes_macro`、`expands_to`、`calls`、`has_branch`、`guarded_by`、`depends_on`、`selects`、`excludes`、`adds_argument`、`requires`、`produces`、`alternative_to` 与 `reachable_from` Relation；所有端点和 Evidence 引用 MUST 存在于同一分析快照。

#### Scenario: 相同输入重复分析
- **WHEN** 使用相同 scanner/knowledge 版本、ScanContext、源码和构建输入重复运行组合 Graph Analyzer
- **THEN** Entity、Relation、ProofPath 的 ID 与排序 SHALL 完全一致
- **AND** 身份材料 MUST NOT 包含机器绝对路径、随机值、对象地址或遍历时序

#### Scenario: 关系引用未知端点
- **WHEN** Relation builder 尝试建立含未知 Entity 或 Evidence ID 的源码或构建关系
- **THEN** Analyzer SHALL 拒绝该关系并返回 failed Diagnostic
- **AND** 无效引用 MUST NOT 进入 AnalysisSnapshot

#### Scenario: 构建项关联现有源码实体
- **WHEN** build Evidence 中规范化的源码路径匹配 C/C++ Frontend 已注册的 source file Entity
- **THEN** Analyzer SHALL 复用该 source file Entity 建立 target selection 关系
- **AND** scanner MUST NOT 因 producer 不同而创建语义重复的源码实体

### Requirement: Graph Analyzer 必须建立有界的跨文件 include 与宏 proof path
Graph Analyzer SHALL 从同项目 include、macro definition、macro invocation 和 replacement token Evidence 建立可追溯关系，并 SHALL 在显式深度、访问节点数和路径数预算内物化从宏调用点到定义及终端 symbol/intrinsic 的 ProofPath。

正式管线的源码 ProofPath 物化范围 SHALL 遵循 `kb-scanner-large-project-performance` 的 fact 驱动需求合同：复用既有匹配规则，覆盖 confirmed、candidate、hint 的 Evidence，保留全部事实和基础关系，只省略与所有需求无关的源码 proof。反向候选计划 SHALL 仅收敛查询组合，详细搜索的路径顺序、预算、完整性和稳定身份 MUST 保持不变。

#### Scenario: 需求 Evidence 位于跨文件路径中间
- **WHEN** 路径包含候选 Evidence 关联关系，但终点本身不是候选符号
- **THEN** Analyzer SHALL 保留该需求相关路径，不能只按终点名称过滤
- **AND** 未匹配需求的基础关系 SHALL 继续保留，缺少 proof MUST NOT 被解释为安全

#### Scenario: 本地头文件宏最终调用 x86 intrinsic
- **WHEN** 源文件包含本地头文件并调用其中函数式宏，且 replacement body 静态引用一个终端 intrinsic
- **THEN** AnalysisSnapshot SHALL 包含 `includes`、`invokes_macro`、`expands_to` 或 `calls` 组成的完整 proof path
- **AND** 每条 Relation SHALL 引用对应 definition、invocation 或 replacement Evidence

#### Scenario: 宏定义出现但没有调用
- **WHEN** Frontend 只发现函数式宏定义及其 replacement token，没有宏 invocation
- **THEN** Graph Analyzer SHALL 建立 definition 与 replacement 的关系
- **AND** scanner MUST NOT 把 macro definition 自身建立为 call site 或 invocation

#### Scenario: include 或宏定义无法唯一解析
- **WHEN** include 目标缺失/歧义，或同一宏存在无法静态消解的多个定义
- **THEN** Analyzer SHALL 保留有证据的候选关系并把相关 path 标记为 partial/unknown
- **AND** scanner MUST NOT 任意选择一个候选或把缺失路径解释为安全

### Requirement: 条件分支和替代实现关系必须基于 sibling 证据
Graph Analyzer SHALL 为同一预处理条件结构建立 condition group、ordered branch、`has_branch` 与 `guarded_by` 关系，并 SHALL 仅在同组 sibling 证据支持时，把 x86 branch/implementation 通过 `alternative_to` 关联到 RISC-V、generic、portable、scalar 或 fallback branch/implementation。

#### Scenario: x86 分支具有 RISC-V sibling
- **WHEN** 同一条件组包含可追溯的 x86 分支与 RISC-V sibling 分支
- **THEN** Analyzer SHALL 建立带 branch role 和 Evidence/Knowledge provenance 的 `alternative_to`
- **AND** 本阶段 MUST NOT 因该关系判定最终 blocking、severity 或 readiness

#### Scenario: x86 分支只有 generic fallback
- **WHEN** 同一条件组没有 RISC-V 专用分支但具有 generic、portable、scalar 或 fallback sibling
- **THEN** Analyzer SHALL 保留该 sibling 为替代候选及其 role
- **AND** Analyzer MUST NOT 声称该候选已被 RISC-V 构建选择

#### Scenario: 相似实现不属于同一条件组
- **WHEN** 两个文件或分支只有名称相似但没有 sibling、include、调用或实现关联证据
- **THEN** Analyzer MUST NOT 仅凭名称建立 `alternative_to`

### Requirement: Proof path 必须传播完整性、预算和未知原因
GraphStore 与 Graph Analyzer SHALL 对每次关键路径查询记录 relation sequence、visited 数量、completion status 和未完成原因；循环、预算截断、partial parse、不支持预处理语义和缺失输入 SHALL 保持 partial/unknown，而 MUST NOT 等价为不存在迁移问题。

#### Scenario: 宏关系包含循环
- **WHEN** 两个或多个宏的 replacement 形成引用循环
- **THEN** proof resolver SHALL 有界终止并返回 cycle 对应的 partial/unknown reason
- **AND** 它 MUST NOT 无限递归或删除循环前已经证明的关系

#### Scenario: 遍历超过预算
- **WHEN** proof 查询超过配置的 max depth、max visited 或 max paths
- **THEN** PathSearchResult SHALL 标记 truncated 并保留已访问计数和已有路径
- **AND** AnalysisSnapshot/StageResult SHALL 传播 partial 状态与稳定 Diagnostic

#### Scenario: 完整图中未发现路径
- **WHEN** 相关输入完整、未触发不支持语义或预算截断，且查询没有找到目标
- **THEN** 结果 SHALL 区分 `not_found` 与因输入不足产生的 `unknown`

### Requirement: Evidence Graph 必须以人工审计的 AVX 事实验收
本 capability SHALL 使用版本化、不可由 scanner 自动重写的 AVX/AVX2 人工审计 baseline 验收关系正确性，且 MUST NOT 以 Legacy Finding 总数、严重度或 blocking 状态作为 correctness oracle。

#### Scenario: 验收 AVX 源码局部事实
- **WHEN** qualification 扫描人工基线中的 37 个 C/C++ 文件
- **THEN** 39 个 x86 header、362 个 vector type、360 个普通源码 intrinsic call 和 45 个 comment hint SHALL 保持可追溯
- **AND** 计数差异 SHALL 指向具体文件/span 和 baseline 条目

#### Scenario: 验收 AVX 宏关系
- **WHEN** qualification 分析两个本地头文件中的人工审计宏
- **THEN** 12 个函数式宏定义 SHALL 被识别为 definition 而非 call
- **AND** replacement body 的 18 个终端 intrinsic 引用 SHALL 具有独立位置和代表性跨文件 proof path

#### Scenario: 遇到 Makefile 编译参数
- **WHEN** AVX 项目包含 4 个 Makefile 中人工审计的 24 个 x86 flag occurrence
- **THEN** 本 capability SHALL 明确将其保留为后续 Build Selection 范围
- **AND** 当前 graph 完整性 MUST NOT 声称已覆盖这些构建事实

### Requirement: Evidence Graph 不得承担构建选择和最终分类职责
Evidence Graph/GraphStore SHALL 只存储和查询 scanner-owned 静态证据关系，不得自行求值 Make/Autoconf/CMake/Meson/RPM/test selection；专用 Build Selection Analyzer MAY 将有 provenance 的选择结果写入同一图，但 scanner MUST NOT 执行项目代码、compiler、配置、构建或测试，也 MUST NOT 在图层产生最终 blocking、severity 或 RISC-V readiness。

#### Scenario: Build Selection Analyzer 提供完整选择关系
- **WHEN** 专用 analyzer 证明某源码、参数或依赖对目标 RISC-V selected/inactive
- **THEN** GraphStore SHALL 保留 relation status、Evidence 和 proof sequence
- **AND** GraphStore MUST NOT 自行升级、覆盖或重新求值该状态

#### Scenario: 关系存在但目标选择仍未知
- **WHEN** x86 实现具有 include、macro、sibling 或部分 build relation 但缺少完整选择 proof
- **THEN** AnalysisSnapshot SHALL 保留关系并将目标可达性保持 unknown/partial
- **AND** Analyzer MUST NOT 猜测该实现会或不会进入 RISC-V 产物

#### Scenario: 项目包含可执行构建构造
- **WHEN** 输入需要执行 shell、Make、M4、CMake、RPM、plugin、response file 或项目测试才能消解
- **THEN** scanner SHALL 返回 unsupported/unknown Diagnostic
- **AND** scanner 和测试 MUST NOT 执行该构造

### Requirement: Evidence Graph 必须隔离 Legacy 并通过独立容器测试
新 GraphStore、Graph Analyzer、relation/proof 模块及其测试 MUST NOT 导入 Legacy parser/evaluator/YAML 或 Legacy DTO；每个新增或实质修改业务模块 SHALL 映射到隔离单元测试，在唯一 `kb-scanner-test` 容器中通过至少 90% line / 80% branch 覆盖门禁，并 SHALL 通过明确的时间/内存基准。

#### Scenario: 审计新模块依赖
- **WHEN** 架构测试检查 graph、analyzer、frontend macro 和 normalization 模块的 import
- **THEN** 它们 MUST NOT 引用 legacy adapter、旧 parser、旧 rule evaluator、旧 report 或 YAML runtime
- **AND** 默认 CLI MAY 继续通过隔离的 compatibility adapter 使用 Legacy

#### Scenario: 运行隔离单元门禁
- **WHEN** 独立测试容器验证本 capability
- **THEN** test inventory SHALL 为每个业务模块列出 fake/mock 边界和对应 unit suite
- **AND** 真实 parser、真实 knowledge、AVX integration 和性能测试 MUST NOT 被计入隔离单元覆盖数字

#### Scenario: 运行图存储基准
- **WHEN** 容器执行合成图和 AVX fixture 基准
- **THEN** 输出 SHALL 记录版本、Entity/Relation 规模、时间、峰值 RSS 和遍历预算
- **AND** 超过批准预算 SHALL 使验收失败而不是改变 core/report 合同规避问题

### Requirement: Evidence Graph 必须表达测试资产与覆盖候选关系
组合 Graph Analyzer SHALL 为 test suite、test target、test source 和 coverage candidate 建立稳定 Entity，并 SHALL 通过 `contains_test`、`selects_test`、`exercises`、`covers_candidate` 与 `alternative_test_for` Relation 连接已有 source/build Entity；所有关系 MUST 引用有效 Evidence/endpoint，并 SHALL 保留 configuration、selection status、confidence 和完整性。

测试资产与选择分析 SHALL 在没有源码 proof 需求时继续执行，并 SHALL 按各阶段新增关系/proof 数量计算原有预算；继承图数量 MUST NOT 挤占本阶段额度，数值上限与 unknown/partial 判定 SHALL 保持不变。

#### Scenario: 测试分析继承大量无关源码图
- **WHEN** 相同测试事实接收不同数量的无关继承关系或 proof
- **THEN** 本阶段新增链路、局部预算截断和 Diagnostic SHALL 一致
- **AND** 无源码 proof 需求 MUST NOT 使测试分析被跳过或 readiness 升级

#### Scenario: selected test target 使用 x86 依赖
- **WHEN** build graph 和测试角色 Evidence 可连接 RISC-V selector、test target、test source 与 knowledge-backed x86 dependency
- **THEN** AnalysisSnapshot SHALL 包含有界且完整的 selector-to-test-dependency ProofPath
- **AND** Classifier SHALL 只消费该 proof，不得在图层重新推断状态

#### Scenario: 实现与测试具有显式关系
- **WHEN** target/source/call/metadata Evidence 明确关联一个 RISC-V/portable implementation 与测试
- **THEN** Graph Analyzer SHALL 建立 `exercises` 或 `covers_candidate` 关系并保留依据
- **AND** GraphStore MUST NOT 将 coverage candidate 自行升级为测试已执行或通过

#### Scenario: 实现和测试只有名称相似
- **WHEN** 两个资产缺少 target、source、call 或 metadata 关系
- **THEN** Graph Analyzer SHALL 不建立确定 coverage relation
- **AND** 缺失关系 SHALL 保持 unknown，而不是被解释为 covered 或 gap

#### Scenario: 测试图超过预算或形成循环
- **WHEN** 测试/实现/target 关系超过 max depth、visited、paths 或形成循环
- **THEN** proof resolver SHALL 有界终止并保留已有关系与 truncated reason
- **AND** Classifier/Assessor MUST NOT 将截断路径升级为确定结论

### Requirement: Evidence Graph 必须向下游提供可闭合的引用子图
Evidence Graph SHALL 确保每个供 Detection/Classification/Projection 使用的 Relation 和 ProofPath 均可解析到其 source、target 及中间 Evidence/Entity，并 SHALL 以稳定 reason 标记缺失、冲突和预算截断。完整引用对象 MUST 可由 snapshot reference index 获得，而不能只暴露悬空 ID。

#### Scenario: 宏替换链完整
- **WHEN** 调用点经宏定义到终端 x86 intrinsic 的所有对象和关系均已恢复
- **THEN** Graph SHALL 提供包含调用 Evidence、macro definition Evidence、terminal symbol Evidence 和全部 relation ID 的 complete proof
- **AND** 下游 SHALL 能在不读取源码的情况下投影全部位置

#### Scenario: 关系引用对象缺失
- **WHEN** Relation 或 ProofPath 引用不存在的 Evidence/Entity
- **THEN** Graph SHALL 将该路径标记为 partial/failed 并提供稳定 reason 和断裂 ID
- **AND** 下游 MUST NOT 将其视为 complete reachability

### Requirement: 重复宏定义必须按可见性和配置保守消歧
Graph Analyzer SHALL 使用 translation unit/include 可见性、configuration identity、定义位置和结构化 macro identity 对重复宏定义候选消歧。只有唯一可见定义或多个语义等价定义时 SHALL 形成 complete definition relation；非等价候选仍然存在时 MUST 保持 ambiguous/unknown。

#### Scenario: 同名宏在当前配置只有一个可见定义
- **WHEN** configuration 和 include/definition 顺序证明唯一候选对调用点可见
- **THEN** Analyzer SHALL 建立 complete call-to-definition Relation 和 ProofPath
- **AND** Classification MAY 使用该 proof 判断调用可达性

#### Scenario: 多个非等价定义仍可见
- **WHEN** 过滤后仍有两个或以上非等价定义且无法证明实际选择
- **THEN** Analyzer SHALL 保留全部候选引用并标记 ambiguous/unknown
- **AND** 它 MUST NOT 通过输入顺序选择第一个定义

### Requirement: 图闭包和宏消歧必须通过修正后的 AVX 基线与单元门禁
人工 AVX baseline SHALL 以真实 token 起点和完整 span 为准，并 SHALL 覆盖 12 个函数式宏定义、18 个 replacement 终端引用及其调用关系。本 change 修改的 reference closure、macro resolver 和 relation diagnostic producer SHALL 各自映射隔离单元测试，在 `kb-scanner-test` 容器中达到每模块至少 90% line / 80% branch。

#### Scenario: 人工基线含错误列号
- **WHEN** 基线列号与源码中 token 的真实起点不一致
- **THEN** 基线 SHALL 被人工修正并记录为 baseline correction
- **AND** scanner MUST NOT 为迁就错误基线而改变正确 span

#### Scenario: 运行图模块门禁
- **WHEN** 独立容器运行 graph unit inventory 和 AVX component test
- **THEN** 隔离 unit SHALL 先满足逐模块覆盖门槛，AVX 对照 SHALL 再验证所有 definition/replacement 引用
- **AND** 真实 parser 集成结果 MUST NOT 被计入隔离单元覆盖率

### Requirement: 枚举选择必须形成有界的声明—引用—守卫证据链
Evidence Graph Analyzer SHALL 为可验证 enum declaration、member、reference 和 selection condition 建立稳定 Entity 与 `defines`、`contains`、`selects`、`guarded_by` 关系，并 SHALL 将条件保护的下游 call/type/include/asm Evidence 纳入同一有界 proof closure。Analyzer MUST NOT 求值任意常量表达式、实例化模板或从成员名称猜测目标选择状态。

#### Scenario: if constexpr 保护 x86 调用
- **WHEN** enum member reference 出现在 if constexpr condition 中且 consequence 包含 knowledge-backed x86 调用
- **THEN** Graph SHALL 连接 file、enum type、member、condition 和 x86 call，并产生可解析 proof path
- **AND** 若模板参数取值未知，condition 到目标选择的状态 SHALL 保持 unknown

#### Scenario: switch case 选择不同后端
- **WHEN** switch/case 分别引用 x86、RISC-V 或 generic enum member并保护不同实现
- **THEN** Graph SHALL 为各 case 建立独立 selection predicate、guarded implementation 和 sibling/alternative role
- **AND** ARM-only case MAY 作为上下文保留，但 MUST NOT 单独形成 x86-to-RISC-V Finding

#### Scenario: declaration binding 唯一
- **WHEN** Tree-sitter 局部索引或 Clang semantic reference 唯一连接 member use 与 declaration
- **THEN** 对应 relation SHALL 为 complete，并保留 declaration/reference Evidence IDs
- **AND** 输入与文件遍历顺序改变 MUST NOT 改变 Entity、Relation 或 ProofPath ID

#### Scenario: declaration binding 歧义或缺失
- **WHEN** 非限定 member reference 对应多个声明、声明位于不可解析外部头文件或引用类型冲突
- **THEN** Graph SHALL 保留全部可验证候选并将 relation/proof 标记为 ambiguous、partial 或 unknown，附稳定 reason
- **AND** 它 MUST NOT 输出悬空引用或伪造 complete primary path

#### Scenario: 未实例化模板
- **WHEN** enum member 出现在依赖模板参数的 constexpr condition 中但没有可验证实例化或 build selection
- **THEN** Graph SHALL 证明语法 guard 和下游依赖关系，但 selection status SHALL 保持 unknown
- **AND** 未出现实例化 Evidence MUST NOT 被解释为 RISC-V 不会进入该分支

#### Scenario: enum graph 超过资源预算
- **WHEN** enum declaration/reference/condition closure 出现循环或超过 depth、visited、path budget
- **THEN** Analyzer SHALL 确定性截断并产生 partial proof 与结构化 Diagnostic
- **AND** 已验证局部链路 SHALL 保留，截断 MUST NOT 被解释为没有迁移风险

### Requirement: 命中上游闭包必须按 occurrence 和配置有界查询
Evidence Graph SHALL 向下游提供以当前 matched Evidence、occurrence 和 configuration 为锚点的相关子图，保留宏调用/展开、条件保护、include 可见性及已有构建作用证明。查询 SHALL 复用事实需求计划和统一入/出边索引，按关系语义进行上游查询与必要的终端展开，MUST NOT 恢复全 root×terminal 搜索或按每条 Finding 重扫全图。

#### Scenario: 命中宏替换中的 intrinsic
- **WHEN** 终端 intrinsic 的 Evidence 位于本地宏 replacement 中且存在可验证调用与外层 guard
- **THEN** 子图 SHALL 包含实际 definition、replacement、invocation、guard 的完整来源与精确端点
- **AND** 多级同 kind 节点 SHALL 分别保留，未出现调用的定义 MUST NOT 被伪造为已调用

#### Scenario: 不同配置共享头文件
- **WHEN** 同一头文件的宏被不同目标或配置引用
- **THEN** 查询 SHALL 保留各自调用、条件和构建来源，不用一个配置的 selected 状态覆盖另一个
- **AND** 未确认 target membership 的路径 SHALL 保持 unknown，不得按宏同名跨目标连线

#### Scenario: 查询遇到循环或预算
- **WHEN** 上游或终端展开遇到循环、缺失引用或 depth/visited/path 上限
- **THEN** 子图 SHALL 保留已验证局部节点和关系，记录稳定原因和实际预算计数
- **AND** 局部截断 MUST NOT 删除原始 Fact、放宽原图预算或被解释为安全

### Requirement: 源码上游关系必须可精确映射展示端点
Graph Analyzer SHALL 为供源码链消费的 macro/condition/build/source 关系提供明确 Entity 到 Evidence 的端点映射与必要配置来源，不要求每个抽象 Entity 都有伪造位置。折叠结构节点的投影 SHALL 能追溯连续 Relation sequence；未知或非唯一映射 SHALL 显式保持 partial/ambiguous。

#### Scenario: 两个普通同类节点没有直接关系
- **WHEN** 两个 source Evidence 仅因 kind 相同被查询到
- **THEN** Graph SHALL 不新增 contains/calls/alternative_to 等无依据关系
- **AND** 下游可以保留各节点，但不得将它们当作一条完整路径

#### Scenario: 无位置的配置实体连接代码
- **WHEN** 合法关系经过没有源码 span 的配置/结构 Entity
- **THEN** Graph SHALL 提供真实关系序列供下游折叠或解释断点
- **AND** 下游 MUST NOT 复制另一 Evidence 的位置给该抽象实体

#### Scenario: 需求子图规模增长
- **WHEN** 在相同命中和相关子图之外增加大量无关图节点
- **THEN** 索引构建 SHALL 一次完成，查询 SHALL 按需访问相关关系，且相关查询结果及预算语义保持一致
- **AND** 性能回归 SHALL 记录访问计数、时间和内存，不以最终 Finding 条数代替查询正确性

### Requirement: 家族成员关系必须与执行和替代证明隔离

Graph SHALL 支持 architecture_family 实体及 candidate_member_of 结构关系，复用现有 source file 身份并保存路径规则 provenance。候选成员边 MUST NOT 被执行可达性、宏调用、alternative proof 或源码主链查询当作执行关系；名称相似 MUST NOT 生成 alternative_to。没有源码 Evidence 的结构来源 MUST NOT 伪造 Evidence ID 或行号。

#### Scenario: 只有路径相似

- **WHEN** 两个文件形成 x86/generic 路径家族但没有现有选择或 sibling proof
- **THEN** SHALL 仅记录候选成员关系，其选择及替代可用性为 unknown
- **AND** 从 x86 fact 进行执行依赖遍历 MUST NOT 经家族边到达 generic 文件

#### Scenario: 复用已有完整证明

- **WHEN** 现有真实 source/build/sibling proof 与家族成员端点及 configuration 精确对应
- **THEN** SHALL 将有效 proof 绑定到相应成员并保留其既有状态和原始 Evidence
- **AND** MUST NOT 因家族标签补齐缺失端点、跨配置借用 proof 或扩大证明范围

#### Scenario: 两个实现共同编译

- **WHEN** 两个成员都属于同一 target 但没有互斥选择证据
- **THEN** SHALL 保留各自选择状态，不因同 target 或同名函数建立替代证明

#### Scenario: 悬空或歧义绑定

- **WHEN** 候选 proof 引用不存在的实体或不能唯一对应成员
- **THEN** SHALL 拒绝无效绑定并输出诊断/unknown，保留原有有效图和路径观察

### Requirement: 函数版本成员必须与执行及替代证明隔离

Graph SHALL 保存函数版本组、属性 owner、真实函数体和非执行成员关系及 provenance。版本共存、相同签名或 default 标签 MUST NOT 自行生成 alternative_to、selected 或 inactive proof；已有精确 source/build 证明 SHALL 按 occurrence/configuration 绑定且不扩大范围。

#### Scenario: Default 与 AVX 版本共存
- **WHEN** 组中有两个真实版本定义但缺少目标选择证明
- **THEN** SHALL 保留成员和源码关系并将目标选择保持 unknown
- **AND** 执行可达性遍历 MUST NOT 通过成员边到达另一版本或据此排除 AVX

#### Scenario: 自动 clone 与真实来源
- **WHEN** 单个 target_clones 属性描述多个 compiler 生成版本
- **THEN** SHALL 关联同一真实 source body 与属性来源
- **AND** MUST NOT 伪造 clone/resolver 的源码 Evidence、调用点或行号

#### Scenario: 绑定缺失或跨配置
- **WHEN** proof 端点缺失、body 归属不唯一或属于不同 configuration
- **THEN** SHALL 拒绝该绑定，保留有效局部结构及 unknown 原因
- **AND** 既有无关完整 proof SHALL 不被改写或清除

### Requirement: 用途证明必须保持非执行性质与可核查闭包

Evidence Graph SHALL 保存候选使用、绑定、控制、逃逸及 semantic role 的真实 provenance，自动 role proof SHALL 引用完整的作用域摘要和支持闭包。用途关系 MUST NOT 直接进入执行可达、alternative 或构建选择判定；单一无依据 source_file 到 role 边不得构成自动排除证明。

#### Scenario: 完整纯数据用途

- **WHEN** Analyzer 已闭合候选全部相关使用
- **THEN** Graph SHALL 提供精确 fact/subject/configuration/root 的 role relation、非空完整 ProofPath 和可核查的使用计数及支持引用
- **AND** 原始执行 graph/proof SHALL 保持，不被用途关系替换

#### Scenario: 只有部分数据来源

- **WHEN** 输入可证明 selector 来源于数据但无法解释其受控调用
- **THEN** Graph SHALL 保存局部来源与 unknown 断点
- **AND** MUST NOT 生成 scopeComplete=true 或伪造 selected/alternative_to

### Requirement: 用途引用和预算必须在消费前闭合

Graph 与消费边界 SHALL 验证 proof 连续端点、对应 role relation、支持引用、统计一致性和 truncated 状态。重复、悬空、跨配置、部分角色或冲突用途 MUST NOT 被升级为完整排除。

#### Scenario: Proof 标 complete 但实际截断

- **WHEN** proof.truncated 为 true、缺少对应 role relation、支持范围不完整或使用计数不一致
- **THEN** SHALL 拒绝排除并保留原候选与诊断
- **AND** 不得仅相信 scopeComplete 或 complete 字符串

### Requirement: 宏作用环境必须按 TU 调用时状态与可行分支合流
Analyzer SHALL 按 TU/configuration、include/definition 顺序与调用 occurrence 解析宏，区分 known defined、explicitly undefined、unknown/conflicting；源码中缺少定义 MUST NOT 单独证明 undefined。对象别名 SHALL 按使用时环境求值，支持受限整数、括号、defined、!、&&、||、==、!= 条件，超出语义边界 SHALL unknown。if/elif/else SHALL 按 first-match 和可行路径分别推进，合流包括未执行任何分支的路径。

#### Scenario: 对象宏别名晚绑定
- **WHEN** A 的 replacement 为 B，B 在 A 的两个使用点之间被重定义或取消
- **THEN** 两处 A SHALL 分别使用当时的 B 状态及来源，不能缓存为定义 A 时的值
- **AND** 别名循环或未知外部 B SHALL 保持 unknown

#### Scenario: 相同分支状态与冲突状态
- **WHEN** 未知条件的所有可行分支均定义同值宏，或其中一支定义不同值/不定义
- **THEN** 前者 SHALL 合流为可证明的相同状态并保留所有来源，后者 SHALL 保留 unknown/conflicting
- **AND** inactive 分支的 define/undef SHALL 不改变可达环境

#### Scenario: 定义存在性与布尔条件
- **WHEN** 已证明 `-DFEATURE=0` 且源码测试 `defined(FEATURE)`、`FEATURE` 或与其他条件组合
- **THEN** SHALL 区分已定义性和数值真假，使用受限表达式语义及明确来源
- **AND** 未知整数行为或不支持表达式 SHALL 不被强制求值

#### Scenario: 重复 include 与未知 include
- **WHEN** 同一头文件在不同宏环境下重复包含，或者遇到未解析的 include
- **THEN** Analyzer SHALL 按当前 TU 状态处理重复包含，仅在完整 guard/pragma once 证明下跳过
- **AND** 未知 include 的潜在宏副作用 SHALL 使相关确定性失效，不能简单沿用旧状态

### Requirement: 固定参数宏传递必须绑定真实调用和终端事实
Analyzer SHALL 对固定参数、完整边界、无 #/##/变参的受支持宏建立实参→形参引用→replacement/嵌套调用的可核查关系，按调用时可见定义处理标识符、整数及其括号包装。终端 x86 符号 SHALL 通过正式 Knowledge/Fact/Observation 路径识别，宏定义存在或参数名称相同 MUST NOT 构成实际调用证明。

#### Scenario: 实参提供 intrinsic 名称
- **WHEN** `OUTER(_mm256_add_epi32, x, y)` 经固定参数包装最终调用该实参
- **THEN** scanner SHALL 保留实参位置、参数声明/引用、各层调用/定义和终端知识来源的关系
- **AND** 不得因初始 replacement 仅为参数名而遗漏已证明的 x86 终端

#### Scenario: 不同调用传入不同终端
- **WHEN** 同一包装分别接收 x86 intrinsic 和普通函数名
- **THEN** Analyzer SHALL 保持每次调用的参数及作用身份，不把一处 x86 证明复制到另一处
- **AND** 普通函数的通用性或 RISC-V 等价性 SHALL 不因命名被确认

#### Scenario: 不支持展开或没有调用
- **WHEN** 参数绑定存在歧义、递归、变参、token pasting、stringification 或宏未被调用
- **THEN** 原事实 SHALL 保留，仅提供局部链及对应断点，不构造完整执行证明

### Requirement: 宏作用图必须按需求复用索引并独立计量预算
Analyzer SHALL 使用原始 facts、宏调用和构建绑定确定需求，按 TU/configuration 复用有序事件及作用索引，不逐 Finding 全项目重扫。每 TU 事件 100000、宏展开深度 32、单调用展开 token 4096、扫描新增作用关系 100000 SHALL 作为本轮硬上限；继承旧图不计入新增关系额度。现有源码链 depth=16/visited=256/paths=32 SHALL 保持，所有截断 SHALL 有稳定原因及计数。

#### Scenario: 新终端尚未形成 Finding
- **WHEN** 宏实参经展开才能发现 x86 终端，而初始 detector 尚无对应 Finding
- **THEN** 需求选择 SHALL 仍能从宏调用事实启动该有界分析，不以已有 Finding 为唯一入口

#### Scenario: 同名宏跨 TU 和配置
- **WHEN** 两个 TU 使用同名头文件宏但环境或构建参数不同
- **THEN** 状态缓存、关系及 proof 消费 SHALL 逐 TU/configuration 隔离
- **AND** baseline/default provenance MUST NOT 充当跨配置拼接 complete 路径的通配证明

#### Scenario: 查询和生成耗尽预算
- **WHEN** include 环、展开或查询达到硬上限
- **THEN** scanner SHALL 保留原始 Fact/Evidence 与已验证局部关系，记录实际使用量/上限并返回 partial/unknown
- **AND** 不完整作用证明 MUST NOT 降低已有 confirmed x86 结论，亦不得冒充 non_execution_data 或替代实现证明
