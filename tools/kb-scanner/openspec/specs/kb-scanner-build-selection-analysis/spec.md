# KB Scanner Build Selection Analysis Specification

## Purpose

定义 KB Scanner 在纯静态、无副作用边界内发现并解释 C/C++ 项目的构建与打包选择，形成可追溯的 RISC-V selector、关系、proof 和非最终 Observation，同时保持现有输出兼容。

## Requirements

### Requirement: 构建工作区必须安全且确定地发现受支持输入
正式 Build Workspace/Frontend SHALL 在 ScanContext 的输入和排除边界内发现 Make、Autoconf（包括 config.guess）、CMake 源码（CMakeLists.txt 与普通 .cmake）、已有 CMake/Meson/CTest 机器产物、compilation database 与 RPM spec 输入，并 SHALL 按规范化项目相对路径和输入 kind 确定性排序；它 MUST NOT 跟随逃逸 workspace 的路径或执行发现到的文件。Scanner SHALL 仅复用现有输入目录和编译数据库；MUST NOT 新增 manifest、传参或读取远端构建目录。CMake 源码 SHALL 路由到独立源码 adapter，不与机器 JSON 混淆。

#### Scenario: 项目包含多类构建输入
- **WHEN** workspace 同时包含 C/C++、Makefile、configure、config.guess/config.sub、CMakeLists.txt、普通 .cmake、CMake File API reply、Meson introspection 和 RPM spec
- **THEN** composite workspace/frontend SHALL 把各输入路由到对应正式 adapter
- **AND** C/C++ 文件 SHALL 继续由既有 C/C++ Frontend 处理

#### Scenario: 构建路径逃逸 workspace
- **WHEN** symlink、include 或机器产物绝对路径指向 workspace 外部
- **THEN** scanner SHALL 拒绝读取该目标并产生结构化 Diagnostic
- **AND** 稳定 Entity/Evidence identity MUST NOT 包含机器绝对路径

### Requirement: 构建 Frontend 必须只产生 scanner-owned 可追溯事实
每个构建 adapter SHALL 从静态输入产生带 source span 或 JSON pointer、producer/version、parse mode、confidence 和配置 identity 的 scanner-owned Entity/Evidence；第三方语法节点、边界 model、parser 异常和 Legacy DTO MUST NOT 泄漏到 Normalizer、Analyzer 或 Detector。

#### Scenario: 构建语法可部分恢复
- **WHEN** 输入包含受支持语法和 parser ERROR/MISSING 或未知字段
- **THEN** Frontend SHALL 保留可定位 Evidence 并返回 partial Diagnostic
- **AND** 未恢复部分 MUST NOT 被解释为没有构建选择风险

#### Scenario: 重复扫描相同构建输入
- **WHEN** scanner/parser 版本、ScanContext 和输入字节相同
- **THEN** Entity/Evidence ID、排序和 Diagnostic 顺序 SHALL 相同
- **AND** identity MUST NOT 使用绝对 checkout 根、随机值、对象地址或时间

### Requirement: Make Frontend 与求值器必须实现安全有界语义子集
Make adapter SHALL 使用锁定的 tree-sitter-make 恢复 assignment、condition、include、target 和 recipe 边界；scanner-owned evaluator SHALL 支持字面文本、已知变量引用、`:=`、`=`、`+=`、`?=`、`ifeq/ifneq/ifdef/ifndef`、静态列表拼接、有限 workspace-local include、静态源码/目录/参数集合及架构 alias 比较，并 SHALL 对 include、展开、候选值和输出关系使用显式预算。

#### Scenario: Make 变量和条件选择 RISC-V 源码
- **WHEN** Makefile 通过受支持赋值、变量展开和互斥条件为 RISC-V target 选择源码或编译参数
- **THEN** evaluator SHALL 产生保留每次赋值、引用、条件和 SourceSpan 的确定选择事实
- **AND** Analyzer SHALL 能从 target architecture 追溯到最终源码或参数

#### Scenario: Make include 形成循环或越过预算
- **WHEN** 静态 include 循环或求值超过配置预算
- **THEN** evaluator SHALL 有界终止、保留已证明事实并返回 partial/unknown reason
- **AND** scanner MUST NOT 任意选择循环后的变量值

