## MODIFIED Requirements

### Requirement: RPM 必须由新轻量 Frontend 静态恢复架构选择
正式 RPM adapter SHALL 在新实现模块中恢复 section、package/subpackage、`%ifarch/%ifnarch`、有界宏条件、`ExclusiveArch/ExcludeArch`、依赖和构建/检查 section provenance，并 SHALL 将其转换为 scanner-owned Evidence；它 MUST NOT 导入或修改 Legacy parser，不得使用完整 RPM/specfile 求值环境。它 SHALL 覆盖 RB-0002、RB-0003、RB-0004 的架构相关事实，且 MUST NOT 因候选可能是目标适配数据、inactive 或无法判断而删除原始事实。

#### Scenario: RPM 条件依赖包含 RISC-V 分支
- **WHEN** spec 的受支持架构条件为 RISC-V 选择 BuildRequires/Requires/Recommends 或 section
- **THEN** Analyzer SHALL 建立 package architecture selector 到依赖/section 的选择关系
- **AND** 互斥 x86 条目 SHALL 保留 Evidence 并仅在排除证明完整时标记 inactive

#### Scenario: RPM 架构约束排除 RISC-V
- **WHEN** 激活的 `ExclusiveArch`/`ExcludeArch` 的完整静态值证明目标 RISC-V 不被允许
- **THEN** scanner SHALL 产生可追溯的目标路径缺口 Observation
- **AND** 最终 severity/blocking SHALL 留给后续 Classifier；未知宏或未激活的约束 MUST NOT 被解释为确定排除目标

#### Scenario: RPM 包含 shell Lua 或 include
- **WHEN** spec 包含非精确 uname 白名单的 shell expansion、Lua、动态宏或 include
- **THEN** scanner SHALL 保留可定位 Evidence 并把依赖未知值或副作用的选择标记 unknown
- **AND** scanner MUST NOT 初始化 RPM、加载 include 或执行宏；精确 `%(uname -m)` SHALL 仅按目标值符号化，不执行命令

### Requirement: uname 架构探测必须按目标值静态替换且不建模误选
scanner SHALL 将精确、无包装的 `uname -m` 识别为 architecture selector，并 SHALL 在不执行命令的情况下以 ScanContext 的规范化 `riscv64` 或 `riscv32` 目标值进行符号求值；使用 probe 本身 MUST NOT 形成 Finding，且 scanner MUST NOT 建立交叉编译环境误选 x86 分支的路径。RPM 的路径缺口判断 SHALL 额外满足同一完整条件组及必需选择的证明门槛，不能把可选优化未匹配自动解释为项目缺少 RISC-V 支持。

#### Scenario: uname selector 具有 RISC-V 分支
- **WHEN** 完整选择结构包含匹配目标的 RISC-V branch
- **THEN** scanner SHALL 将该 branch 标记 selected 并把互斥 x86 branch 标记 inactive
- **AND** proof SHALL 从 uname Evidence 连接到 RISC-V branch 与其选择项

#### Scenario: uname selector 只有通用 fallback
- **WHEN** 结构没有 RISC-V 专用 branch 但具有对目标实际匹配的通用 fallback branch
- **THEN** scanner SHALL 选择通用路径并把互斥 x86 branch 标记 inactive
- **AND** scanner SHALL 继续分析通用路径中的源码、参数和依赖，而不是仅凭 generic/portable/scalar 名称确认匹配

#### Scenario: uname selector 缺少可用路径
- **WHEN** 完整结构只有 x86 branch 且没有 RISC-V 或通用 fallback，并且 RPM 场景中已证明这是必需的目标选择
- **THEN** scanner SHALL 产生 `missing_riscv_selection_path` Observation
- **AND** Observation MUST NOT 声称 RISC-V 会选择 x86 branch

#### Scenario: RPM 可选优化只在 x86 执行
- **WHEN** 完整 RPM 脚本条件只在 x86 设置可选优化，而不能证明该选择是目标构建的必需路径
- **THEN** scanner SHALL 保留 x86 分支及其 inactive 证据
- **AND** 它 MUST NOT 仅因没有 RISC-V 分支输出确定缺口或项目 ready；必需性不明时相关推断 SHALL 保持 unknown

#### Scenario: uname 命令形状不精确
- **WHEN** probe 带 wrapper、管道、重定向、环境前缀、额外命令或未知参数
- **THEN** scanner SHALL 将其保持 unsupported/unknown
- **AND** scanner MUST NOT 执行命令或猜测输出

