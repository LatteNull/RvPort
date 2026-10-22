## ADDED Requirements

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
Graph Analyzer SHALL 为 project、source file、macro definition、macro invocation、condition group、branch、symbol/call site 和 implementation 建立确定性 Entity，并 SHALL 产生 `defines`、`includes`、`invokes_macro`、`expands_to`、`calls`、`has_branch`、`guarded_by`、`alternative_to` 与 `reachable_from` Relation；所有端点和 Evidence 引用 MUST 存在于同一分析快照。

#### Scenario: 相同输入重复分析
- **WHEN** 使用相同 scanner/knowledge 版本、ScanContext 和源码重复运行 Graph Analyzer
- **THEN** Entity、Relation、ProofPath 的 ID 与排序 SHALL 完全一致
- **AND** 身份材料 MUST NOT 包含机器绝对路径、随机值、对象地址或遍历时序

#### Scenario: 关系引用未知端点
- **WHEN** Relation builder 尝试建立含未知 Entity 或 Evidence ID 的关系
- **THEN** Analyzer SHALL 拒绝该关系并返回 failed Diagnostic
- **AND** 无效引用 MUST NOT 进入 AnalysisSnapshot

### Requirement: Graph Analyzer 必须建立有界的跨文件 include 与宏 proof path
Graph Analyzer SHALL 从同项目 include、macro definition、macro invocation 和 replacement token Evidence 建立可追溯关系，并 SHALL 在显式深度、访问节点数和路径数预算内物化从宏调用点到定义及终端 symbol/intrinsic 的 ProofPath。

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
本 capability SHALL 只表达 C/C++ 静态证据关系，MUST NOT 求值 Make/Autoconf/CMake/RPM/test selection，MUST NOT 执行项目代码、compiler、构建或测试，并 MUST NOT产生最终 blocking、severity 或 RISC-V readiness。

#### Scenario: 关系存在但目标构建选择尚未知
- **WHEN** x86 实现具有 include、macro 或 sibling 关系但缺少构建选择证据
- **THEN** AnalysisSnapshot SHALL 保留关系并将目标可达性保持 unknown/partial
- **AND** Analyzer MUST NOT 猜测该实现会或不会进入 RISC-V 产物

#### Scenario: 项目包含可执行预处理或构建构造
- **WHEN** 输入需要执行 shell、compiler、plugin、response file 或项目测试才能消解
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