#### Scenario: Make recipe 或动态函数出现
- **WHEN** 输入包含 recipe、非白名单 function、动态 include、`eval`、普通 `$(shell ...)`、`!=` 或其他命令型求值
- **THEN** scanner SHALL 只保留对应 Evidence 和 unsupported/unknown Diagnostic
- **AND** 它 MUST NOT 启动 Make、shell 或任何外部命令

### Requirement: Autoconf 输入必须区分已生成 Shell 与受限 M4
已有 configure/config.guess/config.sub SHALL 通过锁定的 tree-sitter-bash 和 scanner-owned 有界分析恢复 assignment、case/if selector、匹配顺序、目标模式、精确探测、输出及退出依据；configure.ac/M4 SHALL 只识别批准的宏调用、字面参数和架构条件。分析 SHALL 区分多平台配置逻辑与已求值的 x86 配置结果，以配置单元、脚本版本及目标条件建立接受/拒绝/unknown 关系。scanner MUST NOT 运行 configure、辅助脚本、Autom4te、M4 或任意宏命令，MUST NOT 仅按架构关键词或 wildcard 判定支持。

#### Scenario: config.sub 接受 RISC-V triplet
- **WHEN** 已生成 config.sub 的完整可恢复路径对给定目标名称完成必要规范化、校验、有效输出并成功结束
- **THEN** scanner SHALL 建立 triplet selector 到实际 accepted path 的可追溯选择关系
- **AND** 不相关 x86 branch SHALL 仅在互斥条件完整时标记 inactive；仅包含目标模式不构成接受证明

#### Scenario: config.sub 缺少 RISC-V 和通用路径
- **WHEN** 完整可恢复且作用范围已知的架构选择只接受 x86，并证明目标进入拒绝路径而非可用通用 fallback
- **THEN** scanner SHALL 产生有配置/脚本范围的 missing_riscv_selection_path Observation 候选
- **AND** 它 MUST NOT 描述为 RISC-V 错误进入 x86 branch，也不得从不完整输入推断目标被拒绝

#### Scenario: M4 包含可执行宏
- **WHEN** configure.ac 包含 syscmd、esyscmd、动态 include 或未知参数展开
- **THEN** adapter SHALL 返回 unsupported/unknown Evidence 与 Diagnostic
- **AND** scanner MUST NOT 执行或模拟其副作用

#### Scenario: wildcard 分支失败与多个 case 共存
- **WHEN** 某一 case 的 wildcard 分支 exit 1，而同文件另一个 case 含 RISC-V 或 generic 名称
- **THEN** scanner SHALL 按各 case 的 selector、作用域、顺序和退出结果独立分析
- **AND** MUST NOT 借用另一个 case 的名称证明失败路径可用

#### Scenario: x86 成功构建提供配置结果
- **WHEN** 当前输入可见特定 x86 配置的 Makefile、config.h、config.status/log/cache 或 compile database
- **THEN** scanner SHALL 将它们作为 x86 已观察依据并隔离目标求值
- **AND** MUST NOT 因这些结果成功而替代 config.guess/sub 的 RISC-V 接受分析

### Requirement: 已有构建机器产物必须只读并保留配置身份
Frontend SHALL 通过严格版本/边界校验读取已经存在的 CMake File API reply、Meson introspection、CTest 元数据和 compilation database，SHALL 保留 configuration、target、source、argument、dependency、artifact 与 schema provenance，并 MUST NOT 运行 CMake、Meson、CTest 或 compiler 来生成或补全这些产物。

#### Scenario: 机器产物确认 RISC-V target
- **WHEN** 已有 metadata 同时提供可验证的 RISC-V 配置 identity、target 和 source/argument/dependency
- **THEN** Analyzer SHALL 可建立 observed configuration 到这些选择项的 proof
- **AND** proof SHALL 引用具体输入文件和 JSON pointer/entry identity

#### Scenario: 机器产物缺失架构或已经过期
- **WHEN** metadata 没有目标架构 provenance、引用缺失文件或与源码静态事实冲突
- **THEN** scanner SHALL 保留 observed candidate 并返回 partial/unknown
- **AND** metadata MUST NOT 静默覆盖其他 producer 或被视为 RISC-V selected