### Requirement: 构建选择实现必须通过人工基线和独立单元测试门禁
本 capability SHALL 使用版本化、scanner 不可自动重写的人工选择 baseline 验证 selector、分支、源码、参数、依赖和 target proof；每个新增或实质修改业务模块 SHALL 映射到隔离单元测试，并 SHALL 在独立 `kb-scanner-test` 容器中通过每模块至少 90% line / 80% branch 覆盖门禁、无副作用门禁和完整回归。真实语法组件测试和端到端数量 MUST NOT 替代隔离单元覆盖。

#### Scenario: 验收 AVX Makefile 参数
- **WHEN** qualification 扫描阶段 5 baseline 中 4 个 Makefile
- **THEN** 人工审计的 24 个 x86 flag occurrence SHALL 全部具有准确 SourceSpan 和选择 provenance
- **AND** 每项 SHALL 根据可用构建证据标记 selected、inactive 或 unknown，而不是继续无说明 deferred

#### Scenario: 审计模块测试清单
- **WHEN** 新增、删除或重命名 build frontend、evaluator、normalizer、analyzer、detector 或组合器模块
- **THEN** test inventory SHALL 同步映射隔离 unit suite 与 fake/mock 边界
- **AND** 缺失映射或任一模块覆盖率低于门槛 SHALL 使容器测试失败

#### Scenario: 验证恶意输入和兼容合同
- **WHEN** 容器扫描包含 Make/M4/CMake/RPM 命令构造的 fixture 并运行隔离/输出 regression
- **THEN** marker 文件、workspace 和外部状态 SHALL 无副作用，且 scanner 不启动项目命令
- **AND** 默认 Schema V2、显式 Schema V1、三个 artifact、两份 compiler facts 及冻结 YAML/`generatedSet` 参考资产 SHALL 保持原有合同；冻结参考 MUST NOT 回到默认运行时

#### Scenario: RPM 每层都有独立人工预期
- **WHEN** 验收 RB-0002/3/4
- **THEN** 测试 SHALL 分别比较事实、位置、宏来源、条件状态、关系/Proof、Finding 影响及 V1/V2 投影
- **AND** 单测 SHALL fake 原生语法、读取与进程边界，真实 Bash parser 测试 SHALL 单独作为组件测试运行

## ADDED Requirements

### Requirement: RPM 宏必须保留目标配置来源与三态定义语义
RPM 宏层 SHALL 识别 `_arch`、`_target_cpu`、`_isa`、`__isa_name` 及普通/可选/条件宏引用，区分已知值、确定未定义和 unknown；SHALL 记录每个定义与引用的原始位置、求值时机及目标 profile 来源。受限 `%global/%define`、别名、覆盖和分支合流 SHALL 有确定性语义；未核实 profile、动态/参数化宏、歧义、递归或预算截断 MUST 保持 unknown，MUST NOT 读取宿主 RPM 配置或执行展开。

#### Scenario: 目标宏条件比较 x86
- **WHEN** 受支持 profile 已证明 `_target_cpu` 为 riscv64，条件为其与 x86_64 的字符串相等比较
- **THEN** 条件 SHALL 为假，并保留目标 profile、宏引用和比较 Evidence
- **AND** 该分支下 x86 依赖 SHALL 为 inactive，完整 else 分支 SHALL 可为 selected

#### Scenario: 可选宏的定义状态未知
- **WHEN** `%{?_isa}` 的 definedness 或值无法证明
- **THEN** 宏 SHALL 保留 unknown 及原因
- **AND** scanner MUST NOT 以空字符串、宿主 ISA 或猜测的 RISC-V ISA 代替未知值

#### Scenario: 宏在不同可达分支定义不同值
- **WHEN** 宏值来自两个未能排除且不等值的条件定义
- **THEN** 合流后的值 SHALL 为 unknown 并引用各定义
- **AND** scanner MUST NOT 用最后一条文本定义覆盖其它可达定义

#### Scenario: global 与 define 的展开时机不同
- **WHEN** 已知非参数宏别名在定义后、引用前发生可证明的重新定义
- **THEN** 宏求值 SHALL 按受支持的即时/使用时语义分别记录有效值及定义链
- **AND** 无法实现精确作用域或求值时机的输入 SHALL 降级为 unknown，而非选择任意一个值