#### Scenario: 机器产物不存在
- **WHEN** 项目未提交 CMake/Meson/CTest 机器产物
- **THEN** 对应 adapter SHALL 保持 unavailable 并允许其他静态输入继续分析
- **AND** 缺失产物 MUST NOT 触发 configure/setup/test 命令

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

### Requirement: 构建选择必须形成有完整性状态的统一关系链
Build Selection Analyzer SHALL 将 architecture selector、build variable、condition/branch、source set、directory、compile/link argument、dependency、target、package 与 section 建立 scanner-owned Relation/ProofPath，并 SHALL 为每个目标 RISC-V 选择结果区分 `selected`、`inactive`、`not_selected` 和 `unknown`；所有端点与 Evidence 引用 MUST 存在于同一 AnalysisSnapshot。

构建选择 SHALL 独立于源码 proof 需求继续执行，并 SHALL 依照 `kb-scanner-large-project-performance` 以本阶段新增关系/proof 数量计算原有预算；继承源码图 MUST NOT 消耗该局部额度，数值上限与选择判定规则 MUST NOT 放宽。

#### Scenario: 构建选择继承大量无关源码图
- **WHEN** 相同构建事实接收少量或大量无关继承关系/proof
- **THEN** 本阶段新增选择链、局部预算截断和 Diagnostic SHALL 一致
- **AND** 未生成源码 proof MUST NOT 导致构建选择被跳过或被视为已验证

#### Scenario: 目标选择链完整
- **WHEN** 受支持输入完整证明某源码、参数或依赖进入 RISC-V target
- **THEN** AnalysisSnapshot SHALL 包含从 architecture/configuration selector 到 target item 的完整 proof
- **AND** 每条 Relation SHALL 保留 producer、条件、Evidence 和求值状态 provenance

#### Scenario: 分支被完整互斥条件排除
- **WHEN** 完整条件证明 x86 branch 对目标 RISC-V 不成立
- **THEN** Analyzer SHALL 将该 branch 及其依赖选择标记 inactive/not_selected
- **AND** 它 MUST NOT 删除 x86 Evidence 或把该状态直接解释为项目 ready

#### Scenario: 没有发现选择关系
- **WHEN** 输入缺失、表达式不支持或 provenance 不足以判断 target item
- **THEN** Analyzer SHALL 返回 unknown/partial reason
- **AND** 缺少 proof MUST NOT 被转换为 not_selected 或 inactive

### Requirement: 构建选择阶段必须产生非最终的可追溯 Observation
Build Selection Detector SHALL 仅从有效 build Relation/ProofPath 产生或补充 selected-x86、inactive-x86、missing-target-path 和 unknown Observation，并 SHALL 引用适用的源码/参数 KnowledgeEntry 与全部 Evidence/Relation ID；本阶段 MUST NOT 决定最终 blocker、severity 或 RISC-V readiness。

#### Scenario: RISC-V target 选择 x86 编译参数
- **WHEN** 完整 proof 表明 RISC-V target 选择了命中 compiler-derived x86 KnowledgeEntry 的参数
- **THEN** Detector SHALL 产生 `build_selected_x86_dependency` Observation
- **AND** 两份现有 Clang/GCC knowledge source provenance SHALL 原样可追溯

#### Scenario: x86 项只存在于 inactive branch
- **WHEN** 完整 selector proof 将 x86 源码或参数排除在 RISC-V target 外
- **THEN** Detector SHALL 记录 `build_inactive_x86_path` 上下文
- **AND** 最终 guarded/non-blocking 分类 SHALL 留给后续阶段

#### Scenario: 选择 proof 不完整
- **WHEN** relation 或 proof 因动态表达式、缺失输入或预算截断为 unknown/partial
- **THEN** Detector SHALL 保留 `build_selection_unknown` 和原因
- **AND** Detector MUST NOT 升级为 selected、inactive、非阻断或 ready

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

### Requirement: 构建选择必须为测试资产提供可追溯角色和目标关系
Build Frontend/Selection Analyzer SHALL 从已有 Make、CMake、Meson、CTest、compilation database 和 RPM `%check` 静态输入恢复 test target、test source、test argument/dependency、configuration 和 package section role，并 SHALL 将其以 scanner-owned Evidence/Relation/ProofPath 提供给 Test Selection Analyzer；动态命令或仅凭名称得到的角色 MUST 保持 unknown/candidate。

#### Scenario: CTest metadata 关联测试源码与目标
- **WHEN** 已有 CTest/CMake/Meson metadata 明确声明 test、target、source 和 configuration
- **THEN** Build Selection Analyzer SHALL 建立 configuration 到 test target/source 的选择关系
- **AND** 每条关系 SHALL 保留 JSON pointer、producer、selection status 和 Evidence 引用

#### Scenario: Make test target 对 RISC-V inactive
- **WHEN** 完整架构条件证明含 x86 依赖的 test target 对 RISC-V inactive/not_selected
- **THEN** build proof SHALL 保留该测试路径和 x86 Evidence
- **AND** Test Classifier MAY 据此形成 `x86_test_guarded`，但不得声明项目整体 ready

#### Scenario: 测试 recipe 包含可执行命令
- **WHEN** Make/RPM/CTest 测试定义包含 recipe、shell、Lua 或 test command
- **THEN** scanner SHALL 只恢复声明、参数和选择 Evidence，并将需执行部分保持 unsupported/unknown
- **AND** scanner MUST NOT 运行测试、构建工具或项目命令

### Requirement: 构建选择必须闭合到 selected source 和 x86 dependency
Build Selection Analyzer SHALL 从目标 selector/configuration、target、source membership、condition、argument 和 source Evidence 建立有界的 selector → target → source → x86 dependency Relation/ProofPath。只有路径中的每条关系均 complete、configuration 一致且目标为 selected 时，source dependency 才 SHALL 被标记为 reachable/selected；缺失或冲突输入 MUST 保持 partial/unknown。

#### Scenario: RISC-V 配置选择含 AVX 依赖的源码
- **WHEN** 完整构建关系证明目标配置选择某源码，且该源码具有 knowledge-backed x86 Evidence
- **THEN** Analyzer SHALL 产生引用 target、source、x86 Evidence 和全部 Relation ID 的 complete proof
- **AND** Detector/Classifier SHALL 可据此判断该依赖对目标可达

#### Scenario: 只有局部源码命中而缺少 target membership
- **WHEN** x86 Evidence 存在但无法证明源码属于 selected target
- **THEN** reachability SHALL 保持 unknown 并记录缺少的关系
- **AND** Analyzer MUST NOT 仅凭文本命中声称 selected 或 inactive

### Requirement: 构建参数聚合前必须保留逐 occurrence 证据
Build Frontend/Analyzer SHALL 为每个构建参数 occurrence 保留独立 Evidence、精确 start/end span、configuration 和 selection status，并 SHALL 通过稳定根因关系允许 Projector 聚合，而不是在分析阶段只保留每文件一个代表值。

#### Scenario: 四个 Makefile 包含二十四个 x86 flag occurrence
- **WHEN** 人工基线列出 24 个实际参数位置
- **THEN** AnalysisSnapshot SHALL 恢复且仅恢复这 24 个 occurrence，并逐项匹配 path、span、flag 和 selection status
- **AND** 最终 Finding 可聚合但 trace MUST 可还原全部 occurrence

#### Scenario: 相同 flag 在不同配置状态出现
- **WHEN** 同一 flag 分别位于 selected、inactive 或 unknown configuration
- **THEN** 每个 occurrence SHALL 保留自己的 configuration 和状态
- **AND** 聚合关系 MUST NOT 用一个 occurrence 的状态覆盖其他 occurrence

### Requirement: 构建闭包修正必须具有隔离单元与人工回归门禁
本 change 修改的 target/source resolver、reachability analyzer、occurrence collector 和 proof builder SHALL 分别映射到隔离单元测试，并 SHALL 在唯一 `kb-scanner-test` 容器中达到每模块至少 90% line / 80% branch。AVX build baseline 中已实现的 24 个 occurrence SHALL 从 deferred 记录迁入正式字段级回归。