### Requirement: RPM 条件栈必须保留互斥和未知状态
RPM 条件求值 SHALL 支持有界 `%if/%elif/%else/%endif` 与 `%ifarch/%ifnarch`，保留父条件和先行分支排除依据。每个依赖、参数、section 和架构约束 SHALL 继承自己的完整条件路径；selected 需要所有必要条件成立，inactive 需要完整的排除证据，剩余情况 SHALL 为 unknown。

#### Scenario: 普通 if 与 else 包含互斥依赖
- **WHEN** 同一完整 RPM 条件组中的 if/else 分别声明两个依赖
- **THEN** 两者 MUST NOT 因普通 if 未识别而同时无条件 selected
- **AND** 无法求值的条件 SHALL 使相关路径保持 unknown，而不是忽略条件

#### Scenario: elif 已有先行命中
- **WHEN** 某个先行条件已为真
- **THEN** 之后的 elif/else SHALL 因先行命中被排除
- **AND** 图中 SHALL 保留排除依据，不能只取当前表达式真假

#### Scenario: 未知嵌套条件在已排除父路径下
- **WHEN** 外层条件完整证明为假而内层宏 unknown
- **THEN** 子项 SHALL 可按外层证明标记 inactive，同时保留内层未知事实
- **AND** 未知事实 MUST NOT 反过来生成 selected proof

#### Scenario: 条件结构损坏
- **WHEN** 缺失 endif、孤立 else、重复 else 或超出条件预算影响局部结构
- **THEN** adapter SHALL 给出定位 Diagnostic 并使受影响路径 partial/unknown
- **AND** 它 MUST NOT 将恢复后的未证明条目作为顶层 selected

#### Scenario: 未激活的架构限制
- **WHEN** ExcludeArch 位于完整 inactive 分支内，或其宏值 unknown
- **THEN** scanner MUST NOT 将其解释为当前 package 已确定排除 RISC-V
- **AND** 约束激活状态与目标许可状态 SHALL 分别保留

### Requirement: RPM Shell selector 必须保持原始位置与有界数据流
RPM Frontend SHALL 恢复 `%prep/%build/%install/%check` 的脚本边界、嵌套 RPM 条件及 package identity，识别精确 RPM/Shell uname 形式并以规范化目标值符号化。受支持变量赋值、if/elif/else 和 case SHALL 与受控源码/参数建立真实关系；未知展开或副作用影响的数据流 MUST 为 unknown，不得执行输入。

#### Scenario: RPM 命令宏定义 uname 值
- **WHEN** 静态宏定义使用精确 `%(uname -m)` 并被后续受限条件引用
- **THEN** scanner SHALL 建立 probe → 宏定义 → 宏引用 → 条件的目标选择链
- **AND** 系统 MUST NOT 启动 uname 或 RPM 进程

#### Scenario: 脚本 case 选择 RISC-V 参数
- **WHEN** `%build` 中变量来自精确 `$(uname -m)` 或反引号形式，并由完整 case 匹配目标分支
- **THEN** scanner SHALL 按 first-match 语义选择分支并保留其中的参数事实
- **AND** case 后的通用 `*` MUST NOT 与已匹配分支同时 selected；所有位置 SHALL 指回原 spec

#### Scenario: RPM 预处理与脚本文本边界
- **WHEN** comment、字符串、转义或 here-document 包含 RPM 宏/directive、uname 或依赖形状文本
- **THEN** parser SHALL 先按受支持的 RPM 预处理语义，再按 Shell 语法区分生效构造与纯文本；MUST NOT 以 Shell 引号屏蔽 RPM 层本应处理的构造
- **AND** 预处理或语法边界不确定时 SHALL 返回 partial，而非把剩余纯文本伪造成完整 Shell selector

#### Scenario: 选择变量可能被未知命令改变
- **WHEN** 动态宏、eval、循环或其它不支持副作用可能影响被查询的变量或脚本结构
- **THEN** 依赖该值的选择 SHALL 为 unknown，并保存未知点与先前赋值来源
- **AND** scanner MUST NOT 仅凭文本中较早的 uname 赋值继续给出 complete proof

### Requirement: RPM 依赖宏必须区别于固定 x86 依赖
依赖前端 SHALL 恢复 Requires、BuildRequires、Recommends 的逐 occurrence 原文、限定符、版本条件、宏引用、package/subpackage 及外层条件。后续分析 SHALL 区分目标适配依赖、知识或规范化限定证明的 x86 依赖、仅名称候选及未知项；MUST NOT 根据宏存在或包名推测包内机器码、包可用性或必需性。