#### Scenario: 运行构建分析单元门禁
- **WHEN** 独立容器执行 build-selection unit inventory
- **THEN** fake workspace/snapshot 测试 SHALL 覆盖 complete、inactive、partial、conflict、budget 和乱序输入并满足覆盖门槛
- **AND** 测试 MUST NOT 执行 make、cmake、compiler 或项目命令

#### Scenario: 运行 AVX 构建人工对照
- **WHEN** 新 scanner 扫描 AVX fixture
- **THEN** 24 个 flag occurrence SHALL 与正式人工 baseline 逐字段一致且无 missing/extra
- **AND** baseline MUST NOT 再把已实现的构建证据标为 deferred

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

### Requirement: Makefile 宏参数必须证明实际作用域再关联源码条件
Build Frontend/Normalizer/Analyzer SHALL 静态恢复受支持 CPPFLAGS/CFLAGS/CXXFLAGS 的已知赋值、追加及引用来源，识别 -DNAME、-DNAME=value、分离 token 的 -D NAME[=value] 与 -UNAME，保留原始位置、顺序、target/source 和 configuration。参数到源码条件宏的确定关系 SHALL 同时具有参数被编译 recipe 静态引用、源码目标归属和宏可见性证据；单独赋值或同名字符串 MUST NOT 构成启用证明。所有过程 MUST NOT 执行 Make、编译器或项目命令。

#### Scenario: 已证明 Make 参数启用当前源码
- **WHEN** 受支持 Makefile 的 CPPFLAGS 定义 -DUSE_AVX2，编译目标明确引用该变量且关联当前源码，源码在 #if defined(USE_AVX2) 下调用包装 intrinsic 的宏
- **THEN** Analyzer SHALL 提供参数来源、recipe 使用、目标源码、条件、宏调用/定义/replacement 到 intrinsic 的可验证关联
- **AND** 每条关系 SHALL 保留实际 Evidence、配置和选择状态，可在同一 Finding 自包含展示

#### Scenario: 参数赋值未被使用
- **WHEN** Makefile 声明 -DUSE_AVX2 但缺少其进入当前编译目标的静态引用证据
- **THEN** 参数 Fact SHALL 保留，作用于当前条件宏的结论 SHALL 为 unknown
- **AND** scanner MUST NOT 仅凭变量名为 CFLAGS 或宏同名断言已启用

#### Scenario: 参数属于其他目标
- **WHEN** -DUSE_AVX2 只在另一目标、配置、注释或无关文件出现
- **THEN** scanner SHALL 不将它作为当前命中的确定上游
- **AND** 原事实不得被删除，缺少当前目标输入时 SHALL 保持相应 unknown

#### Scenario: 动态构造不执行
- **WHEN** 参数或目标作用域依赖 shell、eval、无法解析的 recipe、response file 或外部未知值
- **THEN** 分析 SHALL 有界保留事实与 unknown reason
- **AND** scanner MUST NOT 执行构建来补齐证据

### Requirement: 构建宏绑定必须区分定义存在性与值并保留覆盖
参数宏绑定 SHALL 区分定义/取消、已定义性和值，遵循已证明的参数顺序、translation unit/include 可见性和局部 #define/#undef 作用。受支持条件至少 SHALL 包含 #ifdef/#ifndef、defined(NAME)、已知整数宏的 #if NAME 与受限等值比较；未知/不支持表达式和非等价配置 SHALL 保持 unknown，不推断编译器预定义宏与任意用户宏等价。

#### Scenario: 定义为零的宏
- **WHEN** 已证明当前配置使用 -DUSE_AVX2=0 且无后续覆盖
- **THEN** #ifdef USE_AVX2 SHALL 按已定义处理，而 #if USE_AVX2 SHALL 按假处理
- **AND** 链 SHALL 保存参数值与条件 Evidence，不把两者混成同一真假语义

#### Scenario: 取消或源内覆盖
- **WHEN** -U 或可见的源码 #undef/#define 改变先前 -D 的有效状态
- **THEN** 绑定 SHALL 保留原来源与覆盖依据，仅在顺序和作用域完整时给出确定结果
- **AND** 无法消解时 SHALL unknown，不得无条件使用最早或最后出现的同名文本

#### Scenario: 多级条件及宏包装
- **WHEN** intrinsic 经多级宏包装并处于多层已恢复条件内
- **THEN** Analyzer SHALL 保留每层宏/条件的实际关系，参数只关联到其确实控制的条件
- **AND** 宏调用展开关系 MUST NOT 被替代为条件宏启用关系

#### Scenario: 机器参数没有宏映射依据
- **WHEN** 只有 -mavx2 等机器选项，而没有适用的预定义宏语义证据
- **THEN** 参数 Fact SHALL 仍可检测，但参数到任意用户条件宏的绑定 SHALL 不成立
- **AND** scanner MUST NOT 猜测 -mavx2 等价于 -DUSE_AVX2

### Requirement: 构建宏桥接必须通过隔离单元与端到端人工链验收
每个新增或实质修改的 Make frontend、参数 normalizer、macro binding resolver、build/source graph 接线模块 SHALL 映射到隔离 unit suite，在独立 kb-scanner-test 容器中使项目整体及每个受影响模块达到 90% line / 90% branch，覆盖统计 SHALL 包含未被单测加载的项目自有可执行源码；大规模历史缺口 SHALL 报告并请求扩大范围，未达标不得完成验收。人工 fixture SHALL 逐字段验证参数、条件、宏定义/调用、intrinsic 的端点、位置、状态和闭包，而非仅验证 Finding 总数。

#### Scenario: 正反例验收
- **WHEN** 容器测试覆盖完整链、未使用变量、其他 target、-D0、-U、覆盖、未知输入和同名歧义
- **THEN** 正例 SHALL 给出可验证完整链，反例 SHALL 无伪启用边，未知项 SHALL 保留稳定断点
- **AND** fake 原生解析/文件/进程边界的隔离覆盖 SHALL 与真实语法组件测试分开计算

#### Scenario: 既有构建结果回归
- **WHEN** 运行既有 AVX/RPM/enum/候选及可用真实项目基线
- **THEN** 所有结论变化 SHALL 有新增证据和审校记录，纯投影变化不得改变风险判断
- **AND** GCC/Clang 事实哈希、静态边界、原局部图预算和 V1 字段合同 SHALL 保持不变

### Requirement: CMake 选择闭包必须独立于 Make 语法并隔离观察配置
Build Selection SHALL 按 CMake target identity、源码路径、参数作用域与配置闭合统一 Relation/ProofPath，不得套用 Make recipe 或源文件 basename 猜测。源码 RISC-V 静态推导 SHALL 与源环境 x86 compdb/File API 分别保留；冲突、过期或目标 provenance 不足 SHALL 明确 unknown。新增关系预算 SHALL 按本阶段新增量计算。

#### Scenario: 没有前置终止的明确目标
- **WHEN** 有界 CMake 入口将源码与 x86 参数明确加入目标且控制路径完整
- **THEN** scanner SHALL 建立配置/条件、target、source/argument 与局部 x86 依赖的可追溯关系
- **AND** 每个关系 SHALL 保留实际 Evidence 与配置 identity

#### Scenario: x86 观察配置与目标分析共存
- **WHEN** compdb 显示 x86 使用 AVX，但目标 CMake 分支选择通用源码或条件未知
- **THEN** scanner SHALL 按各配置保留证据，不得把 x86 已编译事实当作 RISC-V selected
- **AND** 未解决冲突 SHALL 输出具体断点而不是静默覆盖

### Requirement: 参数作用证明必须按编译使用实例保留多来源与顺序依据
Build Frontend/Normalizer/Analyzer SHALL 使用入口、target、TU、configuration 和 command/use occurrence 标识编译使用实例。参数 SHALL 保留 `-D/-U` 操作、值、真实使用点、来源 Evidence 集合和已证明的顺序；分散 token MUST NOT 合成虚假连续 span。参数赋值或规则存在本身 MUST NOT 证明目标必需或项目已执行构建。

#### Scenario: 参数标记与宏名位于不同赋值
- **WHEN** 两个已知变量分别提供 `-D` 和 `USE_AVX2=1`，同一明确 recipe 按顺序使用它们
- **THEN** Analyzer SHALL 用两个真实来源及使用点证明该参数，而不是因跨行丢弃所有来源或伪造 span
- **AND** 只有实际归属该编译使用实例的条件宏 SHALL 获得作用关系