#### Scenario: 依赖使用目标 ISA 宏
- **WHEN** `Requires: libfoo%{?_isa}` 的完整 profile 证明该限定随 RISC-V 目标展开
- **THEN** scanner SHALL 保留依赖和宏事实，并在后续分析中避免把该 occurrence 当作固定 x86 问题
- **AND** 它 MUST NOT 声称 libfoo 的 RISC-V 包一定存在或项目已 ready

#### Scenario: Recommends 含架构宏
- **WHEN** Recommends 中存在架构宏或明确架构限定
- **THEN** scanner SHALL 提取依赖并保留 soft dependency 语义
- **AND** Classifier MUST NOT 仅凭该软依赖与 selected 状态输出必需依赖阻塞

#### Scenario: 依赖宏未知但不含 x86 字面词
- **WHEN** 依赖包含受关注的架构宏但其值无法证明，且包名不含 x86
- **THEN** scanner SHALL 仍识别架构相关事实并输出适用的 unknown 候选及缺少的证据
- **AND** Detector MUST NOT 仅因没有命中 x86 字符串而静默漏掉该不确定项

#### Scenario: 同名依赖出现在不同子包或条件
- **WHEN** 相同依赖分别位于 selected、inactive 和 unknown 路径或不同子包
- **THEN** 每个 occurrence SHALL 保留独立身份、条件状态及 provenance
- **AND** 一个已确认目标适配 occurrence MUST NOT 过滤其它未知 occurrence

#### Scenario: 复杂依赖表达式超出子集
- **WHEN** rich dependency 或宏组合无法完整解析
- **THEN** scanner SHALL 保留原文、位置和 unknown reason
- **AND** 它 MUST NOT 拆出局部 token 后伪装成完整确定依赖

### Requirement: RPM 选择证明必须以条件组和完整路径为边界
RPM Analyzer SHALL 按 package、section、condition group 和 occurrence 连接宏/变量、条件与依赖/参数。完整 ProofPath SHALL 引用全部必要定义、选择和依赖关系；宏未知、路径缺失或预算截断 SHALL 形成显式断点。确定的 missing_riscv_selection_path SHALL 有同一条件组的完备排除和必需性依据，MUST NOT 使用全文件架构角色汇总代替证明。

#### Scenario: 不同条件组分别包含 x86 和 generic
- **WHEN** 两个独立条件组分别出现 x86 分支及 generic 路径
- **THEN** Analyzer MUST NOT 用第二组的 generic 证明第一组存在 fallback
- **AND** 第一组必需性或结构不完整时 SHALL 保持 unknown，而非直接确认为缺口

#### Scenario: 条目仅带 selected 标记但缺少上游
- **WHEN** RPM 条目声称 selected，但依赖的宏/条件引用缺失、歧义或不完整
- **THEN** Analyzer SHALL 拒绝将该标志作为 complete proof 的充分依据
- **AND** 下游 Detector/Classifier SHALL 保留 unknown，不升级为确定 blocker 或已排除风险

#### Scenario: 继承大型源码图
- **WHEN** 相同 RPM 事实分别附加少量或大量无关继承源码关系
- **THEN** RPM 新增关系/proof 的局部预算、截断与语义 SHALL 一致
- **AND** 宏/条件预算或既有局部图预算到限 SHALL 有界终止、保留原因，不得放宽上限

### Requirement: RPM 结果必须保持现有 V2 与显式 V1 合同
RPM 分析 SHALL 投影到既有默认 V2 与显式 V1，不创建新主结果结构。V2 的 fact、occurrences 和 evidenceChain SHALL 保留原始 spec 的源码上下文、命中高亮、完整引用及 unknown breaks；宏/profile/依赖字段细节仅 SHALL 使用既有字段或可选 namespaced extension。GCC/Clang 事实文件、类别、身份及 provenance MUST 不变。

#### Scenario: Finding 详情追溯 RPM 依赖
- **WHEN** 一个 RPM Finding 具有可追溯的 selector、宏定义/引用、条件与依赖
- **THEN** 用户 SHALL 仅用该 Finding 查看主链、各代码 step 的原始行号/上下文及命中位置
- **AND** 不完整链 SHALL 有明确断点，不能复制其它 occurrence 的位置或包含悬空引用

#### Scenario: 输出兼容与安全
- **WHEN** 同一 fixture 分别使用默认模式与显式 V1 输出
- **THEN** 默认 SHALL 为 V2，显式 V1 SHALL 保持原字段类型和三个 artifact 合同
- **AND** HTML SHALL 安全转义 spec 内容；两份 compiler facts SHALL 通过原有哈希与 provenance 回归