#### Scenario: 同一源文件被两个目标编译
- **WHEN** 两个目标对相同源码分别使用 `-DUSE_AVX2=1` 和 `-UUSE_AVX2`
- **THEN** scanner SHALL 产生分开的作用实例和条件结果，不合并宏环境
- **AND** x86 compdb 的 observed 参数 MUST NOT 自动作为 RISC-V 静态选择证明

#### Scenario: 参数顺序无法证明
- **WHEN** 多个来源定义同一宏但输入不能确认实际覆盖顺序
- **THEN** scanner SHALL 保留全部来源及 unknown/conflicting 原因
- **AND** MUST NOT 用输出排序、文件行号或遍历顺序代替生效顺序

### Requirement: Make 参数桥接必须支持有界 include 条件赋值和明确自动变量
Make 参数桥接 SHALL 在既有安全边界内支持单字面本地 include、受支持 ifeq/ifneq/ifdef/ifndef/else/endif、简单变量引用以及 `=`/`:=`/`+=`/`?=` 的展开时机，并对可行分支分别求值后合流。明确单 target 规则中的 `$@` 和 `$<` SHALL 仅在 target、首个普通 prerequisite 及单 C/C++ 编译源码可确定时绑定；MUST NOT 执行 Make、shell、编译器或项目脚本。

#### Scenario: include 与目标架构条件提供编译参数
- **WHEN** 本地 include 定义参数变量，已支持目标架构条件选择其值，明确 recipe 通过 `$<` 编译源文件并以 `$@` 指定目标
- **THEN** scanner SHALL 保留 include、赋值、条件、引用、recipe 和源码的连续作用证明
- **AND** 正确 uname 结果 SHALL 按目标架构处理，不建模交叉编译误选

#### Scenario: 递归和立即变量展开不同
- **WHEN** `A = $(B)` 与 `C := $(B)` 之后 B 被重新赋值
- **THEN** 参数桥接 SHALL 按各自展开时机恢复值和来源，不统一替换为最后的 B
- **AND** 未知环境覆盖或未定义外部输入 SHALL 保持 unknown

#### Scenario: 未知条件合流
- **WHEN** 未知 Make 条件的可行分支对同一参数提供不同值
- **THEN** 合流 SHALL 保留冲突，不把两个分支顺序执行成确定结果
- **AND** 值与操作等价的所有可行分支 SHALL 能合流，同时保留各分支来源

#### Scenario: 动态和越界构造
- **WHEN** 遇到 eval、普通 shell、动态 include、模式/隐式规则、target-specific 继承、未知 `$^` 或根外路径
- **THEN** 相应参数作用 SHALL 保持 unknown 并给出稳定原因，原始 x86 事实 SHALL 保留
- **AND** 无法界定副作用范围时 SHALL 保守失效该环境，确定 inactive 的分支不得污染可达状态

### Requirement: 宏构建作用扩展必须通过隔离覆盖和规模验收
新增及实质修改的 frontend、normalizer、作用环境、图接线、consumer 和 projection 模块 SHALL 登记隔离单元测试，独立容器内项目整体及受影响模块 SHALL 达到至少 90% 行/90% 分支，统计包含未加载自有源码。新增/修改测试驱动逻辑 SHALL 另有隔离覆盖；组件、端到端或真实项目扫描 MUST NOT 代替单元覆盖。

#### Scenario: 完整验收
- **WHEN** apply 验证本轮能力
- **THEN** SHALL 分别报告单元命令/范围/排除项/覆盖/报告路径、人工 oracle、完整回归和真实项目差异
- **AND** GCC/Clang facts 哈希、默认 V2/显式 V1、三个工件及不执行项目命令边界 SHALL 不变

#### Scenario: 新功能带来额外成本
- **WHEN** 同镜像下运行固定 libarchive 822 文件、1万/2万稀疏/密集及宏/TU 规模样例
- **THEN** SHALL 在 2 CPU/2 GiB/无 swap、每扫描 300 秒以内且无 OOM 的条件下验收，保留分阶段时间、内存、查询计数、截断及工件体积
- **AND** 新功能相对成本 SHALL 作为诊断，不恢复旧相对耗时否决规则，不关闭既有能力或自动降低硬门槛
